from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, roc_auc_score, roc_curve
from sklearn.model_selection import train_test_split
from torch.utils.data import DataLoader, Dataset

from common import (
    CLASSES,
    IMAGE_EXTENSIONS,
    ImageSampleDataset,
    collect_samples,
    evaluation_transform,
    sha256_file,
)


AI_SERVICE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AI_SERVICE_DIR))

from app.image_quality import assess_image_quality  # noqa: E402
from app.model import load_bundle  # noqa: E402
from app.ood import is_out_of_scope  # noqa: E402


class PathDataset(Dataset):
    def __init__(self, paths: list[Path]):
        self.paths = paths
        self.transform = evaluation_transform()

    def __len__(self) -> int:
        return len(self.paths)

    def __getitem__(self, index: int):
        with Image.open(self.paths[index]) as image:
            return self.transform(image.convert("RGB")), index


def collect_valid_unique(paths: list[Path]) -> tuple[list[Path], dict[str, int]]:
    accepted: list[Path] = []
    seen: set[str] = set()
    invalid = duplicate = quality_rejected = 0
    for path in sorted(paths):
        try:
            digest = sha256_file(path)
            if digest in seen:
                duplicate += 1
                continue
            with Image.open(path) as image:
                image.load()
                if not assess_image_quality(image).accepted:
                    quality_rejected += 1
                    continue
        except (OSError, ValueError):
            invalid += 1
            continue
        seen.add(digest)
        accepted.append(path.resolve())
    return accepted, {
        "accepted": len(accepted),
        "invalid": invalid,
        "duplicates": duplicate,
        "quality_rejected": quality_rejected,
    }


def deterministic_wseg_split(
    paths: list[Path], seed: int
) -> tuple[list[Path], list[Path], list[Path]]:
    ranked = sorted(
        paths,
        key=lambda path: hashlib.sha256(
            f"{seed}:{sha256_file(path)}".encode("utf-8")
        ).hexdigest(),
    )
    train_end = round(len(ranked) * 0.70)
    validation_end = train_end + round(len(ranked) * 0.15)
    return ranked[:train_end], ranked[train_end:validation_end], ranked[validation_end:]


def local_ood_paths(root: Path) -> tuple[list[Path], list[str]]:
    paths: list[Path] = []
    categories: list[str] = []
    if not root.is_dir():
        return paths, categories
    for category_root in sorted(
        item for item in root.iterdir() if item.is_dir() and item.name not in CLASSES
    ):
        candidates = [
            path
            for path in category_root.rglob("*")
            if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
        ]
        valid, _stats = collect_valid_unique(candidates)
        paths.extend(valid)
        categories.extend([category_root.name] * len(valid))
    return paths, categories


def embeddings(bundle, dataset, batch_size: int) -> np.ndarray:
    loader = DataLoader(dataset, batch_size=batch_size, shuffle=False, num_workers=0)
    values: list[np.ndarray] = []
    for inputs, _targets in loader:
        values.append(bundle.extract_embeddings(inputs.to(bundle.device)).cpu().numpy())
    if not values:
        return np.empty((0, 0), dtype=np.float32)
    return np.concatenate(values)


def scores(classifier: LogisticRegression, matrix: np.ndarray) -> np.ndarray:
    if len(matrix) == 0:
        return np.asarray([], dtype=np.float64)
    return classifier.predict_proba(matrix)[:, 1]


def rejection_rate(values: np.ndarray, threshold: float) -> float | None:
    return float((values >= threshold).mean()) if len(values) else None


def false_rejection_rate(values: np.ndarray, threshold: float) -> float | None:
    return rejection_rate(values, threshold)


def binary_metrics(id_values: np.ndarray, ood_values: np.ndarray) -> dict:
    if not len(id_values) or not len(ood_values):
        return {}
    labels = np.concatenate([np.zeros(len(id_values)), np.ones(len(ood_values))])
    values = np.concatenate([id_values, ood_values])
    fpr, tpr, _thresholds = roc_curve(labels, values)
    reached = np.flatnonzero(tpr >= 0.95)
    return {
        "auroc": float(roc_auc_score(labels, values)),
        "aupr_ood": float(average_precision_score(labels, values)),
        "fpr95": float(fpr[reached[0]]) if len(reached) else 1.0,
    }


def current_profile_rates(bundle, matrices: dict[str, np.ndarray]) -> dict | None:
    if bundle.ood_profile is None:
        return None
    result: dict[str, float | None] = {}
    for name, matrix in matrices.items():
        if not len(matrix):
            result[name] = None
            continue
        decisions = [is_out_of_scope(item, bundle.ood_profile)[0] for item in matrix]
        result[name] = float(np.mean(decisions))
    return result


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Huấn luyện cổng phạm vi bằng ảnh vết thương WSeg và ảnh da ngoài phạm vi."
    )
    parser.add_argument("--checkpoint", type=Path, default=Path("models/best_model.pth"))
    parser.add_argument("--current-profile", type=Path, default=Path("models/ood_profile.json"))
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--scin", type=Path)
    parser.add_argument("--wseg", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("candidates/ood_profile_wseg.json"))
    parser.add_argument(
        "--report", type=Path, default=Path("reports/ai_evidence/wseg_scope_gate.json")
    )
    parser.add_argument(
        "--embedding-cache",
        type=Path,
        default=Path("candidates/wseg_scope_embeddings.npz"),
    )
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--max-id-fpr", type=float, default=0.05)
    parser.add_argument("--minimum-wound-recall", type=float, default=0.90)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    bundle = load_bundle(args.checkpoint, args.current_profile)
    if bundle is None:
        raise RuntimeError("Không nạp được model phân loại da.")

    id_train_all = collect_samples(args.data, "train", bundle.classes)
    labels = np.asarray([sample.label for sample in id_train_all])
    id_train, id_validation = train_test_split(
        id_train_all,
        test_size=0.2,
        random_state=args.seed,
        stratify=labels,
    )
    id_test = collect_samples(args.data, "test", bundle.classes)

    local_paths, local_categories = local_ood_paths(args.data / "train")
    if not local_paths:
        raise RuntimeError("Không tìm thấy ảnh da ngoài tám lớp mục tiêu.")
    local_indices = np.arange(len(local_paths))
    local_train_idx, local_validation_idx = train_test_split(
        local_indices,
        test_size=0.2,
        random_state=args.seed,
        stratify=np.asarray(local_categories),
    )
    local_train = [local_paths[index] for index in local_train_idx]
    local_validation = [local_paths[index] for index in local_validation_idx]
    local_test, _local_test_categories = local_ood_paths(args.data / "test")

    wound_candidates = [
        path
        for path in args.wseg.rglob("*")
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
    ]
    wound_paths, wound_quality = collect_valid_unique(wound_candidates)
    if len(wound_paths) < 100:
        raise RuntimeError("Tập WSeg hợp lệ quá nhỏ để huấn luyện an toàn.")
    wound_train, wound_validation, wound_test = deterministic_wseg_split(
        wound_paths, args.seed
    )

    print("Đang trích xuất đặc trưng cố định; không thay đổi model chẩn đoán 8 bệnh...")
    matrices = {
        "id_train": embeddings(
            bundle, ImageSampleDataset(id_train, evaluation_transform()), args.batch_size
        ),
        "id_validation": embeddings(
            bundle, ImageSampleDataset(id_validation, evaluation_transform()), args.batch_size
        ),
        "id_test": embeddings(
            bundle, ImageSampleDataset(id_test, evaluation_transform()), args.batch_size
        ),
        "local_train": embeddings(bundle, PathDataset(local_train), args.batch_size),
        "local_validation": embeddings(
            bundle, PathDataset(local_validation), args.batch_size
        ),
        "local_test": embeddings(bundle, PathDataset(local_test), args.batch_size),
        "wound_train": embeddings(bundle, PathDataset(wound_train), args.batch_size),
        "wound_validation": embeddings(
            bundle, PathDataset(wound_validation), args.batch_size
        ),
        "wound_test": embeddings(bundle, PathDataset(wound_test), args.batch_size),
    }

    scin_train_matrix = np.empty((0, matrices["id_train"].shape[1]), dtype=np.float32)
    scin_matrix = np.empty((0, matrices["id_train"].shape[1]), dtype=np.float32)
    scin_train_count = 0
    scin_count = 0
    if args.scin:
        scin_train_samples = collect_samples(args.scin, "train", bundle.classes)
        scin_samples = collect_samples(args.scin, "external_test", bundle.classes)
        scin_train_matrix = embeddings(
            bundle,
            ImageSampleDataset(scin_train_samples, evaluation_transform()),
            args.batch_size,
        )
        scin_matrix = embeddings(
            bundle, ImageSampleDataset(scin_samples, evaluation_transform()), args.batch_size
        )
        scin_train_count = len(scin_train_samples)
        scin_count = len(scin_samples)

    args.embedding_cache.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        args.embedding_cache,
        **matrices,
        scin_train=scin_train_matrix,
        scin_calibration=scin_matrix,
    )
    print(f"Đã lưu cache đặc trưng: {args.embedding_cache}")

    train_x = np.concatenate(
        [
            matrices["id_train"],
            scin_train_matrix,
            matrices["local_train"],
            matrices["wound_train"],
        ]
    )
    train_y = np.concatenate(
        [
            np.zeros(len(matrices["id_train"]) + len(scin_train_matrix)),
            np.ones(len(matrices["local_train"]) + len(matrices["wound_train"])),
        ]
    )
    classifier = LogisticRegression(
        max_iter=3000, class_weight="balanced", random_state=args.seed
    )
    classifier.fit(train_x, train_y)

    candidate_scores = {
        name: scores(classifier, matrix)
        for name, matrix in matrices.items()
        if name not in {"id_train", "local_train", "wound_train"}
    }
    scin_scores = scores(classifier, scin_matrix)
    calibration_groups = [candidate_scores["id_validation"]]
    if len(scin_scores):
        calibration_groups.append(scin_scores)
    threshold = max(
        float(np.quantile(group, 1.0 - args.max_id_fpr, method="higher"))
        for group in calibration_groups
    )

    test_id_fpr = false_rejection_rate(candidate_scores["id_test"], threshold)
    wound_test_recall = rejection_rate(candidate_scores["wound_test"], threshold)
    activation_ready = bool(
        test_id_fpr is not None
        and wound_test_recall is not None
        and test_id_fpr <= max(args.max_id_fpr * 1.5, 0.075)
        and wound_test_recall >= args.minimum_wound_recall
    )

    baseline_rates = current_profile_rates(
        bundle,
        {
            "id_test_false_rejection_rate": matrices["id_test"],
            "wound_test_rejection_rate": matrices["wound_test"],
            "local_test_rejection_rate": matrices["local_test"],
        },
    )
    report = {
        "method": "frozen_feature_logistic_scope_gate_with_wseg",
        "model_version": bundle.version,
        "seed": args.seed,
        "data": {
            "id_train": len(id_train),
            "id_validation": len(id_validation),
            "id_test_held_out": len(id_test),
            "local_ood_train": len(local_train),
            "local_ood_validation": len(local_validation),
            "local_ood_test": len(local_test),
            "wseg_train": len(wound_train),
            "wseg_validation": len(wound_validation),
            "wseg_test_held_out": len(wound_test),
            "wseg_quality_audit": wound_quality,
            "scin_id_train": scin_train_count,
            "scin_calibration": scin_count,
        },
        "score_threshold": threshold,
        "target_max_calibration_false_rejection_rate": args.max_id_fpr,
        "validation": {
            "internal_id_false_rejection_rate": false_rejection_rate(
                candidate_scores["id_validation"], threshold
            ),
            "scin_false_rejection_rate": false_rejection_rate(scin_scores, threshold),
            "local_ood_rejection_rate": rejection_rate(
                candidate_scores["local_validation"], threshold
            ),
            "wound_rejection_rate": rejection_rate(
                candidate_scores["wound_validation"], threshold
            ),
        },
        "held_out_test": {
            "id_false_rejection_rate": test_id_fpr,
            "local_ood_rejection_rate": rejection_rate(
                candidate_scores["local_test"], threshold
            ),
            "wound_rejection_rate": wound_test_recall,
            "id_vs_wound": binary_metrics(
                candidate_scores["id_test"], candidate_scores["wound_test"]
            ),
        },
        "previous_profile": baseline_rates,
        "activation_ready": activation_ready,
        "limitations": [
            "WSeg contains clinical wound images; a superficial scratch captured in a casual phone photo can still differ from this distribution.",
            "This gate rejects unsupported images and does not diagnose wounds, burns, or scratches.",
            "WSeg is CC BY-NC 4.0 and is used for research/demo evaluation only.",
        ],
    }
    profile = {
        "schema_version": 3,
        "model_version": bundle.version,
        "classes": bundle.classes,
        "method": "frozen_feature_logistic_scope_gate",
        "score_threshold": threshold,
        "linear_weights": classifier.coef_[0].tolist(),
        "linear_bias": float(classifier.intercept_[0]),
        "training_summary": report,
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(profile, ensure_ascii=False), encoding="utf-8")
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
