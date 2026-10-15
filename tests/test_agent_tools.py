import json
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import httpx
import pytest
from pydantic import ValidationError

from app.agent_tools.client import AgentToolClient, ToolInvocationError
from app.agent_tools.goal import infer_goal, missing_input_question
from app.agent_tools.guard import (
    AgentRuleViolation,
    ExecutionGuard,
    render_grounded_answer,
    verify_completion,
)
from app.agent_tools.models import (
    AgentCaseState,
    AgentGoalType,
    AgentTerminationReason,
    AgentToolExecutionRequest,
    ToolExecutionStatus,
)
from app.agent_tools.runtime import answer_agent_message
from app.agent_tools.skills import select_skill, skill_allows_tool
from app.agent_tools.state import can_transition, is_terminal, require_transition
from app.errors import AppError
from app.models import ActorContext, KnowledgeAnswer


def invocation() -> AgentToolExecutionRequest:
    return AgentToolExecutionRequest(
        case_id=uuid4(),
        tool_call_id=uuid4(),
        tool_name="get_rental_order",
        arguments={"orderId": "order-1"},
        expected_version=7,
        idempotency_key="case-1:call-1",
    )


def test_tool_call_model_rejects_arbitrary_route_shape() -> None:
    with pytest.raises(ValidationError):
        AgentToolExecutionRequest(
            case_id=uuid4(),
            tool_call_id=uuid4(),
            tool_name="../../payments",
            idempotency_key="call-1",
        )


def test_case_transitions_are_explicit_and_terminal_states_cannot_resume() -> None:
    assert can_transition(AgentCaseState.NEW, AgentCaseState.ANALYZING)
    assert not can_transition(AgentCaseState.SUCCEEDED, AgentCaseState.ANALYZING)
    assert is_terminal(AgentCaseState.SUCCEEDED)

    with pytest.raises(AppError) as error:
        require_transition(AgentCaseState.SUCCEEDED, AgentCaseState.ANALYZING)
    assert error.value.code == "INVALID_CASE_TRANSITION"


def test_execution_guard_enforces_case_step_budget() -> None:
    guard = ExecutionGuard(max_tool_calls=6, remaining_case_steps=1)
    order_id = "00000000-0000-4000-8000-000000000001"
    guard.before_tool("get_rental_order", {"orderId": order_id}, evidence_count=0)
    guard.after_tool(evidence_count=1)

    with pytest.raises(AgentRuleViolation) as error:
        guard.before_tool("get_payment_summary", {"orderId": order_id}, evidence_count=1)

    assert error.value.reason is AgentTerminationReason.BUDGET_EXHAUSTED


def test_execution_guard_stops_repeated_call_without_new_evidence() -> None:
    guard = ExecutionGuard(max_tool_calls=6, remaining_case_steps=6)
    arguments = {"orderId": "00000000-0000-4000-8000-000000000001"}
    guard.before_tool("get_rental_order", arguments, evidence_count=0)
    guard.after_tool(evidence_count=0)

    with pytest.raises(AgentRuleViolation) as error:
        guard.before_tool("get_rental_order", arguments, evidence_count=0)

    assert error.value.reason is AgentTerminationReason.LOOP_DETECTED


def test_execution_guard_stops_after_two_calls_without_progress() -> None:
    guard = ExecutionGuard(max_tool_calls=6, remaining_case_steps=6, stall_limit=2)
    order_id = "00000000-0000-4000-8000-000000000001"
    guard.before_tool("get_rental_order", {"orderId": order_id}, evidence_count=0)
    guard.after_tool(evidence_count=0)
    guard.before_tool("get_payment_summary", {"orderId": order_id}, evidence_count=0)

    with pytest.raises(AgentRuleViolation) as error:
        guard.after_tool(evidence_count=0)

    assert error.value.reason is AgentTerminationReason.NO_PROGRESS


def test_execution_guard_detects_non_adjacent_repeat_in_sliding_window() -> None:
    guard = ExecutionGuard(max_tool_calls=6, remaining_case_steps=6)
    order_id = "00000000-0000-4000-8000-000000000001"
    guard.before_tool("get_rental_order", {"orderId": order_id})
    guard.after_tool(observation={"orderId": order_id})
    guard.before_tool("get_payment_summary", {"orderId": order_id})
    guard.after_tool(observation={"paid": 0})

    with pytest.raises(AgentRuleViolation) as error:
        guard.before_tool("get_rental_order", {"orderId": order_id})

    assert error.value.reason is AgentTerminationReason.LOOP_DETECTED


def test_execution_guard_rejects_tool_outside_allowlist() -> None:
    guard = ExecutionGuard(
        max_tool_calls=6,
        remaining_case_steps=6,
        allowed_tools=frozenset({"get_rental_order"}),
    )

    with pytest.raises(AgentRuleViolation) as error:
        guard.before_tool("create_refund", {"amount": 100})

    assert error.value.reason is AgentTerminationReason.POLICY_VIOLATION


def test_completion_requires_evidence_for_operational_answer() -> None:
    verification = verify_completion(
        user_message="Đơn hàng của tôi đang ở trạng thái nào?",
        answer="Đơn đang hoạt động.",
        evidence_count=0,
        tool_calls=0,
    )

    assert not verification.achieved
    assert verification.reason is AgentTerminationReason.INSUFFICIENT_DATA


def test_completion_allows_verified_operational_answer() -> None:
    order_id = "00000000-0000-4000-8000-000000000001"
    guard = ExecutionGuard(max_tool_calls=6, remaining_case_steps=6)
    guard.before_tool("get_rental_order", {"orderId": order_id})
    guard.after_tool(observation={"id": order_id}, evidence_refs=(order_id,))
    verification = verify_completion(
        user_message="Đơn hàng của tôi đang ở trạng thái nào?",
        answer="Đơn đang hoạt động.",
        evidence_count=1,
        tool_calls=1,
        observations=guard.observations,
    )

    assert verification.achieved


def test_guard_rejects_semantically_invalid_availability_window() -> None:
    guard = ExecutionGuard(max_tool_calls=6, remaining_case_steps=6)

    with pytest.raises(AgentRuleViolation) as error:
        guard.before_tool(
            "check_availability",
            {
                "variantId": "00000000-0000-4000-8000-000000000001",
                "pickupBranchId": "00000000-0000-4000-8000-000000000002",
                "plannedStartAt": "2026-10-15T11:00:00+07:00",
                "plannedDueAt": "2026-10-15T10:00:00+07:00",
            },
        )

    assert error.value.reason is AgentTerminationReason.INVALID_TOOL_ARGUMENTS


def test_completion_requires_goal_required_tool_and_matching_record() -> None:
    order_id = "00000000-0000-4000-8000-000000000001"
    goal = infer_goal(f"Kiểm tra đơn hàng {order_id}")
    guard = ExecutionGuard(max_tool_calls=6, remaining_case_steps=6)
    guard.before_tool("get_payment_summary", {"orderId": order_id})
    guard.after_tool(observation={"status": "ok"}, evidence_refs=(order_id,))

    verification = verify_completion(
        user_message=goal.summary,
        answer="Đã tra cứu.",
        evidence_count=1,
        tool_calls=1,
        goal=goal,
        observations=guard.observations,
    )

    assert not verification.achieved
    assert verification.reason is AgentTerminationReason.VERIFICATION_FAILED


def test_completion_accepts_goal_required_tool_and_matching_record() -> None:
    order_id = "00000000-0000-4000-8000-000000000001"
    goal = infer_goal(f"Kiểm tra đơn hàng {order_id}")
    guard = ExecutionGuard(max_tool_calls=6, remaining_case_steps=6)
    guard.before_tool("get_rental_order", {"orderId": order_id})
    order = {"id": order_id, "status": "ACTIVE", "version": 2, "items": []}
    guard.after_tool(
        observation={"status": "ok", "data": order},
        evidence_refs=(order_id,),
        data=order,
        observed_at=datetime.now(UTC),
        permission_decision="allowed",
    )

    verification = verify_completion(
        user_message=goal.summary,
        answer="Đơn đã được tra cứu.",
        evidence_count=1,
        tool_calls=1,
        goal=goal,
        observations=guard.observations,
    )

    assert verification.achieved


def test_goal_preflight_requests_missing_payment_order_id() -> None:
    goal = infer_goal("Kiểm tra thanh toán của đơn này")

    question = missing_input_question(goal)

    assert goal.missing_inputs == ("orderId",)
    assert question is not None
    assert "ID" in question


def test_goal_attaches_read_skill_plan_and_hard_tool_boundary() -> None:
    goal = infer_goal("Quy trình nhận trang phục như thế nào?")

    assert goal.goal_type is AgentGoalType.KNOWLEDGE_ANSWER
    assert goal.skill_name == "policy_answer_with_citations"
    assert goal.constraints.allowed_tools == ("search_knowledge",)
    assert goal.plan[0].tool_name == "search_knowledge"
    assert skill_allows_tool(goal, "search_knowledge")
    assert not skill_allows_tool(goal, "get_rental_order")


def test_goal_distinguishes_transfer_read_from_create_workflow() -> None:
    transfer_id = "00000000-0000-4000-8000-000000000001"
    lookup = infer_goal(f"Kiểm tra phiếu điều chuyển {transfer_id}")
    create = infer_goal("Tạo điều chuyển kho từ chi nhánh A sang chi nhánh B")

    assert lookup.goal_type is AgentGoalType.STOCK_TRANSFER_LOOKUP
    assert lookup.skill_name == "stock_transfer_lookup"
    assert not lookup.constraints.requires_confirmation
    assert create.goal_type is AgentGoalType.STOCK_TRANSFER_CREATE
    assert create.skill_name == "cross_branch_transfer"
    assert create.constraints.requires_confirmation
    assert create.constraints.requires_approval
    assert skill_allows_tool(create, "create_stock_transfer")


def test_read_only_availability_skill_cannot_select_reallocation_write() -> None:
    goal = infer_goal("Kiểm tra mẫu này còn trống trong lịch không")

    assert goal.goal_type is AgentGoalType.AVAILABILITY_CHECK
    assert goal.skill_name == "availability_and_schedule"
    assert not goal.constraints.requires_confirmation
    assert not skill_allows_tool(goal, "reallocate_rental_item")


def test_refund_status_question_is_not_misclassified_as_refund_write() -> None:
    goal = infer_goal("Kiểm tra trạng thái hoàn tiền của đơn này")

    assert goal.goal_type is AgentGoalType.PAYMENT_SUMMARY
    assert not goal.constraints.requires_confirmation


def test_write_goal_has_explicit_confirmation_and_verification_plan() -> None:
    goal = infer_goal(
        "Gia hạn đơn 00000000-0000-4000-8000-000000000001 đến 2026-10-20T17:00:00+07:00"
    )
    skill = select_skill(goal.goal_type)

    assert goal.goal_type is AgentGoalType.RENTAL_EXTENSION
    assert skill is not None
    assert goal.skill_name == "rental_extension"
    assert goal.constraints.requires_confirmation
    assert not goal.constraints.requires_approval
    assert "extend_rental_order" in goal.constraints.allowed_tools
    assert any(step.verification == "New due time is verified" for step in goal.plan)


def test_transfer_decision_message_is_routed_to_existing_approval_endpoint() -> None:
    goal = infer_goal("Duyệt chuyển phiếu 00000000-0000-4000-8000-000000000001")
    question = missing_input_question(goal)

    assert goal.goal_type is AgentGoalType.STOCK_TRANSFER_DECISION
    assert goal.constraints.allowed_tools == ()
    assert question is not None
    assert "endpoint" in question


def test_availability_predicate_accepts_available_false_as_valid_result() -> None:
    variant_id = "00000000-0000-4000-8000-000000000001"
    branch_id = "00000000-0000-4000-8000-000000000002"
    goal = infer_goal(
        "Kiểm tra còn trống "
        f"{variant_id} {branch_id} "
        "2026-10-16T08:00:00+07:00 2026-10-18T17:00:00+07:00"
    )
    guard = ExecutionGuard(max_tool_calls=6, remaining_case_steps=6)
    arguments = {
        "variantId": variant_id,
        "pickupBranchId": branch_id,
        "plannedStartAt": "2026-10-16T08:00:00+07:00",
        "plannedDueAt": "2026-10-18T17:00:00+07:00",
    }
    guard.before_tool("check_availability", arguments)
    data = {"available": False, "units": []}
    guard.after_tool(
        observation={"status": "ok", "data": data},
        evidence_refs=(variant_id, branch_id),
        data=data,
        observed_at=datetime.now(UTC),
        permission_decision="allowed",
    )

    verification = verify_completion(
        user_message=goal.summary,
        answer="Không có bộ trống trong khoảng thời gian yêu cầu.",
        evidence_count=1,
        tool_calls=1,
        goal=goal,
        observations=guard.observations,
    )

    assert verification.achieved


def test_live_observation_must_be_fresh() -> None:
    order_id = "00000000-0000-4000-8000-000000000001"
    goal = infer_goal(f"Kiểm tra đơn hàng {order_id}")
    guard = ExecutionGuard(max_tool_calls=6, remaining_case_steps=6)
    guard.before_tool("get_rental_order", {"orderId": order_id})
    order = {"id": order_id, "status": "ACTIVE", "version": 2, "items": []}
    guard.after_tool(
        observation={"status": "ok", "data": order},
        evidence_refs=(order_id,),
        data=order,
        observed_at=datetime.now(UTC) - timedelta(minutes=10),
    )

    verification = verify_completion(
        user_message=goal.summary,
        answer="Đơn đang hoạt động.",
        evidence_count=1,
        tool_calls=1,
        goal=goal,
        observations=guard.observations,
    )

    assert not verification.achieved
    assert verification.reason is AgentTerminationReason.VERIFICATION_FAILED


def test_polling_timestamp_change_is_not_domain_progress() -> None:
    transfer_id = "00000000-0000-4000-8000-000000000001"
    guard = ExecutionGuard(max_tool_calls=6, remaining_case_steps=6, stall_limit=2)
    arguments = {"transferId": transfer_id}
    data = {"id": transfer_id, "status": "IN_TRANSIT", "version": 3}
    guard.before_tool("get_stock_transfer", arguments)
    guard.after_tool(
        observation={"data": data, "observedAt": "2026-10-15T00:00:00Z"},
        data=data,
    )
    guard.before_tool("get_stock_transfer", arguments)
    guard.after_tool(
        observation={"data": data, "observedAt": "2026-10-15T00:01:00Z"},
        data=data,
    )
    guard.before_tool("get_stock_transfer", arguments)

    with pytest.raises(AgentRuleViolation) as error:
        guard.after_tool(
            observation={"data": data, "observedAt": "2026-10-15T00:02:00Z"},
            data=data,
        )

    assert error.value.reason is AgentTerminationReason.NO_PROGRESS


def test_live_completion_requires_studio_permission_audit() -> None:
    order_id = "00000000-0000-4000-8000-000000000001"
    goal = infer_goal(f"Kiểm tra đơn hàng {order_id}")
    guard = ExecutionGuard(max_tool_calls=6, remaining_case_steps=6)
    guard.before_tool("get_rental_order", {"orderId": order_id})
    order = {"id": order_id, "status": "ACTIVE", "version": 2, "items": []}
    guard.after_tool(
        observation={"status": "ok", "data": order},
        evidence_refs=(order_id,),
        data=order,
        observed_at=datetime.now(UTC),
    )

    verification = verify_completion(
        user_message=goal.summary,
        answer="Đơn đang hoạt động.",
        evidence_count=1,
        tool_calls=1,
        goal=goal,
        observations=guard.observations,
    )

    assert not verification.achieved
    assert verification.reason is AgentTerminationReason.VERIFICATION_FAILED


def test_live_answer_is_rendered_from_authoritative_observation() -> None:
    order_id = "00000000-0000-4000-8000-000000000001"
    goal = infer_goal(f"Kiểm tra đơn hàng {order_id}")
    guard = ExecutionGuard(max_tool_calls=6, remaining_case_steps=6)
    guard.before_tool("get_rental_order", {"orderId": order_id})
    order = {
        "id": order_id,
        "orderCode": "RENT-001",
        "status": "READY_FOR_PICKUP",
        "plannedStartAt": "2026-10-16T08:00:00+07:00",
        "plannedDueAt": "2026-10-18T17:00:00+07:00",
        "version": 4,
        "items": [],
    }
    guard.after_tool(
        observation={"status": "ok", "data": order},
        data=order,
        observed_at=datetime.now(UTC),
        permission_decision="allowed",
    )

    answer = render_grounded_answer(goal, guard.observations, "Sai trạng thái")

    assert "READY_FOR_PICKUP" in answer
    assert "RENT-001" in answer
    assert "Sai trạng thái" not in answer


@pytest.mark.asyncio
async def test_client_sends_only_fixed_internal_endpoint_and_trusted_headers() -> None:
    seen: dict[str, object] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["headers"] = request.headers
        seen["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "status": "ok",
                "data": {"orderId": "order-1"},
                "source": "studio-api",
                "requestId": "request-1",
                "recordVersion": 7,
            },
        )

    client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="http://studio.test"
    )
    tool_client = AgentToolClient(base_url="http://studio.test", service_key="key", client=client)

    result = await tool_client.execute(
        actor_id="staff-1",
        request_id="request-1",
        invocation=invocation(),
    )

    assert result.status is ToolExecutionStatus.OK
    assert seen["url"] == "http://studio.test/api/v1/internal/agent-tools/execute"
    headers = seen["headers"]
    assert isinstance(headers, httpx.Headers)
    assert headers["X-AI-Service-Key"] == "key"
    assert headers["X-Actor-Id"] == "staff-1"
    assert headers["X-Agent-Tools-Contract"] == "agent-tools/v1"
    body = seen["body"]
    assert isinstance(body, dict)
    assert body["toolName"] == "get_rental_order"
    await client.aclose()


@pytest.mark.asyncio
async def test_timeout_is_never_interpreted_as_a_successful_write() -> None:
    async def handler(_: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out")

    client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="http://studio.test"
    )
    tool_client = AgentToolClient(base_url="http://studio.test", service_key="key", client=client)

    with pytest.raises(ToolInvocationError) as error:
        await tool_client.execute(
            actor_id="staff-1",
            request_id="request-1",
            invocation=invocation(),
        )
    assert error.value.code == "TOOL_OUTCOME_UNKNOWN"
    await client.aclose()


@pytest.mark.asyncio
async def test_rag_turn_persists_only_evidence_and_uses_guarded_state_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    case_id = uuid4()
    actor_id = uuid4()
    transitions: list[AgentCaseState] = []
    persisted: dict[str, object] = {}

    async def fake_create_case(_: object, __: object) -> dict[str, object]:
        return {"id": str(case_id), "state": AgentCaseState.NEW}

    async def fake_transition(_: object, __: object, state: AgentCaseState) -> AgentCaseState:
        transitions.append(state)
        return state

    async def fake_answer(_: object, __: str, top_k: int) -> KnowledgeAnswer:
        assert top_k == 6
        return KnowledgeAnswer(
            outcome="answered",
            answer="Có thể tra cứu đơn.",
            sources=[],
            provisional=False,
        )

    async def fake_append_turn(*args: object) -> None:
        persisted["args"] = args

    monkeypatch.setattr("app.agent_tools.runtime.create_case", fake_create_case)
    monkeypatch.setattr("app.agent_tools.runtime.transition_case", fake_transition)
    monkeypatch.setattr("app.agent_tools.runtime.answer_knowledge", fake_answer)
    monkeypatch.setattr("app.agent_tools.runtime.append_turn", fake_append_turn)

    result = await answer_agent_message(
        ActorContext(user_id=str(actor_id), audiences=("customer", "shared")),
        "Tôi muốn hỏi trạng thái đơn.",
        None,
    )

    assert result.case_id == case_id
    assert result.state == AgentCaseState.SUCCEEDED
    assert transitions == [
        AgentCaseState.ANALYZING,
        AgentCaseState.PLAN_READY,
        AgentCaseState.EXECUTING,
        AgentCaseState.SUCCEEDED,
    ]
    assert persisted["args"] is not None
