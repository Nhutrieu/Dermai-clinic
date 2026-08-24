from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import torch
from torch.utils.data import DataLoader

from common import ImageSampleDataset, collect_samples, evaluation_transform


AI_SERVICE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AI_SERVICE_DIR))

from app.model import load_bundle  # noqa: E402
from app.ood import nearest_centroid_distance  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Đo tỷ lệ từ chối ảnh da hợp lệ của hồ sơ OOD.")
    parser.add_argument("--checkpoint", type=Path, default=Path("models/best_model.pth"))
    parser.add_argument("--profile", type=Path, default=Path("models/ood_profile.json"))
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--split", required=True)
    parser.add_argument("--batch-size", type=int, default=64)
    args = parser.parse_args()
    bundle = load_bundle(args.checkpoint, args.profile)
    if bundle is None or bundle.ood_profile is None:
        raise RuntimeError("Không nạp được model hoặc hồ sơ OOD.")
    samples = collect_samples(args.data, args.split, bundle.classes)
    loader = DataLoader(ImageSampleDataset(samples, evaluation_transform()), batch_size=args.batch_size)
    distances: list[float] = []
    for inputs, _targets in loader:
        embeddings = bundle.extract_embeddings(inputs.to(bundle.device)).cpu().numpy()
        distances.extend(nearest_centroid_distance(item, bundle.ood_profile) for item in embeddings)
    values = np.asarray(distances)
    threshold = bundle.ood_profile.distance_threshold
    print(json.dumps({
        "data": str(args.data),
        "split": args.split,
        "sample_count": len(values),
        "threshold": threshold,
        "false_rejection_count": int((values > threshold).sum()),
        "false_rejection_rate": float((values > threshold).mean()),
        "distance_p95": float(np.quantile(values, 0.95)),
        "distance_p99": float(np.quantile(values, 0.99)),
        "distance_max": float(values.max()),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
