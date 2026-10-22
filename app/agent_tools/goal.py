"""Hybrid goal resolution for the bounded operations agent.

Explicit, high-confidence commands use deterministic rules. Natural-language
requests that do not match a rule may be classified by a model using structured
output. The model never supplies tools, permissions, approvals, or success
criteria; those always come from the trusted skill catalog in code.
"""

import json
import logging
import re
import unicodedata
from dataclasses import dataclass
from typing import Any, Literal

from langchain_core.callbacks import UsageMetadataCallbackHandler
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from pydantic import SecretStr

from app.agent_tools.models import AgentGoalSpec, AgentGoalType, GoalDraft
from app.agent_tools.skills import attach_skill
from app.config import get_settings

_UUID_PATTERN = re.compile(
    r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-"
    r"[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}\b"
)
_ISO_TIMESTAMP_PATTERN = re.compile(
    r"\b\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2})?(?:Z|[+-]\d{2}:\d{2})?\b"
)
_MODEL_CONFIDENCE_THRESHOLD = 0.80
_SAFETY_INPUTS = frozenset({"goalIntent", "writeIntent"})
logger = logging.getLogger(__name__)

_GOAL_CONTRACTS: dict[AgentGoalType, tuple[tuple[str, ...], tuple[str, ...]]] = {
    AgentGoalType.REFUND_REQUEST: (
        ("get_payment", "request_refund", "get_refund_by_idempotency_key"),
        ("requester_confirmed", "financial_approval_granted", "refund_request_verified"),
    ),
    AgentGoalType.PAYMENT_CHECKOUT: (
        ("get_rental_order", "create_payment_checkout", "get_payment_by_idempotency_key"),
        ("requester_confirmed", "financial_approval_granted", "checkout_verified"),
    ),
    AgentGoalType.RENTAL_EXTENSION: (
        ("get_rental_order", "check_availability", "extend_rental_order"),
        ("requester_confirmed", "new_due_time_verified"),
    ),
    AgentGoalType.RENTAL_REALLOCATION: (
        ("get_rental_order", "check_availability", "reallocate_rental_item"),
        ("requester_confirmed", "new_allocation_verified"),
    ),
    AgentGoalType.RENTAL_CANCELLATION: (
        ("get_rental_order", "cancel_rental_order"),
        ("requester_confirmed", "cancelled_order_verified"),
    ),
    AgentGoalType.UNIT_BLOCK_CHANGE: (
        ("get_unit_schedule", "get_unit_block"),
        ("requester_confirmed", "unit_block_verified"),
    ),
    AgentGoalType.STOCK_TRANSFER_DECISION: (
        (),
        ("branch_approval_checked", "transfer_decision_verified"),
    ),
    AgentGoalType.STOCK_TRANSFER_CREATE: (
        ("create_stock_transfer", "get_stock_transfer"),
        ("requester_confirmed", "branch_approval_granted", "transfer_verified"),
    ),
    AgentGoalType.PAYMENT_SUMMARY: (
        ("get_payment_summary",),
        ("payment_summary_observed", "requested_record_matches"),
    ),
    AgentGoalType.AVAILABILITY_CHECK: (
        ("check_availability",),
        ("availability_observed", "requested_scope_matches"),
    ),
    AgentGoalType.STOCK_TRANSFER_LOOKUP: (
        ("get_stock_transfer",),
        ("stock_transfer_observed", "requested_record_matches"),
    ),
    AgentGoalType.UNIT_SCHEDULE: (
        ("get_unit_schedule",),
        ("unit_schedule_observed", "requested_record_matches"),
    ),
    AgentGoalType.RENTAL_ORDER_LOOKUP: (
        ("get_rental_order",),
        ("rental_order_observed", "requested_scope_matches"),
    ),
    AgentGoalType.RENTAL_ORDER_SEARCH: (
        ("find_rental_orders",),
        ("rental_orders_searched", "requested_scope_matches"),
    ),
    AgentGoalType.KNOWLEDGE_ANSWER: (
        ("search_knowledge",),
        ("approved_knowledge_observed", "citation_available"),
    ),
    AgentGoalType.GENERAL_ASSISTANCE: (
        (),
        ("answer_is_grounded_or_input_requested",),
    ),
}

_REQUIRED_INPUTS: dict[AgentGoalType, tuple[str, ...]] = {
    AgentGoalType.REFUND_REQUEST: ("paymentId", "amountVnd", "reason"),
    AgentGoalType.PAYMENT_CHECKOUT: ("orderId", "amountVnd", "purpose"),
    AgentGoalType.RENTAL_EXTENSION: ("orderId", "newDueAt"),
    AgentGoalType.RENTAL_REALLOCATION: ("orderId", "orderItemId", "unitId"),
    AgentGoalType.RENTAL_CANCELLATION: ("orderId", "reason"),
    AgentGoalType.STOCK_TRANSFER_CREATE: ("fromBranchId", "toBranchId", "unitIds"),
    AgentGoalType.PAYMENT_SUMMARY: ("orderId",),
    AgentGoalType.AVAILABILITY_CHECK: (
        "variantId",
        "pickupBranchId",
        "plannedStartAt",
        "plannedDueAt",
    ),
    AgentGoalType.STOCK_TRANSFER_LOOKUP: ("transferId",),
    AgentGoalType.UNIT_SCHEDULE: ("unitId",),
    AgentGoalType.RENTAL_ORDER_LOOKUP: ("orderId",),
    AgentGoalType.RENTAL_ORDER_SEARCH: ("search",),
}

_UNIT_BLOCK_CREATE_INPUTS = ("unitId", "blockType", "blockedFrom", "blockedUntil", "reason")
_UNIT_BLOCK_UPDATE_FIELDS = frozenset(
    {"blockType", "blockedFrom", "blockedUntil", "assignedTo", "costVnd", "reason", "notes"}
)

_WRITE_GOALS = frozenset(
    {
        AgentGoalType.REFUND_REQUEST,
        AgentGoalType.PAYMENT_CHECKOUT,
        AgentGoalType.RENTAL_EXTENSION,
        AgentGoalType.RENTAL_REALLOCATION,
        AgentGoalType.RENTAL_CANCELLATION,
        AgentGoalType.UNIT_BLOCK_CHANGE,
        AgentGoalType.STOCK_TRANSFER_CREATE,
        AgentGoalType.STOCK_TRANSFER_DECISION,
    }
)

_UUID_INPUT_FIELDS: dict[AgentGoalType, tuple[str, ...]] = {
    AgentGoalType.PAYMENT_SUMMARY: ("orderId",),
    AgentGoalType.RENTAL_ORDER_LOOKUP: ("orderId",),
    AgentGoalType.STOCK_TRANSFER_LOOKUP: ("transferId",),
    AgentGoalType.STOCK_TRANSFER_DECISION: ("transferId",),
    AgentGoalType.UNIT_SCHEDULE: ("unitId",),
    AgentGoalType.RENTAL_EXTENSION: ("orderId",),
    AgentGoalType.RENTAL_CANCELLATION: ("orderId",),
    AgentGoalType.PAYMENT_CHECKOUT: ("orderId",),
    AgentGoalType.REFUND_REQUEST: ("paymentId",),
    AgentGoalType.AVAILABILITY_CHECK: ("variantId", "pickupBranchId"),
    AgentGoalType.RENTAL_REALLOCATION: ("orderId", "orderItemId", "unitId"),
    AgentGoalType.STOCK_TRANSFER_CREATE: ("fromBranchId", "toBranchId"),
}

_TIMESTAMP_INPUT_FIELDS: dict[AgentGoalType, tuple[str, ...]] = {
    AgentGoalType.AVAILABILITY_CHECK: ("plannedStartAt", "plannedDueAt"),
    AgentGoalType.RENTAL_EXTENSION: ("newDueAt",),
    AgentGoalType.UNIT_BLOCK_CHANGE: ("blockedFrom", "blockedUntil"),
}


@dataclass(frozen=True)
class GoalResolution:
    goal: AgentGoalSpec
    token_usage: int = 0


def _plain(value: str) -> str:
    normalized = unicodedata.normalize("NFD", value.lower())
    without_marks = "".join(
        character for character in normalized if unicodedata.category(character) != "Mn"
    )
    return without_marks.replace("đ", "d")


def _contains(text: str, *terms: str) -> bool:
    return any(term in text for term in terms)


def _match_rule(message: str) -> AgentGoalType | None:
    text = _plain(message)
    identifiers = _UUID_PATTERN.findall(message)
    if _contains(text, "hoan tien", "refund") and _contains(
        text, "yeu cau", "request", "tao", "create"
    ):
        return AgentGoalType.REFUND_REQUEST
    if _contains(text, "tao thanh toan", "tao checkout", "create checkout", "payment checkout"):
        return AgentGoalType.PAYMENT_CHECKOUT
    if _contains(text, "gia han", "extend", "giu them", "doi ngay tra", "muon them"):
        return AgentGoalType.RENTAL_EXTENSION
    if _contains(text, "doi bo", "doi trang phuc", "reallocate"):
        return AgentGoalType.RENTAL_REALLOCATION
    if _contains(text, "huy don", "cancel order"):
        return AgentGoalType.RENTAL_CANCELLATION
    if _contains(text, "tao lich", "tao block", "create block", "cap nhat block", "huy block"):
        return AgentGoalType.UNIT_BLOCK_CHANGE
    if _contains(text, "duyet chuyen", "approve transfer", "tu choi chuyen", "reject transfer"):
        return AgentGoalType.STOCK_TRANSFER_DECISION
    if _contains(text, "tao dieu chuyen", "tao chuyen kho", "create transfer"):
        return AgentGoalType.STOCK_TRANSFER_CREATE
    if _contains(text, "thanh toan", "tien coc", "quyet toan", "hoan tien", "payment", "refund"):
        return AgentGoalType.PAYMENT_SUMMARY
    if _contains(
        text,
        "kha dung",
        "con trong",
        "availability",
        "co san",
        "trong lich",
        "kiem tra variant",
    ):
        return AgentGoalType.AVAILABILITY_CHECK
    if _contains(text, "dieu chuyen", "chuyen kho", "transfer"):
        return AgentGoalType.STOCK_TRANSFER_LOOKUP
    if _contains(
        text,
        "lich cua bo",
        "lich unit",
        "lich su dung cua unit",
        "unit schedule",
        "lich trang phuc",
    ):
        return AgentGoalType.UNIT_SCHEDULE
    if _contains(text, "don thue", "don hang", "rental order", "order") or (
        re.search(r"\bdon\b", text) and _contains(text, "tim", "doc chi tiet", "tra cuu")
    ):
        return (
            AgentGoalType.RENTAL_ORDER_LOOKUP if identifiers else AgentGoalType.RENTAL_ORDER_SEARCH
        )
    if _contains(
        text,
        "chinh sach",
        "quy trinh",
        "quy dinh",
        "huong dan",
        "bao lau",
        "policy",
        "process",
    ):
        return AgentGoalType.KNOWLEDGE_ANSWER
    return None


def _rule_inputs(
    goal_type: AgentGoalType,
    identifiers: tuple[str, ...],
    timestamps: tuple[str, ...],
) -> dict[str, Any]:
    values: dict[str, Any] = {}
    first_id_goals = {
        AgentGoalType.PAYMENT_SUMMARY: "orderId",
        AgentGoalType.RENTAL_ORDER_LOOKUP: "orderId",
        AgentGoalType.STOCK_TRANSFER_LOOKUP: "transferId",
        AgentGoalType.STOCK_TRANSFER_DECISION: "transferId",
        AgentGoalType.UNIT_SCHEDULE: "unitId",
        AgentGoalType.RENTAL_EXTENSION: "orderId",
        AgentGoalType.RENTAL_CANCELLATION: "orderId",
        AgentGoalType.PAYMENT_CHECKOUT: "orderId",
        AgentGoalType.REFUND_REQUEST: "paymentId",
    }
    first_field = first_id_goals.get(goal_type)
    if first_field is not None and identifiers:
        values[first_field] = identifiers[0]
    if goal_type is AgentGoalType.AVAILABILITY_CHECK:
        if len(identifiers) >= 1:
            values["variantId"] = identifiers[0]
        if len(identifiers) >= 2:
            values["pickupBranchId"] = identifiers[1]
        if len(timestamps) >= 1:
            values["plannedStartAt"] = timestamps[0]
        if len(timestamps) >= 2:
            values["plannedDueAt"] = timestamps[1]
    elif goal_type is AgentGoalType.RENTAL_EXTENSION and timestamps:
        values["newDueAt"] = timestamps[-1]
    elif goal_type is AgentGoalType.RENTAL_REALLOCATION:
        for field_name, value in zip(
            ("orderId", "orderItemId", "unitId"), identifiers, strict=False
        ):
            values[field_name] = value
    elif goal_type is AgentGoalType.STOCK_TRANSFER_CREATE:
        if len(identifiers) >= 1:
            values["fromBranchId"] = identifiers[0]
        if len(identifiers) >= 2:
            values["toBranchId"] = identifiers[1]
        if len(identifiers) >= 3:
            values["unitIds"] = list(identifiers[2:])
    elif goal_type is AgentGoalType.UNIT_SCHEDULE:
        if timestamps:
            values["from"] = timestamps[0]
        if len(timestamps) >= 2:
            values["to"] = timestamps[1]
    return values


def _unit_block_rule_inputs(
    message: str,
    identifiers: tuple[str, ...],
    timestamps: tuple[str, ...],
) -> dict[str, Any]:
    """Extract the operation-specific unit-block contract without guessing values."""
    text = _plain(message)
    if _contains(text, "huy block", "cancel block"):
        action = "cancel"
    elif _contains(text, "cap nhat block", "update block"):
        action = "update"
    else:
        action = "create"

    values: dict[str, Any] = {"blockAction": action}
    if identifiers:
        values["unitId" if action == "create" else "blockId"] = identifiers[0]
    if action != "cancel":
        if timestamps:
            values["blockedFrom"] = timestamps[0]
        if len(timestamps) >= 2:
            values["blockedUntil"] = timestamps[1]
    block_types = (
        (("ve sinh", "cleaning"), "CLEANING"),
        (("sua chua", "repair"), "REPAIR"),
        (("chinh sua", "alteration"), "ALTERATION"),
        (("kiem tra", "inspection"), "INSPECTION"),
        (("noi bo", "internal use"), "INTERNAL_USE"),
        (("thu cong", "manual"), "MANUAL"),
        (("khac", "other"), "OTHER"),
    )
    for aliases, block_type in block_types:
        if _contains(text, *aliases):
            values["blockType"] = block_type
            break
    return values


def _continuation_rule_inputs(
    goal_type: AgentGoalType,
    identifiers: tuple[str, ...],
    timestamps: tuple[str, ...],
    current_values: dict[str, Any],
) -> dict[str, Any]:
    """Fill only missing positional fields when a follow-up has unlabeled values."""
    values: dict[str, Any] = {}
    remaining_ids = list(identifiers)
    if goal_type is AgentGoalType.UNIT_BLOCK_CHANGE:
        action = current_values.get("blockAction", "create")
        target = "unitId" if action == "create" else "blockId"
        if current_values.get(target) in (None, "") and remaining_ids:
            values[target] = remaining_ids.pop(0)
        remaining_timestamps = list(timestamps)
        for field_name in ("blockedFrom", "blockedUntil"):
            if current_values.get(field_name) in (None, "") and remaining_timestamps:
                values[field_name] = remaining_timestamps.pop(0)
        return values
    for field_name in _UUID_INPUT_FIELDS.get(goal_type, ()):
        if current_values.get(field_name) in (None, "") and remaining_ids:
            values[field_name] = remaining_ids.pop(0)

    if (
        goal_type is AgentGoalType.STOCK_TRANSFER_CREATE
        and current_values.get("unitIds") in (None, [], ())
        and remaining_ids
    ):
        values["unitIds"] = remaining_ids

    remaining_timestamps = list(timestamps)
    for field_name in _TIMESTAMP_INPUT_FIELDS.get(goal_type, ()):
        if current_values.get(field_name) in (None, "") and remaining_timestamps:
            values[field_name] = remaining_timestamps.pop(0)
    return values


def _continuation_labeled_text_inputs(
    message: str,
    missing_inputs: tuple[str, ...],
) -> dict[str, Any]:
    """Extract explicitly labelled free-text answers from a follow-up message."""
    labels = {
        "reason": (
            "lý do hủy",
            "ly do huy",
            "cancellation reason",
            "lý do",
            "ly do",
            "reason",
        ),
        "purpose": ("mục đích", "muc dich", "purpose"),
        "search": ("tìm kiếm", "tim kiem", "search"),
    }
    for field_name in missing_inputs:
        aliases = labels.get(field_name)
        if aliases is None:
            continue
        label_pattern = "|".join(re.escape(alias) for alias in aliases)
        match = re.fullmatch(
            rf"\s*(?:{label_pattern})\s*[:\-]\s*(\S(?:.*\S)?)\s*",
            message,
            flags=re.IGNORECASE,
        )
        if match:
            return {field_name: match.group(1)}
    return {}


def _identifiers_from_inputs(values: dict[str, Any]) -> tuple[str, ...]:
    serialized = json.dumps(values, default=str)
    return tuple(dict.fromkeys(match.lower() for match in _UUID_PATTERN.findall(serialized)))


def _missing_inputs(goal_type: AgentGoalType, values: dict[str, Any]) -> tuple[str, ...]:
    if goal_type is AgentGoalType.STOCK_TRANSFER_DECISION:
        return ("approvalEndpoint",)
    if goal_type is AgentGoalType.UNIT_BLOCK_CHANGE:
        action = values.get("blockAction", "create")
        required: tuple[str, ...]
        if action == "cancel":
            required = ("blockId", "reason")
        elif action == "update":
            required = ("blockId",)
        else:
            required = _UNIT_BLOCK_CREATE_INPUTS
        missing = [field for field in required if values.get(field) in (None, "", [], ())]
        if action == "update" and not _UNIT_BLOCK_UPDATE_FIELDS.intersection(values):
            missing.append("blockChange")
        return tuple(missing)
    return tuple(
        field_name
        for field_name in _REQUIRED_INPUTS.get(goal_type, ())
        if values.get(field_name) in (None, "", [], ())
    )


def _build_goal(
    *,
    message: str,
    goal_type: AgentGoalType,
    extracted_inputs: dict[str, Any] | None = None,
    source: Literal["rule", "model", "fallback", "continuation"] = "rule",
    confidence: float = 1.0,
    extra_missing: tuple[str, ...] = (),
) -> AgentGoalSpec:
    identifiers = tuple(dict.fromkeys(match.lower() for match in _UUID_PATTERN.findall(message)))
    timestamps = tuple(_ISO_TIMESTAMP_PATTERN.findall(message))
    values = _rule_inputs(goal_type, identifiers, timestamps)
    if goal_type is AgentGoalType.RENTAL_ORDER_SEARCH:
        code_match = re.search(
            r"(?:mã(?:\s+đơn)?|ma(?:\s+don)?|code)\s*[:#]?\s*[`'\"]?([A-Za-z0-9][A-Za-z0-9_-]{1,63})",
            message,
            flags=re.IGNORECASE,
        )
        if code_match:
            values["search"] = code_match.group(1)
    if goal_type is AgentGoalType.UNIT_BLOCK_CHANGE:
        values.update(_unit_block_rule_inputs(message, identifiers, timestamps))
    values.update(extracted_inputs or {})
    required_tools, success_criteria = _GOAL_CONTRACTS[goal_type]
    if goal_type is AgentGoalType.UNIT_BLOCK_CHANGE:
        action_tool = {
            "create": "create_unit_block",
            "update": "update_unit_block",
            "cancel": "cancel_unit_block",
        }[str(values.get("blockAction", "create"))]
        required_tools = (
            ("get_unit_schedule", action_tool, "get_unit_block")
            if action_tool == "create_unit_block"
            else ("get_unit_block", action_tool)
        )
    missing = tuple(dict.fromkeys((*_missing_inputs(goal_type, values), *extra_missing)))
    return attach_skill(
        AgentGoalSpec(
            summary=message,
            goal_type=goal_type,
            required_tools=required_tools,
            required_identifiers=tuple(
                dict.fromkeys((*identifiers, *_identifiers_from_inputs(values)))
            ),
            extracted_inputs=values,
            missing_inputs=missing,
            success_criteria=success_criteria,
            resolution_source=source,
            confidence=confidence,
        )
    )


def infer_goal(message: str) -> AgentGoalSpec:
    """Deterministic fast-path kept for explicit commands and offline fallback."""
    goal_type = _match_rule(message) or AgentGoalType.GENERAL_ASSISTANCE
    if goal_type is AgentGoalType.GENERAL_ASSISTANCE:
        return _build_goal(message=message, goal_type=goal_type, source="fallback")
    return _build_goal(message=message, goal_type=goal_type, source="rule")


def _classification_models() -> tuple[ChatOpenAI, ...]:
    settings = get_settings()
    models: list[ChatOpenAI] = []
    if settings.GROQ_API_KEY:
        models.append(
            ChatOpenAI(
                model=settings.GROQ_MODEL,
                api_key=SecretStr(settings.GROQ_API_KEY),
                base_url=settings.GROQ_BASE_URL,
                timeout=settings.LLM_TIMEOUT_SECONDS,
                temperature=0,
                max_tokens=512,
                max_retries=0,
            )
        )
    if settings.GEMINI_API_KEY:
        models.append(
            ChatOpenAI(
                model=settings.GEMINI_MODEL,
                api_key=SecretStr(settings.GEMINI_API_KEY),
                base_url=settings.GEMINI_BASE_URL,
                timeout=settings.LLM_TIMEOUT_SECONDS,
                temperature=0,
                max_tokens=512,
                max_retries=0,
            )
        )
    return tuple(models)


def _token_total(metadata: dict[str, Any]) -> int:
    total = 0
    for usage in metadata.values():
        if not isinstance(usage, dict):
            continue
        value = usage.get("total_tokens")
        if isinstance(value, int):
            total += value
        else:
            input_tokens = usage.get("input_tokens", 0)
            output_tokens = usage.get("output_tokens", 0)
            if isinstance(input_tokens, int) and isinstance(output_tokens, int):
                total += input_tokens + output_tokens
    return total


async def _classify_goal(
    message: str, previous_goal: AgentGoalSpec | None = None
) -> tuple[GoalDraft | None, int]:
    models = _classification_models()
    if not models:
        return None, 0
    previous = (
        json.dumps(
            {
                "goalType": previous_goal.goal_type.value,
                "entities": previous_goal.extracted_inputs,
                "missingInputs": previous_goal.missing_inputs,
            },
            ensure_ascii=False,
            default=str,
        )
        if previous_goal
        else "none"
    )
    prompt = [
        SystemMessage(
            content=(
                "Classify a Vietnamese costume-rental operations request. Return only the "
                "GoalDraft schema. Never invent IDs, timestamps, amounts, reasons, or business "
                "facts. Use GENERAL_ASSISTANCE when no supported intent fits. Mark "
                "explicit_write_intent true only when the user clearly asks to change data. "
                "For a follow-up, preserve the previous goal unless the user explicitly changes "
                "the task. Allowed goal types: " + ", ".join(item.value for item in AgentGoalType)
            )
        ),
        HumanMessage(content=f"Previous structured goal: {previous}\nCurrent request: {message}"),
    ]
    consumed_tokens = 0
    for model in models:
        callback = UsageMetadataCallbackHandler()
        try:
            response = await model.with_structured_output(GoalDraft).ainvoke(
                prompt, config={"callbacks": [callback]}
            )
            consumed_tokens += _token_total(callback.usage_metadata)
            return GoalDraft.model_validate(response), consumed_tokens
        except Exception as error:
            consumed_tokens += _token_total(callback.usage_metadata)
            logger.warning(
                "Goal classifier provider failed",
                extra={"provider_model": model.model_name, "error_type": type(error).__name__},
            )
    return None, consumed_tokens


def _draft_inputs(draft: GoalDraft) -> dict[str, Any]:
    values = draft.entities.model_dump(mode="json", by_alias=True, exclude_none=True)
    return {key: value for key, value in values.items() if value not in ("", [], ())}


def _numeric_values(message: str) -> frozenset[str]:
    values: set[str] = set()
    for candidate in re.findall(r"(?<![0-9a-fA-F-])\d[\d.,\s]*", message):
        digits = re.sub(r"\D", "", candidate)
        if digits:
            values.add(digits)
    return frozenset(values)


def _trusted_draft_inputs(
    draft: GoalDraft,
    message: str,
    previous_goal: AgentGoalSpec | None = None,
) -> dict[str, Any]:
    """Keep model-extracted values only when their source is visible to runtime."""
    proposed = _draft_inputs(draft)
    prior = previous_goal.extracted_inputs if previous_goal is not None else {}
    message_lower = message.lower()
    message_plain = _plain(message)
    numeric_values = _numeric_values(message)
    identifiers = tuple(match.lower() for match in _UUID_PATTERN.findall(message))
    timestamps = tuple(_ISO_TIMESTAMP_PATTERN.findall(message))
    expected = (
        _continuation_rule_inputs(draft.goal_type, identifiers, timestamps, prior)
        if previous_goal is not None
        else _rule_inputs(draft.goal_type, identifiers, timestamps)
    )
    used_identifiers = {
        match.lower()
        for value in prior.values()
        for match in _UUID_PATTERN.findall(json.dumps(value, default=str))
    }
    trusted: dict[str, Any] = {}
    for field_name, value in proposed.items():
        prior_value = prior.get(field_name)
        if prior_value not in (None, "", [], ()):
            if prior_value == value:
                trusted[field_name] = value
            # Existing validated fields are immutable in ordinary continuation.
            continue
        if field_name == "unitIds" and isinstance(value, list):
            normalized = [str(item).lower() for item in value]
            expected_units = [str(item).lower() for item in expected.get("unitIds", [])]
            if (
                normalized
                and normalized == expected_units
                and len(normalized) == len(set(normalized))
                and not used_identifiers.intersection(normalized)
            ):
                trusted[field_name] = value
                used_identifiers.update(normalized)
            continue
        value_text = str(value).lower()
        if _UUID_PATTERN.fullmatch(value_text):
            if expected.get(field_name) == value and value_text not in used_identifiers:
                trusted[field_name] = value
                used_identifiers.add(value_text)
            continue
        if field_name in _TIMESTAMP_INPUT_FIELDS.get(draft.goal_type, ()):
            if expected.get(field_name) == value:
                trusted[field_name] = value
            continue
        if prior.get(field_name) == value:
            trusted[field_name] = value
            continue
        if field_name == "amountVnd" and str(value) in numeric_values:
            trusted[field_name] = value
            continue
        if field_name in {"reason", "purpose", "search", "blockType"}:
            if _plain(str(value)) in message_plain:
                trusted[field_name] = value
            continue
        if str(value).lower() in message_lower:
            trusted[field_name] = value
    return trusted


def _confirms_write_intent(message: str) -> bool:
    text = _plain(message)
    return _contains(
        text,
        "xac nhan thuc hien",
        "dong y thuc hien",
        "hay thuc hien",
        "thuc hien di",
        "yes, proceed",
        "confirm and proceed",
    )


def _is_question_like(message: str) -> bool:
    text = _plain(message).strip()
    return (
        message.rstrip().endswith("?")
        or text.startswith(("can ", "could ", "would ", "is it possible", "co the ", "lieu "))
        or _contains(text, "duoc khong", "co duoc", "khong vay", "how to", "lam sao")
    )


def _write_intent_gate(
    message: str,
    goal_type: AgentGoalType,
    *,
    model_explicit: bool = False,
    rule_matched: bool = False,
) -> tuple[str, ...]:
    if goal_type not in _WRITE_GOALS:
        return ()
    if _is_question_like(message):
        return ("writeIntent",)
    if rule_matched or model_explicit:
        return ()
    return ("writeIntent",)


def _merge_continuation(
    previous_goal: AgentGoalSpec,
    message: str,
    draft: GoalDraft | None,
) -> AgentGoalSpec:
    identifiers = tuple(dict.fromkeys(match.lower() for match in _UUID_PATTERN.findall(message)))
    timestamps = tuple(_ISO_TIMESTAMP_PATTERN.findall(message))
    values = dict(previous_goal.extracted_inputs)
    values.update(
        _continuation_rule_inputs(
            previous_goal.goal_type,
            identifiers,
            timestamps,
            values,
        )
    )
    values.update(_continuation_labeled_text_inputs(message, previous_goal.missing_inputs))
    if draft is not None and draft.goal_type in {
        previous_goal.goal_type,
        AgentGoalType.GENERAL_ASSISTANCE,
    }:
        values.update(_trusted_draft_inputs(draft, message, previous_goal))
    safety_missing = tuple(item for item in previous_goal.missing_inputs if item in _SAFETY_INPUTS)
    if "writeIntent" in safety_missing and _confirms_write_intent(message):
        safety_missing = tuple(item for item in safety_missing if item != "writeIntent")
    summary = f"{previous_goal.summary}\nThông tin bổ sung: {message}"[-2_000:]
    return _build_goal(
        message=summary,
        goal_type=previous_goal.goal_type,
        extracted_inputs=values,
        source="continuation",
        confidence=max(previous_goal.confidence, draft.confidence if draft else 0),
        extra_missing=safety_missing,
    )


async def resolve_goal(
    message: str,
    previous_goal: AgentGoalSpec | None = None,
    *,
    allow_model: bool = True,
) -> GoalResolution:
    """Resolve a safe goal from rules, structured model output, or prior case state."""
    rule_type = _match_rule(message)
    if previous_goal is not None:
        rule_values = _continuation_rule_inputs(
            previous_goal.goal_type,
            tuple(match.lower() for match in _UUID_PATTERN.findall(message)),
            tuple(_ISO_TIMESTAMP_PATTERN.findall(message)),
            previous_goal.extracted_inputs,
        )
        if rule_values:
            return GoalResolution(_merge_continuation(previous_goal, message, None))
        draft, tokens = await _classify_goal(message, previous_goal) if allow_model else (None, 0)
        if (
            draft is not None
            and draft.confidence >= _MODEL_CONFIDENCE_THRESHOLD
            and draft.goal_type is not previous_goal.goal_type
            and draft.goal_type is not AgentGoalType.GENERAL_ASSISTANCE
        ):
            extra_missing = _write_intent_gate(
                message,
                draft.goal_type,
                model_explicit=draft.explicit_write_intent,
            )
            return GoalResolution(
                _build_goal(
                    message=message,
                    goal_type=draft.goal_type,
                    extracted_inputs=_trusted_draft_inputs(draft, message, previous_goal),
                    source="model",
                    confidence=draft.confidence,
                    extra_missing=extra_missing,
                ),
                tokens,
            )
        return GoalResolution(_merge_continuation(previous_goal, message, draft), tokens)

    if rule_type is not None:
        rule_goal = _build_goal(
            message=message,
            goal_type=rule_type,
            extra_missing=_write_intent_gate(
                message,
                rule_type,
                rule_matched=True,
            ),
        )
        if not rule_goal.missing_inputs:
            return GoalResolution(rule_goal)
        draft, tokens = await _classify_goal(message) if allow_model else (None, 0)
        if (
            draft is None
            or draft.confidence < _MODEL_CONFIDENCE_THRESHOLD
            or draft.goal_type is not rule_type
        ):
            return GoalResolution(rule_goal, tokens)
        return GoalResolution(
            _build_goal(
                message=message,
                goal_type=rule_type,
                extracted_inputs=_trusted_draft_inputs(draft, message),
                source="model",
                confidence=draft.confidence,
                extra_missing=_write_intent_gate(
                    message,
                    rule_type,
                    model_explicit=draft.explicit_write_intent,
                    rule_matched=True,
                ),
            ),
            tokens,
        )

    draft, tokens = await _classify_goal(message) if allow_model else (None, 0)
    if draft is None:
        return GoalResolution(infer_goal(message), tokens)
    if draft.confidence < _MODEL_CONFIDENCE_THRESHOLD:
        return GoalResolution(
            _build_goal(
                message=message,
                goal_type=AgentGoalType.GENERAL_ASSISTANCE,
                source="model",
                confidence=draft.confidence,
                extra_missing=("goalIntent",),
            ),
            tokens,
        )
    extra_missing = _write_intent_gate(
        message,
        draft.goal_type,
        model_explicit=draft.explicit_write_intent,
    )
    return GoalResolution(
        _build_goal(
            message=message,
            goal_type=draft.goal_type,
            extracted_inputs=_trusted_draft_inputs(draft, message),
            source="model",
            confidence=draft.confidence,
            extra_missing=extra_missing,
        ),
        tokens,
    )


def missing_input_question(goal: AgentGoalSpec) -> str | None:
    """Return one stable clarification question before invoking tools."""
    if not goal.missing_inputs:
        return None
    if "approvalEndpoint" in goal.missing_inputs:
        return (
            "Thao tác duyệt hoặc từ chối điều chuyển chỉ được thực hiện qua endpoint "
            "approval của case đang chờ, không thực hiện bằng message mới."
        )
    if "goalIntent" in goal.missing_inputs:
        return "Bạn muốn tôi kiểm tra thông tin hay thực hiện nghiệp vụ nào?"
    if "writeIntent" in goal.missing_inputs:
        return "Bạn có muốn thực hiện thay đổi này không? Vui lòng xác nhận rõ yêu cầu."
    labels = {
        "orderId": "ID đơn thuê",
        "transferId": "ID phiếu điều chuyển",
        "unitId": "ID bộ trang phục",
        "variantId": "ID mẫu trang phục",
        "pickupBranchId": "ID chi nhánh nhận",
        "plannedStartAt": "thời gian bắt đầu theo ISO-8601",
        "plannedDueAt": "thời gian trả theo ISO-8601",
        "blockId": "ID lịch khóa bộ trang phục",
        "blockType": "loại lịch khóa",
        "blockedFrom": "thời gian khóa bắt đầu theo ISO-8601",
        "blockedUntil": "thời gian khóa kết thúc theo ISO-8601",
        "blockChange": "ít nhất một nội dung cần cập nhật cho lịch khóa",
        "newDueAt": "thời gian trả mới theo ISO-8601",
        "orderItemId": "ID dòng hàng trong đơn",
        "paymentId": "ID thanh toán",
        "fromBranchId": "ID chi nhánh nguồn",
        "toBranchId": "ID chi nhánh đích",
        "unitIds": "danh sách ID bộ trang phục",
        "amountVnd": "số tiền VND",
        "purpose": "mục đích thanh toán",
        "reason": "lý do",
    }
    missing = ", ".join(labels.get(item, item) for item in goal.missing_inputs)
    return f"Vui lòng cung cấp {missing} để tôi xử lý chính xác."
