from __future__ import annotations

import hashlib
import json
import random
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np
import torch
from PIL import Image
from torch import nn
from torch.utils.data import Dataset
from torchvision import models, transforms


CLASSES = [
    "Acne",
    "Candidiasis",
    "Eczema",
    "Lupus",
    "Psoriasis",
    "SkinCancer",
    "Tinea",
    "Warts",
]
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
IMAGENET_MEAN = [0.485, 0.456, 0.406]
IMAGENET_STD = [0.229, 0.224, 0.225]


@dataclass(frozen=True)
class ImageSample:
    path: Path
    label: int
    digest: str
    group_id: str | None = None


class ImageSampleDataset(Dataset):
    def __init__(self, samples: list[ImageSample], transform):
        self.samples = samples
        self.transform = transform

    def __len__(self) -> int:
        return len(self.samples)

    def __getitem__(self, index: int):
        sample = self.samples[index]
        with Image.open(sample.path) as image:
            rgb = image.convert("RGB")
        return self.transform(rgb), sample.label


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def collect_samples(data_root: Path, split: str, classes: list[str] = CLASSES) -> list[ImageSample]:
    split_root = data_root / split
    if not split_root.is_dir():
        raise FileNotFoundError(f"Không tìm thấy thư mục dữ liệu: {split_root}")

    samples: list[ImageSample] = []
    missing: list[str] = []
    for label, class_name in enumerate(classes):
        class_root = split_root / class_name
        if not class_root.is_dir():
            missing.append(class_name)
            continue
        for path in sorted(class_root.rglob("*")):
            if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS:
                digest = sha256_file(path)
                relative = path.relative_to(class_root)
                group_id = (
                    f"{data_root.resolve()}::{split}::{class_name}::{relative.parts[0]}"
                    if len(relative.parts) > 1
                    else digest
                )
                samples.append(ImageSample(path.resolve(), label, digest, group_id))

    if missing:
        raise ValueError(f"Split {split!r} thiếu lớp: {', '.join(missing)}")
    if not samples:
        raise ValueError(f"Split {split!r} không có ảnh thuộc tám lớp mục tiêu.")
    return samples


def validate_label_conflicts(samples: Iterable[ImageSample], classes: list[str] = CLASSES) -> None:
    labels_by_digest: dict[str, set[int]] = defaultdict(set)
    for sample in samples:
        labels_by_digest[sample.digest].add(sample.label)
    conflicts = [labels for labels in labels_by_digest.values() if len(labels) > 1]
    if conflicts:
        readable = [[classes[label] for label in sorted(labels)] for labels in conflicts[:5]]
        raise ValueError(f"Có {len(conflicts)} ảnh trùng nhưng mang nhãn khác nhau: {readable}")


def label_conflict_digests(samples: Iterable[ImageSample]) -> set[str]:
    labels_by_digest: dict[str, set[int]] = defaultdict(set)
    for sample in samples:
        labels_by_digest[sample.digest].add(sample.label)
    return {digest for digest, labels in labels_by_digest.items() if len(labels) > 1}


def exclude_digests(
    samples: list[ImageSample], excluded_digests: set[str]
) -> tuple[list[ImageSample], list[ImageSample]]:
    kept = [sample for sample in samples if sample.digest not in excluded_digests]
    excluded = [sample for sample in samples if sample.digest in excluded_digests]
    return kept, excluded


def deduplicate_samples(
    samples: list[ImageSample],
) -> tuple[list[ImageSample], list[ImageSample]]:
    kept: list[ImageSample] = []
    duplicates: list[ImageSample] = []
    seen: set[str] = set()
    for sample in sorted(samples, key=lambda item: str(item.path).lower()):
        if sample.digest in seen:
            duplicates.append(sample)
        else:
            seen.add(sample.digest)
            kept.append(sample)
    return kept, duplicates


def exclude_cross_split_duplicates(
    train_samples: list[ImageSample], test_samples: list[ImageSample]
) -> tuple[list[ImageSample], list[ImageSample]]:
    test_hashes = {sample.digest for sample in test_samples}
    excluded = [sample for sample in train_samples if sample.digest in test_hashes]
    kept = [sample for sample in train_samples if sample.digest not in test_hashes]
    return kept, excluded


def grouped_stratified_split(
    samples: list[ImageSample], val_ratio: float, seed: int, num_classes: int
) -> tuple[list[ImageSample], list[ImageSample]]:
    if not 0 < val_ratio < 1:
        raise ValueError("val_ratio phải nằm trong khoảng (0, 1).")

    train: list[ImageSample] = []
    validation: list[ImageSample] = []
    rng = random.Random(seed)

    for label in range(num_classes):
        by_group: dict[str, list[ImageSample]] = defaultdict(list)
        for sample in samples:
            if sample.label == label:
                by_group[sample.group_id or sample.digest].append(sample)

        groups = list(by_group.values())
        if len(groups) < 2:
            raise ValueError(f"Lớp {CLASSES[label]} cần ít nhất hai nhóm ảnh khác nhau để chia validation.")
        rng.shuffle(groups)
        target = max(1, round(sum(len(group) for group in groups) * val_ratio))
        selected = 0
        for index, group in enumerate(groups):
            groups_left = len(groups) - index - 1
            if selected < target and groups_left >= 1:
                validation.extend(group)
                selected += len(group)
            else:
                train.extend(group)

    rng.shuffle(train)
    rng.shuffle(validation)
    return train, validation


def class_counts(samples: Iterable[ImageSample], classes: list[str] = CLASSES) -> dict[str, int]:
    counts = Counter(sample.label for sample in samples)
    return {name: counts[index] for index, name in enumerate(classes)}


def training_transform():
    return transforms.Compose(
        [
            transforms.Resize(256),
            transforms.RandomResizedCrop(224, scale=(0.8, 1.0)),
            transforms.RandomHorizontalFlip(),
            transforms.RandomRotation(12),
            transforms.ColorJitter(0.15, 0.15, 0.15, 0.05),
            transforms.ToTensor(),
            transforms.Normalize(IMAGENET_MEAN, IMAGENET_STD),
        ]
    )


def evaluation_transform():
    return transforms.Compose(
        [
            transforms.Resize(256),
            transforms.CenterCrop(224),
            transforms.ToTensor(),
            transforms.Normalize(IMAGENET_MEAN, IMAGENET_STD),
        ]
    )


def build_model(name: str, classes: int, pretrained: bool = True) -> nn.Module:
    if name == "resnet50":
        model = models.resnet50(weights=models.ResNet50_Weights.DEFAULT if pretrained else None)
        model.fc = nn.Linear(model.fc.in_features, classes)
    elif name == "convnext_tiny":
        model = models.convnext_tiny(
            weights=models.ConvNeXt_Tiny_Weights.DEFAULT if pretrained else None
        )
        model.classifier[2] = nn.Linear(model.classifier[2].in_features, classes)
    else:
        model = models.efficientnet_b0(
            weights=models.EfficientNet_B0_Weights.DEFAULT if pretrained else None
        )
        model.classifier[1] = nn.Linear(model.classifier[1].in_features, classes)
    return model


def seed_everything(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.benchmark = False
    torch.backends.cudnn.deterministic = True


def save_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
