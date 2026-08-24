from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import torch
from torch.utils.data import DataLoader

from common import CLASSES, ImageSampleDataset, collect_samples, evaluation_transform


AI_SERVICE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AI_SERVICE_DIR))

from app.model import load_bundle  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Tạo hồ sơ đặc trưng để từ chối ảnh ngoài phạm vi.")
    parser.add_argument("--checkpoint", type=Path, default=Path("models/best_model.pth"))
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("models/ood_profile.json"))
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--workers", type=int, default=0)
    parser.add_argument("--quantile", type=float, default=0.995)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not 0.9 <= args.quantile < 1:
        raise ValueError("quantile phải nằm trong khoảng [0.9, 1).")
    bundle = load_bundle(args.checkpoint)
    if bundle is None:
        raise FileNotFoundError(args.checkpoint)
    samples = collect_samples(args.data, "train", bundle.classes)
    loader = DataLoader(
        ImageSampleDataset(samples, evaluation_transform()),
        batch_size=args.batch_size,
        shuffle=False,
        num_workers=args.workers,
        pin_memory=bundle.device.type == "cuda",
    )
    embeddings: list[np.ndarray] = []
    labels: list[np.ndarray] = []
    for inputs, targets in loader:
        batch = bundle.extract_embeddings(inputs.to(bundle.device, non_blocking=True))
        embeddings.append(batch.cpu().numpy())
        labels.append(targets.numpy())
    matrix = np.concatenate(embeddings)
    target_values = np.concatenate(labels)
    centroids = []
    for index in range(len(bundle.classes)):
        centroid = matrix[target_values == index].mean(axis=0)
        centroid /= max(float(np.linalg.norm(centroid)), 1e-12)
        centroids.append(centroid)
    centroid_matrix = np.stack(centroids)
    own_distances = 1.0 - np.sum(matrix * centroid_matrix[target_values], axis=1)
    payload = {
        "schema_version": 1,
        "model_version": bundle.version,
        "classes": bundle.classes,
        "method": "nearest_class_centroid_cosine_distance",
        "threshold_quantile": args.quantile,
        "distance_threshold": float(np.quantile(own_distances, args.quantile)),
        "sample_count": len(samples),
        "centroids": centroid_matrix.tolist(),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({key: value for key, value in payload.items() if key != "centroids"}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
