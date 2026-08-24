import json
import sys
from pathlib import Path

import numpy as np


AI_SERVICE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AI_SERVICE_DIR))

from app.ood import is_out_of_scope, load_ood_profile, nearest_centroid_distance  # noqa: E402


def test_profile_rejects_mismatched_model(tmp_path):
    path = tmp_path / "profile.json"
    path.write_text(json.dumps({"classes": ["a"], "model_version": "old", "centroids": [[1, 0]], "distance_threshold": 0.2}))
    assert load_ood_profile(path, ["a"], "new") is None


def test_nearest_centroid_cosine_distance(tmp_path):
    path = tmp_path / "profile.json"
    path.write_text(json.dumps({"classes": ["a", "b"], "model_version": "v1", "centroids": [[1, 0], [0, 1]], "distance_threshold": 0.2}))
    profile = load_ood_profile(path, ["a", "b"], "v1")
    assert profile is not None
    assert nearest_centroid_distance(np.array([1.0, 0.0]), profile) == 0.0


def test_mlp_profile_loads_and_scores_embeddings(tmp_path):
    path = tmp_path / "profile.json"
    path.write_text(
        json.dumps(
            {
                "classes": ["a"],
                "model_version": "v2",
                "method": "frozen_feature_mlp_scope_gate",
                "score_threshold": 0.5,
                "feature_mean": [0.0, 0.0],
                "feature_scale": [1.0, 1.0],
                "mlp_weights": [[[1.0, 0.0], [0.0, 1.0]], [[2.0, 2.0]]],
                "mlp_biases": [[0.0, 0.0], [-1.0]],
            }
        ),
        encoding="utf-8",
    )
    profile = load_ood_profile(path, ["a"], "v2")
    assert profile is not None
    rejected, high_score = is_out_of_scope(np.asarray([1.0, 1.0]), profile)
    accepted, low_score = is_out_of_scope(np.asarray([-1.0, -1.0]), profile)
    assert rejected is True
    assert accepted is False
    assert high_score > low_score


def test_mlp_profile_rejects_invalid_shapes(tmp_path):
    path = tmp_path / "profile.json"
    path.write_text(
        json.dumps({
            "classes": ["a"], "model_version": "v2",
            "method": "frozen_feature_mlp_scope_gate", "score_threshold": 0.5,
            "feature_mean": [0.0, 0.0], "feature_scale": [1.0, 1.0],
            "mlp_weights": [[[1.0]], [[1.0]]], "mlp_biases": [[0.0], [0.0]],
        }), encoding="utf-8"
    )
    assert load_ood_profile(path, ["a"], "v2") is None


def test_hard_negative_exemplar_overrides_mlp_acceptance(tmp_path):
    path = tmp_path / "profile.json"
    path.write_text(
        json.dumps(
            {
                "classes": ["a"],
                "model_version": "v3",
                "method": "frozen_feature_mlp_scope_gate",
                "score_threshold": 0.5,
                "feature_mean": [0.0, 0.0],
                "feature_scale": [1.0, 1.0],
                "mlp_weights": [[[1.0, 0.0], [0.0, 1.0]], [[2.0, 2.0]]],
                "mlp_biases": [[0.0, 0.0], [-1.0]],
                "hard_negative_exemplars": [[-0.7071068, -0.7071068]],
                "hard_negative_similarity_threshold": 0.99,
            }
        ),
        encoding="utf-8",
    )
    profile = load_ood_profile(path, ["a"], "v3")
    assert profile is not None
    rejected, similarity = is_out_of_scope(np.asarray([-1.0, -1.0]), profile)
    assert rejected is True
    assert similarity >= 0.99


def test_hard_negative_profile_rejects_invalid_shape(tmp_path):
    path = tmp_path / "profile.json"
    path.write_text(json.dumps({
        "classes": ["a"], "model_version": "v3", "method": "frozen_feature_mlp_scope_gate",
        "score_threshold": 0.5, "feature_mean": [0.0, 0.0], "feature_scale": [1.0, 1.0],
        "mlp_weights": [[[1.0, 0.0]], [[1.0]]], "mlp_biases": [[0.0], [0.0]],
        "hard_negative_exemplars": [[1.0]], "hard_negative_similarity_threshold": 0.95,
    }), encoding="utf-8")
    assert load_ood_profile(path, ["a"], "v3") is None
