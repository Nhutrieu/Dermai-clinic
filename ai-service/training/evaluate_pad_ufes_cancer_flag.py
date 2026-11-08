"""Audit PAD-UFES-20 and test frozen SkinCancer flags without model selection."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import torch

from benchmark_paper_ensembles import model_probabilities, sha256
from common import CLASSES, IMAGE_EXTENSIONS, ImageSample, save_json, seed_everything, sha256_file
from train_v2 import BkNode, dhash


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


MALIGNANT = {"BCC", "SCC", "MEL"}
NONMALIGNANT = {"ACK", "NEV", "SEK"}
DIAGNOSES = MALIGNANT | NONMALIGNANT
HISTORICAL_SPLITS = ("train", "test", "scin-v1/train", "scin-v1/external_test")


def parse_args() -> argparse.Namespace:
    project = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-root", type=Path, default=project / "SkinDisease/sources/pad_ufes20/extracted")
    parser.add_argument("--known-data-root", type=Path, default=project / "SkinDisease")
    parser.add_argument("--manifest", type=Path, default=project / "ai-service/ensemble_research.json")
    parser.add_argument("--regularized", type=Path, default=project / "ai-service/candidates/convnext_tiny_regularized_seed42/evaluation/calibrated_model.pth")
    parser.add_argument("--supcon", type=Path, default=project / "ai-service/candidates/convnext_tiny_supcon_seed42/evaluation/calibrated_model.pth")
    parser.add_argument("--output", type=Path, default=project / "ai-service/reports/paper_ensemble_benchmark/pad_ufes_external_evaluation.json")
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--workers", type=int, default=0)
    parser.add_argument("--seed", type=int, default=42)
    return parser.parse_args()


def read_pad_records(root: Path) -> tuple[list[dict], dict]:
    metadata = root / "metadata.csv"
    if not metadata.is_file():
        raise FileNotFoundError(f"Missing official metadata.csv: {metadata}")
    images: dict[str, Path] = {}
    duplicate_names: set[str] = set()
    for path in root.rglob("*"):
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS:
            if path.name in images:
                duplicate_names.add(path.name)
            images[path.name] = path
    if duplicate_names:
        raise ValueError(f"Repeated image filenames in PAD folders: {sorted(duplicate_names)[:10]}")

    records: list[dict] = []
    missing_images: list[str] = []
    unknown_diagnoses: Counter[str] = Counter()
    biopsy: dict[str, Counter[str]] = defaultdict(Counter)
    with metadata.open("r", encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source)
        required = {"img_id", "patient_id", "diagnostic"}
        if not reader.fieldnames or not required.issubset(reader.fieldnames):
            raise ValueError(f"metadata.csv must contain {sorted(required)}")
        for row in reader:
            diagnosis = row["diagnostic"].strip().upper()
            if diagnosis not in DIAGNOSES:
                unknown_diagnoses[diagnosis] += 1
                continue
            image_id = Path(row["img_id"].strip()).name
            patient_id = row["patient_id"].strip()
            if not image_id or not patient_id:
                raise ValueError("PAD row lacks image or patient ID")
            path = images.get(image_id)
            if path is None:
                missing_images.append(image_id)
                continue
            biopsy[diagnosis][row.get("biopsed", "").strip()] += 1
            records.append({
                "img_id": image_id,
                "patient_id": patient_id,
                "diagnostic": diagnosis,
                "biopsed": row.get("biopsed", "").strip(),
                "path": path,
            })
    if not records:
        raise ValueError("No labeled PAD images found")
    if len({r["img_id"] for r in records}) != len(records):
        raise ValueError("metadata.csv repeats an image ID")
    unmatched_images = sorted(set(images) - {r["img_id"] for r in records})
    return records, {
        "metadata_rows_with_valid_diagnosis_and_image": len(records),
        "images_found": len(images),
        "missing_images": missing_images,
        "unknown_diagnoses": dict(unknown_diagnoses),
        "unmatched_image_count": len(unmatched_images),
        "diagnosis_counts": dict(Counter(r["diagnostic"] for r in records)),
        "patient_count": len({r["patient_id"] for r in records}),
        "biopsed_by_diagnosis": {key: dict(values) for key, values in biopsy.items()},
    }


def historical_images(root: Path) -> list[Path]:
    paths: list[Path] = []
    for split in HISTORICAL_SPLITS:
        folder = root / split
        if not folder.is_dir():
            raise FileNotFoundError(f"Missing historical image split: {folder}")
        paths.extend(path for path in folder.rglob("*") if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS)
    return paths


def audit_overlap(records: list[dict], known_paths: list[Path]) -> dict:
    historical_sha: dict[str, Path] = {}
    historical_dhash: list[int] = []
    for path in known_paths:
        historical_sha.setdefault(sha256_file(path), path)
        historical_dhash.append(dhash(path))
    tree = BkNode(historical_dhash[0], 0)
    for index, value in enumerate(historical_dhash[1:], start=1):
        tree.add(value, index)

    exact_matches = []
    near_matches = []
    pad_hashes: Counter[str] = Counter()
    for record in records:
        digest = sha256_file(record["path"])
        record["digest"] = digest
        pad_hashes[digest] += 1
        if digest in historical_sha:
            exact_matches.append(record["img_id"])
        candidates: list[int] = []
        tree.query(dhash(record["path"]), 3, candidates)
        if candidates:
            near_matches.append({
                "pad_img_id": record["img_id"],
                "historical_paths": [str(known_paths[i]) for i in candidates[:5]],
                "candidate_count": len(candidates),
            })
    return {
        "historical_image_count": len(known_paths),
        "historical_unique_sha256": len(historical_sha),
        "pad_repeated_byte_identical_images": sum(count - 1 for count in pad_hashes.values()),
        "exact_overlap_image_ids": exact_matches,
        "potential_dhash_distance_at_most_3_count": len(near_matches),
        "potential_dhash_matches": near_matches,
        "patient_overlap_status": "Unknown: historical SkinDisease does not have complete patient IDs.",
    }


def internal_duplicate_audit(records: list[dict]) -> dict:
    by_digest: dict[str, list[dict]] = defaultdict(list)
    for record in records:
        by_digest[record["digest"]].append(record)
    duplicates = [group for group in by_digest.values() if len(group) > 1]
    conflicts = [group for group in duplicates if len({row["diagnostic"] for row in group}) > 1]
    return {
        "byte_identical_image_groups": len(duplicates),
        "extra_byte_identical_images": sum(len(group) - 1 for group in duplicates),
        "diagnosis_conflict_groups": len(conflicts),
        "diagnosis_conflict_patients": sorted({row["patient_id"] for group in conflicts for row in group}),
        "diagnosis_conflict_images": [
            [{"img_id": row["img_id"], "patient_id": row["patient_id"], "diagnostic": row["diagnostic"]} for row in group]
            for group in conflicts
        ],
    }


def wilson(successes: int, total: int) -> list[float] | None:
    if total == 0:
        return None
    z = 1.959963984540054
    p = successes / total
    denominator = 1 + z * z / total
    center = (p + z * z / (2 * total)) / denominator
    radius = z * np.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / denominator
    return [float(center - radius), float(center + radius)]


def rate(flags: np.ndarray, indices: list[int]) -> dict:
    successes = int(flags[indices].sum())
    total = len(indices)
    return {"flagged": successes, "images": total, "rate": successes / total if total else None, "wilson_95pct": wilson(successes, total)}


def patient_sensitivity(flags: np.ndarray, records: list[dict]) -> dict:
    by_patient: dict[str, list[int]] = defaultdict(list)
    for index, record in enumerate(records):
        if record["diagnostic"] in MALIGNANT:
            by_patient[record["patient_id"]].append(index)
    successes = sum(any(flags[index] for index in indices) for indices in by_patient.values())
    return {
        "flagged_patients": int(successes),
        "malignant_patients": len(by_patient),
        "rate": successes / len(by_patient) if by_patient else None,
        "wilson_95pct": wilson(int(successes), len(by_patient)),
    }


def model_metrics_from_flags(flags: np.ndarray, records: list[dict]) -> dict:
    if len(flags) != len(records):
        raise ValueError("Flags and records have different lengths")
    indices = {name: [i for i, row in enumerate(records) if row["diagnostic"] == name] for name in sorted(DIAGNOSES)}
    malignant = [i for i, row in enumerate(records) if row["diagnostic"] in MALIGNANT]
    nonmalignant = [i for i, row in enumerate(records) if row["diagnostic"] in NONMALIGNANT]
    return {
        "malignant_image_sensitivity": rate(flags, malignant),
        "malignant_patient_sensitivity": patient_sensitivity(flags, records),
        "nonmalignant_skin_cancer_flag_rate": rate(flags, nonmalignant),
        "by_diagnosis": {name: rate(flags, indices[name]) for name in sorted(DIAGNOSES)},
    }


def model_metrics(probabilities: torch.Tensor, records: list[dict]) -> dict:
    flags = (probabilities.argmax(dim=1).numpy() == CLASSES.index("SkinCancer"))
    return model_metrics_from_flags(flags, records)


def subgroup_sensitivity(records: list[dict], flags: dict[str, np.ndarray], excluded_patients: set[str]) -> dict:
    indices = [i for i, record in enumerate(records) if record["patient_id"] not in excluded_patients]
    kept = [records[i] for i in indices]
    return {
        "excluded_patient_count": len(excluded_patients),
        "remaining_images": len(kept),
        "remaining_patients": len({record["patient_id"] for record in kept}),
        "results": {name: model_metrics_from_flags(model_flags[indices], kept) for name, model_flags in flags.items()},
    }


def paired_group_flag_difference(
    baseline: np.ndarray, candidate: np.ndarray, records: list[dict],
    diagnoses: set[str], seed: int, repetitions: int = 3000,
) -> dict:
    selected_by_patient: dict[str, list[int]] = defaultdict(list)
    for index, record in enumerate(records):
        if record["diagnostic"] in diagnoses:
            selected_by_patient[record["patient_id"]].append(index)
    groups = list(selected_by_patient.values())
    if not groups:
        raise ValueError("No patients for paired bootstrap")
    rng = np.random.default_rng(seed)
    differences = np.empty(repetitions)
    for iteration in range(repetitions):
        sampled = rng.integers(0, len(groups), size=len(groups))
        image_indices = np.fromiter((i for group_index in sampled for i in groups[group_index]), dtype=int)
        differences[iteration] = candidate[image_indices].mean() - baseline[image_indices].mean()
    selected_indices = [i for group in groups for i in group]
    return {
        "image_flag_rate_difference": float(candidate[selected_indices].mean() - baseline[selected_indices].mean()),
        "paired_patient_bootstrap_95pct": [float(value) for value in np.quantile(differences, [0.025, 0.975])],
        "diagnoses": sorted(diagnoses),
        "repetitions": repetitions,
        "seed": seed,
    }


def paired_patient_bootstrap(baseline: np.ndarray, candidate: np.ndarray, records: list[dict], seed: int, repetitions: int = 3000) -> dict:
    result = paired_group_flag_difference(baseline, candidate, records, MALIGNANT, seed, repetitions)
    result["malignant_image_sensitivity_difference"] = result.pop("image_flag_rate_difference")
    return result


def main() -> None:
    args = parse_args()
    if args.batch_size < 1:
        raise ValueError("--batch-size must be positive")
    seed_everything(args.seed)
    records, dataset_audit = read_pad_records(args.dataset_root)
    print(json.dumps({"dataset": dataset_audit["diagnosis_counts"], "patients": dataset_audit["patient_count"]}), flush=True)
    overlap_audit = audit_overlap(records, historical_images(args.known_data_root))
    duplicate_audit = internal_duplicate_audit(records)
    print(json.dumps({"exact_overlap": len(overlap_audit["exact_overlap_image_ids"]), "possible_near_overlap": overlap_audit["potential_dhash_distance_at_most_3_count"]}), flush=True)
    print(json.dumps({"pad_conflicting_image_groups": duplicate_audit["diagnosis_conflict_groups"]}), flush=True)
    excluded_patients = {r["patient_id"] for r in records if r["img_id"] in overlap_audit["exact_overlap_image_ids"]}
    records = [r for r in records if r["patient_id"] not in excluded_patients]
    if not records or not any(r["diagnostic"] in MALIGNANT for r in records):
        raise ValueError("No eligible malignant PAD images remain after exact-overlap exclusion")
    samples = [ImageSample(r["path"], 0, r["digest"], r["patient_id"]) for r in records]

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    entries = manifest["members"]
    if len(entries) != 3:
        raise ValueError("Frozen research manifest must have exactly three members")
    paths = {}
    for key, entry in zip(("baseline", "efficientnet_v2c", "resnet50"), entries):
        path = (args.manifest.parent / entry["checkpoint"]).resolve()
        if sha256(path) != entry["sha256"]:
            raise ValueError(f"Checkpoint SHA-256 differs from frozen manifest: {key}")
        paths[key] = path
    paths["convnext_regularized"] = args.regularized
    paths["convnext_supcon"] = args.supcon
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    probabilities = {}
    checkpoints = {}
    for name, path in paths.items():
        print(f"Inferring {name} ({len(samples)} PAD images) on {device}...", flush=True)
        info, predicted, _ = model_probabilities(path, {"pad_ufes20": samples}, device, args.batch_size, args.workers)
        checkpoints[name] = info
        probabilities[name] = predicted["pad_ufes20"]
    probabilities["ensemble_three_equal"] = torch.stack([probabilities[name] for name in ("baseline", "efficientnet_v2c", "resnet50")]).mean(dim=0)

    results = {name: model_metrics(probs, records) for name, probs in probabilities.items()}
    flags = {name: (probs.argmax(dim=1).numpy() == CLASSES.index("SkinCancer")) for name, probs in probabilities.items()}
    comparisons = {
        name: paired_patient_bootstrap(flags["baseline"], model_flags, records, args.seed)
        for name, model_flags in flags.items() if name != "baseline"
    }
    supcon_tradeoff = {
        "malignant_sensitivity": paired_patient_bootstrap(
            flags["convnext_regularized"], flags["convnext_supcon"], records, args.seed
        ),
        "nonmalignant_flag_rate": paired_group_flag_difference(
            flags["convnext_regularized"], flags["convnext_supcon"], records,
            NONMALIGNANT, args.seed,
        ),
    }
    near_image_ids = {match["pad_img_id"] for match in overlap_audit["potential_dhash_matches"]}
    near_patients = {record["patient_id"] for record in records if record["img_id"] in near_image_ids}
    conflict_patients = set(duplicate_audit["diagnosis_conflict_patients"])
    near_overlap_sensitivity = subgroup_sensitivity(records, flags, near_patients)
    conflict_sensitivity = subgroup_sensitivity(records, flags, conflict_patients)
    combined_sensitivity = subgroup_sensitivity(records, flags, near_patients | conflict_patients)
    report = {
        "source": "https://data.mendeley.com/datasets/zr7vgbcyr2/1",
        "protocol": "Frozen PAD-UFES-20 cancer-flag evaluation; argmax == SkinCancer; no PAD training, calibration or threshold selection.",
        "scope": "SkinCancer flag on smartphone lesions only; no valid eight-class accuracy estimate.",
        "dataset_audit": dataset_audit,
        "overlap_audit": overlap_audit,
        "internal_duplicate_audit": duplicate_audit,
        "excluded_exact_overlap_patients": sorted(excluded_patients),
        "evaluated_images": len(records),
        "evaluated_patients": len({r["patient_id"] for r in records}),
        "checkpoints": checkpoints,
        "results": results,
        "paired_malignant_sensitivity_vs_baseline": comparisons,
        "supcon_vs_regularized_tradeoff": supcon_tradeoff,
        "sensitivity_analysis_excluding_dhash_flagged_patients": near_overlap_sensitivity,
        "sensitivity_analysis_excluding_diagnosis_conflict_patients": conflict_sensitivity,
        "sensitivity_analysis_excluding_both_flagged_patient_sets": combined_sensitivity,
        "predictions": [
            {
                "img_id": row["img_id"], "patient_id": row["patient_id"],
                "diagnostic": row["diagnostic"], "biopsed": row["biopsed"],
                "skin_cancer_flag": {name: bool(model_flags[index]) for name, model_flags in flags.items()},
                "skin_cancer_probability": {name: float(probs[index, CLASSES.index("SkinCancer")]) for name, probs in probabilities.items()},
            }
            for index, row in enumerate(records)
        ],
        "limits": [
            "PAD nonmalignant labels ACK/NEV/SEK do not correspond to DermAI's other seven classes.",
            "dHash candidates require human review; matching hashes do not prove patient independence.",
            "Not a clinical screening validation or deployment recommendation.",
        ],
    }
    save_json(args.output, report)
    print(json.dumps({name: {
        "malignant_sensitivity": value["malignant_image_sensitivity"]["rate"],
        "nonmalignant_flag_rate": value["nonmalignant_skin_cancer_flag_rate"]["rate"],
    } for name, value in results.items()}, indent=2), flush=True)
    print(f"Saved {args.output}", flush=True)


if __name__ == "__main__":
    main()
