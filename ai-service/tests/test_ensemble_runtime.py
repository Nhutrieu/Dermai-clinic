import sys
from pathlib import Path

import numpy as np
import pytest
import torch
from PIL import Image
from torch import nn


AI_SERVICE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AI_SERVICE_DIR))

from app.model import EnsembleBundle, ModelBundle, OutOfScopeImageError, load_ensemble, predict  # noqa: E402
from app.ood import OodProfile  # noqa: E402


class FixedLogitClassifier(nn.Module):
    def __init__(self, logits: list[float]) -> None:
        super().__init__()
        self.features = nn.Conv2d(3, 4, kernel_size=1)
        self.pool = nn.AdaptiveAvgPool2d(1)
        self.classifier = nn.Linear(4, len(logits))
        with torch.no_grad():
            self.classifier.weight.zero_()
            self.classifier.bias.copy_(torch.tensor(logits))

    def forward(self, inputs: torch.Tensor) -> torch.Tensor:
        return self.classifier(self.pool(self.features(inputs)).flatten(1))


def test_ensemble_averages_calibrated_probabilities_and_cleans_gradcam_hooks():
    first = FixedLogitClassifier([3.0, 1.0, 0.0]).eval()
    second = FixedLogitClassifier([0.0, 4.0, 1.0]).eval()
    members = (
        ModelBundle(first, first.features, "first", ["a", "b", "c"], torch.device("cpu"), temperature=2.0),
        ModelBundle(second, second.features, "second", ["a", "b", "c"], torch.device("cpu")),
    )
    bundle = EnsembleBundle(members, "research-ensemble", ["a", "b", "c"], torch.device("cpu"))
    expected = (torch.softmax(torch.tensor([3.0, 1.0, 0.0]) / 2, 0)
                + torch.softmax(torch.tensor([0.0, 4.0, 1.0]), 0)) / 2

    result = predict(bundle, Image.new("RGB", (320, 320), color=(80, 120, 160)))

    assert result["model_version"] == "research-ensemble"
    assert result["disease"] == ["a", "b", "c"][int(expected.argmax())]
    assert result["confidence"] == pytest.approx(float(expected.max()), abs=1e-6)
    assert result["gradcam_image"].startswith("data:image/png;base64,")
    for member in members:
        assert len(member.target_layer._forward_hooks) == 0
        assert len(member.target_layer._backward_hooks) == 0


def test_ensemble_rejects_manifest_with_missing_checkpoint(tmp_path):
    manifest = tmp_path / "ensemble.json"
    manifest.write_text(
        '{"name":"test","members":['
        '{"checkpoint":"missing.pth","sha256":"x"},'
        '{"checkpoint":"also-missing.pth","sha256":"y"}]}',
        encoding="utf-8",
    )
    with pytest.raises(FileNotFoundError):
        load_ensemble(manifest)


def test_ensemble_uses_first_member_ood_gate():
    first = FixedLogitClassifier([3.0, 1.0, 0.0]).eval()
    second = FixedLogitClassifier([0.0, 4.0, 1.0]).eval()
    profile = OodProfile(
        classes=["a", "b", "c"],
        centroids=np.ones((3, 4), dtype=np.float32),
        distance_threshold=-1.0,
        model_version="first",
    )
    members = (
        ModelBundle(first, first.features, "first", profile.classes, torch.device("cpu"), profile),
        ModelBundle(second, second.features, "second", profile.classes, torch.device("cpu")),
    )
    bundle = EnsembleBundle(members, "research-ensemble", profile.classes, torch.device("cpu"))

    with pytest.raises(OutOfScopeImageError):
        predict(bundle, Image.new("RGB", (320, 320), color=(80, 120, 160)))
