from collections.abc import Iterator
from datetime import UTC, datetime
from uuid import UUID, uuid4

import httpx
import pytest

from app.agent_tools import routes
from app.config import get_settings
from app.main import app
from app.models import (
    ActorContext,
    AgentCaseResponse,
    AgentEvidence,
    AgentFindingResolveData,
    AgentFindingResolveInput,
    AgentFindingUpsertInput,
    AgentInternalFindingListData,
)

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
OPERATIONAL_HEADERS = {
    **HEADERS,
    "X-Knowledge-Audiences": "staff_internal,shared",
    "X-Agent-Read-Branch-Ids": str(BRANCH_ID),
    "X-Agent-Manage-Branch-Ids": str(BRANCH_ID),
    "X-Agent-Read-All": "false",
    "X-Agent-Manage-All": "false",
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
    assert paths["/api/v1/agent/internal/findings"]["get"]["security"] == [
        {"InternalServiceKey": []}
    ]
    assert paths["/api/v1/agent/internal/findings/resolve"]["post"]["security"] == [
        {"InternalServiceKey": []}
    ]


@pytest.mark.asyncio
async def test_agent_case_queue_delegates_filters_and_trusted_scope(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    async def fake_list(actor: ActorContext, **filters: object) -> object:
        captured.update(actor=actor, filters=filters)
        from app.models import AgentCaseListData

        return AgentCaseListData(items=[response()], next_cursor="next-page")

    monkeypatch.setattr(routes, "list_agent_cases", fake_list)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        result = await client.get(
            "/api/v1/agent/cases",
            headers=OPERATIONAL_HEADERS,
            params={
                "branchId": str(BRANCH_ID),
                "state": "NEW",
                "ownership": "unassigned",
                "cursor": "cursor-1",
                "limit": 10,
            },
        )

    assert result.status_code == 200
    assert result.json()["data"]["nextCursor"] == "next-page"
    actor = captured["actor"]
    assert isinstance(actor, ActorContext)
    assert actor.agent_read_branch_ids == (BRANCH_ID,)
    assert captured["filters"] == {
        "branch_id": BRANCH_ID,
        "state": routes.AgentCaseState.NEW,
        "ownership": "unassigned",
        "cursor": "cursor-1",
        "limit": 10,
    }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("action", "runtime_name"),
    [("claim", "claim_agent_case"), ("release", "release_agent_case")],
)
async def test_agent_case_ownership_routes_delegate_trusted_actor(
    monkeypatch: pytest.MonkeyPatch,
    action: str,
    runtime_name: str,
) -> None:
    captured: dict[str, object] = {}

    async def fake_action(
        actor: ActorContext, case_id: UUID, expected_version: int
    ) -> AgentCaseResponse:
        captured.update(actor=actor, case_id=case_id, expected_version=expected_version)
        return response()

    monkeypatch.setattr(routes, runtime_name, fake_action)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        result = await client.post(
            f"/api/v1/agent/cases/{CASE_ID}/{action}",
            headers=OPERATIONAL_HEADERS,
            json={"expectedVersion": 4},
        )

    assert result.status_code == 200
    assert captured["case_id"] == CASE_ID
    assert captured["expected_version"] == 4
    actor = captured["actor"]
    assert isinstance(actor, ActorContext)
    assert actor.agent_manage_branch_ids == (BRANCH_ID,)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "rule_code",
    [
        "PREVIOUS_RENTAL_NOT_RETURNED",
        "ALLOCATED_UNIT_NOT_READY",
        "ORDER_PREPARATION_DELAYED",
        "RENTAL_RETURN_OVERDUE",
        "OPERATIONAL_CAPACITY_SHORTFALL",
    ],
)
async def test_internal_finding_upsert_requires_only_service_auth_and_delegates(
    monkeypatch: pytest.MonkeyPatch,
    rule_code: str,
) -> None:
    captured: dict[str, object] = {}

    async def fake_upsert(body: object) -> AgentCaseResponse:
        captured["body"] = body
        return response()

    monkeypatch.setattr(routes, "upsert_agent_finding", fake_upsert)
    payload = {
        "ruleCode": rule_code,
        "ruleVersion": "v1",
        "dedupeKey": "risk:one",
        "branchId": str(BRANCH_ID),
        "primaryEntityId": str(uuid4()),
        "affectedEntityId": (
            None
            if rule_code
            in {
                "ORDER_PREPARATION_DELAYED",
                "RENTAL_RETURN_OVERDUE",
                "OPERATIONAL_CAPACITY_SHORTFALL",
            }
            else str(uuid4())
        ),
        "unitId": (
            None
            if rule_code
            in {
                "ORDER_PREPARATION_DELAYED",
                "RENTAL_RETURN_OVERDUE",
                "OPERATIONAL_CAPACITY_SHORTFALL",
            }
            else str(uuid4())
        ),
        "windowStart": "2026-10-16T08:00:00+07:00",
        "windowEnd": "2026-10-16T10:00:00+07:00",
        "severity": "HIGH",
        "deadlineAt": "2026-10-16T09:30:00+07:00",
        "evidence": {"source": "test"},
        "observedAt": "2026-10-16T07:55:00+07:00",
    }
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        result = await client.post(
            "/api/v1/agent/internal/findings/upsert",
            headers={"X-AI-Service-Key": SERVICE_KEY},
            json=payload,
        )

    assert result.status_code == 200
    body = captured["body"]
    assert isinstance(body, AgentFindingUpsertInput)
    assert body.rule_code == rule_code
    assert body.dedupe_key == "risk:one"
    assert body.branch_id == BRANCH_ID
    assert body.observed_at is not None


@pytest.mark.asyncio
async def test_internal_finding_list_requires_only_service_auth_and_delegates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    async def fake_list(**filters: object) -> AgentInternalFindingListData:
        captured.update(filters)
        return AgentInternalFindingListData(items=[], next_cursor="next")

    monkeypatch.setattr(routes, "list_agent_findings", fake_list)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        result = await client.get(
            "/api/v1/agent/internal/findings",
            headers={"X-AI-Service-Key": SERVICE_KEY},
            params={
                "ruleCode": "PREVIOUS_RENTAL_NOT_RETURNED",
                "status": "OPEN",
                "cursor": "2",
                "limit": 25,
            },
        )

    assert result.status_code == 200
    assert result.json()["data"]["nextCursor"] == "next"
    assert captured == {
        "rule_code": "PREVIOUS_RENTAL_NOT_RETURNED",
        "status": "OPEN",
        "cursor": "2",
        "limit": 25,
    }


@pytest.mark.asyncio
async def test_internal_finding_list_accepts_allocated_unit_not_ready_rule(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    async def fake_list(**filters: object) -> AgentInternalFindingListData:
        captured.update(filters)
        return AgentInternalFindingListData(items=[])

    monkeypatch.setattr(routes, "list_agent_findings", fake_list)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        result = await client.get(
            "/api/v1/agent/internal/findings",
            headers={"X-AI-Service-Key": SERVICE_KEY},
            params={"ruleCode": "ALLOCATED_UNIT_NOT_READY", "status": "OPEN"},
        )

    assert result.status_code == 200
    assert captured["rule_code"] == "ALLOCATED_UNIT_NOT_READY"


@pytest.mark.asyncio
async def test_internal_finding_resolve_requires_only_service_auth_and_delegates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    async def fake_resolve(body: AgentFindingResolveInput) -> AgentFindingResolveData:
        captured["body"] = body
        return AgentFindingResolveData(
            case_id=CASE_ID,
            dedupe_key=body.dedupe_key,
            outcome="RESOLVED",
            source_observed_at=body.observed_at,
        )

    monkeypatch.setattr(routes, "resolve_agent_finding", fake_resolve)
    payload = {
        "dedupeKey": "risk:one",
        "ruleCode": "PREVIOUS_RENTAL_NOT_RETURNED",
        "observedAt": "2026-10-16T08:30:00+07:00",
        "resolutionCode": "RISK_NO_LONGER_PRESENT",
        "evidence": {"reason": "returned"},
    }
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        result = await client.post(
            "/api/v1/agent/internal/findings/resolve",
            headers={"X-AI-Service-Key": SERVICE_KEY},
            json=payload,
        )

    assert result.status_code == 200
    assert result.json()["data"]["outcome"] == "RESOLVED"
    assert isinstance(captured["body"], AgentFindingResolveInput)


def test_finding_observed_at_requires_timezone_and_normalizes_utc() -> None:
    common = {
        "ruleCode": "PREVIOUS_RENTAL_NOT_RETURNED",
        "observedAt": "2026-10-16T08:30:00+07:00",
    }
    resolved = AgentFindingResolveInput.model_validate(
        {
            **common,
            "dedupeKey": "risk:timezone",
            "resolutionCode": "RISK_NO_LONGER_PRESENT",
        }
    )
    assert resolved.observed_at == datetime(2026, 10, 16, 1, 30, tzinfo=UTC)

    with pytest.raises(ValueError, match="timezone offset"):
        AgentFindingResolveInput.model_validate(
            {
                **common,
                "dedupeKey": "risk:timezone",
                "observedAt": "2026-10-16T08:30:00",
                "resolutionCode": "RISK_NO_LONGER_PRESENT",
            }
        )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("path", "payload"),
    [
        (
            "/api/v1/agent/internal/findings/upsert",
            {
                "ruleCode": "PREVIOUS_RENTAL_NOT_RETURNED",
                "ruleVersion": "v1",
                "dedupeKey": "risk:naive-upsert",
                "branchId": str(BRANCH_ID),
                "primaryEntityId": str(uuid4()),
                "affectedEntityId": str(uuid4()),
                "unitId": str(uuid4()),
                "windowStart": "2026-10-16T08:00:00+07:00",
                "windowEnd": "2026-10-16T10:00:00+07:00",
                "severity": "HIGH",
                "deadlineAt": "2026-10-16T09:30:00+07:00",
                "observedAt": "2026-10-16T08:30:00",
            },
        ),
        (
            "/api/v1/agent/internal/findings/resolve",
            {
                "dedupeKey": "risk:naive-resolve",
                "ruleCode": "PREVIOUS_RENTAL_NOT_RETURNED",
                "observedAt": "2026-10-16T08:30:00",
                "resolutionCode": "RISK_NO_LONGER_PRESENT",
            },
        ),
    ],
)
async def test_internal_finding_routes_reject_naive_observed_at(
    path: str, payload: dict[str, object]
) -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        result = await client.post(
            path,
            headers={"X-AI-Service-Key": SERVICE_KEY},
            json=payload,
        )
    assert result.status_code == 400
    assert result.json()["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.asyncio
async def test_internal_finding_upsert_rejects_invalid_service_key() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        result = await client.post(
            "/api/v1/agent/internal/findings/upsert",
            headers={"X-AI-Service-Key": "wrong-key"},
            json={},
        )

    assert result.status_code == 401
    assert result.json()["error"]["code"] == "INVALID_SERVICE_CREDENTIALS"


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
