"""Create patient-separated development splits from the already inspected DermaCon source."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path

from sklearn.model_selection import StratifiedGroupKFold

from common import CLASSES
from train_v2 import BkNode, dhash


EXPECTED_MANIFEST_SHA256 = "cb0c4f2720bfdaa04f13da2dfd159c940c5ae3efb7be6577ee307c63828bb907"


def split_development(rows: list[dict], folds: int = 4, seed: int = 42) -> tuple[list[dict], list[dict]]:
    """Use one deterministic patient-disjoint fold with every class represented."""
    labels = [CLASSES.index(row["label"]) for row in rows]
    groups = [row["case_id"] for row in rows]
    splitter = StratifiedGroupKFold(n_splits=folds, shuffle=True, random_state=seed)
    for train_indices, validation_indices in splitter.split(range(len(rows)), labels, groups):
        training = [rows[index] for index in train_indices]
        validation = [rows[index] for index in validation_indices]
        if {row["label"] for row in training} != set(CLASSES):
            continue
        if {row["label"] for row in validation} != set(CLASSES):
            continue
        if {row["case_id"] for row in training} & {row["case_id"] for row in validation}:
            raise AssertionError("Patient overlap in development split")
        return training, validation
    raise ValueError("No patient-disjoint four-fold split contains all eight classes on both sides")


def remove_near(rows: list[dict], protected: list[dict], hashes: dict[str, int], radius: int = 3) -> tuple[list[dict], list[dict]]:
    tree = None
    for index, row in enumerate(protected):
        value = hashes[row["image_path"]]
        if tree is None:
            tree = BkNode(value, index)
        else:
            tree.add(value, index)
    if tree is None:
        raise ValueError("Protected split is empty")
    kept, excluded = [], []
    for row in rows:
        neighbors = []
        tree.query(hashes[row["image_path"]], radius, neighbors)
        (excluded if neighbors else kept).append(row)
    return kept, excluded


def summarize(rows: list[dict]) -> dict:
    counts = Counter(row["label"] for row in rows)
    return {
        "images": len(rows),
        "patients": len({row["case_id"] for row in rows}),
        "images_by_class": {name: counts[name] for name in CLASSES},
        "patients_by_class": {
            name: len({row["case_id"] for row in rows if row["label"] == name})
            for name in CLASSES
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--holdout-root", type=Path, default=Path("SkinDisease/sources/dermacon_in/holdout"))
    parser.add_argument("--output", type=Path, default=Path("SkinDisease/sources/dermacon_in/adaptation"))
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(f"Preserving prior split: {args.output}")
    manifest = args.holdout_root / "labels_no_near.csv"
    digest = hashlib.sha256(manifest.read_bytes()).hexdigest()
    if digest != EXPECTED_MANIFEST_SHA256:
        raise ValueError("DermaCon manifest differs from the frozen external evaluation")
    with manifest.open(encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source)
        fields = reader.fieldnames
        rows = list(reader)
    if not fields or len(rows) != 986:
        raise ValueError("Unexpected DermaCon manifest size or columns")
    names = [row["image_path"] for row in rows]
    if len(set(names)) != len(names):
        raise ValueError("Repeated image in manifest")
    for row in rows:
        if row["label"] not in CLASSES or row["official_split"] not in ("train", "test"):
            raise ValueError("Unexpected source label or official split")
        image = (args.holdout_root / row["image_path"]).resolve()
        if not image.is_relative_to((args.holdout_root / "images").resolve()) or not image.is_file():
            raise ValueError("Manifest image is missing or outside the source root")
    official_train = [row for row in rows if row["official_split"] == "train"]
    official_test = [row for row in rows if row["official_split"] == "test"]
    if len(official_train) != 803 or len(official_test) != 183:
        raise ValueError("Unexpected official split counts after pre-inference exclusions")
    if {row["case_id"] for row in official_train} & {row["case_id"] for row in official_test}:
        raise ValueError("Official splits share a patient")

    training, validation = split_development(official_train)
    hashes = {row["image_path"]: dhash(args.holdout_root / row["image_path"]) for row in rows}
    validation, val_near_test = remove_near(validation, official_test, hashes)
    training, train_near_protected = remove_near(training, [*validation, *official_test], hashes)
    if not training or not validation or {row["label"] for row in validation} != set(CLASSES):
        raise ValueError("Near-copy exclusions emptied a development class")
    sets = [set(row["case_id"] for row in part) for part in (training, validation, official_test)]
    if any(sets[left] & sets[right] for left, right in ((0, 1), (0, 2), (1, 2))):
        raise AssertionError("Patient overlap after exclusions")
    if len(training) + len(validation) + len(official_test) + len(val_near_test) + len(train_near_protected) != len(rows):
        raise AssertionError("Image accounting mismatch")
    args.output.mkdir(parents=True)
    for name, part in (("train", training), ("validation", validation), ("official_test", official_test)):
        with (args.output / f"{name}.csv").open("x", encoding="utf-8", newline="") as target:
            writer = csv.DictWriter(target, fieldnames=fields)
            writer.writeheader()
            writer.writerows(part)
    report = {
        "status": "development_only_after_first_external_evaluation",
        "input_manifest_sha256": digest,
        "seed": 42,
        "stratified_group_folds": 4,
        "near_duplicate_radius_bits": 3,
        "official_train_before_development_split": summarize(official_train),
        "train": summarize(training),
        "validation": summarize(validation),
        "official_test": summarize(official_test),
        "excluded_validation_near_official_test": summarize(val_near_test),
        "excluded_train_near_protected": summarize(train_near_protected),
        "all_splits_patient_disjoint": True,
        "official_test_previously_evaluated": True,
    }
    (args.output / "split_audit.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
