import json
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import httpx
import pytest
from pydantic import ValidationError

from app.agent_tools import routes, runtime
from app.agent_tools.execution import _postcondition, _readback_arguments, validate_frozen_action
from app.agent_tools.guard import validate_tool_arguments
from app.agent_tools.models import AgentCaseState, AgentToolExecutionResult, ToolExecutionStatus
from app.config import get_settings
from app.main import app
from app.models import (
    ActorContext,
    AgentCaseResponse,
    AgentOverdueFollowUpConfirmationInput,
)


def _payload(outcome: str = "PROMISED_RETURN") -> dict[str, object]:
    occurred_at = datetime.now(UTC) - timedelta(minutes=5)
    payload: dict[str, object] = {
        "analysisId": str(uuid4()),
        "expectedVersion": 4,
        "channel": "PHONE",
        "outcome": outcome,
        "occurredAt": occurred_at.isoformat(),
    }
    if outcome == "PROMISED_RETURN":
        payload["promisedReturnAt"] = (occurred_at + timedelta(hours=2)).isoformat()
    if outcome in {"NO_ANSWER", "REQUESTED_EXTENSION", "REFUSED_RETURN"}:
        payload["nextFollowUpAt"] = (occurred_at + timedelta(hours=1)).isoformat()
    return payload


@pytest.mark.parametrize(
    "outcome",
    [
        "PROMISED_RETURN",
        "NO_ANSWER",
        "REQUESTED_EXTENSION",
        "REFUSED_RETURN",
        "CONTACTED",
        "OTHER",
    ],
)
def test_overdue_follow_up_input_accepts_exact_outcome_shapes(outcome: str) -> None:
    body = AgentOverdueFollowUpConfirmationInput.model_validate(_payload(outcome))
    assert body.outcome == outcome
    assert body.occurred_at.tzinfo is not None


@pytest.mark.parametrize(
    ("outcome", "missing_field"),
    [
        ("PROMISED_RETURN", "promisedReturnAt"),
        ("NO_ANSWER", "nextFollowUpAt"),
        ("REQUESTED_EXTENSION", "nextFollowUpAt"),
        ("REFUSED_RETURN", "nextFollowUpAt"),
    ],
)
def test_overdue_follow_up_input_requires_outcome_times(outcome: str, missing_field: str) -> None:
    payload = _payload(outcome)
    payload.pop(missing_field)
    with pytest.raises(ValidationError):
        AgentOverdueFollowUpConfirmationInput.model_validate(payload)


def test_overdue_follow_up_input_rejects_free_text_and_naive_or_future_times() -> None:
    payload = _payload("CONTACTED")
    payload["summary"] = "customer phone number"
    with pytest.raises(ValidationError):
        AgentOverdueFollowUpConfirmationInput.model_validate(payload)

    payload = _payload("CONTACTED")
    payload["occurredAt"] = datetime.now().replace(microsecond=0).isoformat()
    with pytest.raises(ValidationError):
        AgentOverdueFollowUpConfirmationInput.model_validate(payload)

    payload = _payload("CONTACTED")
    payload["occurredAt"] = (datetime.now(UTC) + timedelta(minutes=1)).isoformat()
    with pytest.raises(ValidationError):
        AgentOverdueFollowUpConfirmationInput.model_validate(payload)

    payload = _payload("PROMISED_RETURN")
    payload["promisedReturnAt"] = (datetime.now(UTC) - timedelta(minutes=1)).isoformat()
    with pytest.raises(ValidationError):
        AgentOverdueFollowUpConfirmationInput.model_validate(payload)


def test_overdue_follow_up_tool_validation_and_readback_contract() -> None:
    arguments = {
        "orderId": str(uuid4()),
        "channel": "PHONE",
        "outcome": "PROMISED_RETURN",
        "occurredAt": "2026-10-19T10:00:00+00:00",
        "promisedReturnAt": "2026-10-19T12:00:00+00:00",
    }
    validate_tool_arguments("record_overdue_follow_up", arguments)
    snapshot = {"toolName": "record_overdue_follow_up", "arguments": arguments}
    assert _readback_arguments(snapshot, None, "agent:key") == (
        "get_customer_interaction_by_idempotency_key",
        {"idempotencyKey": "agent:key"},
    )
    assert _postcondition(snapshot, arguments)
    assert not _postcondition(snapshot, {**arguments, "outcome": "NO_ANSWER"})


@pytest.mark.asyncio
async def test_prepare_overdue_follow_up_freezes_only_structured_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AGENT_CRM_WRITE_ENABLED", "true")
    get_settings.cache_clear()
    case_id = uuid4()
    actor_id = uuid4()
    branch_id = uuid4()
    order_id = uuid4()
    analysis_id = uuid4()
    finding_id = uuid4()
    body = AgentOverdueFollowUpConfirmationInput.model_validate(
        {**_payload("PROMISED_RETURN"), "analysisId": str(analysis_id)}
    )
    case = {
        "case_type": "RENTAL_RETURN",
        "state": AgentCaseState.PLAN_READY,
        "version": 4,
        "branch_id": str(branch_id),
    }
    overview = {
        **case,
        "analysis": {
            "analysis_id": str(analysis_id),
            "source_observed_at": datetime(2026, 10, 19, 9, tzinfo=UTC),
        },
        "finding": {
            "finding_id": str(finding_id),
            "status": "OPEN",
            "rule_code": "RENTAL_RETURN_OVERDUE",
            "dedupe_key": "overdue:one",
            "primary_entity_id": str(order_id),
        },
    }
    captured: dict[str, object] = {}

    async def fake_create_confirmation(**kwargs: object) -> dict[str, object]:
        captured.update(kwargs)
        return {"summary": kwargs["summary"]}

    monkeypatch.setattr(runtime, "_authorized_case", AsyncMock(return_value=case))
    monkeypatch.setattr(runtime, "get_case_overview_by_id", AsyncMock(return_value=overview))
    monkeypatch.setattr(runtime, "create_run", AsyncMock(return_value=uuid4()))
    monkeypatch.setattr(
        runtime,
        "observe_live_tool",
        AsyncMock(
            return_value=AgentToolExecutionResult(
                status=ToolExecutionStatus.OK,
                data={
                    "ruleCode": "RENTAL_RETURN_OVERDUE",
                    "riskStillPresent": True,
                    "observedAt": "2026-10-19T10:05:00+00:00",
                    "primaryOrder": {
                        "id": str(order_id),
                        "pickupBranchId": str(branch_id),
                    },
                },
            )
        ),
    )
    monkeypatch.setattr(runtime, "create_overdue_follow_up_confirmation", fake_create_confirmation)
    monkeypatch.setattr(runtime, "append_turn", AsyncMock())
    monkeypatch.setattr(runtime, "mark_run", AsyncMock())
    monkeypatch.setattr(runtime, "_case_response", AsyncMock(return_value=SimpleNamespace()))

    await runtime.prepare_overdue_follow_up_confirmation(
        ActorContext(
            user_id=str(actor_id),
            audiences=("staff_internal", "shared"),
            agent_manage_branch_ids=(branch_id,),
        ),
        case_id,
        body,
    )

    snapshot = captured["action_snapshot"]
    assert isinstance(snapshot, dict)
    assert snapshot["toolName"] == "record_overdue_follow_up"
    assert set(snapshot["arguments"]) == {
        "orderId",
        "channel",
        "outcome",
        "occurredAt",
        "promisedReturnAt",
    }
    assert "customerUserId" not in snapshot["arguments"]
    assert "summary" not in snapshot["arguments"]
    assert snapshot["recommendation"]["findingSourceObservedAt"] == (
        "2026-10-19T09:00:00+00:00"
    )
    stored_snapshot = json.loads(json.dumps(snapshot))
    stored_hash = sha256(
        json.dumps(
            stored_snapshot, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode()
    ).hexdigest()
    validate_frozen_action(stored_snapshot, stored_hash)
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_case4_confirmation_routes_only_to_dedicated_runtime(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    case_id = uuid4()
    confirmation_id = uuid4()
    branch_id = uuid4()
    actor = ActorContext(
        user_id=str(uuid4()),
        audiences=("staff_internal", "shared"),
        agent_manage_branch_ids=(branch_id,),
    )
    monkeypatch.setattr(
        runtime,
        "_authorized_case",
        AsyncMock(return_value={"case_type": "RENTAL_RETURN", "branch_id": str(branch_id)}),
    )
    dedicated = AsyncMock(return_value=SimpleNamespace())
    monkeypatch.setattr(runtime, "_decide_overdue_follow_up_confirmation_runtime", dedicated)

    await runtime.decide_case_confirmation(actor, case_id, confirmation_id, True)

    dedicated.assert_awaited_once()


@pytest.mark.asyncio
async def test_overdue_follow_up_prepare_route_validates_and_delegates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service_key = "test-ai-internal-key-at-least-32-characters"
    actor_id = uuid4()
    case_id = uuid4()
    monkeypatch.setenv("AI_INTERNAL_API_KEY", service_key)
    get_settings.cache_clear()
    captured: dict[str, object] = {}

    async def fake_prepare(
        actor: ActorContext,
        requested_case_id: object,
        body: AgentOverdueFollowUpConfirmationInput,
    ) -> AgentCaseResponse:
        captured.update(actor=actor, case_id=requested_case_id, body=body)
        return AgentCaseResponse(
            case_id=case_id,
            state="WAITING_CONFIRMATION",
            message="Confirmation ready",
            evidence=[],
            completed=False,
        )

    monkeypatch.setattr(routes, "prepare_overdue_follow_up_confirmation", fake_prepare)
    transport = httpx.ASGITransport(app=app)
    headers = {
        "X-AI-Service-Key": service_key,
        "X-Actor-Id": str(actor_id),
        "X-Knowledge-Audiences": "staff_internal,shared",
    }
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        result = await client.post(
            f"/api/v1/agent/cases/{case_id}/overdue-follow-ups/confirmations",
            headers=headers,
            json=_payload("NO_ANSWER"),
        )
        invalid = await client.post(
            f"/api/v1/agent/cases/{case_id}/overdue-follow-ups/confirmations",
            headers=headers,
            json={**_payload("CONTACTED"), "summary": "PII must not enter the snapshot"},
        )

    assert result.status_code == 200
    assert invalid.status_code == 400
    assert captured["case_id"] == case_id
    assert isinstance(captured["body"], AgentOverdueFollowUpConfirmationInput)
    get_settings.cache_clear()
