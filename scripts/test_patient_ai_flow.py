from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
from pathlib import Path

import httpx


def encoded(value: dict) -> str:
    raw = json.dumps(value, separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def token(secret: str, subject: str) -> str:
    header = encoded({"alg": "HS256", "typ": "JWT"})
    now = int(time.time())
    payload = encoded({"sub": subject, "role": "PATIENT", "iat": now, "exp": now + 300})
    unsigned = f"{header}.{payload}"
    signature = base64.urlsafe_b64encode(
        hmac.new(secret.encode(), unsigned.encode(), hashlib.sha256).digest()
    ).rstrip(b"=").decode()
    return f"{unsigned}.{signature}"


def main() -> None:
    secret = os.environ["DERMAI_TEST_JWT_SECRET"]
    subject = os.environ["DERMAI_TEST_PATIENT_IDENTITY"]
    image_path = Path(os.environ["DERMAI_TEST_IMAGE"])
    base_url = os.environ.get("DERMAI_TEST_BASE_URL", "http://localhost:8080")
    headers = {"Authorization": f"Bearer {token(secret, subject)}"}
    created_id = None

    with httpx.Client(base_url=base_url, headers=headers, timeout=120) as client:
        profile = client.get("/api/v1/patients/me")
        profile.raise_for_status()
        with image_path.open("rb") as image:
            prediction = client.post(
                "/ai/predict",
                files={"image": (image_path.name, image, "image/jpeg")},
            )
        prediction.raise_for_status()
        result = prediction.json()
        try:
            created = client.post(
                "/api/v1/patients/me/ai-assessments",
                json={
                    "predictedLabel": result["disease"],
                    "confidence": result["confidence"],
                    "top3": result["top3"],
                    "uncertain": result["uncertain"],
                    "modelVersion": result["model_version"],
                    "sharedWithDoctor": False,
                },
            )
            created.raise_for_status()
            created_id = created.json()["id"]

            history = client.get("/api/v1/patients/me/ai-assessments")
            history.raise_for_status()
            assert any(item["id"] == created_id for item in history.json())

            sharing = client.patch(
                f"/api/v1/patients/me/ai-assessments/{created_id}/sharing",
                json={"sharedWithDoctor": True},
            )
            sharing.raise_for_status()
            assert sharing.json()["sharedWithDoctor"] is True

            print(json.dumps({
                "profile": profile.status_code,
                "predict": prediction.status_code,
                "save": created.status_code,
                "history": history.status_code,
                "share": sharing.status_code,
                "disease": result["disease"],
                "top3": len(result["top3"]),
                "gradcam": result["gradcam_image"].startswith("data:image/png;base64,"),
            }))
        finally:
            if created_id:
                deleted = client.delete(f"/api/v1/patients/me/ai-assessments/{created_id}")
                deleted.raise_for_status()


if __name__ == "__main__":
    main()
