from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

import numpy as np
from PIL import Image
from torch.utils.data import DataLoader, Dataset

from common import IMAGE_EXTENSIONS, evaluation_transform, sha256_file


AI_SERVICE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AI_SERVICE_DIR))

from app.model import load_bundle  # noqa: E402


class PathDataset(Dataset):
    def __init__(self, paths: list[Path]):
        self.paths = paths
        self.transform = evaluation_transform()

    def __len__(self) -> int:
        return len(self.paths)

    def __getitem__(self, index: int):
        with Image.open(self.paths[index]) as image:
            return self.transform(image.convert("RGB")), index


def stable_rank(path: Path, seed: int) -> str:
    return hashlib.sha256(f"{seed}:{path.as_posix()}".encode("utf-8")).hexdigest()


def collect_by_category(root: Path, seed: int, max_per_category: int) -> dict[str, list[Path]]:
    categories: dict[str, list[Path]] = {}
    seen: set[str] = set()
    for category_root in sorted(item for item in root.iterdir() if item.is_dir()):
        valid: list[Path] = []
        for path in sorted(category_root.rglob("*")):
            if not path.is_file() or path.suffix.lower() not in IMAGE_EXTENSIONS:
                continue
            try:
                digest = sha256_file(path)
                if digest in seen:
                    continue
                with Image.open(path) as image:
                    image.verify()
            except (OSError, ValueError):
                continue
            seen.add(digest)
            valid.append(path.resolve())
        ranked = sorted(valid, key=lambda item: stable_rank(item, seed))
        if max_per_category > 0:
            ranked = ranked[:max_per_category]
        if len(ranked) >= 3:
            categories[category_root.name] = ranked
    if len(categories) < 50:
        raise RuntimeError("Tập ảnh ngoài phạm vi không đủ đa dạng để hiệu chỉnh an toàn.")
    return categories


def split_categories(
    categories: dict[str, list[Path]],
) -> tuple[list[Path], list[Path], list[Path], dict[str, dict[str, int]]]:
    train: list[Path] = []
    validation: list[Path] = []
    test: list[Path] = []
    counts: dict[str, dict[str, int]] = {}
    for category, paths in categories.items():
        train_end = max(1, round(len(paths) * 0.70))
        validation_count = max(1, round(len(paths) * 0.15))
        validation_end = min(len(paths) - 1, train_end + validation_count)
        category_train = paths[:train_end]
        category_validation = paths[train_end:validation_end]
        category_test = paths[validation_end:]
        train.extend(category_train)
        validation.extend(category_validation)
        test.extend(category_test)
        counts[category] = {
            "train": len(category_train),
            "validation": len(category_validation),
            "test": len(category_test),
        }
    return train, validation, test, counts


def embeddings(bundle, paths: list[Path], batch_size: int) -> np.ndarray:
    loader = DataLoader(
        PathDataset(paths), batch_size=batch_size, shuffle=False, num_workers=0
    )
    values: list[np.ndarray] = []
    for inputs, _indices in loader:
        values.append(bundle.extract_embeddings(inputs.to(bundle.device)).cpu().numpy())
    return np.concatenate(values).astype(np.float32)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Bổ sung ảnh tự nhiên đa dạng vào cache huấn luyện cổng ngoài phạm vi."
    )
    parser.add_argument("--base-cache", type=Path, default=Path("candidates/wseg_scope_embeddings.npz"))
    parser.add_argument("--checkpoint", type=Path, default=Path("models/best_model.pth"))
    parser.add_argument("--profile", type=Path, default=Path("models/ood_profile.json"))
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("candidates/broad_scope_embeddings.npz"))
    parser.add_argument("--manifest", type=Path, default=Path("reports/ai_evidence/broad_ood_dataset.json"))
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--max-per-category", type=int, default=100)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    bundle = load_bundle(args.checkpoint, args.profile)
    if bundle is None:
        raise RuntimeError("Không nạp được mô hình phân loại da.")
    cached = np.load(args.base_cache, allow_pickle=False)
    base = {name: cached[name].astype(np.float32) for name in cached.files}
    categories = collect_by_category(args.data, args.seed, args.max_per_category)
    train, validation, test, counts = split_categories(categories)
    matrices = {
        "broad_train": embeddings(bundle, train, args.batch_size),
        "broad_validation": embeddings(bundle, validation, args.batch_size),
        "broad_test": embeddings(bundle, test, args.batch_size),
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(args.output, **base, **matrices)
    manifest = {
        "source": "Caltech 101",
        "official_record": "https://data.caltech.edu/records/mzrjq-6wc02",
        "archive_md5": "3138e1922a9193bfa496528edbbc45d0",
        "purpose": "Negative/OOD examples only; never used as a disease label.",
        "seed": args.seed,
        "max_per_category": args.max_per_category,
        "categories": len(categories),
        "counts": {
            "train": len(train),
            "validation": len(validation),
            "test_held_out": len(test),
        },
        "category_counts": counts,
        "split_integrity": "Deterministic, category-stratified, mutually exclusive file paths.",
    }
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
