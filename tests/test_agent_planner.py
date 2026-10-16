from uuid import uuid4

import pytest

from app.agent_tools import goal as goal_module
from app.agent_tools.goal import infer_goal, resolve_goal
from app.agent_tools.planner import propose_write_action


@pytest.mark.asyncio
async def test_cancellation_plans_without_an_llm(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    order_id = uuid4()
    previous = infer_goal(f"Hủy đơn thuê {order_id}")

    async def no_classification(*_: object) -> tuple[None, int]:
        return None, 0

    monkeypatch.setattr(goal_module, "_classify_goal", no_classification)
    resolved = await resolve_goal("Lý do hủy: khách đổi kế hoạch", previous)
    planning = await propose_write_action("Lý do hủy: khách đổi kế hoạch", resolved.goal)

    assert planning.token_usage == 0
    assert planning.proposal is not None
    assert planning.proposal.tool_name == "cancel_rental_order"
    assert planning.proposal.arguments == {
        "orderId": str(order_id),
        "reason": "khách đổi kế hoạch",
    }
    assert planning.proposal.expected_version is None
