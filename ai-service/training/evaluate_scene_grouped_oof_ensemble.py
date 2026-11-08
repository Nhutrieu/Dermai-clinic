"""Compare fixed two-model probability blends using locked grouped OOF predictions.

The selected blend is a development choice. Its OOF score is not an untouched
test score, and this script never reads the external test sources.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix

from common import CLASSES, save_json, sha256_file
from evaluate_evidence import calibration_metrics
from prepare_scene_grouped_oof_folds import OUTPUT as OUTER_MANIFEST, PROJECT


RUN_ROOT = PROJECT / "ai-service/candidates"
OUTPUT = PROJECT / "ai-service/reports/scene_grouped_oof_ensemble_seed42.json"
SUMMARY = PROJECT / "ai-service/reports/scene_grouped_oof_ensemble_seed42.md"
ARCHITECTURES = {
    "efficientnet_b0": "oof_b0_fold{fold}_seed42",
    "convnext_tiny": "oof_convnext_fold{fold}_seed42",
}
CONVNEXT_WEIGHTS = (0.0, 0.25, 0.5, 0.75, 1.0)


def read_probabilities(architecture: str, fold: int, outer: dict, expected_rows: dict) -> dict[str, np.ndarray]:
    directory = RUN_ROOT / ARCHITECTURES[architecture].format(fold=fold)
    payload = json.loads((directory / "oof_predictions.json").read_text(encoding="utf-8"))
    selection = json.loads((directory / "selection_report.json").read_text(encoding="utf-8"))
    dataset = json.loads((directory / "dataset_summary.json").read_text(encoding="utf-8"))
    if (
        payload["outer_fold"] != fold
        or payload["outer_manifest_sha256"] != outer["manifest_sha256"]
        or payload["architecture"] != architecture
        or payload["classes"] != CLASSES
        or payload["checkpoint_sha256"] != sha256_file(directory / "best_model.pth")
        or selection["configuration"]["oof_fold"] != fold
        or selection["configuration"]["model"] != architecture
        or selection["fixed_test_used_for_selection"] is not False
        or selection["external_test_used_for_selection"] is not False
        or dataset["oof"]["checkpoint_selection_role"] != "inner_validation_only"
        or dataset["oof"]["outer_manifest_sha256"] != outer["manifest_sha256"]
    ):
        raise ValueError(f"OOF provenance mismatch: {directory}")
    result = {}
    for row in payload["rows"]:
        path = row["path"]
        expected = expected_rows.get(path)
        if expected is None or path in result:
            raise ValueError(f"Unexpected or repeated OOF image: {path}")
        if row["sha256"] != expected["sha256"] or row["class"] != expected["class"]:
            raise ValueError(f"OOF image label/hash mismatch: {path}")
        probabilities = np.asarray(row["probabilities"], dtype=float)
        if (
            probabilities.shape != (len(CLASSES),)
            or not np.isfinite(probabilities).all()
            or (probabilities < 0).any()
            or abs(float(probabilities.sum()) - 1.0) > 1e-4
        ):
            raise ValueError(f"Invalid probability vector: {path}")
        result[path] = probabilities
    if set(result) != set(expected_rows):
        raise ValueError(f"Incomplete OOF fold: {directory}")
    return result


def score(probabilities: np.ndarray, targets: np.ndarray) -> dict:
    predicted = probabilities.argmax(axis=1)
    report = classification_report(
        targets, predicted, labels=list(range(len(CLASSES))),
        target_names=CLASSES, output_dict=True, zero_division=0,
    )
    calibration = calibration_metrics(probabilities, targets)
    top3 = np.argsort(-probabilities, axis=1)[:, :3]
    return {
        "accuracy": float(accuracy_score(targets, predicted)),
        "macro_recall": float(report["macro avg"]["recall"]),
        "macro_f1": float(report["macro avg"]["f1-score"]),
        "top3_accuracy": float((top3 == targets[:, None]).any(axis=1).mean()),
        "confusion_matrix": confusion_matrix(
            targets, predicted, labels=list(range(len(CLASSES)))
        ).tolist(),
        "calibration": {
            key: calibration[key] for key in (
                "mean_confidence", "expected_calibration_error",
                "negative_log_likelihood", "multiclass_brier_score",
            )
        },
        "per_class": {
            name: {
                "support": int(report[name]["support"]),
                "recall": float(report[name]["recall"]),
                "precision": float(report[name]["precision"]),
                "f1": float(report[name]["f1-score"]),
            }
            for name in CLASSES
        },
    }


def source_score(probabilities: np.ndarray, targets: np.ndarray) -> dict:
    """Keep absent classes out of a source-specific macro recall."""
    predicted = probabilities.argmax(axis=1)
    classes_present = [index for index in range(len(CLASSES)) if (targets == index).any()]
    per_class = {}
    for index in classes_present:
        matching = targets == index
        per_class[CLASSES[index]] = {
            "images": int(matching.sum()),
            "recall": float((predicted[matching] == index).mean()),
        }
    return {
        "images": len(targets),
        "accuracy": float((predicted == targets).mean()),
        "macro_recall_present_classes": float(np.mean([
            item["recall"] for item in per_class.values()
        ])),
        "per_class": per_class,
    }


def paired_cluster_interval(
    selected_correct: np.ndarray, single_correct: np.ndarray, groups: list[str],
    seed: int = 42, repetitions: int = 3000,
) -> list[float]:
    """Resample known case/scene groups; unknown patients remain singletons."""
    if len(selected_correct) != len(single_correct) or len(groups) != len(selected_correct):
        raise ValueError("Paired bootstrap rows differ")
    _, inverse = np.unique(np.asarray(groups), return_inverse=True)
    group_count = int(inverse.max()) + 1
    group_sizes = np.bincount(inverse, minlength=group_count)
    difference = selected_correct.astype(float) - single_correct.astype(float)
    group_differences = np.bincount(inverse, weights=difference, minlength=group_count)
    rng = np.random.default_rng(seed)
    estimates = np.empty(repetitions, dtype=float)
    for iteration in range(repetitions):
        sampled = rng.integers(0, group_count, size=group_count)
        estimates[iteration] = group_differences[sampled].sum() / group_sizes[sampled].sum()
    return [float(value) for value in np.quantile(estimates, [0.025, 0.975])]


def write_summary(report: dict) -> None:
    def percent(value: float) -> str:
        return f"{100 * value:.2f}%"

    image_count = f"{report['images']:,}".replace(",", ".")
    lines = [
        "# So sánh OOF năm fold: B0, ConvNeXt và tổ hợp",
        "",
        f"Tập phát triển: **{image_count} ảnh**, chia năm fold theo nhóm ca/cảnh. "
        "Mỗi dự đoán được tạo từ checkpoint không học và không chọn epoch trên fold chứa ảnh đó.",
        "",
        "**Đây là kết quả phát triển để chọn cách kết hợp, không phải độ chính xác trên test độc lập mới.** "
        "Công thức train đã được nghiên cứu trên nguồn này trước khi chia lại fold. "
        "Nhiều ảnh không có mã bệnh nhân nên không thể xác nhận tách hoàn toàn theo người.",
        "",
        "| Tỉ trọng ConvNeXt | Accuracy | Macro recall | Macro F1 | SkinCancer recall | Train gốc accuracy | SCIN accuracy |",
        "| ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for name, item in report["candidates"].items():
        metrics = item["metrics"]
        selected = " **được chọn**" if name == report["selected"] else ""
        lines.append(
            f"| {item['convnext_weight']:.2f}{selected} | {percent(metrics['accuracy'])} "
            f"| {percent(metrics['macro_recall'])} | {percent(metrics['macro_f1'])} "
            f"| {percent(metrics['per_class']['SkinCancer']['recall'])} "
            f"| {percent(item['per_source']['original_train']['accuracy'])} "
            f"| {percent(item['per_source']['SCIN']['accuracy'])} |"
        )
    selected = report["candidates"][report["selected"]]
    selected_weight = selected["convnext_weight"]
    if selected_weight == 0.0:
        choice = ("Phương án được chọn là EfficientNet-B0 đơn. Trong năm tỉ trọng đã thử, "
                  "phép gộp không thắng quy tắc chọn trên OOF.")
    elif selected_weight == 1.0:
        choice = ("Phương án được chọn là ConvNeXt-Tiny đơn. Trong năm tỉ trọng đã thử, "
                  "phép gộp không thắng quy tắc chọn trên OOF.")
    else:
        choice = f"Phương án được chọn là tổ hợp với tỉ trọng ConvNeXt {selected_weight:.2f}."
    lines += [
        "",
        "Quy tắc chọn đã định trước: recall SkinCancer không thấp hơn model đơn tốt nhất; "
        "sau đó ưu tiên macro recall, macro F1 rồi accuracy trong năm tỉ trọng đã khóa.",
        choice,
        "",
        "## Kết quả của phương án được chọn theo từng bệnh",
        "",
        "| Bệnh | Số ảnh | Recall | Precision | F1 |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for name, item in selected["metrics"]["per_class"].items():
        lines.append(
            f"| {name} | {item['support']} | {percent(item['recall'])} "
            f"| {percent(item['precision'])} | {percent(item['f1'])} |"
        )
    lines += [
        "",
        "## Theo nguồn ảnh",
        "",
        "| Nguồn | Số ảnh | Số lớp có ảnh | Accuracy | Macro recall trên lớp có ảnh |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for name, item in selected["per_source"].items():
        lines.append(
            f"| {name} | {item['images']} | {len(item['per_class'])} "
            f"| {percent(item['accuracy'])} | {percent(item['macro_recall_present_classes'])} |"
        )
    lines += [
        "",
        "## So sánh ghép theo cùng ảnh với từng model đơn",
        "",
        "| Model đơn | Phương án chọn sửa đúng | Phương án chọn làm sai | Chênh accuracy | Khoảng bootstrap 95% theo nhóm ca/cảnh |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for name, item in report["selected_paired_against_single_models"].items():
        lower, upper = item["paired_bootstrap_95pct_interval"]
        lines.append(
            f"| {name} | {item['selected_correct_single_wrong']} "
            f"| {item['single_correct_selected_wrong']} "
            f"| {percent(item['accuracy_difference'])} | [{percent(lower)}; {percent(upper)}] |"
        )
    lines += [
        "",
        "Khoảng bootstrap này mô tả biến thiên trên chính tập phát triển. Vì tỉ trọng tổ hợp được chọn "
        "bằng dự đoán OOF của tập này, khoảng đó không xác nhận mức cải thiện trên dữ liệu mới.",
        "",
        "SCIN trong tập này không có ảnh SkinCancer. Chỉ số SCIN không đánh giá được khả năng phát hiện lớp đó. "
        "Ma trận nhầm lẫn, top-3, hiệu chuẩn, kết quả từng fold và số ảnh sửa/làm sai "
        "so với model đơn nằm trong tệp JSON cùng tên.",
        "",
        "Sau khi chọn phương án, cần một bộ test mới đủ tám bệnh, tách bệnh nhân/nguồn và có nhãn đáng tin cậy "
        "để xác nhận khả năng tổng quát hóa trước khi thay mô hình đang dùng.",
        "",
    ]
    SUMMARY.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    if OUTPUT.exists() or SUMMARY.exists():
        raise FileExistsError(f"Preserving prior OOF comparison: {OUTPUT} / {SUMMARY}")
    outer = json.loads(OUTER_MANIFEST.read_text(encoding="utf-8"))
    if outer["total_images"] != 5937 or outer["fold_count"] != 5:
        raise ValueError("Unexpected OOF manifest")
    canonical = "".join(
        f"{row['fold']}\t{row['class']}\t{row['path']}\t{row['sha256']}\t{row['scene_or_case_group']}\n"
        for row in outer["images"]
    )
    if hashlib.sha256(canonical.encode("utf-8")).hexdigest() != outer["manifest_sha256"]:
        raise ValueError("OOF manifest checksum mismatch")
    paths = [row["path"] for row in outer["images"]]
    if len(paths) != len(set(paths)):
        raise ValueError("Repeated path in outer OOF manifest")
    targets = np.asarray([CLASSES.index(row["class"]) for row in outer["images"]], dtype=int)
    by_architecture = {}
    for architecture in ARCHITECTURES:
        predictions = {}
        for fold in range(5):
            expected = {
                row["path"]: row for row in outer["images"] if row["fold"] == fold
            }
            predictions.update(read_probabilities(architecture, fold, outer, expected))
        if set(predictions) != set(paths):
            raise ValueError(f"Missing OOF images for {architecture}")
        by_architecture[architecture] = np.stack([predictions[path] for path in paths])

    b0 = by_architecture["efficientnet_b0"]
    convnext = by_architecture["convnext_tiny"]
    folds = np.asarray([row["fold"] for row in outer["images"]], dtype=int)
    sources = np.asarray([
        "SCIN" if row["path"].startswith("SkinDisease/scin-v1/") else "original_train"
        for row in outer["images"]
    ])
    candidates = {}
    for weight in CONVNEXT_WEIGHTS:
        key = f"convnext_{weight:.2f}_b0_{1 - weight:.2f}"
        blended = (1 - weight) * b0 + weight * convnext
        candidates[key] = {
            "convnext_weight": weight,
            "metrics": score(blended, targets),
            "per_source": {
                source: source_score(blended[sources == source], targets[sources == source])
                for source in ("original_train", "SCIN")
            },
            "per_fold": [
                {
                    "fold": fold,
                    "images": int((folds == fold).sum()),
                    **{
                        name: value for name, value in score(blended[folds == fold], targets[folds == fold]).items()
                        if name in ("accuracy", "macro_recall", "macro_f1", "top3_accuracy")
                    },
                }
                for fold in range(5)
            ],
        }
    best_single_skin_cancer_recall = max(
        candidates[key]["metrics"]["per_class"]["SkinCancer"]["recall"]
        for key in ("convnext_0.00_b0_1.00", "convnext_1.00_b0_0.00")
    )
    eligible = [
        key for key, item in candidates.items()
        if item["metrics"]["per_class"]["SkinCancer"]["recall"] + 1e-12
        >= best_single_skin_cancer_recall
    ]
    selected_name = max(
        eligible,
        key=lambda key: (
            candidates[key]["metrics"]["macro_recall"],
            candidates[key]["metrics"]["macro_f1"],
            candidates[key]["metrics"]["accuracy"],
            -abs(candidates[key]["convnext_weight"] - 0.5),
        ),
    )
    selected_weight = candidates[selected_name]["convnext_weight"]
    selected_correct = ((1 - selected_weight) * b0 + selected_weight * convnext).argmax(axis=1) == targets
    groups = [row["scene_or_case_group"] for row in outer["images"]]
    paired = {}
    for name, single in (("efficientnet_b0", b0), ("convnext_tiny", convnext)):
        single_correct = single.argmax(axis=1) == targets
        paired[name] = {
            "selected_correct_single_wrong": int((selected_correct & ~single_correct).sum()),
            "single_correct_selected_wrong": int((~selected_correct & single_correct).sum()),
            "accuracy_difference": float(selected_correct.mean() - single_correct.mean()),
            "paired_bootstrap_95pct_interval": paired_cluster_interval(
                selected_correct, single_correct, groups,
            ),
            "bootstrap_unit": "known_case_or_scene_group_otherwise_image",
            "bootstrap_repetitions": 3000,
        }
    result = {
        "scope": "Development OOF comparison and blend selection; selected score is not independent test performance.",
        "outer_manifest_sha256": outer["manifest_sha256"],
        "images": len(paths),
        "folds": 5,
        "selection_metric": "Require SkinCancer recall at least the best single OOF model; then macro recall, macro F1, accuracy; five pre-specified weights.",
        "best_single_skin_cancer_recall": best_single_skin_cancer_recall,
        "eligible_candidates": eligible,
        "candidates": candidates,
        "selected": selected_name,
        "selected_paired_against_single_models": paired,
    }
    write_summary(result)
    save_json(OUTPUT, result)
    print(json.dumps({
        "selected": selected_name,
        "candidates": {
            name: {metric: value for metric, value in item["metrics"].items() if metric != "per_class"}
            for name, item in candidates.items()
        },
    }, indent=2), flush=True)


if __name__ == "__main__":
    main()
