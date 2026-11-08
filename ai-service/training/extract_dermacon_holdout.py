"""Extract only the preselected DermaCon-IN images from verified source archives."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
import zipfile
from collections import defaultdict
from pathlib import Path

from PIL import Image


ARCHIVE_MD5 = {
    "DATASET_0.zip": "d937613230f152245ac787e8f071417c",
    "DATASET_1.zip": "56ff28d9a912b156afac086ca3227251",
}


def md5_file(path: Path) -> str:
    digest = hashlib.md5()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def archive_index(archives: list[Path], wanted: set[str]) -> dict[str, tuple[Path, str]]:
    found = {}
    for archive in archives:
        with zipfile.ZipFile(archive) as source:
            for member in source.infolist():
                name = Path(member.filename.replace("\\", "/")).name
                if member.is_dir() or name not in wanted:
                    continue
                if name in found:
                    raise ValueError(f"Selected image occurs in multiple archive entries: {name}")
                found[name] = archive, member.filename
    missing = wanted - set(found)
    if missing:
        raise ValueError(f"Missing {len(missing)} preselected images in official archives")
    return found


def extract(index: dict[str, tuple[Path, str]], destination: Path) -> dict:
    destination.mkdir(parents=True, exist_ok=True)
    hashes = {}
    by_archive = defaultdict(list)
    for name, (archive, member) in sorted(index.items()):
        by_archive[archive].append((name, member))
    for archive, entries in by_archive.items():
        with zipfile.ZipFile(archive) as source:
            for name, member in entries:
                target = destination / name
                if target.exists():
                    raise FileExistsError(f"Preserving existing review image: {target}")
                temporary = destination / f".{name}.partial"
                try:
                    with source.open(member) as original, temporary.open("xb") as result:
                        shutil.copyfileobj(original, result, length=1024 * 1024)
                    with Image.open(temporary) as image:
                        image.verify()
                    hashes[name] = hashlib.sha256(temporary.read_bytes()).hexdigest()
                    temporary.replace(target)
                finally:
                    temporary.unlink(missing_ok=True)
    names_by_digest = defaultdict(list)
    for name, digest in hashes.items():
        names_by_digest[digest].append(name)
    duplicates = [names for names in names_by_digest.values() if len(names) > 1]
    return {"extracted": len(hashes), "unique_sha256": len(names_by_digest), "exact_duplicate_groups": duplicates}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, default=Path("SkinDisease/sources/dermacon_in"))
    parser.add_argument("--holdout-root", type=Path, default=Path("SkinDisease/sources/dermacon_in/holdout"))
    args = parser.parse_args()
    archives = [args.source_root / name for name in ARCHIVE_MD5]
    for archive in archives:
        if md5_file(archive) != ARCHIVE_MD5[archive.name]:
            raise ValueError(f"Official archive MD5 mismatch: {archive.name}")
    with (args.holdout_root / "labels.csv").open(encoding="utf-8-sig", newline="") as source:
        rows = list(csv.DictReader(source))
    wanted = {Path(row["image_path"]).name for row in rows}
    if len(wanted) != len(rows) or not wanted:
        raise ValueError("Holdout label manifest has missing or repeated image names")
    index = archive_index(archives, wanted)
    result = extract(index, args.holdout_root / "images")
    report = {
        **result,
        "archive_md5": ARCHIVE_MD5,
        "selection_manifest": str(args.holdout_root / "labels.csv"),
        "scope": "Only images selected before inference were extracted; no model predictions computed.",
    }
    (args.holdout_root / "extraction_audit.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(result), flush=True)


if __name__ == "__main__":
    main()
