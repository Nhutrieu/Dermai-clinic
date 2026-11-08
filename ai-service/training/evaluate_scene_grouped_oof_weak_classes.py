"""One exploratory inner-fitted follow-up for Lupus/Psoriasis; no outer fitting."""

from __future__ import annotations

import itertools
import json

import numpy as np

from common import CLASSES, save_json, sha256_file
from evaluate_scene_grouped_oof_classwise_fusion import (
    INNER_PLAN, OUTER_MANIFEST, PROJECT, aligned_inner_predictions,
    choose_class_weights, classwise_blend,
)
from evaluate_scene_grouped_oof_ensemble import (
    ARCHITECTURES, read_probabilities, score, source_score,
)

OUTPUT = PROJECT / "ai-service/reports/scene_grouped_oof_weak_classes_seed42.json"
SUMMARY = OUTPUT.with_suffix(".md")
PROTOCOL = PROJECT / "docs/59-thu-gop-uu-tien-lupus-psoriasis.md"
TARGETS = (CLASSES.index("Lupus"), CLASSES.index("Psoriasis"))
CANCER = CLASSES.index("SkinCancer")


def counts(probabilities: np.ndarray, labels: np.ndarray) -> dict:
    predicted = probabilities.argmax(axis=1)
    matrix = np.bincount(labels * len(CLASSES) + predicted, minlength=len(CLASSES)**2).reshape(len(CLASSES), -1)
    tp = matrix.diagonal().astype(float)
    support = matrix.sum(axis=1)
    predicted_count = matrix.sum(axis=0)
    precision = np.divide(tp, predicted_count, out=np.zeros_like(tp), where=predicted_count > 0)
    recall = np.divide(tp, support, out=np.zeros_like(tp), where=support > 0)
    f1 = np.divide(2 * tp, support + predicted_count, out=np.zeros_like(tp), where=support + predicted_count > 0)
    return {"precision": precision, "recall": recall, "f1": f1,
            "macro_f1": float(f1.mean()), "accuracy": float(tp.sum() / len(labels))}


def apply_rule(b0: np.ndarray, convnext: np.ndarray, weights: np.ndarray, boosts: np.ndarray) -> np.ndarray:
    combined = classwise_blend(b0, convnext, weights) * boosts[None, :]
    return combined / combined.sum(axis=1, keepdims=True)


def fit_rule(b0: np.ndarray, convnext: np.ndarray, labels: np.ndarray) -> tuple[np.ndarray, np.ndarray, dict]:
    base_weights, _ = choose_class_weights(b0, convnext, labels)
    base_boosts = np.ones(len(CLASSES))
    baseline = counts(apply_rule(b0, convnext, base_weights, base_boosts), labels)
    others = [i for i in range(len(CLASSES)) if i not in TARGETS and i != CANCER]

    def key(metrics: dict, weights: np.ndarray, boosts: np.ndarray) -> tuple:
        complexity = np.abs(weights - base_weights).sum() + np.abs(boosts - 1).sum()
        return (float(metrics["recall"][list(TARGETS)].min()),
                float(metrics["f1"][list(TARGETS)].mean()), metrics["macro_f1"],
                metrics["accuracy"], -float(complexity))

    best_weights, best_boosts = base_weights.copy(), base_boosts.copy()
    best_metrics = baseline
    best_key = key(baseline, best_weights, best_boosts)
    eligible = 0
    for left_weight, right_weight, left_boost, right_boost in itertools.product(
        (0.0, 0.25, 0.5, 0.75, 1.0), (0.0, 0.25, 0.5, 0.75, 1.0),
        (1.0, 1.1, 1.25), (1.0, 1.1, 1.25),
    ):
        weights = base_weights.copy()
        boosts = base_boosts.copy()
        weights[list(TARGETS)] = (left_weight, right_weight)
        boosts[list(TARGETS)] = (left_boost, right_boost)
        metrics = counts(apply_rule(b0, convnext, weights, boosts), labels)
        if (metrics["recall"][CANCER] + 1e-12 < baseline["recall"][CANCER]
            or (metrics["recall"][others] + 0.02 + 1e-12 < baseline["recall"][others]).any()
            or (metrics["precision"][list(TARGETS)] + 0.02 + 1e-12 < baseline["precision"][list(TARGETS)]).any()
            or metrics["macro_f1"] + 1e-12 < baseline["macro_f1"]
            or metrics["accuracy"] + 0.005 + 1e-12 < baseline["accuracy"]):
            continue
        eligible += 1
        candidate_key = key(metrics, weights, boosts)
        if candidate_key > best_key:
            best_key = candidate_key
            best_weights, best_boosts, best_metrics = weights, boosts, metrics
    return best_weights, best_boosts, {
        "eligible_grid_candidates": eligible,
        "convnext_weights": dict(zip(CLASSES, best_weights.tolist())),
        "score_multipliers": dict(zip(CLASSES, best_boosts.tolist())),
        "inner_baseline": {k: v.tolist() if isinstance(v, np.ndarray) else v for k, v in baseline.items()},
        "inner_selected": {k: v.tolist() if isinstance(v, np.ndarray) else v for k, v in best_metrics.items()},
    }


def summary(report: dict) -> str:
    pct = lambda x: f"{100*x:.2f}%"
    lines = ["# Kiểm tra bổ sung cho Lupus và Psoriasis", "",
        "Thí nghiệm được đề xuất sau khi đã xem OOF. Mỗi fold chỉ chọn cấu hình bằng inner validation; "
        "điểm outer vẫn là dữ liệu phát triển đã xem, không phải xác nhận trên test mới.", "",
        "| Phương án | Accuracy | Macro F1 | Lupus recall | Lupus precision | Psoriasis recall | Psoriasis precision | SkinCancer recall |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for name, m in report["methods"].items():
        p = m["per_class"]
        lines.append(f"| {name} | {pct(m['accuracy'])} | {pct(m['macro_f1'])} | "
            f"{pct(p['Lupus']['recall'])} | {pct(p['Lupus']['precision'])} | "
            f"{pct(p['Psoriasis']['recall'])} | {pct(p['Psoriasis']['precision'])} | {pct(p['SkinCancer']['recall'])} |")
    lines += ["", "## Từng bệnh", "",
        "| Bệnh | Ảnh | Recall cũ | Recall thử | Precision cũ | Precision thử | F1 cũ | F1 thử | Sửa đúng | Đổi sai |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
    base = report["methods"]["classwise_baseline"]
    trial = report["methods"]["weak_class_trial"]
    for name in CLASSES:
        a, b = base["per_class"][name], trial["per_class"][name]
        pair = report["paired_per_class"][name]
        lines.append(f"| {name} | {a['support']} | {pct(a['recall'])} | {pct(b['recall'])} | "
            f"{pct(a['precision'])} | {pct(b['precision'])} | {pct(a['f1'])} | {pct(b['f1'])} | "
            f"{pair['corrected']} | {pair['lost']} |")
    lines += ["", "## Theo nguồn", "",
        "| Nguồn | Bệnh | Số ảnh | Recall cũ | Recall thử |",
        "| --- | --- | ---: | ---: | ---: |"]
    for source in ("original_train", "SCIN"):
        for name in ("Lupus", "Psoriasis"):
            a, b = [report["methods"][m]["per_source"][source]["per_class"][name]
                    for m in ("classwise_baseline", "weak_class_trial")]
            lines.append(f"| {source} | {name} | {a['images']} | {pct(a['recall'])} | {pct(b['recall'])} |")
    lines += ["", "## Lỗi của hai model ban đầu", "",
        "Không thể chọn đúng bằng cách chỉ chọn nhãn argmax của B0 hoặc ConvNeXt khi cả hai cùng sai. "
        "Điểm này không phải giới hạn của mọi cách gộp xác suất hoặc mô hình mới.", ""]
    for name, d in report["diagnosis"].items():
        lines.append(f"- {name}: cả hai cùng sai {d['both_wrong']}/{d['images']} ảnh. "
            f"Bản gộp cũ nhầm nhiều nhất sang: " + "; ".join(f"{k}: {v} ảnh" for k, v in d['baseline_errors'].items()) + ".")
    for method in ("classwise_baseline", "weak_class_trial"):
        lines += ["", f"## Confusion matrix: {method}", "",
            "| Nhãn thật / dự đoán | " + " | ".join(CLASSES) + " |",
            "| --- | " + " | ".join("---:" for _ in CLASSES) + " |"]
        for name, row in zip(CLASSES, report["methods"][method]["confusion_matrix"]):
            lines.append("| " + name + " | " + " | ".join(map(str, row)) + " |")
    lines += ["", "## Kết luận theo tiêu chí bổ sung", "", report["decision"]["reason"], "",
        "Hệ số điểm làm thay đổi xác suất và có thể làm calibration kém hơn; chưa hiệu chỉnh lại, "
        "không diễn giải các điểm đó như xác suất lâm sàng đã xác nhận. Không thay checkpoint hoặc bảng Excel kết quả cũ.", ""]
    return "\n".join(lines)


def main() -> None:
    if OUTPUT.exists() or SUMMARY.exists():
        raise FileExistsError("Preserving completed weak-class experiment")
    outer = json.loads(OUTER_MANIFEST.read_text(encoding="utf-8"))
    inner = json.loads(INNER_PLAN.read_text(encoding="utf-8"))
    if inner["outer_manifest_sha256"] != outer["manifest_sha256"]:
        raise ValueError("Manifest identity differs")
    rows = outer["images"]
    paths = [r["path"] for r in rows]
    targets = np.array([CLASSES.index(r["class"]) for r in rows])
    folds = np.array([r["fold"] for r in rows])
    sources = np.array(["SCIN" if p.startswith("SkinDisease/scin-v1/") else "original_train" for p in paths])
    by_arch = {}
    for architecture in ARCHITECTURES:
        predictions = {}
        for fold in range(5):
            expected = {r["path"]: r for r in rows if r["fold"] == fold}
            predictions.update(read_probabilities(architecture, fold, outer, expected))
        if set(predictions) != set(paths):
            raise ValueError("Outer prediction coverage differs")
        by_arch[architecture] = np.stack([predictions[p] for p in paths])
    b0, convnext = by_arch["efficientnet_b0"], by_arch["convnext_tiny"]
    baseline, trial = np.empty_like(b0), np.empty_like(b0)
    fold_reports = []
    for fold in range(5):
        a, labels = aligned_inner_predictions("efficientnet_b0", fold, outer, inner)
        b, comparison_labels = aligned_inner_predictions("convnext_tiny", fold, outer, inner)
        if not np.array_equal(labels, comparison_labels):
            raise ValueError("Inner labels differ")
        baseline_weights, _ = choose_class_weights(a, b, labels)
        weights, boosts, detail = fit_rule(a, b, labels)
        mask = folds == fold
        baseline[mask] = classwise_blend(b0[mask], convnext[mask], baseline_weights)
        trial[mask] = apply_rule(b0[mask], convnext[mask], weights, boosts)
        fold_reports.append({"fold": fold, **detail,
            "outer_baseline": score(baseline[mask], targets[mask]),
            "outer_trial": score(trial[mask], targets[mask])})
    probabilities = {"convnext_tiny": convnext, "classwise_baseline": baseline, "weak_class_trial": trial}
    methods = {name: score(p, targets) | {"per_source": {
        source: source_score(p[sources == source], targets[sources == source])
        for source in ("original_train", "SCIN")}}
        for name, p in probabilities.items()}
    old = json.loads((PROJECT / "ai-service/reports/scene_grouped_oof_classwise_fusion_seed42.json").read_text(encoding="utf-8"))
    if methods["classwise_baseline"]["confusion_matrix"] != old["methods"]["classwise_inner_fitted"]["confusion_matrix"]:
        raise ValueError("Reproduced baseline differs from completed result")
    predicted_base, predicted_trial = baseline.argmax(axis=1), trial.argmax(axis=1)
    pairs, diagnosis = {}, {}
    for i, name in enumerate(CLASSES):
        mask = targets == i
        corrected = int((mask & (predicted_trial == targets) & (predicted_base != targets)).sum())
        lost = int((mask & (predicted_trial != targets) & (predicted_base == targets)).sum())
        pairs[name] = {"corrected": corrected, "lost": lost, "net": corrected - lost}
        if i in TARGETS:
            error_counts = methods["classwise_baseline"]["confusion_matrix"][i]
            errors = sorted(((CLASSES[j], c) for j, c in enumerate(error_counts) if j != i and c), key=lambda x: -x[1])
            diagnosis[name] = {"images": int(mask.sum()),
                "both_wrong": int((mask & (b0.argmax(axis=1) != targets) & (convnext.argmax(axis=1) != targets)).sum()),
                "baseline_errors": dict(errors)}
    base, candidate = methods["classwise_baseline"], methods["weak_class_trial"]
    passed = (all(candidate["per_class"][CLASSES[i]]["recall"] > base["per_class"][CLASSES[i]]["recall"] for i in TARGETS)
              and candidate["per_class"]["SkinCancer"]["recall"] >= base["per_class"]["SkinCancer"]["recall"]
              and candidate["macro_f1"] >= base["macro_f1"])
    report = {"scope": "Adaptive development follow-up after inspecting OOF; not a new independent test.",
        "images": len(rows), "protocol_sha256": sha256_file(PROTOCOL),
        "outer_manifest_sha256": outer["manifest_sha256"], "inner_plan_sha256": sha256_file(INNER_PLAN),
        "grid_candidates_per_fold": 225, "folds": fold_reports, "methods": methods,
        "paired_per_class": pairs, "diagnosis": diagnosis,
        "decision": {"meets_followup_criteria": passed,
            "reason": "Nhánh thử tăng recall cả hai bệnh, giữ recall SkinCancer và macro F1 so với bản cũ; chỉ là ứng viên phát triển cần kiểm tra nguồn mới."
                if passed else "Nhánh thử chưa đồng thời tăng recall cả Lupus/Psoriasis, giữ recall SkinCancer và macro F1. Giữ bản gộp cũ làm ứng viên; chưa có căn cứ thay bằng nhánh thử."}}
    save_json(OUTPUT, report)
    SUMMARY.write_text(summary(report), encoding="utf-8")
    print(json.dumps({"decision": report["decision"], "diagnosis": diagnosis,
        "methods": {name: {"accuracy": m["accuracy"], "macro_f1": m["macro_f1"],
            "targets": {d: m["per_class"][d] for d in ("Lupus", "Psoriasis", "SkinCancer")}}
            for name, m in methods.items()}}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
