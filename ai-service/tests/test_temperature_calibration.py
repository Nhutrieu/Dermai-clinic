import sys
from pathlib import Path

import torch
from PIL import Image
from torch import nn


AI_SERVICE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AI_SERVICE_DIR))

from app.model import ModelBundle, predict  # noqa: E402


class FixedLogitClassifier(nn.Module):
    def __init__(self) -> None:
        super().__init__()
        self.features = nn.Conv2d(3, 4, kernel_size=3, padding=1)
        self.pool = nn.AdaptiveAvgPool2d(1)
        self.classifier = nn.Linear(4, 3)
        with torch.no_grad():
            self.classifier.weight.zero_()
            self.classifier.bias.copy_(torch.tensor([4.0, 1.0, 0.0]))

    def forward(self, inputs: torch.Tensor) -> torch.Tensor:
        features = self.features(inputs)
        return self.classifier(self.pool(features).flatten(1))


def test_temperature_reduces_overconfidence_without_changing_ranking():
    model = FixedLogitClassifier().eval()
    image = Image.new("RGB", (320, 320), color=(90, 130, 170))
    raw = ModelBundle(
        model, model.features, "raw", ["a", "b", "c"], torch.device("cpu")
    )
    calibrated = ModelBundle(
        model,
        model.features,
        "calibrated",
        ["a", "b", "c"],
        torch.device("cpu"),
        temperature=2.0,
    )

    raw_result = predict(raw, image)
    calibrated_result = predict(calibrated, image)

    assert calibrated_result["disease"] == raw_result["disease"] == "a"
    assert [item["label"] for item in calibrated_result["top3"]] == [
        item["label"] for item in raw_result["top3"]
    ]
    assert calibrated_result["confidence"] < raw_result["confidence"]
