"""Audit a new eight-class holdout and compare frozen checkpoint predictions.

The script refuses exact copies of images in the project's historical train/test
splits. Potential near copies, patient independence and labels require review.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path

import numpy as np
import torch
from sklearn.metrics import confusion_matrix

from benchmark_paper_ensembles import (
    model_probabilities,
    paired_accuracy_difference,
    report_metrics,
    sha256,
)
from common import CLASSES, IMAGE_EXTENSIONS, ImageSample, save_json, seed_everything, sha256_file
from train_v2 import BkNode, dhash


REQUIRED_COLUMNS = {"image_path", "label", "case_id", "source", "label_reviewer"}
PRIOR_INSPECTED_SOURCE_DIRS = (
    "caltech101",
    "dermacon_in",
    "dermatonet_2026",
    "hiba_2023",
    "med_node_2015",
    "milk10k_2025",
    "pad_ufes20",
    "skindisnet_v2",
    "slice3d_permissive_2024",
    "wseg",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--images-root", required=True, type=Path)
    parser.add_argument("--labels-csv", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument(
        "--manifest", type=Path,
        default=Path(__file__).resolve().parents[1] / "ensemble_research.json",
    )
    parser.add_argument("--secondary-manifest", type=Path, help="Frozen secondary checkpoints, reported descriptively")
    parser.add_argument(
        "--scene-split-manifest", type=Path,
        help="Frozen fresh B0/ConvNeXt checkpoints and their fixed 50:50 combination; descriptive only",
    )
    parser.add_argument("--inspected-fingerprints", type=Path, help="SHA-256/dHash manifest of images already used for exploratory evaluation")
    parser.add_argument("--audit-only", action="store_true", help="Validate labels and independence before model inference")
    parser.add_argument(
        "--known-data-root", type=Path,
        default=Path(__file__).resolve().parents[2] / "SkinDisease",
    )
    parser.add_argument("--min-per-class", type=int, default=20)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--workers", type=int, default=0)
    parser.add_argument("--seed", type=int, default=42)
    return parser.parse_args()


def read_new_samples(images_root: Path, labels_csv: Path) -> tuple[list[ImageSample], dict]:
    root = images_root.resolve(strict=True)
    samples: list[ImageSample] = []
    seen_paths: set[Path] = set()
    seen_digests: set[str] = set()
    sources: Counter[str] = Counter()
    reviewers: set[str] = set()
    with labels_csv.open("r", encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source)
        if not reader.fieldnames or not REQUIRED_COLUMNS.issubset(reader.fieldnames):
            raise ValueError(f"CSV cần các cột: {', '.join(sorted(REQUIRED_COLUMNS))}")
        for line_number, row in enumerate(reader, start=2):
            relative = Path(row["image_path"].strip())
            if relative.is_absolute() or ".." in relative.parts or relative.suffix.lower() not in IMAGE_EXTENSIONS:
                raise ValueError(f"Đường dẫn ảnh không hợp lệ ở dòng {line_number}")
            path = (root / relative).resolve(strict=True)
            if not path.is_relative_to(root):
                raise ValueError(f"Đường dẫn ảnh không hợp lệ ở dòng {line_number}")
            label = row["label"].strip()
            case_id = row["case_id"].strip()
            image_source = row["source"].strip()
            reviewer = row["label_reviewer"].strip()
            if label not in CLASSES or not case_id or not image_source or not reviewer:
                raise ValueError(f"Thiếu nhãn, mã ca, nguồn hoặc người xác nhận ở dòng {line_number}")
            if "::" in image_source or "::" in case_id:
                raise ValueError(f"Mã nguồn và mã ca không được chứa '::' ở dòng {line_number}")
            digest = sha256_file(path)
            if path in seen_paths or digest in seen_digests:
                raise ValueError(f"Ảnh lặp trong CSV ở dòng {line_number}")
            seen_paths.add(path)
            seen_digests.add(digest)
            sources[image_source] += 1
            reviewers.add(reviewer)
            samples.append(ImageSample(path, CLASSES.index(label), digest, f"{image_source}::{case_id}"))
    if not samples:
        raise ValueError("CSV không có ảnh.")
    dataset_digest = hashlib.sha256()
    for sample in samples:
        relative = sample.path.relative_to(root).as_posix()
        item = [relative, CLASSES[sample.label], sample.group_id, sample.digest]
        dataset_digest.update((json.dumps(item, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8"))
    return samples, {
        "sources": dict(sources),
        "label_reviewers": sorted(reviewers),
        "labels_csv_sha256": sha256_file(labels_csv),
        "ordered_dataset_fingerprint_sha256": dataset_digest.hexdigest(),
    }


def historical_image_paths(root: Path) -> list[Path]:
    splits = [root / "train", root / "test", root / "scin-v1" / "train", root / "scin-v1" / "external_test"]
    missing = [str(path) for path in splits if not path.is_dir()]
    if missing:
        raise FileNotFoundError(f"Thiếu dữ liệu lịch sử để kiểm tra ảnh trùng: {missing}")
    return [
        path
        for split in splits
        for path in split.rglob("*")
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
    ]


def historical_hashes(root: Path) -> set[str]:
    return {sha256_file(path) for path in historical_image_paths(root)}


def previously_inspected_image_paths(root: Path) -> list[Path]:
    """Include every locally retained source used in earlier model audits."""
    source_root = root / "sources"
    missing = [name for name in PRIOR_INSPECTED_SOURCE_DIRS if not (source_root / name).is_dir()]
    if missing:
        raise FileNotFoundError(
            f"Thiếu nguồn ảnh đã kiểm tra trước; không thể xác nhận test mới độc lập: {missing}"
        )
    return [
        path
        for name in PRIOR_INSPECTED_SOURCE_DIRS
        for path in (source_root / name).rglob("*")
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
    ]


def near_duplicate_candidates(
    samples: list[ImageSample], historical_paths: list[Path],
    new_root: Path, known_root: Path,
    inspected_dhash: list[tuple[int, str]] | None = None, radius: int = 3,
) -> list[dict]:
    """Flag dHash neighbours for human review; dHash alone is not proof of reuse."""
    if not historical_paths and not inspected_dhash:
        return []
    new_root = new_root.resolve()
    known_root = known_root.resolve()
    historical_dhash = [dhash(path) for path in historical_paths]
    known_descriptions = [str(path.resolve().relative_to(known_root)) for path in historical_paths]
    for value, description in inspected_dhash or []:
        historical_dhash.append(value)
        known_descriptions.append(description)
    tree = BkNode(historical_dhash[0], 0)
    for index, value in enumerate(historical_dhash[1:], start=1):
        tree.add(value, index)
    matches = []
    for sample in samples:
        value = dhash(sample.path)
        candidate_indices: list[int] = []
        tree.query(value, radius, candidate_indices)
        if candidate_indices:
            ordered = sorted(candidate_indices, key=lambda index: (value ^ historical_dhash[index]).bit_count())
            matches.append({
                "new_image_path": str(sample.path.relative_to(new_root)),
                "nearest_distance": (value ^ historical_dhash[ordered[0]]).bit_count(),
                "candidate_count": len(candidate_indices),
                "historical_examples": [known_descriptions[index] for index in ordered[:5]],
            })
    return matches


def load_inspected_fingerprints(path: Path) -> tuple[set[str], list[tuple[int, str]]]:
    manifest = json.loads(path.read_text(encoding="utf-8"))
    rows = manifest.get("fingerprints", [])
    if manifest.get("image_count") != len(rows):
        raise ValueError("Inspected image fingerprint count mismatch")
    source = manifest.get("source", "inspected-source")
    digests: set[str] = set()
    hashes: list[tuple[int, str]] = []
    for row in rows:
        digest = row["sha256"]
        fingerprint = row["dhash64"]
        if len(digest) != 64 or len(fingerprint) != 16:
            raise ValueError("Invalid image SHA-256 or dHash fingerprint")
        digests.add(digest)
        hashes.append((int(fingerprint, 16), f"{source}::{row['image_id']}"))
    return digests, hashes


def load_secondary_manifest(path: Path) -> list[tuple[str, Path]]:
    manifest = json.loads(path.read_text(encoding="utf-8"))
    entries = manifest.get("members", [])
    if not entries:
        raise ValueError("Secondary manifest must contain members")
    seen = {"baseline", "ensemble_three_equal", "efficientnet_v2c", "resnet50"}
    resolved = []
    for entry in entries:
        name = entry["id"]
        if not isinstance(name, str) or not name or name in seen:
            raise ValueError(f"Invalid or repeated secondary model id: {name}")
        seen.add(name)
        checkpoint = (path.parent / entry["checkpoint"]).resolve()
        if sha256(checkpoint) != entry["sha256"]:
            raise ValueError(f"Secondary checkpoint SHA-256 mismatch: {name}")
        resolved.append((name, checkpoint))
    return resolved


def load_scene_split_manifest(path: Path) -> list[tuple[str, Path]]:
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if manifest.get("combination") != "equal_probability_50_50":
        raise ValueError("Scene-split combination must be frozen at equal probability 50:50")
    entries = load_secondary_manifest(path)
    if [name for name, _ in entries] != ["scene_split_b0", "scene_split_convnext"]:
        raise ValueError("Scene-split manifest must list B0 followed by ConvNeXt")
    return entries


def source_breakdown(
    probabilities: torch.Tensor, targets: torch.Tensor, samples: list[ImageSample], seed: int,
) -> dict:
    """Report each contributing source separately; never hide source shift in one mean."""
    sources = sorted({sample.group_id.split("::", 1)[0] for sample in samples})
    result = {}
    for source in sources:
        indices = [
            index for index, sample in enumerate(samples)
            if sample.group_id.split("::", 1)[0] == source
        ]
        subset = [samples[index] for index in indices]
        subset_probabilities = probabilities[indices]
        subset_targets = targets[indices]
        result[source] = {
            "images": len(indices),
            "cases": len({sample.group_id for sample in subset}),
            "metrics": report_metrics(subset_probabilities, subset_targets),
            "confusion_matrix": confusion_counts(subset_probabilities, subset_targets),
            "case_cluster_uncertainty": case_cluster_intervals(
                subset_probabilities, subset_targets, subset, seed,
            ),
        }
    return result


def confusion_counts(probabilities: torch.Tensor, targets: torch.Tensor) -> list[list[int]]:
    return confusion_matrix(
        targets.numpy(), probabilities.argmax(dim=1).numpy(),
        labels=list(range(len(CLASSES))),
    ).tolist()


def case_cluster_intervals(
    probabilities: torch.Tensor, targets: torch.Tensor, samples: list[ImageSample],
    seed: int, repetitions: int = 2000,
) -> dict:
    """Bootstrap image-level accuracy and recall while resampling whole cases."""
    if len(probabilities) != len(targets) or len(targets) != len(samples):
        raise ValueError("Predictions, targets and samples have different lengths")
    predicted = probabilities.argmax(dim=1).numpy()
    truth = targets.numpy()
    correct = predicted == truth
    estimates = {}
    for label in [None, *range(len(CLASSES))]:
        indices = [i for i, target in enumerate(truth) if label is None or target == label]
        groups: dict[str, list[int]] = {}
        for index in indices:
            sample = samples[index]
            groups.setdefault(sample.group_id or sample.digest, []).append(index)
        if not groups:
            continue
        grouped_indices = [np.asarray(group, dtype=int) for group in groups.values()]
        rng = np.random.default_rng(seed + (label or 0) + 1)
        bootstraps = np.empty(repetitions, dtype=float)
        for iteration in range(repetitions):
            chosen = rng.integers(0, len(groups), size=len(groups))
            sampled_indices = np.concatenate([grouped_indices[i] for i in chosen])
            bootstraps[iteration] = correct[sampled_indices].mean()
        estimates["accuracy" if label is None else CLASSES[label]] = {
            "correct_images": int(correct[indices].sum()),
            "images": len(indices),
            "cases": len(groups),
            "estimate": float(correct[indices].mean()),
            "case_cluster_bootstrap_95pct": [float(value) for value in np.quantile(bootstraps, [0.025, 0.975])],
            "repetitions": repetitions,
        }
    return estimates


def main() -> None:
    args = parse_args()
    if args.min_per_class < 1:
        raise ValueError("--min-per-class phải >= 1")
    seed_everything(args.seed)
    samples, metadata = read_new_samples(args.images_root, args.labels_csv)
    historical_paths = historical_image_paths(args.known_data_root)
    prior_source_paths = previously_inspected_image_paths(args.known_data_root)
    known_paths = historical_paths + prior_source_paths
    new_digests = {sample.digest for sample in samples}
    overlap = new_digests & {sha256_file(path) for path in historical_paths}
    if overlap:
        raise ValueError(f"Bộ ảnh mới trùng chính xác {len(overlap)} ảnh trong dữ liệu lịch sử.")
    prior_source_overlap = new_digests & {sha256_file(path) for path in prior_source_paths}
    if prior_source_overlap:
        raise ValueError(
            f"Bộ ảnh mới trùng chính xác {len(prior_source_overlap)} ảnh từ nguồn ngoài đã đánh giá trước."
        )
    inspected_digests: set[str] = set()
    inspected_dhash: list[tuple[int, str]] = []
    if args.inspected_fingerprints is not None:
        inspected_digests, inspected_dhash = load_inspected_fingerprints(args.inspected_fingerprints)
        inspected_overlap = new_digests & inspected_digests
        if inspected_overlap:
            raise ValueError(f"Bộ ảnh mới trùng chính xác {len(inspected_overlap)} ảnh từ nguồn đã đánh giá trước.")
    counts = Counter(sample.label for sample in samples)
    case_groups = {
        index: {sample.group_id for sample in samples if sample.label == index}
        for index in range(len(CLASSES))
    }
    inadequate = {
        name: len(case_groups[index])
        for index, name in enumerate(CLASSES)
        if len(case_groups[index]) < args.min_per_class
    }
    if inadequate:
        raise ValueError(f"Chưa đủ {args.min_per_class} ca ở mỗi lớp: {inadequate}")

    near_matches = near_duplicate_candidates(
        samples, known_paths, args.images_root, args.known_data_root, inspected_dhash
    )
    dataset = {
        "images": len(samples),
        "cases": len({sample.group_id for sample in samples}),
        "per_class": {name: counts[index] for index, name in enumerate(CLASSES)},
        "cases_per_class": {name: len(case_groups[index]) for index, name in enumerate(CLASSES)},
        **metadata,
    }
    independence = {
        "historical_images_checked": len(historical_paths),
        "prior_source_images_checked": len(prior_source_paths),
        "prior_source_directories_checked": list(PRIOR_INSPECTED_SOURCE_DIRS),
        "previously_inspected_images_checked": len(prior_source_paths) + len(inspected_dhash),
        "inspected_fingerprint_manifest_sha256": sha256_file(args.inspected_fingerprints) if args.inspected_fingerprints else None,
        "exact_hash_overlap_with_historical_train_and_test": 0,
        "exact_hash_overlap_with_previously_inspected_sources": 0,
        "potential_dhash_near_duplicate_count": len(near_matches),
        "potential_dhash_near_duplicates_for_manual_review": near_matches,
        "patient_overlap_with_historical_data": "Cannot verify: historical dataset lacks complete patient IDs.",
        "source_and_reviewer_metadata": "Self-reported in input CSV; must be audited separately.",
    }
    if args.audit_only:
        report = {
            "mode": "audit_only",
            "dataset": dataset,
            "independence_checks": independence,
            "model_inference_performed": False,
            "review_required": "Check dHash candidates, source, patient IDs and clinician labels before interpreting model metrics.",
        }
        save_json(args.output, report)
        print(json.dumps({"images": len(samples), "cases": dataset["cases"], "potential_near_duplicates": len(near_matches), "output": str(args.output)}, ensure_ascii=False, indent=2))
        return

    if near_matches:
        raise ValueError(
            f"Có {len(near_matches)} ảnh nghi trùng với dữ liệu đã xem. "
            "Chạy --audit-only để xem các cặp rồi loại hoặc xác minh trước khi chấm mô hình."
        )

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    entries = manifest["members"]
    if len(entries) != 3:
        raise ValueError("Chỉ đánh giá tổ hợp ba model đã khóa trước; không dò tổ hợp trên test mới.")
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    probabilities = []
    checkpoint_info = []
    targets = None
    for entry in entries:
        path = (args.manifest.parent / entry["checkpoint"]).resolve()
        if sha256(path) != entry["sha256"]:
            raise ValueError(f"Checkpoint không khớp manifest: {path}")
        info, predicted, labels = model_probabilities(
            path, {"new_test": samples}, device, args.batch_size, args.workers
        )
        if targets is not None and not torch.equal(targets, labels["new_test"]):
            raise RuntimeError("Thứ tự ảnh khác nhau giữa các model.")
        targets = labels["new_test"]
        probabilities.append(predicted["new_test"])
        checkpoint_info.append(info)
    assert targets is not None
    baseline = probabilities[0]
    ensemble = torch.stack(probabilities).mean(dim=0)
    secondary_results = {}
    secondary_comparisons = {}
    secondary_checkpoint_info = {}
    secondary_uncertainty = {}
    secondary_probabilities = {}
    if args.secondary_manifest is not None:
        for name, path in load_secondary_manifest(args.secondary_manifest):
            info, predicted, labels = model_probabilities(
                path, {"new_test": samples}, device, args.batch_size, args.workers
            )
            if not torch.equal(targets, labels["new_test"]):
                raise RuntimeError(f"Prediction order differs for secondary model {name}")
            model_probability = predicted["new_test"]
            secondary_probabilities[name] = model_probability
            secondary_checkpoint_info[name] = info
            secondary_results[name] = report_metrics(model_probability, targets)
            secondary_uncertainty[name] = case_cluster_intervals(model_probability, targets, samples, args.seed)
            secondary_comparisons[name] = paired_accuracy_difference(
                baseline, model_probability, targets, samples, args.seed
            )
    scene_split_results = {}
    scene_split_comparisons = {}
    scene_split_uncertainty = {}
    scene_split_checkpoint_info = {}
    scene_split_probabilities = {}
    if args.scene_split_manifest is not None:
        expected_architectures = {
            "scene_split_b0": "efficientnet_b0",
            "scene_split_convnext": "convnext_tiny",
        }
        for name, path in load_scene_split_manifest(args.scene_split_manifest):
            info, predicted, labels = model_probabilities(
                path, {"new_test": samples}, device, args.batch_size, args.workers
            )
            if info["architecture"] != expected_architectures[name]:
                raise ValueError(f"Unexpected architecture for {name}: {info['architecture']}")
            if not torch.equal(targets, labels["new_test"]):
                raise RuntimeError(f"Prediction order differs for {name}")
            scene_split_checkpoint_info[name] = info
            scene_split_probabilities[name] = predicted["new_test"]
        scene_split_probabilities["scene_split_equal_ensemble"] = (
            scene_split_probabilities["scene_split_b0"]
            + scene_split_probabilities["scene_split_convnext"]
        ) / 2
        for name, model_probability in scene_split_probabilities.items():
            scene_split_results[name] = report_metrics(model_probability, targets)
            scene_split_uncertainty[name] = case_cluster_intervals(
                model_probability, targets, samples, args.seed
            )
            scene_split_comparisons[name] = paired_accuracy_difference(
                baseline, model_probability, targets, samples, args.seed
            )
    all_probabilities = {
        "baseline": baseline,
        "ensemble_three_equal": ensemble,
        **secondary_probabilities,
        **scene_split_probabilities,
    }
    if len(all_probabilities) != 2 + len(secondary_probabilities) + len(scene_split_probabilities):
        raise ValueError("Secondary model ids overlap with the frozen scene-split ids")
    report = {
        "protocol": "Primary: frozen equal-weight three-model ensemble versus current baseline. Secondary checkpoints descriptive only; no weight or winner selection on this test.",
        "dataset": dataset,
        "independence_checks": independence,
        "checkpoints": checkpoint_info,
        "baseline": report_metrics(baseline, targets),
        "ensemble": report_metrics(ensemble, targets),
        "paired_comparison": paired_accuracy_difference(baseline, ensemble, targets, samples, args.seed),
        "case_cluster_uncertainty": {
            "baseline": case_cluster_intervals(baseline, targets, samples, args.seed),
            "ensemble": case_cluster_intervals(ensemble, targets, samples, args.seed),
            "secondary_models": secondary_uncertainty,
        },
        "secondary_checkpoints": secondary_checkpoint_info,
        "secondary_models": secondary_results,
        "secondary_comparisons_vs_baseline": secondary_comparisons,
        "scene_split_manifest_sha256": (
            sha256_file(args.scene_split_manifest) if args.scene_split_manifest else None
        ),
        "scene_split_checkpoints": scene_split_checkpoint_info,
        "scene_split_models": scene_split_results,
        "scene_split_case_cluster_uncertainty": scene_split_uncertainty,
        "scene_split_comparisons_vs_baseline": scene_split_comparisons,
        "per_source": {
            name: source_breakdown(values, targets, samples, args.seed)
            for name, values in all_probabilities.items()
        },
        "confusion_matrices": {
            name: confusion_counts(values, targets)
            for name, values in all_probabilities.items()
        },
        "deployment_readiness": "Not determined by this script; evaluate OOD, latency, calibration and clinical review separately.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    save_json(args.output, report)
    print(json.dumps({
        "images": len(samples),
        "baseline_accuracy": report["baseline"]["accuracy"],
        "ensemble_accuracy": report["ensemble"]["accuracy"],
        "baseline_cancer_recall": report["baseline"]["per_class"]["SkinCancer"]["recall"],
        "ensemble_cancer_recall": report["ensemble"]["per_class"]["SkinCancer"]["recall"],
        "output": str(args.output),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
