import sys
from pathlib import Path

import pytest


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "training"))

from prepare_dermacon_holdout import mapped_label, prepare  # noqa: E402


def row(name, subject, disease, confidence="5"):
    return {
        "Image_name": name, "Subject_ID": subject, "Disease_label": disease,
        "Confidence": confidence, "Gradability": "Yes",
        "Quality": "Yes, the quality is sufficient for me or another colleague to make a diagnosis.",
    }


def test_mapping_excludes_tuberculosis_lupus_and_low_confidence():
    assert mapped_label(row("a.jpg", "1", "Discoid Lupus Erythematosus")) == "Lupus"
    assert mapped_label(row("a.jpg", "1", "Lupus vulgaris")) is None
    assert mapped_label(row("a.jpg", "1", "Tinea Versicolor")) is None
    assert mapped_label(row("a.jpg", "1", "Tinea Corporis", "3")) is None
    assert mapped_label(row("a.jpg", "1", "Basal Cell Carcinoma")) == "SkinCancer"


def test_prepare_preserves_official_patient_split_and_pseudonymizes_ids():
    original = [row("a.jpg", "SUB001", "Tinea Corporis"), row("b.jpg", "SUB002", "Eczema")]
    selected, report = prepare(original, original[:1], original[1:])
    assert report["selected_images"] == 2
    assert {item["official_split"] for item in selected} == {"train", "test"}
    assert all("SUB" not in item["case_id"] for item in selected)
    with pytest.raises(ValueError, match="overlapping"):
        prepare([row("a.jpg", "SUB001", "Tinea Corporis"), row("b.jpg", "SUB001", "Eczema")],
                [row("a.jpg", "SUB001", "Tinea Corporis")], [row("b.jpg", "SUB001", "Eczema")])
