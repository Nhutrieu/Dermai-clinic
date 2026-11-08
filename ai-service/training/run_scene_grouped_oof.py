"""Run the locked five-fold B0/ConvNeXt training recipes sequentially."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from common import sha256_file
from evaluate_scene_grouped_oof_ensemble import OUTPUT as ENSEMBLE_OUTPUT
from prepare_scene_grouped_oof_folds import OUTPUT as OUTER_MANIFEST, PROJECT
from prepare_scene_grouped_oof_inner_splits import OUTPUT as INNER_PLAN


RECIPES = {
    "efficientnet_b0": {
        "directory": "oof_b0_fold{fold}_seed42",
        "batch_size": 32,
        "learning_rate": 0.0002,
        "backbone_lr_ratio": 0.25,
        "weight_decay": 0.0002,
        "label_smoothing": 0.05,
        "effective_number_beta": 0.999,
        "ema_decay": 0.995,
        "patience": 7,
    },
    "convnext_tiny": {
        "directory": "oof_convnext_fold{fold}_seed42",
        "batch_size": 16,
        "learning_rate": 0.0003,
        "backbone_lr_ratio": 0.1,
        "weight_decay": 0.01,
        "label_smoothing": 0.1,
        "effective_number_beta": 0.9999,
        "ema_decay": 0.5,
        "patience": 6,
    },
}


def command_for(architecture: str, fold: int) -> tuple[list[str], Path]:
    recipe = RECIPES[architecture]
    output = PROJECT / "ai-service/candidates" / recipe["directory"].format(fold=fold)
    command = [
        sys.executable, str(PROJECT / "ai-service/training/train_v2.py"),
        "--data", str(PROJECT / "SkinDisease"),
        "--extra-data", str(PROJECT / "SkinDisease/scin-v1"),
        "--model", architecture,
        "--epochs", "24", "--freeze-epochs", "2",
        "--batch-size", str(recipe["batch_size"]),
        "--learning-rate", str(recipe["learning_rate"]),
        "--backbone-lr-ratio", str(recipe["backbone_lr_ratio"]),
        "--weight-decay", str(recipe["weight_decay"]),
        "--label-smoothing", str(recipe["label_smoothing"]),
        "--effective-number-beta", str(recipe["effective_number_beta"]),
        "--ema-decay", str(recipe["ema_decay"]),
        "--patience", str(recipe["patience"]),
        "--near-duplicate-distance", "3", "--near-test-distance", "0",
        "--near-pixel-correlation", "0.85",
        "--reviewed-scene-manifest", str(PROJECT / "ai-service/reports/historical_validation_same_scene_review.json"),
        "--seed", "42", "--oof-fold", str(fold),
        "--oof-outer-manifest", str(OUTER_MANIFEST),
        "--oof-inner-plan", str(INNER_PLAN),
        "--output", str(output),
    ]
    return command, output


def completed(output: Path, architecture: str, fold: int, manifest_sha256: str) -> bool:
    if not output.exists():
        return False
    required = [output / name for name in (
        "best_model.pth", "selection_report.json", "dataset_summary.json", "oof_predictions.json"
    )]
    if not all(path.is_file() for path in required):
        raise FileExistsError(f"Partial OOF run needs inspection before retry: {output}")
    report = json.loads((output / "oof_predictions.json").read_text(encoding="utf-8"))
    if (
        report["architecture"] != architecture
        or report["outer_fold"] != fold
        or report["outer_manifest_sha256"] != manifest_sha256
        or report["checkpoint_sha256"] != sha256_file(output / "best_model.pth")
    ):
        raise ValueError(f"Existing OOF run differs from locked plan: {output}")
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--architecture", choices=[*RECIPES, "both"], default="both")
    parser.add_argument("--fold", type=int, choices=range(5), default=None)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    outer = json.loads(OUTER_MANIFEST.read_text(encoding="utf-8"))
    inner = json.loads(INNER_PLAN.read_text(encoding="utf-8"))
    if inner["outer_manifest_sha256"] != outer["manifest_sha256"]:
        raise ValueError("OOF outer/inner manifests differ")
    architectures = list(RECIPES) if args.architecture == "both" else [args.architecture]
    folds = range(5) if args.fold is None else [args.fold]
    for architecture in architectures:
        for fold in folds:
            command, output = command_for(architecture, fold)
            if args.dry_run:
                print(json.dumps({"architecture": architecture, "fold": fold, "command": command}), flush=True)
                continue
            if completed(output, architecture, fold, outer["manifest_sha256"]):
                print(f"Already complete: {architecture} fold {fold}", flush=True)
                continue
            print(f"Starting {architecture} fold {fold}: {output}", flush=True)
            subprocess.run(command, cwd=PROJECT, check=True)
    if args.architecture == "both" and args.fold is None and not args.dry_run:
        if ENSEMBLE_OUTPUT.exists():
            print(f"Existing OOF comparison preserved: {ENSEMBLE_OUTPUT}", flush=True)
        else:
            subprocess.run(
                [sys.executable, str(PROJECT / "ai-service/training/evaluate_scene_grouped_oof_ensemble.py")],
                cwd=PROJECT, check=True,
            )


if __name__ == "__main__":
    main()
