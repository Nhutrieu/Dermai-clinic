import sys
from pathlib import Path

import numpy as np
import torch
from PIL import Image
from torch import nn


AI_SERVICE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AI_SERVICE_DIR))

from app.model import ModelBundle, predict, preprocess_image  # noqa: E402


class TinyClassifier(nn.Module):
    def __init__(self) -> None:
        super().__init__()
        self.features = nn.Conv2d(3, 4, kernel_size=3, padding=1)
        self.pool = nn.AdaptiveAvgPool2d(1)
        self.classifier = nn.Linear(4, 3)

    def forward(self, inputs: torch.Tensor) -> torch.Tensor:
        features = self.features(inputs)
        return self.classifier(self.pool(features).flatten(1))


def test_preprocess_base_is_spatially_aligned_with_model_tensor():
    x_gradient = np.tile(np.arange(400, dtype=np.uint8), (200, 1))
    image = Image.fromarray(np.stack([x_gradient, x_gradient, x_gradient], axis=2))

    tensor, base = preprocess_image(image)

    mean = torch.tensor([0.485, 0.456, 0.406])[:, None, None]
    std = torch.tensor([0.229, 0.224, 0.225])[:, None, None]
    recovered = ((tensor * std + mean).clamp(0, 1) * 255).round().byte()
    recovered = recovered.permute(1, 2, 0).numpy()
    assert base.shape == (224, 224, 3)
    assert np.max(np.abs(recovered.astype(int) - base.astype(int))) <= 1


def test_predict_removes_gradcam_hooks_after_every_request():
    model = TinyClassifier().eval()
    target = model.features
    bundle = ModelBundle(
        model=model,
        target_layer=target,
        version="tiny-test",
        classes=["a", "b", "c"],
        device=torch.device("cpu"),
    )
    image = Image.new("RGB", (320, 180), color=(80, 120, 160))
    initial_forward_hooks = len(target._forward_hooks)
    initial_backward_hooks = len(target._backward_hooks)

    first = predict(bundle, image)
    second = predict(bundle, image)

    assert first["model_version"] == "tiny-test"
    assert second["gradcam_image"].startswith("data:image/png;base64,")
    assert len(target._forward_hooks) == initial_forward_hooks
    assert len(target._backward_hooks) == initial_backward_hooks
