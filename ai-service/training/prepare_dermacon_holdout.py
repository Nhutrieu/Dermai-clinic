"""Prepare a narrow, checksum-verified DermaCon-IN source holdout manifest."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path


OFFICIAL_MD5 = {
    "Skin_Metadata_original.csv": "0f74f664dae01c7cf8095d91ebc1d5f6",
    "train_split_original.csv": "89ffe5aabf31b2a993c62e201a1821b6",
    "test_split_original.csv": "1f514fb4f38178c00d173935b6513dd3",
}
DISEASE_MAP = {
    "Acne": "Acne",
    "Candidal Intertrigo": "Candidiasis",
    "Eczema": "Eczema",
    "Discoid Lupus Erythematosus": "Lupus",
    "Psoriasis": "Psoriasis",
    "Basal Cell Carcinoma": "SkinCancer",
    "Squamous Cell Carcinoma": "SkinCancer",
    "Melanoma": "SkinCancer",
    "Tinea Corporis": "Tinea",
    "Wart": "Warts",
    "Verruca Vulgaris": "Warts",
}
CLASSES = ("Acne", "Candidiasis", "Eczema", "Lupus", "Psoriasis", "SkinCancer", "Tinea", "Warts")
CSV_FIELDS = (
    "image_path", "label", "case_id", "source", "label_reviewer",
    "source_disease_label", "official_split", "diagnostic_confidence",
)


def md5_file(path: Path) -> str:
    digest = hashlib.md5()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_rows(path: Path) -> list[dict]:
    with path.open(encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source)
        expected = {"Image_name", "Subject_ID", "Disease_label", "Quality", "Gradability", "Confidence"}
        if not reader.fieldnames or not expected.issubset(reader.fieldnames):
            raise ValueError(f"Unexpected DermaCon-IN metadata columns in {path}")
        return list(reader)


def mapped_label(row: dict) -> str | None:
    label = DISEASE_MAP.get(row["Disease_label"].strip())
    if label is None:
        return None
    if row["Gradability"].strip() != "Yes":
        return None
    if not row["Quality"].strip().startswith("Yes, the quality is sufficient"):
        return None
    try:
        confidence = int(row["Confidence"])
    except ValueError as exc:
        raise ValueError("Mapped diagnosis has invalid confidence") from exc
    return label if confidence >= 4 else None


def prepare(metadata: list[dict], train: list[dict], test: list[dict]) -> tuple[list[dict], dict]:
    image_rows = {}
    for row in metadata:
        name = row["Image_name"].strip()
        subject = row["Subject_ID"].strip()
        if not name or Path(name).name != name or not subject or name in image_rows:
            raise ValueError("Missing, unsafe or repeated image/subject identifier")
        image_rows[name] = row
    split_by_name = {}
    subjects_by_split = defaultdict(set)
    for split_name, values in (("train", train), ("test", test)):
        for row in values:
            name = row["Image_name"].strip()
            if name not in image_rows or name in split_by_name:
                raise ValueError("Official split repeats or lacks an image")
            original = image_rows[name]
            if any(row[field].strip() != original[field].strip() for field in ("Subject_ID", "Disease_label")):
                raise ValueError("Official split metadata differs from original table")
            split_by_name[name] = split_name
            subjects_by_split[split_name].add(original["Subject_ID"].strip())
    if len(split_by_name) != len(metadata) or subjects_by_split["train"] & subjects_by_split["test"]:
        raise ValueError("Official subject-wise split is incomplete or overlapping")
    selected = []
    for name, row in sorted(image_rows.items()):
        label = mapped_label(row)
        if label is None:
            continue
        subject = row["Subject_ID"].strip()
        case_id = hashlib.sha256(f"DermaCon-IN::{subject}".encode()).hexdigest()[:24]
        selected.append({
            "image_path": f"images/{name}",
            "label": label,
            "case_id": case_id,
            "source": "DermaCon-IN-v1",
            "label_reviewer": "published_dermatologist_annotation",
            "source_disease_label": row["Disease_label"].strip(),
            "official_split": split_by_name[name],
            "diagnostic_confidence": row["Confidence"].strip(),
        })
    images = Counter(row["label"] for row in selected)
    cases = {label: len({row["case_id"] for row in selected if row["label"] == label}) for label in CLASSES}
    return selected, {
        "source": "DermaCon-IN-v1",
        "source_url": "https://dataverse.harvard.edu/dataset.xhtml?persistentId=doi:10.7910/DVN/W7OUZM",
        "license": "CC BY-NC-SA 4.0",
        "metadata_rows": len(metadata),
        "official_train_rows": len(train),
        "official_test_rows": len(test),
        "official_train_test_subject_overlap": 0,
        "selected_images": len(selected),
        "images_by_class": {label: images[label] for label in CLASSES},
        "subjects_by_class": cases,
        "selected_images_by_official_split": dict(Counter(row["official_split"] for row in selected)),
        "label_mapping": {label: DISEASE_MAP[label] for label in sorted(DISEASE_MAP)},
        "selection": "Exact disease labels only; Gradability Yes, diagnostic Quality Yes, Confidence >=4",
        "limitations": [
            "Lupus and SkinCancer have fewer than 20 distinct subjects.",
            "Published clinician labels are not uniformly pathology-confirmed.",
            "This is a disease-selected external source, not the target clinic's disease prevalence.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--metadata-root", type=Path, default=Path("SkinDisease/sources/dermacon_in"))
    parser.add_argument("--output", type=Path, default=Path("SkinDisease/sources/dermacon_in/holdout"))
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(f"Output exists; preserving prior holdout: {args.output}")
    for name, expected in OFFICIAL_MD5.items():
        if md5_file(args.metadata_root / name) != expected:
            raise ValueError(f"Official Dataverse MD5 mismatch: {name}")
    metadata = read_rows(args.metadata_root / "Skin_Metadata_original.csv")
    train = read_rows(args.metadata_root / "train_split_original.csv")
    test = read_rows(args.metadata_root / "test_split_original.csv")
    selected, report = prepare(metadata, train, test)
    report["official_original_file_md5"] = OFFICIAL_MD5
    args.output.mkdir(parents=True)
    with (args.output / "labels.csv").open("x", encoding="utf-8", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(selected)
    (args.output / "metadata_audit.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(json.dumps({"selected_images": report["selected_images"], "images_by_class": report["images_by_class"], "subjects_by_class": report["subjects_by_class"]}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
