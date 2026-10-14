from types import SimpleNamespace

import httpx
import pytest

from app.errors import AppError
from app.knowledge import llm


def settings(**overrides: object) -> SimpleNamespace:
    values: dict[str, object] = {
        "GROQ_BASE_URL": "https://groq.test/v1",
        "GROQ_API_KEY": "groq-key",
        "GROQ_MODEL": "groq-model",
        "GEMINI_BASE_URL": "https://gemini.test/v1",
        "GEMINI_API_KEY": "gemini-key",
        "GEMINI_MODEL": "gemini-model",
        "LLM_TIMEOUT_SECONDS": 1,
        "LLM_RETRY_COUNT": 1,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


@pytest.mark.asyncio
async def test_generate_uses_groq_first(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []

    async def fake_call(
        _client: httpx.AsyncClient,
        provider: llm.Provider,
        _system: str,
        _user: str,
        _retry_count: int,
    ) -> str:
        calls.append(provider.name)
        return "groq answer"

    monkeypatch.setattr(llm, "get_settings", settings)
    monkeypatch.setattr(llm, "_call_provider", fake_call)

    assert await llm.generate_completion("system", "user") == "groq answer"
    assert calls == ["groq"]


@pytest.mark.asyncio
async def test_generate_falls_back_to_gemini_on_retryable_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    async def fake_call(
        _client: httpx.AsyncClient,
        provider: llm.Provider,
        _system: str,
        _user: str,
        _retry_count: int,
    ) -> str:
        calls.append(provider.name)
        if provider.name == "groq":
            raise llm.ProviderFailure("groq", retryable=True)
        return "gemini answer"

    monkeypatch.setattr(llm, "get_settings", settings)
    monkeypatch.setattr(llm, "_call_provider", fake_call)

    assert await llm.generate_completion("system", "user") == "gemini answer"
    assert calls == ["groq", "gemini"]


@pytest.mark.asyncio
async def test_generate_does_not_fallback_on_rejected_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    async def fake_call(
        _client: httpx.AsyncClient,
        provider: llm.Provider,
        _system: str,
        _user: str,
        _retry_count: int,
    ) -> str:
        calls.append(provider.name)
        raise llm.ProviderFailure(provider.name, retryable=False)

    monkeypatch.setattr(llm, "get_settings", settings)
    monkeypatch.setattr(llm, "_call_provider", fake_call)

    with pytest.raises(AppError) as captured:
        await llm.generate_completion("system", "user")

    assert captured.value.code == "LLM_UNAVAILABLE"
    assert calls == ["groq"]


@pytest.mark.asyncio
async def test_generate_requires_at_least_one_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        llm,
        "get_settings",
        lambda: settings(GROQ_API_KEY=None, GEMINI_API_KEY=None),
    )

    with pytest.raises(AppError) as captured:
        await llm.generate_completion("system", "user")

    assert captured.value.code == "LLM_NOT_CONFIGURED"
