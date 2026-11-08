import sys
from pathlib import Path


TRAINING_DIR = Path(__file__).resolve().parents[1] / "training"
sys.path.insert(0, str(TRAINING_DIR))

from build_validation_review_queue import choose_review_rows, review_signal  # noqa: E402


def test_review_signal_never_claims_label_error():
    assert review_signal(0, 0, 0) == "both_agree"
    assert review_signal(0, 1, 1) == "both_disagree_same_prediction"
    assert review_signal(0, 1, 2) == "both_disagree_different_predictions"
    assert review_signal(0, 0, 1) == "one_disagrees"


def test_review_selection_keeps_distinct_cases_and_agreement_controls():
    def row(key, case, signal, concern=0, confidence=0.9):
        return {
            "sample_key": key, "case_key": case, "review_signal": signal,
            "clinical_priority": concern, "regularized_probability": confidence,
            "supcon_probability": confidence,
        }

    rows = [
        row("a", "case1", "both_disagree_same_prediction"),
        row("b", "case1", "both_disagree_same_prediction", 1),
        row("c", "case2", "both_disagree_different_predictions", 1),
        row("d", "case3", "one_disagrees"),
        row("e", "case4", "both_agree"),
        row("f", "case5", "both_agree"),
    ]
    priority, controls = choose_review_rows(rows, priority_limit=3, control_count=1, seed=42)
    assert [item["sample_key"] for item in priority] == ["b", "c", "d"]
    assert len(controls) == 1 and controls[0]["review_signal"] == "both_agree"
    assert len({item["case_key"] for item in [*priority, *controls]}) == 4
    assert choose_review_rows(rows, 0, 0, 42) == ([], [])
