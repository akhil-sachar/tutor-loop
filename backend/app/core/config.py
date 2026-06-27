from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


ROOT_DIR = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    app_name: str = "TutorLoop"
    app_env: str = "development"
    cors_origins: str = "*"

    mongodb_uri: str | None = None
    mongodb_db_name: str = "tutorloop"
    mongodb_vector_index: str = "tutorloop_vector_index"
    embedding_dimensions: int = 768

    gemini_api_key: str | None = None
    gemini_model: str = "gemini-3.5-pro"
    gemini_embedding_model: str = "gemini-embedding-001"

    livekit_url: str | None = None
    livekit_api_key: str | None = None
    livekit_api_secret: str | None = None

    jwt_secret: str = "dev-only-change-me"
    demo_seed_on_startup: bool = True

    frontend_dir: Path = ROOT_DIR / "frontend"

    model_config = SettingsConfigDict(
        env_file=(ROOT_DIR / ".env", ROOT_DIR / "backend" / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def use_mongo(self) -> bool:
        return bool(self.mongodb_uri)

    @property
    def use_gemini(self) -> bool:
        return bool(self.gemini_api_key)

    @property
    def use_livekit(self) -> bool:
        return bool(self.livekit_url and self.livekit_api_key and self.livekit_api_secret)


@lru_cache
def get_settings() -> Settings:
    return Settings()
