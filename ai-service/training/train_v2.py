from __future__ import annotations

import argparse
import copy
import json
import math
import sys
from collections import Counter
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import torch
from PIL import Image
from sklearn.metrics import classification_report
from torch import nn
from torch.utils.data import DataLoader
from torchvision import transforms

from common import (
    CLASSES,
    IMAGENET_MEAN,
    IMAGENET_STD,
    ImageSample,
    ImageSampleDataset,
    build_model,
    class_counts,
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


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Huấn luyện candidate V2 cho tám nhóm bệnh, giảm overfit và leakage."
    )
    parser.add_argument("--data", required=True, type=Path)
    parser.add_argument("--extra-data", action="append", type=Path, default=[])
    parser.add_argument(
        "--model",
        choices=["efficientnet_b0", "resnet50", "convnext_tiny"],
        default="efficientnet_b0",
    )
    parser.add_argument("--epochs", type=int, default=24)
    parser.add_argument("--freeze-epochs", type=int, default=2)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--workers", type=int, default=0)
    parser.add_argument("--learning-rate", type=float, default=2e-4)
    parser.add_argument("--backbone-lr-ratio", type=float, default=0.25)
    parser.add_argument("--weight-decay", type=float, default=2e-4)
    parser.add_argument("--label-smoothing", type=float, default=0.05)
    parser.add_argument("--effective-number-beta", type=float, default=0.999)
    parser.add_argument("--ema-decay", type=float, default=0.995)
    parser.add_argument("--val-ratio", type=float, default=0.15)
    parser.add_argument("--near-duplicate-distance", type=int, default=3)
    parser.add_argument("--patience", type=int, default=7)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--amp", action=argparse.BooleanOptionalAction, default=True)
    return parser.parse_args()


def dhash(path: Path) -> int:
    with Image.open(path) as image:
        gray = image.convert("L").resize((9, 8), Image.Resampling.LANCZOS)
        values = np.asarray(gray, dtype=np.int16)
    bits = values[:, 1:] > values[:, :-1]
    result = 0
    for bit in bits.reshape(-1):
        result = (result << 1) | int(bit)
    return result


class BkNode:
    def __init__(self, value: int, index: int):
        self.value = value
        self.indices = [index]
        self.children: dict[int, BkNode] = {}

    def add(self, value: int, index: int) -> None:
        distance = (self.value ^ value).bit_count()
        if distance == 0:
            self.indices.append(index)
            return
        child = self.children.get(distance)
        if child is None:
            self.children[distance] = BkNode(value, index)
        else:
            child.add(value, index)

    def query(self, value: int, radius: int, output: list[int]) -> None:
        distance = (self.value ^ value).bit_count()
        if distance <= radius:
            output.extend(self.indices)
        lower, upper = distance - radius, distance + radius
        for edge, child in self.children.items():
            if lower <= edge <= upper:
                child.query(value, radius, output)


class UnionFind:
    def __init__(self, size: int):
        self.parent = list(range(size))

    def find(self, value: int) -> int:
        while self.parent[value] != value:
            self.parent[value] = self.parent[self.parent[value]]
            value = self.parent[value]
        return value

    def union(self, left: int, right: int) -> None:
        left_root, right_root = self.find(left), self.find(right)
        if left_root != right_root:
            self.parent[right_root] = left_root


def remove_near_test_duplicates(
    train: list[ImageSample], test: list[ImageSample], radius: int
) -> tuple[list[ImageSample], list[ImageSample], dict[Path, int]]:
    train_hashes = {sample.path: dhash(sample.path) for sample in train}
    test_hashes = {sample.path: dhash(sample.path) for sample in test}
    test_tree: BkNode | None = None
    for index, value in enumerate(test_hashes.values()):
        if test_tree is None:
            test_tree = BkNode(value, index)
        else:
            test_tree.add(value, index)
    excluded: list[ImageSample] = []
    kept: list[ImageSample] = []
    assert test_tree is not None
    for sample in train:
        matches: list[int] = []
        test_tree.query(train_hashes[sample.path], radius, matches)
        (excluded if matches else kept).append(sample)
    return kept, excluded, train_hashes


def group_near_duplicates(
    samples: list[ImageSample], hashes: dict[Path, int], radius: int
) -> tuple[list[ImageSample], list[ImageSample], dict]:
    union = UnionFind(len(samples))
    trees: dict[int, BkNode] = {}
    for index, sample in enumerate(samples):
        value = hashes.get(sample.path)
        if value is None:
            value = dhash(sample.path)
            hashes[sample.path] = value
        tree = trees.get(sample.label)
        if tree is None:
            trees[sample.label] = BkNode(value, index)
        else:
            matches: list[int] = []
            tree.query(value, radius, matches)
            for match in matches:
                union.union(index, match)
            tree.add(value, index)

    # Keep every image from a known SCIN case in the same split even when
    # viewpoints differ enough that dHash does not link them.
    case_first_index: dict[str, int] = {}
    for index, sample in enumerate(samples):
        if not sample.group_id or sample.group_id == sample.digest:
            continue
        prior = case_first_index.get(sample.group_id)
        if prior is None:
            case_first_index[sample.group_id] = index
        else:
            union.union(index, prior)

    members: dict[int, list[int]] = {}
    for index in range(len(samples)):
        members.setdefault(union.find(index), []).append(index)
    conflicting_roots = {
        root
        for root, indices in members.items()
        if len({samples[index].label for index in indices}) > 1
    }
    conflicts: list[ImageSample] = []
    grouped: list[ImageSample] = []
    multi_image_groups = 0
    for root, indices in members.items():
        if root in conflicting_roots:
            conflicts.extend(samples[index] for index in indices)
            continue
        if len(indices) > 1:
            multi_image_groups += 1
        group_name = f"dhash:{hashes[samples[root].path]:016x}:{root}"
        for index in indices:
            grouped.append(replace(samples[index], group_id=group_name))
    return grouped, conflicts, {
        "groups": len(members),
        "multi_image_groups": multi_image_groups,
        "conflicting_groups": len(conflicting_roots),
    }


def training_transform_v2():
    return transforms.Compose(
        [
            transforms.Resize(256),
            transforms.RandomResizedCrop(224, scale=(0.82, 1.0), ratio=(0.88, 1.14)),
            transforms.RandomHorizontalFlip(),
            transforms.RandomRotation(15),
            transforms.ColorJitter(0.12, 0.12, 0.08, 0.02),
            transforms.ToTensor(),
            transforms.Normalize(IMAGENET_MEAN, IMAGENET_STD),
            transforms.RandomErasing(p=0.08, scale=(0.02, 0.06), ratio=(0.5, 2.0)),
        ]
    )


def classifier_parameters(model: nn.Module) -> tuple[list[nn.Parameter], list[nn.Parameter]]:
    if hasattr(model, "fc"):
        head = list(model.fc.parameters())
    else:
        head = list(model.classifier.parameters())
    head_ids = {id(parameter) for parameter in head}
    backbone = [parameter for parameter in model.parameters() if id(parameter) not in head_ids]
    return backbone, head


def make_loader(dataset, batch_size: int, shuffle: bool, workers: int, use_cuda: bool):
    return DataLoader(
        dataset,
        batch_size=batch_size,
        shuffle=shuffle,
        num_workers=workers,
        pin_memory=use_cuda,
        persistent_workers=workers > 0,
    )


def run_epoch(
    model: nn.Module,
    loader: DataLoader,
    loss_fn: nn.Module,
    device: torch.device,
    optimizer: torch.optim.Optimizer | None = None,
    scaler: torch.amp.GradScaler | None = None,
) -> dict:
    training = optimizer is not None
    model.train(training)
    losses: list[float] = []
    targets_all: list[int] = []
    predictions_all: list[int] = []
    top3_correct = 0
    for inputs, targets in loader:
        inputs = inputs.to(device, non_blocking=True)
        targets = targets.to(device, non_blocking=True)
        if training:
            optimizer.zero_grad(set_to_none=True)
        with torch.set_grad_enabled(training):
            with torch.autocast(device_type=device.type, enabled=scaler is not None and scaler.is_enabled()):
                logits = model(inputs)
                loss = loss_fn(logits, targets)
            if training:
                assert scaler is not None
                scaler.scale(loss).backward()
                scaler.unscale_(optimizer)
                torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=2.0)
                scaler.step(optimizer)
                scaler.update()
        losses.append(float(loss.detach().cpu()))
        predictions = logits.argmax(dim=1)
        top3_correct += int((logits.topk(3, dim=1).indices == targets[:, None]).any(dim=1).sum())
        targets_all.extend(targets.cpu().tolist())
        predictions_all.extend(predictions.cpu().tolist())
    report = classification_report(
        targets_all,
        predictions_all,
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
        "top3_accuracy": top3_correct / len(targets_all),
        "per_class_f1": {name: float(report[name]["f1-score"]) for name in CLASSES},
    }


def update_ema(ema: nn.Module, model: nn.Module, decay: float) -> None:
    with torch.no_grad():
        for ema_value, model_value in zip(ema.state_dict().values(), model.state_dict().values()):
            if torch.is_floating_point(ema_value):
                ema_value.mul_(decay).add_(model_value.detach(), alpha=1.0 - decay)
            else:
                ema_value.copy_(model_value)


def effective_number_weights(samples: list[ImageSample], beta: float, device: torch.device):
    counts = np.asarray(list(class_counts(samples).values()), dtype=np.float64)
    weights = (1.0 - beta) / np.maximum(1.0 - np.power(beta, counts), 1e-12)
    weights /= weights.mean()
    return torch.tensor(weights, dtype=torch.float32, device=device), counts.astype(int).tolist()


def main() -> None:
    args = parse_args()
    if not 0 <= args.label_smoothing < 0.5:
        raise ValueError("label-smoothing phải nằm trong [0, 0.5).")
    if not 0 < args.ema_decay < 1:
        raise ValueError("ema-decay phải nằm trong (0, 1).")
    seed_everything(args.seed)
    args.output.mkdir(parents=True, exist_ok=True)

    base_train = collect_samples(args.data, "train")
    extra_train_by_root = {str(root): collect_samples(root, "train") for root in args.extra_data}
    raw_train = [*base_train, *(sample for values in extra_train_by_root.values() for sample in values)]
    raw_test = collect_samples(args.data, "test")
    conflicts = label_conflict_digests([*raw_train, *raw_test])
    train_clean, exact_label_conflicts = exclude_digests(raw_train, conflicts)
    test_clean, _test_conflicts = exclude_digests(raw_test, conflicts)
    train_clean, exact_duplicates = deduplicate_samples(train_clean)
    test_clean, _test_duplicates = deduplicate_samples(test_clean)
    train_clean, exact_cross_split = exclude_cross_split_duplicates(train_clean, test_clean)

    print("Đang kiểm tra near-duplicate bằng dHash...", flush=True)
    train_clean, near_test_duplicates, hashes = remove_near_test_duplicates(
        train_clean, test_clean, args.near_duplicate_distance
    )
    grouped_train, near_label_conflicts, near_audit = group_near_duplicates(
        train_clean, hashes, args.near_duplicate_distance
    )
    train_samples, validation_samples = grouped_stratified_split(
        grouped_train, args.val_ratio, args.seed, len(CLASSES)
    )
    summary = {
        "classes": CLASSES,
        "seed": args.seed,
        "raw_train_sources": {
            str(args.data): class_counts(base_train),
            **{root: class_counts(samples) for root, samples in extra_train_by_root.items()},
        },
        "excluded": {
            "exact_label_conflicts": class_counts(exact_label_conflicts),
            "exact_duplicates": class_counts(exact_duplicates),
            "exact_train_test_duplicates": class_counts(exact_cross_split),
            "near_train_test_duplicates": class_counts(near_test_duplicates),
            "near_label_conflicts": class_counts(near_label_conflicts),
        },
        "near_duplicate_audit": near_audit,
        "train": class_counts(train_samples),
        "validation": class_counts(validation_samples),
        "fixed_test_untouched": class_counts(test_clean),
        "totals": {
            "raw_train": len(raw_train),
            "train": len(train_samples),
            "validation": len(validation_samples),
            "fixed_test_untouched": len(test_clean),
        },
    }
    save_json(args.output / "dataset_summary.json", summary)
    print(json.dumps(summary["totals"], ensure_ascii=False), flush=True)

    use_cuda = torch.cuda.is_available()
    device = torch.device("cuda" if use_cuda else "cpu")
    amp_enabled = bool(args.amp and use_cuda)
    loaders = {
        "train": make_loader(
            ImageSampleDataset(train_samples, training_transform_v2()),
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
    model = build_model(args.model, len(CLASSES), pretrained=True).to(device)
    ema = copy.deepcopy(model).eval()
    for parameter in ema.parameters():
        parameter.requires_grad_(False)
    backbone, head = classifier_parameters(model)
    for parameter in backbone:
        parameter.requires_grad_(False)
    optimizer = torch.optim.AdamW(
        [
            {"params": backbone, "lr": args.learning_rate * args.backbone_lr_ratio},
            {"params": head, "lr": args.learning_rate},
        ],
        weight_decay=args.weight_decay,
    )
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(
        optimizer, T_max=max(1, args.epochs - args.freeze_epochs), eta_min=1e-6
    )
    weights, counts = effective_number_weights(
        train_samples, args.effective_number_beta, device
    )
    loss_fn = nn.CrossEntropyLoss(weight=weights, label_smoothing=args.label_smoothing)
    scaler = torch.amp.GradScaler("cuda", enabled=amp_enabled)

    history: list[dict] = []
    best: dict | None = None
    stale = 0
    checkpoint_path = args.output / "best_model.pth"
    print(
        f"Thiết bị={device}; model={args.model}; train={len(train_samples)}; val={len(validation_samples)}; class_counts={counts}",
        flush=True,
    )
    for epoch in range(1, args.epochs + 1):
        if epoch == args.freeze_epochs + 1:
            for parameter in backbone:
                parameter.requires_grad_(True)
            print("Đã mở khóa backbone để fine-tune toàn bộ.", flush=True)
        train_metrics = run_epoch(
            model, loaders["train"], loss_fn, device, optimizer, scaler
        )
        update_ema(ema, model, args.ema_decay)
        raw_validation = run_epoch(model, loaders["validation"], loss_fn, device)
        ema_validation = run_epoch(ema, loaders["validation"], loss_fn, device)
        if epoch > args.freeze_epochs:
            scheduler.step()
        source = "ema" if ema_validation["macro_f1"] >= raw_validation["macro_f1"] else "raw"
        selected_validation = ema_validation if source == "ema" else raw_validation
        result = {
            "epoch": epoch,
            "learning_rates": [group["lr"] for group in optimizer.param_groups],
            "backbone_frozen": epoch <= args.freeze_epochs,
            "train": train_metrics,
            "validation_raw": raw_validation,
            "validation_ema": ema_validation,
            "selected_weights": source,
        }
        history.append(result)
        save_json(args.output / "history.json", history)
        print(
            json.dumps(
                {
                    "epoch": epoch,
                    "train_macro_f1": round(train_metrics["macro_f1"], 4),
                    "validation_macro_f1": round(selected_validation["macro_f1"], 4),
                    "validation_accuracy": round(selected_validation["accuracy"], 4),
                    "weights": source,
                },
                ensure_ascii=False,
            ),
            flush=True,
        )
        objective = (
            selected_validation["macro_f1"],
            selected_validation["top3_accuracy"],
            -selected_validation["loss"],
        )
        if best is None or objective > best["objective"]:
            state = ema.state_dict() if source == "ema" else model.state_dict()
            version = f"{args.model}-v2-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
            best = {
                "objective": objective,
                "epoch": epoch,
                "source": source,
                "validation": selected_validation,
                "version": version,
            }
            torch.save(
                {
                    "model_state_dict": state,
                    "architecture": args.model,
                    "classes": CLASSES,
                    "version": version,
                    "best_validation_macro_f1": selected_validation["macro_f1"],
                    "best_validation_accuracy": selected_validation["accuracy"],
                    "best_validation_top3_accuracy": selected_validation["top3_accuracy"],
                    "seed": args.seed,
                    "pretrained": True,
                    "input_size": 224,
                    "normalization": {"mean": IMAGENET_MEAN, "std": IMAGENET_STD},
                    "training_recipe": "v2_progressive_finetune_effective_weights_label_smoothing_ema",
                    "temperature": 1.0,
                },
                checkpoint_path,
            )
            stale = 0
        else:
            stale += 1
        if epoch > args.freeze_epochs and args.patience > 0 and stale >= args.patience:
            print(f"Early stopping sau epoch {epoch}.", flush=True)
            break

    if best is None or not checkpoint_path.exists():
        raise RuntimeError("Không tạo được candidate checkpoint.")
    report = {
        "selection_policy": "Epoch/weights selected only by validation macro F1, then top-3, then loss.",
        "best": {**best, "objective": list(best["objective"])},
        "configuration": vars(args) | {"data": str(args.data), "extra_data": [str(x) for x in args.extra_data], "output": str(args.output)},
        "fixed_test_used_for_selection": False,
        "external_test_used_for_selection": False,
    }
    save_json(args.output / "selection_report.json", report)
    print(json.dumps(report["best"], ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
