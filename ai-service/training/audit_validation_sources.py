"""Measure the frozen validation predictions separately by image source.

This is a descriptive analysis of existing labels, not a new test or relabeling.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path

from sklearn.metrics import classification_report

from common import CLASSES


SOURCE_PREFIXES = {
    "SkinDisease_original": "SkinDisease/train/",
    "SCIN_train_pool": "SkinDisease/scin-v1/train/",
}
MODELS = {
    "regularized": "regularized_prediction",
    "supcon": "supcon_prediction",
}


def source_of(path: str) -> str:
    matches = [name for name, prefix in SOURCE_PREFIXES.items() if path.startswith(prefix)]
    if len(matches) != 1:
        raise ValueError(f"Unknown validation image source: {path}")
    return matches[0]


def summarize(rows: list[dict]) -> dict:
    if not rows or len({row["sample_key"] for row in rows}) != len(rows):
        raise ValueError("Validation rows must be nonempty and have unique sample keys.")
    by_source = {name: [] for name in SOURCE_PREFIXES}
    for row in rows:
        if row["recorded_label"] not in CLASSES:
            raise ValueError("Unknown recorded label")
        if any(row[field] not in CLASSES for field in MODELS.values()):
            raise ValueError("Unknown prediction label")
        by_source[source_of(row["image_path"])].append(row)

    result = {}
    for source, subset in by_source.items():
        if not subset:
            raise ValueError(f"No validation images from {source}")
        truth = [row["recorded_label"] for row in subset]
        present = [name for name in CLASSES if name in truth]
        model_results = {}
        for model, field in MODELS.items():
            predicted = [row[field] for row in subset]
            report = classification_report(
                truth, predicted, labels=CLASSES, output_dict=True, zero_division=0
            )
            model_results[model] = {
                "accuracy": sum(a == b for a, b in zip(truth, predicted)) / len(subset),
                "macro_f1_present_classes": sum(report[name]["f1-score"] for name in present) / len(present),
                "macro_f1_all_eight_classes": report["macro avg"]["f1-score"],
                "per_class_recall": {
                    name: report[name]["recall"] for name in present
                },
            }
        result[source] = {
            "images": len(subset),
            "split_groups_not_verified_patients": len({row["case_key"] for row in subset}),
            "recorded_label_counts": dict(Counter(truth)),
            "any_model_disagreement_with_recorded_label": sum(
                row[MODELS["regularized"]] != row["recorded_label"]
                or row[MODELS["supcon"]] != row["recorded_label"]
                for row in subset
            ),
            "models": model_results,
        }
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--review-dir", type=Path,
        default=Path("ai-service/reports/validation_label_review"),
    )
    parser.add_argument(
        "--output", type=Path,
        default=Path("ai-service/reports/validation_source_audit.json"),
    )
    args = parser.parse_args()
    with (args.review_dir / "all_validation_predictions.csv").open(
        encoding="utf-8-sig", newline=""
    ) as source:
        rows = list(csv.DictReader(source))
    queue_summary = json.loads((args.review_dir / "summary.json").read_text(encoding="utf-8"))
    if len(rows) != queue_summary["validation_count"]:
        raise ValueError("Review CSV row count does not match its saved summary")
    by_source = summarize(rows)
    for model in MODELS:
        overall_truth = [row["recorded_label"] for row in rows]
        overall_prediction = [row[MODELS[model]] for row in rows]
        overall_report = classification_report(
            overall_truth, overall_prediction, labels=CLASSES, output_dict=True, zero_division=0
        )
        saved = queue_summary["models"][model]["validation_macro_f1"]
        if abs(overall_report["macro avg"]["f1-score"] - saved) > 1e-10:
            raise RuntimeError(f"Validation prediction audit differs from checkpoint: {model}")
    output = {
        "scope": "Descriptive source-stratified validation audit; labels are not newly verified.",
        "validation_count": len(rows),
        "validation_fingerprint_sha256": queue_summary["validation_fingerprint_sha256"],
        "sources": by_source,
        "limitations": [
            "SkinDisease_original has unverified source, label basis, and patient IDs.",
            "SCIN labels are mapped from retrospective dermatologist differentials, not pathological confirmation.",
            "SCIN_train_pool contains no SkinCancer, so it cannot assess eight-class performance alone.",
            "Both sources contributed to model training; neither source stratum is a new external test.",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({name: {"images": data["images"], "models": {
        model: {"accuracy": metrics["accuracy"], "macro_f1_present_classes": metrics["macro_f1_present_classes"]}
        for model, metrics in data["models"].items()}
    } for name, data in by_source.items()}, indent=2), flush=True)


if __name__ == "__main__":
    main()
