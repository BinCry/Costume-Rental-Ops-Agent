import json
from datetime import UTC, datetime
from hashlib import sha256
from uuid import uuid4

import pytest

from app.agent_tools import execution
from app.agent_tools.client import ToolInvocationError
from app.agent_tools.models import AgentToolExecutionResult, ToolExecutionStatus
from app.models import ActorContext


def frozen(tool_name: str, arguments: dict[str, object], expected_version: int | None = None):
    unsigned = {
        "toolName": tool_name,
        "arguments": arguments,
        "expectedVersion": expected_version,
        "readbackTool": "get_rental_order",
    }
    unsigned_hash = sha256(
        json.dumps(unsigned, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    snapshot = {**unsigned, "payloadHash": unsigned_hash}
    stored_hash = sha256(
        json.dumps(snapshot, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return snapshot, stored_hash


@pytest.mark.asyncio
async def test_versioned_write_succeeds_only_after_readback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    order_id = str(uuid4())
    snapshot, stored_hash = frozen(
        "extend_rental_order",
        {"orderId": order_id, "newDueAt": "2026-10-20T00:00:00Z", "reason": "Customer request"},
        4,
    )
    calls: list[str] = []

    async def fake_call(**kwargs):
        calls.append(kwargs["tool_name"])
        data = (
            {"id": order_id, "version": 5}
            if len(calls) == 1
            else {
                "id": order_id,
                "plannedDueAt": "2026-10-20T00:00:00Z",
                "version": 5,
            }
        )
        return AgentToolExecutionResult(
            status=ToolExecutionStatus.OK,
            data=data,
            observed_at=datetime.now(UTC),
        )

    monkeypatch.setattr(execution, "_call", fake_call)
    result = await execution.execute_frozen_action(
        actor=ActorContext(user_id=str(uuid4()), audiences=("staff_internal",)),
        case_id=uuid4(),
        snapshot=snapshot,
        stored_hash=stored_hash,
    )

    assert result.status is ToolExecutionStatus.OK
    assert calls == ["extend_rental_order", "get_rental_order"]
    assert result.evidence is not None


@pytest.mark.asyncio
async def test_unknown_write_is_reconciled_without_retry(monkeypatch: pytest.MonkeyPatch) -> None:
    order_id = str(uuid4())
    snapshot, stored_hash = frozen(
        "cancel_rental_order",
        {"orderId": order_id, "reason": "Customer request"},
        7,
    )
    calls: list[str] = []

    async def fake_call(**kwargs):
        calls.append(kwargs["tool_name"])
        if len(calls) == 1:
            raise ToolInvocationError("TOOL_OUTCOME_UNKNOWN", "timeout")
        return AgentToolExecutionResult(
            status=ToolExecutionStatus.OK,
            data={"id": order_id, "status": "CANCELLED", "version": 8},
            observed_at=datetime.now(UTC),
        )

    monkeypatch.setattr(execution, "_call", fake_call)
    result = await execution.execute_frozen_action(
        actor=ActorContext(user_id=str(uuid4()), audiences=("staff_internal",)),
        case_id=uuid4(),
        snapshot=snapshot,
        stored_hash=stored_hash,
    )

    assert result.status is ToolExecutionStatus.OK
    assert calls == ["cancel_rental_order", "get_rental_order"]
