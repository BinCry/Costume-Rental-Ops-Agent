"""Structured, non-executing write-action planner.

The planner never receives a callable write tool.  Its output is only an
untrusted proposal which runtime canonicalizes and freezes before asking for a
human confirmation.
"""

from dataclasses import dataclass
from typing import Any, Final

from langchain_core.callbacks import UsageMetadataCallbackHandler
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from pydantic import SecretStr

from app.agent_tools.models import ActionProposal, AgentGoalSpec
from app.config import get_settings

WRITE_TOOL_NAMES: Final = frozenset(
    {
        "create_unit_block",
        "update_unit_block",
        "cancel_unit_block",
        "extend_rental_order",
        "reallocate_rental_item",
        "cancel_rental_order",
        "create_stock_transfer",
        "create_payment_checkout",
        "request_refund",
    }
)


@dataclass(frozen=True)
class PlanningResult:
    proposal: ActionProposal | None
    token_usage: int = 0


def _token_total(metadata: dict[str, Any]) -> int:
    total = 0
    for usage in metadata.values():
        if not isinstance(usage, dict):
            continue
        value = usage.get("total_tokens")
        if isinstance(value, int):
            total += value
            continue
        input_tokens = usage.get("input_tokens", 0)
        output_tokens = usage.get("output_tokens", 0)
        if isinstance(input_tokens, int) and isinstance(output_tokens, int):
            total += input_tokens + output_tokens
    return total


def is_write_request(message: str) -> bool:
    text = message.casefold()
    return any(
        phrase in text
        for phrase in (
            "gia hạn",
            "gia han",
            "extend",
            "hủy đơn",
            "huy don",
            "cancel order",
            "đổi bộ",
            "doi bo",
            "reallocate",
            "tạo lịch",
            "tao lich",
            "create block",
            "điều chuyển",
            "dieu chuyen",
            "create transfer",
            "duyệt chuyển",
            "duyet chuyen",
            "approve transfer",
            "tạo thanh toán",
            "tao thanh toan",
            "checkout",
            "hoàn tiền",
            "hoan tien",
            "refund",
        )
    )


def _models() -> tuple[ChatOpenAI, ...]:
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
                max_retries=0,
            )
        )
    return tuple(models)


async def propose_write_action(message: str, goal: AgentGoalSpec) -> PlanningResult:
    """Return one structured proposal, or ``None`` when safe planning is impossible."""
    models = _models()
    if not models:
        return PlanningResult(None)
    allowed_write_tools = tuple(
        tool_name for tool_name in goal.constraints.allowed_tools if tool_name in WRITE_TOOL_NAMES
    )
    if not allowed_write_tools:
        return PlanningResult(None)
    plan = "\n".join(
        f"{step.order}. {step.action}; verify: {step.verification}" for step in goal.plan
    )
    prompt = [
        SystemMessage(
            content=(
                "You are an operations action planner. Return exactly one action proposal "
                "only if every argument is explicitly stated or authoritative context has "
                "already supplied it. Allowed tool names: "
                + ", ".join(sorted(allowed_write_tools))
                + ". Never invent IDs, versions, amounts, dates, branch IDs, or reasons. "
                "Always leave expected_version null; runtime obtains it from a fresh read. "
                "For update_unit_block, omit expectedUpdatedAt because runtime supplies it. "
                "This does not execute anything. Follow this business skill: "
                + (goal.skill_name or "unspecified")
                + ". Workflow:\n"
                + plan
            )
        ),
        HumanMessage(content=message),
    ]
    last_error: Exception | None = None
    consumed_tokens = 0
    for model in models:
        callback = UsageMetadataCallbackHandler()
        try:
            response = await model.with_structured_output(ActionProposal).ainvoke(
                prompt, config={"callbacks": [callback]}
            )
            consumed_tokens += _token_total(callback.usage_metadata)
            proposal = ActionProposal.model_validate(response)
            if proposal.tool_name not in allowed_write_tools:
                return PlanningResult(None, consumed_tokens)
            return PlanningResult(proposal, consumed_tokens)
        except Exception as error:
            consumed_tokens += _token_total(callback.usage_metadata)
            last_error = error
    if last_error is not None:
        raise last_error
    return PlanningResult(None, consumed_tokens)
