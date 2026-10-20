"""Deterministic Phase-3 rental-readiness simulation.

The LLM may explain this result, but it never selects a unit or writes an
action.  Keeping this module free of tool calls makes its behaviour unit-testable
and prevents a narrative model from expanding the operational scope.
"""

from __future__ import annotations

import json
from typing import Any

from pydantic import Field

from app.models import AgentReadinessAnalysisNarrative, ApiModel

SIMULATOR_VERSION = "rental-readiness/v1"
RANKING_POLICY_VERSION = "same-branch/v1"


class _NarrativeDraft(ApiModel):
    summary: str = Field(min_length=1, max_length=1_000)
    rationale: list[str] = Field(default_factory=list, max_length=6)
    risks: list[str] = Field(default_factory=list, max_length=6)
    next_step: str = Field(min_length=1, max_length=500)


def _fallback(
    *, before: dict[str, Any], options: list[dict[str, Any]], recommended_option_id: str | None
) -> AgentReadinessAnalysisNarrative:
    if before.get("optionType") == "KEEP_ORDER_STATUS":
        status = str(before.get("status") or "")
        action = "bắt đầu chuẩn bị đơn" if status == "CONFIRMED" else "hoàn tất chuẩn bị đơn"
        return AgentReadinessAnalysisNarrative(
            summary=f"Đơn sắp đến giờ nhận nhưng vẫn ở trạng thái {status}.",
            rationale=[
                "Tất cả unit đã được phân bổ và đang sẵn sàng tại đúng chi nhánh.",
                "Không phát hiện đơn trước chưa trả, block hoặc điều chuyển đang hoạt động.",
            ],
            risks=["Khách có thể phải chờ nếu quy trình chuẩn bị không hoàn tất trước giờ nhận."],
            next_step=f"Nhân viên cần {action} và xác nhận thủ công trên hệ thống.",
            fallback=True,
        )
    if recommended_option_id is None:
        return AgentReadinessAnalysisNarrative(
            summary=(
                "Không có unit thay thế cùng variant tại chi nhánh nhận "
                "trong thời điểm đã kiểm tra."
            ),
            rationale=["Unit hiện tại không kịp hoàn tất cleaning buffer trước giờ nhận."],
            risks=["Đơn nhận sau có nguy cơ không có trang phục đúng lịch."],
            next_step="Chuyển nhân viên vận hành xử lý ngoài phạm vi đề xuất tự động.",
            fallback=True,
        )
    selected = next(item for item in options if item["optionId"] == recommended_option_id)
    return AgentReadinessAnalysisNarrative(
        summary=f"Đề xuất đổi sang unit {selected['targetUnit']['unitCode']} cùng chi nhánh.",
        rationale=[
            "Unit hiện tại không kịp sẵn sàng trước giờ nhận.",
            "Unit thay thế đã qua kiểm tra availability cho đúng khoảng thuê.",
        ],
        risks=["Cần đọc lại trạng thái và version trước khi tạo confirmation thực thi."],
        next_step="Xem recommendation; Phase 4 sẽ revalidate trước khi xác nhận thay đổi.",
        fallback=True,
    )


def simulate(
    context: dict[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]], str | None, str]:
    primary = context["primaryOrder"]
    rule_code = str(context.get("ruleCode") or "PREVIOUS_RENTAL_NOT_RETURNED")
    if rule_code == "ORDER_PREPARATION_DELAYED":
        option_type = (
            "START_PREPARATION" if primary.get("status") == "CONFIRMED" else "COMPLETE_PREPARATION"
        )
        option_id = option_type.lower().replace("_", "-")
        before = {
            "optionType": "KEEP_ORDER_STATUS",
            "status": primary.get("status"),
            "plannedStartAt": primary.get("plannedStartAt"),
            "feasible": False,
            "reasonCodes": ["ORDER_NOT_READY_FOR_PICKUP"],
        }
        preparation_options: list[dict[str, Any]] = [
            {
                "optionId": option_id,
                "optionType": option_type,
                "feasible": True,
                "executable": False,
                "rank": 1,
                "reasonCodes": ["UNITS_READY", "MANUAL_PREPARATION_REQUIRED"],
            }
        ]
        snapshot = {
            "ruleCode": rule_code,
            "before": before,
            "primaryOrder": primary,
            "affectedOrder": None,
            "allocatedUnits": context.get("allocatedUnits", []),
            "observedAt": context["observedAt"],
        }
        return snapshot, preparation_options, option_id, "READY"
    affected = context.get("affectedOrder")
    earliest_ready_at = context.get("earliestReadyAt")
    reason_codes = context.get("reasonCodes")
    if not isinstance(reason_codes, list) or not all(
        isinstance(code, str) for code in reason_codes
    ):
        reason_codes = (
            ["PREVIOUS_RENTAL_NOT_RETURNED", "CLEANING_BUFFER_NOT_MET"]
            if rule_code == "PREVIOUS_RENTAL_NOT_RETURNED"
            else ["ALLOCATED_UNIT_NOT_READY"]
        )
    before = {
        "optionType": "KEEP_CURRENT_UNIT",
        "unitId": context["currentUnit"]["id"],
        "plannedStartAt": primary["plannedStartAt"],
        "earliestReadyAt": earliest_ready_at,
        "feasible": False,
        "reasonCodes": reason_codes,
    }
    options: list[dict[str, Any]] = []
    units = context.get("replacementUnits")
    if isinstance(units, list):
        for unit in sorted(
            (item for item in units if isinstance(item, dict)),
            key=lambda item: (str(item.get("unitCode", "")), str(item.get("id", ""))),
        ):
            unit_id = unit.get("id")
            unit_code = unit.get("unitCode")
            if not isinstance(unit_id, str) or not isinstance(unit_code, str):
                continue
            option_id = f"reallocate:{unit_id}"
            options.append(
                {
                    "optionId": option_id,
                    "optionType": "REALLOCATE_SAME_BRANCH",
                    "feasible": True,
                    "rank": len(options) + 1,
                    "reasonCodes": ["SAME_VARIANT", "SAME_BRANCH", "AVAILABLE_FOR_WINDOW"],
                    "targetUnit": {
                        "id": unit_id,
                        "unitCode": unit_code,
                        "conditionGrade": unit.get("conditionGrade"),
                    },
                    # Preview only. It lacks a payload hash and is deliberately
                    # not consumable by the write execution workflow.
                    "actionPreview": {
                        "toolName": "reallocate_rental_item",
                        "arguments": {
                            "orderId": primary["id"],
                            "orderItemId": primary["item"]["id"],
                            "unitId": unit_id,
                            "reason": (
                                "Rental readiness recommendation; revalidate before execution"
                            ),
                        },
                        "expectedVersion": primary["version"],
                    },
                }
            )
    recommended_option_id = options[0]["optionId"] if options else None
    outcome = "READY" if recommended_option_id else "NO_FEASIBLE_OPTION"
    snapshot = {
        "ruleCode": rule_code,
        "before": before,
        "primaryOrder": primary,
        "affectedOrder": affected,
        "currentUnit": context["currentUnit"],
        "cleaningBufferMinutes": context.get("cleaningBufferMinutes"),
        "earliestReadyAt": earliest_ready_at,
        "observedAt": context["observedAt"],
    }
    return snapshot, options, recommended_option_id, outcome


async def explain(
    *, snapshot: dict[str, Any], options: list[dict[str, Any]], recommended_option_id: str | None
) -> AgentReadinessAnalysisNarrative:
    # Keep simulation importable in worker/test environments that intentionally
    # do not install model-provider dependencies.
    from langchain_core.messages import HumanMessage, SystemMessage

    from app.agent_tools.planner import _models

    fallback = _fallback(
        before=snapshot["before"], options=options, recommended_option_id=recommended_option_id
    )
    models = _models()
    if not models:
        return fallback
    prompt = [
        SystemMessage(
            content=(
                "You explain a rental-readiness recommendation in Vietnamese. "
                "Use only supplied facts. Do not create options, IDs, actions, costs, "
                "or ranking changes. Keep the response operational and concise."
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
