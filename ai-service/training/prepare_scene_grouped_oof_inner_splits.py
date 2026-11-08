"""Lock an inner checkpoint-selection split for each outer OOF fold."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from common import CLASSES, ImageSample, class_counts, grouped_stratified_split, save_json, sha256_file
from prepare_scene_grouped_oof_folds import EXPECTED_FINGERPRINT, OUTPUT as OUTER_MANIFEST, PROJECT


OUTPUT = PROJECT / "ai-service/reports/scene_grouped_oof_inner_seed42.json"


def checked_outer_rows() -> tuple[dict, list[ImageSample], dict[str, int]]:
    report = json.loads(OUTER_MANIFEST.read_text(encoding="utf-8"))
    if report["source_split_fingerprint_sha256"] != EXPECTED_FINGERPRINT or report["total_images"] != 5937:
        raise ValueError("Unexpected outer fold source")
    rows = report["images"]
    canonical = "".join(
        f"{row['fold']}\t{row['class']}\t{row['path']}\t{row['sha256']}\t{row['scene_or_case_group']}\n"
        for row in rows
    )
    if hashlib.sha256(canonical.encode("utf-8")).hexdigest() != report["manifest_sha256"]:
        raise ValueError("Outer fold manifest checksum mismatch")
    samples = []
    fold_by_path = {}
    for row in rows:
        path = (PROJECT / row["path"]).resolve()
        if not path.is_relative_to(PROJECT.resolve()) or path in fold_by_path:
            raise ValueError("Invalid or repeated image path in outer manifest")
        if sha256_file(path) != row["sha256"]:
            raise ValueError(f"Image changed: {path}")
        if row["class"] not in CLASSES or row["fold"] not in range(5):
            raise ValueError("Invalid class or fold in outer manifest")
        samples.append(ImageSample(path, CLASSES.index(row["class"]), row["sha256"], row["scene_or_case_group"]))
        fold_by_path[path] = row["fold"]
    return report, samples, fold_by_path


def main() -> None:
    if OUTPUT.exists():
        raise FileExistsError(f"Preserving prior inner-split plan: {OUTPUT}")
    outer, samples, fold_by_path = checked_outer_rows()
    plans = []
    for outer_fold in range(5):
        candidates = [sample for sample in samples if fold_by_path[sample.path] != outer_fold]
        held_out = [sample for sample in samples if fold_by_path[sample.path] == outer_fold]
        train, inner_validation = grouped_stratified_split(candidates, 0.15, 142 + outer_fold, len(CLASSES))
        group_sets = [
            {sample.group_id or sample.digest for sample in part}
            for part in (train, inner_validation, held_out)
        ]
        if any(group_sets[left] & group_sets[right] for left, right in ((0, 1), (0, 2), (1, 2))):
            raise ValueError(f"Case/scene group crosses training roles in outer fold {outer_fold}")
        if len(train) + len(inner_validation) + len(held_out) != len(samples):
            raise ValueError(f"Incomplete three-way split for outer fold {outer_fold}")
        counts = {role: class_counts(part) for role, part in (
            ("train", train), ("inner_validation", inner_validation), ("outer_holdout", held_out)
        )}
        if any(any(value == 0 for value in by_class.values()) for by_class in counts.values()):
            raise ValueError(f"A training role lacks a disease class in outer fold {outer_fold}")
        paths = sorted(sample.path.relative_to(PROJECT).as_posix() for sample in inner_validation)
        plans.append({
            "outer_fold": outer_fold,
            "train_images": len(train),
            "inner_validation_images": len(inner_validation),
            "outer_holdout_images": len(held_out),
            "class_images": counts,
            "inner_validation_paths": paths,
        })
    report = {
        "purpose": "Three-way grouped roles per outer fold: train, inner checkpoint selection, untouched outer OOF prediction.",
        "outer_manifest_sha256": outer["manifest_sha256"],
        "inner_val_ratio_of_outer_training_pool": 0.15,
        "inner_seed_rule": "142 + outer_fold",
        "folds": plans,
    }
    save_json(OUTPUT, report)
    print(json.dumps({
        "outer_manifest_sha256": report["outer_manifest_sha256"],
        "folds": [
            {key: value for key, value in plan.items() if key != "inner_validation_paths"}
            for plan in plans
        ],
    }, indent=2), flush=True)


if __name__ == "__main__":
    main()
