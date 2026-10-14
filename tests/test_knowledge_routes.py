from collections.abc import Iterator

import httpx
import pytest

from app.config import get_settings
from app.knowledge import routes
from app.main import app
from app.models import ActorContext, KnowledgeAnswer

SERVICE_KEY = "test-ai-internal-key-at-least-32-characters"
GUEST_HEADERS = {
    "X-AI-Service-Key": SERVICE_KEY,
    "X-Actor-Id": "guest",
    "X-Knowledge-Audiences": "customer,shared",
}


@pytest.fixture(autouse=True)
def configure_internal_auth(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setenv("AI_INTERNAL_API_KEY", SERVICE_KEY)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_answer_allows_guest_with_customer_safe_audiences(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_actor: ActorContext | None = None

    async def fake_answer(actor: ActorContext, query: str, top_k: int) -> KnowledgeAnswer:
        nonlocal captured_actor
        captured_actor = actor
        assert query == "Where do I return the costume?"
        assert top_k == 5
        return KnowledgeAnswer(
            outcome="insufficient_context",
            answer="Insufficient approved context",
            sources=[],
            provisional=False,
        )

    monkeypatch.setattr(routes, "answer_knowledge", fake_answer)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/knowledge/answer",
            headers=GUEST_HEADERS,
            json={"query": "Where do I return the costume?"},
        )

    assert response.status_code == 200
    assert response.json() == {
        "success": True,
        "data": {
            "result": {
                "outcome": "insufficient_context",
                "answer": "Insufficient approved context",
                "sources": [],
                "provisional": False,
            }
        },
        "message": "Knowledge answer completed",
    }
    assert captured_actor is not None
    assert captured_actor.user_id == "guest"
    assert captured_actor.audiences == ("customer", "shared")


@pytest.mark.asyncio
async def test_internal_search_still_rejects_guest() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/knowledge/search",
            headers=GUEST_HEADERS,
            json={"query": "quy trình nội bộ"},
        )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTHENTICATED_ACTOR_REQUIRED"


@pytest.mark.asyncio
async def test_answer_requires_trusted_actor_context() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/knowledge/answer",
            headers={"X-AI-Service-Key": SERVICE_KEY},
            json={"query": "Tôi trả đồ ở đâu?"},
        )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_ACTOR_CONTEXT"


@pytest.mark.asyncio
async def test_answer_rejects_missing_internal_service_key() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/knowledge/answer", json={"query": "Tôi trả đồ ở đâu?"}
        )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_SERVICE_CREDENTIALS"


@pytest.mark.asyncio
async def test_answer_returns_shared_validation_error_contract() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/knowledge/answer",
            headers={
                **GUEST_HEADERS,
                "X-Request-Id": "validation-request-id",
            },
            json={"query": "x"},
        )

    body = response.json()
    assert response.status_code == 400
    assert response.headers["X-Request-Id"] == "validation-request-id"
    assert body["success"] is False
    assert body["error"] == {
        "code": "VALIDATION_ERROR",
        "message": "Invalid knowledge answer request",
    }
    assert body["statusCode"] == 400
    assert body["path"] == "/api/v1/knowledge/answer"
    assert body["requestId"] == "validation-request-id"
    assert isinstance(body["timestamp"], str)


@pytest.mark.asyncio
async def test_unknown_route_returns_shared_not_found_contract() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            "/api/v1/unknown",
            headers={"X-Request-Id": "not-found-request-id"},
        )

    body = response.json()
    assert response.status_code == 404
    assert body["error"] == {"code": "NOT_FOUND", "message": "Route not found"}
    assert body["requestId"] == "not-found-request-id"


@pytest.mark.asyncio
async def test_unsupported_method_returns_shared_error_contract() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            "/api/v1/knowledge/answer",
            headers={"X-Request-Id": "method-request-id"},
        )

    body = response.json()
    assert response.status_code == 405
    assert body["error"] == {
        "code": "METHOD_NOT_ALLOWED",
        "message": "Method not allowed",
    }
    assert body["requestId"] == "method-request-id"
    assert response.headers["Allow"] == "POST"


@pytest.mark.asyncio
async def test_answer_rejects_whitespace_only_query() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/knowledge/answer",
            headers=GUEST_HEADERS,
            json={"query": "   "},
        )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.asyncio
async def test_answer_distinguishes_malformed_json() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/knowledge/answer",
            headers={
                "Content-Type": "application/json",
                **GUEST_HEADERS,
            },
            content="{",
        )

    assert response.status_code == 400
    assert response.json()["error"] == {
        "code": "INVALID_JSON",
        "message": "Request body contains invalid JSON",
    }


@pytest.mark.asyncio
async def test_unexpected_error_keeps_request_id_header(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fail_answer(actor: ActorContext, query: str, top_k: int) -> KnowledgeAnswer:
        raise RuntimeError("test failure")

    monkeypatch.setattr(routes, "answer_knowledge", fail_answer)
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/knowledge/answer",
            headers={
                "X-AI-Service-Key": SERVICE_KEY,
                "X-Actor-Id": "guest",
                "X-Knowledge-Audiences": "customer,shared",
                "X-Request-Id": "failure-request-id",
            },
            json={"query": "Where do I return the costume?"},
        )

    assert response.status_code == 500
    assert response.headers["X-Request-Id"] == "failure-request-id"
    assert response.json()["requestId"] == "failure-request-id"
    assert response.json()["error"]["code"] == "INTERNAL_SERVER_ERROR"


def test_openapi_matches_runtime_error_and_security_contracts() -> None:
    schema = app.openapi()
    paths = schema["paths"]
    answer = paths["/api/v1/knowledge/answer"]["post"]
    search = paths["/api/v1/knowledge/search"]["post"]

    assert "400" in answer["responses"]
    assert "422" not in answer["responses"]
    assert "422" not in search["responses"]
    assert answer["security"] == [{"InternalServiceKey": []}]
    assert search["security"] == [{"InternalServiceKey": []}]
    actor_headers = {
        parameter["name"]: parameter
        for parameter in answer["parameters"]
        if parameter.get("in") == "header"
    }
    assert actor_headers["x-actor-id"]["required"] is True
    assert actor_headers["x-knowledge-audiences"]["required"] is True
    assert "ErrorResponse" in schema["components"]["schemas"]
    assert "success" in schema["components"]["schemas"]["ErrorResponse"]["required"]
