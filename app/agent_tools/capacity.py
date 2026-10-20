"""Deterministic, non-executable guidance for branch capacity shortfalls."""

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
    return AgentReadinessAnalysisNarrative(
        summary=(
            f"Khối lượng công việc còn lại "
            f"{int(context.get('remainingRequiredMinutes') or 0)} phút, "
            f"vượt năng lực còn lại "
            f"{int(context.get('remainingAvailableMinutes') or 0)} phút."
        ),
        rationale=[
            "Công việc PLANNED dùng effort ước tính; công việc IN_PROGRESS dùng effort còn lại.",
            "Năng lực còn lại được phân bổ theo phần thời gian chưa trôi qua của capacity window.",
        ],
        risks=["Một hoặc nhiều công việc có thể không hoàn tất trước deadline của cửa sổ."],
        next_step="Quản lý rà soát thứ tự ưu tiên và bổ sung năng lực nếu không thể giảm workload.",
        fallback=True,
    )


def simulate(
    context: dict[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]], str | None, str]:
    window = context["capacityWindow"]
    gap = int(context.get("capacityGapMinutes") or 0)
    before = {
        "optionType": "KEEP_CURRENT_CAPACITY_PLAN",
        "availableMinutes": window.get("availableMinutes"),
        "remainingAvailableMinutes": window.get("remainingAvailableMinutes"),
        "requiredMinutes": context.get("requiredMinutes"),
        "remainingRequiredMinutes": context.get("remainingRequiredMinutes"),
        "capacityGapMinutes": gap,
        "feasible": False,
        "reasonCodes": ["OPERATIONAL_CAPACITY_SHORTFALL"],
    }
    options: list[dict[str, Any]] = [
        {
            "optionId": "reprioritize-operational-tasks",
            "optionType": "REPRIORITIZE_OPERATIONAL_TASKS",
            "feasible": True,
            "executable": False,
            "rank": 1,
            "reasonCodes": ["CAPACITY_GAP_PRESENT", "MANUAL_SCHEDULING_REQUIRED"],
        }
    ]
    if gap > max(int(window.get("remainingAvailableMinutes") or 0) // 2, 60):
        options.insert(
            0,
            {
                "optionId": "escalate-capacity-shortfall",
                "optionType": "ESCALATE_CAPACITY_SHORTFALL",
                "feasible": True,
                "executable": False,
                "rank": 1,
                "reasonCodes": ["LARGE_CAPACITY_GAP", "MANAGER_REVIEW_REQUIRED"],
            },
        )
        options[1]["rank"] = 2
    snapshot = {
        "ruleCode": "OPERATIONAL_CAPACITY_SHORTFALL",
        "before": before,
        "branchId": context.get("branchId"),
        "capacityWindow": window,
        "requiredMinutes": context.get("requiredMinutes"),
        "remainingRequiredMinutes": context.get("remainingRequiredMinutes"),
        "capacityGapMinutes": gap,
        "workload": context.get("workload", []),
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
            "remainingRequiredMinutes": snapshot.get("remainingRequiredMinutes"),
            "remainingAvailableMinutes": (snapshot.get("capacityWindow") or {}).get(
                "remainingAvailableMinutes"
            ),
        }
    )
    models = _models()
    if not models:
        return fallback
    prompt = [
        SystemMessage(
            content=(
                "You explain a branch operational-capacity recommendation in Vietnamese. "
                "Use only supplied facts. Do not assign staff, change tasks, contact customers, "
                "or create executable actions. Keep the response concise."
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
