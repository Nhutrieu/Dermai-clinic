from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

from PIL import Image


DEFAULT_CLASSES = [
    "Acne",
    "Candidiasis",
    "Eczema",
    "Lupus",
    "Psoriasis",
    "SkinCancer",
    "Tinea",
    "Warts",
]
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def relative_paths(paths: list[Path], root: Path) -> list[str]:
    return [str(path.relative_to(root)).replace("\\", "/") for path in paths]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Kiểm tra tám lớp mục tiêu: ảnh hỏng, trùng nhãn và leakage train/test."
    )
    parser.add_argument("--data", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--all-classes", action="store_true")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Trả exit code 1 nếu có ảnh xung đột nhãn hoặc trùng train/test.",
    )
    args = parser.parse_args()

    classes = None if args.all_classes else set(DEFAULT_CLASSES)
    hashes: dict[str, list[Path]] = defaultdict(list)
    broken: list[Path] = []
    counts: Counter = Counter()
    missing: list[str] = []

    for split in ("train", "test"):
        split_root = args.data / split
        if not split_root.is_dir():
            raise FileNotFoundError(f"Không tìm thấy {split_root}")
        selected_classes = (
            sorted(path.name for path in split_root.iterdir() if path.is_dir())
            if classes is None
            else DEFAULT_CLASSES
        )
        for class_name in selected_classes:
            class_root = split_root / class_name
            if not class_root.is_dir():
                missing.append(f"{split}/{class_name}")
                continue
            for path in sorted(class_root.rglob("*")):
                if not path.is_file() or path.suffix.lower() not in IMAGE_EXTENSIONS:
                    continue
                counts[(split, class_name)] += 1
                try:
                    with Image.open(path) as image:
                        image.verify()
                    hashes[file_sha256(path)].append(path.resolve())
                except (OSError, ValueError):
                    broken.append(path.resolve())

    duplicate_groups = [paths for paths in hashes.values() if len(paths) > 1]
    cross_split = [
        paths
        for paths in duplicate_groups
        if {path.relative_to(args.data.resolve()).parts[0] for path in paths}
        >= {"train", "test"}
    ]
    label_conflicts = [
        paths
        for paths in duplicate_groups
        if len({path.parent.name for path in paths}) > 1
    ]

    report = {
        "data_root": str(args.data.resolve()),
        "classes": "all" if classes is None else DEFAULT_CLASSES,
        "counts": {
            split: {
                class_name: counts[(split, class_name)]
                for class_name in sorted({key[1] for key in counts if key[0] == split})
            }
            for split in ("train", "test")
        },
        "totals": {
            "images": sum(counts.values()),
            "broken": len(broken),
            "duplicate_groups": len(duplicate_groups),
            "cross_split_duplicate_groups": len(cross_split),
            "label_conflict_groups": len(label_conflicts),
        },
        "missing_class_folders": missing,
        "broken_files": relative_paths(broken, args.data.resolve()),
        "cross_split_duplicates": [
            relative_paths(paths, args.data.resolve()) for paths in cross_split
        ],
        "label_conflicts": [
            relative_paths(paths, args.data.resolve()) for paths in label_conflicts
        ],
    }

    for key, count in sorted(counts.items()):
        print(f"{key[0]:5} {key[1]:16} {count:5}")
    print(json.dumps(report["totals"], ensure_ascii=False))
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    if broken or missing or (args.strict and (label_conflicts or cross_split)):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
