"""Predict each fold's inner validation with its already selected OOF checkpoint.

These predictions are solely for fitting a class-wise fusion rule. The outer
fold OOF predictions remain separate and are never read to choose weights.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import torch
from torch.utils.data import DataLoader

from common import (
    CLASSES, ImageSample, ImageSampleDataset, build_model, evaluation_transform,
    save_json, sha256_file,
)
from evaluate_scene_grouped_oof_ensemble import ARCHITECTURES, RUN_ROOT, read_probabilities
from prepare_scene_grouped_oof_folds import OUTPUT as OUTER_MANIFEST, PROJECT
from prepare_scene_grouped_oof_inner_splits import OUTPUT as INNER_PLAN


def validate_existing(path: Path, expected: dict, rows: list[dict]) -> None:
    payload = json.loads(path.read_text(encoding="utf-8"))
    for key, value in expected.items():
        if payload.get(key) != value:
            raise ValueError(f"Existing inner predictions differ in {key}: {path}")
    if len(payload.get("rows", [])) != len(rows):
        raise ValueError(f"Existing inner predictions differ in count: {path}")
    if any(
        item["path"] != row["path"] or item["sha256"] != row["sha256"]
        or item["class"] != row["class"]
        for item, row in zip(payload["rows"], rows)
    ):
        raise ValueError(f"Existing inner predictions differ in image identity: {path}")
    for item in payload["rows"]:
        vector = np.asarray(item["probabilities"], dtype=float)
        if (
            vector.shape != (len(CLASSES),) or not np.isfinite(vector).all()
            or (vector < 0).any() or abs(float(vector.sum()) - 1.0) > 1e-4
        ):
            raise ValueError(f"Invalid existing inner probability vector: {path}")


def run_one(architecture: str, fold: int, outer: dict, inner: dict, device: torch.device) -> None:
    directory = RUN_ROOT / ARCHITECTURES[architecture].format(fold=fold)
    expected_outer = {row["path"]: row for row in outer["images"] if row["fold"] == fold}
    read_probabilities(architecture, fold, outer, expected_outer)
    plan = inner["folds"][fold]
    if plan["outer_fold"] != fold:
        raise ValueError("Inner plan fold order changed")
    by_path = {row["path"]: row for row in outer["images"]}
    rows = [by_path[path] for path in plan["inner_validation_paths"]]
    if (
        len(rows) != plan["inner_validation_images"]
        or len({row["path"] for row in rows}) != len(rows)
        or any(row["fold"] == fold for row in rows)
    ):
        raise ValueError(f"Invalid inner validation rows for fold {fold}")
    checkpoint_path = directory / "best_model.pth"
    identity = {
        "role": "inner_validation_for_classwise_fusion_only",
        "architecture": architecture,
        "outer_fold": fold,
        "outer_manifest_sha256": outer["manifest_sha256"],
        "inner_plan_sha256": sha256_file(INNER_PLAN),
        "checkpoint_sha256": sha256_file(checkpoint_path),
        "classes": CLASSES,
    }
    output = directory / "inner_predictions.json"
    if output.exists():
        validate_existing(output, identity, rows)
        print(f"Already complete: {architecture} fold {fold} inner predictions", flush=True)
        return
    samples = []
    for row in rows:
        image = PROJECT.joinpath(*row["path"].split("/")).resolve()
        if not image.is_relative_to(PROJECT.resolve()) or sha256_file(image) != row["sha256"]:
            raise ValueError(f"Inner image missing or changed: {row['path']}")
        samples.append(ImageSample(
            image, CLASSES.index(row["class"]), row["sha256"], row["scene_or_case_group"]
        ))
    checkpoint = torch.load(checkpoint_path, map_location="cpu", weights_only=False)
    if checkpoint["architecture"] != architecture or checkpoint["classes"] != CLASSES:
        raise ValueError(f"Checkpoint architecture/classes differ: {checkpoint_path}")
    model = build_model(architecture, len(CLASSES), pretrained=False)
    model.load_state_dict(checkpoint["model_state_dict"])
    model.to(device).eval()
    loader = DataLoader(
        ImageSampleDataset(samples, evaluation_transform()),
        batch_size=16 if architecture == "convnext_tiny" else 32,
        shuffle=False, num_workers=0, pin_memory=device.type == "cuda",
    )
    probabilities = []
    with torch.inference_mode():
        for images, _ in loader:
            logits = model(images.to(device, non_blocking=True))
            probabilities.extend(torch.softmax(logits, dim=1).cpu().tolist())
    if len(probabilities) != len(rows):
        raise RuntimeError("Inner prediction count mismatch")
    save_json(output, identity | {
        "rows": [
            {"path": row["path"], "sha256": row["sha256"], "class": row["class"],
             "probabilities": prediction}
            for row, prediction in zip(rows, probabilities)
        ],
    })
    print(f"Saved {len(rows)} inner predictions: {architecture} fold {fold}", flush=True)
    del model
    if device.type == "cuda":
        torch.cuda.empty_cache()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--architecture", choices=[*ARCHITECTURES, "both"], default="both")
    parser.add_argument("--fold", type=int, choices=range(5))
    parser.add_argument("--device", choices=["cpu", "cuda"], default="cuda" if torch.cuda.is_available() else "cpu")
    args = parser.parse_args()
    outer = json.loads(OUTER_MANIFEST.read_text(encoding="utf-8"))
    inner = json.loads(INNER_PLAN.read_text(encoding="utf-8"))
    if inner["outer_manifest_sha256"] != outer["manifest_sha256"] or len(inner["folds"]) != 5:
        raise ValueError("OOF outer and inner manifests differ")
    device = torch.device(args.device)
    architectures = list(ARCHITECTURES) if args.architecture == "both" else [args.architecture]
    folds = range(5) if args.fold is None else [args.fold]
    for architecture in architectures:
        for fold in folds:
            run_one(architecture, fold, outer, inner, device)


if __name__ == "__main__":
    main()
