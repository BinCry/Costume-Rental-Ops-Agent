import json
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any
from uuid import uuid4

import httpx
import pytest
from pydantic import ValidationError

from app.agent_tools import goal as goal_module
from app.agent_tools import graph as graph_module
from app.agent_tools.client import AgentToolClient, ToolInvocationError
from app.agent_tools.goal import infer_goal, missing_input_question, resolve_goal
from app.agent_tools.graph import _turn_step_limit
from app.agent_tools.guard import (
    ALL_TOOL_POLICIES,
    AgentRuleViolation,
    CompletionVerification,
    ExecutionGuard,
    ToolAuthorization,
    render_grounded_answer,
    validate_write_matches_goal,
    verify_completion,
)
from app.agent_tools.models import (
    AgentCaseState,
    AgentGoalType,
    AgentRunStatus,
    AgentTerminationReason,
    AgentToolExecutionRequest,
    GoalDraft,
    GoalEntities,
    ToolExecutionStatus,
)
from app.agent_tools.runtime import answer_agent_message
from app.agent_tools.skills import (
    SKILLS,
    BusinessSkill,
    SkillStep,
    attach_skill,
    select_skill,
    skill_allows_tool,
    validate_skill_registry,
)
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


def test_write_proposal_must_match_validated_goal_inputs() -> None:
    trusted_order_id = str(uuid4())
    changed_order_id = str(uuid4())
    goal = infer_goal(f"Gia hạn đơn {trusted_order_id} đến 2026-10-20T10:00:00Z")

    with pytest.raises(ValueError, match="orderId differs"):
        validate_write_matches_goal(
            "extend_rental_order",
            {
                "orderId": changed_order_id,
                "newDueAt": "2026-10-20T10:00:00Z",
            },
            goal,
        )

    validate_write_matches_goal(
        "extend_rental_order",
        {
            "orderId": trusted_order_id,
            "newDueAt": "2026-10-20T10:00:00Z",
        },
        goal,
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


def test_completion_verification_requires_consistent_terminal_state() -> None:
    with pytest.raises(ValueError, match="Successful completion"):
        CompletionVerification(True, AgentTerminationReason.GOAL_ACHIEVED)

    with pytest.raises(ValueError, match="requires a termination reason"):
        CompletionVerification(False)


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


def test_unit_block_create_uses_studio_api_contract_fields() -> None:
    unit_id = str(uuid4())
    goal = infer_goal(
        f"Tạo block vệ sinh {unit_id} từ 2026-10-16T08:00:00Z đến 2026-10-16T10:00:00Z"
    )

    assert goal.goal_type is AgentGoalType.UNIT_BLOCK_CHANGE
    assert goal.extracted_inputs["blockAction"] == "create"
    assert goal.extracted_inputs["blockType"] == "CLEANING"
    assert goal.extracted_inputs["blockedFrom"] == "2026-10-16T08:00:00Z"
    assert goal.extracted_inputs["blockedUntil"] == "2026-10-16T10:00:00Z"
    assert "create_unit_block" in goal.required_tools
    assert "reason" in goal.missing_inputs
    assert "plannedStartAt" not in goal.extracted_inputs
    assert "plannedDueAt" not in goal.extracted_inputs


def test_guard_rejects_inverted_unit_block_window() -> None:
    guard = ExecutionGuard(
        max_tool_calls=2,
        remaining_case_steps=2,
        tool_policies=ALL_TOOL_POLICIES,
    )

    with pytest.raises(AgentRuleViolation) as error:
        guard.before_tool(
            "create_unit_block",
            {
                "unitId": str(uuid4()),
                "blockType": "REPAIR",
                "blockedFrom": "2026-10-16T10:00:00Z",
                "blockedUntil": "2026-10-16T08:00:00Z",
                "reason": "Repair",
            },
            authorization=ToolAuthorization(confirmation_id=str(uuid4())),
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


def test_natural_paraphrase_uses_safe_rule_and_requests_missing_write_inputs() -> None:
    goal = infer_goal("Khách muốn giữ thêm hai hôm")

    assert goal.goal_type is AgentGoalType.RENTAL_EXTENSION
    assert goal.resolution_source == "rule"
    assert goal.missing_inputs == ("orderId", "newDueAt")
    assert goal.constraints.requires_confirmation


@pytest.mark.asyncio
async def test_model_goal_draft_is_bounded_by_trusted_skill(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    order_id = uuid4()

    async def fake_classify(*_: object) -> tuple[GoalDraft, int]:
        return (
            GoalDraft(
                goal_type=AgentGoalType.RENTAL_EXTENSION,
                confidence=0.94,
                summary="Gia hạn thời gian thuê",
                entities=GoalEntities(
                    order_id=order_id,
                    new_due_at=datetime(2026, 10, 20, 10, 0, tzinfo=UTC),
                ),
                explicit_write_intent=True,
            ),
            37,
        )

    monkeypatch.setattr(goal_module, "_classify_goal", fake_classify)
    resolution = await resolve_goal(
        f"Khách cần sử dụng đơn {order_id} đến 2026-10-20T10:00:00Z lâu hơn dự kiến"
    )

    assert resolution.token_usage == 37
    assert resolution.goal.goal_type is AgentGoalType.RENTAL_EXTENSION
    assert resolution.goal.resolution_source == "model"
    assert resolution.goal.missing_inputs == ()
    assert resolution.goal.extracted_inputs["orderId"] == str(order_id)
    assert resolution.goal.constraints.allowed_tools == (
        "get_rental_order",
        "check_availability",
        "extend_rental_order",
    )


@pytest.mark.asyncio
async def test_model_cannot_invent_goal_entities(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    invented_order_id = uuid4()

    async def fake_classify(*_: object) -> tuple[GoalDraft, int]:
        return (
            GoalDraft(
                goal_type=AgentGoalType.RENTAL_EXTENSION,
                confidence=0.96,
                summary="Gia hạn đơn",
                entities=GoalEntities(
                    order_id=invented_order_id,
                    new_due_at=datetime(2026, 10, 20, 10, 0, tzinfo=UTC),
                ),
                explicit_write_intent=True,
            ),
            20,
        )

    monkeypatch.setattr(goal_module, "_classify_goal", fake_classify)
    resolution = await resolve_goal("Khách muốn dùng đồ lâu hơn")

    assert resolution.goal.extracted_inputs == {}
    assert resolution.goal.missing_inputs == ("orderId", "newDueAt")


@pytest.mark.asyncio
async def test_ambiguous_follow_up_cannot_clear_write_intent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    order_id = uuid4()
    previous = infer_goal(f"Gia hạn đơn {order_id} đến 2026-10-20T10:00:00Z").model_copy(
        update={"missing_inputs": ("writeIntent",)}
    )

    async def fake_classify(*_: object) -> tuple[GoalDraft, int]:
        return (
            GoalDraft(
                goal_type=AgentGoalType.GENERAL_ASSISTANCE,
                confidence=0.40,
                summary="Không rõ",
            ),
            10,
        )

    monkeypatch.setattr(goal_module, "_classify_goal", fake_classify)
    resolution = await resolve_goal("Tôi không hiểu", previous)

    assert resolution.goal.goal_type is AgentGoalType.RENTAL_EXTENSION
    assert "writeIntent" in resolution.goal.missing_inputs


@pytest.mark.asyncio
async def test_order_id_follow_up_does_not_replace_payment_goal() -> None:
    order_id = uuid4()
    previous = infer_goal("Kiểm tra thanh toán của đơn này")

    resolution = await resolve_goal(f"order {order_id}", previous)

    assert resolution.goal.goal_type is AgentGoalType.PAYMENT_SUMMARY
    assert resolution.goal.extracted_inputs["orderId"] == str(order_id)
    assert resolution.goal.missing_inputs == ()


@pytest.mark.asyncio
async def test_goal_resolver_skips_model_when_budget_reserve_is_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fail_if_called(*_: object) -> tuple[GoalDraft, int]:
        raise AssertionError("classifier must not be called")

    monkeypatch.setattr(goal_module, "_classify_goal", fail_if_called)
    resolution = await resolve_goal("Tôi cần được hỗ trợ", allow_model=False)

    assert resolution.token_usage == 0
    assert resolution.goal.goal_type is AgentGoalType.GENERAL_ASSISTANCE
    assert resolution.goal.resolution_source == "fallback"


@pytest.mark.asyncio
async def test_write_question_requires_explicit_intent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    order_id = uuid4()

    async def no_classification(*_: object) -> tuple[None, int]:
        return None, 0

    monkeypatch.setattr(goal_module, "_classify_goal", no_classification)
    resolution = await resolve_goal(
        f"Can customer extend order {order_id} to 2026-10-20T10:00:00Z?"
    )

    assert resolution.goal.goal_type is AgentGoalType.RENTAL_EXTENSION
    assert resolution.goal.missing_inputs == ("writeIntent",)


@pytest.mark.asyncio
async def test_model_cannot_replace_validated_continuation_target(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_order_id = uuid4()
    unrelated_id = uuid4()
    previous = infer_goal(f"Gia hạn đơn {original_order_id} đến 2026-10-20T10:00:00Z").model_copy(
        update={"missing_inputs": ("writeIntent",)}
    )

    async def fake_classify(*_: object) -> tuple[GoalDraft, int]:
        return (
            GoalDraft(
                goal_type=AgentGoalType.RENTAL_EXTENSION,
                confidence=0.95,
                summary="Bổ sung lý do",
                entities=GoalEntities(order_id=unrelated_id),
            ),
            12,
        )

    monkeypatch.setattr(goal_module, "_classify_goal", fake_classify)
    resolution = await resolve_goal(f"Mã tham chiếu lý do là {unrelated_id}", previous)

    assert resolution.goal.extracted_inputs["orderId"] == str(original_order_id)
    assert "writeIntent" in resolution.goal.missing_inputs


@pytest.mark.asyncio
async def test_model_cannot_reuse_one_uuid_for_multiple_business_roles(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    shared_id = uuid4()

    async def fake_classify(*_: object) -> tuple[GoalDraft, int]:
        return (
            GoalDraft(
                goal_type=AgentGoalType.RENTAL_REALLOCATION,
                confidence=0.95,
                summary="Đổi bộ được cấp",
                entities=GoalEntities(
                    order_id=shared_id,
                    order_item_id=shared_id,
                    unit_id=shared_id,
                ),
                explicit_write_intent=True,
            ),
            15,
        )

    monkeypatch.setattr(goal_module, "_classify_goal", fake_classify)
    resolution = await resolve_goal(f"Hãy đổi bộ cho đơn {shared_id}")

    assert resolution.goal.extracted_inputs == {"orderId": str(shared_id)}
    assert resolution.goal.missing_inputs == ("orderItemId", "unitId")


@pytest.mark.asyncio
async def test_waiting_input_continuation_merges_into_existing_goal() -> None:
    previous = infer_goal("Kiểm tra thanh toán của đơn này")
    order_id = uuid4()

    resolution = await resolve_goal(str(order_id), previous)

    assert resolution.goal.goal_type is AgentGoalType.PAYMENT_SUMMARY
    assert resolution.goal.resolution_source == "continuation"
    assert resolution.goal.extracted_inputs["orderId"] == str(order_id)
    assert resolution.goal.missing_inputs == ()
    assert "Thông tin bổ sung" in resolution.goal.summary


@pytest.mark.asyncio
async def test_waiting_input_continuation_preserves_existing_positional_id() -> None:
    variant_id = uuid4()
    branch_id = uuid4()
    previous = infer_goal(f"Kiểm tra khả dụng mẫu {variant_id}")

    resolution = await resolve_goal(
        f"{branch_id} 2026-10-20T09:00:00+07:00 2026-10-22T18:00:00+07:00",
        previous,
    )

    assert resolution.goal.extracted_inputs["variantId"] == str(variant_id)
    assert resolution.goal.extracted_inputs["pickupBranchId"] == str(branch_id)
    assert resolution.goal.missing_inputs == ()


def test_goal_attaches_read_skill_plan_and_hard_tool_boundary() -> None:
    goal = infer_goal("Quy trình nhận trang phục như thế nào?")

    assert goal.goal_type is AgentGoalType.KNOWLEDGE_ANSWER
    assert goal.skill_name == "policy_answer_with_citations"
    assert goal.constraints.allowed_tools == ("search_knowledge",)
    assert goal.plan[0].tool_name == "search_knowledge"
    assert skill_allows_tool(goal, "search_knowledge")
    assert not skill_allows_tool(goal, "get_rental_order")


def test_skill_registry_is_typed_and_valid() -> None:
    validate_skill_registry()

    assert all(isinstance(step, SkillStep) for skill in SKILLS for step in skill.workflow)


def test_skill_registry_rejects_unknown_tool() -> None:
    invalid = BusinessSkill(
        name="unsafe_skill",
        goal_types=frozenset({AgentGoalType.KNOWLEDGE_ANSWER}),
        allowed_tools=("arbitrary_http",),
        workflow=(SkillStep("Call arbitrary route", "arbitrary_http", "Request completed"),),
    )

    with pytest.raises(ValueError, match="unknown tools"):
        validate_skill_registry((invalid,))


def test_skill_registry_requires_write_gates_from_tool_policy() -> None:
    invalid = BusinessSkill(
        name="unsafe_refund",
        goal_types=frozenset({AgentGoalType.REFUND_REQUEST}),
        allowed_tools=("request_refund",),
        workflow=(SkillStep("Request refund", "request_refund", "Refund is verified"),),
    )

    with pytest.raises(ValueError, match="requires requester confirmation"):
        validate_skill_registry((invalid,))

    partially_guarded = BusinessSkill(
        name="partially_guarded_refund",
        goal_types=frozenset({AgentGoalType.REFUND_REQUEST}),
        allowed_tools=("request_refund",),
        workflow=(SkillStep("Request refund", "request_refund", "Refund is verified"),),
        requires_confirmation=True,
    )

    with pytest.raises(ValueError, match="requires approval"):
        validate_skill_registry((partially_guarded,))


def test_skill_registry_rejects_duplicate_goal_owner() -> None:
    first = BusinessSkill(
        name="first",
        goal_types=frozenset({AgentGoalType.GENERAL_ASSISTANCE}),
        allowed_tools=(),
        workflow=(SkillStep("Clarify", None, "Scope is clear"),),
    )
    second = BusinessSkill(
        name="second",
        goal_types=frozenset({AgentGoalType.GENERAL_ASSISTANCE}),
        allowed_tools=(),
        workflow=(SkillStep("Answer", None, "Answer is grounded"),),
    )

    with pytest.raises(ValueError, match="owned by both"):
        validate_skill_registry((first, second))


def test_skill_registry_rejects_missing_goal_owner() -> None:
    with pytest.raises(ValueError, match="does not cover goals"):
        validate_skill_registry((SKILLS[0],))


def test_attach_skill_rejects_required_tool_outside_boundary() -> None:
    goal = infer_goal("Quy trình nhận trang phục như thế nào?")
    invalid = goal.model_copy(update={"required_tools": ("get_rental_order",)})

    with pytest.raises(ValueError, match="outside the skill boundary"):
        attach_skill(invalid)


def test_turn_step_limit_enforces_skill_budget() -> None:
    goal = infer_goal("Quy trình nhận trang phục như thế nào?")
    constrained = goal.model_copy(
        update={"constraints": goal.constraints.model_copy(update={"max_steps": 2})}
    )

    assert _turn_step_limit(constrained, configured_limit=6) == 2
    assert _turn_step_limit(constrained, configured_limit=1) == 1


@pytest.mark.asyncio
async def test_graph_turn_wires_skill_budget_to_guard_and_recursion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    goal = infer_goal("hello")
    goal = goal.model_copy(
        update={"constraints": goal.constraints.model_copy(update={"max_steps": 2})}
    )
    guard_arguments: dict[str, Any] = {}
    invocation_config: dict[str, Any] = {}

    def capture_guard(**kwargs: Any) -> ExecutionGuard:
        guard_arguments.update(kwargs)
        return ExecutionGuard(**kwargs)

    class FakeCheckpointerContext:
        async def __aenter__(self) -> object:
            return object()

        async def __aexit__(
            self,
            exc_type: object,
            exc: object,
            traceback: object,
        ) -> bool:
            return False

    class FakeAgent:
        async def ainvoke(
            self,
            _input: object,
            *,
            config: dict[str, Any],
        ) -> dict[str, list[SimpleNamespace]]:
            invocation_config.update(config)
            return {"messages": [SimpleNamespace(content="No matching data.")]}

    async def skip_checkpoint_setup(_checkpointer: object) -> None:
        return None

    monkeypatch.setattr(graph_module, "_models", lambda: (object(), None))
    monkeypatch.setattr(graph_module, "ExecutionGuard", capture_guard)
    monkeypatch.setattr(
        graph_module,
        "AsyncPostgresSaver",
        SimpleNamespace(from_conn_string=lambda _url: FakeCheckpointerContext()),
    )
    monkeypatch.setattr(graph_module, "_ensure_checkpoint_tables", skip_checkpoint_setup)
    monkeypatch.setattr(graph_module, "create_agent", lambda **_kwargs: FakeAgent())

    result = await graph_module.run_graph_turn(
        ActorContext(user_id=str(uuid4()), audiences=("customer", "shared")),
        uuid4(),
        "hello",
        goal=goal,
    )

    assert result is not None
    assert guard_arguments["max_tool_calls"] == 2
    assert invocation_config["recursion_limit"] == 6
    assert result.goal_verified
    assert result.termination_reason is AgentTerminationReason.GOAL_ACHIEVED
    assert result.handoff is None


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


def test_knowledge_answer_is_rendered_with_retrieved_citation() -> None:
    goal = infer_goal("What is the rental cancellation policy?")
    guard = ExecutionGuard(max_tool_calls=6, remaining_case_steps=6)
    guard.before_tool("search_knowledge", {"query": goal.summary})
    citation = "Rental policy — Cancellation"
    guard.after_tool(
        observation={"status": "ok"},
        evidence_refs=("rental-policy",),
        data={"results": [{"sourceId": "rental-policy", "citation": citation}]},
    )

    answer = render_grounded_answer(goal, guard.observations, "Cancellation requires notice.")
    verification = verify_completion(
        user_message=goal.summary,
        answer=answer,
        evidence_count=1,
        tool_calls=1,
        goal=goal,
        observations=guard.observations,
    )

    assert citation in answer
    assert verification.achieved


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


@pytest.mark.asyncio
async def test_runtime_treats_explicit_goal_achieved_as_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    case_id = uuid4()
    actor_id = uuid4()
    run_id = uuid4()
    transitions: list[AgentCaseState] = []
    goal = infer_goal("hello")

    async def fake_get_case(*_: object) -> dict[str, object]:
        return {
            "id": str(case_id),
            "state": AgentCaseState.NEW,
            "version": 1,
        }

    async def fake_create_run(*_: object) -> object:
        return run_id

    async def fake_budget(*_: object) -> tuple[int, int]:
        return 0, 0

    async def fake_resolve(*_: object, **__: object) -> object:
        return SimpleNamespace(goal=goal, token_usage=0)

    async def fake_graph_turn(*_: object, **__: object) -> object:
        return graph_module.GraphTurn(
            answer="Xin chÃ o!",
            termination_reason=AgentTerminationReason.GOAL_ACHIEVED,
            goal_verified=True,
            goal=goal,
        )

    async def fake_transition(
        _: object,
        __: object,
        state: AgentCaseState,
        ___: object = None,
    ) -> AgentCaseState:
        transitions.append(state)
        return state

    async def no_op(*_: object, **__: object) -> None:
        return None

    async def fail_knowledge(*_: object, **__: object) -> KnowledgeAnswer:
        raise AssertionError("knowledge fallback must not run after a graph result")

    monkeypatch.setattr("app.agent_tools.runtime.get_case", fake_get_case)
    monkeypatch.setattr("app.agent_tools.runtime.create_run", fake_create_run)
    monkeypatch.setattr("app.agent_tools.runtime.get_case_budget_usage", fake_budget)
    monkeypatch.setattr("app.agent_tools.runtime.resolve_goal", fake_resolve)
    monkeypatch.setattr("app.agent_tools.runtime.run_graph_turn", fake_graph_turn)
    monkeypatch.setattr("app.agent_tools.runtime.transition_case", fake_transition)
    monkeypatch.setattr("app.agent_tools.runtime.set_goal", no_op)
    monkeypatch.setattr("app.agent_tools.runtime.set_goal_status", no_op)
    monkeypatch.setattr("app.agent_tools.runtime.append_turn", no_op)
    monkeypatch.setattr("app.agent_tools.runtime.mark_run", no_op)
    monkeypatch.setattr("app.agent_tools.runtime.answer_knowledge", fail_knowledge)

    result = await answer_agent_message(
        ActorContext(user_id=str(actor_id), audiences=("customer", "shared")),
        "hello",
        case_id,
    )

    assert result.state == AgentCaseState.SUCCEEDED
    assert result.termination_reason == AgentTerminationReason.GOAL_ACHIEVED
    assert AgentCaseState.HANDED_OFF not in transitions


@pytest.mark.asyncio
async def test_goal_resolution_failure_releases_active_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    case_id = uuid4()
    actor_id = uuid4()
    run_id = uuid4()
    marked: list[tuple[object, ...]] = []

    async def fake_get_case(*_: object) -> dict[str, object]:
        return {
            "id": str(case_id),
            "state": AgentCaseState.NEW,
            "version": 1,
        }

    async def fake_create_run(*_: object) -> object:
        return run_id

    async def fake_budget(*_: object) -> tuple[int, int]:
        return 0, 0

    async def fake_resolve(*_: object) -> object:
        raise RuntimeError("provider setup failed")

    async def fake_mark_run(*args: object, **_: object) -> None:
        marked.append(args)

    monkeypatch.setattr("app.agent_tools.runtime.get_case", fake_get_case)
    monkeypatch.setattr("app.agent_tools.runtime.create_run", fake_create_run)
    monkeypatch.setattr("app.agent_tools.runtime.get_case_budget_usage", fake_budget)
    monkeypatch.setattr("app.agent_tools.runtime.resolve_goal", fake_resolve)
    monkeypatch.setattr("app.agent_tools.runtime.mark_run", fake_mark_run)

    with pytest.raises(AppError) as error:
        await answer_agent_message(
            ActorContext(user_id=str(actor_id), audiences=("staff_internal",)),
            "Kiểm tra đơn",
            case_id,
        )

    assert error.value.code == "GOAL_RESOLUTION_FAILED"
    assert marked == [(run_id, AgentRunStatus.FAILED, "GOAL_RESOLUTION_FAILED")]
