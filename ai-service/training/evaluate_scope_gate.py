from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
from torch.utils.data import DataLoader

from common import ImageSampleDataset, collect_samples, evaluation_transform


AI_SERVICE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AI_SERVICE_DIR))

from app.model import load_bundle  # noqa: E402
from app.ood import is_out_of_scope  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Đo tỷ lệ loại nhầm của cổng phạm vi trên ảnh hợp lệ.")
    parser.add_argument("--checkpoint", type=Path, default=Path("models/best_model.pth"))
    parser.add_argument("--profile", type=Path, default=Path("models/ood_profile.json"))
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--split", required=True)
    parser.add_argument("--batch-size", type=int, default=64)
    args = parser.parse_args()
    bundle = load_bundle(args.checkpoint, args.profile)
    if bundle is None or bundle.ood_profile is None:
        raise RuntimeError("Không nạp được cổng phạm vi.")
    samples = collect_samples(args.data, args.split, bundle.classes)
    loader = DataLoader(ImageSampleDataset(samples, evaluation_transform()), batch_size=args.batch_size)
    scores: list[float] = []
    rejected: list[bool] = []
    for inputs, _targets in loader:
        embeddings = bundle.extract_embeddings(inputs.to(bundle.device)).cpu().numpy()
        for embedding in embeddings:
            decision, score = is_out_of_scope(embedding, bundle.ood_profile)
            rejected.append(decision)
            scores.append(score)
    values = np.asarray(scores)
    print(json.dumps({
        "data": str(args.data),
        "split": args.split,
        "sample_count": len(samples),
        "false_rejection_count": int(np.sum(rejected)),
        "false_rejection_rate": float(np.mean(rejected)),
        "score_p95": float(np.quantile(values, 0.95)),
        "score_p99": float(np.quantile(values, 0.99)),
        "score_max": float(values.max()),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
