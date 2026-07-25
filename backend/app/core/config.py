from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = Field(..., alias="DATABASE_URL")
    frontend_url: str = Field(default="http://localhost:3000", alias="FRONTEND_URL")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    upload_dir: str = Field(default="./uploads", alias="UPLOAD_DIR")

    ai_provider: str = Field(default="openrouter", alias="AI_PROVIDER")
    ai_api_key: str = Field(default="", alias="AI_API_KEY")
    ai_base_url: str = Field(default="", alias="AI_BASE_URL")
    ai_model: str = Field(default="openai/gpt-4o-mini", alias="AI_MODEL")
    embedding_model: str = Field(
        default="openai/text-embedding-3-small",
        alias="EMBEDDING_MODEL",
    )
    embedding_dimensions: int = Field(default=1536, alias="EMBEDDING_DIMENSIONS")
    # remote = OpenRouter/OpenAI/etc (costs); local = free ONNX model on the machine
    embedding_provider: str = Field(default="remote", alias="EMBEDDING_PROVIDER")
    local_embedding_model: str = Field(
        default="sentence-transformers/all-MiniLM-L6-v2",
        alias="LOCAL_EMBEDDING_MODEL",
    )

    collector_play_app_id: str = Field(
        default="com.zeptoconsumerapp",
        alias="COLLECTOR_PLAY_APP_ID",
    )
    collector_ios_app_id: str = Field(default="1575323645", alias="COLLECTOR_IOS_APP_ID")
    collector_country: str = Field(default="in", alias="COLLECTOR_COUNTRY")
    collector_lang: str = Field(default="en", alias="COLLECTOR_LANG")
    collector_max_per_store: int = Field(default=100, alias="COLLECTOR_MAX_PER_STORE")
    collector_master_dataset_name: str = Field(
        default="Zepto Public Mentions",
        alias="COLLECTOR_MASTER_DATASET_NAME",
    )

    @field_validator("database_url")
    @classmethod
    def database_url_required(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("DATABASE_URL is required")
        return value.strip()

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.frontend_url.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
