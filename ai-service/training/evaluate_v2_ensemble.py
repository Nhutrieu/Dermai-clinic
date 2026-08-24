from __future__ import annotations

import argparse
import gc
import json
import sys
from pathlib import Path

import numpy as np
import torch

from common import CLASSES, build_model, save_json, seed_everything
from evaluate_v2_candidate import (
    baseline_metrics,
    cleaned_splits,
    fit_temperature,
    infer_logits,
    metrics,
)


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


CRITICAL_CLASSES = ("Lupus", "SkinCancer")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Chọn ensemble hai checkpoint chỉ bằng validation rồi đánh giá trên test."
    )
    parser.add_argument("--baseline-checkpoint", required=True, type=Path)
    parser.add_argument("--candidate-checkpoint", required=True, type=Path)
    parser.add_argument("--data", required=True, type=Path)
    parser.add_argument("--extra-data", action="append", type=Path, default=[])
    parser.add_argument("--external-data", required=True, type=Path)
    parser.add_argument("--baseline-fixed", required=True, type=Path)
    parser.add_argument("--baseline-external", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--workers", type=int, default=0)
    parser.add_argument("--val-ratio", type=float, default=0.15)
    parser.add_argument("--near-duplicate-distance", type=int, default=0)
    parser.add_argument("--seed", type=int, default=42)
    return parser.parse_args()


def load_and_infer(
    checkpoint_path: Path,
    splits: tuple,
    device: torch.device,
    batch_size: int,
    workers: int,
) -> tuple[dict, list[torch.Tensor], list[torch.Tensor]]:
    checkpoint = torch.load(checkpoint_path, map_location="cpu", weights_only=False)
    model = build_model(
        checkpoint["architecture"], len(checkpoint["classes"]), pretrained=False
    )
    model.load_state_dict(checkpoint["model_state_dict"])
    model.to(device).eval()
    logits: list[torch.Tensor] = []
    targets: list[torch.Tensor] = []
    for samples in splits:
        split_logits, split_targets = infer_logits(
            model, samples, device, batch_size, workers
        )
        logits.append(split_logits)
        targets.append(split_targets)
    model.to("cpu")
    del model
    gc.collect()
    if device.type == "cuda":
        torch.cuda.empty_cache()
    return checkpoint, logits, targets


def critical_recall_ok(candidate: dict, reference: dict, tolerance: float = 0.03) -> bool:
    return all(
        candidate["per_class"][name]["recall"]
        >= reference["per_class"][name]["recall"] - tolerance
        for name in CRITICAL_CLASSES
    )


def main() -> None:
    args = parse_args()
    seed_everything(args.seed)
    validation, fixed_test, external = cleaned_splits(args)
    splits = (validation, fixed_test, external)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(
        f"Đang infer validation={len(validation)}, fixed={len(fixed_test)}, "
        f"external={len(external)} trên {device}...",
        flush=True,
    )

    baseline_checkpoint, baseline_logits, targets = load_and_infer(
        args.baseline_checkpoint, splits, device, args.batch_size, args.workers
    )
    candidate_checkpoint, candidate_logits, candidate_targets = load_and_infer(
        args.candidate_checkpoint, splits, device, args.batch_size, args.workers
    )
    for left, right in zip(targets, candidate_targets):
        if not torch.equal(left, right):
            raise RuntimeError("Thứ tự mẫu giữa hai lượt infer không khớp.")
    if baseline_checkpoint["classes"] != candidate_checkpoint["classes"]:
        raise RuntimeError("Ánh xạ lớp giữa hai checkpoint không khớp.")

    baseline_temperature = fit_temperature(baseline_logits[0], targets[0])
    candidate_temperature = fit_temperature(candidate_logits[0], targets[0])
    baseline_validation = metrics(
        baseline_logits[0], targets[0], baseline_temperature
    )

    trials: list[dict] = []
    for alpha in np.linspace(0.0, 1.0, 21):
        validation_logits = (
            (1.0 - alpha) * baseline_logits[0] / baseline_temperature
            + alpha * candidate_logits[0] / candidate_temperature
        )
        temperature = fit_temperature(validation_logits, targets[0])
        validation_metrics = metrics(validation_logits, targets[0], temperature)
        safe = critical_recall_ok(validation_metrics, baseline_validation)
        trials.append(
            {
                "alpha_candidate": float(alpha),
                "temperature": temperature,
                "critical_recall_ok": safe,
                "validation": validation_metrics,
            }
        )

    safe_trials = [trial for trial in trials if trial["critical_recall_ok"]]
    pool = safe_trials or trials
    selected = max(
        pool,
        key=lambda trial: (
            trial["validation"]["macro_f1_present_classes"],
            trial["validation"]["top3_accuracy"],
            -trial["validation"]["calibration"]["negative_log_likelihood"],
        ),
    )
    alpha = selected["alpha_candidate"]
    temperature = selected["temperature"]

    ensemble_logits = [
        (1.0 - alpha) * old / baseline_temperature
        + alpha * new / candidate_temperature
        for old, new in zip(baseline_logits, candidate_logits)
    ]
    ensemble = {
        "validation": metrics(ensemble_logits[0], targets[0], temperature),
        "fixed_test": metrics(ensemble_logits[1], targets[1], temperature),
        "external_test": metrics(ensemble_logits[2], targets[2], temperature),
    }
    baseline = {
        "fixed_test": baseline_metrics(args.baseline_fixed),
        "external_test": baseline_metrics(args.baseline_external),
    }
    comparison = {
        split: {
            metric: ensemble[split][metric] - baseline[split][metric]
            for metric in (
                "accuracy",
                "macro_f1_all_classes",
                "macro_f1_present_classes",
                "weighted_f1",
                "top3_accuracy",
            )
        }
        for split in ("fixed_test", "external_test")
    }
    no_critical_recall_regression = critical_recall_ok(
        ensemble["fixed_test"], baseline["fixed_test"]
    )
    classification_ready = bool(
        ensemble["fixed_test"]["macro_f1_present_classes"]
        >= baseline["fixed_test"]["macro_f1_present_classes"] + 0.005
        and ensemble["external_test"]["macro_f1_present_classes"]
        >= baseline["external_test"]["macro_f1_present_classes"]
        and ensemble["external_test"]["top3_accuracy"]
        >= baseline["external_test"]["top3_accuracy"] - 0.02
        and no_critical_recall_regression
    )
    report = {
        "method": "temperature_scaled_logit_ensemble",
        "selection_used_validation_only": True,
        "baseline_version": baseline_checkpoint["version"],
        "candidate_version": candidate_checkpoint["version"],
        "baseline_temperature": baseline_temperature,
        "candidate_temperature": candidate_temperature,
        "selected_alpha_candidate": alpha,
        "ensemble_temperature": temperature,
        "selection_trials": trials,
        "ensemble": ensemble,
        "baseline": baseline,
        "comparison_ensemble_minus_baseline": comparison,
        "no_critical_recall_regression": no_critical_recall_regression,
        "classification_ready": classification_ready,
        "deployment_ready": False,
        "deployment_blocker": (
            "Ensemble runtime và OOD profile chưa được triển khai/đánh giá."
        ),
    }
    args.output.mkdir(parents=True, exist_ok=True)
    save_json(args.output / "evaluation.json", report)
    save_json(
        args.output / "ensemble_config.json",
        {
            "method": report["method"],
            "baseline_checkpoint": str(args.baseline_checkpoint),
            "candidate_checkpoint": str(args.candidate_checkpoint),
            "baseline_version": report["baseline_version"],
            "candidate_version": report["candidate_version"],
            "baseline_temperature": baseline_temperature,
            "candidate_temperature": candidate_temperature,
            "alpha_candidate": alpha,
            "ensemble_temperature": temperature,
        },
    )
    print(
        json.dumps(
            {
                "selected_alpha_candidate": alpha,
                "ensemble_fixed": {
                    key: ensemble["fixed_test"][key]
                    for key in ("accuracy", "macro_f1_present_classes", "top3_accuracy")
                },
                "ensemble_external": {
                    key: ensemble["external_test"][key]
                    for key in ("accuracy", "macro_f1_present_classes", "top3_accuracy")
                },
                "delta": comparison,
                "no_critical_recall_regression": no_critical_recall_regression,
                "classification_ready": classification_ready,
            },
            ensure_ascii=False,
            indent=2,
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
