from __future__ import annotations

import argparse
import ast
import csv
import hashlib
import json
import shutil
import sys
import time
import urllib.error
import urllib.request
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from PIL import Image, UnidentifiedImageError


SCIN_BUCKET = "https://storage.googleapis.com/dx-scin-public-data/"
SCIN_RELEASE = "1.0.0"
SCIN_LICENSE_URL = "https://github.com/google-research-datasets/scin/blob/main/LICENSE"
CLASSES = [
    "Acne",
    "Candidiasis",
    "Eczema",
    "Lupus",
    "Psoriasis",
    "SkinCancer",
    "Tinea",
    "Warts",
]

# Keep the map deliberately narrow. SCIN labels are retrospective differential
# diagnoses, so broad or clinically different aliases must not be folded together.
STRICT_LABEL_MAP = {
    "Acne": {"Acne"},
    "Candidiasis": {"Candida", "Candida intertrigo"},
    "Eczema": {"Eczema"},
    "Lupus": {"Cutaneous lupus"},
    "Psoriasis": {"Psoriasis"},
    "Tinea": {"Tinea"},
    "Warts": {"Verruca vulgaris"},
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Prepare a licensed, case-level SCIN supplement for DermAI."
    )
    parser.add_argument(
        "--metadata",
        type=Path,
        default=Path("ai-service/data-sources/scin"),
    )
    parser.add_argument(
        "--output", type=Path, default=Path("SkinDisease/scin-v1")
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=Path("ai-service/reports/scin_selection.json"),
    )
    parser.add_argument("--minimum-weight", type=float, default=0.5)
    parser.add_argument("--external-ratio", type=float, default=0.2)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--retries", type=int, default=3)
    parser.add_argument("--download-workers", type=int, default=8)
    return parser.parse_args()


def stable_rank(seed: int, class_name: str, case_id: str) -> str:
    value = f"{seed}:{class_name}:{case_id}".encode("utf-8")
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as source:
        return list(csv.DictReader(source))


def parse_weighted_label(raw: str) -> dict[str, float]:
    if not raw:
        return {}
    parsed = ast.literal_eval(raw)
    if not isinstance(parsed, dict):
        return {}
    return {str(name): float(weight) for name, weight in parsed.items()}


def select_cases(
    cases: list[dict[str, str]],
    labels: list[dict[str, str]],
    minimum_weight: float,
    external_ratio: float,
    seed: int,
) -> list[dict]:
    labels_by_case = {row["case_id"]: row for row in labels}
    selected: dict[str, list[dict]] = {name: [] for name in STRICT_LABEL_MAP}

    for case in cases:
        label_row = labels_by_case.get(case["case_id"])
        if not label_row:
            continue
        weighted = parse_weighted_label(label_row.get("weighted_skin_condition_label", ""))
        if not weighted:
            continue
        top_label = max(weighted, key=weighted.get)
        top_weight = weighted[top_label]
        if top_weight < minimum_weight:
            continue
        target = next(
            (name for name, aliases in STRICT_LABEL_MAP.items() if top_label in aliases),
            None,
        )
        if not target:
            continue
        images = [
            case.get(f"image_{index}_path", "").strip()
            for index in (1, 2, 3)
            if case.get(f"image_{index}_path", "").strip()
        ]
        if images:
            selected[target].append(
                {
                    "case_id": case["case_id"],
                    "class": target,
                    "source_label": top_label,
                    "weight": top_weight,
                    "images": images,
                }
            )

    result: list[dict] = []
    for class_name, class_cases in selected.items():
        ordered = sorted(
            class_cases,
            key=lambda item: stable_rank(seed, class_name, item["case_id"]),
        )
        external_count = max(1, round(len(ordered) * external_ratio)) if ordered else 0
        # At least one case remains available for training whenever possible.
        external_count = min(external_count, max(0, len(ordered) - 1))
        for index, item in enumerate(ordered):
            result.append(
                {**item, "split": "external_test" if index < external_count else "train"}
            )
    return result


def download(url: str, destination: Path, retries: int) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".part")
    for attempt in range(1, retries + 1):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "DermAI-research/1.0"})
            with urllib.request.urlopen(request, timeout=60) as response, temporary.open("wb") as output:
                shutil.copyfileobj(response, output)
            temporary.replace(destination)
            return
        except (OSError, urllib.error.URLError):
            temporary.unlink(missing_ok=True)
            if attempt == retries:
                raise
            time.sleep(attempt * 2)


def validate_image(path: Path) -> tuple[int, int]:
    try:
        with Image.open(path) as image:
            image.verify()
        with Image.open(path) as image:
            width, height = image.size
    except (OSError, UnidentifiedImageError) as error:
        raise ValueError(f"Invalid image {path}: {error}") from error
    if width < 64 or height < 64:
        raise ValueError(f"Image is too small ({width}x{height}): {path}")
    return width, height


def fetch_image(item: dict, image_path: str, output: Path, retries: int) -> dict:
    case_dir = output / item["split"] / item["class"] / item["case_id"]
    destination = case_dir / Path(image_path).name
    try:
        if not destination.exists():
            download(SCIN_BUCKET + image_path, destination, retries)
        width, height = validate_image(destination)
        return {
            "ok": True,
            "record": {
                **item,
                "source_path": image_path,
                "local_path": str(destination),
                "sha256": sha256_file(destination),
                "width": width,
                "height": height,
                "duplicate_of": None,
            },
        }
    except Exception as error:
        destination.unlink(missing_ok=True)
        return {
            "ok": False,
            "failure": {**item, "source_path": image_path, "error": str(error)},
        }


def main() -> None:
    args = parse_args()
    if not 0 < args.minimum_weight <= 1:
        raise ValueError("--minimum-weight must be in (0, 1].")
    if not 0 < args.external_ratio < 0.5:
        raise ValueError("--external-ratio must be in (0, 0.5).")
    if not 1 <= args.download_workers <= 16:
        raise ValueError("--download-workers must be between 1 and 16.")

    cases_path = args.metadata / "scin_cases.csv"
    labels_path = args.metadata / "scin_labels.csv"
    if not cases_path.exists() or not labels_path.exists():
        raise FileNotFoundError("SCIN metadata is missing. Download scin_cases.csv and scin_labels.csv first.")

    selected = select_cases(
        load_csv(cases_path),
        load_csv(labels_path),
        args.minimum_weight,
        args.external_ratio,
        args.seed,
    )
    for split in ("train", "external_test"):
        for class_name in CLASSES:
            (args.output / split / class_name).mkdir(parents=True, exist_ok=True)

    records: list[dict] = []
    failures: list[dict] = []
    jobs = [(item, image_path) for item in selected for image_path in item["images"]]
    with ThreadPoolExecutor(max_workers=args.download_workers) as executor:
        futures = [
            executor.submit(fetch_image, item, image_path, args.output, args.retries)
            for item, image_path in jobs
        ]
        for completed, future in enumerate(as_completed(futures), start=1):
            result = future.result()
            if result["ok"]:
                records.append(result["record"])
            else:
                failures.append(result["failure"])
            if completed % 50 == 0 or completed == len(jobs):
                print(
                    f"Downloaded/checked {completed}/{len(jobs)}; failures={len(failures)}",
                    flush=True,
                )

    # Prefer preserving the external copy when a known SCIN duplicate crosses the split.
    digests: dict[str, str] = {}
    usable: list[dict] = []
    duplicate_count = 0
    for record in sorted(
        records,
        key=lambda item: (item["split"] != "external_test", item["local_path"]),
    ):
        prior = digests.get(record["sha256"])
        if prior:
            Path(record["local_path"]).unlink(missing_ok=True)
            record["duplicate_of"] = prior
            record["local_path"] = None
            duplicate_count += 1
        else:
            digests[record["sha256"]] = record["local_path"]
            usable.append(record)
    case_counts = Counter((item["split"], item["class"]) for item in selected)
    image_counts = Counter((item["split"], item["class"]) for item in usable)
    report = {
        "source": "Skin Condition Image Network (SCIN)",
        "source_repository": "https://github.com/google-research-datasets/scin",
        "release": SCIN_RELEASE,
        "license": "SCIN Data Use License",
        "license_url": SCIN_LICENSE_URL,
        "restrictions": [
            "Attribution is required when material or adaptations are shared.",
            "Re-identification or re-linking of contributors is prohibited.",
        ],
        "selection": {
            "minimum_top_label_weight": args.minimum_weight,
            "external_case_ratio": args.external_ratio,
            "seed": args.seed,
            "strict_label_map": {key: sorted(value) for key, value in STRICT_LABEL_MAP.items()},
            "skin_cancer_excluded": "SCIN has too few retrospective differential labels for reliable SkinCancer supplementation.",
        },
        "case_counts": {
            split: {name: case_counts[(split, name)] for name in CLASSES}
            for split in ("train", "external_test")
        },
        "image_counts": {
            split: {name: image_counts[(split, name)] for name in CLASSES}
            for split in ("train", "external_test")
        },
        "downloaded_images": len(usable),
        "duplicates_removed": duplicate_count,
        "failures": failures,
        "records": usable,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({key: report[key] for key in ("case_counts", "image_counts", "downloaded_images", "duplicates_removed")}, indent=2), flush=True)
    if failures:
        print(f"Warning: {len(failures)} images failed; see {args.report}", file=sys.stderr)


if __name__ == "__main__":
    main()
