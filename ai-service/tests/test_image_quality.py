import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter


AI_SERVICE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AI_SERVICE_DIR))

from app.image_quality import assess_image_quality  # noqa: E402


def test_rejects_image_that_is_too_small():
    result = assess_image_quality(Image.new("RGB", (160, 160), "gray"))
    assert not result.accepted
    assert result.reason


def test_rejects_overexposed_image():
    result = assess_image_quality(Image.new("RGB", (320, 320), "white"))
    assert not result.accepted
    assert result.reason


def test_rejects_blurred_image():
    checker = np.indices((320, 320)).sum(axis=0) % 2
    rgb = np.repeat((checker * 255).astype(np.uint8)[..., None], 3, axis=2)
    result = assess_image_quality(Image.fromarray(rgb).filter(ImageFilter.GaussianBlur(radius=14)))
    assert not result.accepted
    assert result.reason


def test_accepts_clear_detailed_image():
    checker = (np.indices((320, 320)).sum(axis=0) // 12) % 2
    rgb = np.repeat((checker * 180 + 35).astype(np.uint8)[..., None], 3, axis=2)
    assert assess_image_quality(Image.fromarray(rgb)).accepted
