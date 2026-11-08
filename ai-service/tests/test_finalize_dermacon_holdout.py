import sys
from pathlib import Path

import pytest


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "training"))

from finalize_dermacon_holdout import excluded_names  # noqa: E402


def test_near_candidates_are_excluded_before_inference():
    rows = [{"image_path": "images/a.jpg"}, {"image_path": "images/b.jpg"}]
    audit = {
        "mode": "audit_only", "model_inference_performed": False,
        "dataset": {"images": 2},
        "independence_checks": {
            "exact_hash_overlap_with_historical_train_and_test": 0,
            "exact_hash_overlap_with_previously_inspected_sources": 0,
            "potential_dhash_near_duplicate_count": 1,
            "potential_dhash_near_duplicates_for_manual_review": [
                {"new_image_path": "images\\b.jpg"}
            ],
        },
    }
    assert excluded_names(audit, rows) == {"b.jpg"}
    audit["model_inference_performed"] = True
    with pytest.raises(ValueError, match="pre-inference"):
        excluded_names(audit, rows)
