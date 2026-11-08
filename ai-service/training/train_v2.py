from __future__ import annotations

import argparse
import copy
import hashlib
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
    sha256_file,
    seed_everything,
)


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


PROJECT = Path(__file__).resolve().parents[2]


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
    parser.add_argument(
        "--near-test-distance", type=int, default=None,
        help="Separate dHash radius for excluding old fixed-test neighbours; defaults to near-duplicate-distance.",
    )
    parser.add_argument("--near-pixel-correlation", type=float, default=None)
    parser.add_argument("--reviewed-scene-manifest", type=Path, default=None)
    parser.add_argument("--patience", type=int, default=7)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--oof-fold", type=int, choices=range(5), default=None)
    parser.add_argument("--oof-outer-manifest", type=Path, default=None)
    parser.add_argument("--oof-inner-plan", type=Path, default=None)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--amp", action=argparse.BooleanOptionalAction, default=True)
    return parser.parse_args()


def assigned_oof_roles(grouped_samples, outer_manifest: Path, inner_plan: Path, fold: int):
    """Return train, inner validation and untouched outer samples from locked roles."""
    outer = json.loads(outer_manifest.read_text(encoding="utf-8"))
    inner = json.loads(inner_plan.read_text(encoding="utf-8"))
    rows = outer["images"]
    canonical = "".join(
        f"{row['fold']}\t{row['class']}\t{row['path']}\t{row['sha256']}\t{row['scene_or_case_group']}\n"
        for row in rows
    )
    manifest_sha256 = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    if (
        outer["source_split_fingerprint_sha256"] != "922f900cfed05bca4c5e9ea6b3ae65b4f64381363bed22ca2e007c23c7e6f9c4"
        or manifest_sha256 != outer["manifest_sha256"]
        or inner["outer_manifest_sha256"] != manifest_sha256
        or len(rows) != 5937
    ):
        raise ValueError("OOF manifests do not match the audited development pool")
    plan = next((item for item in inner["folds"] if item["outer_fold"] == fold), None)
    if plan is None:
        raise ValueError(f"Missing inner plan for fold {fold}")
    by_path = {row["path"]: row for row in rows}
    inner_paths = set(plan["inner_validation_paths"])
    if len(by_path) != len(rows) or len(inner_paths) != len(plan["inner_validation_paths"]):
        raise ValueError("Repeated image path in OOF manifests")
    roles = {"train": [], "inner_validation": [], "outer_holdout": []}
    seen = set()
    for sample in grouped_samples:
        relative = sample.path.relative_to(PROJECT).as_posix()
        row = by_path.get(relative)
        if row is None or relative in seen:
            raise ValueError(f"Grouped sample missing or repeated in OOF manifest: {relative}")
        seen.add(relative)
        if (
            row["sha256"] != sample.digest
            or row["class"] != CLASSES[sample.label]
            or row["scene_or_case_group"] != (sample.group_id or sample.digest)
        ):
            raise ValueError(f"OOF sample label, hash or group changed: {relative}")
        if row["fold"] == fold:
            if relative in inner_paths:
                raise ValueError("Outer fold image also appears in inner validation")
            role = "outer_holdout"
        elif relative in inner_paths:
            role = "inner_validation"
        else:
            role = "train"
        roles[role].append(sample)
    if seen != set(by_path):
        raise ValueError("OOF manifest contains an image absent from the grouped development pool")
    groups = {
        role: {sample.group_id or sample.digest for sample in values}
        for role, values in roles.items()
    }
    if any(groups[left] & groups[right] for left, right in (
        ("train", "inner_validation"), ("train", "outer_holdout"),
        ("inner_validation", "outer_holdout"),
    )):
        raise ValueError("A case or scene crosses OOF training roles")
    for role, values in roles.items():
        expected = plan[f"{role}_images"]
        if len(values) != expected or class_counts(values) != plan["class_images"][role]:
            raise ValueError(f"OOF {role} count differs from locked inner plan")
    return roles["train"], roles["inner_validation"], roles["outer_holdout"], manifest_sha256


def dhash(path: Path) -> int:
    with Image.open(path) as image:
        gray = image.convert("L").resize((9, 8), Image.Resampling.LANCZOS)
        values = np.asarray(gray, dtype=np.int16)
    bits = values[:, 1:] > values[:, :-1]
    result = 0
    for bit in bits.reshape(-1):
        result = (result << 1) | int(bit)
    return result


def normalized_gray(path: Path) -> np.ndarray:
    with Image.open(path) as image:
        pixels = np.asarray(
            image.convert("L").resize((96, 96), Image.Resampling.LANCZOS),
            dtype=np.float32,
        ).reshape(-1)
    return (pixels - pixels.mean()) / (pixels.std() + 1e-6)


def load_reviewed_scene_pairs(path: Path, project: Path = PROJECT) -> list[tuple[Path, Path]]:
    review = json.loads(path.read_text(encoding="utf-8"))
    pairs = []
    for row in review["pairs"]:
        if row["decision"] != "same_scene_or_lesion_by_visual_review":
            raise ValueError("Reviewed manifest contains an unconfirmed pair")
        resolved = []
        for path_key, digest_key in (
            ("validation_path", "validation_sha256"), ("train_path", "train_sha256")
        ):
            image = project.joinpath(*row[path_key].split("/")).resolve()
            if not image.is_relative_to(project.resolve()) or sha256_file(image) != row[digest_key]:
                raise ValueError(f"Reviewed image changed or left project: {row[path_key]}")
            resolved.append(image)
        pairs.append((resolved[0], resolved[1]))
    return pairs


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
    samples: list[ImageSample], hashes: dict[Path, int], radius: int,
    pixel_correlation: float | None = None,
    reviewed_pairs: list[tuple[Path, Path]] | None = None,
) -> tuple[list[ImageSample], list[ImageSample], dict]:
    if pixel_correlation is not None and not -1 <= pixel_correlation <= 1:
        raise ValueError("Pixel correlation must be in [-1, 1]")
    union = UnionFind(len(samples))
    trees: dict[int, BkNode] = {}
    gray_cache: dict[Path, np.ndarray] = {}
    candidate_pairs = 0
    pixel_accepted_pairs = 0
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
                candidate_pairs += 1
                if pixel_correlation is not None:
                    left = gray_cache.get(sample.path)
                    if left is None:
                        left = normalized_gray(sample.path)
                        gray_cache[sample.path] = left
                    right_path = samples[match].path
                    right = gray_cache.get(right_path)
                    if right is None:
                        right = normalized_gray(right_path)
                        gray_cache[right_path] = right
                    if float(np.mean(left * right)) < pixel_correlation:
                        continue
                pixel_accepted_pairs += 1
                union.union(index, match)
            tree.add(value, index)

    index_by_path = {sample.path: index for index, sample in enumerate(samples)}
    for left_path, right_path in reviewed_pairs or []:
        if left_path not in index_by_path or right_path not in index_by_path:
            raise ValueError("Reviewed pair missing from training pool")
        left, right = index_by_path[left_path], index_by_path[right_path]
        if samples[left].label != samples[right].label:
            raise ValueError("Reviewed pair has conflicting labels")
        union.union(left, right)

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
        "dhash_candidate_pairs": candidate_pairs,
        "pixel_accepted_pairs": pixel_accepted_pairs,
        "pixel_correlation_threshold": pixel_correlation,
        "reviewed_pairs_linked": len(reviewed_pairs or []),
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
    if args.oof_fold is not None:
        if args.oof_outer_manifest is None:
            args.oof_outer_manifest = PROJECT / "ai-service/reports/scene_grouped_oof_folds_seed42.json"
        if args.oof_inner_plan is None:
            args.oof_inner_plan = PROJECT / "ai-service/reports/scene_grouped_oof_inner_seed42.json"
        if args.output.exists():
            raise FileExistsError(f"Preserving prior OOF run: {args.output}")
    elif args.oof_outer_manifest is not None or args.oof_inner_plan is not None:
        raise ValueError("OOF manifest paths require --oof-fold")
    near_test_distance = args.near_duplicate_distance if args.near_test_distance is None else args.near_test_distance
    if args.near_duplicate_distance < 0 or near_test_distance < 0:
        raise ValueError("dHash radii cannot be negative")
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
        train_clean, test_clean, near_test_distance
    )
    reviewed_pairs = load_reviewed_scene_pairs(args.reviewed_scene_manifest) if args.reviewed_scene_manifest else None
    grouped_train, near_label_conflicts, near_audit = group_near_duplicates(
        train_clean, hashes, args.near_duplicate_distance,
        pixel_correlation=args.near_pixel_correlation, reviewed_pairs=reviewed_pairs,
    )
    outer_samples = []
    oof_manifest_sha256 = None
    if args.oof_fold is None:
        train_samples, validation_samples = grouped_stratified_split(
            grouped_train, args.val_ratio, args.seed, len(CLASSES)
        )
    else:
        train_samples, validation_samples, outer_samples, oof_manifest_sha256 = assigned_oof_roles(
            grouped_train, args.oof_outer_manifest, args.oof_inner_plan, args.oof_fold
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
        "near_test_distance": near_test_distance,
        "near_train_validation_group_distance": args.near_duplicate_distance,
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
    if args.oof_fold is not None:
        summary["oof"] = {
            "outer_fold": args.oof_fold,
            "outer_manifest_sha256": oof_manifest_sha256,
            "outer_holdout": class_counts(outer_samples),
            "outer_holdout_images": len(outer_samples),
            "checkpoint_selection_role": "inner_validation_only",
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
        "configuration": vars(args) | {
            "data": str(args.data),
            "extra_data": [str(x) for x in args.extra_data],
            "output": str(args.output),
            "reviewed_scene_manifest": (
                str(args.reviewed_scene_manifest) if args.reviewed_scene_manifest else None
            ),
            "oof_outer_manifest": str(args.oof_outer_manifest) if args.oof_outer_manifest else None,
            "oof_inner_plan": str(args.oof_inner_plan) if args.oof_inner_plan else None,
        },
        "fixed_test_used_for_selection": False,
        "external_test_used_for_selection": False,
    }
    save_json(args.output / "selection_report.json", report)
    print(json.dumps(report["best"], ensure_ascii=False, indent=2), flush=True)

    if args.oof_fold is not None:
        checkpoint = torch.load(checkpoint_path, map_location="cpu", weights_only=False)
        model.load_state_dict(checkpoint["model_state_dict"])
        model.eval()
        outer_loader = make_loader(
            ImageSampleDataset(outer_samples, evaluation_transform()),
            args.batch_size, False, args.workers, use_cuda,
        )
        probability_rows = []
        with torch.inference_mode():
            for inputs, _labels in outer_loader:
                logits = model(inputs.to(device, non_blocking=True))
                probability_rows.extend(torch.softmax(logits, dim=1).cpu().tolist())
        if len(probability_rows) != len(outer_samples):
            raise RuntimeError("OOF prediction count differs from outer fold size")
        save_json(args.output / "oof_predictions.json", {
            "scope": "Outer-fold predictions from a checkpoint chosen on separate inner validation; development data, not independent test.",
            "outer_fold": args.oof_fold,
            "outer_manifest_sha256": oof_manifest_sha256,
            "architecture": args.model,
            "classes": CLASSES,
            "checkpoint_sha256": sha256_file(checkpoint_path),
            "rows": [
                {
                    "path": sample.path.relative_to(PROJECT).as_posix(),
                    "sha256": sample.digest,
                    "class": CLASSES[sample.label],
                    "probabilities": probabilities,
                }
                for sample, probabilities in zip(outer_samples, probability_rows)
            ],
        })
        print(f"Saved {len(probability_rows)} OOF predictions for fold {args.oof_fold}.", flush=True)


if __name__ == "__main__":
    main()
