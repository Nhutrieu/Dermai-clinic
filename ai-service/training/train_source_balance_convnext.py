"""Paired pilot: continue one frozen ConvNeXt checkpoint with standard or source-balanced sampling.

Only the previously selected validation split is inspected. No old test set or
SCIN case holdout is inferred on, and this script never deploys a checkpoint.
"""

from __future__ import annotations

import argparse
import copy
import json
from collections import Counter
from pathlib import Path

import torch
from sklearn.metrics import classification_report
from torch import nn
from torch.utils.data import DataLoader, WeightedRandomSampler

from audit_validation_sources import source_of
from common import (
    CLASSES, ImageSample, ImageSampleDataset, build_model, evaluation_transform,
    save_json, seed_everything, sha256_file,
)
from evaluate_v2_candidate import infer_logits
from train_supcon_convnext import cleaned_train_validation
from train_v2 import (
    classifier_parameters, effective_number_weights, make_loader, run_epoch,
    training_transform_v2, update_ema,
)


WORKSPACE = Path(__file__).resolve().parents[2]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=Path("SkinDisease"))
    parser.add_argument("--extra-data", action="append", type=Path, default=[Path("SkinDisease/scin-v1")])
    parser.add_argument(
        "--init-checkpoint", type=Path,
        default=Path("ai-service/candidates/convnext_tiny_regularized_seed42/evaluation/calibrated_model.pth"),
    )
    parser.add_argument("--sampler", choices=["standard", "source_balanced"], required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--epochs", type=int, default=4)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--workers", type=int, default=0)
    parser.add_argument("--min-source-examples", type=int, default=30)
    parser.add_argument("--backbone-lr", type=float, default=1e-5)
    parser.add_argument("--head-lr", type=float, default=5e-5)
    parser.add_argument("--weight-decay", type=float, default=0.01)
    parser.add_argument("--label-smoothing", type=float, default=0.1)
    parser.add_argument("--effective-number-beta", type=float, default=0.9999)
    parser.add_argument("--ema-decay", type=float, default=0.5)
    parser.add_argument("--val-ratio", type=float, default=0.15)
    parser.add_argument("--near-duplicate-distance", type=int, default=0)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--amp", action=argparse.BooleanOptionalAction, default=True)
    return parser.parse_args()


def sample_source(sample: ImageSample) -> str:
    return source_of(sample.path.resolve().relative_to(WORKSPACE).as_posix())


def source_balance_weights(samples: list[ImageSample], minimum: int) -> tuple[torch.Tensor, dict]:
    """Equalize sources within eligible classes, preserving class mass in expectation."""
    if minimum < 1:
        raise ValueError("Minimum source examples must be positive")
    cells = Counter((sample.label, sample_source(sample)) for sample in samples)
    class_counts = Counter(sample.label for sample in samples)
    weights = []
    eligible = []
    for label in range(len(CLASSES)):
        sources = [source for source in ("SkinDisease_original", "SCIN_train_pool") if cells[label, source] >= minimum]
        if len(sources) == 2:
            eligible.append(CLASSES[label])
    for sample in samples:
        source = sample_source(sample)
        count = cells[sample.label, source]
        weight = (
            class_counts[sample.label] / (2 * count)
            if CLASSES[sample.label] in eligible else 1.0
        )
        weights.append(weight)
    return torch.tensor(weights, dtype=torch.double), {
        "cell_counts": {CLASSES[label]: {
            source: cells[label, source] for source in ("SkinDisease_original", "SCIN_train_pool")
        } for label in range(len(CLASSES))},
        "eligible_classes": eligible,
        "minimum_per_source_cell": minimum,
        "expected_class_mass_preserved": True,
    }


def source_metrics(model: nn.Module, samples: list[ImageSample], device: torch.device, batch_size: int, workers: int) -> dict:
    logits, targets = infer_logits(model, samples, device, batch_size, workers)
    predictions = logits.argmax(dim=1).tolist()
    result = {}
    for source in ("SkinDisease_original", "SCIN_train_pool"):
        indices = [index for index, sample in enumerate(samples) if sample_source(sample) == source]
        truth = [int(targets[index]) for index in indices]
        guessed = [predictions[index] for index in indices]
        report = classification_report(
            truth, guessed, labels=list(range(len(CLASSES))),
            target_names=CLASSES, output_dict=True, zero_division=0,
        )
        present = {label for label in truth}
        result[source] = {
            "images": len(indices),
            "accuracy": sum(a == b for a, b in zip(truth, guessed)) / len(indices),
            "macro_f1_present_classes": sum(report[CLASSES[label]]["f1-score"] for label in present) / len(present),
            "per_class_recall": {
                CLASSES[label]: report[CLASSES[label]]["recall"] for label in sorted(present)
            },
        }
    return result


def main() -> None:
    args = parse_args()
    if args.epochs != 4 or args.batch_size != 16 or args.seed != 42 or args.val_ratio != 0.15 or args.near_duplicate_distance != 0:
        raise ValueError("The registered pilot fixes 4 epochs, batch 16, seed 42, val ratio .15 and dHash distance 0")
    if args.output.exists():
        raise FileExistsError(f"Output already exists: {args.output}")
    seed_everything(args.seed)
    training, validation, split_summary = cleaned_train_validation(args)
    saved_split = json.loads((args.init_checkpoint.parent.parent / "dataset_summary.json").read_text(encoding="utf-8"))
    for key in ("train", "validation", "fixed_test_untouched"):
        if split_summary[key] != saved_split[key]:
            raise RuntimeError(f"Different data split: {key}")
    if len(training) != 5045 or len(validation) != 892:
        raise RuntimeError("Unexpected data split size")
    weights, sampler_audit = source_balance_weights(training, args.min_source_examples)
    use_cuda = torch.cuda.is_available()
    device = torch.device("cuda" if use_cuda else "cpu")
    checkpoint = torch.load(args.init_checkpoint, map_location="cpu", weights_only=False)
    if checkpoint["architecture"] != "convnext_tiny" or checkpoint["classes"] != CLASSES:
        raise ValueError("Expected the selected eight-class ConvNeXt checkpoint")
    model = build_model("convnext_tiny", len(CLASSES), pretrained=False)
    model.load_state_dict(checkpoint["model_state_dict"])
    model.to(device)
    ema = copy.deepcopy(model).eval()
    for parameter in ema.parameters():
        parameter.requires_grad_(False)
    backbone, head = classifier_parameters(model)
    optimizer = torch.optim.AdamW([
        {"params": backbone, "lr": args.backbone_lr},
        {"params": head, "lr": args.head_lr},
    ], weight_decay=args.weight_decay)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=args.epochs, eta_min=1e-6)
    class_weights, _ = effective_number_weights(training, args.effective_number_beta, device)
    loss_fn = nn.CrossEntropyLoss(weight=class_weights, label_smoothing=args.label_smoothing)
    scaler = torch.amp.GradScaler("cuda", enabled=bool(args.amp and use_cuda))
    train_dataset = ImageSampleDataset(training, training_transform_v2())
    if args.sampler == "source_balanced":
        sampler = WeightedRandomSampler(
            weights, num_samples=len(training), replacement=True,
            generator=torch.Generator().manual_seed(args.seed),
        )
        train_loader = DataLoader(
            train_dataset, batch_size=args.batch_size, sampler=sampler,
            num_workers=args.workers, pin_memory=use_cuda,
            persistent_workers=args.workers > 0,
        )
    else:
        train_loader = make_loader(train_dataset, args.batch_size, True, args.workers, use_cuda)
    validation_loader = make_loader(
        ImageSampleDataset(validation, evaluation_transform()),
        args.batch_size * 2, False, args.workers, use_cuda,
    )
    initial = run_epoch(model, validation_loader, loss_fn, device)
    if abs(initial["macro_f1"] - 0.7747352341251492) > 1e-10:
        raise RuntimeError("Starting checkpoint does not reproduce saved validation F1")
    print(json.dumps({"sampler": args.sampler, "device": str(device), "initial_f1": initial["macro_f1"], "eligible": sampler_audit["eligible_classes"]}), flush=True)
    args.output.mkdir(parents=True)
    save_json(args.output / "dataset_summary.json", split_summary)
    history = []
    final_model = model
    for epoch in range(1, args.epochs + 1):
        train_result = run_epoch(model, train_loader, loss_fn, device, optimizer, scaler)
        update_ema(ema, model, args.ema_decay)
        raw = run_epoch(model, validation_loader, loss_fn, device)
        smoothed = run_epoch(ema, validation_loader, loss_fn, device)
        final_model = ema if smoothed["macro_f1"] >= raw["macro_f1"] else model
        selected = smoothed if final_model is ema else raw
        history.append({
            "epoch": epoch, "train": train_result, "validation_raw": raw,
            "validation_ema": smoothed, "selected_weights": "ema" if final_model is ema else "raw",
        })
        save_json(args.output / "history.json", history)
        print(json.dumps({"epoch": epoch, "train_f1": train_result["macro_f1"], "validation_f1": selected["macro_f1"], "weights": history[-1]["selected_weights"]}), flush=True)
        scheduler.step()
    by_source = source_metrics(final_model, validation, device, args.batch_size * 2, args.workers)
    final = history[-1]
    chosen = final["validation_ema"] if final["selected_weights"] == "ema" else final["validation_raw"]
    result = {
        "protocol": "Four additional epochs from the same checkpoint; only sampler differs between arms; final epoch is primary.",
        "sampler": args.sampler,
        "initial_checkpoint_sha256": sha256_file(args.init_checkpoint),
        "initial_validation_macro_f1": initial["macro_f1"],
        "final_validation": chosen,
        "final_validation_by_source": by_source,
        "sampler_audit": sampler_audit,
        "data_split": split_summary["totals"],
        "configuration": {
            "epochs": args.epochs, "batch_size": args.batch_size,
            "backbone_lr": args.backbone_lr, "head_lr": args.head_lr,
            "weight_decay": args.weight_decay, "label_smoothing": args.label_smoothing,
            "effective_number_beta": args.effective_number_beta,
            "ema_decay": args.ema_decay, "seed": args.seed,
        },
        "fixed_test_or_scin_external_used": False,
        "clinical_accuracy_claim": False,
    }
    save_json(args.output / "selection_report.json", result)
    torch.save({
        "model_state_dict": final_model.state_dict(),
        "architecture": "convnext_tiny", "classes": CLASSES,
        "version": f"convnext_tiny_{args.sampler}_pilot_seed42",
        "temperature": 1.0,
        "initial_checkpoint_sha256": result["initial_checkpoint_sha256"],
    }, args.output / "final_model.pth")
    print(json.dumps({"sampler": args.sampler, "final_macro_f1": chosen["macro_f1"], "by_source": by_source}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
