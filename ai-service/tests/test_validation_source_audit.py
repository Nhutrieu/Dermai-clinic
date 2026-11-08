import sys
from pathlib import Path

import pytest


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "training"))

from audit_validation_sources import source_of, summarize  # noqa: E402


def test_source_audit_separates_scin_and_does_not_count_absent_classes():
    def row(key, path, label, regularized, supcon):
        return {
            "sample_key": key, "case_key": key, "image_path": path,
            "recorded_label": label, "regularized_prediction": regularized,
            "supcon_prediction": supcon,
            "review_signal": "both_agree" if label == regularized == supcon else "one_disagrees",
        }

    result = summarize([
        row("a", "SkinDisease/train/Acne/a.jpg", "Acne", "Acne", "Acne"),
        row("b", "SkinDisease/scin-v1/train/Eczema/1/b.png", "Eczema", "Acne", "Eczema"),
    ])
    assert result["SkinDisease_original"]["images"] == 1
    assert result["SCIN_train_pool"]["images"] == 1
    assert result["SCIN_train_pool"]["models"]["supcon"]["macro_f1_present_classes"] == 1
    assert result["SCIN_train_pool"]["models"]["regularized"]["macro_f1_present_classes"] == 0


def test_source_audit_rejects_unrecognized_data_or_duplicate_rows():
    with pytest.raises(ValueError, match="Unknown validation image source"):
        source_of("SkinDisease/scin-v1/external_test/Eczema/image.png")
    bad = {
        "sample_key": "x", "case_key": "x", "image_path": "SkinDisease/train/Acne/a.jpg",
        "recorded_label": "Acne", "regularized_prediction": "Acne",
        "supcon_prediction": "Acne", "review_signal": "both_agree",
    }
    with pytest.raises(ValueError, match="unique"):
        summarize([bad, bad])
