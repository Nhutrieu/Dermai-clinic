import base64
import io
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
import torch
from PIL import Image
from torch import nn
from torchvision import models, transforms

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


def load_bundle(path: Path) -> ModelBundle | None:
    if not path.exists():
        return None
    checkpoint = torch.load(path, map_location="cpu", weights_only=False)
    classes = checkpoint.get("classes", CLASSES)
    architecture = checkpoint.get("architecture", "efficientnet_b0")
    model, target = build_model(architecture, len(classes))
    model.load_state_dict(checkpoint["model_state_dict"])
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model.to(device).eval()
    return ModelBundle(model, target, checkpoint.get("version", path.stem), classes, device)


PREPROCESS = transforms.Compose([
    transforms.Resize(256),
    transforms.CenterCrop(224),
    transforms.ToTensor(),
    transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
])


class GradCam:
    def __init__(self, model: nn.Module, layer: nn.Module):
        self.model, self.activations, self.gradients = model, None, None
        layer.register_forward_hook(lambda _m, _i, out: setattr(self, "activations", out))
        layer.register_full_backward_hook(
            lambda _m, _gi, go: setattr(self, "gradients", go[0])
        )

    def create(self, tensor: torch.Tensor, class_idx: int) -> np.ndarray:
        self.model.zero_grad(set_to_none=True)
        logits = self.model(tensor)
        logits[0, class_idx].backward()
        weights = self.gradients.mean(dim=(2, 3), keepdim=True)
        cam = torch.relu((weights * self.activations).sum(dim=1))[0]
        cam -= cam.min()
        cam /= cam.max().clamp_min(1e-8)
        return cam.detach().cpu().numpy()


def predict(bundle: ModelBundle, image: Image.Image, confidence_threshold: float = 0.55) -> dict:
    rgb = image.convert("RGB")
    tensor = PREPROCESS(rgb).unsqueeze(0).to(bundle.device)
    with torch.no_grad():
        probabilities = torch.softmax(bundle.model(tensor), dim=1)[0]
    values, indices = probabilities.topk(min(3, len(bundle.classes)))
    top = [
        {"label": bundle.classes[i], "probability": round(float(v), 6)}
        for v, i in zip(values.cpu(), indices.cpu())
    ]
    best_idx = int(indices[0])
    heat = GradCam(bundle.model, bundle.target_layer).create(tensor, best_idx)
    base = np.array(rgb.resize((224, 224)))
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
        "uncertain": top[0]["probability"] < confidence_threshold,
        "disclaimer": DISCLAIMER,
    }
