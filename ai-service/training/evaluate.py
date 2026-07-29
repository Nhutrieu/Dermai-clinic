from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import torch
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, f1_score
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
    label_conflict_digests,
    save_json,
)


def save_confusion_matrix(
    matrix: np.ndarray, output_path: Path, classes: list[str], split: str
) -> None:
    figure, axis = plt.subplots(figsize=(10, 9))
    image = axis.imshow(matrix, interpolation="nearest", cmap="Blues")
    figure.colorbar(image, ax=axis, fraction=0.046, pad=0.04)
    axis.set(
        xticks=np.arange(len(classes)),
        yticks=np.arange(len(classes)),
        xticklabels=classes,
        yticklabels=classes,
        ylabel="Nhãn thật",
        xlabel="Nhãn dự đoán",
        title=f"Confusion matrix — {split}",
    )
    plt.setp(axis.get_xticklabels(), rotation=45, ha="right", rotation_mode="anchor")
    threshold = matrix.max() / 2 if matrix.size else 0
    for row in range(matrix.shape[0]):
        for column in range(matrix.shape[1]):
            axis.text(
                column,
                row,
                str(matrix[row, column]),
                ha="center",
                va="center",
                color="white" if matrix[row, column] > threshold else "black",
                fontsize=8,
            )
    figure.tight_layout()
    figure.savefig(output_path, dpi=180, bbox_inches="tight")
    plt.close(figure)


def evaluate_checkpoint(
    checkpoint_path: Path,
    data_root: Path,
    output_dir: Path,
    batch_size: int = 32,
    workers: int = 2,
    split: str = "test",
    reference_data_roots: list[Path] | None = None,
) -> dict:
    checkpoint = torch.load(checkpoint_path, map_location="cpu", weights_only=False)
    classes = checkpoint.get("classes", CLASSES)
    if classes != CLASSES:
        raise ValueError(f"Class map checkpoint không khớp pipeline: {classes}")

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = build_model(
        checkpoint.get("architecture", "efficientnet_b0"), len(classes), pretrained=False
    )
    model.load_state_dict(checkpoint["model_state_dict"])
    model.to(device).eval()

    raw_evaluation = collect_samples(data_root, split, classes)
    references: list = []
    roots = reference_data_roots
    if roots is None and split == "test":
        roots = [data_root]
    for root in roots or []:
        references.extend(collect_samples(root, "train", classes))
    conflicts = label_conflict_digests([*references, *raw_evaluation])
    evaluation_without_conflicts, _ = exclude_digests(raw_evaluation, conflicts)
    if split == "test":
        # The training pipeline preserves the fixed test set and removes matching
        # copies from train. Keep the same policy so historical metrics remain comparable.
        evaluation_without_leakage = evaluation_without_conflicts
        cross_split_duplicates = []
    else:
        # External evaluation must not contain an image already available to training.
        evaluation_without_leakage, cross_split_duplicates = exclude_cross_split_duplicates(
            evaluation_without_conflicts, references
        )
    samples, within_split_duplicates = deduplicate_samples(evaluation_without_leakage)
    loader = DataLoader(
        ImageSampleDataset(samples, evaluation_transform()),
        batch_size=batch_size,
        shuffle=False,
        num_workers=workers,
        pin_memory=device.type == "cuda",
        persistent_workers=workers > 0,
    )

    targets: list[int] = []
    predictions: list[int] = []
    top3_correct = 0
    with torch.inference_mode():
        for inputs, labels in loader:
            inputs = inputs.to(device, non_blocking=True)
            logits = model(inputs)
            predicted = logits.argmax(dim=1).cpu()
            top3 = logits.topk(min(3, len(classes)), dim=1).indices.cpu()
            targets.extend(labels.tolist())
            predictions.extend(predicted.tolist())
            top3_correct += int((top3 == labels.unsqueeze(1)).any(dim=1).sum())

    labels = list(range(len(classes)))
    observed_labels = sorted(set(targets))
    report = classification_report(
        targets,
        predictions,
        labels=labels,
        target_names=classes,
        output_dict=True,
        zero_division=0,
    )
    matrix = confusion_matrix(targets, predictions, labels=labels)
    metrics = {
        "checkpoint": checkpoint_path.name,
        "model_version": checkpoint.get("version", checkpoint_path.stem),
        "architecture": checkpoint.get("architecture", "efficientnet_b0"),
        "split": split,
        "excluded_reference_duplicates": len(cross_split_duplicates),
        "excluded_within_split_duplicates": len(within_split_duplicates),
        "test_images": len(targets),
        "test_class_counts": class_counts(samples, classes),
        "accuracy": float(accuracy_score(targets, predictions)),
        "top3_accuracy": float(top3_correct / len(targets)),
        "macro_f1": float(
            f1_score(
                targets,
                predictions,
                labels=observed_labels,
                average="macro",
                zero_division=0,
            )
        ),
        "weighted_f1": float(
            f1_score(targets, predictions, labels=labels, average="weighted", zero_division=0)
        ),
        "per_class": {
            name: {
                "precision": float(report[name]["precision"]),
                "recall": float(report[name]["recall"]),
                "f1": float(report[name]["f1-score"]),
                "support": int(report[name]["support"]),
            }
            for name in classes
        },
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    prefix = "test" if split == "test" else split
    save_json(output_dir / f"{prefix}_metrics.json", metrics)
    save_json(output_dir / f"{prefix}_classification_report.json", report)
    save_json(output_dir / f"{prefix}_confusion_matrix.json", matrix.tolist())
    save_confusion_matrix(
        matrix, output_dir / f"{prefix}_confusion_matrix.png", classes, split
    )
    print(metrics, flush=True)
    return metrics


def main() -> None:
    parser = argparse.ArgumentParser(description="Đánh giá checkpoint trên test độc lập.")
    parser.add_argument("--checkpoint", required=True, type=Path)
    parser.add_argument("--data", required=True, type=Path)
    parser.add_argument("--output", type=Path, default=Path("models"))
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--split", default="test")
    parser.add_argument(
        "--reference-data",
        action="append",
        type=Path,
        default=None,
        help="Dataset root(s) whose train split is checked for cross-split conflicts.",
    )
    args = parser.parse_args()
    evaluate_checkpoint(
        args.checkpoint,
        args.data,
        args.output,
        args.batch_size,
        args.workers,
        args.split,
        args.reference_data,
    )


if __name__ == "__main__":
    main()
