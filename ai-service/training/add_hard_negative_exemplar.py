from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageEnhance, ImageOps


AI_SERVICE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AI_SERVICE_DIR))

from app.model import load_bundle, preprocess_image  # noqa: E402
from app.ood import is_out_of_scope  # noqa: E402


def variants(image: Image.Image) -> list[Image.Image]:
    rgb = image.convert("RGB")
    width, height = rgb.size

    def center_crop(scale: float) -> Image.Image:
        crop_width, crop_height = round(width * scale), round(height * scale)
        left, top = (width - crop_width) // 2, (height - crop_height) // 2
        return rgb.crop((left, top, left + crop_width, top + crop_height))

    return [
        rgb,
        ImageOps.mirror(rgb),
        ImageEnhance.Brightness(rgb).enhance(0.85),
        ImageEnhance.Brightness(rgb).enhance(1.15),
        ImageEnhance.Contrast(rgb).enhance(0.85),
        ImageEnhance.Contrast(rgb).enhance(1.15),
        center_crop(0.90),
        center_crop(0.80),
    ]


def embeddings(bundle, images: list[Image.Image]) -> np.ndarray:
    tensors = [preprocess_image(image)[0] for image in images]
    import torch

    batch = torch.stack(tensors).to(bundle.device)
    values = bundle.extract_embeddings(batch).cpu().numpy().astype(np.float32)
    return values / np.clip(np.linalg.norm(values, axis=1, keepdims=True), 1e-12, None)


def exemplar_rejections(
    values: np.ndarray, exemplars: np.ndarray, threshold: float
) -> np.ndarray:
    normalized = values / np.clip(np.linalg.norm(values, axis=1, keepdims=True), 1e-12, None)
    return np.max(normalized @ exemplars.T, axis=1) >= threshold


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Bổ sung mẫu hard-negative đã xác nhận vào cổng an toàn OOD."
    )
    parser.add_argument("--image", type=Path, required=True)
    parser.add_argument("--profile", type=Path, default=Path("models/ood_profile.json"))
    parser.add_argument("--checkpoint", type=Path, default=Path("models/best_model.pth"))
    parser.add_argument(
        "--cache", type=Path, default=Path("candidates/wseg_scope_embeddings.npz")
    )
    parser.add_argument(
        "--output", type=Path, default=Path("candidates/ood_profile_hard_negative.json")
    )
    parser.add_argument(
        "--report", type=Path, default=Path("reports/ai_evidence/hard_negative_gate.json")
    )
    parser.add_argument("--similarity-threshold", type=float, default=0.95)
    args = parser.parse_args()

    bundle = load_bundle(args.checkpoint, args.profile)
    if bundle is None or bundle.ood_profile is None:
        raise RuntimeError("Không nạp được model hoặc profile OOD nền.")
    with Image.open(args.image) as image:
        exemplar_matrix = embeddings(bundle, variants(image))

    cached = np.load(args.cache, allow_pickle=False)
    cohort_names = (
        "id_validation", "scin_calibration", "id_test", "local_validation",
        "local_test", "wound_validation", "wound_test",
    )
    cohorts: dict[str, dict] = {}
    for name in cohort_names:
        values = cached[name].astype(np.float32)
        exemplar = exemplar_rejections(values, exemplar_matrix, args.similarity_threshold)
        base = np.asarray(
            [is_out_of_scope(value, bundle.ood_profile)[0] for value in values], dtype=bool
        )
        cohorts[name] = {
            "count": len(values),
            "hard_negative_rejection_rate": float(exemplar.mean()),
            "base_rejection_rate": float(base.mean()),
            "combined_rejection_rate": float((exemplar | base).mean()),
            "maximum_similarity": float(np.max(values @ exemplar_matrix.T)),
        }

    with Image.open(args.image) as image:
        original_embedding = embeddings(bundle, [image])[0]
    original_similarity = float(np.max(exemplar_matrix @ original_embedding))
    original_base_rejected, original_base_score = is_out_of_scope(
        original_embedding, bundle.ood_profile
    )
    report = {
        "method": "confirmed_hard_negative_embedding_bank",
        "source": "User-confirmed unsupported wound/scratch image.",
        "image_bytes_stored_in_profile": False,
        "variant_count": len(exemplar_matrix),
        "similarity_threshold": args.similarity_threshold,
        "cohorts": cohorts,
        "regression_case": {
            "used_as_hard_negative": True,
            "base_rejected": original_base_rejected,
            "base_score": original_base_score,
            "hard_negative_similarity": original_similarity,
            "hard_negative_rejected": original_similarity >= args.similarity_threshold,
            "combined_rejected": bool(
                original_base_rejected or original_similarity >= args.similarity_threshold
            ),
        },
    }
    payload = json.loads(args.profile.read_text(encoding="utf-8"))
    existing = np.asarray(payload.get("hard_negative_exemplars", []), dtype=np.float32)
    if existing.ndim == 2 and len(existing):
        exemplar_matrix = np.concatenate([existing, exemplar_matrix])
    payload["hard_negative_exemplars"] = exemplar_matrix.tolist()
    payload["hard_negative_similarity_threshold"] = args.similarity_threshold
    payload["hard_negative_gate_summary"] = report
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
