from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, field_validator


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    model_path: Path = Path("models/best_model.pth")
    ensemble_manifest_path: Path | None = None
    research_manifest_path: Path | None = Path(__file__).resolve().parents[1] / "models/research_pipeline/manifest.json"
    ood_profile_path: Path = Path("models/ood_profile.json")
    rag_index_path: Path = Path("rag/index")
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"
    max_upload_bytes: int = 10 * 1024 * 1024
    confidence_threshold: float = 0.70
    confidence_margin_threshold: float = 0.20
    normalized_entropy_threshold: float = 0.65
    inference_threads: int = Field(default=4, ge=1, le=32)
    allowed_mime: tuple[str, ...] = ("image/jpeg", "image/png", "image/webp")

    @field_validator("research_manifest_path", mode="before")
    @classmethod
    def disable_research_explicitly(cls, value):
        return None if isinstance(value, str) and value.lower() in {"off", "none", ""} else value


settings = Settings()
