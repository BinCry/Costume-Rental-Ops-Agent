import asyncio
import logging
from dataclasses import dataclass
from typing import Any

import httpx

from app.config import Settings, get_settings
from app.errors import AppError

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Provider:
    name: str
    base_url: str
    api_key: str
    model: str


class ProviderFailure(Exception):
    def __init__(self, provider: str, retryable: bool) -> None:
        super().__init__(f"{provider} completion failed")
        self.provider = provider
        self.retryable = retryable


def _configured_providers(settings: Settings) -> list[Provider]:
    providers: list[Provider] = []
    if settings.GROQ_API_KEY:
        providers.append(
            Provider("groq", settings.GROQ_BASE_URL, settings.GROQ_API_KEY, settings.GROQ_MODEL)
        )
    if settings.GEMINI_API_KEY:
        providers.append(
            Provider(
                "gemini",
                settings.GEMINI_BASE_URL,
                settings.GEMINI_API_KEY,
                settings.GEMINI_MODEL,
            )
        )
    return providers


def _chat_url(base_url: str) -> str:
    normalized = base_url.rstrip("/")
    return (
        normalized if normalized.endswith("/chat/completions") else f"{normalized}/chat/completions"
    )


def _read_content(payload: Any) -> str:
    try:
        content = payload["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as error:
        raise ValueError("Completion response has no message content") from error
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        return "".join(
            part.get("text", "")
            for part in content
            if isinstance(part, dict) and isinstance(part.get("text", ""), str)
        ).strip()
    raise ValueError("Completion response has invalid message content")


def _retry_delay(response: httpx.Response | None, attempt: int) -> float:
    if response is not None:
        retry_after = response.headers.get("retry-after")
        if retry_after:
            try:
                return min(float(retry_after), 2.0)
            except ValueError:
                pass
    return float(min(0.25 * (2**attempt), 2.0))


async def _call_provider(
    client: httpx.AsyncClient,
    provider: Provider,
    system: str,
    user: str,
    retry_count: int,
) -> str:
    for attempt in range(retry_count + 1):
        response: httpx.Response | None = None
        try:
            response = await client.post(
                _chat_url(provider.base_url),
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {provider.api_key}",
                },
                json={
                    "model": provider.model,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    "temperature": 0.1,
                    "max_tokens": 600,
                },
            )
        except httpx.HTTPError:
            retryable = True
        else:
            retryable = response.status_code == 429 or response.status_code >= 500
            if response.is_success:
                try:
                    content = _read_content(response.json())
                except (ValueError, TypeError):
                    retryable = True
                else:
                    if content:
                        return content
                    retryable = True

        if not retryable:
            logger.warning(
                "LLM provider rejected request provider=%s status=%s",
                provider.name,
                response.status_code if response is not None else "network_error",
            )
            raise ProviderFailure(provider.name, retryable=False)
        if attempt < retry_count:
            await asyncio.sleep(_retry_delay(response, attempt))

    raise ProviderFailure(provider.name, retryable=True)


async def generate_completion(system: str, user: str) -> str:
    settings = get_settings()
    providers = _configured_providers(settings)
    if not providers:
        raise AppError(
            503,
            "LLM_NOT_CONFIGURED",
            "The answer service is not configured. Contact the administrator.",
        )

    timeout = httpx.Timeout(settings.LLM_TIMEOUT_SECONDS)
    async with httpx.AsyncClient(timeout=timeout) as client:
        for provider in providers:
            try:
                return await _call_provider(
                    client,
                    provider,
                    system,
                    user,
                    settings.LLM_RETRY_COUNT,
                )
            except ProviderFailure as error:
                logger.warning(
                    "LLM provider failed provider=%s fallback_allowed=%s",
                    error.provider,
                    error.retryable,
                )
                if not error.retryable:
                    break

    raise AppError(503, "LLM_UNAVAILABLE", "The answer service is unavailable")
