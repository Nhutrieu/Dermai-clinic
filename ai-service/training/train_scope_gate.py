from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import torch
from PIL import Image
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, roc_auc_score, roc_curve
from sklearn.model_selection import train_test_split
from torch.utils.data import DataLoader, Dataset

from common import CLASSES, IMAGE_EXTENSIONS, ImageSampleDataset, collect_samples, evaluation_transform


AI_SERVICE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AI_SERVICE_DIR))

from app.image_quality import assess_image_quality  # noqa: E402
from app.model import load_bundle  # noqa: E402


class PathDataset(Dataset):
    def __init__(self, paths: list[Path]):
        self.paths = paths
        self.transform = evaluation_transform()

    def __len__(self) -> int:
        return len(self.paths)

    def __getitem__(self, index: int):
        with Image.open(self.paths[index]) as image:
            return self.transform(image.convert("RGB")), index


def valid_ood_paths(root: Path) -> tuple[list[Path], list[str]]:
    paths: list[Path] = []
    categories: list[str] = []
    for category_root in sorted(item for item in root.iterdir() if item.is_dir() and item.name not in CLASSES):
        for path in sorted(category_root.rglob("*")):
            if not path.is_file() or path.suffix.lower() not in IMAGE_EXTENSIONS:
                continue
            try:
                with Image.open(path) as image:
                    if not assess_image_quality(image).accepted:
                        continue
            except OSError:
                continue
            paths.append(path)
            categories.append(category_root.name)
    return paths, categories


def main() -> None:
    parser = argparse.ArgumentParser(description="Huấn luyện cổng nhị phân nhận diện ảnh ngoài phạm vi.")
    parser.add_argument("--checkpoint", type=Path, default=Path("models/best_model.pth"))
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("models/ood_profile.json"))
    parser.add_argument("--report", type=Path, default=Path("reports/ai_evidence/scope_gate_validation.json"))
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--validation-ratio", type=float, default=0.2)
    parser.add_argument("--max-id-fpr", type=float, default=0.05)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    bundle = load_bundle(args.checkpoint)
    if bundle is None:
        raise RuntimeError("Không nạp được model.")
    id_samples = collect_samples(args.data, "train", bundle.classes)
    ood_paths, ood_categories = valid_ood_paths(args.data / "train")
    if not ood_paths:
        raise RuntimeError("Không có ảnh ngoài phạm vi hợp lệ.")

    def embeddings(loader: DataLoader) -> np.ndarray:
        values: list[np.ndarray] = []
        for inputs, _targets in loader:
            values.append(bundle.extract_embeddings(inputs.to(bundle.device)).cpu().numpy())
        return np.concatenate(values)

    id_matrix = embeddings(DataLoader(ImageSampleDataset(id_samples, evaluation_transform()), batch_size=args.batch_size))
    ood_matrix = embeddings(DataLoader(PathDataset(ood_paths), batch_size=args.batch_size))
    id_train, id_validation = train_test_split(id_matrix, test_size=args.validation_ratio, random_state=args.seed)
    indices = np.arange(len(ood_matrix))
    ood_train_indices, ood_validation_indices = train_test_split(
        indices,
        test_size=args.validation_ratio,
        random_state=args.seed,
        stratify=np.asarray(ood_categories),
    )
    train_x = np.concatenate([id_train, ood_matrix[ood_train_indices]])
    train_y = np.concatenate([np.zeros(len(id_train)), np.ones(len(ood_train_indices))])
    validation_x = np.concatenate([id_validation, ood_matrix[ood_validation_indices]])
    validation_y = np.concatenate([np.zeros(len(id_validation)), np.ones(len(ood_validation_indices))])
    classifier = LogisticRegression(max_iter=2000, class_weight="balanced", random_state=args.seed)
    classifier.fit(train_x, train_y)
    scores = classifier.predict_proba(validation_x)[:, 1]
    fpr, tpr, thresholds = roc_curve(validation_y, scores)
    valid = np.flatnonzero(fpr <= args.max_id_fpr)
    selected = valid[np.argmax(tpr[valid])]
    threshold = float(thresholds[selected])
    reached = np.flatnonzero(tpr >= 0.95)
    report = {
        "method": "frozen_feature_logistic_scope_gate",
        "model_version": bundle.version,
        "seed": args.seed,
        "training_id_count": len(id_train),
        "training_ood_count": len(ood_train_indices),
        "validation_id_count": len(id_validation),
        "validation_ood_count": len(ood_validation_indices),
        "auroc": float(roc_auc_score(validation_y, scores)),
        "aupr_ood": float(average_precision_score(validation_y, scores)),
        "fpr95": float(fpr[reached[0]]) if len(reached) else 1.0,
        "score_threshold": threshold,
        "validation_id_false_rejection_rate": float((scores[:len(id_validation)] >= threshold).mean()),
        "validation_ood_rejection_rate": float((scores[len(id_validation):] >= threshold).mean()),
        "limitation": "Trained on near-OOD dermatology categories; wounds, scratches and burns still require a separate held-out cohort.",
    }
    profile = {
        "schema_version": 2,
        "model_version": bundle.version,
        "classes": bundle.classes,
        "method": report["method"],
        "score_threshold": threshold,
        "linear_weights": classifier.coef_[0].tolist(),
        "linear_bias": float(classifier.intercept_[0]),
        "training_summary": report,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(profile, ensure_ascii=False), encoding="utf-8")
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
