from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import torch

from common import (
    CLASSES,
    ImageSampleDataset,
    build_model,
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
from evaluate_v2_candidate import baseline_metrics, fit_temperature, infer_logits, metrics


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fit temperature trên validation gốc, không dùng test để hiệu chỉnh."
    )
    parser.add_argument("--checkpoint", required=True, type=Path)
    parser.add_argument("--data", required=True, type=Path)
    parser.add_argument("--extra-data", action="append", type=Path, default=[])
    parser.add_argument("--fixed-predictions", required=True, type=Path)
    parser.add_argument("--external-predictions", required=True, type=Path)
    parser.add_argument("--output-checkpoint", required=True, type=Path)
    parser.add_argument("--output-report", required=True, type=Path)
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--workers", type=int, default=0)
    parser.add_argument("--val-ratio", type=float, default=0.15)
    parser.add_argument("--seed", type=int, default=42)
    return parser.parse_args()


def original_validation_split(args: argparse.Namespace):
    base_train = collect_samples(args.data, "train")
    extra_train = [
        sample
        for root in args.extra_data
        for sample in collect_samples(root, "train")
    ]
    raw_train = [*base_train, *extra_train]
    raw_test = collect_samples(args.data, "test")
    conflicts = label_conflict_digests([*raw_train, *raw_test])
    train_clean, _ = exclude_digests(raw_train, conflicts)
    test_clean, _ = exclude_digests(raw_test, conflicts)
    train_clean, _ = deduplicate_samples(train_clean)
    test_clean, _ = deduplicate_samples(test_clean)
    train_clean, _ = exclude_cross_split_duplicates(train_clean, test_clean)
    _, validation = grouped_stratified_split(
        train_clean, args.val_ratio, args.seed, len(CLASSES)
    )
    return validation


def main() -> None:
    args = parse_args()
    seed_everything(args.seed)
    checkpoint = torch.load(args.checkpoint, map_location="cpu", weights_only=False)
    if checkpoint["classes"] != CLASSES:
        raise RuntimeError("Ánh xạ lớp trong checkpoint không khớp cấu hình 8 nhóm bệnh.")
    validation = original_validation_split(args)
    model = build_model(
        checkpoint["architecture"], len(checkpoint["classes"]), pretrained=False
    )
    model.load_state_dict(checkpoint["model_state_dict"])
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model.to(device).eval()
    print(f"Đang infer {len(validation)} ảnh validation gốc trên {device}...", flush=True)
    logits, targets = infer_logits(
        model, validation, device, args.batch_size, args.workers
    )
    temperature = fit_temperature(logits, targets)

    validation_raw = metrics(logits, targets, 1.0)
    validation_calibrated = metrics(logits, targets, temperature)
    fixed_raw = baseline_metrics(args.fixed_predictions)
    external_raw = baseline_metrics(args.external_predictions)

    def recalibrate_evidence(path: Path) -> dict:
        payload = json.loads(path.read_text(encoding="utf-8"))
        rows = payload["predictions"]
        probabilities = torch.tensor(
            [[row["probabilities"][name] for name in CLASSES] for row in rows],
            dtype=torch.float32,
        )
        evidence_logits = probabilities.clamp_min(1e-12).log()
        evidence_targets = torch.tensor(
            [CLASSES.index(row["true_label"]) for row in rows], dtype=torch.long
        )
        return metrics(evidence_logits, evidence_targets, temperature)

    fixed_calibrated = recalibrate_evidence(args.fixed_predictions)
    external_calibrated = recalibrate_evidence(args.external_predictions)
    report = {
        "model_version": checkpoint["version"],
        "temperature": temperature,
        "temperature_fitted_on_validation_only": True,
        "validation_count": len(validation),
        "validation": {"raw": validation_raw, "calibrated": validation_calibrated},
        "fixed_test": {"raw": fixed_raw, "calibrated": fixed_calibrated},
        "external_test": {"raw": external_raw, "calibrated": external_calibrated},
        "ranking_metrics_unchanged": True,
    }
    save_json(args.output_report, report)
    calibrated_checkpoint = dict(checkpoint)
    calibrated_checkpoint["temperature"] = temperature
    calibrated_checkpoint["calibration"] = {
        "method": "temperature_scaling",
        "fitted_on": "original_validation_split_only",
        "validation_count": len(validation),
        "seed": args.seed,
        "validation_ratio": args.val_ratio,
    }
    args.output_checkpoint.parent.mkdir(parents=True, exist_ok=True)
    torch.save(calibrated_checkpoint, args.output_checkpoint)
    print(
        json.dumps(
            {
                "temperature": temperature,
                "validation_ece": {
                    "raw": validation_raw["calibration"]["expected_calibration_error"],
                    "calibrated": validation_calibrated["calibration"]["expected_calibration_error"],
                },
                "fixed_ece": {
                    "raw": fixed_raw["calibration"]["expected_calibration_error"],
                    "calibrated": fixed_calibrated["calibration"]["expected_calibration_error"],
                },
                "external_ece": {
                    "raw": external_raw["calibration"]["expected_calibration_error"],
                    "calibrated": external_calibrated["calibration"]["expected_calibration_error"],
                },
            },
            ensure_ascii=False,
            indent=2,
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
