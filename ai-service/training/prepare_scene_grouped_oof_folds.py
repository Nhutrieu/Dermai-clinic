"""Lock five development folds grouped by known case and reviewed same-scene links.

These folds are for future out-of-fold training. They do not create model
predictions or an independent external test result.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
from sklearn.model_selection import StratifiedGroupKFold

from common import CLASSES, save_json
from prepare_leak_aware_development_split import split_fingerprint
from train_supcon_convnext import cleaned_train_validation


PROJECT = Path(__file__).resolve().parents[2]
EXPECTED_FINGERPRINT = "922f900cfed05bca4c5e9ea6b3ae65b4f64381363bed22ca2e007c23c7e6f9c4"
OUTPUT = PROJECT / "ai-service/reports/scene_grouped_oof_folds_seed42.json"


def make_folds(samples: list, seed: int = 42) -> tuple[list[dict], list[dict]]:
    samples = sorted(samples, key=lambda sample: sample.path.relative_to(PROJECT).as_posix())
    labels = np.array([sample.label for sample in samples], dtype=int)
    groups = [sample.group_id or sample.digest for sample in samples]
    group_labels: dict[str, set[int]] = defaultdict(set)
    for sample, group in zip(samples, groups):
        group_labels[group].add(sample.label)
    if any(len(values) != 1 for values in group_labels.values()):
        raise ValueError("One scene/case group contains conflicting disease labels")

    assignments = np.full(len(samples), -1, dtype=int)
    splitter = StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=seed)
    for fold, (_, held_out) in enumerate(splitter.split(np.zeros(len(samples)), labels, groups)):
        if np.any(assignments[held_out] >= 0):
            raise ValueError("An image was assigned to more than one fold")
        assignments[held_out] = fold
    if np.any(assignments < 0):
        raise ValueError("Some images have no fold")

    group_folds: dict[str, set[int]] = defaultdict(set)
    digest_folds: dict[str, set[int]] = defaultdict(set)
    rows = []
    for sample, group, fold in zip(samples, groups, assignments.tolist()):
        group_folds[group].add(fold)
        digest_folds[sample.digest].add(fold)
        rows.append({
            "path": sample.path.relative_to(PROJECT).as_posix(),
            "sha256": sample.digest,
            "class": CLASSES[sample.label],
            "scene_or_case_group": group,
            "fold": fold,
        })
    if any(len(values) != 1 for values in group_folds.values()):
        raise ValueError("A scene/case group crosses folds")
    if any(len(values) != 1 for values in digest_folds.values()):
        raise ValueError("Identical image bytes cross folds")

    summaries = []
    for fold in range(5):
        held_out = [row for row in rows if row["fold"] == fold]
        counts = Counter(row["class"] for row in held_out)
        if set(counts) != set(CLASSES):
            raise ValueError(f"Fold {fold} does not contain all eight classes")
        summaries.append({
            "fold": fold,
            "images": len(held_out),
            "scene_or_case_groups": len({row["scene_or_case_group"] for row in held_out}),
            "class_images": {name: counts[name] for name in CLASSES},
            "scin_images": sum(row["path"].startswith("SkinDisease/scin-v1/") for row in held_out),
        })
    return rows, summaries


def main() -> None:
    if OUTPUT.exists():
        raise FileExistsError(f"Preserving prior fold manifest: {OUTPUT}")
    review = PROJECT / "ai-service/reports/historical_validation_same_scene_review.json"
    split_args = argparse.Namespace(
        data=PROJECT / "SkinDisease", extra_data=[PROJECT / "SkinDisease/scin-v1"],
        val_ratio=0.15, near_duplicate_distance=3, near_test_distance=0,
        near_pixel_correlation=0.85, reviewed_scene_manifest=review, seed=42,
    )
    training, validation, _ = cleaned_train_validation(split_args)
    fingerprint = split_fingerprint(training, validation)
    if fingerprint != EXPECTED_FINGERPRINT or len(training) != 5047 or len(validation) != 890:
        raise ValueError("The previously audited development pool changed")
    rows, summaries = make_folds([*training, *validation])
    canonical = "".join(
        f"{row['fold']}\t{row['class']}\t{row['path']}\t{row['sha256']}\t{row['scene_or_case_group']}\n"
        for row in rows
    )
    report = {
        "purpose": "Grouped five-fold development manifest for future out-of-fold training and ensemble selection, not an independent test.",
        "grouping_limit": "SCIN case IDs and reviewed/dHash same-scene links are grouped; patient IDs are unavailable for many other images.",
        "source_split_fingerprint_sha256": fingerprint,
        "seed": 42,
        "fold_count": 5,
        "total_images": len(rows),
        "manifest_sha256": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
        "folds": summaries,
        "images": rows,
    }
    save_json(OUTPUT, report)
    print(json.dumps({key: value for key, value in report.items() if key != "images"}, indent=2), flush=True)


if __name__ == "__main__":
    main()
