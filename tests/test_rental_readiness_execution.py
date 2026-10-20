import json
from datetime import UTC, datetime
from hashlib import sha256
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.agent_tools import runtime
from app.agent_tools.execution import validate_frozen_action
from app.agent_tools.models import AgentCaseState, AgentToolExecutionResult, ToolExecutionStatus
from app.agent_tools.runtime import _readiness_action_from_context
from app.config import get_settings
from app.errors import AppError
from app.models import ActorContext

CURRENT_UNIT_ID = "00000000-0000-0000-0000-000000000013"
REPLACEMENT_UNIT_ID = "00000000-0000-0000-0000-000000000021"
ORDER_ID = "00000000-0000-0000-0000-000000000010"
ORDER_ITEM_ID = "00000000-0000-0000-0000-000000000011"
BRANCH_ID = "00000000-0000-0000-0000-000000000030"
AFFECTED_ORDER_ID = "00000000-0000-0000-0000-000000000012"


def _inputs(
    rule_code: str = "ALLOCATED_UNIT_NOT_READY",
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], str]:
    option_id = f"reallocate:{REPLACEMENT_UNIT_ID}"
    affected_entity_id = (
        CURRENT_UNIT_ID if rule_code == "ALLOCATED_UNIT_NOT_READY" else AFFECTED_ORDER_ID
    )
    case = {
        "branch_id": BRANCH_ID,
        "finding": {
            "rule_code": rule_code,
            "unit_id": CURRENT_UNIT_ID,
            "affected_entity_id": affected_entity_id,
        },
    }
    analysis = {
        "recommended_option_id": option_id,
        "options": [
            {
                "optionId": option_id,
                "optionType": "REALLOCATE_SAME_BRANCH",
                "targetUnit": {"id": REPLACEMENT_UNIT_ID, "unitCode": "A-01"},
                "actionPreview": {
                    "toolName": "reallocate_rental_item",
                    "arguments": {
                        "orderId": ORDER_ID,
                        "orderItemId": ORDER_ITEM_ID,
                        "unitId": REPLACEMENT_UNIT_ID,
                    },
                    "expectedVersion": 7,
                },
            }
        ],
    }
    context = {
        "ruleCode": rule_code,
        "primaryOrder": {
            "id": ORDER_ID,
            "pickupBranchId": BRANCH_ID,
            "version": 7,
            "item": {"id": ORDER_ITEM_ID},
        },
        "affectedOrder": (
            None if rule_code == "ALLOCATED_UNIT_NOT_READY" else {"id": AFFECTED_ORDER_ID}
        ),
        "currentUnit": {"id": CURRENT_UNIT_ID},
        "replacementUnits": [{"id": REPLACEMENT_UNIT_ID, "unitCode": "A-01"}],
    }
    return case, analysis, context, option_id


def test_allocated_unit_not_ready_can_prepare_reallocation_without_affected_order() -> None:
    case, analysis, context, option_id = _inputs()

    selected_option_id, arguments, version = _readiness_action_from_context(
        case=case,
        analysis=analysis,
        context=context,
    )

    assert selected_option_id == option_id
    assert arguments == {
        "orderId": ORDER_ID,
        "orderItemId": ORDER_ITEM_ID,
        "unitId": REPLACEMENT_UNIT_ID,
        "reason": "Rental readiness recommendation",
    }
    assert version == 7


@pytest.mark.asyncio
async def test_prepare_readiness_confirmation_serializes_database_timestamp(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AGENT_READINESS_EXECUTION_ENABLED", "true")
    get_settings.cache_clear()
    case_id = uuid4()
    actor_id = uuid4()
    analysis_id = uuid4()
    finding_id = uuid4()
    case, analysis, context, option_id = _inputs()
    case.update(
        {
            "case_type": "RENTAL_READINESS",
            "state": AgentCaseState.PLAN_READY,
            "version": 4,
        }
    )
    analysis.update(
        {
            "analysis_id": str(analysis_id),
            "source_observed_at": datetime(2026, 10, 19, 9, tzinfo=UTC),
        }
    )
    overview = {
        **case,
        "analysis": analysis,
        "finding": {
            **case["finding"],
            "finding_id": str(finding_id),
            "status": "OPEN",
            "dedupe_key": "readiness:one",
            "primary_entity_id": ORDER_ID,
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
                data={**context, "riskStillPresent": True, "observedAt": "2026-10-19T10:00:00Z"},
            )
        ),
    )
    monkeypatch.setattr(runtime, "create_readiness_confirmation", fake_create_confirmation)
    monkeypatch.setattr(runtime, "append_turn", AsyncMock())
    monkeypatch.setattr(runtime, "mark_run", AsyncMock())
    monkeypatch.setattr(runtime, "_case_response", AsyncMock(return_value=SimpleNamespace()))

    await runtime.prepare_readiness_confirmation(
        ActorContext(
            user_id=str(actor_id),
            audiences=("staff_internal", "shared"),
            agent_manage_branch_ids=(uuid4(),),
        ),
        case_id,
        analysis_id,
        4,
    )

    snapshot = captured["action_snapshot"]
    assert isinstance(snapshot, dict)
    assert snapshot["recommendation"]["optionId"] == option_id
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


def test_previous_rental_rule_still_requires_matching_affected_order() -> None:
    case, analysis, context, option_id = _inputs("PREVIOUS_RENTAL_NOT_RETURNED")

    selected_option_id, _, _ = _readiness_action_from_context(
        case=case,
        analysis=analysis,
        context=context,
    )

    assert selected_option_id == option_id


@pytest.mark.parametrize("changed_field", ["rule", "affected_unit"])
def test_allocated_unit_not_ready_rejects_stale_identity(changed_field: str) -> None:
    case, analysis, context, _ = _inputs()
    if changed_field == "rule":
        context["ruleCode"] = "PREVIOUS_RENTAL_NOT_RETURNED"
    else:
        case["finding"]["affected_entity_id"] = AFFECTED_ORDER_ID

    with pytest.raises(AppError) as error:
        _readiness_action_from_context(case=case, analysis=analysis, context=context)

    assert error.value.code == "AGENT_RECOMMENDATION_STALE"


@pytest.mark.asyncio
async def test_capacity_confirmation_is_rejected_before_live_or_write_tools(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AGENT_READINESS_EXECUTION_ENABLED", "true")
    get_settings.cache_clear()

    async def fake_authorized_case(*_: object, **__: object) -> dict[str, object]:
        return {"case_type": "OPERATIONAL_CAPACITY"}

    live_tool = AsyncMock(side_effect=AssertionError("live tool must not run"))
    monkeypatch.setattr(runtime, "_authorized_case", fake_authorized_case)
    monkeypatch.setattr(runtime, "observe_live_tool", live_tool)

    actor = ActorContext(user_id=str(uuid4()), audiences=("staff_internal", "shared"))
    with pytest.raises(AppError) as error:
        await runtime.prepare_readiness_confirmation(actor, uuid4(), uuid4(), 1)

    assert error.value.code == "AGENT_RECOMMENDATION_NOT_EXECUTABLE"
    live_tool.assert_not_awaited()
    get_settings.cache_clear()
