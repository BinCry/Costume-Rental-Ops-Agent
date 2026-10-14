from functools import lru_cache
from pathlib import Path
from typing import Annotated

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=True,
    )

    APP_ENV: str = "development"
    HOST: str = "0.0.0.0"
    PORT: int = Field(default=8001, ge=1, le=65_535)
    LOG_LEVEL: str = "INFO"

    AI_DATABASE_URL: str
    KNOWLEDGE_BASE_ROOT: Path = Path("knowledge-base")
    KNOWLEDGE_CORPUS_ID: str = "costume-rental-operations"
    KNOWLEDGE_MODEL_ID: str = "intfloat/multilingual-e5-small"
    KNOWLEDGE_MODEL_REVISION: str = "614241f622f53c4eeff9890bdc4f31cfecc418b3"
    KNOWLEDGE_MODEL_CACHE_DIR: Path = Path(".cache/huggingface")
    KNOWLEDGE_MIN_SCORE: float = Field(default=0.72, ge=0, le=1)

    GROQ_BASE_URL: str = "https://api.groq.com/openai/v1"
    GROQ_API_KEY: str | None = None
    GROQ_MODEL: str = "openai/gpt-oss-120b"
    GEMINI_BASE_URL: str = "https://generativelanguage.googleapis.com/v1beta/openai"
    GEMINI_API_KEY: str | None = None
    GEMINI_MODEL: str = "gemini-3.8-flash"
    LLM_TIMEOUT_SECONDS: float = Field(default=25, gt=0, le=120)
    LLM_RETRY_COUNT: int = Field(default=1, ge=0, le=3)

    AI_INTERNAL_API_KEY: str | None = Field(default=None, min_length=32)
    # Studio is the authorization and business-execution boundary.  This URL
    # is deliberately only used by the fixed internal tool client, never by an
    # LLM-provided value.
    STUDIO_API_URL: str | None = None
    AGENT_TOOL_TIMEOUT_SECONDS: float = Field(default=15, gt=0, le=120)
    AGENT_MAX_STEPS_PER_TURN: int = Field(default=6, ge=1, le=12)
    AI_WEB_ALLOWED_ORIGINS: Annotated[tuple[str, ...], NoDecode] = ("http://localhost:5173",)

    @field_validator("GROQ_API_KEY", "GEMINI_API_KEY", "AI_INTERNAL_API_KEY", mode="before")
    @classmethod
    def empty_to_none(cls, value: object) -> object:
        return None if value == "" else value

    @field_validator("AI_WEB_ALLOWED_ORIGINS", mode="before")
    @classmethod
    def split_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return tuple(item.strip() for item in value.split(",") if item.strip())
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
