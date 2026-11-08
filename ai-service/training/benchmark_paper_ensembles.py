from __future__ import annotations

"""Evaluate fixed, equal-weight ensembles without selecting weights on test data."""

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import torch

from common import CLASSES, build_model, save_json, seed_everything
from evaluate_v2_candidate import cleaned_splits, infer_logits, metrics


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=Path("SkinDisease"))
    parser.add_argument("--extra-data", action="append", type=Path, default=[Path("SkinDisease/scin-v1")])
    parser.add_argument("--external-data", type=Path, default=Path("SkinDisease/scin-v1"))
    parser.add_argument("--baseline", required=True, type=Path)
    parser.add_argument("--candidate", required=True, type=Path)
    parser.add_argument("--resnet", required=True, type=Path)
    parser.add_argument("--convnext", type=Path, help="Optional third architecture checkpoint")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--workers", type=int, default=0)
    parser.add_argument("--val-ratio", type=float, default=0.15)
    parser.add_argument("--near-duplicate-distance", type=int, default=0)
    parser.add_argument("--seed", type=int, default=42)
    return parser.parse_args()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def model_probabilities(
    path: Path, splits: dict[str, list], device: torch.device, batch_size: int, workers: int
) -> tuple[dict, dict[str, torch.Tensor], dict[str, torch.Tensor]]:
    checkpoint = torch.load(path, map_location="cpu", weights_only=False)
    if checkpoint["classes"] != CLASSES:
        raise ValueError(f"Class order mismatch: {path}")
    temperature = float(checkpoint.get("temperature", 1.0))
    if not 0 < temperature < 100:
        raise ValueError(f"Invalid temperature: {path}")
    model = build_model(checkpoint["architecture"], len(CLASSES), pretrained=False)
    model.load_state_dict(checkpoint["model_state_dict"])
    model.to(device).eval()
    probabilities = {}
    targets = {}
    for split, samples in splits.items():
        logits, labels = infer_logits(model, samples, device, batch_size, workers)
        probabilities[split] = torch.softmax(logits / temperature, dim=1)
        targets[split] = labels
    del model
    if device.type == "cuda":
        torch.cuda.empty_cache()
    info = {
        "path": str(path),
        "sha256": sha256(path),
        "version": checkpoint["version"],
        "architecture": checkpoint["architecture"],
        "temperature": temperature,
    }
    return info, probabilities, targets


def report_metrics(probabilities: torch.Tensor, targets: torch.Tensor) -> dict:
    # metrics() accepts logits. Log probabilities reconstruct the same softmax.
    return metrics(probabilities.clamp_min(1e-12).log(), targets, 1.0)


def paired_accuracy_difference(
    baseline: torch.Tensor,
    ensemble: torch.Tensor,
    targets: torch.Tensor,
    samples: list,
    seed: int,
    repetitions: int = 3000,
) -> dict:
    baseline_correct = (baseline.argmax(dim=1) == targets).numpy()
    ensemble_correct = (ensemble.argmax(dim=1) == targets).numpy()
    difference = ensemble_correct.astype(float) - baseline_correct.astype(float)
    groups: dict[str, list[int]] = {}
    for index, sample in enumerate(samples):
        groups.setdefault(sample.group_id or sample.digest, []).append(index)
    group_indices = [np.asarray(indices, dtype=int) for indices in groups.values()]
    rng = np.random.default_rng(seed)
    deltas = np.empty(repetitions, dtype=float)
    for iteration in range(repetitions):
        sampled = rng.integers(0, len(group_indices), size=len(group_indices))
        indices = np.concatenate([group_indices[index] for index in sampled])
        deltas[iteration] = difference[indices].mean()
    return {
        "ensemble_correct_baseline_wrong": int((ensemble_correct & ~baseline_correct).sum()),
        "baseline_correct_ensemble_wrong": int((baseline_correct & ~ensemble_correct).sum()),
        "accuracy_difference": float(difference.mean()),
        "paired_bootstrap_95pct_interval": [float(value) for value in np.quantile(deltas, [0.025, 0.975])],
        "bootstrap_unit": "case_group_where_known_otherwise_image",
        "bootstrap_repetitions": repetitions,
    }


def main() -> None:
    args = parse_args()
    seed_everything(args.seed)
    _validation, fixed, external = cleaned_splits(args)
    splits = {"fixed_test": fixed, "scin_external": external}
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    checkpoints = {"baseline": args.baseline, "candidate_v2c": args.candidate, "resnet50": args.resnet}
    if args.convnext is not None:
        checkpoints["convnext_tiny"] = args.convnext
    metadata = {}
    predictions = {}
    reference_targets = None
    for name, path in checkpoints.items():
        print(f"Inferring {name} on {device}...", flush=True)
        info, probabilities, targets = model_probabilities(
            path, splits, device, args.batch_size, args.workers
        )
        if reference_targets is not None:
            if any(not torch.equal(targets[split], reference_targets[split]) for split in splits):
                raise RuntimeError("Prediction order differs across checkpoints")
        reference_targets = targets
        metadata[name] = info
        predictions[name] = probabilities

    assert reference_targets is not None
    # These combinations and weights are specified before viewing their test results.
    combinations = {
        "baseline": ["baseline"],
        "candidate_v2c": ["candidate_v2c"],
        "resnet50": ["resnet50"],
        "baseline_resnet_50_50": ["baseline", "resnet50"],
        "candidate_resnet_50_50": ["candidate_v2c", "resnet50"],
        "baseline_candidate_50_50": ["baseline", "candidate_v2c"],
        "all_three_equal": ["baseline", "candidate_v2c", "resnet50"],
    }
    if args.convnext is not None:
        combinations["convnext_tiny"] = ["convnext_tiny"]
        combinations["all_four_equal"] = ["baseline", "candidate_v2c", "resnet50", "convnext_tiny"]
    results = {}
    averaged_probabilities = {}
    for name, members in combinations.items():
        results[name] = {}
        averaged_probabilities[name] = {}
        for split in splits:
            average = torch.stack([predictions[member][split] for member in members]).mean(dim=0)
            averaged_probabilities[name][split] = average
            results[name][split] = report_metrics(average, reference_targets[split])
    paired_comparison = {
        split: paired_accuracy_difference(
            averaged_probabilities["baseline"][split],
            averaged_probabilities["all_three_equal"][split],
            reference_targets[split],
            samples,
            args.seed,
        )
        for split, samples in splits.items()
    }
    paired_four = None
    if args.convnext is not None:
        paired_four = {
            split: paired_accuracy_difference(
                averaged_probabilities["baseline"][split],
                averaged_probabilities["all_four_equal"][split],
                reference_targets[split],
                samples,
                args.seed,
            )
            for split, samples in splits.items()
        }
    report = {
        "protocol": "Pre-specified equal-weight probability averaging; no test-set weight search.",
        "dataset_interpretation": {
            "fixed_test": "Historical SkinDisease holdout; patient identifiers are unavailable.",
            "scin_external": "Historical split name. Case-disjoint SCIN holdout, not an independent-source external validation: all checkpoints also trained on other SCIN cases.",
        },
        "model_selection_warning": "Exploratory comparison: multiple ensembles are measured on the same fixed and SCIN case holdout tests. Reusing these results to tune weights would invalidate the holdouts.",
        "datasets": {name: len(samples) for name, samples in splits.items()},
        "checkpoints": metadata,
        "combinations": combinations,
        "results": results,
        "paired_baseline_vs_three_model_ensemble": paired_comparison,
        "paired_baseline_vs_four_model_ensemble": paired_four,
    }
    args.output.mkdir(parents=True, exist_ok=True)
    save_json(args.output / "paper_ensemble_benchmark.json", report)
    overview = {
        name: {
            split: {
                "accuracy": result["accuracy"],
                "macro_f1": result["macro_f1_present_classes"],
                "skin_cancer_recall": result["per_class"]["SkinCancer"]["recall"] if split == "fixed_test" else None,
                "lupus_recall": result["per_class"]["Lupus"]["recall"] if split == "fixed_test" else None,
            }
            for split, result in by_split.items()
        }
        for name, by_split in results.items()
    }
    print(json.dumps(overview, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
