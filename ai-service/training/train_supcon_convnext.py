"""Fine-tune the existing ConvNeXt with weighted CE and supervised contrastive loss."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import random
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import torch
from PIL import Image
from sklearn.metrics import classification_report
from torch import nn
from torch.nn import functional as F
from torch.utils.data import DataLoader, Dataset, Sampler

from common import (
    CLASSES, IMAGENET_MEAN, IMAGENET_STD, ImageSample, ImageSampleDataset,
    build_model, class_counts, collect_samples, deduplicate_samples,
    evaluation_transform, exclude_cross_split_duplicates, exclude_digests,
    grouped_stratified_split, label_conflict_digests, save_json, seed_everything,
    sha256_file,
)
from train_v2 import (
    classifier_parameters, effective_number_weights, group_near_duplicates,
    load_reviewed_scene_pairs,
    make_loader, remove_near_test_duplicates, run_epoch, training_transform_v2,
    update_ema,
)


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def split_fingerprint(train: list[ImageSample], validation: list[ImageSample]) -> str:
    rows = sorted(
        (split, sample.path.relative_to(Path(__file__).resolve().parents[2]).as_posix(), sample.digest)
        for split, samples in (("train", train), ("validation", validation))
        for sample in samples
    )
    digest = hashlib.sha256()
    for split, path, image_digest in rows:
        digest.update(f"{split}\t{path}\t{image_digest}\n".encode("utf-8"))
    return digest.hexdigest()


class TwoViewDataset(Dataset):
    def __init__(self, samples: list[ImageSample]) -> None:
        self.samples = samples
        self.transform = training_transform_v2()

    def __len__(self) -> int:
        return len(self.samples)

    def __getitem__(self, index: int):
        sample = self.samples[index]
        with Image.open(sample.path) as image:
            rgb = image.convert("RGB")
        return self.transform(rgb), self.transform(rgb), sample.label


class BalancedSupConBatchSampler(Sampler[list[int]]):
    """Draw four labels and two distinct source images per label per batch."""

    def __init__(self, samples: list[ImageSample], seed: int) -> None:
        self.by_class: dict[int, list[int]] = defaultdict(list)
        for index, sample in enumerate(samples):
            self.by_class[sample.label].append(index)
        if len(self.by_class) < 4 or any(len(indices) < 2 for indices in self.by_class.values()):
            raise ValueError("Balanced SupCon needs four classes and two images per class.")
        self.classes = sorted(self.by_class)
        self.seed = seed
        self.epoch = 0
        self.batches_per_epoch = math.ceil(len(samples) / 8)

    def __len__(self) -> int:
        return self.batches_per_epoch

    def __iter__(self):
        rng = random.Random(self.seed + self.epoch)
        self.epoch += 1
        for _ in range(self.batches_per_epoch):
            classes = rng.sample(self.classes, 4)
            batch = [index for label in classes for index in rng.sample(self.by_class[label], 2)]
            rng.shuffle(batch)
            yield batch


def supcon_loss(embeddings: torch.Tensor, labels: torch.Tensor, temperature: float = 0.07) -> torch.Tensor:
    """Multi-positive supervised contrastive objective; input has two views per image."""
    if embeddings.ndim != 2 or len(embeddings) != len(labels) or len(labels) < 2:
        raise ValueError("SupCon cần embedding 2D và nhãn cùng số lượng.")
    if not 0 < temperature:
        raise ValueError("Contrastive temperature phải dương.")
    # Keep the similarity matrix and logsumexp in float32 under CUDA AMP.
    with torch.autocast(device_type=embeddings.device.type, enabled=False):
        vectors = F.normalize(embeddings.float(), dim=1)
        similarities = vectors @ vectors.T / temperature
        diagonal = torch.eye(len(labels), dtype=torch.bool, device=labels.device)
        positives = (labels[:, None] == labels[None, :]) & ~diagonal
        counts = positives.sum(dim=1)
        if torch.any(counts == 0):
            raise ValueError("Mỗi ảnh cần ít nhất một positive; dùng hai view mỗi ảnh.")
        log_probabilities = similarities.masked_fill(diagonal, -1e9)
        log_probabilities = log_probabilities - torch.logsumexp(log_probabilities, dim=1, keepdim=True)
        return -((log_probabilities * positives).sum(dim=1) / counts).mean()


def forward_with_embeddings(model: nn.Module, images: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
    features = model.features(images)
    pooled = model.avgpool(features)
    normalized = model.classifier[0](pooled)
    embeddings = model.classifier[1](normalized)
    return model.classifier[2](embeddings), embeddings


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=Path("SkinDisease"))
    parser.add_argument("--extra-data", action="append", type=Path, default=[])
    parser.add_argument("--init-checkpoint", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--epochs", type=int, default=8)
    parser.add_argument("--batch-size", type=int, default=8, help="Original images; each yields two views")
    parser.add_argument("--balanced-batch", action="store_true", help="Four classes and two source images per class")
    parser.add_argument("--workers", type=int, default=0)
    parser.add_argument("--backbone-lr", type=float, default=1e-5)
    parser.add_argument("--head-lr", type=float, default=5e-5)
    parser.add_argument("--projection-lr", type=float, default=1e-4)
    parser.add_argument("--weight-decay", type=float, default=0.01)
    parser.add_argument("--label-smoothing", type=float, default=0.1)
    parser.add_argument("--effective-number-beta", type=float, default=0.9999)
    parser.add_argument("--contrastive-weight", type=float, default=0.1)
    parser.add_argument("--contrastive-temperature", type=float, default=0.07)
    parser.add_argument("--projection-dim", type=int, default=128)
    parser.add_argument("--ema-decay", type=float, default=0.5)
    parser.add_argument("--val-ratio", type=float, default=0.15)
    parser.add_argument("--near-duplicate-distance", type=int, default=0)
    parser.add_argument(
        "--near-test-distance", type=int, default=None,
        help="Optional separate dHash radius for excluding old fixed-test neighbours; defaults to near-duplicate-distance.",
    )
    parser.add_argument("--near-pixel-correlation", type=float, default=None)
    parser.add_argument("--reviewed-scene-manifest", type=Path, default=None)
    parser.add_argument("--expected-split-fingerprint", type=str, default=None)
    parser.add_argument("--patience", type=int, default=4)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--amp", action=argparse.BooleanOptionalAction, default=True)
    return parser.parse_args()


def cleaned_train_validation(args: argparse.Namespace) -> tuple[list[ImageSample], list[ImageSample], dict]:
    near_test_distance = getattr(args, "near_test_distance", None)
    if near_test_distance is None:
        near_test_distance = args.near_duplicate_distance
    if near_test_distance < 0 or args.near_duplicate_distance < 0:
        raise ValueError("dHash radii cannot be negative")
    base_train = collect_samples(args.data, "train")
    extra_by_root = {str(root): collect_samples(root, "train") for root in args.extra_data}
    raw_train = [*base_train, *(sample for values in extra_by_root.values() for sample in values)]
    raw_test = collect_samples(args.data, "test")
    conflicts = label_conflict_digests([*raw_train, *raw_test])
    train_clean, conflicting = exclude_digests(raw_train, conflicts)
    test_clean, _ = exclude_digests(raw_test, conflicts)
    train_clean, duplicate = deduplicate_samples(train_clean)
    test_clean, _ = deduplicate_samples(test_clean)
    train_clean, cross_split = exclude_cross_split_duplicates(train_clean, test_clean)
    train_clean, near_test, hashes = remove_near_test_duplicates(
        train_clean, test_clean, near_test_distance
    )
    reviewed_scene_manifest = getattr(args, "reviewed_scene_manifest", None)
    reviewed_pairs = load_reviewed_scene_pairs(reviewed_scene_manifest) if reviewed_scene_manifest else None
    grouped, near_conflict, near_audit = group_near_duplicates(
        train_clean, hashes, args.near_duplicate_distance,
        pixel_correlation=getattr(args, "near_pixel_correlation", None),
        reviewed_pairs=reviewed_pairs,
    )
    training, validation = grouped_stratified_split(grouped, args.val_ratio, args.seed, len(CLASSES))
    summary = {
        "classes": CLASSES,
        "seed": args.seed,
        "train": class_counts(training),
        "validation": class_counts(validation),
        "fixed_test_untouched": class_counts(test_clean),
        "totals": {"train": len(training), "validation": len(validation), "fixed_test_untouched": len(test_clean)},
        "excluded": {
            "label_conflicts": class_counts(conflicting),
            "exact_duplicates": class_counts(duplicate),
            "exact_cross_split": class_counts(cross_split),
            "near_test": class_counts(near_test),
            "near_label_conflicts": class_counts(near_conflict),
        },
        "near_duplicate_audit": near_audit,
        "near_test_distance": near_test_distance,
        "near_train_validation_group_distance": args.near_duplicate_distance,
    }
    return training, validation, summary


def run_supcon_epoch(
    model: nn.Module, projection: nn.Module, loader: DataLoader,
    classification_loss: nn.Module, optimizer: torch.optim.Optimizer,
    scaler: torch.amp.GradScaler, device: torch.device,
    contrastive_weight: float, contrastive_temperature: float,
) -> dict:
    model.train()
    projection.train()
    totals = {"classification_loss": 0.0, "contrastive_loss": 0.0, "total_loss": 0.0}
    targets_all: list[int] = []
    predictions_all: list[int] = []
    image_count = 0
    for first, second, targets in loader:
        first = first.to(device, non_blocking=True)
        second = second.to(device, non_blocking=True)
        targets = targets.to(device, non_blocking=True)
        images = torch.cat([first, second], dim=0)
        doubled_targets = targets.repeat(2)
        optimizer.zero_grad(set_to_none=True)
        with torch.autocast(device_type=device.type, enabled=scaler.is_enabled()):
            logits, embeddings = forward_with_embeddings(model, images)
            projected = projection(embeddings)
            ce = classification_loss(logits, doubled_targets)
            contrastive = supcon_loss(projected, doubled_targets, contrastive_temperature)
            total = ce + contrastive_weight * contrastive
        scaler.scale(total).backward()
        scaler.unscale_(optimizer)
        torch.nn.utils.clip_grad_norm_(list(model.parameters()) + list(projection.parameters()), max_norm=2.0)
        scaler.step(optimizer)
        scaler.update()
        count = len(targets)
        image_count += count
        for key, value in (("classification_loss", ce), ("contrastive_loss", contrastive), ("total_loss", total)):
            totals[key] += float(value.detach()) * count
        targets_all.extend(targets.cpu().tolist())
        predictions_all.extend(logits[:count].argmax(dim=1).detach().cpu().tolist())
    report = classification_report(
        targets_all, predictions_all,
        labels=list(range(len(CLASSES))), target_names=CLASSES,
        output_dict=True, zero_division=0,
    )
    return {
        **{key: value / image_count for key, value in totals.items()},
        "accuracy": float(report["accuracy"]),
        "macro_f1": float(report["macro avg"]["f1-score"]),
        "per_class_f1": {name: float(report[name]["f1-score"]) for name in CLASSES},
    }


def main() -> None:
    args = parse_args()
    if args.epochs < 1 or args.batch_size < 2 or args.projection_dim < 2:
        raise ValueError("epochs, batch-size và projection-dim không hợp lệ.")
    if args.balanced_batch and args.batch_size != 8:
        raise ValueError("Balanced batch protocol requires --batch-size 8.")
    if not 0 < args.ema_decay < 1 or args.contrastive_weight < 0:
        raise ValueError("EMA hoặc trọng số SupCon không hợp lệ.")
    seed_everything(args.seed)
    args.output.mkdir(parents=True, exist_ok=True)
    training, validation, summary = cleaned_train_validation(args)
    fingerprint = split_fingerprint(training, validation)
    if args.expected_split_fingerprint and fingerprint != args.expected_split_fingerprint:
        raise ValueError(f"Development split fingerprint changed: {fingerprint}")
    summary["split_fingerprint_sha256"] = fingerprint
    prior_summary_path = args.init_checkpoint.parent / "dataset_summary.json"
    if prior_summary_path.exists():
        prior = json.loads(prior_summary_path.read_text(encoding="utf-8"))
        if any(summary[split] != prior[split] for split in ("train", "validation", "fixed_test_untouched")):
            raise ValueError("Split dữ liệu khác checkpoint ConvNeXt gốc; không thể so sánh công bằng.")
    save_json(args.output / "dataset_summary.json", summary)
    print(json.dumps(summary["totals"], ensure_ascii=False), flush=True)

    use_cuda = torch.cuda.is_available()
    device = torch.device("cuda" if use_cuda else "cpu")
    checkpoint = torch.load(args.init_checkpoint, map_location="cpu", weights_only=False)
    if checkpoint.get("architecture") != "convnext_tiny" or checkpoint.get("classes") != CLASSES:
        raise ValueError("Checkpoint đầu vào phải là ConvNeXt-Tiny đúng thứ tự tám lớp.")
    model = build_model("convnext_tiny", len(CLASSES), pretrained=False)
    model.load_state_dict(checkpoint["model_state_dict"])
    model = model.to(device)
    ema = copy.deepcopy(model).eval()
    for parameter in ema.parameters():
        parameter.requires_grad_(False)
    projection = nn.Sequential(
        nn.Linear(model.classifier[2].in_features, 256),
        nn.ReLU(inplace=True),
        nn.Linear(256, args.projection_dim),
    ).to(device)
    backbone, head = classifier_parameters(model)
    optimizer = torch.optim.AdamW(
        [
            {"params": backbone, "lr": args.backbone_lr},
            {"params": head, "lr": args.head_lr},
            {"params": projection.parameters(), "lr": args.projection_lr},
        ],
        weight_decay=args.weight_decay,
    )
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=args.epochs, eta_min=1e-6)
    weights, counts = effective_number_weights(training, args.effective_number_beta, device)
    loss_fn = nn.CrossEntropyLoss(weight=weights, label_smoothing=args.label_smoothing)
    scaler = torch.amp.GradScaler("cuda", enabled=bool(args.amp and use_cuda))
    if args.balanced_batch:
        train_loader = DataLoader(
            TwoViewDataset(training),
            batch_sampler=BalancedSupConBatchSampler(training, args.seed),
            num_workers=args.workers,
            pin_memory=use_cuda,
            persistent_workers=args.workers > 0,
        )
    else:
        train_loader = make_loader(TwoViewDataset(training), args.batch_size, True, args.workers, use_cuda)
    validation_loader = make_loader(
        ImageSampleDataset(validation, evaluation_transform()),
        args.batch_size * 2, False, args.workers, use_cuda,
    )
    initial = run_epoch(model, validation_loader, loss_fn, device)
    print(json.dumps({"initial_validation_macro_f1": initial["macro_f1"], "device": str(device), "class_counts": counts}), flush=True)
    history: list[dict] = []
    best: dict | None = None
    stale = 0
    for epoch in range(1, args.epochs + 1):
        train_result = run_supcon_epoch(
            model, projection, train_loader, loss_fn, optimizer, scaler,
            device, args.contrastive_weight, args.contrastive_temperature,
        )
        update_ema(ema, model, args.ema_decay)
        raw_validation = run_epoch(model, validation_loader, loss_fn, device)
        ema_validation = run_epoch(ema, validation_loader, loss_fn, device)
        scheduler.step()
        source = "ema" if ema_validation["macro_f1"] >= raw_validation["macro_f1"] else "raw"
        selected = ema_validation if source == "ema" else raw_validation
        row = {
            "epoch": epoch,
            "learning_rates": [group["lr"] for group in optimizer.param_groups],
            "train": train_result,
            "validation_raw": raw_validation,
            "validation_ema": ema_validation,
            "selected_weights": source,
        }
        history.append(row)
        save_json(args.output / "history.json", history)
        print(json.dumps({
            "epoch": epoch,
            "train_macro_f1": round(train_result["macro_f1"], 4),
            "train_ce": round(train_result["classification_loss"], 4),
            "train_supcon": round(train_result["contrastive_loss"], 4),
            "validation_macro_f1": round(selected["macro_f1"], 4),
            "weights": source,
        }), flush=True)
        objective = (selected["macro_f1"], selected["top3_accuracy"], -selected["loss"])
        if best is None or objective > best["objective"]:
            version = f"convnext_tiny-supcon-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
            best = {"objective": objective, "epoch": epoch, "source": source, "validation": selected, "version": version}
            torch.save({
                "model_state_dict": (ema if source == "ema" else model).state_dict(),
                "architecture": "convnext_tiny",
                "classes": CLASSES,
                "version": version,
                "seed": args.seed,
                "input_size": 224,
                "normalization": {"mean": IMAGENET_MEAN, "std": IMAGENET_STD},
                "training_recipe": (
                    "joint_weighted_ce_supervised_contrastive_balanced_batch_finetune"
                    if args.balanced_batch else "joint_weighted_ce_supervised_contrastive_finetune"
                ),
                "initial_checkpoint_sha256": sha256_file(args.init_checkpoint),
                "temperature": 1.0,
            }, args.output / "best_model.pth")
            stale = 0
        else:
            stale += 1
        if args.patience > 0 and stale >= args.patience:
            print(f"Early stopping at epoch {epoch}.", flush=True)
            break
    assert best is not None
    save_json(args.output / "selection_report.json", {
        "method": "joint weighted cross-entropy and supervised contrastive fine-tuning",
        "selection_policy": "Validation macro F1, then top-3, then CE loss; no fixed/SCIN test selection.",
        "initial_validation": initial,
        "best": {**best, "objective": list(best["objective"])},
        "configuration": {
            **vars(args),
            "data": str(args.data),
            "extra_data": [str(path) for path in args.extra_data],
            "init_checkpoint": str(args.init_checkpoint),
            "output": str(args.output),
            "reviewed_scene_manifest": (
                str(args.reviewed_scene_manifest) if args.reviewed_scene_manifest else None
            ),
        },
        "fixed_test_used_for_selection": False,
        "scin_case_holdout_used_for_selection": False,
    })
    print(json.dumps({"best_epoch": best["epoch"], "initial_macro_f1": initial["macro_f1"], "selected_macro_f1": best["validation"]["macro_f1"]}), flush=True)


if __name__ == "__main__":
    main()
