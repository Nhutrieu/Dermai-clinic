from __future__ import annotations

import argparse
import hashlib
import io
import math
import platform
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

import numpy as np
import torch
import torchvision
from PIL import Image
from torch import nn
from torch.utils.data import DataLoader


AI_SERVICE_ROOT = Path(__file__).resolve().parents[1]
if str(AI_SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(AI_SERVICE_ROOT))

from app.model import GradCam, ModelBundle, predict, preprocess_image  # noqa: E402
from common import (  # noqa: E402
    CLASSES,
    ImageSample,
    ImageSampleDataset,
    build_model,
    class_counts,
    collect_samples,
    deduplicate_samples,
    evaluation_transform,
    exclude_cross_split_duplicates,
    exclude_digests,
    label_conflict_digests,
    save_json,
    seed_everything,
    sha256_file,
)


DEFAULT_UNCERTAIN_THRESHOLD = 0.55


def display_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(Path.cwd().resolve()).as_posix()
    except ValueError:
        return path.name


def clean_evaluation_samples(
    data_root: Path,
    split: str,
    reference_samples: list[ImageSample],
    preserve_fixed_test: bool,
) -> tuple[list[ImageSample], dict]:
    raw_samples = collect_samples(data_root, split, CLASSES)
    conflicts = label_conflict_digests([*reference_samples, *raw_samples])
    without_conflicts, conflict_samples = exclude_digests(raw_samples, conflicts)

    # The original fixed test is the historical hold-out. Its matching files were
    # removed from training, so removing them here would silently change the test.
    if preserve_fixed_test:
        without_reference_duplicates = without_conflicts
        reference_duplicates: list[ImageSample] = []
    else:
        without_reference_duplicates, reference_duplicates = exclude_cross_split_duplicates(
            without_conflicts, reference_samples
        )
    clean_samples, within_split_duplicates = deduplicate_samples(
        without_reference_duplicates
    )
    metadata = {
        "data_root": display_path(data_root),
        "split": split,
        "raw_images": len(raw_samples),
        "evaluated_images": len(clean_samples),
        "class_counts": class_counts(clean_samples, CLASSES),
        "excluded_label_conflict_files": len(conflict_samples),
        "excluded_reference_duplicates": len(reference_duplicates),
        "excluded_within_split_duplicates": len(within_split_duplicates),
        "fixed_test_preserved": preserve_fixed_test,
    }
    return clean_samples, metadata


def infer_probabilities(
    model: nn.Module,
    samples: list[ImageSample],
    device: torch.device,
    batch_size: int,
    workers: int,
) -> tuple[np.ndarray, np.ndarray]:
    loader = DataLoader(
        ImageSampleDataset(samples, evaluation_transform()),
        batch_size=batch_size,
        shuffle=False,
        num_workers=workers,
        pin_memory=device.type == "cuda",
        persistent_workers=workers > 0,
    )
    probabilities: list[np.ndarray] = []
    targets: list[np.ndarray] = []
    model.eval()
    with torch.inference_mode():
        for inputs, labels in loader:
            logits = model(inputs.to(device, non_blocking=True))
            probabilities.append(torch.softmax(logits, dim=1).cpu().numpy())
            targets.append(labels.numpy())
    return np.concatenate(probabilities), np.concatenate(targets)


def calibration_metrics(
    probabilities: np.ndarray,
    targets: np.ndarray,
    bins: int = 15,
    uncertain_threshold: float = DEFAULT_UNCERTAIN_THRESHOLD,
) -> dict:
    if probabilities.ndim != 2 or targets.ndim != 1:
        raise ValueError("probabilities must be 2-D and targets must be 1-D")
    if len(probabilities) != len(targets) or not len(targets):
        raise ValueError("probabilities and targets must have the same non-zero length")
    if bins < 2:
        raise ValueError("bins must be at least 2")

    predictions = probabilities.argmax(axis=1)
    confidence = probabilities.max(axis=1)
    correct = predictions == targets
    bin_indices = np.minimum((confidence * bins).astype(int), bins - 1)
    reliability: list[dict] = []
    ece = 0.0
    gaps: list[float] = []

    # ECE uses equal-width maximum-softmax bins. Empty bins are retained so the
    # JSON can be plotted directly without guessing the binning convention.
    for index in range(bins):
        mask = bin_indices == index
        count = int(mask.sum())
        lower = index / bins
        upper = (index + 1) / bins
        if count:
            bin_accuracy = float(correct[mask].mean())
            mean_confidence = float(confidence[mask].mean())
            gap = abs(bin_accuracy - mean_confidence)
            ece += (count / len(targets)) * gap
            gaps.append(gap)
        else:
            bin_accuracy = None
            mean_confidence = None
            gap = None
        reliability.append(
            {
                "index": index,
                "lower": lower,
                "upper": upper,
                "right_edge_inclusive": index == bins - 1,
                "count": count,
                "fraction": count / len(targets),
                "accuracy": bin_accuracy,
                "mean_confidence": mean_confidence,
                "absolute_gap": gap,
            }
        )

    clipped = np.clip(probabilities, 1e-15, 1.0)
    true_probabilities = clipped[np.arange(len(targets)), targets]
    one_hot = np.eye(probabilities.shape[1], dtype=np.float64)[targets]
    accepted = confidence >= uncertain_threshold
    rejected = ~accepted
    accepted_count = int(accepted.sum())
    rejected_count = int(rejected.sum())

    return {
        "sample_count": len(targets),
        "class_count": probabilities.shape[1],
        "binning": {
            "method": "equal_width_top1_confidence",
            "bins": bins,
            "interval": "[lower, upper), except final bin includes 1.0",
        },
        "accuracy": float(correct.mean()),
        "mean_confidence": float(confidence.mean()),
        "expected_calibration_error": float(ece),
        "maximum_calibration_error": float(max(gaps, default=0.0)),
        "negative_log_likelihood": float(-np.log(true_probabilities).mean()),
        "multiclass_brier_score": float(np.square(probabilities - one_hot).sum(axis=1).mean()),
        "per_class_one_vs_rest_brier": {
            CLASSES[index]: float(
                np.square(probabilities[:, index] - (targets == index).astype(float)).mean()
            )
            for index in range(probabilities.shape[1])
        },
        "uncertainty_policy": {
            "accept_when_top1_confidence_at_least": uncertain_threshold,
            "accepted": accepted_count,
            "rejected": rejected_count,
            "coverage": accepted_count / len(targets),
            "accepted_accuracy": float(correct[accepted].mean()) if accepted_count else None,
            "rejected_accuracy": float(correct[rejected].mean()) if rejected_count else None,
            "accepted_errors": int((~correct & accepted).sum()),
            "rejected_errors": int((~correct & rejected).sum()),
        },
        "reliability": reliability,
    }


def prediction_rows(
    samples: list[ImageSample], probabilities: np.ndarray, targets: np.ndarray
) -> list[dict]:
    rows: list[dict] = []
    for sample, probability, target in zip(samples, probabilities, targets):
        ranked = np.argsort(-probability)
        prediction = int(ranked[0])
        entropy = float(-np.sum(probability * np.log(np.clip(probability, 1e-15, 1.0))))
        rows.append(
            {
                # The digest is stable enough to reproduce a row without publishing
                # source filenames or SCIN case identifiers.
                "sample_id": f"sha256:{sample.digest}",
                "true_label": CLASSES[int(target)],
                "predicted_label": CLASSES[prediction],
                "correct": prediction == int(target),
                "confidence": float(probability[prediction]),
                "margin_top1_top2": float(probability[ranked[0]] - probability[ranked[1]]),
                "entropy_nats": entropy,
                "normalized_entropy": entropy / math.log(len(CLASSES)),
                "true_label_rank": int(np.flatnonzero(ranked == int(target))[0]) + 1,
                "uncertain_at_0_55": float(probability[prediction])
                < DEFAULT_UNCERTAIN_THRESHOLD,
                "probabilities": {
                    CLASSES[index]: float(probability[index]) for index in range(len(CLASSES))
                },
                "top3": [
                    {"label": CLASSES[int(index)], "probability": float(probability[index])}
                    for index in ranked[:3]
                ],
            }
        )
    return rows


def error_analysis(rows: list[dict]) -> dict:
    errors = [row for row in rows if not row["correct"]]
    confusion_pairs = Counter(
        (row["true_label"], row["predicted_label"]) for row in errors
    )
    by_true_label = {
        label: {
            "total": sum(row["true_label"] == label for row in rows),
            "errors": sum(row["true_label"] == label for row in errors),
        }
        for label in CLASSES
    }
    for values in by_true_label.values():
        values["error_rate"] = (
            values["errors"] / values["total"] if values["total"] else None
        )

    return {
        "sample_count": len(rows),
        "error_count": len(errors),
        "error_rate": len(errors) / len(rows),
        "error_count_by_confidence": {
            "at_least_0_55": sum(row["confidence"] >= 0.55 for row in errors),
            "at_least_0_80": sum(row["confidence"] >= 0.80 for row in errors),
            "at_least_0_90": sum(row["confidence"] >= 0.90 for row in errors),
        },
        "by_true_label": by_true_label,
        "confusion_pairs": [
            {"true_label": pair[0], "predicted_label": pair[1], "count": count}
            for pair, count in sorted(
                confusion_pairs.items(), key=lambda item: (-item[1], item[0])
            )
        ],
        "errors": sorted(errors, key=lambda row: (-row["confidence"], row["sample_id"])),
        "clinical_review_status": "pending; no dermatologist review was performed by this tool",
    }


def percentile_summary(samples_ms: list[float]) -> dict:
    values = np.asarray(samples_ms, dtype=np.float64)
    return {
        "iterations": len(samples_ms),
        "mean_ms": float(values.mean()),
        "std_ms": float(values.std()),
        "min_ms": float(values.min()),
        "p50_ms": float(np.percentile(values, 50)),
        "p90_ms": float(np.percentile(values, 90)),
        "p95_ms": float(np.percentile(values, 95)),
        "p99_ms": float(np.percentile(values, 99)),
        "max_ms": float(values.max()),
        "throughput_per_second_from_mean": float(1000 / values.mean()),
        "samples_ms": samples_ms,
    }


def synchronize(device: torch.device) -> None:
    if device.type == "cuda":
        torch.cuda.synchronize(device)


def benchmark_operation(
    operation: Callable[[], object],
    device: torch.device,
    warmup: int,
    iterations: int,
) -> dict:
    for _ in range(warmup):
        operation()
    synchronize(device)
    samples_ms: list[float] = []
    for _ in range(iterations):
        synchronize(device)
        started = time.perf_counter_ns()
        operation()
        synchronize(device)
        samples_ms.append((time.perf_counter_ns() - started) / 1_000_000)
    return percentile_summary(samples_ms)


def target_layer(model: nn.Module, architecture: str) -> nn.Module:
    if architecture == "resnet50":
        return model.layer4[-1]
    if architecture == "convnext_tiny":
        return model.features[-1]
    return model.features[-1]


def load_model(checkpoint: dict, device: torch.device) -> nn.Module:
    model = build_model(
        checkpoint.get("architecture", "efficientnet_b0"),
        len(checkpoint.get("classes", CLASSES)),
        pretrained=False,
    )
    model.load_state_dict(checkpoint["model_state_dict"])
    return model.to(device).eval()


def device_metadata(device: torch.device) -> dict:
    if device.type == "cuda":
        properties = torch.cuda.get_device_properties(device)
        return {
            "type": "cuda",
            "name": properties.name,
            "total_memory_bytes": properties.total_memory,
            "compute_capability": f"{properties.major}.{properties.minor}",
            "cuda_runtime": torch.version.cuda,
            "cudnn": torch.backends.cudnn.version(),
        }
    return {
        "type": "cpu",
        "name": platform.processor() or platform.uname().processor or "not reported by OS",
        "logical_threads_used_by_torch": torch.get_num_threads(),
    }


def latency_benchmarks(
    checkpoint: dict,
    source_image: Image.Image,
    devices: list[str],
    warmup: int,
    forward_iterations: int,
    full_iterations: int,
) -> dict:
    results: dict[str, dict] = {}
    architecture = checkpoint.get("architecture", "efficientnet_b0")
    classes = checkpoint.get("classes", CLASSES)
    parameter_bytes = sum(
        tensor.numel() * tensor.element_size()
        for tensor in checkpoint["model_state_dict"].values()
    )

    for requested in devices:
        if requested == "cuda" and not torch.cuda.is_available():
            results[requested] = {"status": "unavailable", "reason": "CUDA is not available"}
            continue
        device = torch.device(requested)
        model = load_model(checkpoint, device)
        tensor, _ = preprocess_image(source_image)
        tensor = tensor.unsqueeze(0).to(device)
        bundle = ModelBundle(
            model=model,
            target_layer=target_layer(model, architecture),
            version=checkpoint.get("version", "unknown"),
            classes=classes,
            device=device,
        )
        if device.type == "cuda":
            torch.cuda.reset_peak_memory_stats(device)

        def forward_only() -> torch.Tensor:
            with torch.inference_mode():
                return model(tensor)

        results[requested] = {
            "status": "measured",
            "device": device_metadata(device),
            "batch_size": 1,
            "warmup_iterations": warmup,
            "model_forward_preprocessed_tensor": benchmark_operation(
                forward_only, device, warmup, forward_iterations
            ),
            # This mirrors app.predict: PIL transforms, softmax/Top-3, a second
            # forward+backward for Grad-CAM, overlay creation and PNG/base64 encoding.
            "application_predict_with_gradcam": benchmark_operation(
                lambda: predict(bundle, source_image), device, warmup, full_iterations
            ),
            "peak_cuda_memory_allocated_bytes": (
                torch.cuda.max_memory_allocated(device) if device.type == "cuda" else None
            ),
        }
        del model, bundle, tensor
        if device.type == "cuda":
            torch.cuda.empty_cache()

    return {
        "status": "measured_local_machine",
        "scope": {
            "model_forward_preprocessed_tensor": "one forward pass; excludes image preprocessing and transport",
            "application_predict_with_gradcam": "in-process app.predict from an already decoded PIL image; excludes HTTP, upload, image decode and RAG",
        },
        "model_parameter_bytes": parameter_bytes,
        "environment": {
            "platform": platform.platform(),
            "python": platform.python_version(),
            "torch": torch.__version__,
            "torchvision": torchvision.__version__,
        },
        "results": results,
    }


def synthetic_ood_images(seed: int) -> list[tuple[str, Image.Image]]:
    size = 256
    rng = np.random.default_rng(seed)
    black = np.zeros((size, size, 3), dtype=np.uint8)
    white = np.full((size, size, 3), 255, dtype=np.uint8)
    gray = np.full((size, size, 3), 127, dtype=np.uint8)
    gradient = np.tile(np.arange(size, dtype=np.uint8), (size, 1))
    gradient_rgb = np.stack([gradient, np.flipud(gradient), gradient], axis=2)
    checker = ((np.indices((size, size)).sum(axis=0) // 16) % 2 * 255).astype(np.uint8)
    checker_rgb = np.stack([checker, checker, checker], axis=2)
    noise = rng.integers(0, 256, size=(size, size, 3), dtype=np.uint8)
    return [
        ("uniform_black", Image.fromarray(black)),
        ("uniform_white", Image.fromarray(white)),
        ("uniform_gray", Image.fromarray(gray)),
        ("synthetic_gradient", Image.fromarray(gradient_rgb)),
        ("checkerboard", Image.fromarray(checker_rgb)),
        ("seeded_rgb_noise", Image.fromarray(noise)),
    ]


def image_digest(image: Image.Image) -> str:
    output = io.BytesIO()
    image.save(output, format="PNG")
    return hashlib.sha256(output.getvalue()).hexdigest()


def ood_probe_report(
    model: nn.Module,
    device: torch.device,
    seed: int,
    threshold: float,
    fixed_test_probabilities: np.ndarray,
) -> dict:
    rows: list[dict] = []
    for name, image in synthetic_ood_images(seed):
        tensor, _ = preprocess_image(image)
        with torch.inference_mode():
            probability = torch.softmax(model(tensor.unsqueeze(0).to(device)), dim=1)[0]
        probability_np = probability.cpu().numpy()
        ranked = np.argsort(-probability_np)
        rows.append(
            {
                "probe": name,
                "png_sha256": image_digest(image),
                "predicted_label": CLASSES[int(ranked[0])],
                "maximum_softmax_probability": float(probability_np[ranked[0]]),
                "rejected_at_0_55": float(probability_np[ranked[0]]) < threshold,
                "top3": [
                    {"label": CLASSES[int(index)], "probability": float(probability_np[index])}
                    for index in ranked[:3]
                ],
            }
        )

    confidences = [row["maximum_softmax_probability"] for row in rows]
    rejected = sum(row["rejected_at_0_55"] for row in rows)
    return {
        "status": "limited_synthetic_sanity_probe",
        "probe_count": len(rows),
        "seed": seed,
        "uncertain_threshold": threshold,
        "synthetic_probe_rejection_count": rejected,
        "synthetic_probe_rejection_rate": rejected / len(rows),
        "synthetic_probe_msp": {
            "mean": float(np.mean(confidences)),
            "min": float(np.min(confidences)),
            "max": float(np.max(confidences)),
        },
        "fixed_test_msp_context": {
            "mean": float(fixed_test_probabilities.max(axis=1).mean()),
            "min": float(fixed_test_probabilities.max(axis=1).min()),
            "max": float(fixed_test_probabilities.max(axis=1).max()),
        },
        "probes": rows,
        # Six generated patterns are useful regression probes, not a clinically
        # representative OOD benchmark, so threshold-free OOD metrics are withheld.
        "true_ood_benchmark": {
            "status": "unavailable",
            "reason": "No labeled, clinically representative out-of-scope image dataset is present locally.",
            "auroc": None,
            "aupr": None,
            "fpr_at_95_tpr": None,
        },
        "interpretation_limit": "Do not generalize the synthetic rejection rate to real non-dermatology or unseen-disease images.",
    }


def heatmap_statistics(heatmap: np.ndarray) -> dict:
    peak_y, peak_x = np.unravel_index(int(np.argmax(heatmap)), heatmap.shape)
    mass = float(heatmap.sum())
    height, width = heatmap.shape
    if mass > 0:
        ys, xs = np.indices(heatmap.shape)
        centroid = {
            "x_normalized": float((xs * heatmap).sum() / mass / max(width - 1, 1)),
            "y_normalized": float((ys * heatmap).sum() / mass / max(height - 1, 1)),
        }
    else:
        centroid = None
    return {
        "native_shape": [height, width],
        "minimum": float(heatmap.min()),
        "maximum": float(heatmap.max()),
        "mean": float(heatmap.mean()),
        "standard_deviation": float(heatmap.std()),
        "fraction_at_least_0_50": float((heatmap >= 0.5).mean()),
        "peak": {
            "x_normalized": peak_x / max(width - 1, 1),
            "y_normalized": peak_y / max(height - 1, 1),
        },
        "activation_weighted_centroid": centroid,
    }


def gradcam_metadata(
    model: nn.Module,
    checkpoint: dict,
    samples: list[ImageSample],
    rows: list[dict],
    device: torch.device,
) -> dict:
    selected: list[tuple[int, str]] = []
    for label in CLASSES:
        correct = [
            index
            for index, row in enumerate(rows)
            if row["true_label"] == label and row["correct"]
        ]
        errors = [
            index
            for index, row in enumerate(rows)
            if row["true_label"] == label and not row["correct"]
        ]
        if correct:
            selected.append(
                (max(correct, key=lambda index: rows[index]["confidence"]), "highest_confidence_correct_for_true_class")
            )
        if errors:
            selected.append(
                (max(errors, key=lambda index: rows[index]["confidence"]), "highest_confidence_error_for_true_class")
            )

    layer = target_layer(model, checkpoint.get("architecture", "efficientnet_b0"))
    evidence: list[dict] = []
    for index, reason in selected:
        sample = samples[index]
        row = rows[index]
        with Image.open(sample.path) as source:
            original_size = list(source.size)
            tensor, _ = preprocess_image(source)
        predicted_index = CLASSES.index(row["predicted_label"])
        with GradCam(model, layer) as gradcam:
            heatmap = gradcam.create(tensor.unsqueeze(0).to(device), predicted_index)
        evidence.append(
            {
                "sample_id": row["sample_id"],
                "selection_reason": reason,
                "true_label": row["true_label"],
                "predicted_label": row["predicted_label"],
                "correct": row["correct"],
                "confidence": row["confidence"],
                "gradcam_target": row["predicted_label"],
                "original_size_pixels": original_size,
                "heatmap": heatmap_statistics(heatmap),
                "clinical_review": None,
            }
        )
    return {
        "status": "generated_metadata_pending_clinical_review",
        "selection_policy": "highest-confidence correct and error for each true class when available",
        "sample_count": len(evidence),
        "overlay_images_saved": False,
        "overlay_images_saved_reason": "Medical source/derived images remain local and are not added to tracked evidence artifacts.",
        "samples": evidence,
        "interpretation_limit": "Grad-CAM localization is descriptive and does not establish causality or clinical validity.",
    }


def write_summary(
    output_path: Path,
    manifest: dict,
    fixed_calibration: dict,
    external_calibration: dict,
    fixed_errors: dict,
    external_errors: dict,
    latency: dict,
    ood: dict,
    gradcam: dict,
) -> None:
    def percent(value: float) -> str:
        return f"{value * 100:.2f}%"

    def confusion_summary(report: dict) -> str:
        return "; ".join(
            f"{item['true_label']}→{item['predicted_label']} ({item['count']})"
            for item in report["confusion_pairs"][:3]
        )

    def high_confidence_examples(report: dict) -> str:
        examples = [row for row in report["errors"] if row["confidence"] >= 0.90][:3]
        return "; ".join(
            f"`{row['sample_id'][:23]}…` {row['true_label']}→{row['predicted_label']} ({percent(row['confidence'])})"
            for row in examples
        ) or "none"

    latency_rows: list[str] = []
    for name, result in latency["results"].items():
        if result["status"] != "measured":
            latency_rows.append(f"| {name} | unavailable | unavailable |")
            continue
        forward = result["model_forward_preprocessed_tensor"]["p50_ms"]
        full = result["application_predict_with_gradcam"]["p50_ms"]
        latency_rows.append(f"| {name} | {forward:.2f} ms | {full:.2f} ms |")

    content = f"""# AI evaluation evidence

Generated at `{manifest['generated_at_utc']}` from model `{manifest['checkpoint']['model_version']}`.

## Integrity

- Checkpoint: `{manifest['checkpoint']['path']}`
- SHA-256: `{manifest['checkpoint']['sha256']}` (verified against expected value: `{manifest['checkpoint']['expected_sha256_match']}`)
- Size: {manifest['checkpoint']['size_bytes']} bytes

## Calibration and error evidence

| Evaluation set | Images | Accuracy | ECE (15 bins) | Brier | NLL | Errors |
|---|---:|---:|---:|---:|---:|---:|
| Fixed test | {fixed_calibration['sample_count']} | {percent(fixed_calibration['accuracy'])} | {fixed_calibration['expected_calibration_error']:.4f} | {fixed_calibration['multiclass_brier_score']:.4f} | {fixed_calibration['negative_log_likelihood']:.4f} | {fixed_errors['error_count']} |
| SCIN external | {external_calibration['sample_count']} | {percent(external_calibration['accuracy'])} | {external_calibration['expected_calibration_error']:.4f} | {external_calibration['multiclass_brier_score']:.4f} | {external_calibration['negative_log_likelihood']:.4f} | {external_errors['error_count']} |

ECE is equal-width Top-1 ECE. Brier is the multiclass sum-of-squares mean. These are raw softmax scores; no calibration method was fitted on test data. Per-image files use image SHA-256 identifiers, not source filenames.

- Fixed-test dominant confusions: {confusion_summary(fixed_errors)}. Errors at confidence ≥ 0.90: {fixed_errors['error_count_by_confidence']['at_least_0_90']}; examples by hash prefix: {high_confidence_examples(fixed_errors)}.
- SCIN-external dominant confusions: {confusion_summary(external_errors)}. Errors at confidence ≥ 0.90: {external_errors['error_count_by_confidence']['at_least_0_90']}; examples by hash prefix: {high_confidence_examples(external_errors)}.
- The 0.55 policy accepted {fixed_errors['error_count_by_confidence']['at_least_0_55']}/{fixed_errors['error_count']} fixed-test errors and {external_errors['error_count_by_confidence']['at_least_0_55']}/{external_errors['error_count']} external errors; it is not a reliable correctness or OOD gate.

## Local latency

| Device | Model-forward p50 | `app.predict` + Grad-CAM p50 |
|---|---:|---:|
{chr(10).join(latency_rows)}

The full measurement starts from an already decoded PIL image and excludes HTTP upload, decoding, RAG and frontend latency. Raw samples and p95/p99 are in `latency.json`.

## OOD and Grad-CAM limits

- Synthetic non-clinical probes rejected at confidence < 0.55: {ood['synthetic_probe_rejection_count']}/{ood['probe_count']} ({percent(ood['synthetic_probe_rejection_rate'])}). Rejecting none is a failed sanity check for the current threshold and demonstrates overconfident behavior on these probes. It is not a clinical OOD benchmark.
- True OOD AUROC/AUPR/FPR95: unavailable because no labeled, clinically representative OOD set exists locally.
- Grad-CAM metadata generated for {gradcam['sample_count']} deterministic correct/error examples. Overlay files are not tracked; clinical review remains pending.
- Subgroup evidence by skin tone, age, sex and Vietnamese population: unavailable from the normalized evaluation inputs.

## Artifacts

See `manifest.json` for provenance and the JSON files beside this summary for reliability bins, per-image probabilities/errors, latency samples, synthetic probes and Grad-CAM statistics.
"""
    output_path.write_text(content, encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate reproducible integrity, calibration, latency, OOD and error evidence."
    )
    parser.add_argument("--checkpoint", required=True, type=Path)
    parser.add_argument("--data", required=True, type=Path)
    parser.add_argument("--external-data", required=True, type=Path)
    parser.add_argument("--external-split", default="external_test")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--expected-sha256")
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--workers", type=int, default=0)
    parser.add_argument("--bins", type=int, default=15)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--uncertain-threshold", type=float, default=0.55)
    parser.add_argument("--latency-devices", nargs="+", choices=["cpu", "cuda"], default=None)
    parser.add_argument("--latency-warmup", type=int, default=5)
    parser.add_argument("--latency-iterations", type=int, default=50)
    parser.add_argument("--full-latency-iterations", type=int, default=10)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.batch_size < 1 or args.workers < 0:
        raise ValueError("batch-size must be positive and workers cannot be negative")
    if not 0 < args.uncertain_threshold < 1:
        raise ValueError("uncertain-threshold must be in (0, 1)")
    if min(args.latency_warmup, args.latency_iterations, args.full_latency_iterations) < 1:
        raise ValueError("latency iteration counts must be positive")

    seed_everything(args.seed)
    args.output.mkdir(parents=True, exist_ok=True)
    checkpoint_sha256 = sha256_file(args.checkpoint)
    expected_match = (
        None
        if args.expected_sha256 is None
        else checkpoint_sha256 == args.expected_sha256.lower()
    )
    if expected_match is False:
        raise ValueError(
            f"Checkpoint SHA-256 mismatch: expected {args.expected_sha256}, got {checkpoint_sha256}"
        )

    checkpoint = torch.load(args.checkpoint, map_location="cpu", weights_only=False)
    classes = checkpoint.get("classes", CLASSES)
    if classes != CLASSES:
        raise ValueError(f"Checkpoint class map does not match pipeline: {classes}")

    reference_samples = [
        *collect_samples(args.data, "train", CLASSES),
        *collect_samples(args.external_data, "train", CLASSES),
    ]
    fixed_samples, fixed_dataset = clean_evaluation_samples(
        args.data, "test", reference_samples, preserve_fixed_test=True
    )
    external_samples, external_dataset = clean_evaluation_samples(
        args.external_data,
        args.external_split,
        reference_samples,
        preserve_fixed_test=False,
    )

    evaluation_device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = load_model(checkpoint, evaluation_device)
    fixed_probabilities, fixed_targets = infer_probabilities(
        model, fixed_samples, evaluation_device, args.batch_size, args.workers
    )
    external_probabilities, external_targets = infer_probabilities(
        model, external_samples, evaluation_device, args.batch_size, args.workers
    )
    fixed_rows = prediction_rows(fixed_samples, fixed_probabilities, fixed_targets)
    external_rows = prediction_rows(
        external_samples, external_probabilities, external_targets
    )
    fixed_calibration = calibration_metrics(
        fixed_probabilities, fixed_targets, args.bins, args.uncertain_threshold
    )
    external_calibration = calibration_metrics(
        external_probabilities, external_targets, args.bins, args.uncertain_threshold
    )
    fixed_errors = error_analysis(fixed_rows)
    external_errors = error_analysis(external_rows)
    gradcam = gradcam_metadata(
        model, checkpoint, fixed_samples, fixed_rows, evaluation_device
    )
    ood = ood_probe_report(
        model,
        evaluation_device,
        args.seed,
        args.uncertain_threshold,
        fixed_probabilities,
    )

    with Image.open(fixed_samples[0].path) as source:
        source_image = source.convert("RGB")
    latency_devices = args.latency_devices or (
        ["cpu", "cuda"] if torch.cuda.is_available() else ["cpu"]
    )
    latency = latency_benchmarks(
        checkpoint,
        source_image,
        latency_devices,
        args.latency_warmup,
        args.latency_iterations,
        args.full_latency_iterations,
    )

    save_json(
        args.output / "fixed_test_predictions.json",
        {"dataset": fixed_dataset, "predictions": fixed_rows},
    )
    save_json(
        args.output / "scin_external_test_predictions.json",
        {"dataset": external_dataset, "predictions": external_rows},
    )
    save_json(args.output / "fixed_test_calibration.json", fixed_calibration)
    save_json(args.output / "scin_external_test_calibration.json", external_calibration)
    save_json(args.output / "fixed_test_errors.json", fixed_errors)
    save_json(args.output / "scin_external_test_errors.json", external_errors)
    save_json(args.output / "latency.json", latency)
    save_json(args.output / "ood_synthetic_probes.json", ood)
    save_json(args.output / "gradcam_samples.json", gradcam)

    manifest = {
        "schema_version": 1,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "checkpoint": {
            "path": display_path(args.checkpoint),
            "sha256": checkpoint_sha256,
            "expected_sha256": args.expected_sha256,
            "expected_sha256_match": expected_match,
            "size_bytes": args.checkpoint.stat().st_size,
            "model_version": checkpoint.get("version", args.checkpoint.stem),
            "architecture": checkpoint.get("architecture", "efficientnet_b0"),
            "classes": classes,
        },
        "evaluation": {
            "device": device_metadata(evaluation_device),
            "seed": args.seed,
            "batch_size": args.batch_size,
            "workers": args.workers,
            "uncertain_threshold": args.uncertain_threshold,
            "calibration_bins": args.bins,
            "fixed_test": fixed_dataset,
            "scin_external_test": external_dataset,
        },
        "artifacts": [
            "fixed_test_predictions.json",
            "scin_external_test_predictions.json",
            "fixed_test_calibration.json",
            "scin_external_test_calibration.json",
            "fixed_test_errors.json",
            "scin_external_test_errors.json",
            "latency.json",
            "ood_synthetic_probes.json",
            "gradcam_samples.json",
            "summary.md",
        ],
        "unavailable_evidence": [
            "Clinically representative labeled OOD benchmark and AUROC/AUPR/FPR95",
            "Dermatologist review of individual errors and Grad-CAM localization",
            "Subgroup evaluation by skin tone, age, sex and Vietnamese population",
            "End-to-end production latency including HTTP, upload, decode, RAG and frontend",
        ],
    }
    save_json(args.output / "manifest.json", manifest)
    write_summary(
        args.output / "summary.md",
        manifest,
        fixed_calibration,
        external_calibration,
        fixed_errors,
        external_errors,
        latency,
        ood,
        gradcam,
    )
    print(
        {
            "checkpoint_sha256": checkpoint_sha256,
            "fixed_test_images": len(fixed_samples),
            "external_test_images": len(external_samples),
            "output": display_path(args.output),
        },
        flush=True,
    )


if __name__ == "__main__":
    main()
