"""Prepare a clinician review queue from the frozen eight-class validation split.

Model disagreement is a review signal, never evidence that a recorded label is wrong.
Fixed-test images are hashed only to reconstruct the original split; no model
inference or review selection uses them. SCIN external holdout and PAD are unused.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
import shutil
from collections import Counter, defaultdict
from pathlib import Path

import torch

from benchmark_paper_ensembles import model_probabilities, report_metrics
from common import CLASSES, ImageSample, seed_everything
from train_supcon_convnext import cleaned_train_validation


WORKSPACE = Path(__file__).resolve().parents[2]
MACHINE_FIELDS = [
    "sample_key", "case_key", "image_path", "recorded_label", "review_signal",
    "clinical_priority", "regularized_prediction", "regularized_probability",
    "regularized_recorded_label_probability", "supcon_prediction",
    "supcon_probability", "supcon_recorded_label_probability",
]
REVIEW_FIELDS = [
    "sample_key", "review_image", "reviewer_id", "reviewed_label",
    "clinical_information_available", "review_notes",
]
SIGNAL_ORDER = {
    "both_disagree_same_prediction": 0,
    "both_disagree_different_predictions": 1,
    "one_disagrees": 2,
    "both_agree": 3,
}
CLINICAL_PRIORITY_CLASSES = {"Lupus", "SkinCancer"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=Path("SkinDisease"))
    parser.add_argument("--extra-data", action="append", type=Path, default=[Path("SkinDisease/scin-v1")])
    parser.add_argument(
        "--regularized", type=Path,
        default=Path("ai-service/candidates/convnext_tiny_regularized_seed42/evaluation/calibrated_model.pth"),
    )
    parser.add_argument(
        "--supcon", type=Path,
        default=Path("ai-service/candidates/convnext_tiny_supcon_seed42/evaluation/calibrated_model.pth"),
    )
    parser.add_argument(
        "--output", type=Path, default=Path("ai-service/reports/validation_label_review"),
    )
    parser.add_argument("--priority-limit", type=int, default=100)
    parser.add_argument("--control-count", type=int, default=20)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--workers", type=int, default=0)
    parser.add_argument("--val-ratio", type=float, default=0.15)
    parser.add_argument("--near-duplicate-distance", type=int, default=0)
    parser.add_argument("--seed", type=int, default=42)
    return parser.parse_args()


def review_signal(label: int, first: int, second: int) -> str:
    if first == label and second == label:
        return "both_agree"
    if first != label and second != label:
        return (
            "both_disagree_same_prediction" if first == second
            else "both_disagree_different_predictions"
        )
    return "one_disagrees"


def relative_image_path(sample: ImageSample) -> str:
    return sample.path.resolve().relative_to(WORKSPACE).as_posix()


def sample_fingerprint(samples: list[ImageSample]) -> str:
    digest = hashlib.sha256()
    for sample in samples:
        digest.update(
            f"{relative_image_path(sample)}\t{sample.digest}\t{sample.label}\n".encode("utf-8")
        )
    return digest.hexdigest()


def create_rows(samples: list[ImageSample], first: torch.Tensor, second: torch.Tensor) -> list[dict]:
    if first.shape != second.shape or first.shape != (len(samples), len(CLASSES)):
        raise ValueError("Probability arrays do not match validation samples and class count.")
    rows = []
    for index, sample in enumerate(samples):
        first_label = int(first[index].argmax())
        second_label = int(second[index].argmax())
        signal = review_signal(sample.label, first_label, second_label)
        path = relative_image_path(sample)
        case_identity = sample.group_id or sample.digest
        involved = {CLASSES[sample.label], CLASSES[first_label], CLASSES[second_label]}
        rows.append({
            "sample_key": hashlib.sha256(f"{path}\t{sample.digest}".encode()).hexdigest()[:20],
            "case_key": hashlib.sha256(case_identity.encode()).hexdigest()[:20],
            "image_path": path,
            "recorded_label": CLASSES[sample.label],
            "review_signal": signal,
            "clinical_priority": int(bool(involved & CLINICAL_PRIORITY_CLASSES)),
            "regularized_prediction": CLASSES[first_label],
            "regularized_probability": round(float(first[index, first_label]), 6),
            "regularized_recorded_label_probability": round(float(first[index, sample.label]), 6),
            "supcon_prediction": CLASSES[second_label],
            "supcon_probability": round(float(second[index, second_label]), 6),
            "supcon_recorded_label_probability": round(float(second[index, sample.label]), 6),
        })
    return rows


def choose_review_rows(rows: list[dict], priority_limit: int, control_count: int, seed: int) -> tuple[list[dict], list[dict]]:
    if priority_limit < 0 or control_count < 0:
        raise ValueError("Review counts cannot be negative.")
    discordant = sorted(
        (row for row in rows if row["review_signal"] != "both_agree"),
        key=lambda row: (
            SIGNAL_ORDER[row["review_signal"]],
            -row["clinical_priority"],
            -min(row["regularized_probability"], row["supcon_probability"]),
            row["sample_key"],
        ),
    )
    chosen = []
    used_cases = set()
    for row in discordant:
        if len(chosen) >= priority_limit:
            break
        if row["case_key"] not in used_cases:
            chosen.append(row)
            used_cases.add(row["case_key"])
    controls = list(row for row in rows if row["review_signal"] == "both_agree" and row["case_key"] not in used_cases)
    random.Random(seed).shuffle(controls)
    sampled_controls = []
    for row in controls:
        if len(sampled_controls) >= control_count:
            break
        if row["case_key"] not in used_cases:
            sampled_controls.append(row)
            used_cases.add(row["case_key"])
    return chosen, sampled_controls


def write_csv(path: Path, fields: list[str], rows: list[dict]) -> None:
    with path.open("x", newline="", encoding="utf-8-sig") as target:
        writer = csv.DictWriter(target, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    args = parse_args()
    if (args.seed, args.val_ratio, args.near_duplicate_distance) != (42, 0.15, 0):
        raise ValueError("Frozen validation review requires seed=42, val-ratio=0.15, near-duplicate-distance=0.")
    paths = [args.output / name for name in ("all_validation_predictions.csv", "review_template.csv", "summary.json")]
    review_images = args.output / "review_images"
    if any(path.exists() for path in [*paths, review_images]):
        raise FileExistsError("Review outputs already exist; choose a new --output to preserve reviewer edits.")
    seed_everything(args.seed)
    _training, validation, split_summary = cleaned_train_validation(args)
    expected_path = args.regularized.parent.parent / "dataset_summary.json"
    expected = json.loads(expected_path.read_text(encoding="utf-8"))
    for key in ("train", "validation", "fixed_test_untouched"):
        if split_summary[key] != expected[key]:
            raise RuntimeError(f"Reconstructed split count mismatch: {key}")
    if len(validation) != 892:
        raise RuntimeError(f"Expected frozen 892-image validation split, got {len(validation)}")
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    predictions = {}
    metadata = {}
    reference_targets = torch.tensor([sample.label for sample in validation])
    for name, checkpoint in (("regularized", args.regularized), ("supcon", args.supcon)):
        print(f"Running {name} on {len(validation)} validation images with {device}...", flush=True)
        info, probabilities, targets = model_probabilities(
            checkpoint, {"validation": validation}, device, args.batch_size, args.workers
        )
        if not torch.equal(targets["validation"], reference_targets):
            raise RuntimeError(f"Validation target order differs for {name}")
        metrics = report_metrics(probabilities["validation"], reference_targets)
        evaluation_path = checkpoint.parent / "evaluation.json"
        saved_f1 = json.loads(evaluation_path.read_text(encoding="utf-8"))["candidate"]["validation"]["macro_f1_all_classes"]
        if abs(metrics["macro_f1_all_classes"] - saved_f1) > 1e-10:
            raise RuntimeError(f"Reconstructed validation metric mismatch for {name}")
        predictions[name] = probabilities["validation"]
        metadata[name] = {**info, "validation_macro_f1": metrics["macro_f1_all_classes"]}
    rows = create_rows(validation, predictions["regularized"], predictions["supcon"])
    priority, controls = choose_review_rows(rows, args.priority_limit, args.control_count, args.seed)
    review_rows = []
    for row in [*priority, *controls]:
        suffix = Path(row["image_path"]).suffix.lower()
        review_rows.append({
            "sample_key": row["sample_key"],
            "review_image": f"review_images/{row['sample_key']}{suffix}",
            "source_image": row["image_path"],
        })
    random.Random(args.seed).shuffle(review_rows)
    signal_counts = Counter(row["review_signal"] for row in rows)
    by_label = defaultdict(Counter)
    for row in rows:
        by_label[row["recorded_label"]][row["review_signal"]] += 1
    report = {
        "purpose": "Clinician review candidates only; model disagreement does not establish label error.",
        "split": "frozen_validation_seed42; fixed test used only for original duplicate exclusion; no inference on fixed test, SCIN external holdout, or PAD",
        "validation_count": len(rows),
        "validation_fingerprint_sha256": sample_fingerprint(validation),
        "models": metadata,
        "signal_counts": dict(signal_counts),
        "signal_counts_by_recorded_label": {name: dict(by_label[name]) for name in CLASSES},
        "selected_discordant_images": len(priority),
        "selected_random_agreement_controls": len(controls),
        "selection": "One image per case group where known; disagreement category, then Lupus/SkinCancer involvement, then model probability; controls sampled with seed 42. Review template order shuffled.",
        "caveats": [
            "Recorded labels are not independently verified clinical ground truth.",
            "Both models share training data and architecture family; agreement does not validate a label.",
            "Review image filenames hide the class folder, but images or embedded metadata may still reveal a diagnosis.",
            "Images alone may lack the clinical context needed to determine a diagnosis.",
            "A reviewed validation set cannot serve as a new independent test set.",
        ],
    }
    args.output.mkdir(parents=True, exist_ok=True)
    review_images.mkdir()
    for row in review_rows:
        shutil.copyfile(WORKSPACE / row["source_image"], args.output / row["review_image"])
    write_csv(paths[0], MACHINE_FIELDS, rows)
    write_csv(paths[1], REVIEW_FIELDS, review_rows)
    with paths[2].open("x", encoding="utf-8") as target:
        json.dump(report, target, indent=2, ensure_ascii=False)
        target.write("\n")
    print(json.dumps({"validation": len(rows), "signals": dict(signal_counts), "review": len(review_rows)}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
