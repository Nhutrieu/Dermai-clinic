from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import torch
from PIL import Image
from sklearn.metrics import average_precision_score, roc_auc_score, roc_curve
from torch.utils.data import DataLoader, Dataset

from common import CLASSES, IMAGE_EXTENSIONS, ImageSampleDataset, collect_samples, evaluation_transform


AI_SERVICE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AI_SERVICE_DIR))

from app.image_quality import assess_image_quality  # noqa: E402
from app.model import load_bundle  # noqa: E402
from app.ood import nearest_centroid_distance  # noqa: E402


class PathDataset(Dataset):
    def __init__(self, paths: list[Path]):
        self.paths = paths
        self.transform = evaluation_transform()

    def __len__(self) -> int:
        return len(self.paths)

    def __getitem__(self, index: int):
        with Image.open(self.paths[index]) as image:
            return self.transform(image.convert("RGB")), index


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            value.update(chunk)
    return value.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description="Đánh giá OOD thật bằng các nhóm ngoài tám lớp mục tiêu.")
    parser.add_argument("--checkpoint", type=Path, default=Path("models/best_model.pth"))
    parser.add_argument("--profile", type=Path, default=Path("models/ood_profile.json"))
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--id-split", default="test")
    parser.add_argument("--ood-split", default="train")
    parser.add_argument("--output", type=Path, default=Path("reports/ai_evidence/ood_benchmark.json"))
    parser.add_argument("--batch-size", type=int, default=64)
    args = parser.parse_args()

    bundle = load_bundle(args.checkpoint, args.profile)
    if bundle is None or bundle.ood_profile is None:
        raise RuntimeError("Không nạp được model hoặc hồ sơ OOD.")
    id_samples = collect_samples(args.data, args.id_split, bundle.classes)
    id_hashes = {sample.digest for sample in id_samples}
    ood_root = args.data / args.ood_split
    ood_paths: list[Path] = []
    categories: list[str] = []
    quality_rejected = 0
    duplicate_rejected = 0
    for category_root in sorted(path for path in ood_root.iterdir() if path.is_dir() and path.name not in CLASSES):
        for path in sorted(category_root.rglob("*")):
            if not path.is_file() or path.suffix.lower() not in IMAGE_EXTENSIONS:
                continue
            if digest(path) in id_hashes:
                duplicate_rejected += 1
                continue
            try:
                with Image.open(path) as image:
                    quality = assess_image_quality(image)
            except OSError:
                quality_rejected += 1
                continue
            if not quality.accepted:
                quality_rejected += 1
                continue
            ood_paths.append(path)
            categories.append(category_root.name)
    if not ood_paths:
        raise RuntimeError("Không tìm thấy ảnh OOD hợp lệ.")

    def distances(loader: DataLoader) -> np.ndarray:
        values: list[float] = []
        for inputs, _targets in loader:
            embeddings = bundle.extract_embeddings(inputs.to(bundle.device)).cpu().numpy()
            values.extend(nearest_centroid_distance(item, bundle.ood_profile) for item in embeddings)
        return np.asarray(values)

    id_loader = DataLoader(ImageSampleDataset(id_samples, evaluation_transform()), batch_size=args.batch_size)
    ood_loader = DataLoader(PathDataset(ood_paths), batch_size=args.batch_size)
    id_scores = distances(id_loader)
    ood_scores = distances(ood_loader)
    labels = np.concatenate([np.zeros(len(id_scores)), np.ones(len(ood_scores))])
    scores = np.concatenate([id_scores, ood_scores])
    fpr, tpr, _thresholds = roc_curve(labels, scores)
    reached = np.flatnonzero(tpr >= 0.95)
    fpr95 = float(fpr[reached[0]]) if len(reached) else 1.0
    threshold = bundle.ood_profile.distance_threshold
    by_category: dict[str, dict] = {}
    grouped: dict[str, list[float]] = defaultdict(list)
    for category, score in zip(categories, ood_scores):
        grouped[category].append(float(score))
    for category, values in sorted(grouped.items()):
        array = np.asarray(values)
        by_category[category] = {
            "count": len(values),
            "rejected": int((array > threshold).sum()),
            "rejection_rate": float((array > threshold).mean()),
            "mean_distance": float(array.mean()),
        }
    report = {
        "method": "nearest_class_centroid_cosine_distance",
        "model_version": bundle.version,
        "id_count": len(id_scores),
        "ood_count": len(ood_scores),
        "quality_rejected_before_embedding": quality_rejected,
        "duplicate_rejected": duplicate_rejected,
        "auroc": float(roc_auc_score(labels, scores)),
        "aupr_ood": float(average_precision_score(labels, scores)),
        "fpr95": fpr95,
        "configured_threshold": threshold,
        "id_false_rejection_rate": float((id_scores > threshold).mean()),
        "ood_rejection_rate": float((ood_scores > threshold).mean()),
        "by_category": by_category,
        "limitation": "Near-OOD dermatology benchmark; it does not yet contain a labeled wound/scratch/burn cohort.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
