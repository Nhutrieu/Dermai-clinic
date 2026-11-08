import sys
from pathlib import Path

import numpy as np
import torch


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "training"))

from evaluate_pad_ufes_cancer_flag import (  # noqa: E402
    internal_duplicate_audit, model_metrics, paired_group_flag_difference,
    paired_patient_bootstrap, subgroup_sensitivity,
)


def test_cancer_flag_reports_image_and_patient_sensitivity_separately():
    records = [
        {"patient_id": "p1", "diagnostic": "BCC"},
        {"patient_id": "p1", "diagnostic": "BCC"},
        {"patient_id": "p2", "diagnostic": "MEL"},
        {"patient_id": "p3", "diagnostic": "NEV"},
    ]
    probabilities = torch.zeros((4, 8))
    probabilities[:, 0] = 1
    probabilities[[0, 3], 5] = 2
    metrics = model_metrics(probabilities, records)

    assert metrics["malignant_image_sensitivity"]["flagged"] == 1
    assert metrics["malignant_image_sensitivity"]["images"] == 3
    assert metrics["malignant_patient_sensitivity"]["flagged_patients"] == 1
    assert metrics["malignant_patient_sensitivity"]["malignant_patients"] == 2
    assert metrics["by_diagnosis"]["NEV"]["rate"] == 1


def test_patient_bootstrap_keeps_paired_identical_flags_at_zero():
    records = [
        {"patient_id": "p1", "diagnostic": "BCC"},
        {"patient_id": "p1", "diagnostic": "BCC"},
        {"patient_id": "p2", "diagnostic": "MEL"},
        {"patient_id": "p3", "diagnostic": "SEK"},
    ]
    flags = np.array([True, False, False, True])
    result = paired_patient_bootstrap(flags, flags.copy(), records, seed=42, repetitions=100)

    assert result["malignant_image_sensitivity_difference"] == 0
    assert result["paired_patient_bootstrap_95pct"] == [0, 0]

    benign = paired_group_flag_difference(flags, np.array([True, False, False, False]), records, {"SEK"}, seed=42, repetitions=100)
    assert benign["image_flag_rate_difference"] == -1
    assert benign["paired_patient_bootstrap_95pct"] == [-1, -1]


def test_conflicting_identical_images_flag_the_whole_patient_for_sensitivity_check():
    records = [
        {"img_id": "a.png", "patient_id": "p1", "diagnostic": "BCC", "digest": "same"},
        {"img_id": "b.png", "patient_id": "p1", "diagnostic": "NEV", "digest": "same"},
        {"img_id": "c.png", "patient_id": "p1", "diagnostic": "SCC", "digest": "other"},
        {"img_id": "d.png", "patient_id": "p2", "diagnostic": "MEL", "digest": "unique"},
    ]
    audit = internal_duplicate_audit(records)
    sensitivity = subgroup_sensitivity(records, {"model": np.array([True, True, True, False])}, {"p1"})

    assert audit["diagnosis_conflict_groups"] == 1
    assert audit["diagnosis_conflict_patients"] == ["p1"]
    assert sensitivity["remaining_images"] == 1
    assert sensitivity["results"]["model"]["malignant_image_sensitivity"]["flagged"] == 0
