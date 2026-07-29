from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import torch
from sklearn.metrics import classification_report
from torch import nn
from torch.utils.data import DataLoader

from common import (
    CLASSES,
    ImageSampleDataset,
    build_model,
    class_counts,
    collect_samples,
    deduplicate_samples,
    evaluation_transform,
    exclude_digests,
    exclude_cross_split_duplicates,
    grouped_stratified_split,
    label_conflict_digests,
    save_json,
    seed_everything,
    training_transform,
)
from evaluate import evaluate_checkpoint


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Huấn luyện bộ phân loại tám nhóm bệnh da liễu và đánh giá trên test độc lập."
    )
    parser.add_argument("--data", required=True, type=Path)
    parser.add_argument(
        "--extra-data",
        action="append",
        type=Path,
        default=[],
        help="Additional dataset root(s) containing train/<class>; may be repeated.",
    )
    parser.add_argument(
        "--model",
        choices=["efficientnet_b0", "resnet50", "convnext_tiny"],
        default="efficientnet_b0",
    )
    parser.add_argument("--epochs", type=int, default=20)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--learning-rate", type=float, default=3e-4)
    parser.add_argument("--weight-decay", type=float, default=1e-4)
    parser.add_argument("--val-ratio", type=float, default=0.15)
    parser.add_argument("--patience", type=int, default=5)
    parser.add_argument("--output", type=Path, default=Path("models"))
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--pretrained", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--amp", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--class-weighted", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--evaluate-test", action=argparse.BooleanOptionalAction, default=True)
    return parser.parse_args()


def make_loader(dataset, batch_size: int, shuffle: bool, workers: int, use_cuda: bool):
    return DataLoader(
        dataset,
        batch_size=batch_size,
        shuffle=shuffle,
        num_workers=workers,
        pin_memory=use_cuda,
        persistent_workers=workers > 0,
    )


def run_epoch(model, loader, loss_fn, device, optimizer=None, amp_enabled=False):
    training = optimizer is not None
    model.train(training)
    scaler = torch.amp.GradScaler("cuda", enabled=amp_enabled and training)
    losses: list[float] = []
    all_targets: list[int] = []
    all_predictions: list[int] = []

    for inputs, targets in loader:
        inputs = inputs.to(device, non_blocking=True)
        targets = targets.to(device, non_blocking=True)
        if training:
            optimizer.zero_grad(set_to_none=True)

        with torch.set_grad_enabled(training):
            with torch.autocast(device_type=device.type, enabled=amp_enabled):
                logits = model(inputs)
                loss = loss_fn(logits, targets)
            if training:
                scaler.scale(loss).backward()
                scaler.step(optimizer)
                scaler.update()

        losses.append(float(loss.detach().cpu()))
        all_targets.extend(targets.detach().cpu().tolist())
        all_predictions.extend(logits.argmax(dim=1).detach().cpu().tolist())

    report = classification_report(
        all_targets,
        all_predictions,
        labels=list(range(len(CLASSES))),
        target_names=CLASSES,
        output_dict=True,
        zero_division=0,
    )
    return {
        "loss": float(np.mean(losses)),
        "accuracy": float(report["accuracy"]),
        "macro_f1": float(report["macro avg"]["f1-score"]),
        "weighted_f1": float(report["weighted avg"]["f1-score"]),
    }


def main() -> None:
    args = parse_args()
    if args.epochs < 1 or args.batch_size < 1 or args.workers < 0:
        raise ValueError("epochs/batch-size phải dương và workers không được âm.")

    seed_everything(args.seed)
    args.output.mkdir(parents=True, exist_ok=True)
    print("Đang đọc và băm dataset để loại leakage...", flush=True)
    base_train = collect_samples(args.data, "train")
    extra_train_by_root = {
        str(root): collect_samples(root, "train") for root in args.extra_data
    }
    raw_train = [base_train, *extra_train_by_root.values()]
    raw_train = [sample for source in raw_train for sample in source]
    test_samples = collect_samples(args.data, "test")
    conflict_hashes = label_conflict_digests([*raw_train, *test_samples])
    train_without_conflicts, train_conflicts = exclude_digests(raw_train, conflict_hashes)
    test_without_conflicts, test_conflicts = exclude_digests(test_samples, conflict_hashes)
    unique_train, train_duplicates = deduplicate_samples(train_without_conflicts)
    clean_test, test_duplicates = deduplicate_samples(test_without_conflicts)
    clean_train, cross_split_duplicates = exclude_cross_split_duplicates(unique_train, clean_test)
    train_samples, validation_samples = grouped_stratified_split(
        clean_train, args.val_ratio, args.seed, len(CLASSES)
    )

    dataset_summary = {
        "classes": CLASSES,
        "seed": args.seed,
        "validation_ratio": args.val_ratio,
        "raw_train": class_counts(raw_train),
        "raw_train_sources": {
            str(args.data): class_counts(base_train),
            **{
                root: class_counts(samples)
                for root, samples in extra_train_by_root.items()
            },
        },
        "excluded_label_conflicts": {
            "train": class_counts(train_conflicts),
            "test": class_counts(test_conflicts),
        },
        "excluded_within_split_duplicates": {
            "train": class_counts(train_duplicates),
            "test": class_counts(test_duplicates),
        },
        "excluded_train_test_duplicates": class_counts(cross_split_duplicates),
        "train": class_counts(train_samples),
        "validation": class_counts(validation_samples),
        "test": class_counts(clean_test),
        "totals": {
            "raw_train": len(raw_train),
            "label_conflict_digests": len(conflict_hashes),
            "excluded_label_conflict_files": len(train_conflicts) + len(test_conflicts),
            "excluded_within_split_duplicates": len(train_duplicates) + len(test_duplicates),
            "excluded_train_test_duplicates": len(cross_split_duplicates),
            "train": len(train_samples),
            "validation": len(validation_samples),
            "test": len(clean_test),
        },
    }
    save_json(args.output / "dataset_summary.json", dataset_summary)
    print(dataset_summary["totals"], flush=True)

    use_cuda = torch.cuda.is_available()
    device = torch.device("cuda" if use_cuda else "cpu")
    amp_enabled = bool(args.amp and use_cuda)
    loaders = {
        "train": make_loader(
            ImageSampleDataset(train_samples, training_transform()),
            args.batch_size,
            True,
            args.workers,
            use_cuda,
        ),
        "validation": make_loader(
            ImageSampleDataset(validation_samples, evaluation_transform()),
            args.batch_size,
            False,
            args.workers,
            use_cuda,
        ),
    }

    print(
        f"Thiết bị: {device}; model: {args.model}; pretrained: {args.pretrained}; AMP: {amp_enabled}",
        flush=True,
    )
    model = build_model(args.model, len(CLASSES), pretrained=args.pretrained).to(device)
    optimizer = torch.optim.AdamW(
        model.parameters(), lr=args.learning_rate, weight_decay=args.weight_decay
    )
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=args.epochs)

    if args.class_weighted:
        counts = np.array(list(class_counts(train_samples).values()), dtype=np.float32)
        weights = counts.sum() / (len(counts) * counts)
        loss_fn = nn.CrossEntropyLoss(weight=torch.tensor(weights, device=device))
    else:
        loss_fn = nn.CrossEntropyLoss()

    checkpoint_path = args.output / "best_model.pth"
    history: list[dict] = []
    best_macro_f1 = -1.0
    stale_epochs = 0

    for epoch in range(1, args.epochs + 1):
        train_metrics = run_epoch(
            model, loaders["train"], loss_fn, device, optimizer, amp_enabled
        )
        validation_metrics = run_epoch(
            model, loaders["validation"], loss_fn, device, None, amp_enabled
        )
        scheduler.step()
        epoch_result = {
            "epoch": epoch,
            "learning_rate": optimizer.param_groups[0]["lr"],
            "train": train_metrics,
            "validation": validation_metrics,
        }
        history.append(epoch_result)
        save_json(args.output / "history.json", history)
        print(epoch_result, flush=True)

        if validation_metrics["macro_f1"] > best_macro_f1:
            best_macro_f1 = validation_metrics["macro_f1"]
            stale_epochs = 0
            torch.save(
                {
                    "model_state_dict": model.state_dict(),
                    "architecture": args.model,
                    "classes": CLASSES,
                    "version": f"{args.model}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
                    "best_validation_macro_f1": best_macro_f1,
                    "seed": args.seed,
                    "pretrained": args.pretrained,
                    "input_size": 224,
                    "normalization": {
                        "mean": [0.485, 0.456, 0.406],
                        "std": [0.229, 0.224, 0.225],
                    },
                },
                checkpoint_path,
            )
        else:
            stale_epochs += 1
            if args.patience > 0 and stale_epochs >= args.patience:
                print(f"Early stopping sau {epoch} epoch.", flush=True)
                break

    if not checkpoint_path.exists():
        raise RuntimeError("Huấn luyện kết thúc nhưng không tạo được best_model.pth.")

    if args.evaluate_test:
        evaluate_checkpoint(
            checkpoint_path=checkpoint_path,
            data_root=args.data,
            output_dir=args.output,
            batch_size=args.batch_size,
            workers=args.workers,
        )


if __name__ == "__main__":
    main()
