import base64
import io
import math
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
import torch
from PIL import Image
from torch import nn
from torchvision import models, transforms

from .ood import OodProfile, is_out_of_scope, load_ood_profile

CLASSES = [
    "Acne", "Candidiasis", "Eczema", "Lupus",
    "Psoriasis", "SkinCancer", "Tinea", "Warts",
]
DISCLAIMER = "Kết quả chỉ nhằm hỗ trợ, không thay thế chẩn đoán của bác sĩ."


@dataclass
class ModelBundle:
    model: nn.Module
    target_layer: nn.Module
    version: str
    classes: list[str]
    device: torch.device
    ood_profile: OodProfile | None = None
    temperature: float = 1.0

    def extract_embeddings(self, inputs: torch.Tensor) -> torch.Tensor:
        captured: list[torch.Tensor] = []
        handle = self.target_layer.register_forward_hook(
            lambda _module, _args, output: captured.append(output)
        )
        try:
            with torch.no_grad():
                self.model(inputs)
        finally:
            handle.remove()
        if not captured:
            raise RuntimeError("Không thể trích xuất đặc trưng từ mô hình.")
        features = captured[0]
        if features.ndim > 2:
            features = features.mean(dim=tuple(range(2, features.ndim)))
        return torch.nn.functional.normalize(features.flatten(1), dim=1)


class OutOfScopeImageError(ValueError):
    pass


def build_model(architecture: str, num_classes: int) -> tuple[nn.Module, nn.Module]:
    if architecture == "resnet50":
        model = models.resnet50(weights=None)
        model.fc = nn.Linear(model.fc.in_features, num_classes)
        return model, model.layer4[-1]
    if architecture == "convnext_tiny":
        model = models.convnext_tiny(weights=None)
        model.classifier[2] = nn.Linear(model.classifier[2].in_features, num_classes)
        return model, model.features[-1]
    model = models.efficientnet_b0(weights=None)
    model.classifier[1] = nn.Linear(model.classifier[1].in_features, num_classes)
    return model, model.features[-1]


def load_bundle(path: Path, ood_profile_path: Path | None = None) -> ModelBundle | None:
    if not path.exists():
        return None
    checkpoint = torch.load(path, map_location="cpu", weights_only=False)
    classes = checkpoint.get("classes", CLASSES)
    architecture = checkpoint.get("architecture", "efficientnet_b0")
    model, target = build_model(architecture, len(classes))
    model.load_state_dict(checkpoint["model_state_dict"])
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model.to(device).eval()
    version = checkpoint.get("version", path.stem)
    profile = load_ood_profile(ood_profile_path, classes, version) if ood_profile_path else None
    temperature = float(checkpoint.get("temperature", 1.0))
    if not math.isfinite(temperature) or temperature <= 0:
        raise ValueError(
            "Temperature calibration trong checkpoint phải là số dương hữu hạn."
        )
    return ModelBundle(model, target, version, classes, device, profile, temperature)


SPATIAL_PREPROCESS = transforms.Compose([
    transforms.Resize(256),
    transforms.CenterCrop(224),
])

PREPROCESS = transforms.Compose([
    SPATIAL_PREPROCESS,
    transforms.ToTensor(),
    transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
])


class GradCam:
    def __init__(self, model: nn.Module, layer: nn.Module):
        self.model, self.activations, self.gradients = model, None, None
        self._forward_handle = layer.register_forward_hook(
            lambda _m, _i, out: setattr(self, "activations", out)
        )
        self._backward_handle = layer.register_full_backward_hook(
            lambda _m, _gi, go: setattr(self, "gradients", go[0])
        )

    def close(self) -> None:
        self._forward_handle.remove()
        self._backward_handle.remove()

    def __enter__(self) -> "GradCam":
        return self

    def __exit__(self, _exc_type, _exc_value, _traceback) -> None:
        self.close()

    def create(self, tensor: torch.Tensor, class_idx: int) -> np.ndarray:
        self.model.zero_grad(set_to_none=True)
        logits = self.model(tensor)
        logits[0, class_idx].backward()
        if self.activations is None or self.gradients is None:
            raise RuntimeError("Grad-CAM hooks did not capture activations and gradients.")
        weights = self.gradients.mean(dim=(2, 3), keepdim=True)
        cam = torch.relu((weights * self.activations).sum(dim=1))[0]
        cam -= cam.min()
        cam /= cam.max().clamp_min(1e-8)
        return cam.detach().cpu().numpy()


def preprocess_image(image: Image.Image) -> tuple[torch.Tensor, np.ndarray]:
    """Return model input and an RGB base image with identical spatial transforms."""
    rgb = image.convert("RGB")
    spatially_aligned = SPATIAL_PREPROCESS(rgb)
    tensor = PREPROCESS(rgb)
    return tensor, np.asarray(spatially_aligned)


def predict(
    bundle: ModelBundle,
    image: Image.Image,
    confidence_threshold: float = 0.70,
    confidence_margin_threshold: float = 0.20,
    normalized_entropy_threshold: float = 0.65,
) -> dict:
    tensor, base = preprocess_image(image)
    tensor = tensor.unsqueeze(0).to(bundle.device)
    if bundle.ood_profile is not None:
        embedding = bundle.extract_embeddings(tensor)[0].cpu().numpy()
        rejected, _score = is_out_of_scope(embedding, bundle.ood_profile)
        if rejected:
            raise OutOfScopeImageError("Ảnh nằm ngoài 8 nhóm bệnh mà hệ thống hỗ trợ. Vui lòng chọn ảnh tổn thương da khác hoặc khám trực tiếp.")
    with torch.no_grad():
        logits = bundle.model(tensor)
        probabilities = torch.softmax(logits / bundle.temperature, dim=1)[0]
    values, indices = probabilities.topk(min(3, len(bundle.classes)))
    top = [
        {"label": bundle.classes[i], "probability": round(float(v), 6)}
        for v, i in zip(values.cpu(), indices.cpu())
    ]
    probability_values = probabilities.detach().cpu().numpy()
    normalized_entropy = float(
        -(probability_values * np.log(np.clip(probability_values, 1e-12, 1.0))).sum()
        / math.log(max(2, len(probability_values)))
    )
    confidence_margin = top[0]["probability"] - (top[1]["probability"] if len(top) > 1 else 0.0)
    uncertain = (
        top[0]["probability"] < confidence_threshold
        or confidence_margin < confidence_margin_threshold
        or normalized_entropy > normalized_entropy_threshold
    )
    best_idx = int(indices[0])
    with GradCam(bundle.model, bundle.target_layer) as gradcam:
        heat = gradcam.create(tensor, best_idx)
    heat = cv2.resize(heat, (224, 224))
    colored = cv2.applyColorMap(np.uint8(255 * heat), cv2.COLORMAP_JET)
    colored = cv2.cvtColor(colored, cv2.COLOR_BGR2RGB)
    overlay = np.uint8(0.55 * base + 0.45 * colored)
    output = io.BytesIO()
    Image.fromarray(overlay).save(output, format="PNG")
    return {
        "disease": top[0]["label"],
        "confidence": top[0]["probability"],
        "top3": top,
        "gradcam_image": "data:image/png;base64," + base64.b64encode(output.getvalue()).decode(),
        "model_version": bundle.version,
        "uncertain": uncertain,
        "disclaimer": DISCLAIMER,
    }
