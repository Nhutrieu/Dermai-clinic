import csv
import hashlib
import json
import sys
from pathlib import Path

import pytest
import torch
from PIL import Image


TRAINING_DIR = Path(__file__).resolve().parents[1] / "training"
sys.path.insert(0, str(TRAINING_DIR))

import evaluate_new_ensemble_holdout as holdout  # noqa: E402
from common import CLASSES  # noqa: E402
from evaluate_new_ensemble_holdout import historical_hashes, read_new_samples  # noqa: E402


def write_labels(path: Path, image_path: str) -> None:
    with path.open("w", encoding="utf-8", newline="") as destination:
        writer = csv.DictWriter(
            destination,
            fieldnames=["image_path", "label", "case_id", "source", "label_reviewer"],
        )
        writer.writeheader()
        writer.writerow({
            "image_path": image_path,
            "label": "Acne",
            "case_id": "case-1",
            "source": "new-clinic",
            "label_reviewer": "reviewer-1",
        })


def test_new_holdout_detects_exact_overlap_with_historical_data(tmp_path):
    images = tmp_path / "new"
    images.mkdir()
    image = images / "one.png"
    Image.new("RGB", (16, 16), color="red").save(image)
    labels = tmp_path / "labels.csv"
    write_labels(labels, image.name)
    samples, metadata = read_new_samples(images, labels)

    historical = tmp_path / "historical"
    for split in ("train", "test", "scin-v1/train", "scin-v1/external_test"):
        (historical / split).mkdir(parents=True)
    (historical / "train" / "copy.png").write_bytes(image.read_bytes())

    assert {sample.digest for sample in samples} & historical_hashes(historical)
    assert metadata["sources"] == {"new-clinic": 1}


def test_new_holdout_rejects_path_outside_images_root(tmp_path):
    images = tmp_path / "new"
    images.mkdir()
    outside = tmp_path / "outside.png"
    Image.new("RGB", (16, 16), color="red").save(outside)
    labels = tmp_path / "labels.csv"
    write_labels(labels, "../outside.png")

    with pytest.raises(ValueError, match="Đường dẫn ảnh"):
        read_new_samples(images, labels)


def make_eight_class_fixture(tmp_path: Path):
    images = tmp_path / "images"
    images.mkdir()
    labels = tmp_path / "labels.csv"
    with labels.open("w", encoding="utf-8", newline="") as destination:
        writer = csv.DictWriter(destination, fieldnames=["image_path", "label", "case_id", "source", "label_reviewer"])
        writer.writeheader()
        for index, label in enumerate(CLASSES):
            name = f"case_{index}.png"
            Image.new("RGB", (16, 16), color=(index * 20, index * 13, 255 - index * 17)).save(images / name)
            writer.writerow({"image_path": name, "label": label, "case_id": f"case-{index}", "source": "fixture", "label_reviewer": "doctor-code"})
    known = tmp_path / "known"
    for split in ("train", "test", "scin-v1/train", "scin-v1/external_test"):
        (known / split).mkdir(parents=True)
    for source in holdout.PRIOR_INSPECTED_SOURCE_DIRS:
        (known / "sources" / source).mkdir(parents=True)
    Image.new("RGB", (16, 16), color=(255, 255, 255)).save(known / "train" / "known.png")
    return images, labels, known


def test_audit_only_validates_eight_classes_without_model_inference(tmp_path, monkeypatch):
    images, labels, known = make_eight_class_fixture(tmp_path)
    output = tmp_path / "audit.json"
    monkeypatch.setattr(sys, "argv", [
        "evaluate_new_ensemble_holdout.py", "--images-root", str(images),
        "--labels-csv", str(labels), "--known-data-root", str(known),
        "--output", str(output), "--min-per-class", "1", "--audit-only",
    ])
    monkeypatch.setattr(holdout, "model_probabilities", lambda *args, **kwargs: pytest.fail("model inference in audit-only mode"))

    holdout.main()
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["mode"] == "audit_only"
    assert report["model_inference_performed"] is False
    assert report["dataset"]["images"] == 8
    assert all(count == 1 for count in report["dataset"]["cases_per_class"].values())
    assert report["dataset"]["labels_csv_sha256"]
    assert report["dataset"]["ordered_dataset_fingerprint_sha256"]
    assert all(not Path(item["new_image_path"]).is_absolute() for item in report["independence_checks"]["potential_dhash_near_duplicates_for_manual_review"])


def test_new_holdout_rejects_images_from_previously_inspected_source(tmp_path, monkeypatch):
    images, labels, known = make_eight_class_fixture(tmp_path)
    reused = images / "case_0.png"
    inspected = tmp_path / "inspected.json"
    inspected.write_text(json.dumps({
        "source": "prior-exploratory-set",
        "image_count": 1,
        "fingerprints": [{
            "image_id": reused.name,
            "sha256": hashlib.sha256(reused.read_bytes()).hexdigest(),
            "dhash64": "0000000000000000",
        }],
    }), encoding="utf-8")
    monkeypatch.setattr(sys, "argv", [
        "evaluate_new_ensemble_holdout.py", "--images-root", str(images),
        "--labels-csv", str(labels), "--known-data-root", str(known),
        "--inspected-fingerprints", str(inspected),
        "--output", str(tmp_path / "audit.json"), "--min-per-class", "1", "--audit-only",
    ])

    with pytest.raises(ValueError, match="nguồn đã đánh giá trước"):
        holdout.main()


def test_new_holdout_rejects_reused_image_from_prior_external_source(tmp_path, monkeypatch):
    images, labels, known = make_eight_class_fixture(tmp_path)
    reused = images / "case_0.png"
    prior_source = known / "sources" / "med_node_2015" / "prior.png"
    prior_source.write_bytes(reused.read_bytes())
    monkeypatch.setattr(sys, "argv", [
        "evaluate_new_ensemble_holdout.py", "--images-root", str(images),
        "--labels-csv", str(labels), "--known-data-root", str(known),
        "--output", str(tmp_path / "audit.json"), "--min-per-class", "1", "--audit-only",
    ])

    with pytest.raises(ValueError, match="nguồn ngoài đã đánh giá trước"):
        holdout.main()


def test_new_holdout_requires_prior_source_images_for_independence_audit(tmp_path, monkeypatch):
    images, labels, known = make_eight_class_fixture(tmp_path)
    (known / "sources" / "med_node_2015").rmdir()
    monkeypatch.setattr(sys, "argv", [
        "evaluate_new_ensemble_holdout.py", "--images-root", str(images),
        "--labels-csv", str(labels), "--known-data-root", str(known),
        "--output", str(tmp_path / "audit.json"), "--min-per-class", "1", "--audit-only",
    ])

    with pytest.raises(FileNotFoundError, match="Thiếu nguồn ảnh đã kiểm tra trước"):
        holdout.main()


def test_frozen_secondary_checkpoint_is_reported_without_changing_primary_comparison(tmp_path, monkeypatch):
    images, labels, known = make_eight_class_fixture(tmp_path)
    checkpoints = tmp_path / "checkpoints"
    checkpoints.mkdir()
    def entry(name: str):
        path = checkpoints / f"{name}.pth"
        path.write_bytes(name.encode("utf-8"))
        return {"checkpoint": f"checkpoints/{path.name}", "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    primary = tmp_path / "primary.json"
    primary.write_text(json.dumps({"members": [entry(name) for name in ("baseline", "v2c", "resnet")]}), encoding="utf-8")
    secondary = tmp_path / "secondary.json"
    secondary.write_text(json.dumps({"members": [{"id": "convnext", **entry("convnext") }]}), encoding="utf-8")
    scene_split = tmp_path / "scene_split.json"
    scene_split.write_text(json.dumps({
        "combination": "equal_probability_50_50",
        "members": [
            {"id": "scene_split_b0", **entry("scene_b0")},
            {"id": "scene_split_convnext", **entry("scene_convnext")},
        ],
    }), encoding="utf-8")
    output = tmp_path / "result.json"

    def fake_model_probabilities(path, splits, device, batch_size, workers):
        samples = splits["new_test"]
        targets = torch.tensor([sample.label for sample in samples])
        probabilities = (
            torch.eye(len(CLASSES))[[0] * len(samples)]
            if path.stem in ("convnext", "scene_convnext")
            else torch.eye(len(CLASSES))[targets]
        )
        architecture = "convnext_tiny" if path.stem == "scene_convnext" else "efficientnet_b0"
        return {"path": str(path), "architecture": architecture}, {"new_test": probabilities}, {"new_test": targets}

    monkeypatch.setattr(holdout, "model_probabilities", fake_model_probabilities)
    monkeypatch.setattr(holdout, "near_duplicate_candidates", lambda *args, **kwargs: [])
    monkeypatch.setattr(sys, "argv", [
        "evaluate_new_ensemble_holdout.py", "--images-root", str(images),
        "--labels-csv", str(labels), "--known-data-root", str(known),
        "--manifest", str(primary), "--secondary-manifest", str(secondary),
        "--scene-split-manifest", str(scene_split),
        "--output", str(output), "--min-per-class", "1",
    ])

    holdout.main()
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["baseline"]["accuracy"] == 1
    assert report["ensemble"]["accuracy"] == 1
    assert report["secondary_models"]["convnext"]["accuracy"] == 1 / len(CLASSES)
    assert "convnext" in report["secondary_comparisons_vs_baseline"]
    assert report["scene_split_models"]["scene_split_b0"]["accuracy"] == 1
    assert report["scene_split_models"]["scene_split_equal_ensemble"]["accuracy"] == 1 / len(CLASSES)
    assert report["per_source"]["baseline"]["fixture"]["cases"] == len(CLASSES)
    assert sum(report["confusion_matrices"]["baseline"][i][i] for i in range(len(CLASSES))) == len(CLASSES)
    assert report["case_cluster_uncertainty"]["baseline"]["SkinCancer"]["cases"] == 1
    assert report["case_cluster_uncertainty"]["baseline"]["SkinCancer"]["case_cluster_bootstrap_95pct"] == [1, 1]
    assert report["case_cluster_uncertainty"]["secondary_models"]["convnext"]["SkinCancer"]["case_cluster_bootstrap_95pct"] == [0, 0]

    manifest = json.loads(secondary.read_text(encoding="utf-8"))
    manifest["members"][0]["sha256"] = "0" * 64
    secondary.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        holdout.load_secondary_manifest(secondary)


def test_unresolved_near_matches_stop_inference(tmp_path, monkeypatch):
    images, labels, known = make_eight_class_fixture(tmp_path)
    monkeypatch.setattr(holdout, "near_duplicate_candidates", lambda *args, **kwargs: [{"new_image_path": "case_0.png"}])
    monkeypatch.setattr(holdout, "model_probabilities", lambda *args, **kwargs: pytest.fail("inference should be blocked"))
    monkeypatch.setattr(sys, "argv", [
        "evaluate_new_ensemble_holdout.py", "--images-root", str(images),
        "--labels-csv", str(labels), "--known-data-root", str(known),
        "--output", str(tmp_path / "result.json"), "--min-per-class", "1",
    ])

    with pytest.raises(ValueError, match="nghi trùng"):
        holdout.main()
