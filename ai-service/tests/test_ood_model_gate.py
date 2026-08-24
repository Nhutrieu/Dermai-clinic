import sys
from pathlib import Path

import numpy as np
import pytest
import torch
from PIL import Image
from torch import nn


AI_SERVICE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AI_SERVICE_DIR))

from app.model import ModelBundle, OutOfScopeImageError, predict  # noqa: E402
from app.ood import OodProfile  # noqa: E402


class TinyClassifier(nn.Module):
    def __init__(self) -> None:
        super().__init__()
        self.features = nn.Conv2d(3, 4, kernel_size=3, padding=1)
        self.pool = nn.AdaptiveAvgPool2d(1)
        self.classifier = nn.Linear(4, 3)

    def forward(self, inputs: torch.Tensor) -> torch.Tensor:
        features = self.features(inputs)
        return self.classifier(self.pool(features).flatten(1))


def test_predict_rejects_embedding_outside_profile():
    model = TinyClassifier().eval()
    profile = OodProfile(
        classes=["a", "b", "c"],
        centroids=np.asarray([[1, 0, 0, 0], [1, 0, 0, 0], [1, 0, 0, 0]], dtype=np.float32),
        distance_threshold=-1.0,
        model_version="tiny-test",
    )
    bundle = ModelBundle(model, model.features, "tiny-test", profile.classes, torch.device("cpu"), profile)

    with pytest.raises(OutOfScopeImageError):
        predict(bundle, Image.new("RGB", (320, 320), color=(80, 120, 160)))
