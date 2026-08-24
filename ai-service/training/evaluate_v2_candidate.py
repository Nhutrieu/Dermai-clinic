from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path

import numpy as np
import torch
from sklearn.metrics import classification_report
from torch import nn
from torch.utils.data import DataLoader

from common import (
    CLASSES,
    ImageSample,
    ImageSampleDataset,
    build_model,
    collect_samples,
    deduplicate_samples,
    evaluation_transform,
    exclude_cross_split_duplicates,
    exclude_digests,
    grouped_stratified_split,
    label_conflict_digests,
    save_json,
    seed_everything,
)
from evaluate_evidence import calibration_metrics
from train_v2 import group_near_duplicates, remove_near_test_duplicates


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Calibrate và đánh giá candidate V2 mà không dùng test để chọn model."
    )
    parser.add_argument("--checkpoint", required=True, type=Path)
    parser.add_argument("--data", required=True, type=Path)
    parser.add_argument("--extra-data", action="append", type=Path, default=[])
    parser.add_argument("--external-data", required=True, type=Path)
    parser.add_argument("--baseline-fixed", required=True, type=Path)
    parser.add_argument("--baseline-external", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--workers", type=int, default=0)
    parser.add_argument("--val-ratio", type=float, default=0.15)
    parser.add_argument("--near-duplicate-distance", type=int, default=3)
    parser.add_argument("--seed", type=int, default=42)
    return parser.parse_args()


def cleaned_splits(args: argparse.Namespace) -> tuple[list[ImageSample], list[ImageSample], list[ImageSample]]:
    base_train = collect_samples(args.data, "train")
    extra_train = [
        sample
        for root in args.extra_data
        for sample in collect_samples(root, "train")
    ]
    raw_train = [*base_train, *extra_train]
    raw_test = collect_samples(args.data, "test")
    conflicts = label_conflict_digests([*raw_train, *raw_test])
    train_clean, _ = exclude_digests(raw_train, conflicts)
    fixed_test, _ = exclude_digests(raw_test, conflicts)
    train_clean, _ = deduplicate_samples(train_clean)
    fixed_test, _ = deduplicate_samples(fixed_test)
    train_clean, _ = exclude_cross_split_duplicates(train_clean, fixed_test)
    train_clean, _, hashes = remove_near_test_duplicates(
        train_clean, fixed_test, args.near_duplicate_distance
    )
    grouped_train, _, _ = group_near_duplicates(
        train_clean, hashes, args.near_duplicate_distance
    )
    training, validation = grouped_stratified_split(
        grouped_train, args.val_ratio, args.seed, len(CLASSES)
    )

    external = collect_samples(args.external_data, "external_test")
    all_reference = [*training, *validation, *fixed_test]
    external_conflicts = label_conflict_digests([*all_reference, *external])
    external, _ = exclude_digests(external, external_conflicts)
    external, _ = exclude_cross_split_duplicates(external, all_reference)
    external, _ = deduplicate_samples(external)
    return validation, fixed_test, external


def infer_logits(
    model: nn.Module,
    samples: list[ImageSample],
    device: torch.device,
    batch_size: int,
    workers: int,
) -> tuple[torch.Tensor, torch.Tensor]:
    loader = DataLoader(
        ImageSampleDataset(samples, evaluation_transform()),
        batch_size=batch_size,
        shuffle=False,
        num_workers=workers,
        pin_memory=device.type == "cuda",
        persistent_workers=workers > 0,
    )
    logits: list[torch.Tensor] = []
    targets: list[torch.Tensor] = []
    model.eval()
    with torch.inference_mode():
        for inputs, labels in loader:
            logits.append(model(inputs.to(device)).cpu())
            targets.append(labels.cpu())
    return torch.cat(logits), torch.cat(targets)


def fit_temperature(logits: torch.Tensor, targets: torch.Tensor) -> float:
    log_temperature = nn.Parameter(torch.zeros(()))
    optimizer = torch.optim.LBFGS(
        [log_temperature], lr=0.1, max_iter=80, line_search_fn="strong_wolfe"
    )

    def closure():
        optimizer.zero_grad(set_to_none=True)
        temperature = log_temperature.exp().clamp(0.25, 10.0)
        loss = nn.functional.cross_entropy(logits / temperature, targets)
        loss.backward()
        return loss

    optimizer.step(closure)
    return float(log_temperature.detach().exp().clamp(0.25, 10.0))


def metrics(logits: torch.Tensor, targets: torch.Tensor, temperature: float) -> dict:
    probabilities = torch.softmax(logits / temperature, dim=1).numpy()
    target_values = targets.numpy()
    predictions = probabilities.argmax(axis=1)
    report = classification_report(
        target_values,
        predictions,
        labels=list(range(len(CLASSES))),
        target_names=CLASSES,
        output_dict=True,
        zero_division=0,
    )
    support_labels = [index for index in range(len(CLASSES)) if int((target_values == index).sum()) > 0]
    present_f1 = float(np.mean([report[CLASSES[index]]["f1-score"] for index in support_labels]))
    top3 = np.argsort(-probabilities, axis=1)[:, :3]
    return {
        "count": len(target_values),
        "accuracy": float((predictions == target_values).mean()),
        "macro_f1_all_classes": float(report["macro avg"]["f1-score"]),
        "macro_f1_present_classes": present_f1,
        "weighted_f1": float(report["weighted avg"]["f1-score"]),
        "top3_accuracy": float((top3 == target_values[:, None]).any(axis=1).mean()),
        "per_class": {
            name: {
                "precision": float(report[name]["precision"]),
                "recall": float(report[name]["recall"]),
                "f1": float(report[name]["f1-score"]),
                "support": int(report[name]["support"]),
            }
            for name in CLASSES
        },
        "calibration": calibration_metrics(probabilities, target_values),
    }


def baseline_metrics(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = payload["predictions"]
    targets = np.asarray([CLASSES.index(row["true_label"]) for row in rows])
    probabilities = np.asarray(
        [[row["probabilities"][name] for name in CLASSES] for row in rows],
        dtype=np.float32,
    )
    logits = torch.from_numpy(np.log(np.clip(probabilities, 1e-12, 1.0)))
    return metrics(logits, torch.from_numpy(targets), 1.0)


def main() -> None:
    args = parse_args()
    seed_everything(args.seed)
    validation, fixed_test, external = cleaned_splits(args)
    checkpoint = torch.load(args.checkpoint, map_location="cpu", weights_only=False)
    model = build_model(checkpoint["architecture"], len(checkpoint["classes"]), pretrained=False)
    model.load_state_dict(checkpoint["model_state_dict"])
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model.to(device).eval()

    print(
        f"Đang infer validation={len(validation)}, fixed={len(fixed_test)}, external={len(external)} trên {device}...",
        flush=True,
    )
    validation_logits, validation_targets = infer_logits(
        model, validation, device, args.batch_size, args.workers
    )
    temperature = fit_temperature(validation_logits, validation_targets)
    fixed_logits, fixed_targets = infer_logits(
        model, fixed_test, device, args.batch_size, args.workers
    )
    external_logits, external_targets = infer_logits(
        model, external, device, args.batch_size, args.workers
    )
    candidate = {
        "validation": metrics(validation_logits, validation_targets, temperature),
        "fixed_test": metrics(fixed_logits, fixed_targets, temperature),
        "external_test": metrics(external_logits, external_targets, temperature),
    }
    baseline = {
        "fixed_test": baseline_metrics(args.baseline_fixed),
        "external_test": baseline_metrics(args.baseline_external),
    }
    comparison = {
        split: {
            metric: candidate[split][metric] - baseline[split][metric]
            for metric in (
                "accuracy", "macro_f1_all_classes", "macro_f1_present_classes",
                "weighted_f1", "top3_accuracy"
            )
        }
        for split in ("fixed_test", "external_test")
    }
    critical = ("Lupus", "SkinCancer")
    no_critical_recall_regression = all(
        candidate["fixed_test"]["per_class"][name]["recall"]
        >= baseline["fixed_test"]["per_class"][name]["recall"] - 0.03
        for name in critical
    )
    classification_ready = bool(
        candidate["fixed_test"]["macro_f1_present_classes"]
        >= baseline["fixed_test"]["macro_f1_present_classes"] + 0.005
        and candidate["external_test"]["macro_f1_present_classes"]
        >= baseline["external_test"]["macro_f1_present_classes"]
        and no_critical_recall_regression
    )
    report = {
        "model_version": checkpoint["version"],
        "temperature": temperature,
        "temperature_fitted_on_validation_only": True,
        "candidate": candidate,
        "baseline": baseline,
        "comparison_candidate_minus_baseline": comparison,
        "no_critical_recall_regression": no_critical_recall_regression,
        "classification_ready": classification_ready,
        "deployment_ready": False,
        "deployment_blocker": "OOD profile must be retrained for this checkpoint before deployment.",
    }
    args.output.mkdir(parents=True, exist_ok=True)
    save_json(args.output / "evaluation.json", report)
    calibrated = copy.deepcopy(checkpoint)
    calibrated["temperature"] = temperature
    calibrated["calibration_method"] = "temperature_scaling_on_validation"
    torch.save(calibrated, args.output / "calibrated_model.pth")
    print(
        json.dumps(
            {
                "temperature": temperature,
                "candidate_fixed": {key: candidate["fixed_test"][key] for key in ("accuracy", "macro_f1_present_classes", "top3_accuracy")},
                "candidate_external": {key: candidate["external_test"][key] for key in ("accuracy", "macro_f1_present_classes", "top3_accuracy")},
                "delta": comparison,
                "classification_ready": classification_ready,
            },
            ensure_ascii=False,
            indent=2,
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
