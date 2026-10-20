import json
from datetime import UTC, datetime
from hashlib import sha256
from typing import Any
from uuid import uuid4

import pytest

from app.agent_tools import execution
from app.agent_tools.client import ToolInvocationError
from app.agent_tools.models import AgentToolExecutionResult, ToolExecutionStatus
from app.models import ActorContext


@pytest.mark.parametrize(
    ("tool_name", "arguments", "readback_tool", "readback_data"),
    [
        (
            "create_unit_block",
            {
                "unitId": "10000000-0000-4000-8000-000000000001",
                "blockType": "CLEANING",
                "blockedFrom": "2026-10-16T08:00:00.000Z",
                "blockedUntil": "2026-10-16T10:00:00.000Z",
                "reason": "Scheduled cleaning",
            },
            "get_unit_block",
            {
                "id": "10000000-0000-4000-8000-000000000011",
                "unitId": "10000000-0000-4000-8000-000000000001",
                "blockType": "CLEANING",
                "blockedFrom": "2026-10-16T08:00:00Z",
                "blockedUntil": "2026-10-16T10:00:00Z",
                "reason": "Scheduled cleaning",
                "status": "PLANNED",
            },
        ),
        (
            "update_unit_block",
            {
                "blockId": "10000000-0000-4000-8000-000000000011",
                "reason": "Updated reason",
                "expectedUpdatedAt": "2026-10-15T08:00:00Z",
            },
            "get_unit_block",
            {"id": "10000000-0000-4000-8000-000000000011", "reason": "Updated reason"},
        ),
        (
            "cancel_unit_block",
            {"blockId": "10000000-0000-4000-8000-000000000011", "reason": "Cancel"},
            "get_unit_block",
            {"id": "10000000-0000-4000-8000-000000000011", "status": "CANCELLED"},
        ),
        (
            "extend_rental_order",
            {
                "orderId": "10000000-0000-4000-8000-000000000002",
                "newDueAt": "2026-10-20T08:00:00Z",
                "reason": "Requested",
            },
            "get_rental_order",
            {
                "id": "10000000-0000-4000-8000-000000000002",
                "plannedDueAt": "2026-10-20T08:00:00.000Z",
            },
        ),
        (
            "reallocate_rental_item",
            {
                "orderId": "10000000-0000-4000-8000-000000000002",
                "orderItemId": "10000000-0000-4000-8000-000000000003",
                "unitId": "10000000-0000-4000-8000-000000000004",
                "reason": "Replacement",
            },
            "get_rental_order",
            {
                "id": "10000000-0000-4000-8000-000000000002",
                "items": [
                    {
                        "id": "10000000-0000-4000-8000-000000000003",
                        "unitId": "10000000-0000-4000-8000-000000000004",
                    }
                ],
            },
        ),
        (
            "cancel_rental_order",
            {"orderId": "10000000-0000-4000-8000-000000000002", "reason": "Cancel"},
            "get_rental_order",
            {"id": "10000000-0000-4000-8000-000000000002", "status": "CANCELLED"},
        ),
        (
            "create_stock_transfer",
            {
                "fromBranchId": "10000000-0000-4000-8000-000000000005",
                "toBranchId": "10000000-0000-4000-8000-000000000006",
                "unitIds": ["10000000-0000-4000-8000-000000000004"],
            },
            "get_stock_transfer",
            {
                "id": "10000000-0000-4000-8000-000000000012",
                "status": "REQUESTED",
                "fromBranchId": "10000000-0000-4000-8000-000000000005",
                "toBranchId": "10000000-0000-4000-8000-000000000006",
                "items": [{"unitId": "10000000-0000-4000-8000-000000000004"}],
            },
        ),
        (
            "approve_stock_transfer",
            {"transferId": "10000000-0000-4000-8000-000000000012"},
            "get_stock_transfer",
            {"id": "10000000-0000-4000-8000-000000000012", "status": "APPROVED"},
        ),
        (
            "reject_stock_transfer",
            {"transferId": "10000000-0000-4000-8000-000000000012", "reason": "Reject"},
            "get_stock_transfer",
            {"id": "10000000-0000-4000-8000-000000000012", "status": "REJECTED"},
        ),
        (
            "create_payment_checkout",
            {
                "orderId": "10000000-0000-4000-8000-000000000002",
                "purpose": "RENTAL",
                "amountVnd": 100000,
            },
            "get_payment_by_idempotency_key",
            {
                "orderId": "10000000-0000-4000-8000-000000000002",
                "purpose": "RENTAL",
                "amountVnd": 100000,
            },
        ),
        (
            "request_refund",
            {
                "paymentId": "10000000-0000-4000-8000-000000000009",
                "amountVnd": 50000,
                "reason": "Overpayment",
            },
            "get_refund_by_idempotency_key",
            {
                "paymentId": "10000000-0000-4000-8000-000000000009",
                "amountVnd": 50000,
                "status": "REQUESTED",
            },
        ),
    ],
)
def test_every_write_has_a_matching_readback_postcondition(
    tool_name: str,
    arguments: dict[str, object],
    readback_tool: str,
    readback_data: dict[str, object],
) -> None:
    snapshot = {"toolName": tool_name, "arguments": arguments}
    write_result = AgentToolExecutionResult(
        status=ToolExecutionStatus.OK,
        data={"id": readback_data.get("id")},
        observed_at=datetime.now(UTC),
    )

    readback = execution._readback_arguments(snapshot, write_result, "agent:test")

    assert readback is not None
    assert readback[0] == readback_tool
    assert execution._postcondition(snapshot, readback_data)


def frozen(
    tool_name: str, arguments: dict[str, object], expected_version: int | None = None
) -> tuple[dict[str, Any], str]:
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

    async def fake_call(**kwargs: Any) -> AgentToolExecutionResult:
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

    async def fake_call(**kwargs: Any) -> AgentToolExecutionResult:
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


@pytest.mark.asyncio
async def test_resumed_write_reads_back_without_resending_prior_write(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    order_id = str(uuid4())
    item_id = str(uuid4())
    unit_id = str(uuid4())
    snapshot, stored_hash = frozen(
        "reallocate_rental_item",
        {
            "orderId": order_id,
            "orderItemId": item_id,
            "unitId": unit_id,
            "reason": "Rental readiness recommendation",
        },
        4,
    )
    calls: list[str] = []

    async def fake_prior(_: object) -> dict[str, object]:
        return {"status": "OK", "outcome": {}}

    async def fake_call(**kwargs: Any) -> AgentToolExecutionResult:
        calls.append(kwargs["tool_name"])
        return AgentToolExecutionResult(
            status=ToolExecutionStatus.OK,
            data={"id": order_id, "items": [{"id": item_id, "unitId": unit_id}]},
            observed_at=datetime.now(UTC),
        )

    monkeypatch.setattr(execution, "get_tool_call", fake_prior)
    monkeypatch.setattr(execution, "_call", fake_call)
    result = await execution.execute_frozen_action(
        actor=ActorContext(user_id=str(uuid4()), audiences=("staff_internal",)),
        case_id=uuid4(),
        snapshot=snapshot,
        stored_hash=stored_hash,
    )

    assert result.status is ToolExecutionStatus.OK
    assert calls == ["get_rental_order"]
