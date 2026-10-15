"""Deterministic execution and read-back for frozen agent actions."""

import json
from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from app.agent_tools.cases import finish_tool_call, start_tool_call
from app.agent_tools.client import AgentToolClient, ToolInvocationError
from app.agent_tools.guard import WRITE_TOOL_POLICIES, validate_tool_arguments
from app.agent_tools.models import (
    AgentToolExecutionRequest,
    AgentToolExecutionResult,
    ToolExecutionStatus,
)
from app.config import get_settings
from app.models import ActorContext, AgentEvidence


@dataclass(frozen=True)
class WriteExecution:
    status: ToolExecutionStatus
    message: str
    write_result: AgentToolExecutionResult | None = None
    readback_result: AgentToolExecutionResult | None = None
    evidence: AgentEvidence | None = None


def validate_frozen_action(snapshot: dict[str, Any], stored_hash: str) -> None:
    actual = sha256(
        json.dumps(snapshot, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    if actual != stored_hash:
        raise ValueError("Frozen action payload hash does not match the stored snapshot")
    unsigned = {key: value for key, value in snapshot.items() if key != "payloadHash"}
    unsigned_hash = sha256(
        json.dumps(unsigned, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    if snapshot.get("payloadHash") != unsigned_hash:
        raise ValueError("Frozen action content does not match its payloadHash")
    tool_name = snapshot.get("toolName")
    arguments = snapshot.get("arguments")
    if not isinstance(tool_name, str) or tool_name not in WRITE_TOOL_POLICIES:
        raise ValueError("Frozen action contains an unknown write tool")
    if not isinstance(arguments, dict):
        raise ValueError("Frozen action arguments are invalid")
    validate_tool_arguments(tool_name, arguments)
    expected_version = snapshot.get("expectedVersion")
    if WRITE_TOOL_POLICIES[tool_name].requires_expected_version and not isinstance(
        expected_version, int
    ):
        raise ValueError("Frozen action is missing expectedVersion")


def _client() -> AgentToolClient:
    settings = get_settings()
    if not settings.STUDIO_API_URL or not settings.AI_INTERNAL_API_KEY:
        raise ToolInvocationError(
            "TOOL_DEPENDENCY_UNAVAILABLE", "Studio tool API is not configured"
        )
    return AgentToolClient(
        base_url=settings.STUDIO_API_URL,
        service_key=settings.AI_INTERNAL_API_KEY,
        timeout_seconds=settings.AGENT_TOOL_TIMEOUT_SECONDS,
    )


async def _call(
    *,
    actor: ActorContext,
    case_id: UUID,
    tool_name: str,
    arguments: dict[str, Any],
    idempotency_key: str,
    expected_version: int | None = None,
    confirmation_id: UUID | None = None,
    approval_id: UUID | None = None,
    payload_hash: str | None = None,
) -> AgentToolExecutionResult:
    tool_call_id = uuid5(NAMESPACE_URL, f"{idempotency_key}:{tool_name}")
    request_id = uuid4()
    await start_tool_call(
        case_id,
        tool_call_id,
        tool_name,
        request_id,
        idempotency_key,
        payload_hash,
        expected_version,
        confirmation_id,
        approval_id,
    )
    invocation = AgentToolExecutionRequest(
        case_id=case_id,
        tool_call_id=tool_call_id,
        tool_name=tool_name,
        arguments=arguments,
        expected_version=expected_version,
        idempotency_key=idempotency_key,
        approval_id=approval_id,
    )
    try:
        result = await _client().execute(
            actor_id=actor.user_id,
            request_id=str(request_id),
            invocation=invocation,
        )
    except ToolInvocationError as error:
        await finish_tool_call(tool_call_id, error.code, {"status": error.code})
        raise
    await finish_tool_call(
        tool_call_id, result.status.value.upper(), result.model_dump(mode="json")
    )
    return result


def _readback_arguments(
    snapshot: dict[str, Any], write_result: AgentToolExecutionResult | None, idempotency_key: str
) -> tuple[str, dict[str, Any]] | None:
    tool_name = str(snapshot["toolName"])
    arguments = snapshot["arguments"]
    data = write_result.data if write_result is not None else None
    if tool_name in {"create_unit_block", "update_unit_block", "cancel_unit_block"}:
        block_id = data.get("id") if isinstance(data, dict) else arguments.get("blockId")
        return ("get_unit_block", {"blockId": block_id}) if block_id else None
    if tool_name in {"extend_rental_order", "reallocate_rental_item", "cancel_rental_order"}:
        return "get_rental_order", {"orderId": arguments["orderId"]}
    if tool_name in {"create_stock_transfer", "approve_stock_transfer", "reject_stock_transfer"}:
        transfer_id = data.get("id") if isinstance(data, dict) else arguments.get("transferId")
        return ("get_stock_transfer", {"transferId": transfer_id}) if transfer_id else None
    if tool_name == "create_payment_checkout":
        return "get_payment_by_idempotency_key", {"idempotencyKey": idempotency_key}
    if tool_name == "request_refund":
        return "get_refund_by_idempotency_key", {"idempotencyKey": idempotency_key}
    return None


def _same(left: Any, right: Any) -> bool:
    if isinstance(left, str) and isinstance(right, str):
        try:
            return datetime.fromisoformat(left.replace("Z", "+00:00")) == datetime.fromisoformat(
                right.replace("Z", "+00:00")
            )
        except ValueError:
            pass
    return str(left) == str(right)


def _postcondition(snapshot: dict[str, Any], data: dict[str, Any]) -> bool:
    tool_name = str(snapshot["toolName"])
    arguments = snapshot["arguments"]
    if tool_name == "create_unit_block":
        return (
            _same(data.get("unitId"), arguments.get("unitId"))
            and data.get("status") == "PLANNED"
            and _same(data.get("blockType"), arguments.get("blockType"))
            and _same(data.get("blockedFrom"), arguments.get("blockedFrom"))
            and _same(data.get("blockedUntil"), arguments.get("blockedUntil"))
            and _same(data.get("reason"), arguments.get("reason"))
        )
    if tool_name == "update_unit_block":
        return _same(data.get("id"), arguments.get("blockId")) and all(
            key in {"blockId", "expectedUpdatedAt"} or _same(data.get(key), value)
            for key, value in arguments.items()
        )
    if tool_name == "cancel_unit_block":
        return _same(data.get("id"), arguments.get("blockId")) and data.get("status") == "CANCELLED"
    if tool_name == "extend_rental_order":
        return _same(data.get("id"), arguments.get("orderId")) and _same(
            data.get("plannedDueAt"), arguments.get("newDueAt")
        )
    if tool_name == "reallocate_rental_item":
        items = data.get("items")
        return isinstance(items, list) and any(
            isinstance(item, dict)
            and _same(item.get("id"), arguments.get("orderItemId"))
            and _same(item.get("unitId"), arguments.get("unitId"))
            for item in items
        )
    if tool_name == "cancel_rental_order":
        return _same(data.get("id"), arguments.get("orderId")) and data.get("status") == "CANCELLED"
    if tool_name == "create_stock_transfer":
        items = data.get("items")
        observed_units = (
            {str(item.get("unitId")) for item in items if isinstance(item, dict)}
            if isinstance(items, list)
            else set()
        )
        return (
            data.get("status") == "REQUESTED"
            and _same(data.get("fromBranchId"), arguments.get("fromBranchId"))
            and _same(data.get("toBranchId"), arguments.get("toBranchId"))
            and observed_units == {str(unit_id) for unit_id in arguments.get("unitIds", [])}
        )
    if tool_name == "approve_stock_transfer":
        return (
            _same(data.get("id"), arguments.get("transferId")) and data.get("status") == "APPROVED"
        )
    if tool_name == "reject_stock_transfer":
        return (
            _same(data.get("id"), arguments.get("transferId")) and data.get("status") == "REJECTED"
        )
    if tool_name == "create_payment_checkout":
        return (
            _same(data.get("orderId"), arguments.get("orderId"))
            and _same(data.get("amountVnd"), arguments.get("amountVnd"))
            and _same(data.get("purpose"), arguments.get("purpose"))
        )
    if tool_name == "request_refund":
        return (
            data.get("status") == "REQUESTED"
            and _same(data.get("paymentId"), arguments.get("paymentId"))
            and _same(data.get("amountVnd"), arguments.get("amountVnd"))
        )
    return False


async def execute_frozen_action(
    *,
    actor: ActorContext,
    case_id: UUID,
    snapshot: dict[str, Any],
    stored_hash: str,
    confirmation_id: UUID | None = None,
    approval_id: UUID | None = None,
) -> WriteExecution:
    validate_frozen_action(snapshot, stored_hash)
    tool_name = str(snapshot["toolName"])
    payload_hash = str(snapshot.get("payloadHash") or stored_hash)
    idempotency_key = f"agent:{case_id}:{tool_name}:{payload_hash}"
    write_result: AgentToolExecutionResult | None = None
    write_unknown = False
    try:
        write_result = await _call(
            actor=actor,
            case_id=case_id,
            tool_name=tool_name,
            arguments=snapshot["arguments"],
            idempotency_key=idempotency_key,
            expected_version=snapshot.get("expectedVersion"),
            confirmation_id=confirmation_id,
            approval_id=approval_id,
            payload_hash=stored_hash,
        )
    except ToolInvocationError as error:
        if error.code != "TOOL_OUTCOME_UNKNOWN":
            return WriteExecution(ToolExecutionStatus.DEPENDENCY_UNAVAILABLE, error.message)
        write_unknown = True
    if write_result is not None and write_result.status is not ToolExecutionStatus.OK:
        return WriteExecution(write_result.status, "Studio rejected the write action", write_result)

    readback = _readback_arguments(snapshot, write_result, idempotency_key)
    if readback is None:
        status = (
            ToolExecutionStatus.UNKNOWN_OUTCOME
            if write_unknown
            else ToolExecutionStatus.VALIDATION_ERROR
        )
        return WriteExecution(status, "The write outcome cannot be reconciled safely", write_result)
    read_tool, read_arguments = readback
    try:
        read_result = await _call(
            actor=actor,
            case_id=case_id,
            tool_name=read_tool,
            arguments=read_arguments,
            idempotency_key=f"{idempotency_key}:readback",
        )
    except ToolInvocationError:
        return WriteExecution(
            ToolExecutionStatus.UNKNOWN_OUTCOME,
            "Write completed or timed out, but read-back is unavailable",
            write_result,
        )
    if read_result.status is not ToolExecutionStatus.OK or not isinstance(read_result.data, dict):
        return WriteExecution(
            ToolExecutionStatus.UNKNOWN_OUTCOME if write_unknown else read_result.status,
            "Read-back did not return the expected record",
            write_result,
            read_result,
        )
    if not _postcondition(snapshot, read_result.data):
        return WriteExecution(
            ToolExecutionStatus.VERSION_CONFLICT,
            "Read-back did not verify the requested postcondition",
            write_result,
            read_result,
        )
    evidence = AgentEvidence(
        source_type="live_tool",
        source_id=read_tool,
        observed_at=read_result.observed_at.isoformat() if read_result.observed_at else None,
    )
    return WriteExecution(
        ToolExecutionStatus.OK,
        "Write action completed and was verified by read-back",
        write_result,
        read_result,
        evidence,
    )


async def observe_live_tool(
    actor: ActorContext,
    case_id: UUID,
    tool_name: str,
    arguments: dict[str, Any],
    purpose: str,
) -> AgentToolExecutionResult:
    """Perform one audited read used for policy scope or write verification."""
    return await _call(
        actor=actor,
        case_id=case_id,
        tool_name=tool_name,
        arguments=arguments,
        idempotency_key=f"agent:{case_id}:read:{purpose}",
    )
