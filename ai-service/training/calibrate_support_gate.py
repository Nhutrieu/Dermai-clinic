from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image
from sklearn.cluster import MiniBatchKMeans


AI_SERVICE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AI_SERVICE_DIR))

from app.model import load_bundle, preprocess_image  # noqa: E402
from app.ood import is_out_of_scope  # noqa: E402


def normalize_rows(values: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(values, axis=1, keepdims=True)
    return values / np.clip(norms, 1e-12, None)


def similarities(values: np.ndarray, prototypes: np.ndarray) -> np.ndarray:
    return np.max(normalize_rows(values) @ prototypes.T, axis=1)


def base_decisions(values: np.ndarray, profile) -> np.ndarray:
    return np.asarray([is_out_of_scope(value, profile)[0] for value in values], dtype=bool)


def rate(values: np.ndarray) -> float | None:
    return float(values.mean()) if len(values) else None


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Hiệu chỉnh cổng độ phủ prototype cho ảnh ngoài miền dữ liệu."
    )
    parser.add_argument(
        "--cache", type=Path, default=Path("candidates/wseg_scope_embeddings.npz")
    )
    parser.add_argument("--profile", type=Path, default=Path("models/ood_profile.json"))
    parser.add_argument(
        "--output", type=Path, default=Path("candidates/ood_profile_support_gate.json")
    )
    parser.add_argument(
        "--report", type=Path, default=Path("reports/ai_evidence/support_gate.json")
    )
    parser.add_argument("--checkpoint", type=Path, default=Path("models/best_model.pth"))
    parser.add_argument("--external-image", type=Path)
    parser.add_argument("--max-support-id-fpr", type=float, default=0.01)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    cached = np.load(args.cache, allow_pickle=False)
    arrays = {name: cached[name].astype(np.float32) for name in cached.files}
    train_id = np.concatenate([arrays["id_train"], arrays["scin_train"]])
    validation_names = (
        "id_validation", "scin_calibration", "local_validation", "wound_validation"
    )
    test_names = ("id_test", "local_test", "wound_test")

    payload = json.loads(args.profile.read_text(encoding="utf-8"))
    bundle = load_bundle(args.checkpoint, args.profile)
    if bundle is None or bundle.ood_profile is None:
        raise RuntimeError("Không nạp được model hoặc profile OOD nền.")

    trials: list[dict] = []
    selected: dict | None = None
    for cluster_count in (16, 32, 64, 128):
        estimator = MiniBatchKMeans(
            n_clusters=cluster_count,
            random_state=args.seed,
            batch_size=512,
            n_init=5,
            max_iter=200,
        )
        estimator.fit(train_id)
        prototypes = normalize_rows(estimator.cluster_centers_.astype(np.float32))
        id_similarity = similarities(arrays["id_validation"], prototypes)
        scin_similarity = similarities(arrays["scin_calibration"], prototypes)
        threshold = min(
            float(np.quantile(id_similarity, args.max_support_id_fpr, method="lower")),
            float(np.quantile(scin_similarity, args.max_support_id_fpr, method="lower")),
        )
        metrics: dict[str, float | int] = {
            "cluster_count": cluster_count,
            "similarity_threshold": threshold,
        }
        for name in validation_names:
            support = similarities(arrays[name], prototypes) < threshold
            base = base_decisions(arrays[name], bundle.ood_profile)
            metrics[f"{name}_support_rejection_rate"] = float(support.mean())
            metrics[f"{name}_combined_rejection_rate"] = float((support | base).mean())
        objective = float(
            metrics["wound_validation_combined_rejection_rate"]
            + 0.25 * metrics["local_validation_combined_rejection_rate"]
        )
        metrics["objective"] = objective
        trials.append(metrics)
        if selected is None or objective > float(selected["metrics"]["objective"]):
            selected = {"metrics": metrics, "prototypes": prototypes}

    assert selected is not None
    metrics = selected["metrics"]
    prototypes = selected["prototypes"]
    threshold = float(metrics["similarity_threshold"])
    held_out: dict[str, dict] = {}
    for name in test_names:
        support = similarities(arrays[name], prototypes) < threshold
        base = base_decisions(arrays[name], bundle.ood_profile)
        held_out[name] = {
            "count": len(support),
            "support_rejection_rate": rate(support),
            "base_rejection_rate": rate(base),
            "combined_rejection_rate": rate(support | base),
        }

    external: dict | None = None
    if args.external_image:
        with Image.open(args.external_image) as image:
            tensor, _base = preprocess_image(image)
        embedding = bundle.extract_embeddings(
            tensor.unsqueeze(0).to(bundle.device)
        )[0].cpu().numpy()
        similarity = float(similarities(embedding[None, :], prototypes)[0])
        base_rejected, base_score = is_out_of_scope(embedding, bundle.ood_profile)
        external = {
            "path": str(args.external_image),
            "used_for_fit_or_threshold": False,
            "base_rejected": base_rejected,
            "base_score": base_score,
            "support_similarity": similarity,
            "support_threshold": threshold,
            "support_rejected": similarity < threshold,
            "combined_rejected": bool(base_rejected or similarity < threshold),
        }

    report = {
        "method": "normalized_embedding_support_prototypes",
        "selection": "Cluster count selected on validation cohorts only.",
        "max_support_id_false_rejection_rate": args.max_support_id_fpr,
        "trials": trials,
        "selected": metrics,
        "held_out_test": held_out,
        "external_regression_case": external,
    }
    payload["support_prototypes"] = prototypes.tolist()
    payload["support_similarity_threshold"] = threshold
    payload["support_gate_summary"] = report
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
