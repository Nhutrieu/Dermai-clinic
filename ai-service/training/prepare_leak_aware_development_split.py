"""Prepare a new research split grouping dHash neighbours without broad test exclusion.

This only changes future development data. It does not repair historical model
metrics or provide a patient-independent test.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

from common import CLASSES, save_json, sha256_file
from train_supcon_convnext import cleaned_train_validation
from train_v2 import BkNode, dhash, normalized_gray


PROJECT = Path(__file__).resolve().parents[2]


def split_fingerprint(train, validation) -> str:
    rows = sorted(
        (split, sample.path.relative_to(PROJECT).as_posix(), sample.digest)
        for split, samples in (("train", train), ("validation", validation))
        for sample in samples
    )
    digest = hashlib.sha256()
    for split, path, image_digest in rows:
        digest.update(f"{split}\t{path}\t{image_digest}\n".encode("utf-8"))
    return digest.hexdigest()


def same_label_near_overlap(train, validation, radius: int, pixel_correlation: float) -> tuple[int, int]:
    trees: dict[int, BkNode] = {}
    for index, sample in enumerate(train):
        value = dhash(sample.path)
        if sample.label not in trees:
            trees[sample.label] = BkNode(value, index)
        else:
            trees[sample.label].add(value, index)
    raw_count = 0
    verified_count = 0
    gray_cache = {}
    for sample in validation:
        matches: list[int] = []
        trees[sample.label].query(dhash(sample.path), radius, matches)
        raw_count += bool(matches)
        if not matches:
            continue
        left = normalized_gray(sample.path)
        for index in matches:
            right_path = train[index].path
            right = gray_cache.get(right_path)
            if right is None:
                right = normalized_gray(right_path)
                gray_cache[right_path] = right
            if float(np.mean(left * right)) >= pixel_correlation:
                verified_count += 1
                break
    return raw_count, verified_count


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=PROJECT / "SkinDisease")
    parser.add_argument("--extra-data", type=Path, default=PROJECT / "SkinDisease/scin-v1")
    parser.add_argument("--review", type=Path, default=PROJECT / "ai-service/reports/historical_validation_same_scene_review.json")
    parser.add_argument("--output", type=Path, default=PROJECT / "ai-service/reports/leak_aware_development_split_seed42.json")
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(f"Preserving prior split report: {args.output}")
    split_args = argparse.Namespace(
        data=args.data, extra_data=[args.extra_data], val_ratio=0.15,
        near_duplicate_distance=3, near_test_distance=0,
        near_pixel_correlation=0.85, reviewed_scene_manifest=args.review,
        seed=42,
    )
    train, validation, summary = cleaned_train_validation(split_args)
    membership = {sample.path: ("train", sample.digest) for sample in train}
    membership.update({sample.path: ("validation", sample.digest) for sample in validation})
    if len(membership) != len(train) + len(validation):
        raise ValueError("Image occurs in both new partitions")

    review = json.loads(args.review.read_text(encoding="utf-8"))
    reviewed_together = 0
    for pair in review["pairs"]:
        val_path = PROJECT.joinpath(*pair["validation_path"].split("/")).resolve()
        train_path = PROJECT.joinpath(*pair["train_path"].split("/")).resolve()
        for path, key in ((val_path, "validation_sha256"), (train_path, "train_sha256")):
            if not path.is_relative_to(PROJECT) or sha256_file(path) != pair[key]:
                raise ValueError(f"Reviewed image changed or left project: {path}")
        if val_path not in membership or train_path not in membership:
            raise ValueError("Reviewed same-scene pair missing from new split")
        if membership[val_path][0] != membership[train_path][0]:
            raise ValueError("Reviewed same-scene pair still crosses the new split")
        reviewed_together += 1

    scin_root = (args.extra_data / "train").resolve()
    case_splits: dict[Path, set[str]] = defaultdict(set)
    for path, (split, _digest) in membership.items():
        if path.is_relative_to(scin_root):
            case_splits[path.parent].add(split)
    mixed_cases = sum(len(splits) > 1 for splits in case_splits.values())
    if mixed_cases:
        raise ValueError(f"SCIN cases crossing new split: {mixed_cases}")

    print("Checking cross-partition dHash neighbours...", flush=True)
    raw_near_overlap, verified_near_overlap = same_label_near_overlap(train, validation, 3, 0.85)
    if verified_near_overlap:
        raise ValueError(f"Verified same-label neighbours cross new split: {verified_near_overlap}")
    group_sizes = Counter(sample.group_id for sample in [*train, *validation])
    report = {
        "scope": "New research-only train/validation split; not an independent test or a repaired historical metric.",
        "seed": 42,
        "near_test_exclusion_dhash_radius": 0,
        "train_validation_group_dhash_radius": 3,
        "train_validation_group_min_gray_correlation": 0.85,
        "summary": summary,
        "review_manifest_sha256": sha256_file(args.review),
        "reviewed_same_scene_pairs_kept_together": reviewed_together,
        "scin_cases_crossing_split": mixed_cases,
        "validation_images_with_same_label_train_neighbour_dhash_at_most_3": raw_near_overlap,
        "validation_images_with_verified_train_neighbour": verified_near_overlap,
        "group_size_audit": {
            "largest_group_images": max(group_sizes.values()),
            "groups_over_10_images": sum(size > 10 for size in group_sizes.values()),
        },
        "split_fingerprint_sha256": split_fingerprint(train, validation),
        "limitations": [
            "dHash grouping may merge different images and miss different views of the same patient.",
            "The old fixed test has been repeatedly inspected and cannot validate a new model independently.",
            "SkinDisease lacks verified patient IDs; this is not a patient-level split.",
        ],
    }
    save_json(args.output, report)
    print(json.dumps({key: report[key] for key in (
        "near_test_exclusion_dhash_radius", "train_validation_group_dhash_radius",
        "train_validation_group_min_gray_correlation",
        "reviewed_same_scene_pairs_kept_together", "scin_cases_crossing_split",
        "validation_images_with_same_label_train_neighbour_dhash_at_most_3",
        "validation_images_with_verified_train_neighbour",
        "group_size_audit", "split_fingerprint_sha256",
    )}, ensure_ascii=False, indent=2), flush=True)
    print(json.dumps(summary["totals"], ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
