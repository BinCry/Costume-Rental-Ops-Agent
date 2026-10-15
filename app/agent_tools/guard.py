"""Deterministic policy, progress, loop, and completion guards for the agent."""

import hashlib
import json
from collections import Counter, deque
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any, Literal, cast
from uuid import UUID

from app.agent_tools.models import AgentGoalSpec, AgentGoalType, AgentTerminationReason


class AgentRuleViolation(RuntimeError):
    def __init__(self, reason: AgentTerminationReason, message: str) -> None:
        super().__init__(message)
        self.reason = reason
        self.message = message


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str, separators=(",", ":"))


def _without_volatile_fields(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _without_volatile_fields(item)
            for key, item in value.items()
            if key not in {"observedAt", "observed_at", "requestId", "request_id"}
        }
    if isinstance(value, list):
        return [_without_volatile_fields(item) for item in value]
    return value


def _fingerprint(value: Any) -> str:
    normalized = _without_volatile_fields(value)
    return hashlib.sha256(_canonical(normalized).encode("utf-8")).hexdigest()


def _progress_snapshot(tool_name: str | None, data: Any, fallback: Any) -> Any:
    """Keep only fields that represent business progress for known live tools."""
    if not isinstance(data, dict):
        return fallback
    if tool_name == "get_rental_order":
        items = data.get("items")
        allocations = (
            [
                {"id": item.get("id"), "unitId": item.get("unitId")}
                for item in items
                if isinstance(item, dict)
            ]
            if isinstance(items, list)
            else None
        )
        return {
            "id": data.get("id"),
            "status": data.get("status"),
            "version": data.get("version"),
            "allocations": allocations,
        }
    if tool_name == "get_payment_summary":
        return {
            "orderId": data.get("orderId"),
            "status": data.get("status"),
            "rental": data.get("rental"),
            "deposit": data.get("deposit"),
            "extra": data.get("extra"),
            "canPickup": data.get("canPickup"),
            "canComplete": data.get("canComplete"),
        }
    if tool_name == "check_availability":
        units = data.get("units")
        unit_ids = (
            [item.get("id") for item in units if isinstance(item, dict)]
            if isinstance(units, list)
            else None
        )
        return {"available": data.get("available"), "unitIds": unit_ids}
    if tool_name == "get_stock_transfer":
        return {
            "id": data.get("id"),
            "status": data.get("status"),
            "version": data.get("version"),
        }
    if tool_name in {"find_rental_orders", "get_unit_schedule"}:
        items = data.get("items")
        if isinstance(items, list):
            return {
                "pagination": data.get("pagination"),
                "items": [
                    {"id": item.get("id"), "status": item.get("status")}
                    for item in items
                    if isinstance(item, dict)
                ],
            }
    return fallback


@dataclass(frozen=True)
class ToolPolicy:
    name: str
    mode: Literal["read", "write"]
    required_permission: str
    retry_safe: bool
    polling: bool = False
    requires_confirmation: bool = False
    requires_approval: bool = False
    requires_expected_version: bool = False
    readback_tool: str | None = None


READ_TOOL_POLICIES: Mapping[str, ToolPolicy] = {
    "search_knowledge": ToolPolicy("search_knowledge", "read", "knowledge:read", True),
    "get_rental_order": ToolPolicy("get_rental_order", "read", "rentals:read", True),
    "get_payment_summary": ToolPolicy("get_payment_summary", "read", "payments:read", True),
    "check_availability": ToolPolicy("check_availability", "read", "rentals:read", True),
    "find_rental_orders": ToolPolicy("find_rental_orders", "read", "rentals:read", True),
    "get_unit_schedule": ToolPolicy("get_unit_schedule", "read", "scheduling:read", True),
    "get_stock_transfer": ToolPolicy(
        "get_stock_transfer", "read", "transfers:read", True, polling=True
    ),
    "get_unit_block": ToolPolicy("get_unit_block", "read", "inventory:read", True),
    "get_payment": ToolPolicy("get_payment", "read", "payments:read", True),
    "get_payment_by_idempotency_key": ToolPolicy(
        "get_payment_by_idempotency_key", "read", "payments:read", True
    ),
    "get_refund_by_idempotency_key": ToolPolicy(
        "get_refund_by_idempotency_key", "read", "payments:read", True
    ),
}

# Write tools are deliberately absent from the ReAct tool list.  The model may
# propose one of these names, but only deterministic runtime code can invoke it
# after its frozen snapshot has passed confirmation/approval gates.
WRITE_TOOL_POLICIES: Mapping[str, ToolPolicy] = {
    "create_unit_block": ToolPolicy(
        "create_unit_block",
        "write",
        "scheduling:manage",
        False,
        requires_confirmation=True,
        readback_tool="get_unit_block",
    ),
    "update_unit_block": ToolPolicy(
        "update_unit_block",
        "write",
        "scheduling:manage",
        False,
        requires_confirmation=True,
        readback_tool="get_unit_block",
    ),
    "cancel_unit_block": ToolPolicy(
        "cancel_unit_block",
        "write",
        "scheduling:manage",
        False,
        requires_confirmation=True,
        readback_tool="get_unit_block",
    ),
    "extend_rental_order": ToolPolicy(
        "extend_rental_order",
        "write",
        "rentals:manage",
        False,
        requires_confirmation=True,
        requires_expected_version=True,
        readback_tool="get_rental_order",
    ),
    "reallocate_rental_item": ToolPolicy(
        "reallocate_rental_item",
        "write",
        "rentals:manage",
        False,
        requires_confirmation=True,
        requires_expected_version=True,
        readback_tool="get_rental_order",
    ),
    "cancel_rental_order": ToolPolicy(
        "cancel_rental_order",
        "write",
        "rentals:manage",
        False,
        requires_confirmation=True,
        requires_expected_version=True,
        readback_tool="get_rental_order",
    ),
    "create_stock_transfer": ToolPolicy(
        "create_stock_transfer",
        "write",
        "transfers:manage",
        False,
        requires_confirmation=True,
        readback_tool="get_stock_transfer",
    ),
    "approve_stock_transfer": ToolPolicy(
        "approve_stock_transfer",
        "write",
        "transfers:manage",
        False,
        requires_approval=True,
        requires_expected_version=True,
        readback_tool="get_stock_transfer",
    ),
    "reject_stock_transfer": ToolPolicy(
        "reject_stock_transfer",
        "write",
        "transfers:manage",
        False,
        requires_approval=True,
        requires_expected_version=True,
        readback_tool="get_stock_transfer",
    ),
    "create_payment_checkout": ToolPolicy(
        "create_payment_checkout",
        "write",
        "payments:manage",
        False,
        requires_confirmation=True,
        requires_approval=True,
        readback_tool="get_payment_by_idempotency_key",
    ),
    "request_refund": ToolPolicy(
        "request_refund",
        "write",
        "payments:manage",
        False,
        requires_confirmation=True,
        requires_approval=True,
        readback_tool="get_refund_by_idempotency_key",
    ),
}

ALL_TOOL_POLICIES: Mapping[str, ToolPolicy] = {**READ_TOOL_POLICIES, **WRITE_TOOL_POLICIES}


@dataclass(frozen=True)
class ToolAuthorization:
    confirmation_id: str | None = None
    approval_id: str | None = None
    expected_version: int | None = None


@dataclass(frozen=True)
class ToolObservation:
    tool_name: str
    arguments: dict[str, Any]
    status: str
    fingerprint: str | None
    evidence_refs: tuple[str, ...] = ()
    data: Any | None = field(default=None, repr=False)
    observed_at: datetime | None = None
    permission_decision: str | None = None


@dataclass(frozen=True)
class CompletionVerification:
    achieved: bool
    reason: AgentTerminationReason | None = None
    message: str | None = None


@dataclass(frozen=True)
class HandoffContext:
    reason: str
    goal: str
    attempted_tools: tuple[str, ...]
    successful_tools: tuple[str, ...]
    failed_tools: tuple[str, ...]
    evidence_count: int
    next_action: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "reason": self.reason,
            "goal": self.goal,
            "attemptedTools": list(self.attempted_tools),
            "successfulTools": list(self.successful_tools),
            "failedTools": list(self.failed_tools),
            "evidenceCount": self.evidence_count,
            "nextAction": self.next_action,
        }


def _parse_datetime(value: Any, field_name: str) -> datetime:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be an ISO-8601 string")
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError(f"{field_name} must be a valid ISO-8601 timestamp") from error


def _require_uuid(arguments: dict[str, Any], field_name: str) -> None:
    value = arguments.get(field_name)
    if not isinstance(value, str):
        raise ValueError(f"{field_name} is required")
    UUID(value)


def validate_tool_arguments(tool_name: str, arguments: dict[str, Any]) -> None:
    """Apply semantic checks before the request reaches Studio's authoritative schema."""
    id_fields = {
        "get_rental_order": ("orderId",),
        "get_payment_summary": ("orderId",),
        "get_unit_schedule": ("unitId",),
        "get_stock_transfer": ("transferId",),
        "check_availability": ("variantId", "pickupBranchId"),
        "create_unit_block": ("unitId",),
        "update_unit_block": ("blockId",),
        "cancel_unit_block": ("blockId",),
        "extend_rental_order": ("orderId",),
        "reallocate_rental_item": ("orderId", "orderItemId", "unitId"),
        "cancel_rental_order": ("orderId",),
        "create_stock_transfer": ("fromBranchId", "toBranchId"),
        "approve_stock_transfer": ("transferId",),
        "reject_stock_transfer": ("transferId",),
        "create_payment_checkout": ("orderId",),
        "request_refund": ("paymentId",),
        "get_unit_block": ("blockId",),
        "get_payment": ("paymentId",),
    }
    for field_name in id_fields.get(tool_name, ()):
        _require_uuid(arguments, field_name)

    if tool_name == "find_rental_orders":
        search = arguments.get("search")
        page_size = arguments.get("pageSize", 10)
        if not isinstance(search, str) or not search.strip() or len(search.strip()) > 100:
            raise ValueError("search must contain between 1 and 100 characters")
        if not isinstance(page_size, int) or not 1 <= page_size <= 20:
            raise ValueError("pageSize must be between 1 and 20")
    elif tool_name == "check_availability":
        start = _parse_datetime(arguments.get("plannedStartAt"), "plannedStartAt")
        due = _parse_datetime(arguments.get("plannedDueAt"), "plannedDueAt")
        if due <= start:
            raise ValueError("plannedDueAt must be after plannedStartAt")
    elif tool_name == "get_unit_schedule":
        start_value = arguments.get("from")
        end_value = arguments.get("to")
        range_start = _parse_datetime(start_value, "from") if start_value is not None else None
        range_end = _parse_datetime(end_value, "to") if end_value is not None else None
        if range_start is not None and range_end is not None and range_end <= range_start:
            raise ValueError("to must be after from")
    elif tool_name == "create_stock_transfer":
        unit_ids = arguments.get("unitIds")
        if not isinstance(unit_ids, list) or not 1 <= len(unit_ids) <= 100:
            raise ValueError("unitIds must contain between 1 and 100 unit IDs")
        for unit_id in unit_ids:
            if not isinstance(unit_id, str):
                raise ValueError("unitIds must contain UUIDs")
            UUID(unit_id)
    elif tool_name in {"cancel_unit_block", "cancel_rental_order", "reject_stock_transfer"}:
        reason = arguments.get("reason")
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError("reason is required")


@dataclass
class ExecutionGuard:
    """Fail-closed harness around model-selected tools."""

    max_tool_calls: int
    remaining_case_steps: int
    loop_window: int = 6
    repeat_limit: int = 2
    stall_limit: int = 5
    allowed_tools: frozenset[str] | None = None
    polling_tools: frozenset[str] = frozenset()
    tool_policies: Mapping[str, ToolPolicy] = field(default_factory=lambda: READ_TOOL_POLICIES)
    tool_calls: int = 0
    observations: list[ToolObservation] = field(default_factory=list)
    _recent_signatures: deque[str] = field(init=False, repr=False)
    _signature_counts: Counter[str] = field(init=False, repr=False)
    _last_observation_by_signature: dict[str, str] = field(default_factory=dict, repr=False)
    _current_signature: str | None = field(default=None, init=False, repr=False)
    _current_tool: str | None = field(default=None, init=False, repr=False)
    _current_arguments: dict[str, Any] = field(default_factory=dict, init=False, repr=False)
    _evidence_before_call: int = field(default=0, init=False, repr=False)
    _stalled_calls: int = field(default=0, init=False, repr=False)

    def __post_init__(self) -> None:
        if self.loop_window < 1 or self.repeat_limit < 2 or self.stall_limit < 1:
            raise ValueError("Invalid execution guard limits")
        self._recent_signatures = deque()
        self._signature_counts = Counter()

    def before_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        evidence_count: int = 0,
        authorization: ToolAuthorization | None = None,
    ) -> None:
        policy = self.tool_policies.get(tool_name)
        blocked_by_allowlist = (
            self.allowed_tools is not None and tool_name not in self.allowed_tools
        )
        if policy is None or blocked_by_allowlist:
            raise AgentRuleViolation(
                AgentTerminationReason.POLICY_VIOLATION,
                "Agent đã bị chặn vì yêu cầu một tool không nằm trong allowlist.",
            )
        authorization = authorization or ToolAuthorization()
        if policy.mode == "write":
            if policy.requires_confirmation and authorization.confirmation_id is None:
                raise AgentRuleViolation(
                    AgentTerminationReason.HUMAN_INPUT_REQUIRED,
                    "Thao tác ghi cần người yêu cầu xác nhận trước khi thực thi.",
                )
            if policy.requires_approval and authorization.approval_id is None:
                raise AgentRuleViolation(
                    AgentTerminationReason.HUMAN_INPUT_REQUIRED,
                    "Thao tác ghi cần phê duyệt hợp lệ trước khi thực thi.",
                )
            if policy.requires_expected_version and authorization.expected_version is None:
                raise AgentRuleViolation(
                    AgentTerminationReason.POLICY_VIOLATION,
                    "Thao tác ghi thiếu expectedVersion để chống cập nhật dữ liệu cũ.",
                )
        try:
            validate_tool_arguments(tool_name, arguments)
        except (TypeError, ValueError) as error:
            raise AgentRuleViolation(
                AgentTerminationReason.INVALID_TOOL_ARGUMENTS,
                f"Tham số tool không hợp lệ: {error}",
            ) from error

        signature = _canonical({"tool": tool_name, "arguments": arguments})
        polling = policy.polling or tool_name in self.polling_tools
        repeated = self._signature_counts[signature] >= self.repeat_limit - 1
        if repeated and not polling:
            raise AgentRuleViolation(
                AgentTerminationReason.LOOP_DETECTED,
                "Agent đã dừng vì lặp lại cùng tool và tham số trong cửa sổ gần nhất.",
            )

        available = min(self.max_tool_calls, self.remaining_case_steps)
        if self.tool_calls >= available:
            raise AgentRuleViolation(
                AgentTerminationReason.BUDGET_EXHAUSTED,
                "Agent đã đạt giới hạn số bước an toàn cho yêu cầu này.",
            )

        if len(self._recent_signatures) == self.loop_window:
            removed = self._recent_signatures.popleft()
            self._signature_counts[removed] -= 1
            if self._signature_counts[removed] == 0:
                del self._signature_counts[removed]
        self._recent_signatures.append(signature)
        self._signature_counts[signature] += 1
        self.tool_calls += 1
        self._current_signature = signature
        self._current_tool = tool_name
        self._current_arguments = dict(arguments)
        self._evidence_before_call = evidence_count

    def after_tool(
        self,
        evidence_count: int | None = None,
        *,
        observation: Any | None = None,
        status: str = "ok",
        evidence_refs: Sequence[str] = (),
        data: Any | None = None,
        observed_at: datetime | None = None,
        permission_decision: str | None = None,
    ) -> None:
        """Measure progress from a new successful domain observation."""
        normalized_status = status.lower()
        successful = normalized_status == "ok"
        progress_value = _progress_snapshot(self._current_tool, data, observation)
        observed = (
            _fingerprint(progress_value) if successful and progress_value is not None else None
        )
        previous = (
            self._last_observation_by_signature.get(self._current_signature)
            if self._current_signature is not None
            else None
        )
        observation_progress = observed is not None and observed != previous
        evidence_progress = (
            evidence_count is not None and evidence_count > self._evidence_before_call
        )
        if self._current_signature is not None and observed is not None:
            self._last_observation_by_signature[self._current_signature] = observed
        if self._current_tool is not None:
            self.observations.append(
                ToolObservation(
                    tool_name=self._current_tool,
                    arguments=dict(self._current_arguments),
                    status=normalized_status,
                    fingerprint=observed,
                    evidence_refs=tuple(evidence_refs),
                    data=data,
                    observed_at=observed_at,
                    permission_decision=permission_decision,
                )
            )

        if evidence_progress or observation_progress:
            self._stalled_calls = 0
        else:
            self._stalled_calls += 1
        if self._stalled_calls >= self.stall_limit:
            raise AgentRuleViolation(
                AgentTerminationReason.NO_PROGRESS,
                "Agent đã dừng vì nhiều lần gọi tool không tạo ra thay đổi hoặc dữ liệu hữu ích.",
            )


_SOCIAL_MESSAGES = {"hi", "hello", "xin chào", "chào", "cảm ơn", "cam on", "thanks"}


def _fresh_live_observation(observation: ToolObservation) -> bool:
    if observation.tool_name == "search_knowledge":
        return True
    if observation.observed_at is None:
        return False
    observed_at = observation.observed_at
    if observed_at.tzinfo is None:
        observed_at = observed_at.replace(tzinfo=UTC)
    now = datetime.now(UTC)
    return now - timedelta(minutes=5) <= observed_at <= now + timedelta(minutes=1)


def _has_fields(data: Any, *field_names: str) -> bool:
    return isinstance(data, dict) and all(field_name in data for field_name in field_names)


def _domain_predicate(
    goal: AgentGoalSpec,
    observations: Sequence[ToolObservation],
    answer: str,
) -> str | None:
    """Return an explanation when authoritative result shape/freshness is insufficient."""
    by_tool = {item.tool_name: item for item in observations if item.status == "ok"}
    missing_tools = [tool_name for tool_name in goal.required_tools if tool_name not in by_tool]
    if missing_tools:
        return f"Chưa có kết quả thành công từ tool bắt buộc: {', '.join(missing_tools)}."
    matching = [by_tool[tool_name] for tool_name in goal.required_tools]
    stale = [item.tool_name for item in matching if not _fresh_live_observation(item)]
    if stale:
        return f"Observation không có thời điểm hợp lệ hoặc đã cũ: {', '.join(stale)}."
    unaudited = [
        item.tool_name
        for item in matching
        if item.tool_name != "search_knowledge" and item.permission_decision != "allowed"
    ]
    if unaudited:
        return f"Thiếu permission decision từ Studio cho tool: {', '.join(unaudited)}."

    if goal.goal_type is AgentGoalType.KNOWLEDGE_ANSWER:
        observation = by_tool.get("search_knowledge")
        if observation is None or not observation.evidence_refs:
            return "Không có nguồn tri thức có thể trích dẫn."
        citations: list[str] = []
        if isinstance(observation.data, dict):
            results = observation.data.get("results", [])
            if isinstance(results, list):
                for item in results:
                    if isinstance(item, dict) and isinstance(item.get("citation"), str):
                        citations.append(cast(str, item["citation"]))
        if not citations or not any(citation in answer for citation in citations):
            return "Câu trả lời kiến thức chưa chứa citation từ nguồn đã truy xuất."
    elif goal.goal_type is AgentGoalType.RENTAL_ORDER_LOOKUP:
        observation = by_tool["get_rental_order"]
        if not _has_fields(observation.data, "id", "status", "version", "items"):
            return "Kết quả đơn thuê thiếu id, status, version hoặc items."
    elif goal.goal_type is AgentGoalType.RENTAL_ORDER_SEARCH:
        observation = by_tool["find_rental_orders"]
        if not isinstance(observation.data, (dict, list)):
            return "Kết quả tìm đơn không có danh sách hợp lệ."
    elif goal.goal_type is AgentGoalType.PAYMENT_SUMMARY:
        observation = by_tool["get_payment_summary"]
        if not _has_fields(observation.data, "orderId", "rental", "deposit", "extra", "canPickup"):
            return "Tóm tắt thanh toán thiếu các trường quyết toán bắt buộc."
    elif goal.goal_type is AgentGoalType.AVAILABILITY_CHECK:
        observation = by_tool["check_availability"]
        data = observation.data
        if not _has_fields(data, "available", "units") or not isinstance(data, dict):
            return "Kết quả availability thiếu available hoặc units."
        if not isinstance(data["available"], bool):
            return "Trường available không phải boolean."
        if not isinstance(data["units"], list):
            return "Trường units không phải danh sách."
    elif goal.goal_type is AgentGoalType.UNIT_SCHEDULE:
        observation = by_tool["get_unit_schedule"]
        if not isinstance(observation.data, (dict, list)):
            return "Kết quả lịch unit không có danh sách hợp lệ."
    elif goal.goal_type is AgentGoalType.STOCK_TRANSFER_LOOKUP:
        observation = by_tool["get_stock_transfer"]
        if not _has_fields(observation.data, "id", "status", "fromBranchId", "toBranchId"):
            return "Kết quả điều chuyển thiếu trạng thái hoặc phạm vi chi nhánh."

    if goal.required_identifiers:
        authoritative_data = _canonical([item.data for item in matching]).lower()
        arguments_and_refs = _canonical(
            [{"arguments": item.arguments, "evidence": item.evidence_refs} for item in matching]
        ).lower()
        for identifier in goal.required_identifiers:
            identifier = identifier.lower()
            if identifier not in authoritative_data and identifier not in arguments_and_refs:
                return "Bằng chứng không khớp đầy đủ với record được yêu cầu."
    return None


def render_grounded_answer(
    goal: AgentGoalSpec,
    observations: Sequence[ToolObservation],
    fallback: str,
) -> str:
    """Render live operational facts deterministically instead of trusting prose claims."""
    successful = {item.tool_name: item for item in observations if item.status == "ok"}
    tool_name = goal.required_tools[0] if len(goal.required_tools) == 1 else None
    observation = successful.get(tool_name) if tool_name is not None else None
    if observation is None or not isinstance(observation.data, dict):
        return fallback
    data = observation.data
    if goal.goal_type is AgentGoalType.RENTAL_ORDER_LOOKUP:
        order_label = data.get("orderCode") or data.get("id")
        return (
            f"Đơn {order_label} đang ở trạng thái {data.get('status')}. "
            f"Thời gian nhận dự kiến: {data.get('plannedStartAt')}; "
            f"thời gian trả dự kiến: {data.get('plannedDueAt')}; "
            f"phiên bản dữ liệu: {data.get('version')}."
        )
    if goal.goal_type is AgentGoalType.PAYMENT_SUMMARY:
        rental_value = data.get("rental")
        deposit_value = data.get("deposit")
        extra_value = data.get("extra")
        rental = cast(dict[str, Any], rental_value) if isinstance(rental_value, dict) else {}
        deposit = cast(dict[str, Any], deposit_value) if isinstance(deposit_value, dict) else {}
        extra = cast(dict[str, Any], extra_value) if isinstance(extra_value, dict) else {}
        return (
            f"Quyết toán đơn {data.get('orderId')}: "
            f"còn tiền thuê {rental.get('remainingVnd')} VND, "
            f"tiền cọc phải thu {deposit.get('dueVnd')} VND và đã thu "
            f"{deposit.get('paidVnd')} VND, "
            f"còn phụ phí {extra.get('remainingVnd')} VND; "
            f"đủ điều kiện nhận đồ: {data.get('canPickup')}, "
            f"đủ điều kiện hoàn tất: {data.get('canComplete')}."
        )
    if goal.goal_type is AgentGoalType.AVAILABILITY_CHECK:
        units_value = data.get("units")
        units = units_value if isinstance(units_value, list) else []
        availability = "còn" if data.get("available") is True else "không còn"
        return f"Khoảng thời gian yêu cầu {availability} bộ phù hợp; số bộ khả dụng: {len(units)}."
    if goal.goal_type is AgentGoalType.STOCK_TRANSFER_LOOKUP:
        return (
            f"Phiếu điều chuyển {data.get('id')} đang ở trạng thái {data.get('status')}, "
            f"từ chi nhánh {data.get('fromBranchId')} đến {data.get('toBranchId')}."
        )
    if goal.goal_type in {
        AgentGoalType.RENTAL_ORDER_SEARCH,
        AgentGoalType.UNIT_SCHEDULE,
    }:
        items_value = data.get("items")
        items = items_value if isinstance(items_value, list) else []
        return f"Đã tìm thấy {len(items)} bản ghi phù hợp trong phạm vi được phép."
    return fallback


def verify_completion(
    *,
    user_message: str,
    answer: str,
    evidence_count: int,
    tool_calls: int,
    goal: AgentGoalSpec | None = None,
    observations: Sequence[ToolObservation] = (),
) -> CompletionVerification:
    """Evaluate measurable goal predicates before returning ``SUCCEEDED``."""
    clean_answer = answer.strip()
    if not clean_answer:
        return CompletionVerification(
            False,
            AgentTerminationReason.VERIFICATION_FAILED,
            "Agent không tạo được câu trả lời có thể xác minh.",
        )
    normalized_message = " ".join(user_message.lower().strip().rstrip("!?.").split())
    if normalized_message in _SOCIAL_MESSAGES:
        return CompletionVerification(True)
    if clean_answer.endswith("?") and evidence_count == 0:
        return CompletionVerification(
            False, AgentTerminationReason.HUMAN_INPUT_REQUIRED, clean_answer
        )
    if evidence_count == 0:
        detail = "sau khi gọi tool" if tool_calls else "cho yêu cầu nghiệp vụ"
        return CompletionVerification(
            False,
            AgentTerminationReason.INSUFFICIENT_DATA,
            f"Chưa có bằng chứng đủ để xác minh kết quả {detail}.",
        )

    successful = [item for item in observations if item.status == "ok"]
    if goal is not None and goal.required_tools:
        predicate_error = _domain_predicate(goal, successful, clean_answer)
        if predicate_error is not None:
            return CompletionVerification(
                False,
                AgentTerminationReason.VERIFICATION_FAILED,
                predicate_error,
            )
    elif tool_calls > 0 and not successful:
        return CompletionVerification(
            False,
            AgentTerminationReason.INSUFFICIENT_DATA,
            "Không có tool nào trả về observation thành công để xác minh kết quả.",
        )
    return CompletionVerification(True)


def build_handoff_context(
    *,
    goal: AgentGoalSpec,
    reason: AgentTerminationReason,
    observations: Sequence[ToolObservation],
    evidence_count: int,
) -> HandoffContext:
    successful = tuple(item.tool_name for item in observations if item.status == "ok")
    failed = tuple(item.tool_name for item in observations if item.status != "ok")
    next_actions = {
        AgentTerminationReason.HUMAN_INPUT_REQUIRED: (
            "Cung cấp thông tin còn thiếu rồi tiếp tục case."
        ),
        AgentTerminationReason.INSUFFICIENT_DATA: (
            "Kiểm tra nguồn dữ liệu hoặc bổ sung record cần tra cứu."
        ),
        AgentTerminationReason.BUDGET_EXHAUSTED: (
            "Con người xem kết quả dở dang trước khi tạo lượt mới."
        ),
        AgentTerminationReason.LOOP_DETECTED: "Xem lại kế hoạch và chọn tool hoặc tham số khác.",
        AgentTerminationReason.NO_PROGRESS: "Kiểm tra dependency hoặc xử lý nghiệp vụ thủ công.",
        AgentTerminationReason.POLICY_VIOLATION: (
            "Không mở quyền tự động; chuyển actor có thẩm quyền."
        ),
        AgentTerminationReason.INVALID_TOOL_ARGUMENTS: "Bổ sung định danh hoặc thời gian hợp lệ.",
        AgentTerminationReason.VERIFICATION_FAILED: "Đọc lại record và kiểm tra success criteria.",
    }
    return HandoffContext(
        reason=reason.value,
        goal=goal.summary,
        attempted_tools=tuple(item.tool_name for item in observations),
        successful_tools=successful,
        failed_tools=failed,
        evidence_count=evidence_count,
        next_action=next_actions.get(reason, "Chuyển người phụ trách kiểm tra case."),
    )
