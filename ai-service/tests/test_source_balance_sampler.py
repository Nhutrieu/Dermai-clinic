import sys
from collections import defaultdict
from pathlib import Path

import pytest


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "training"))

from common import ImageSample  # noqa: E402
from train_source_balance_convnext import WORKSPACE, sample_source, source_balance_weights  # noqa: E402


def test_source_balance_preserves_class_mass_and_skips_sparse_cells():
    samples = []
    for label, source, count in ((0, "train", 4), (0, "scin-v1/train", 2),
                                  (1, "train", 3), (1, "scin-v1/train", 1),
                                  (5, "train", 2)):
        for index in range(count):
            samples.append(ImageSample(WORKSPACE / "SkinDisease" / source / f"{label}_{index}.jpg", label, str(index)))
    weights, audit = source_balance_weights(samples, minimum=2)
    assert audit["eligible_classes"] == ["Acne"]
    mass = defaultdict(float)
    for sample, weight in zip(samples, weights):
        mass[sample.label, sample_source(sample)] += float(weight)
    assert mass[0, "SkinDisease_original"] == pytest.approx(3)
    assert mass[0, "SCIN_train_pool"] == pytest.approx(3)
    assert sum(value for (label, _), value in mass.items() if label == 0) == pytest.approx(6)
    assert mass[1, "SkinDisease_original"] == pytest.approx(3)
    assert mass[1, "SCIN_train_pool"] == pytest.approx(1)
