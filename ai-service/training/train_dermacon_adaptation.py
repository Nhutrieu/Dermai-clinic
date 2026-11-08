"""Paired development-only EfficientNet-B0 pilot with optional DermaCon source sampling."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path

import torch
from sklearn.metrics import classification_report
from torch import nn
from torch.utils.data import DataLoader, WeightedRandomSampler

from common import (
    CLASSES, ImageSample, ImageSampleDataset, build_model, evaluation_transform,
    save_json, seed_everything, sha256_file,
)
from evaluate_v2_candidate import infer_logits
from train_supcon_convnext import cleaned_train_validation
from train_v2 import classifier_parameters, effective_number_weights, run_epoch, training_transform_v2


def source_sampling_weights(core_count: int, extra_count: int, extra_fraction: float) -> torch.Tensor:
    if core_count < 1 or not 0 <= extra_fraction < 1 or (extra_fraction > 0 and extra_count < 1):
        raise ValueError("Invalid source sampling counts or fraction")
    if extra_fraction == 0:
        return torch.full((core_count,), 1 / core_count, dtype=torch.double)
    return torch.tensor(
        [(1 - extra_fraction) / core_count] * core_count
        + [extra_fraction / extra_count] * extra_count,
        dtype=torch.double,
    )


def read_source_split(path: Path, images_root: Path, expected_count: int) -> tuple[list[ImageSample], set[str]]:
    with path.open(encoding="utf-8-sig", newline="") as source:
        rows = list(csv.DictReader(source))
    if len(rows) != expected_count:
        raise ValueError(f"Unexpected source split size: {path}")
    samples = []
    cases = set()
    for row in rows:
        relative = Path(row["image_path"])
        if relative.is_absolute() or ".." in relative.parts or row["label"] not in CLASSES:
            raise ValueError("Invalid image path or label in source split")
        image = (images_root / relative).resolve()
        if not image.is_relative_to((images_root / "images").resolve()) or not image.is_file():
            raise ValueError(f"Source image missing or outside image root: {image}")
        case = row["case_id"]
        if not case:
            raise ValueError("Missing patient group")
        cases.add(case)
        samples.append(ImageSample(image, CLASSES.index(row["label"]), sha256_file(image), case))
    return samples, cases


def evaluate(model: nn.Module, samples: list[ImageSample], device: torch.device, batch_size: int, workers: int) -> dict:
    logits, targets = infer_logits(model, samples, device, batch_size, workers)
    predicted = logits.argmax(dim=1)
    report = classification_report(
        targets.numpy(), predicted.numpy(), labels=list(range(len(CLASSES))),
        target_names=CLASSES, output_dict=True, zero_division=0,
    )
    present = {int(label) for label in targets.tolist()}
    return {
        "images": len(samples),
        "accuracy": float(report["accuracy"]),
        "macro_f1_all_eight": float(report["macro avg"]["f1-score"]),
        "macro_f1_present_classes": sum(report[CLASSES[index]]["f1-score"] for index in present) / len(present),
        "per_class": {
            name: {
                "correct": int(((targets == index) & (predicted == index)).sum()),
                "support": int((targets == index).sum()),
                "recall": float(report[name]["recall"]),
                "f1": float(report[name]["f1-score"]),
            }
            for index, name in enumerate(CLASSES)
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--arm", required=True, choices=("control", "dermacon_15pct"))
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--split-root", type=Path, default=Path("SkinDisease/sources/dermacon_in/adaptation"))
    parser.add_argument("--images-root", type=Path, default=Path("SkinDisease/sources/dermacon_in/holdout"))
    parser.add_argument("--init-checkpoint", type=Path, default=Path("ai-service/candidates/production_calibrated/best_model.pth"))
    parser.add_argument("--data", type=Path, default=Path("SkinDisease"))
    parser.add_argument("--extra-data", action="append", type=Path, default=[Path("SkinDisease/scin-v1")])
    parser.add_argument("--workers", type=int, default=0)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(f"Preserving prior run: {args.output}")
    split_audit = json.loads((args.split_root / "split_audit.json").read_text(encoding="utf-8"))
    if not split_audit["all_splits_patient_disjoint"] or not split_audit["official_test_previously_evaluated"]:
        raise ValueError("Expected a patient-disjoint, previously inspected development source")
    seed_everything(42)
    split_args = argparse.Namespace(
        data=args.data, extra_data=args.extra_data, val_ratio=0.15,
        near_duplicate_distance=0, seed=42,
    )
    core_train, historical_validation, historical_summary = cleaned_train_validation(split_args)
    if len(core_train) != 5045 or len(historical_validation) != 892:
        raise ValueError("Historical training split changed")
    source_train, train_cases = read_source_split(args.split_root / "train.csv", args.images_root, 590)
    source_validation, validation_cases = read_source_split(args.split_root / "validation.csv", args.images_root, 213)
    source_test, test_cases = read_source_split(args.split_root / "official_test.csv", args.images_root, 183)
    if train_cases & validation_cases or train_cases & test_cases or validation_cases & test_cases:
        raise ValueError("Source patient overlap")
    prior_digests = {sample.digest for sample in [*core_train, *historical_validation]}
    if prior_digests & {sample.digest for sample in [*source_train, *source_validation, *source_test]}:
        raise ValueError("Source image duplicates historical data")
    fraction = 0.15 if args.arm == "dermacon_15pct" else 0.0
    training = [*core_train, *source_train] if fraction else core_train
    weights = source_sampling_weights(len(core_train), len(source_train), fraction)
    sampler = WeightedRandomSampler(
        weights, num_samples=len(core_train), replacement=True,
        generator=torch.Generator().manual_seed(42),
    )
    use_cuda = torch.cuda.is_available()
    device = torch.device("cuda" if use_cuda else "cpu")
    checkpoint = torch.load(args.init_checkpoint, map_location="cpu", weights_only=False)
    if checkpoint["architecture"] != "efficientnet_b0" or checkpoint["classes"] != CLASSES:
        raise ValueError("Expected current eight-class EfficientNet-B0 checkpoint")
    model = build_model("efficientnet_b0", len(CLASSES), pretrained=False)
    model.load_state_dict(checkpoint["model_state_dict"])
    model.to(device)
    initial = {
        "dermacon_validation": evaluate(model, source_validation, device, 64, args.workers),
        "dermacon_official_test": evaluate(model, source_test, device, 64, args.workers),
    }
    backbone, head = classifier_parameters(model)
    optimizer = torch.optim.AdamW(
        [{"params": backbone, "lr": 1e-5}, {"params": head, "lr": 5e-5}],
        weight_decay=0.01,
    )
    class_weights, _ = effective_number_weights(core_train, 0.9999, device)
    loss_fn = nn.CrossEntropyLoss(weight=class_weights, label_smoothing=0.1)
    scaler = torch.amp.GradScaler("cuda", enabled=use_cuda)
    loader = DataLoader(
        ImageSampleDataset(training, training_transform_v2()),
        batch_size=32, sampler=sampler, num_workers=args.workers,
        pin_memory=use_cuda, persistent_workers=args.workers > 0,
    )
    args.output.mkdir(parents=True)
    config = {
        "arm": args.arm, "seed": 42, "epochs": 3, "batch_size": 32,
        "steps_per_epoch_images": len(core_train), "dermacon_sampling_fraction": fraction,
        "backbone_lr": 1e-5, "head_lr": 5e-5, "weight_decay": 0.01,
        "label_smoothing": 0.1, "effective_number_beta": 0.9999,
        "init_checkpoint_sha256": sha256_file(args.init_checkpoint),
        "source_split_audit_sha256": hashlib.sha256((args.split_root / "split_audit.json").read_bytes()).hexdigest(),
        "source_images": {"train": 590, "validation": 213, "official_test": 183},
        "historical_images": {"train": len(core_train), "validation_reused": len(historical_validation)},
        "old_fixed_test_used": False, "source_official_test_previously_inspected": True,
        "checkpoint_selection": "final_epoch_only",
    }
    save_json(args.output / "configuration.json", config)
    print(json.dumps({"arm": args.arm, "device": str(device), "initial": initial}), flush=True)
    history = []
    for epoch in range(1, 4):
        trained = run_epoch(model, loader, loss_fn, device, optimizer, scaler)
        history.append({"epoch": epoch, "train": trained})
        save_json(args.output / "history.json", history)
        print(json.dumps({"arm": args.arm, "epoch": epoch, "train_accuracy": trained["accuracy"], "train_macro_f1": trained["macro_f1"]}), flush=True)
    final = {
        "dermacon_validation": evaluate(model, source_validation, device, 64, args.workers),
        "dermacon_official_test": evaluate(model, source_test, device, 64, args.workers),
        "historical_validation_regression_only": evaluate(model, historical_validation, device, 64, args.workers),
    }
    result = {
        "protocol": "Development-only paired pilot; fixed third epoch; only 15% source sampling differs.",
        "configuration": config,
        "initial": initial,
        "final": final,
        "clinical_accuracy_claim": False,
        "deployment_candidate": False,
    }
    save_json(args.output / "selection_report.json", result)
    torch.save({
        "model_state_dict": model.state_dict(), "architecture": "efficientnet_b0",
        "classes": CLASSES, "version": f"efficientnet_b0_dermacon_development_{args.arm}_seed42",
        "temperature": 1.0, "calibration_status": "not_calibrated_not_for_deployment",
        "initial_checkpoint_sha256": config["init_checkpoint_sha256"],
    }, args.output / "final_model.pth")
    print(json.dumps({"arm": args.arm, "final_validation": final["dermacon_validation"], "final_official_test": final["dermacon_official_test"]}), flush=True)


if __name__ == "__main__":
    main()
