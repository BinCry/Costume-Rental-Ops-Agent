"""Deterministic overdue-return guidance with an optional narrative layer."""

import json
from typing import Any

from pydantic import Field

from app.models import AgentReadinessAnalysisNarrative, ApiModel


class _NarrativeDraft(ApiModel):
    summary: str = Field(min_length=1, max_length=1_000)
    rationale: list[str] = Field(default_factory=list, max_length=8)
    risks: list[str] = Field(default_factory=list, max_length=8)
    next_step: str = Field(min_length=1, max_length=1_000)


def _fallback(context: dict[str, Any]) -> AgentReadinessAnalysisNarrative:
    overdue_minutes = int(context.get("overdueMinutes") or 0)
    escalation = context.get("escalationRequired") is True
    return AgentReadinessAnalysisNarrative(
        summary=f"Đơn thuê đã quá hạn trả {overdue_minutes} phút và vẫn còn unit ở khách.",
        rationale=[
            "Đơn vẫn ACTIVE sau hạn trả và thời gian ân hạn.",
            "Chỉ các unit có allocation ACTIVE được tính là chưa trả.",
        ],
        risks=["Unit chưa trả không thể được kiểm tra, vệ sinh hoặc đưa lại vào tồn khả dụng."],
        next_step=(
            "Báo quản lý chi nhánh và liên hệ khách để xác nhận thời điểm trả."
            if escalation
            else (
                "Liên hệ khách để xác nhận thời điểm trả; dùng luồng gia hạn riêng "
                "nếu khách yêu cầu."
            )
        ),
        fallback=True,
    )


def simulate(
    context: dict[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]], str | None, str]:
    primary = context["primaryOrder"]
    before = {
        "optionType": "KEEP_OVERDUE_RENTAL_UNCHANGED",
        "status": primary.get("status"),
        "plannedDueAt": primary.get("plannedDueAt"),
        "graceDeadline": context.get("graceDeadline"),
        "overdueMinutes": context.get("overdueMinutes"),
        "feasible": False,
        "reasonCodes": ["RENTAL_RETURN_OVERDUE"],
    }
    options: list[dict[str, Any]] = []
    if context.get("escalationRequired") is True:
        options.append(
            {
                "optionId": "escalate-overdue-return",
                "optionType": "ESCALATE_OVERDUE_RETURN",
                "feasible": True,
                "executable": False,
                "rank": 1,
                "reasonCodes": ["OVERDUE_MORE_THAN_24_HOURS", "MANUAL_CONTACT_REQUIRED"],
            }
        )
    options.append(
        {
            "optionId": "contact-customer-for-return",
            "optionType": "CONTACT_CUSTOMER_FOR_RETURN",
            "feasible": True,
            "executable": False,
            "rank": len(options) + 1,
            "reasonCodes": ["RENTAL_RETURN_OVERDUE", "MANUAL_CONTACT_REQUIRED"],
        }
    )
    snapshot = {
        "ruleCode": "RENTAL_RETURN_OVERDUE",
        "before": before,
        "primaryOrder": primary,
        "lateGraceMinutes": context.get("lateGraceMinutes"),
        "graceDeadline": context.get("graceDeadline"),
        "overdueMinutes": context.get("overdueMinutes"),
        "activeUnits": context.get("activeUnits", []),
        "downstreamReadinessRisk": context.get("downstreamReadinessRisk", False),
        "observedAt": context["observedAt"],
    }
    return snapshot, options, options[0]["optionId"], "READY"


async def explain(
    *, snapshot: dict[str, Any], options: list[dict[str, Any]], recommended_option_id: str | None
) -> AgentReadinessAnalysisNarrative:
    from langchain_core.messages import HumanMessage, SystemMessage

    from app.agent_tools.planner import _models

    fallback = _fallback(
        {
            "overdueMinutes": snapshot.get("overdueMinutes"),
            "escalationRequired": recommended_option_id == "escalate-overdue-return",
        }
    )
    models = _models()
    if not models:
        return fallback
    prompt = [
        SystemMessage(
            content=(
                "You explain an overdue rental-return recommendation in Vietnamese. "
                "Use only supplied facts. Do not create actions, fees, customer details, "
                "extensions, or ranking changes. Keep the response operational and concise."
            )
        ),
        HumanMessage(
            content=json.dumps(
                {
                    "snapshot": snapshot,
                    "options": options,
                    "recommendedOptionId": recommended_option_id,
                },
                ensure_ascii=False,
                default=str,
            )
        ),
    ]
    for model in models:
        try:
            result = await model.with_structured_output(_NarrativeDraft).ainvoke(prompt)
            draft = _NarrativeDraft.model_validate(result)
            return AgentReadinessAnalysisNarrative(
                summary=draft.summary,
                rationale=draft.rationale,
                risks=draft.risks,
                next_step=draft.next_step,
                fallback=False,
            )
        except Exception:
            continue
    return fallback
