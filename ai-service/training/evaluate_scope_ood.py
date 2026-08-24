from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image
from torch.utils.data import DataLoader, Dataset

from common import CLASSES, IMAGE_EXTENSIONS, evaluation_transform


AI_SERVICE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AI_SERVICE_DIR))

from app.image_quality import assess_image_quality  # noqa: E402
from app.model import load_bundle  # noqa: E402
from app.ood import is_out_of_scope  # noqa: E402


class OodDataset(Dataset):
    def __init__(self, rows: list[tuple[Path, str]]):
        self.rows = rows
        self.transform = evaluation_transform()

    def __len__(self) -> int:
        return len(self.rows)

    def __getitem__(self, index: int):
        path, _category = self.rows[index]
        with Image.open(path) as image:
            return self.transform(image.convert("RGB")), index


def main() -> None:
    parser = argparse.ArgumentParser(description="Đo tỷ lệ chặn các nhóm OOD thật.")
    parser.add_argument("--checkpoint", type=Path, default=Path("models/best_model.pth"))
    parser.add_argument("--profile", type=Path, default=Path("models/ood_profile.json"))
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--split", default="train")
    parser.add_argument("--batch-size", type=int, default=64)
    args = parser.parse_args()
    bundle = load_bundle(args.checkpoint, args.profile)
    if bundle is None or bundle.ood_profile is None:
        raise RuntimeError("Không nạp được cổng phạm vi.")
    rows: list[tuple[Path, str]] = []
    quality_rejected = 0
    for root in sorted(item for item in (args.data / args.split).iterdir() if item.is_dir() and item.name not in CLASSES):
        for path in sorted(root.rglob("*")):
            if not path.is_file() or path.suffix.lower() not in IMAGE_EXTENSIONS:
                continue
            try:
                with Image.open(path) as image:
                    if not assess_image_quality(image).accepted:
                        quality_rejected += 1
                        continue
            except OSError:
                quality_rejected += 1
                continue
            rows.append((path, root.name))
    decisions: list[bool] = []
    loader = DataLoader(OodDataset(rows), batch_size=args.batch_size)
    for inputs, indices in loader:
        embeddings = bundle.extract_embeddings(inputs.to(bundle.device)).cpu().numpy()
        decisions.extend(is_out_of_scope(item, bundle.ood_profile)[0] for item in embeddings)
    print(json.dumps({
        "embedded_ood_count": len(rows),
        "quality_rejected_count": quality_rejected,
        "scope_gate_rejected_count": int(np.sum(decisions)),
        "scope_gate_rejection_rate": float(np.mean(decisions)),
        "combined_rejection_rate": float((quality_rejected + np.sum(decisions)) / (quality_rejected + len(rows))),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
