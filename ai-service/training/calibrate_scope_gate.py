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
    parser = argparse.ArgumentParser(description="Hiệu chỉnh ngưỡng cổng phạm vi trên ảnh hợp lệ.")
    parser.add_argument("--checkpoint", type=Path, default=Path("models/best_model.pth"))
    parser.add_argument("--profile", type=Path, default=Path("models/ood_profile.json"))
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--split", required=True)
    parser.add_argument("--max-false-rejection-rate", type=float, default=0.05)
    parser.add_argument("--batch-size", type=int, default=64)
    args = parser.parse_args()
    bundle = load_bundle(args.checkpoint, args.profile)
    if bundle is None or bundle.ood_profile is None:
        raise RuntimeError("Không nạp được cổng phạm vi.")
    samples = collect_samples(args.data, args.split, bundle.classes)
    loader = DataLoader(ImageSampleDataset(samples, evaluation_transform()), batch_size=args.batch_size)
    scores: list[float] = []
    for inputs, _targets in loader:
        embeddings = bundle.extract_embeddings(inputs.to(bundle.device)).cpu().numpy()
        scores.extend(is_out_of_scope(item, bundle.ood_profile)[1] for item in embeddings)
    quantile = 1.0 - args.max_false_rejection_rate
    threshold = float(np.quantile(np.asarray(scores), quantile, method="higher"))
    payload = json.loads(args.profile.read_text(encoding="utf-8"))
    payload["score_threshold"] = threshold
    payload["calibration"] = {
        "data": str(args.data),
        "split": args.split,
        "sample_count": len(samples),
        "target_max_false_rejection_rate": args.max_false_rejection_rate,
        "score_threshold": threshold,
        "note": "This dataset is used for threshold calibration and is no longer an independent test set.",
    }
    args.profile.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(payload["calibration"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
