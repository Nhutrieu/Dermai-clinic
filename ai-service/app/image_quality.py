from dataclasses import dataclass

import cv2
import numpy as np
from PIL import Image


@dataclass(frozen=True)
class ImageQualityResult:
    accepted: bool
    reason: str | None = None


def assess_image_quality(
    image: Image.Image,
    *,
    min_dimension: int = 224,
    min_brightness: float = 18.0,
    max_brightness: float = 242.0,
    min_contrast: float = 10.0,
    min_sharpness: float = 16.0,
) -> ImageQualityResult:
    """Reject technically unusable images before model inference."""
    rgb = np.asarray(image.convert("RGB"))
    height, width = rgb.shape[:2]
    if min(height, width) < min_dimension:
        return ImageQualityResult(False, f"Ảnh quá nhỏ. Vui lòng dùng ảnh có mỗi chiều tối thiểu {min_dimension} px.")

    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    brightness = float(gray.mean())
    if brightness < min_brightness:
        return ImageQualityResult(False, "Ảnh quá tối. Vui lòng chụp lại ở nơi đủ sáng.")
    if brightness > max_brightness:
        return ImageQualityResult(False, "Ảnh quá sáng hoặc bị cháy sáng. Vui lòng chụp lại.")
    if float(gray.std()) < min_contrast:
        return ImageQualityResult(False, "Ảnh thiếu chi tiết hoặc độ tương phản quá thấp. Vui lòng chụp lại gần vùng da.")

    scale = min(1.0, 1024 / max(height, width))
    if scale < 1.0:
        gray = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    if float(cv2.Laplacian(gray, cv2.CV_64F).var()) < min_sharpness:
        return ImageQualityResult(False, "Ảnh bị mờ. Vui lòng giữ máy ổn định và lấy nét vào vùng da.")
    return ImageQualityResult(True)
