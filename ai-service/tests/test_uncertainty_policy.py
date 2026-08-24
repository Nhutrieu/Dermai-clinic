import sys
from pathlib import Path

import torch
from PIL import Image
from torch import nn


AI_SERVICE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AI_SERVICE_DIR))

from app.model import ModelBundle, predict  # noqa: E402


class TinyClassifier(nn.Module):
    def __init__(self) -> None:
        super().__init__()
        self.features = nn.Conv2d(3, 4, kernel_size=3, padding=1)
        self.pool = nn.AdaptiveAvgPool2d(1)
        self.classifier = nn.Linear(4, 3)

    def forward(self, inputs: torch.Tensor) -> torch.Tensor:
        features = self.features(inputs)
        return self.classifier(self.pool(features).flatten(1))


def test_close_probabilities_are_marked_uncertain():
    model = TinyClassifier().eval()
    with torch.no_grad():
        model.classifier.weight.zero_()
        model.classifier.bias.zero_()
    bundle = ModelBundle(model, model.features, "tiny-test", ["a", "b", "c"], torch.device("cpu"))

    result = predict(bundle, Image.new("RGB", (320, 320), color=(80, 120, 160)))

    assert result["uncertain"] is True
