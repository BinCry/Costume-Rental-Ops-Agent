"""Deterministic first-pass goal contract for the bounded operations agent."""

import re
import unicodedata

from app.agent_tools.models import AgentGoalSpec, AgentGoalType
from app.agent_tools.skills import attach_skill

_UUID_PATTERN = re.compile(
    r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-"
    r"[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}\b"
)
_ISO_TIMESTAMP_PATTERN = re.compile(
    r"\b\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2})?(?:Z|[+-]\d{2}:\d{2})?\b"
)


def _plain(value: str) -> str:
    normalized = unicodedata.normalize("NFD", value.lower())
    without_marks = "".join(
        character for character in normalized if unicodedata.category(character) != "Mn"
    )
    return without_marks.replace("đ", "d")


def _contains(text: str, *terms: str) -> bool:
    return any(term in text for term in terms)


def infer_goal(message: str) -> AgentGoalSpec:
    """Create a measurable goal without trusting the model to define its own success."""
    text = _plain(message)
    identifiers = tuple(dict.fromkeys(match.lower() for match in _UUID_PATTERN.findall(message)))
    timestamps = tuple(_ISO_TIMESTAMP_PATTERN.findall(message))

    def goal(**values: object) -> AgentGoalSpec:
        return attach_skill(AgentGoalSpec.model_validate(values))

    if _contains(text, "hoan tien", "refund") and _contains(
        text, "yeu cau", "request", "tao", "create"
    ):
        return goal(
            summary=message,
            goal_type=AgentGoalType.REFUND_REQUEST,
            required_tools=("get_payment", "request_refund", "get_refund_by_idempotency_key"),
            required_identifiers=identifiers,
            success_criteria=(
                "requester_confirmed",
                "financial_approval_granted",
                "refund_request_verified",
            ),
        )
    if _contains(text, "tao thanh toan", "tao checkout", "create checkout", "payment checkout"):
        return goal(
            summary=message,
            goal_type=AgentGoalType.PAYMENT_CHECKOUT,
            required_tools=(
                "get_rental_order",
                "create_payment_checkout",
                "get_payment_by_idempotency_key",
            ),
            required_identifiers=identifiers,
            success_criteria=(
                "requester_confirmed",
                "financial_approval_granted",
                "checkout_verified",
            ),
        )
    if _contains(text, "gia han", "extend"):
        return goal(
            summary=message,
            goal_type=AgentGoalType.RENTAL_EXTENSION,
            required_tools=("get_rental_order", "check_availability", "extend_rental_order"),
            required_identifiers=identifiers,
            success_criteria=("requester_confirmed", "new_due_time_verified"),
        )
    if _contains(text, "doi bo", "doi trang phuc", "reallocate"):
        return goal(
            summary=message,
            goal_type=AgentGoalType.RENTAL_REALLOCATION,
            required_tools=("get_rental_order", "check_availability", "reallocate_rental_item"),
            required_identifiers=identifiers,
            success_criteria=("requester_confirmed", "new_allocation_verified"),
        )
    if _contains(text, "huy don", "cancel order"):
        return goal(
            summary=message,
            goal_type=AgentGoalType.RENTAL_CANCELLATION,
            required_tools=("get_rental_order", "cancel_rental_order"),
            required_identifiers=identifiers,
            success_criteria=("requester_confirmed", "cancelled_order_verified"),
        )
    if _contains(text, "tao lich", "tao block", "create block", "cap nhat block", "huy block"):
        return goal(
            summary=message,
            goal_type=AgentGoalType.UNIT_BLOCK_CHANGE,
            required_tools=("get_unit_schedule", "get_unit_block"),
            required_identifiers=identifiers,
            success_criteria=("requester_confirmed", "unit_block_verified"),
        )
    if _contains(text, "duyet chuyen", "approve transfer", "tu choi chuyen", "reject transfer"):
        return goal(
            summary=message,
            goal_type=AgentGoalType.STOCK_TRANSFER_DECISION,
            required_tools=(),
            required_identifiers=identifiers,
            missing_inputs=("approvalEndpoint",),
            success_criteria=("branch_approval_checked", "transfer_decision_verified"),
        )
    if _contains(text, "tao dieu chuyen", "tao chuyen kho", "create transfer"):
        return goal(
            summary=message,
            goal_type=AgentGoalType.STOCK_TRANSFER_CREATE,
            required_tools=("create_stock_transfer", "get_stock_transfer"),
            required_identifiers=identifiers,
            success_criteria=(
                "requester_confirmed",
                "branch_approval_granted",
                "transfer_verified",
            ),
        )
    if _contains(
        text, "thanh toan", "tien coc", "quyet toan", "hoan tien", "payment", "refund"
    ):
        return goal(
            summary=message,
            goal_type=AgentGoalType.PAYMENT_SUMMARY,
            required_tools=("get_payment_summary",),
            required_identifiers=identifiers,
            missing_inputs=() if identifiers else ("orderId",),
            success_criteria=("payment_summary_observed", "requested_record_matches"),
        )
    if _contains(text, "kha dung", "con trong", "availability", "co san", "trong lich"):
        return goal(
            summary=message,
            goal_type=AgentGoalType.AVAILABILITY_CHECK,
            required_tools=("check_availability",),
            required_identifiers=identifiers,
            missing_inputs=tuple(
                item
                for item, present in (
                    ("variantId", len(identifiers) >= 1),
                    ("pickupBranchId", len(identifiers) >= 2),
                    ("plannedStartAt", len(timestamps) >= 1),
                    ("plannedDueAt", len(timestamps) >= 2),
                )
                if not present
            ),
            success_criteria=("availability_observed", "requested_scope_matches"),
        )
    if _contains(text, "dieu chuyen", "chuyen kho", "transfer"):
        return goal(
            summary=message,
            goal_type=AgentGoalType.STOCK_TRANSFER_LOOKUP,
            required_tools=("get_stock_transfer",),
            required_identifiers=identifiers,
            missing_inputs=() if identifiers else ("transferId",),
            success_criteria=("stock_transfer_observed", "requested_record_matches"),
        )
    if _contains(text, "lich cua bo", "lich unit", "unit schedule", "lich trang phuc"):
        return goal(
            summary=message,
            goal_type=AgentGoalType.UNIT_SCHEDULE,
            required_tools=("get_unit_schedule",),
            required_identifiers=identifiers,
            missing_inputs=() if identifiers else ("unitId",),
            success_criteria=("unit_schedule_observed", "requested_record_matches"),
        )
    if _contains(text, "don thue", "don hang", "rental order", "order"):
        tool = "get_rental_order" if identifiers else "find_rental_orders"
        goal_type = (
            AgentGoalType.RENTAL_ORDER_LOOKUP if identifiers else AgentGoalType.RENTAL_ORDER_SEARCH
        )
        criterion = "rental_order_observed" if identifiers else "rental_orders_searched"
        return goal(
            summary=message,
            goal_type=goal_type,
            required_tools=(tool,),
            required_identifiers=identifiers,
            success_criteria=(criterion, "requested_scope_matches"),
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
        return goal(
            summary=message,
            goal_type=AgentGoalType.KNOWLEDGE_ANSWER,
            required_tools=("search_knowledge",),
            required_identifiers=identifiers,
            success_criteria=("approved_knowledge_observed", "citation_available"),
        )
    return goal(
        summary=message,
        goal_type=AgentGoalType.GENERAL_ASSISTANCE,
        required_identifiers=identifiers,
        success_criteria=("answer_is_grounded_or_input_requested",),
    )


def missing_input_question(goal: AgentGoalSpec) -> str | None:
    """Return one stable clarification question before invoking the model or tools."""
    if not goal.missing_inputs:
        return None
    if "approvalEndpoint" in goal.missing_inputs:
        return (
            "Thao tác duyệt hoặc từ chối điều chuyển chỉ được thực hiện qua endpoint "
            "approval của case đang chờ, không thực hiện bằng message mới."
        )
    labels = {
        "orderId": "ID đơn thuê",
        "transferId": "ID phiếu điều chuyển",
        "unitId": "ID bộ trang phục",
        "variantId": "ID mẫu trang phục",
        "pickupBranchId": "ID chi nhánh nhận",
        "plannedStartAt": "thời gian bắt đầu theo ISO-8601",
        "plannedDueAt": "thời gian trả theo ISO-8601",
    }
    missing = ", ".join(labels.get(item, item) for item in goal.missing_inputs)
    return f"Vui lòng cung cấp {missing} để tôi kiểm tra chính xác."
