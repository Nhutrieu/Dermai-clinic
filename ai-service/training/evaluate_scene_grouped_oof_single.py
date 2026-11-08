"""Report one architecture's completed five-fold development OOF predictions."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from common import CLASSES, save_json
from evaluate_scene_grouped_oof_ensemble import (
    ARCHITECTURES, read_probabilities, score, source_score,
)
from prepare_scene_grouped_oof_folds import OUTPUT as OUTER_MANIFEST, PROJECT


def report_for(architecture: str) -> dict:
    outer = json.loads(OUTER_MANIFEST.read_text(encoding="utf-8"))
    if outer["total_images"] != 5937 or outer["fold_count"] != 5:
        raise ValueError("Unexpected OOF manifest")
    paths = [row["path"] for row in outer["images"]]
    if len(paths) != 5937 or len(set(paths)) != len(paths):
        raise ValueError("OOF image paths are incomplete or repeated")
    targets = np.asarray([CLASSES.index(row["class"]) for row in outer["images"]])
    folds = np.asarray([row["fold"] for row in outer["images"]])
    sources = np.asarray([
        "SCIN" if path.startswith("SkinDisease/scin-v1/") else "original_train"
        for path in paths
    ])
    predictions = {}
    for fold in range(5):
        expected = {row["path"]: row for row in outer["images"] if row["fold"] == fold}
        predictions.update(read_probabilities(architecture, fold, outer, expected))
    if set(predictions) != set(paths):
        raise ValueError("Five OOF folds do not cover every image")
    probabilities = np.stack([predictions[path] for path in paths])
    metrics = score(probabilities, targets)
    if sum(map(sum, metrics["confusion_matrix"])) != len(paths):
        raise ValueError("Confusion matrix does not cover every image")
    return {
        "scope": "Five-fold grouped development OOF for a single model; not an independent test of new patients.",
        "architecture": architecture,
        "outer_manifest_sha256": outer["manifest_sha256"],
        "images": len(paths),
        "folds": 5,
        "metrics": metrics,
        "per_fold": [
            {"fold": fold, "images": int((folds == fold).sum()),
             "metrics": score(probabilities[folds == fold], targets[folds == fold])}
            for fold in range(5)
        ],
        "per_source": {
            source: source_score(probabilities[sources == source], targets[sources == source])
            for source in ("original_train", "SCIN")
        },
    }


def summary(report: dict) -> str:
    def pct(value: float) -> str:
        return f"{value * 100:.2f}%"

    metrics = report["metrics"]
    matrix = metrics["confusion_matrix"]
    name = "EfficientNet-B0" if report["architecture"] == "efficientnet_b0" else "ConvNeXt-Tiny"
    lines = [
        f"# {name}: đánh giá OOF năm fold",
        "",
        f"Tập phát triển **{report['images']:,} ảnh** chia năm fold theo nhóm ca/cảnh đã biết. "
        "Mỗi dự đoán đến từ checkpoint không train và không chọn epoch trên fold chứa ảnh đó. "
        "Đây không phải bộ test bệnh nhân mới; nhiều ảnh không có mã người bệnh để xác nhận tách hoàn toàn.",
        "",
        "| Accuracy | Macro recall | Macro F1 | SkinCancer recall | Top-3 accuracy |",
        "| ---: | ---: | ---: | ---: | ---: |",
        f"| {pct(metrics['accuracy'])} | {pct(metrics['macro_recall'])} "
        f"| {pct(metrics['macro_f1'])} | {pct(metrics['per_class']['SkinCancer']['recall'])} "
        f"| {pct(metrics['top3_accuracy'])} |",
        "",
        "## Từng bệnh",
        "",
        "| Bệnh | Số ảnh | Recall | Precision | F1 |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for disease in CLASSES:
        item = metrics["per_class"][disease]
        lines.append(
            f"| {disease} | {item['support']} | {pct(item['recall'])} "
            f"| {pct(item['precision'])} | {pct(item['f1'])} |"
        )
    lines += [
        "",
        "## Ma trận nhầm lẫn",
        "",
        "Hàng là nhãn thật, cột là nhãn dự đoán.",
        "",
        "| Nhãn thật / dự đoán | " + " | ".join(CLASSES) + " |",
        "| --- | " + " | ".join("---:" for _ in CLASSES) + " |",
    ]
    for disease, counts in zip(CLASSES, matrix):
        lines.append(f"| {disease} | " + " | ".join(map(str, counts)) + " |")
    lines += [
        "",
        "## Theo fold và nguồn ảnh",
        "",
        "| Fold | Số ảnh | Accuracy | Macro F1 |",
        "| ---: | ---: | ---: | ---: |",
    ]
    for item in report["per_fold"]:
        lines.append(
            f"| {item['fold']} | {item['images']} | {pct(item['metrics']['accuracy'])} "
            f"| {pct(item['metrics']['macro_f1'])} |"
        )
    lines += [
        "",
        "| Nguồn | Số ảnh | Accuracy | Macro recall trên các lớp có ảnh |",
        "| --- | ---: | ---: | ---: |",
    ]
    for source, item in report["per_source"].items():
        lines.append(
            f"| {source} | {item['images']} | {pct(item['accuracy'])} "
            f"| {pct(item['macro_recall_present_classes'])} |"
        )
    lines += [
        "",
        "| Nguồn | Bệnh | Số ảnh | Recall |",
        "| --- | --- | ---: | ---: |",
    ]
    for source, item in report["per_source"].items():
        for disease, values in item["per_class"].items():
            lines.append(f"| {source} | {disease} | {values['images']} | {pct(values['recall'])} |")
    scin = report["per_source"]["SCIN"]
    eczema_images = scin["per_class"]["Eczema"]["images"]
    lines += [
        "",
        f"SCIN có {eczema_images}/{scin['images']} ảnh Eczema, nên accuracy của nguồn này "
        "chịu ảnh hưởng lớn từ Eczema; hãy xem cả macro recall và từng bệnh trong bảng trên.",
        "",
        "SCIN trong tập này không có ảnh SkinCancer. Chỉ số riêng SCIN vì thế không đo được lớp đó. "
        "Báo cáo so sánh OOF hai model và các phép gộp dùng cùng 5.937 ảnh. "
        "Các kết quả này hỗ trợ chọn ứng viên phát triển; cần bộ test mới để xác nhận sau khi chọn.",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--architecture", choices=ARCHITECTURES, required=True)
    args = parser.parse_args()
    stem = f"scene_grouped_oof_single_{args.architecture}_seed42"
    json_path = PROJECT / "ai-service/reports" / f"{stem}.json"
    md_path = PROJECT / "ai-service/reports" / f"{stem}.md"
    if json_path.exists() or md_path.exists():
        raise FileExistsError(f"Preserving prior single-model OOF report: {stem}")
    report = report_for(args.architecture)
    md_path.write_text(summary(report), encoding="utf-8")
    save_json(json_path, report)
    print(json.dumps({
        "architecture": args.architecture,
        "images": report["images"],
        "accuracy": report["metrics"]["accuracy"],
        "macro_f1": report["metrics"]["macro_f1"],
        "skin_cancer_recall": report["metrics"]["per_class"]["SkinCancer"]["recall"],
    }, indent=2), flush=True)


if __name__ == "__main__":
    main()
