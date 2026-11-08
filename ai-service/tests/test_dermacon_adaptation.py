"""Patient isolation and fixed source sampling for the development pilot."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "training"))

from common import CLASSES  # noqa: E402
from prepare_dermacon_adaptation import remove_near, split_development  # noqa: E402
from train_dermacon_adaptation import source_sampling_weights  # noqa: E402


def test_development_split_keeps_all_patient_images_together():
    rows = [
        {"image_path": f"images/{label}_{case}_{view}.jpg", "label": label, "case_id": f"patient_{case}"}
        for label in CLASSES for case in range(16) for view in range(2)
    ]
    training, validation = split_development(rows)
    assert len(training) + len(validation) == len(rows)
    assert {row["case_id"] for row in training}.isdisjoint({row["case_id"] for row in validation})
    assert {row["label"] for row in training} == set(CLASSES)
    assert {row["label"] for row in validation} == set(CLASSES)


def test_near_neighbor_is_excluded_from_training():
    protected = [{"image_path": "images/protected.jpg"}]
    rows = [{"image_path": "images/near.jpg"}, {"image_path": "images/far.jpg"}]
    hashes = {"images/protected.jpg": 0, "images/near.jpg": 0b111, "images/far.jpg": 0b1111}
    kept, excluded = remove_near(rows, protected, hashes, radius=3)
    assert kept == [rows[1]]
    assert excluded == [rows[0]]


def test_source_sampling_preserves_fixed_mass_and_steps():
    weights = source_sampling_weights(8, 2, 0.15)
    assert len(weights) == 10
    assert float(weights[:8].sum()) == pytest.approx(0.85)
    assert float(weights[8:].sum()) == pytest.approx(0.15)
    control = source_sampling_weights(8, 2, 0)
    assert len(control) == 8
    assert float(control.sum()) == pytest.approx(1)
