"""Bounded agent turn runtime and persisted case lifecycle."""

import json
import logging
from hashlib import sha256
from typing import Any
from uuid import UUID, uuid4

from langgraph.types import Command

from app.agent_tools.cases import (
    CaseBusyError,
    append_turn,
    create_approval,
    create_case,
    create_confirmation,
    create_run,
    decide_approval,
    decide_confirmation,
    get_case,
    get_case_budget_usage,
    get_case_by_id,
    get_case_overview,
    get_pending_approval,
    mark_run,
    pending_actions,
    set_goal,
    set_goal_status,
    transition_case,
)
from app.agent_tools.client import AgentToolClient, ToolInvocationError
from app.agent_tools.execution import execute_frozen_action, observe_live_tool
from app.agent_tools.goal import infer_goal, missing_input_question, resolve_goal
from app.agent_tools.graph import GraphTurn, run_graph_turn
from app.agent_tools.guard import (
    WRITE_TOOL_POLICIES,
    validate_tool_arguments,
    validate_write_matches_goal,
)
from app.agent_tools.models import (
    ActionProposal,
    AgentCaseState,
    AgentGoalSpec,
    AgentRunStatus,
    AgentTerminationReason,
    ToolExecutionStatus,
)
from app.agent_tools.planner import propose_write_action
from app.agent_tools.state import can_transition
from app.agent_tools.workflow import WriteWorkflowState, run_write_workflow
from app.config import get_settings
from app.errors import AppError
from app.knowledge.service import answer_knowledge
from app.models import (
    ActorContext,
    AgentCaseResponse,
    AgentEvidence,
    AgentGoal,
    AgentHandoff,
    PendingApproval,
    PendingConfirmation,
)

logger = logging.getLogger(__name__)
_MODEL_CALL_TOKEN_RESERVE = 4_096


def _run_timeout_seconds() -> float:
    """Cover provider fallback, graph/planner work, and one tool call."""
    settings = get_settings()
    return (
        4 * settings.LLM_TIMEOUT_SECONDS
        + settings.AGENT_MAX_TURN_SECONDS
        + settings.AGENT_TOOL_TIMEOUT_SECONDS
        + 30
    )


def _require_case_branch(case: dict[str, Any] | None, branch_id: UUID) -> dict[str, Any]:
    # A legacy unscoped case must never be silently assigned to the current branch.
    if case is None or case.get("branch_id") != str(branch_id):
        raise AppError(404, "AGENT_CASE_NOT_FOUND", "Agent case not found")
    return case


async def answer_agent_message(
    actor: ActorContext,
    message: str,
    case_id: UUID | None,
    branch_id: UUID,
) -> AgentCaseResponse:
    try:
        actor_id = UUID(actor.user_id)
    except ValueError as error:
        raise AppError(400, "INVALID_ACTOR_CONTEXT", "Trusted actor context is invalid") from error

    if case_id is None:
        case = await create_case(actor_id, tuple(actor.audiences), branch_id)
    else:
        case = _require_case_branch(await get_case(case_id, actor_id), branch_id)

    current = case["state"]
    if current not in {AgentCaseState.NEW, AgentCaseState.WAITING_INPUT}:
        raise AppError(
            409,
            "INVALID_CASE_TRANSITION",
            "This agent case cannot accept another message",
        )
    resolved_case_id = UUID(case["id"])
    run_id = None
    settings = get_settings()
    if "version" in case:
        try:
            run_id = await create_run(resolved_case_id, message, _run_timeout_seconds())
        except CaseBusyError as error:
            raise AppError(
                409, "CASE_BUSY", "An agent request is already running for this case"
            ) from error
    previous_tokens = 0
    previous_steps = 0
    if "version" in case:
        previous_tokens, previous_steps = await get_case_budget_usage(resolved_case_id)

    try:
        previous_goal = None
        if current is AgentCaseState.WAITING_INPUT and isinstance(case.get("goal"), dict):
            previous_goal = AgentGoalSpec.model_validate(case["goal"])
        if previous_tokens >= settings.AGENT_MAX_TOKENS_PER_CASE:
            goal = previous_goal or infer_goal(message)
            goal_tokens = 0
        else:
            resolution = await resolve_goal(
                message,
                previous_goal,
                allow_model=(
                    settings.AGENT_MAX_TOKENS_PER_CASE - previous_tokens
                    >= _MODEL_CALL_TOKEN_RESERVE
                ),
            )
            goal = resolution.goal
            goal_tokens = resolution.token_usage
    except Exception as error:
        logger.exception(
            "Agent goal resolution failed",
            extra={"case_id": str(resolved_case_id), "error_type": type(error).__name__},
        )
        if run_id is not None:
            await mark_run(run_id, AgentRunStatus.FAILED, "GOAL_RESOLUTION_FAILED")
        raise AppError(
            503,
            "GOAL_RESOLUTION_FAILED",
            "Could not safely understand the agent request",
        ) from error

    await transition_case(resolved_case_id, actor_id, AgentCaseState.ANALYZING)
    if "version" in case:
        await set_goal(resolved_case_id, actor_id, goal)

    write_goal = any(
        tool_name in WRITE_TOOL_POLICIES for tool_name in goal.constraints.allowed_tools
    )
    clarification = missing_input_question(goal)
    if "version" in case and write_goal and clarification is None:
        return await _plan_write_confirmation(
            actor=actor,
            case_id=resolved_case_id,
            message=message,
            run_id=run_id,
            goal=goal,
            previous_tokens=previous_tokens,
            previous_steps=previous_steps,
            goal_resolution_tokens=goal_tokens,
        )

    graph_turn = None
    if "version" in case:
        remaining_steps = settings.AGENT_MAX_STEPS_PER_CASE - previous_steps
        remaining_tokens = (
            settings.AGENT_MAX_TOKENS_PER_CASE - previous_tokens - goal_tokens
        )
        if clarification is not None:
            graph_turn = GraphTurn(
                answer=clarification,
                termination_reason=AgentTerminationReason.HUMAN_INPUT_REQUIRED,
                goal=goal,
            )
        elif remaining_steps <= 0 or remaining_tokens <= 0:
            graph_turn = GraphTurn(
                answer="Agent đã đạt giới hạn an toàn của case này.",
                termination_reason=AgentTerminationReason.BUDGET_EXHAUSTED,
            )
        else:
            graph_turn = await run_graph_turn(
                actor,
                resolved_case_id,
                message,
                branch_id,
                remaining_case_steps=remaining_steps,
                remaining_case_tokens=remaining_tokens,
                goal=goal,
            )
        if (
            graph_turn is None
            and goal.required_tools
            and goal.required_tools != ("search_knowledge",)
        ):
            graph_turn = GraphTurn(
                answer="Agent chưa được cấu hình model để thực hiện tra cứu dữ liệu trực tiếp.",
                termination_reason=AgentTerminationReason.DEPENDENCY_FAILURE,
                goal=goal,
            )
    knowledge = None if graph_turn is not None else await answer_knowledge(actor, message, top_k=6)
    graph_termination = graph_turn.termination_reason if graph_turn is not None else None
    rule_termination = (
        graph_termination
        if graph_termination is not AgentTerminationReason.GOAL_ACHIEVED
        else None
    )
    answered = (
        (
            graph_turn is not None
            and graph_termination is AgentTerminationReason.GOAL_ACHIEVED
            and graph_turn.goal_verified
        )
        or knowledge is not None
        and knowledge.outcome == "answered"
    )
    if graph_turn is not None:
        answer = graph_turn.answer
    elif knowledge is not None:
        answer = knowledge.answer
    else:
        answer = "Không thể tạo câu trả lời cho yêu cầu này."
    if rule_termination is AgentTerminationReason.HUMAN_INPUT_REQUIRED:
        state = await transition_case(
            resolved_case_id,
            actor_id,
            AgentCaseState.WAITING_INPUT,
        )
    elif rule_termination is AgentTerminationReason.INSUFFICIENT_DATA:
        state = await transition_case(
            resolved_case_id,
            actor_id,
            AgentCaseState.INSUFFICIENT_DATA,
            rule_termination,
        )
    elif rule_termination is not None:
        state = await transition_case(
            resolved_case_id,
            actor_id,
            AgentCaseState.HANDED_OFF,
            rule_termination,
        )
    elif answered:
        await transition_case(resolved_case_id, actor_id, AgentCaseState.PLAN_READY)
        await transition_case(resolved_case_id, actor_id, AgentCaseState.EXECUTING)
        if "version" in case:
            state = await transition_case(
                resolved_case_id,
                actor_id,
                AgentCaseState.SUCCEEDED,
                AgentTerminationReason.GOAL_ACHIEVED,
            )
        else:
            state = await transition_case(resolved_case_id, actor_id, AgentCaseState.SUCCEEDED)
    else:
        if "version" in case:
            state = await transition_case(
                resolved_case_id,
                actor_id,
                AgentCaseState.INSUFFICIENT_DATA,
                AgentTerminationReason.INSUFFICIENT_DATA,
            )
        else:
            state = await transition_case(
                resolved_case_id, actor_id, AgentCaseState.INSUFFICIENT_DATA
            )
    goal_status = (
        "achieved"
        if answered
        else "waiting_input"
        if state is AgentCaseState.WAITING_INPUT
        else "blocked"
    )
    if "version" in case:
        await set_goal_status(resolved_case_id, actor_id, goal_status)
    evidence = [
        AgentEvidence(
            source_type="knowledge",
            source_id=source.document_id,
            citation=source.citation,
        )
        for source in ([] if knowledge is None else knowledge.sources)
    ]
    if graph_turn is not None:
        evidence.extend(graph_turn.evidence)
    await append_turn(
        resolved_case_id,
        message,
        answer,
        [
            {
                "source_type": item.source_type,
                "source_id": item.source_id,
                "citation": item.citation,
                "observed_at": item.observed_at,
                "payload": {"citation": item.citation},
            }
            for item in evidence
        ],
        "termination" if rule_termination else "agent_answer",
        "STOPPED" if rule_termination else "COMPLETED",
        (
            json.dumps(
                {
                    "reason": rule_termination.value,
                    "toolCalls": graph_turn.tool_calls if graph_turn else 0,
                    "tokens": goal_tokens + (graph_turn.token_usage if graph_turn else 0),
                    "handoff": graph_turn.handoff if graph_turn else None,
                },
                ensure_ascii=False,
            )
            if rule_termination
            else "Goal completion verified"
        ),
    )
    run_status = (
        AgentRunStatus.PAUSED
        if state
        in {
            AgentCaseState.WAITING_INPUT,
            AgentCaseState.WAITING_CONFIRMATION,
            AgentCaseState.WAITING_APPROVAL,
        }
        else AgentRunStatus.COMPLETED
    )
    if run_id is not None:
        await mark_run(
            run_id,
            run_status,
            token_usage=goal_tokens + (graph_turn.token_usage if graph_turn is not None else 0),
            step_count=max(1, graph_turn.tool_calls) if graph_turn is not None else 1,
        )
    final_reason = graph_termination or (
        AgentTerminationReason.GOAL_ACHIEVED
        if answered
        else AgentTerminationReason.INSUFFICIENT_DATA
    )
    return AgentCaseResponse(
        case_id=resolved_case_id,
        state=state.value,
        message=answer,
        evidence=evidence,
        run_status=run_status.value,
        goal=_public_goal(goal.model_copy(update={"status": goal_status}).model_dump()),
        steps_used=(previous_steps + max(1, graph_turn.tool_calls)) if graph_turn else 1,
        tokens_used=previous_tokens
        + goal_tokens
        + (graph_turn.token_usage if graph_turn else 0),
        termination_reason=final_reason.value,
        pending_input=answer if state is AgentCaseState.WAITING_INPUT else None,
        handoff=(
            _public_handoff(
                reason=final_reason.value,
                goal=goal,
                evidence=evidence,
                detail=graph_turn.handoff if graph_turn is not None else None,
            )
            if state is AgentCaseState.HANDED_OFF
            else None
        ),
        completed=state
        not in {
            AgentCaseState.WAITING_INPUT,
            AgentCaseState.WAITING_CONFIRMATION,
            AgentCaseState.WAITING_APPROVAL,
        },
    )


async def _plan_write_confirmation(
    *,
    actor: ActorContext,
    case_id: UUID,
    message: str,
    run_id: UUID | None,
    goal: AgentGoalSpec,
    previous_tokens: int,
    previous_steps: int,
    goal_resolution_tokens: int = 0,
) -> AgentCaseResponse:
    """Freeze an LLM proposal before it can cross the confirmation boundary."""
    actor_id = UUID(actor.user_id)
    settings = get_settings()
    if (
        previous_steps >= settings.AGENT_MAX_STEPS_PER_CASE
        or previous_tokens + goal_resolution_tokens
        > settings.AGENT_MAX_TOKENS_PER_CASE - _MODEL_CALL_TOKEN_RESERVE
    ):
        answer = "Agent đã đạt giới hạn an toàn của case; cần người vận hành tiếp nhận."
        await transition_case(
            case_id,
            actor_id,
            AgentCaseState.HANDED_OFF,
            AgentTerminationReason.BUDGET_EXHAUSTED,
        )
        await append_turn(case_id, message, answer, [], "write_planning", "BLOCKED", answer)
        if run_id is not None:
            await mark_run(
                run_id,
                AgentRunStatus.COMPLETED,
                token_usage=goal_resolution_tokens,
                step_count=1,
            )
        return await read_agent_case(actor, case_id)
    planning_tokens = goal_resolution_tokens
    try:
        planning = await propose_write_action(message, goal)
        proposal = planning.proposal
        planning_tokens += planning.token_usage
    except Exception:
        proposal = None
    if previous_tokens + planning_tokens > settings.AGENT_MAX_TOKENS_PER_CASE:
        answer = "Lập kế hoạch đã chạm token budget; chưa có thao tác ghi nào được thực thi."
        await transition_case(
            case_id,
            actor_id,
            AgentCaseState.HANDED_OFF,
            AgentTerminationReason.BUDGET_EXHAUSTED,
        )
        await append_turn(case_id, message, answer, [], "write_planning", "BLOCKED", answer)
        if run_id is not None:
            await mark_run(
                run_id, AgentRunStatus.COMPLETED, token_usage=planning_tokens, step_count=1
            )
        return await read_agent_case(actor, case_id)
    if proposal is None:
        answer = (
            "Tôi chưa thể tạo thao tác ghi an toàn từ yêu cầu này. "
            "Hãy cung cấp ID, lý do, thời gian/số tiền và phiên bản bản ghi nếu có."
        )
        await transition_case(case_id, actor_id, AgentCaseState.WAITING_INPUT)
        await append_turn(case_id, message, answer, [], "write_planning", "PAUSED", answer)
        if run_id is not None:
            await mark_run(run_id, AgentRunStatus.PAUSED, token_usage=planning_tokens, step_count=1)
        return await read_agent_case(actor, case_id)

    try:
        proposal, planning_evidence = await _enrich_write_proposal(actor, case_id, proposal)
    except (ToolInvocationError, ValueError) as error:
        answer = f"Không thể đọc trạng thái hiện tại để lập hành động an toàn: {error}."
        await transition_case(case_id, actor_id, AgentCaseState.WAITING_INPUT)
        await append_turn(case_id, message, answer, [], "write_context", "PAUSED", answer)
        if run_id is not None:
            await mark_run(run_id, AgentRunStatus.PAUSED, token_usage=planning_tokens, step_count=1)
        return await read_agent_case(actor, case_id)

    policy = WRITE_TOOL_POLICIES.get(proposal.tool_name)
    try:
        if policy is None:
            raise ValueError("tool is not in the write allowlist")
        validate_tool_arguments(proposal.tool_name, proposal.arguments)
        validate_write_matches_goal(proposal.tool_name, proposal.arguments, goal)
        if policy.requires_expected_version and proposal.expected_version is None:
            raise ValueError("expectedVersion must come from a fresh read observation")
    except ValueError as error:
        answer = f"Không thể tạo hành động an toàn: {error}."
        await transition_case(
            case_id,
            actor_id,
            AgentCaseState.HANDED_OFF,
            AgentTerminationReason.INVALID_TOOL_ARGUMENTS,
        )
        await append_turn(case_id, message, answer, [], "write_planning", "BLOCKED", answer)
        if run_id is not None:
            await mark_run(
                run_id, AgentRunStatus.COMPLETED, token_usage=planning_tokens, step_count=1
            )
        return await read_agent_case(actor, case_id)

    frozen_without_hash = {
        "toolName": proposal.tool_name,
        "arguments": proposal.arguments,
        "expectedVersion": proposal.expected_version,
        "readbackTool": policy.readback_tool,
    }
    canonical = json.dumps(
        frozen_without_hash, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    snapshot = {**frozen_without_hash, "payloadHash": sha256(canonical.encode()).hexdigest()}
    await transition_case(case_id, actor_id, AgentCaseState.PLAN_READY)
    current = await get_case(case_id, actor_id)
    if current is None:
        raise AppError(404, "AGENT_CASE_NOT_FOUND", "Agent case not found")
    confirmation = await create_confirmation(
        case_id,
        proposal.summary,
        snapshot,
        # The subsequent PLAN_READY -> WAITING_CONFIRMATION transition is the
        # only version change while this request owns the case claim.
        int(current["version"]) + 1,
        settings.AGENT_CONFIRMATION_TTL_MINUTES,
    )
    await transition_case(case_id, actor_id, AgentCaseState.WAITING_CONFIRMATION)
    answer = f"Tôi đã chuẩn bị thao tác: {proposal.summary}. Hãy xác nhận snapshot này để tiếp tục."
    await append_turn(
        case_id,
        message,
        answer,
        [
            {
                "source_type": item.source_type,
                "source_id": item.source_id,
                "citation": item.citation,
                "observed_at": item.observed_at,
                "payload": {"purpose": "write_planning"},
            }
            for item in planning_evidence
        ],
        "write_confirmation",
        "PAUSED",
        json.dumps({"confirmationId": confirmation["id"], "action": snapshot}, ensure_ascii=False),
    )
    await run_write_workflow(
        case_id=str(case_id),
        value=WriteWorkflowState(
            case_id=str(case_id),
            entry_gate="confirmation",
            owner_actor={"user_id": actor.user_id, "audiences": list(actor.audiences)},
            confirmation_id=str(confirmation["id"]),
            confirmation_snapshot=snapshot,
        ),
        after_confirmation=_apply_confirmation_workflow,
        after_approval=_apply_approval_workflow,
    )
    if run_id is not None:
        await mark_run(
            run_id,
            AgentRunStatus.PAUSED,
            token_usage=planning_tokens,
            step_count=1 + len(planning_evidence),
        )
    return await read_agent_case(actor, case_id)


async def _enrich_write_proposal(
    actor: ActorContext, case_id: UUID, proposal: ActionProposal
) -> tuple[ActionProposal, list[AgentEvidence]]:
    """Replace optimistic-lock data with values from fresh Studio observations."""
    arguments = dict(proposal.arguments)
    expected_version = proposal.expected_version
    read_tool: str | None = None
    read_arguments: dict[str, object] = {}
    if proposal.tool_name in {
        "extend_rental_order",
        "reallocate_rental_item",
        "cancel_rental_order",
    }:
        read_tool = "get_rental_order"
        read_arguments = {"orderId": arguments["orderId"]}
    elif proposal.tool_name in {"approve_stock_transfer", "reject_stock_transfer"}:
        read_tool = "get_stock_transfer"
        read_arguments = {"transferId": arguments["transferId"]}
    elif proposal.tool_name == "update_unit_block":
        read_tool = "get_unit_block"
        read_arguments = {"blockId": arguments["blockId"]}

    if read_tool is None:
        return proposal, []
    result = await observe_live_tool(
        actor, case_id, read_tool, read_arguments, f"plan-{proposal.tool_name}"
    )
    if result.status is not ToolExecutionStatus.OK or not isinstance(result.data, dict):
        raise ValueError(f"{read_tool} did not return the requested record")
    if proposal.tool_name == "update_unit_block":
        updated_at = result.data.get("updatedAt")
        if not isinstance(updated_at, str):
            raise ValueError("unit block read is missing updatedAt")
        arguments["expectedUpdatedAt"] = updated_at
        expected_version = None
    else:
        version = result.record_version or result.data.get("version")
        if not isinstance(version, int) or version < 1:
            raise ValueError("record read is missing a valid version")
        expected_version = version
    evidence = AgentEvidence(
        source_type="live_tool",
        source_id=read_tool,
        observed_at=result.observed_at.isoformat() if result.observed_at else None,
    )
    return proposal.model_copy(
        update={"arguments": arguments, "expected_version": expected_version}
    ), [evidence]


async def read_agent_case(
    actor: ActorContext, case_id: UUID, branch_id: UUID | None = None
) -> AgentCaseResponse:
    try:
        actor_id = UUID(actor.user_id)
    except ValueError as error:
        raise AppError(400, "INVALID_ACTOR_CONTEXT", "Trusted actor context is invalid") from error
    case = await get_case_overview(case_id, actor_id)
    if case is None:
        raise AppError(404, "AGENT_CASE_NOT_FOUND", "Agent case not found")
    if branch_id is not None:
        _require_case_branch(case, branch_id)
    if not case.get("branch_id"):
        raise AppError(404, "AGENT_CASE_NOT_FOUND", "Agent case not found")
    terminal = {
        AgentCaseState.SUCCEEDED,
        AgentCaseState.INSUFFICIENT_DATA,
        AgentCaseState.HANDED_OFF,
        AgentCaseState.FAILED,
        AgentCaseState.CANCELLED,
    }
    pending = await pending_actions(case_id)
    confirmation = pending.get("confirmation")
    approval = pending.get("approval")
    return AgentCaseResponse(
        case_id=case_id,
        state=case["state"].value,
        message=case["message"],
        evidence=[AgentEvidence(**item) for item in case["evidence"]],
        run_status=case.get("last_run_status"),
        goal=_public_goal(case.get("goal")),
        termination_reason=case.get("termination_reason"),
        steps_used=case.get("steps_used", 0),
        tokens_used=case.get("tokens_used", 0),
        pending_input=case["message"] if case["state"] is AgentCaseState.WAITING_INPUT else None,
        pending_confirmation=(
            PendingConfirmation(
                confirmation_id=UUID(confirmation["id"]),
                summary=confirmation["summary"],
                expires_at=confirmation["expires_at"].isoformat(),
            )
            if confirmation is not None
            else None
        ),
        pending_approval=(
            PendingApproval(
                approval_id=UUID(approval["id"]),
                summary=approval["summary"],
                required_permission=approval["required_permission"],
                expires_at=approval["expires_at"].isoformat(),
            )
            if approval is not None
            else None
        ),
        handoff=(
            _public_handoff(
                reason=str(case.get("termination_reason") or "HANDED_OFF"),
                goal=(
                    AgentGoalSpec.model_validate(case["goal"])
                    if isinstance(case.get("goal"), dict)
                    else None
                ),
                evidence=[AgentEvidence(**item) for item in case["evidence"]],
            )
            if case["state"] is AgentCaseState.HANDED_OFF
            else None
        ),
        completed=case["state"] in terminal,
    )


def _public_goal(goal: object) -> AgentGoal | None:
    if not isinstance(goal, dict):
        return None
    try:
        parsed = AgentGoalSpec.model_validate(goal)
    except ValueError:
        return AgentGoal.model_validate(goal)
    return AgentGoal(
        summary=parsed.summary,
        status=parsed.status,
        goal_type=parsed.goal_type.value,
        skill_name=parsed.skill_name,
        constraints=parsed.constraints.model_dump(by_alias=True),
        plan=[step.model_dump(by_alias=True) for step in parsed.plan],
        success_criteria=list(parsed.success_criteria),
    )


def _public_handoff(
    *,
    reason: str,
    goal: AgentGoalSpec | None,
    evidence: list[AgentEvidence],
    detail: dict[str, Any] | None = None,
) -> AgentHandoff:
    """Build a safe handoff summary without exposing model reasoning or secrets."""
    observed_tools = list(
        dict.fromkeys(item.source_id for item in evidence if item.source_type == "live_tool")
    )
    detail_attempted = detail.get("attemptedTools") if isinstance(detail, dict) else None
    detail_successful = detail.get("successfulTools") if isinstance(detail, dict) else None
    detail_failed = detail.get("failedTools") if isinstance(detail, dict) else None
    attempted = (
        [str(item) for item in detail_attempted]
        if isinstance(detail_attempted, list)
        else observed_tools
    )
    successful = (
        [str(item) for item in detail_successful]
        if isinstance(detail_successful, list)
        else observed_tools
    )
    failed = [str(item) for item in detail_failed] if isinstance(detail_failed, list) else []
    next_actions = {
        AgentTerminationReason.BUDGET_EXHAUSTED.value: (
            "Người vận hành xem evidence và tiếp tục case thủ công."
        ),
        AgentTerminationReason.LOOP_DETECTED.value: (
            "Kiểm tra dữ liệu hoặc tool đang lặp trước khi thử lại."
        ),
        AgentTerminationReason.NO_PROGRESS.value: "Bổ sung dữ liệu đầu vào hoặc xử lý thủ công.",
        AgentTerminationReason.TOOL_OUTCOME_UNKNOWN.value: (
            "Đối soát bằng API đọc; không tự retry thao tác ghi."
        ),
        AgentTerminationReason.POLICY_VIOLATION.value: (
            "Người có đúng quyền và branch scope tiếp nhận."
        ),
        AgentTerminationReason.VERIFICATION_FAILED.value: (
            "Đọc lại bản ghi và lập kế hoạch mới từ version hiện tại."
        ),
    }
    supplied_action = detail.get("nextAction") if isinstance(detail, dict) else None
    return AgentHandoff(
        reason=reason,
        goal=goal.summary if goal is not None else None,
        attempted_tools=attempted,
        successful_tools=successful,
        failed_tools=failed,
        evidence_count=len(evidence),
        next_action=(
            str(supplied_action)
            if supplied_action
            else next_actions.get(
                reason, "Người vận hành xem case, evidence và quyết định bước tiếp theo."
            )
        ),
        side_effects=(
            "unknown; reconcile using read-back"
            if reason == AgentTerminationReason.TOOL_OUTCOME_UNKNOWN.value
            else "none verified"
        ),
    )


def _freeze_action(
    tool_name: str,
    arguments: dict[str, object],
    expected_version: int | None,
) -> dict[str, object]:
    policy = WRITE_TOOL_POLICIES[tool_name]
    unsigned = {
        "toolName": tool_name,
        "arguments": arguments,
        "expectedVersion": expected_version,
        "readbackTool": policy.readback_tool,
    }
    canonical = json.dumps(unsigned, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return {**unsigned, "payloadHash": sha256(canonical.encode()).hexdigest()}


async def _approval_scope(
    actor: ActorContext, case_id: UUID, snapshot: dict[str, object]
) -> tuple[UUID, ...]:
    tool_name = snapshot.get("toolName")
    arguments = snapshot.get("arguments")
    if not isinstance(arguments, dict):
        raise AppError(409, "STALE_ACTION_SNAPSHOT", "Frozen action arguments are invalid")
    if tool_name == "create_stock_transfer":
        return (UUID(str(arguments["fromBranchId"])), UUID(str(arguments["toBranchId"])))
    if tool_name in {"approve_stock_transfer", "reject_stock_transfer"}:
        result = await observe_live_tool(
            actor,
            case_id,
            "get_stock_transfer",
            {"transferId": arguments["transferId"]},
            "approval-scope",
        )
        if result.status is not ToolExecutionStatus.OK or not isinstance(result.data, dict):
            raise AppError(409, "APPROVAL_SCOPE_UNKNOWN", "Could not verify transfer branches")
        return (
            UUID(str(result.data["fromBranchId"])),
            UUID(str(result.data["toBranchId"])),
        )
    if tool_name == "create_payment_checkout":
        result = await observe_live_tool(
            actor, case_id, "get_rental_order", {"orderId": arguments["orderId"]}, "approval-scope"
        )
    elif tool_name == "request_refund":
        result = await observe_live_tool(
            actor, case_id, "get_payment", {"paymentId": arguments["paymentId"]}, "approval-scope"
        )
    else:
        return ()
    if result.status is not ToolExecutionStatus.OK or not isinstance(result.data, dict):
        raise AppError(409, "APPROVAL_SCOPE_UNKNOWN", "Could not verify approval branch scope")
    branch_id = result.data.get("pickupBranchId")
    if not isinstance(branch_id, str):
        raise AppError(409, "APPROVAL_SCOPE_UNKNOWN", "Approval branch scope is missing")
    return (UUID(branch_id),)


async def _pause_for_approval(
    *,
    actor: ActorContext,
    case_id: UUID,
    confirmation_id: UUID,
    snapshot: dict[str, object],
    summary: str,
) -> dict[str, Any]:
    policy = WRITE_TOOL_POLICIES[str(snapshot["toolName"])]
    branches = await _approval_scope(actor, case_id, snapshot)
    approval = await create_approval(
        case_id,
        confirmation_id,
        summary,
        policy.required_permission,
        "high",
        snapshot,
        branches,
        get_settings().AGENT_APPROVAL_TTL_HOURS,
    )
    await transition_case(case_id, UUID(actor.user_id), AgentCaseState.WAITING_APPROVAL)
    return approval


def _execution_termination(status: ToolExecutionStatus) -> AgentTerminationReason:
    if status is ToolExecutionStatus.UNKNOWN_OUTCOME:
        return AgentTerminationReason.TOOL_OUTCOME_UNKNOWN
    if status is ToolExecutionStatus.VERSION_CONFLICT:
        return AgentTerminationReason.VERIFICATION_FAILED
    if status in {ToolExecutionStatus.FORBIDDEN, ToolExecutionStatus.APPROVAL_EXPIRED}:
        return AgentTerminationReason.POLICY_VIOLATION
    return AgentTerminationReason.DEPENDENCY_FAILURE


async def _fail_case_if_active(case_id: UUID, owner_id: UUID) -> None:
    case = await get_case(case_id, owner_id)
    if (
        case is not None
        and case["state"] is AgentCaseState.EXECUTING
        and can_transition(case["state"], AgentCaseState.FAILED)
    ):
        await transition_case(
            case_id,
            owner_id,
            AgentCaseState.FAILED,
            AgentTerminationReason.DEPENDENCY_FAILURE,
        )


def _actor_from_workflow(value: object) -> ActorContext:
    if not isinstance(value, dict):
        raise AppError(409, "INVALID_WORKFLOW_STATE", "Workflow actor is missing")
    user_id = value.get("user_id")
    audiences = value.get("audiences", [])
    if not isinstance(user_id, str) or not isinstance(audiences, list):
        raise AppError(409, "INVALID_WORKFLOW_STATE", "Workflow actor is invalid")
    return ActorContext.model_validate({"user_id": user_id, "audiences": audiences})


def _workflow_decision(state: WriteWorkflowState, kind: str) -> dict[str, Any]:
    decision = state.get("decision")
    if not isinstance(decision, dict) or decision.get("kind") != kind:
        raise AppError(409, "INVALID_WORKFLOW_RESUME", f"Invalid {kind} resume payload")
    return decision


async def _append_execution_turn(
    *,
    case_id: UUID,
    prompt: str,
    execution: Any,
    step_type: str,
) -> None:
    evidence = [] if execution.evidence is None else [execution.evidence]
    await append_turn(
        case_id,
        prompt,
        execution.message,
        [
            {
                "source_type": item.source_type,
                "source_id": item.source_id,
                "citation": item.citation,
                "observed_at": item.observed_at,
                "payload": {"verified": True},
            }
            for item in evidence
        ],
        step_type,
        "COMPLETED" if execution.status is ToolExecutionStatus.OK else "STOPPED",
        execution.message,
    )


async def _apply_confirmation_workflow(state: WriteWorkflowState) -> dict[str, Any]:
    """Run only after LangGraph resumes the requester confirmation interrupt."""
    decision = _workflow_decision(state, "confirmation")
    case_id = UUID(state["case_id"])
    confirmation_id = UUID(state["confirmation_id"])
    actor = _actor_from_workflow(state.get("owner_actor"))
    actor_id = UUID(actor.user_id)
    if str(decision.get("decisionId")) != str(confirmation_id):
        raise AppError(409, "INVALID_WORKFLOW_RESUME", "Confirmation ID does not match checkpoint")
    if not decision.get("approve"):
        await transition_case(
            case_id,
            actor_id,
            AgentCaseState.CANCELLED,
            AgentTerminationReason.CONFIRMATION_REJECTED,
        )
        await set_goal_status(case_id, actor_id, "rejected")
        return {"next_gate": "done", "workflow_status": "CANCELLED"}

    snapshot = decision.get("snapshot")
    stored_hash = decision.get("storedHash")
    if not isinstance(snapshot, dict) or not isinstance(stored_hash, str):
        raise AppError(409, "STALE_ACTION_SNAPSHOT", "Frozen action is invalid")
    if snapshot != state.get("confirmation_snapshot"):
        raise AppError(409, "STALE_ACTION_SNAPSHOT", "Checkpoint action does not match decision")
    policy = WRITE_TOOL_POLICIES.get(str(snapshot.get("toolName")))
    if policy is None:
        raise AppError(409, "STALE_ACTION_SNAPSHOT", "Frozen action is not allowlisted")
    await transition_case(case_id, actor_id, AgentCaseState.EXECUTING)
    if policy.requires_approval:
        approval = await _pause_for_approval(
            actor=actor,
            case_id=case_id,
            confirmation_id=confirmation_id,
            snapshot=snapshot,
            summary="Approve confirmed high-risk agent action",
        )
        return {
            "next_gate": "approval",
            "workflow_status": "WAITING_APPROVAL",
            "approval_id": str(approval["id"]),
            "approval_snapshot": snapshot,
        }

    execution = await execute_frozen_action(
        actor=actor,
        case_id=case_id,
        snapshot=snapshot,
        stored_hash=stored_hash,
        confirmation_id=confirmation_id,
    )
    if (
        execution.status is ToolExecutionStatus.OK
        and snapshot.get("toolName") == "create_stock_transfer"
    ):
        data = execution.readback_result.data if execution.readback_result else None
        if not isinstance(data, dict) or not isinstance(data.get("id"), str):
            raise AppError(409, "VERIFICATION_FAILED", "Transfer read-back is incomplete")
        approve_action = _freeze_action(
            "approve_stock_transfer", {"transferId": data["id"]}, int(data["version"])
        )
        reject_action = _freeze_action(
            "reject_stock_transfer",
            {"transferId": data["id"], "reason": "Agent approval rejected"},
            int(data["version"]),
        )
        wrapper = {
            "kind": "transfer_decision",
            "approveAction": approve_action,
            "rejectAction": reject_action,
            "fromBranchId": data["fromBranchId"],
            "toBranchId": data["toBranchId"],
        }
        approval = await create_approval(
            case_id,
            confirmation_id,
            "Approve or reject the requested stock transfer",
            "transfers:manage",
            "high",
            wrapper,
            (UUID(str(data["fromBranchId"])), UUID(str(data["toBranchId"]))),
            get_settings().AGENT_APPROVAL_TTL_HOURS,
        )
        await transition_case(case_id, actor_id, AgentCaseState.WAITING_APPROVAL)
        await _append_execution_turn(
            case_id=case_id,
            prompt="Confirmation approved",
            execution=execution,
            step_type="write_execution",
        )
        return {
            "next_gate": "approval",
            "workflow_status": "WAITING_APPROVAL",
            "approval_id": str(approval["id"]),
            "approval_snapshot": wrapper,
        }

    if execution.status is ToolExecutionStatus.OK:
        await transition_case(
            case_id,
            actor_id,
            AgentCaseState.SUCCEEDED,
            AgentTerminationReason.GOAL_ACHIEVED,
        )
        await set_goal_status(case_id, actor_id, "achieved")
        workflow_status = "SUCCEEDED"
    else:
        await transition_case(
            case_id,
            actor_id,
            AgentCaseState.HANDED_OFF,
            _execution_termination(execution.status),
        )
        workflow_status = "HANDED_OFF"
    await _append_execution_turn(
        case_id=case_id,
        prompt="Confirmation approved",
        execution=execution,
        step_type="write_execution",
    )
    return {"next_gate": "done", "workflow_status": workflow_status}


async def _apply_approval_workflow(state: WriteWorkflowState) -> dict[str, Any]:
    """Run only after LangGraph resumes an authorized approval interrupt."""
    decision = _workflow_decision(state, "approval")
    case_id = UUID(state["case_id"])
    approval_id = UUID(state["approval_id"])
    owner = _actor_from_workflow(state.get("owner_actor"))
    owner_id = UUID(owner.user_id)
    if str(decision.get("decisionId")) != str(approval_id):
        raise AppError(409, "INVALID_WORKFLOW_RESUME", "Approval ID does not match checkpoint")
    approver = _actor_from_workflow(decision.get("actor"))
    approve = bool(decision.get("approve"))
    stored = state.get("approval_snapshot")
    if not isinstance(stored, dict):
        raise AppError(409, "STALE_ACTION_SNAPSHOT", "Approval snapshot is invalid")
    if not approve and stored.get("kind") != "transfer_decision":
        await transition_case(
            case_id,
            owner_id,
            AgentCaseState.CANCELLED,
            AgentTerminationReason.APPROVAL_REJECTED,
        )
        await set_goal_status(case_id, owner_id, "rejected")
        return {"next_gate": "done", "workflow_status": "CANCELLED"}

    if stored.get("kind") == "transfer_decision":
        selected = stored.get("approveAction") if approve else stored.get("rejectAction")
    else:
        selected = stored
    if not isinstance(selected, dict):
        raise AppError(409, "STALE_ACTION_SNAPSHOT", "Approval action is invalid")
    selected_hash = sha256(
        json.dumps(selected, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    await transition_case(case_id, owner_id, AgentCaseState.EXECUTING)
    execution = await execute_frozen_action(
        actor=approver,
        case_id=case_id,
        snapshot=selected,
        stored_hash=selected_hash,
        approval_id=approval_id,
    )
    if execution.status is ToolExecutionStatus.OK:
        await transition_case(
            case_id,
            owner_id,
            AgentCaseState.SUCCEEDED if approve else AgentCaseState.CANCELLED,
            (
                AgentTerminationReason.GOAL_ACHIEVED
                if approve
                else AgentTerminationReason.APPROVAL_REJECTED
            ),
        )
        await set_goal_status(case_id, owner_id, "achieved" if approve else "rejected")
        workflow_status = "SUCCEEDED" if approve else "CANCELLED"
    else:
        await transition_case(
            case_id,
            owner_id,
            AgentCaseState.HANDED_OFF,
            _execution_termination(execution.status),
        )
        workflow_status = "HANDED_OFF"
    await _append_execution_turn(
        case_id=case_id,
        prompt="Approval granted" if approve else "Approval rejected",
        execution=execution,
        step_type="approval_execution",
    )
    return {"next_gate": "done", "workflow_status": workflow_status}


async def decide_case_confirmation(
    actor: ActorContext,
    case_id: UUID,
    confirmation_id: UUID,
    approve: bool,
    reason: str | None = None,
    branch_id: UUID | None = None,
) -> AgentCaseResponse:
    """Record requester confirmation and synchronously continue the frozen action."""
    try:
        actor_id = UUID(actor.user_id)
    except ValueError as error:
        raise AppError(400, "INVALID_ACTOR_CONTEXT", "Trusted actor context is invalid") from error
    case = await get_case(case_id, actor_id)
    if case is None:
        raise AppError(404, "AGENT_CASE_NOT_FOUND", "Agent case not found")
    if branch_id is not None:
        _require_case_branch(case, branch_id)
    if case["state"] != AgentCaseState.WAITING_CONFIRMATION:
        raise AppError(409, "INVALID_CASE_TRANSITION", "Case is not waiting for confirmation")
    try:
        run_id = await create_run(case_id, None, _run_timeout_seconds())
    except CaseBusyError as error:
        raise AppError(
            409, "CASE_BUSY", "An agent request is already running for this case"
        ) from error
    try:
        decided = await decide_confirmation(confirmation_id, case_id, actor_id, approve, reason)
        if not decided:
            raise AppError(409, "CONFIRMATION_NOT_PENDING", "Confirmation is no longer pending")
        snapshot = decided["action_snapshot"]
        if not isinstance(snapshot, dict):
            raise AppError(409, "STALE_ACTION_SNAPSHOT", "Frozen action is invalid")
        workflow_result = await run_write_workflow(
            case_id=str(case_id),
            value=Command(
                resume={
                    "kind": "confirmation",
                    "decisionId": str(confirmation_id),
                    "approve": approve,
                    "reason": reason,
                    "snapshot": snapshot,
                    "storedHash": str(decided["payload_hash"]),
                }
            ),
            bootstrap_state=WriteWorkflowState(
                case_id=str(case_id),
                entry_gate="confirmation",
                owner_actor={"user_id": actor.user_id, "audiences": list(actor.audiences)},
                confirmation_id=str(confirmation_id),
                confirmation_snapshot=snapshot,
            ),
            after_confirmation=_apply_confirmation_workflow,
            after_approval=_apply_approval_workflow,
        )
        workflow_status = workflow_result.get("workflow_status")
        run_status = (
            AgentRunStatus.PAUSED
            if workflow_status == "WAITING_APPROVAL"
            else AgentRunStatus.CANCELLED
            if workflow_status == "CANCELLED"
            else AgentRunStatus.COMPLETED
        )
        await mark_run(run_id, run_status, step_count=2)
        return await read_agent_case(actor, case_id)
    except AppError:
        await _fail_case_if_active(case_id, actor_id)
        await mark_run(run_id, AgentRunStatus.FAILED, error_code="AGENT_CONFIRMATION_FAILED")
        raise
    except Exception:
        await _fail_case_if_active(case_id, actor_id)
        await mark_run(run_id, AgentRunStatus.FAILED, error_code="AGENT_CONFIRMATION_FAILED")
        raise


async def decide_case_approval(
    actor: ActorContext,
    approval_id: UUID,
    approve: bool,
    reason: str | None = None,
    branch_id: UUID | None = None,
) -> AgentCaseResponse:
    """Authorize an approver in Studio, record the decision, then resume synchronously."""
    try:
        approver_id = UUID(actor.user_id)
    except ValueError as error:
        raise AppError(400, "INVALID_ACTOR_CONTEXT", "Trusted actor context is invalid") from error
    pending = await get_pending_approval(approval_id, approver_id, approve)
    if pending is None:
        raise AppError(409, "APPROVAL_NOT_PENDING", "Approval is no longer pending")
    case_id = pending["case_id"]
    case = await get_case_by_id(case_id)
    if case is None:
        raise AppError(404, "AGENT_CASE_NOT_FOUND", "Agent case not found")
    if branch_id is not None:
        _require_case_branch(case, branch_id)
    if not case.get("branch_id"):
        raise AppError(404, "AGENT_CASE_NOT_FOUND", "Agent case not found")
    if case["state"] is not AgentCaseState.WAITING_APPROVAL:
        raise AppError(409, "INVALID_CASE_TRANSITION", "Case is not waiting for approval")
    try:
        run_id = await create_run(case_id, None, _run_timeout_seconds())
    except CaseBusyError as error:
        raise AppError(
            409, "CASE_BUSY", "An agent request is already running for this case"
        ) from error

    settings = get_settings()
    try:
        if not settings.STUDIO_API_URL or not settings.AI_INTERNAL_API_KEY:
            raise AppError(503, "STUDIO_API_NOT_CONFIGURED", "Studio API is not configured")
        client = AgentToolClient(
            base_url=settings.STUDIO_API_URL,
            service_key=settings.AI_INTERNAL_API_KEY,
            timeout_seconds=settings.AGENT_TOOL_TIMEOUT_SECONDS,
        )
        try:
            authorized = await client.authorize_approval(
                actor_id=actor.user_id,
                request_id=str(uuid4()),
                branch_id=str(case["branch_id"]),
                required_permission=str(pending["required_permission"]),
                branch_ids=tuple(str(item) for item in pending["required_branch_ids"]),
            )
        except ToolInvocationError as error:
            raise AppError(503, error.code, error.message) from error
        if not authorized:
            raise AppError(403, "APPROVAL_FORBIDDEN", "Approver lacks permission or branch scope")

        decided = await decide_approval(approval_id, approver_id, approve, reason)
        if decided is None:
            raise AppError(409, "APPROVAL_NOT_PENDING", "Approval is no longer pending")
        owner_id = UUID(str(case["actor_id"]))
        owner_actor = ActorContext(user_id=str(owner_id), audiences=tuple(case["audiences"]))
        stored = decided["action_snapshot"]
        if not isinstance(stored, dict):
            raise AppError(409, "STALE_ACTION_SNAPSHOT", "Approval snapshot is invalid")
        stored_hash = sha256(
            json.dumps(stored, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        if stored_hash != pending["payload_hash"]:
            raise AppError(409, "STALE_ACTION_SNAPSHOT", "Approval payload hash is invalid")
        workflow_result = await run_write_workflow(
            case_id=str(case_id),
            value=Command(
                resume={
                    "kind": "approval",
                    "decisionId": str(approval_id),
                    "approve": approve,
                    "reason": reason,
                    "actor": {
                        "user_id": actor.user_id,
                        "audiences": list(actor.audiences),
                    },
                }
            ),
            bootstrap_state=WriteWorkflowState(
                case_id=str(case_id),
                entry_gate="approval",
                owner_actor={
                    "user_id": owner_actor.user_id,
                    "audiences": list(owner_actor.audiences),
                },
                approval_id=str(approval_id),
                approval_snapshot=stored,
            ),
            after_confirmation=_apply_confirmation_workflow,
            after_approval=_apply_approval_workflow,
        )
        workflow_status = workflow_result.get("workflow_status")
        await mark_run(
            run_id,
            AgentRunStatus.CANCELLED
            if workflow_status == "CANCELLED"
            else AgentRunStatus.COMPLETED,
            step_count=2,
        )
        return await read_agent_case(owner_actor, case_id)
    except AppError:
        await _fail_case_if_active(case_id, UUID(str(case["actor_id"])))
        await mark_run(run_id, AgentRunStatus.FAILED, error_code="AGENT_APPROVAL_FAILED")
        raise
    except Exception:
        await _fail_case_if_active(case_id, UUID(str(case["actor_id"])))
        await mark_run(run_id, AgentRunStatus.FAILED, error_code="AGENT_APPROVAL_FAILED")
        raise


async def cancel_agent_case(
    actor: ActorContext, case_id: UUID, branch_id: UUID | None = None
) -> AgentCaseResponse:
    try:
        actor_id = UUID(actor.user_id)
    except ValueError as error:
        raise AppError(400, "INVALID_ACTOR_CONTEXT", "Trusted actor context is invalid") from error
    case = await get_case(case_id, actor_id)
    if case is None:
        raise AppError(404, "AGENT_CASE_NOT_FOUND", "Agent case not found")
    if branch_id is not None:
        _require_case_branch(case, branch_id)
    if case.get("active_run_id") is not None:
        raise AppError(409, "CASE_BUSY", "An agent request is already running for this case")
    if case["state"] in {
        AgentCaseState.SUCCEEDED,
        AgentCaseState.INSUFFICIENT_DATA,
        AgentCaseState.HANDED_OFF,
        AgentCaseState.FAILED,
        AgentCaseState.CANCELLED,
    }:
        raise AppError(409, "INVALID_CASE_TRANSITION", "Terminal agent cases cannot be cancelled")
    await transition_case(
        case_id, actor_id, AgentCaseState.CANCELLED, AgentTerminationReason.CANCELLED_BY_USER
    )
    return await read_agent_case(actor, case_id)
