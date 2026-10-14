from pytest import MonkeyPatch

from app.config import Settings


def test_allowed_origins_accepts_comma_separated_env_value(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setenv("AI_DATABASE_URL", "postgresql://test:test@localhost/test")
    monkeypatch.setenv(
        "AI_WEB_ALLOWED_ORIGINS",
        "http://localhost:5173,https://studio.example.com",
    )

    settings = Settings(_env_file=None)

    assert settings.AI_WEB_ALLOWED_ORIGINS == (
        "http://localhost:5173",
        "https://studio.example.com",
    )


def test_default_groq_model_is_gpt_oss(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setenv("AI_DATABASE_URL", "postgresql://test:test@localhost/test")
    monkeypatch.delenv("GROQ_MODEL", raising=False)

    settings = Settings(_env_file=None)

    assert settings.GROQ_MODEL == "openai/gpt-oss-120b"
