"""Exclude all pre-inference dHash neighbors from the DermaCon-IN holdout."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path


def excluded_names(audit: dict, rows: list[dict]) -> set[str]:
    if audit.get("mode") != "audit_only" or audit.get("model_inference_performed") is not False:
        raise ValueError("Input must be a pre-inference audit-only report")
    if audit["dataset"]["images"] != len(rows):
        raise ValueError("Audit count does not match the original label manifest")
    independence = audit["independence_checks"]
    if independence["exact_hash_overlap_with_historical_train_and_test"] != 0:
        raise ValueError("Historical exact-image overlap is not zero")
    if independence["exact_hash_overlap_with_previously_inspected_sources"] != 0:
        raise ValueError("Previously inspected exact-image overlap is not zero")
    candidates = independence["potential_dhash_near_duplicates_for_manual_review"]
    if len(candidates) != independence["potential_dhash_near_duplicate_count"]:
        raise ValueError("Near-copy candidate count mismatch")
    names = {Path(candidate["new_image_path"].replace("\\", "/")).name for candidate in candidates}
    available = {Path(row["image_path"].replace("\\", "/")).name for row in rows}
    if not names.issubset(available) or len(available) != len(rows):
        raise ValueError("Candidate names do not match unique manifest images")
    return names


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--labels", type=Path, default=Path("SkinDisease/sources/dermacon_in/holdout/labels.csv"))
    parser.add_argument("--audit", type=Path, default=Path("ai-service/reports/dermacon_in_external_audit.json"))
    parser.add_argument("--output", type=Path, default=Path("SkinDisease/sources/dermacon_in/holdout/labels_no_near.csv"))
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(f"Preserving prior filtered labels: {args.output}")
    audit = json.loads(args.audit.read_text(encoding="utf-8"))
    with args.labels.open(encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source)
        fields = reader.fieldnames
        rows = list(reader)
    if not fields:
        raise ValueError("Original labels CSV lacks a header")
    names = excluded_names(audit, rows)
    kept = [row for row in rows if Path(row["image_path"]).name not in names]
    with args.output.open("x", encoding="utf-8", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=fields)
        writer.writeheader()
        writer.writerows(kept)
    report = {
        "rule": "Exclude every dHash distance <=3 neighbor of historical train/test/SCIN/PAD before inference; no label correction.",
        "original_images": len(rows),
        "excluded_images": len(rows) - len(kept),
        "remaining_images": len(kept),
        "excluded_by_project_label": dict(Counter(row["label"] for row in rows if Path(row["image_path"]).name in names)),
    }
    (args.output.parent / "near_exclusion_audit.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report), flush=True)


if __name__ == "__main__":
    main()
