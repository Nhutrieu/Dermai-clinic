from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    model_path: Path = Path("models/best_model.pth")
    ood_profile_path: Path = Path("models/ood_profile.json")
    rag_index_path: Path = Path("rag/index")
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"
    max_upload_bytes: int = 10 * 1024 * 1024
    confidence_threshold: float = 0.70
    confidence_margin_threshold: float = 0.20
    normalized_entropy_threshold: float = 0.65
    allowed_mime: tuple[str, ...] = ("image/jpeg", "image/png", "image/webp")


settings = Settings()
