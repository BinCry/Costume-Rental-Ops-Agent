from collections.abc import Iterator
from uuid import UUID, uuid4

import httpx
import pytest

from app.agent_tools import routes
from app.config import get_settings
from app.main import app
from app.models import ActorContext, AgentCaseResponse, AgentEvidence

SERVICE_KEY = "test-ai-internal-key-at-least-32-characters"
ACTOR_ID = str(uuid4())
CASE_ID = uuid4()
BRANCH_ID = uuid4()
HEADERS = {
    "X-AI-Service-Key": SERVICE_KEY,
    "X-Actor-Id": ACTOR_ID,
    "X-Knowledge-Audiences": "customer,shared",
    "X-Case-Branch-Id": str(BRANCH_ID),
}


@pytest.fixture(autouse=True)
def configure_internal_auth(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setenv("AI_INTERNAL_API_KEY", SERVICE_KEY)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def response() -> AgentCaseResponse:
    return AgentCaseResponse(
        case_id=CASE_ID,
        state="SUCCEEDED",
        message="Thông tin đã được trả lời từ nguồn đáng tin cậy.",
        evidence=[
            AgentEvidence(
                source_type="knowledge",
                source_id="rental/order-lifecycle",
                citation="knowledge-base/rental/order-lifecycle.md",
            )
        ],
        completed=True,
    )


@pytest.mark.asyncio
async def test_agent_message_requires_authenticated_actor() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        result = await client.post(
            "/api/v1/agent/messages",
            headers={
                "X-AI-Service-Key": SERVICE_KEY,
                "X-Actor-Id": "guest",
                "X-Knowledge-Audiences": "customer,shared",
            },
            json={"message": "Tình trạng đơn của tôi?", "branchId": str(BRANCH_ID)},
        )

    assert result.status_code == 401
    assert result.json()["error"]["code"] == "AUTHENTICATED_ACTOR_REQUIRED"


@pytest.mark.asyncio
async def test_agent_message_uses_trusted_actor_and_returns_standard_envelope(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    async def fake_answer(
        actor: ActorContext, message: str, case_id: object, branch_id: UUID
    ) -> AgentCaseResponse:
        captured.update(actor=actor, message=message, case_id=case_id, branch_id=branch_id)
        return response()

    monkeypatch.setattr(routes, "answer_agent_message", fake_answer)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        result = await client.post(
            "/api/v1/agent/messages",
            headers=HEADERS,
            json={"message": "Tình trạng đơn của tôi?", "branchId": str(BRANCH_ID)},
        )

    assert result.status_code == 200
    assert result.json()["data"]["result"]["caseId"] == str(CASE_ID)
    assert captured["actor"] == ActorContext(user_id=ACTOR_ID, audiences=("customer", "shared"))
    assert captured["message"] == "Tình trạng đơn của tôi?"
    assert captured["case_id"] is None
    assert captured["branch_id"] == BRANCH_ID


@pytest.mark.asyncio
async def test_agent_message_rejects_mismatched_branch(monkeypatch: pytest.MonkeyPatch) -> None:
    async def never_called(*_: object) -> AgentCaseResponse:
        raise AssertionError("branch mismatch must be blocked before runtime")

    monkeypatch.setattr(routes, "answer_agent_message", never_called)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        result = await client.post(
            "/api/v1/agent/messages",
            headers=HEADERS,
            json={"message": "Kiểm tra đơn", "branchId": str(uuid4())},
        )
    assert result.status_code == 403
    assert result.json()["error"]["code"] == "AGENT_BRANCH_MISMATCH"


@pytest.mark.asyncio
async def test_agent_case_rejects_missing_service_key() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        result = await client.get(
            f"/api/v1/agent/cases/{CASE_ID}",
            headers={
                "X-Actor-Id": ACTOR_ID,
                "X-Knowledge-Audiences": "customer,shared",
            },
        )

    assert result.status_code == 401
    assert result.json()["error"]["code"] == "INVALID_SERVICE_CREDENTIALS"


def test_agent_openapi_has_internal_service_security() -> None:
    paths = app.openapi()["paths"]
    message = paths["/api/v1/agent/messages"]["post"]
    case = paths["/api/v1/agent/cases/{case_id}"]["get"]

    assert message["security"] == [{"InternalServiceKey": []}]
    assert case["security"] == [{"InternalServiceKey": []}]


@pytest.mark.asyncio
async def test_agent_approval_uses_trusted_actor(monkeypatch: pytest.MonkeyPatch) -> None:
    approval_id = uuid4()
    captured: dict[str, object] = {}

    async def fake_decide(
        actor: ActorContext,
        approval: UUID,
        approve: bool,
        reason: str | None = None,
        branch_id: UUID | None = None,
    ) -> AgentCaseResponse:
        captured.update(
            actor=actor, approval=approval, approve=approve, reason=reason, branch_id=branch_id
        )
        return response()

    monkeypatch.setattr(routes, "decide_case_approval", fake_decide)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        result = await client.post(
            f"/api/v1/agent/approvals/{approval_id}/approve",
            headers=HEADERS,
            json={"reason": "Reviewed"},
        )

    assert result.status_code == 200
    assert captured["approval"] == approval_id
    assert captured["approve"] is True
    assert captured["reason"] == "Reviewed"
    assert captured["actor"] == ActorContext(user_id=ACTOR_ID, audiences=("customer", "shared"))
    assert captured["branch_id"] == BRANCH_ID
