"""Evaluate conservative class-wise B0/ConvNeXt fusion on outer OOF folds.

Each fold's eight weights are chosen only from that fold's inner-validation
predictions, then applied unchanged to its separate outer-fold predictions.
The pooled result is development evidence, not an independent patient test.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np

from common import CLASSES, save_json, sha256_file
from evaluate_scene_grouped_oof_ensemble import (
    ARCHITECTURES, OUTPUT as FIXED_OUTPUT, RUN_ROOT, paired_cluster_interval,
    read_probabilities, score, source_score,
)
from prepare_scene_grouped_oof_folds import OUTPUT as OUTER_MANIFEST, PROJECT
from prepare_scene_grouped_oof_inner_splits import OUTPUT as INNER_PLAN


OUTPUT = PROJECT / "ai-service/reports/scene_grouped_oof_classwise_fusion_seed42.json"
SUMMARY = PROJECT / "ai-service/reports/scene_grouped_oof_classwise_fusion_seed42.md"


def aligned_inner_predictions(
    architecture: str, fold: int, outer: dict, inner: dict,
) -> tuple[np.ndarray, np.ndarray]:
    directory = RUN_ROOT / ARCHITECTURES[architecture].format(fold=fold)
    payload = json.loads((directory / "inner_predictions.json").read_text(encoding="utf-8"))
    checkpoint = directory / "best_model.pth"
    identity = {
        "role": "inner_validation_for_classwise_fusion_only",
        "architecture": architecture,
        "outer_fold": fold,
        "outer_manifest_sha256": outer["manifest_sha256"],
        "inner_plan_sha256": sha256_file(INNER_PLAN),
        "checkpoint_sha256": sha256_file(checkpoint),
        "classes": CLASSES,
    }
    if any(payload.get(key) != value for key, value in identity.items()):
        raise ValueError(f"Inner prediction provenance differs: {directory}")
    plan = inner["folds"][fold]
    if plan["outer_fold"] != fold:
        raise ValueError("Inner plan fold order changed")
    paths = plan["inner_validation_paths"]
    by_path = {row["path"]: row for row in outer["images"]}
    if len(payload["rows"]) != len(paths) or len(paths) != len(set(paths)):
        raise ValueError(f"Inner prediction count differs: {directory}")
    probabilities = []
    targets = []
    for path, item in zip(paths, payload["rows"]):
        expected = by_path[path]
        if (
            item["path"] != path or item["sha256"] != expected["sha256"]
            or item["class"] != expected["class"] or expected["fold"] == fold
        ):
            raise ValueError(f"Inner image identity differs: {path}")
        vector = np.asarray(item["probabilities"], dtype=float)
        if (
            vector.shape != (len(CLASSES),) or not np.isfinite(vector).all()
            or (vector < 0).any() or abs(float(vector.sum()) - 1.0) > 1e-4
        ):
            raise ValueError(f"Invalid inner probability vector: {path}")
        probabilities.append(vector)
        targets.append(CLASSES.index(item["class"]))
    return np.stack(probabilities), np.asarray(targets, dtype=int)


def choose_class_weights(
    b0: np.ndarray, convnext: np.ndarray, targets: np.ndarray,
) -> tuple[np.ndarray, dict]:
    """Use only clear paired recall advantages; otherwise keep 50:50."""
    if b0.shape != convnext.shape or b0.shape != (len(targets), len(CLASSES)):
        raise ValueError("Inner prediction shapes differ")
    b0_correct = b0.argmax(axis=1) == targets
    convnext_correct = convnext.argmax(axis=1) == targets
    weights = np.full(len(CLASSES), 0.5, dtype=float)
    details = {}
    for index, name in enumerate(CLASSES):
        matching = targets == index
        support = int(matching.sum())
        if support == 0:
            raise ValueError(f"No inner-validation images for {name}")
        b0_only = int((matching & b0_correct & ~convnext_correct).sum())
        convnext_only = int((matching & convnext_correct & ~b0_correct).sum())
        advantage = convnext_only - b0_only
        threshold = max(3, math.ceil(0.05 * support))
        if advantage >= threshold:
            weights[index] = 0.75
        elif advantage <= -threshold:
            weights[index] = 0.25
        details[name] = {
            "inner_support": support,
            "b0_only_correct": b0_only,
            "convnext_only_correct": convnext_only,
            "advantage_convnext_images": advantage,
            "minimum_advantage_for_tilt": threshold,
            "convnext_weight": float(weights[index]),
        }
    return weights, details


def classwise_blend(b0: np.ndarray, convnext: np.ndarray, weights: np.ndarray) -> np.ndarray:
    if b0.shape != convnext.shape or b0.shape[1] != len(CLASSES) or weights.shape != (len(CLASSES),):
        raise ValueError("Blend shapes differ")
    if not np.isfinite(weights).all() or (weights < 0).any() or (weights > 1).any():
        raise ValueError("Invalid class weights")
    combined = (1 - weights[None, :]) * b0 + weights[None, :] * convnext
    return combined / combined.sum(axis=1, keepdims=True)


def paired(selected: np.ndarray, baseline: np.ndarray, targets: np.ndarray, groups: list[str]) -> dict:
    selected_correct = selected.argmax(axis=1) == targets
    baseline_correct = baseline.argmax(axis=1) == targets
    return {
        "classwise_correct_baseline_wrong": int((selected_correct & ~baseline_correct).sum()),
        "baseline_correct_classwise_wrong": int((~selected_correct & baseline_correct).sum()),
        "accuracy_difference": float(selected_correct.mean() - baseline_correct.mean()),
        "paired_bootstrap_95pct_interval": paired_cluster_interval(
            selected_correct, baseline_correct, groups,
        ),
        "bootstrap_unit": "known_case_or_scene_group_otherwise_image",
        "bootstrap_repetitions": 3000,
    }


def write_summary(report: dict) -> None:
    def pct(value: float) -> str:
        return f"{value * 100:.2f}%"

    display_name = {
        "efficientnet_b0": "EfficientNet-B0",
        "convnext_tiny": "ConvNeXt-Tiny",
        "equal_50_50": "Gộp đều 50:50",
        "selected_fixed_weight": "Trọng số cố định được chọn",
        "classwise_inner_fitted": "Gộp theo từng bệnh",
    }
    lines = [
        "# Thử gộp B0 và ConvNeXt theo từng bệnh",
        "",
        "Mỗi fold chọn tám trọng số bằng ảnh inner validation, rồi áp dụng lên ảnh outer fold "
        "mà bước chọn trọng số chưa xem nhãn. Đây là đánh giá phát triển; không phải test độc lập mới.",
        "",
        "| Phương án | Accuracy | Macro recall | Macro F1 | SkinCancer recall |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for name, item in report["methods"].items():
        lines.append(
            f"| {display_name[name]} | {pct(item['accuracy'])} | {pct(item['macro_recall'])} "
            f"| {pct(item['macro_f1'])} | {pct(item['per_class']['SkinCancer']['recall'])} |"
        )
    recommendation = report["development_recommendation"]
    fixed_weight = report["fixed_weight_selected_on_same_oof"]["convnext_weight"]
    lines += [
        "",
        f"**Đề xuất để kiểm thử độc lập:** {display_name[recommendation['method']]}. "
        "Quy tắc: recall SkinCancer không thấp hơn model đơn tốt nhất, "
        "rồi so macro recall, macro F1 và accuracy. "
        f"Phương án cố định dùng {fixed_weight:.2f} trọng số ConvNeXt và đã được chọn trên chính OOF, "
        "nên đây chỉ là đề xuất phát triển.",
    ]
    lines += [
        "",
        "| Phương án | Train gốc accuracy | SCIN accuracy | Train gốc macro recall | SCIN macro recall trên lớp có ảnh |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for name, item in report["methods"].items():
        original = item["per_source"]["original_train"]
        scin = item["per_source"]["SCIN"]
        lines.append(
            f"| {display_name[name]} | {pct(original['accuracy'])} | {pct(scin['accuracy'])} "
            f"| {pct(original['macro_recall_present_classes'])} "
            f"| {pct(scin['macro_recall_present_classes'])} |"
        )
    lines += [
        "",
        "## Recall từng bệnh theo nguồn ảnh",
        "",
        "| Nguồn | Bệnh | Số ảnh | B0 | ConvNeXt | 50:50 | Trọng số cố định | Theo bệnh |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for source in ("original_train", "SCIN"):
        reference = report["methods"]["efficientnet_b0"]["per_source"][source]["per_class"]
        for disease in CLASSES:
            if disease not in reference:
                continue
            support = reference[disease]["images"]
            recalls = []
            for method in (
                "efficientnet_b0", "convnext_tiny", "equal_50_50",
                "selected_fixed_weight", "classwise_inner_fitted",
            ):
                item = report["methods"][method]["per_source"][source]["per_class"][disease]
                if item["images"] != support:
                    raise ValueError(f"Source/class support differs: {source}/{disease}")
                recalls.append(pct(item["recall"]))
            lines.append(f"| {source} | {disease} | {support} | " + " | ".join(recalls) + " |")
    lines += [
        "",
        "## Chỉ số riêng của từng bệnh trên cùng 5.937 ảnh OOF",
        "",
        "| Bệnh | Số ảnh | B0 recall | ConvNeXt recall | 50:50 recall | Theo bệnh recall | B0 F1 | ConvNeXt F1 | 50:50 F1 | Theo bệnh F1 |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    methods = report["methods"]
    for disease in CLASSES:
        b0 = methods["efficientnet_b0"]["per_class"][disease]
        convnext = methods["convnext_tiny"]["per_class"][disease]
        equal = methods["equal_50_50"]["per_class"][disease]
        classwise = methods["classwise_inner_fitted"]["per_class"][disease]
        lines.append(
            f"| {disease} | {b0['support']} | {pct(b0['recall'])} | {pct(convnext['recall'])} "
            f"| {pct(equal['recall'])} | {pct(classwise['recall'])} | {pct(b0['f1'])} "
            f"| {pct(convnext['f1'])} | {pct(equal['f1'])} | {pct(classwise['f1'])} |"
        )
    recall_regressions = [
        f"{disease} ({pct(methods['convnext_tiny']['per_class'][disease]['recall'])} "
        f"xuống {pct(methods['classwise_inner_fitted']['per_class'][disease]['recall'])})"
        for disease in CLASSES
        if methods["classwise_inner_fitted"]["per_class"][disease]["recall"]
        < methods["convnext_tiny"]["per_class"][disease]["recall"] - 1e-12
    ]
    if recall_regressions:
        lines += ["", "Recall của cách gộp theo bệnh thấp hơn ConvNeXt đơn ở: " + "; ".join(recall_regressions) + "."]
    lines += [
        "",
        "## Ảnh sửa đúng và làm sai theo từng bệnh so với trọng số cố định",
        "",
        "| Bệnh thật | Số ảnh | Gộp theo bệnh sửa đúng | Gộp theo bệnh làm sai | Chênh số ảnh đúng |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for disease, item in report["paired_per_class_against_fixed"].items():
        lines.append(
            f"| {disease} | {item['images']} | {item['classwise_correct_fixed_wrong']} "
            f"| {item['fixed_correct_classwise_wrong']} | {item['net_correct']} |"
        )
    lines += [
        "",
        "## Ma trận nhầm lẫn của từng phương án",
        "",
        "Hàng là nhãn thật, cột là nhãn dự đoán; thứ tự lớp giống nhau ở cả bốn bảng.",
        "",
    ]
    for name, item in methods.items():
        matrix = item["confusion_matrix"]
        if len(matrix) != len(CLASSES) or any(len(row) != len(CLASSES) for row in matrix):
            raise ValueError(f"Invalid confusion matrix: {name}")
        lines.extend([
            f"### {display_name[name]}",
            "",
            "| Nhãn thật \\ dự đoán | " + " | ".join(CLASSES) + " |",
            "| --- | " + " | ".join("---:" for _ in CLASSES) + " |",
        ])
        for disease, counts in zip(CLASSES, matrix):
            lines.append(f"| {disease} | " + " | ".join(str(value) for value in counts) + " |")
        lines.append("")
    lines += [
        "",
        "Quy tắc đã khóa: ở mỗi bệnh, nếu ConvNeXt nhận đúng hơn B0 ít nhất "
        "`max(3, ceil(5% số ảnh của bệnh))` ảnh trên inner validation thì đặt trọng số ConvNeXt 0,75; "
        "nếu B0 hơn mức đó thì đặt 0,25; còn lại 0,50. Cả tám điểm được chuẩn hóa về tổng 1 trước khi chọn nhãn.",
        "",
        "| Bệnh | Trọng số ConvNeXt ở fold 0 | Fold 1 | Fold 2 | Fold 3 | Fold 4 |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for disease in CLASSES:
        values = [fold["weights"][disease]["convnext_weight"] for fold in report["folds"]]
        lines.append(f"| {disease} | " + " | ".join(f"{value:.2f}" for value in values) + " |")
    lines += [
        "",
        "## Bộ trọng số đề xuất để kiểm thử lần sau",
        "",
        "Sau khi đã chấm outer fold, quy tắc tương tự được áp dụng lên toàn bộ dự đoán OOF "
        "để đề xuất một bộ tám trọng số cho mô hình cuối. **Không chấm bộ trọng số này "
        "trên chính OOF rồi gọi đó là điểm kiểm thử**; cần mô hình huấn luyện cuối và bộ test mới.",
        "",
        "| Bệnh | B0 chỉ mình đúng | ConvNeXt chỉ mình đúng | Trọng số ConvNeXt đề xuất |",
        "| --- | ---: | ---: | ---: |",
    ]
    for disease, item in report["pooled_oof_proposed_weights"].items():
        lines.append(
            f"| {disease} | {item['b0_only_correct']} | {item['convnext_only_correct']} "
            f"| {item['convnext_weight']:.2f} |"
        )
    lines += [
        "",
        "## Đổi đúng/sai so với model đơn và các cách gộp",
        "",
    ]
    for baseline_name in ("efficientnet_b0", "convnext_tiny", "equal_50_50", "selected_fixed_weight"):
        comparison = report["paired_against"][baseline_name]
        lower, upper = comparison["paired_bootstrap_95pct_interval"]
        lines.append(
            f"So với {display_name[baseline_name]}, cách theo bệnh sửa đúng "
            f"**{comparison['classwise_correct_baseline_wrong']}** ảnh và làm sai "
            f"**{comparison['baseline_correct_classwise_wrong']}** ảnh. "
            f"Chênh accuracy {pct(comparison['accuracy_difference'])}; "
            f"khoảng bootstrap theo nhóm ca/cảnh [{pct(lower)}; {pct(upper)}]."
        )
    lines += [
        "",
        "Khoảng bootstrap chỉ mô tả biến thiên trong tập phát triển. Nhiều ảnh chưa có mã bệnh nhân; "
        "công thức train hai model cũng từng được nghiên cứu trên nguồn này. "
        "Phải đo trên bộ test mới đủ tám bệnh và tách bệnh nhân trước khi kết luận cải thiện thực tế.",
        "SCIN trong tập này không có ảnh SkinCancer, nên chỉ số riêng SCIN không đo được bệnh đó.",
        "",
    ]
    SUMMARY.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    if OUTPUT.exists() or SUMMARY.exists():
        raise FileExistsError(f"Preserving prior class-wise OOF comparison: {OUTPUT} / {SUMMARY}")
    outer = json.loads(OUTER_MANIFEST.read_text(encoding="utf-8"))
    inner = json.loads(INNER_PLAN.read_text(encoding="utf-8"))
    if (
        inner["outer_manifest_sha256"] != outer["manifest_sha256"]
        or len(outer["images"]) != 5937 or len(inner["folds"]) != 5
    ):
        raise ValueError("OOF manifests differ from locked plan")
    paths = [row["path"] for row in outer["images"]]
    targets = np.asarray([CLASSES.index(row["class"]) for row in outer["images"]], dtype=int)
    groups = [row["scene_or_case_group"] for row in outer["images"]]
    folds = np.asarray([row["fold"] for row in outer["images"]], dtype=int)
    sources = np.asarray([
        "SCIN" if row["path"].startswith("SkinDisease/scin-v1/") else "original_train"
        for row in outer["images"]
    ])
    by_architecture = {}
    for architecture in ARCHITECTURES:
        predictions = {}
        for fold in range(5):
            expected = {row["path"]: row for row in outer["images"] if row["fold"] == fold}
            predictions.update(read_probabilities(architecture, fold, outer, expected))
        if set(predictions) != set(paths):
            raise ValueError(f"Missing outer predictions for {architecture}")
        by_architecture[architecture] = np.stack([predictions[path] for path in paths])
    b0 = by_architecture["efficientnet_b0"]
    convnext = by_architecture["convnext_tiny"]
    fixed_report = json.loads(FIXED_OUTPUT.read_text(encoding="utf-8"))
    if fixed_report["outer_manifest_sha256"] != outer["manifest_sha256"] or fixed_report["images"] != len(paths):
        raise ValueError("Fixed-weight comparison differs from class-wise OOF manifest")
    fixed_name = fixed_report["selected"]
    fixed_weight = float(fixed_report["candidates"][fixed_name]["convnext_weight"])
    if fixed_weight not in (0.0, 0.25, 0.5, 0.75, 1.0):
        raise ValueError("Unexpected selected fixed weight")
    selected_fixed = (1 - fixed_weight) * b0 + fixed_weight * convnext
    classwise = np.empty_like(b0)
    fold_reports = []
    for fold in range(5):
        b0_inner, inner_targets = aligned_inner_predictions("efficientnet_b0", fold, outer, inner)
        convnext_inner, comparison_targets = aligned_inner_predictions("convnext_tiny", fold, outer, inner)
        if not np.array_equal(inner_targets, comparison_targets):
            raise ValueError(f"Inner labels differ between models on fold {fold}")
        weights, details = choose_class_weights(b0_inner, convnext_inner, inner_targets)
        mask = folds == fold
        classwise[mask] = classwise_blend(b0[mask], convnext[mask], weights)
        fold_reports.append({
            "fold": fold,
            "outer_images": int(mask.sum()),
            "weights": details,
            "outer_classwise": score(classwise[mask], targets[mask]),
            "outer_equal_50_50": score((b0[mask] + convnext[mask]) / 2, targets[mask]),
        })
    equal = (b0 + convnext) / 2
    _, pooled_weights = choose_class_weights(b0, convnext, targets)
    method_probabilities = {
        "efficientnet_b0": b0,
        "convnext_tiny": convnext,
        "equal_50_50": equal,
        "selected_fixed_weight": selected_fixed,
        "classwise_inner_fitted": classwise,
    }
    methods = {
        name: score(probabilities, targets) | {
            "per_source": {
                source: source_score(probabilities[sources == source], targets[sources == source])
                for source in ("original_train", "SCIN")
            }
        }
        for name, probabilities in method_probabilities.items()
    }
    fixed_metrics = fixed_report["candidates"][fixed_name]["metrics"]
    for metric in ("accuracy", "macro_recall", "macro_f1"):
        if abs(methods["selected_fixed_weight"][metric] - fixed_metrics[metric]) > 1e-12:
            raise ValueError(f"Selected fixed-weight {metric} differs from locked report")
    if methods["selected_fixed_weight"]["confusion_matrix"] != fixed_metrics["confusion_matrix"]:
        raise ValueError("Selected fixed-weight confusion matrix differs from locked report")
    cancer_floor = max(
        methods[name]["per_class"]["SkinCancer"]["recall"]
        for name in ("efficientnet_b0", "convnext_tiny")
    )
    eligible = [
        name for name in ("selected_fixed_weight", "classwise_inner_fitted")
        if methods[name]["per_class"]["SkinCancer"]["recall"] + 1e-12 >= cancer_floor
    ]
    recommended = max(
        eligible,
        key=lambda name: (
            methods[name]["macro_recall"], methods[name]["macro_f1"],
            methods[name]["accuracy"], name == "selected_fixed_weight",
        ),
    )
    classwise_correct = classwise.argmax(axis=1) == targets
    fixed_correct = selected_fixed.argmax(axis=1) == targets
    paired_per_class = {}
    for index, disease in enumerate(CLASSES):
        matching = targets == index
        corrected = int((matching & classwise_correct & ~fixed_correct).sum())
        lost = int((matching & ~classwise_correct & fixed_correct).sum())
        paired_per_class[disease] = {
            "images": int(matching.sum()),
            "classwise_correct_fixed_wrong": corrected,
            "fixed_correct_classwise_wrong": lost,
            "net_correct": corrected - lost,
        }
    report = {
        "scope": "Class-wise weights selected from each fold's inner validation and evaluated on its outer OOF; development evidence only.",
        "images": len(paths),
        "outer_manifest_sha256": outer["manifest_sha256"],
        "inner_plan_sha256": sha256_file(INNER_PLAN),
        "rule": "For each class, ConvNeXt weight 0.75 if paired correct-count advantage >= max(3, ceil(0.05*class support)); 0.25 if B0 advantage reaches threshold; otherwise 0.50. Normalize row probabilities.",
        "folds": fold_reports,
        "pooled_oof_proposed_weights": pooled_weights,
        "fixed_weight_selected_on_same_oof": {"name": fixed_name, "convnext_weight": fixed_weight},
        "development_recommendation": {
            "method": recommended,
            "eligible_methods": eligible,
            "cancer_recall_floor": cancer_floor,
            "rule": "Require SkinCancer recall at least best single OOF model, then macro recall, macro F1, accuracy; fixed weight wins an exact tie.",
            "scope": "Development choice only; requires new independent eight-class test before deployment.",
        },
        "methods": methods,
        "paired_per_class_against_fixed": paired_per_class,
        "paired_against": {
            "efficientnet_b0": paired(classwise, b0, targets, groups),
            "convnext_tiny": paired(classwise, convnext, targets, groups),
            "equal_50_50": paired(classwise, equal, targets, groups),
            "selected_fixed_weight": paired(classwise, selected_fixed, targets, groups),
        },
    }
    write_summary(report)
    save_json(OUTPUT, report)
    print(json.dumps({
        "development_recommendation": report["development_recommendation"],
        "classwise": {key: methods["classwise_inner_fitted"][key] for key in ("accuracy", "macro_recall", "macro_f1")},
        "equal_50_50": {key: methods["equal_50_50"][key] for key in ("accuracy", "macro_recall", "macro_f1")},
        "paired_against_equal": report["paired_against"]["equal_50_50"],
    }, indent=2), flush=True)


if __name__ == "__main__":
    main()
