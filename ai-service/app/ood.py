from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np


@dataclass(frozen=True)
class OodProfile:
    classes: list[str]
    centroids: np.ndarray | None
    distance_threshold: float | None
    model_version: str
    linear_weights: np.ndarray | None = None
    linear_bias: float = 0.0
    score_threshold: float | None = None
    feature_mean: np.ndarray | None = None
    feature_scale: np.ndarray | None = None
    mlp_weights: tuple[np.ndarray, np.ndarray] | None = None
    mlp_biases: tuple[np.ndarray, np.ndarray] | None = None
    hard_negative_exemplars: np.ndarray | None = None
    hard_negative_similarity_threshold: float | None = None


def load_ood_profile(path: Path, classes: list[str], model_version: str) -> OodProfile | None:
    if not path.exists():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("classes") != classes or payload.get("model_version") != model_version:
        return None
    if payload.get("method") == "frozen_feature_mlp_scope_gate":
        mean = np.asarray(payload.get("feature_mean"), dtype=np.float32)
        scale = np.asarray(payload.get("feature_scale"), dtype=np.float32)
        weights = tuple(
            np.asarray(item, dtype=np.float32) for item in payload.get("mlp_weights", [])
        )
        biases = tuple(
            np.asarray(item, dtype=np.float32) for item in payload.get("mlp_biases", [])
        )
        raw_exemplars = payload.get("hard_negative_exemplars")
        exemplar_threshold = payload.get("hard_negative_similarity_threshold")
        exemplars = (
            np.asarray(raw_exemplars, dtype=np.float32)
            if raw_exemplars is not None
            else None
        )
        valid_exemplars = (
            exemplars is None
            and exemplar_threshold is None
        ) or (
            exemplars is not None
            and exemplars.ndim == 2
            and exemplars.shape[1] == len(mean)
            and len(exemplars) > 0
            and exemplar_threshold is not None
            and 0.0 < float(exemplar_threshold) <= 1.0
        )
        valid = (
            mean.ndim == 1
            and scale.shape == mean.shape
            and np.all(scale > 0)
            and len(weights) == 2
            and len(biases) == 2
            and weights[0].ndim == 2
            and weights[0].shape[1] == len(mean)
            and biases[0].shape == (weights[0].shape[0],)
            and weights[1].shape == (1, weights[0].shape[0])
            and biases[1].shape == (1,)
            and valid_exemplars
        )
        if not valid:
            return None
        return OodProfile(
            classes=classes,
            centroids=None,
            distance_threshold=None,
            model_version=model_version,
            score_threshold=float(payload["score_threshold"]),
            feature_mean=mean,
            feature_scale=scale,
            mlp_weights=(weights[0], weights[1]),
            mlp_biases=(biases[0], biases[1]),
            hard_negative_exemplars=exemplars,
            hard_negative_similarity_threshold=(
                float(exemplar_threshold) if exemplar_threshold is not None else None
            ),
        )
    if payload.get("method") == "frozen_feature_logistic_scope_gate":
        weights = np.asarray(payload.get("linear_weights"), dtype=np.float32)
        if weights.ndim != 1:
            return None
        return OodProfile(
            classes=classes,
            centroids=None,
            distance_threshold=None,
            model_version=model_version,
            linear_weights=weights,
            linear_bias=float(payload.get("linear_bias", 0.0)),
            score_threshold=float(payload["score_threshold"]),
        )
    centroids = np.asarray(payload.get("centroids"), dtype=np.float32)
    if centroids.ndim != 2 or centroids.shape[0] != len(classes):
        return None
    norms = np.linalg.norm(centroids, axis=1, keepdims=True)
    centroids = centroids / np.clip(norms, 1e-12, None)
    return OodProfile(
        classes=classes,
        centroids=centroids,
        distance_threshold=float(payload["distance_threshold"]),
        model_version=model_version,
    )


def nearest_centroid_distance(embedding: np.ndarray, profile: OodProfile) -> float:
    if profile.centroids is None:
        raise ValueError("Hồ sơ không chứa centroid.")
    vector = np.asarray(embedding, dtype=np.float32).reshape(-1)
    vector /= max(float(np.linalg.norm(vector)), 1e-12)
    return float(1.0 - np.max(profile.centroids @ vector))


def is_out_of_scope(embedding: np.ndarray, profile: OodProfile) -> tuple[bool, float]:
    vector = np.asarray(embedding, dtype=np.float32).reshape(-1)
    if profile.hard_negative_exemplars is not None:
        if (
            profile.hard_negative_similarity_threshold is None
            or profile.hard_negative_exemplars.ndim != 2
            or profile.hard_negative_exemplars.shape[1] != len(vector)
        ):
            raise ValueError("Kích thước đặc trưng không khớp ngân hàng hard-negative.")
        normalized = vector / max(float(np.linalg.norm(vector)), 1e-12)
        similarity = float(np.max(profile.hard_negative_exemplars @ normalized))
        if similarity >= profile.hard_negative_similarity_threshold:
            return True, similarity
    if profile.mlp_weights is not None and profile.mlp_biases is not None:
        if (
            profile.feature_mean is None
            or profile.feature_scale is None
            or profile.score_threshold is None
            or vector.shape != profile.feature_mean.shape
        ):
            raise ValueError("Kích thước đặc trưng không khớp hồ sơ OOD MLP.")
        standardized = (vector - profile.feature_mean) / profile.feature_scale
        hidden = np.maximum(profile.mlp_weights[0] @ standardized + profile.mlp_biases[0], 0.0)
        logit = float((profile.mlp_weights[1] @ hidden + profile.mlp_biases[1])[0])
        score = float(1.0 / (1.0 + np.exp(-np.clip(logit, -60, 60))))
        return score >= profile.score_threshold, score
    if profile.linear_weights is not None and profile.score_threshold is not None:
        if vector.shape != profile.linear_weights.shape:
            raise ValueError("Kích thước đặc trưng không khớp hồ sơ OOD.")
        logit = float(profile.linear_weights @ vector + profile.linear_bias)
        score = float(1.0 / (1.0 + np.exp(-np.clip(logit, -60, 60))))
        return score >= profile.score_threshold, score
    score = nearest_centroid_distance(vector, profile)
    return score > float(profile.distance_threshold), score
