import argparse
import hashlib
from collections import Counter, defaultdict
from pathlib import Path

from PIL import Image


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", required=True, type=Path)
    args = parser.parse_args()
    hashes, broken, counts = defaultdict(list), [], Counter()
    for split in ("train", "test"):
        for path in (args.data / split).glob("*/*"):
            if not path.is_file():
                continue
            counts[(split, path.parent.name)] += 1
            try:
                with Image.open(path) as image:
                    image.verify()
                digest = hashlib.sha256(path.read_bytes()).hexdigest()
                hashes[digest].append(path)
            except (OSError, ValueError):
                broken.append(path)
    leakage = [
        paths for paths in hashes.values()
        if {p.parents[1].name for p in paths} >= {"train", "test"}
    ]
    for key, count in sorted(counts.items()):
        print(f"{key[0]:5} {key[1]:24} {count:5}")
    print(f"Broken: {len(broken)}; cross-split duplicate groups: {len(leakage)}")
    if broken or leakage:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

