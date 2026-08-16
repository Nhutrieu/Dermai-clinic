import math
import sys
from pathlib import Path

import numpy as np


TRAINING_DIR = Path(__file__).resolve().parents[1] / "training"
sys.path.insert(0, str(TRAINING_DIR))

from evaluate_evidence import calibration_metrics, error_analysis, heatmap_statistics  # noqa: E402


def test_calibration_metrics_are_zero_for_perfect_predictions():
    probabilities = np.array([[1.0, 0.0], [0.0, 1.0]])
    targets = np.array([0, 1])

    metrics = calibration_metrics(probabilities, targets, bins=5)

    assert metrics["expected_calibration_error"] == 0
    assert metrics["multiclass_brier_score"] == 0
    assert metrics["negative_log_likelihood"] == 0
    assert sum(item["count"] for item in metrics["reliability"]) == 2


def test_calibration_metrics_match_known_binary_example():
    probabilities = np.array([[0.8, 0.2], [0.8, 0.2]])
    targets = np.array([0, 1])

    metrics = calibration_metrics(probabilities, targets, bins=5)

    assert math.isclose(metrics["accuracy"], 0.5)
    assert math.isclose(metrics["expected_calibration_error"], 0.3)
    assert math.isclose(metrics["multiclass_brier_score"], 0.68)
    assert math.isclose(
        metrics["negative_log_likelihood"], (-math.log(0.8) - math.log(0.2)) / 2
    )


def test_error_analysis_preserves_per_image_evidence_and_confusion_counts():
    rows = [
        {"sample_id": "a", "true_label": "Acne", "predicted_label": "Acne", "correct": True, "confidence": 0.7},
        {"sample_id": "b", "true_label": "Acne", "predicted_label": "Eczema", "correct": False, "confidence": 0.9},
        {"sample_id": "c", "true_label": "Acne", "predicted_label": "Eczema", "correct": False, "confidence": 0.6},
    ]

    report = error_analysis(rows)

    assert report["error_count"] == 2
    assert report["error_count_by_confidence"]["at_least_0_90"] == 1
    assert report["confusion_pairs"][0] == {
        "true_label": "Acne",
        "predicted_label": "Eczema",
        "count": 2,
    }
    assert [row["sample_id"] for row in report["errors"]] == ["b", "c"]


def test_heatmap_statistics_report_peak_and_coverage():
    heatmap = np.array([[0.0, 0.5], [1.0, 0.5]], dtype=np.float32)

    report = heatmap_statistics(heatmap)

    assert report["native_shape"] == [2, 2]
    assert report["fraction_at_least_0_50"] == 0.75
    assert report["peak"] == {"x_normalized": 0.0, "y_normalized": 1.0}
