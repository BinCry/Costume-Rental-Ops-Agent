"""Bounded agent turn runtime and persisted case lifecycle."""

import contextlib
import json
import logging
from datetime import UTC, datetime
from hashlib import sha256
from typing import Any
from uuid import UUID, uuid4

from langgraph.types import Command

from app.agent_tools.capacity import explain as explain_capacity
from app.agent_tools.capacity import simulate as simulate_capacity
from app.agent_tools.cases import (
    AnalysisForbiddenError,
    AnalysisStaleError,
    CaseAlreadyClaimedError,
    CaseBusyError,
    CaseReleaseForbiddenError,
    CaseVersionConflictError,
    FindingResolutionConflictError,
    ReadinessConfirmationError,
    append_turn,
    begin_readiness_analysis,
    claim_case,
    create_approval,
    create_case,
    create_confirmation,
    create_overdue_follow_up_confirmation,
    create_readiness_confirmation,
    create_run,
    decide_approval,
    decide_confirmation,
    decide_overdue_follow_up_confirmation,
    decide_readiness_confirmation,
    finalize_overdue_follow_up_execution,
    finalize_readiness_analysis,
    finalize_readiness_execution,
    get_case,
    get_case_budget_usage,
    get_case_by_id,
    get_case_overview_by_id,
    get_pending_approval,
    list_findings,
    list_operational_cases,
    mark_run,
    pending_actions,
    release_case,
    replan_readiness_execution,
    resolve_finding,
    set_goal,
    set_goal_status,
    transition_case,
    upsert_finding,
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
    OPERATIONAL_CASE_TYPES,
    ActionProposal,
    AgentCaseState,
    AgentGoalSpec,
    AgentRunStatus,
    AgentTerminationReason,
    ToolExecutionStatus,
)
from app.agent_tools.overdue import explain as explain_overdue
from app.agent_tools.overdue import simulate as simulate_overdue
from app.agent_tools.planner import propose_write_action
from app.agent_tools.readiness import explain as explain_readiness
from app.agent_tools.readiness import simulate as simulate_readiness
from app.agent_tools.state import can_transition
from app.agent_tools.workflow import WriteWorkflowState, run_write_workflow
from app.config import get_settings
from app.errors import AppError
from app.knowledge.service import answer_knowledge
from app.models import (
    ActorContext,
    AgentCaseListData,
    AgentCaseResponse,
    AgentEvidence,
    AgentFinding,
    AgentFindingResolveData,
    AgentFindingResolveInput,
    AgentFindingUpsertInput,
    AgentGoal,
    AgentHandoff,
    AgentInternalFinding,
    AgentInternalFindingListData,
    AgentOverdueFollowUpConfirmationInput,
    AgentReadinessAnalysis,
    PendingApproval,
    PendingConfirmation,
)

logger = logging.getLogger(__name__)
_MODEL_CALL_TOKEN_RESERVE = 4_096


def _actor_uuid(actor: ActorContext) -> UUID:
    try:
        return UUID(actor.user_id)
    except ValueError as error:
        raise AppError(400, "INVALID_ACTOR_CONTEXT", "Trusted actor context is invalid") from error


def _branch_allowed(actor: ActorContext, branch_id: str | None, *, manage: bool) -> bool:
    if branch_id is None:
        return False
    if manage:
        return actor.agent_manage_all or UUID(branch_id) in actor.agent_manage_branch_ids
    return (
        actor.agent_read_all
        or actor.agent_manage_all
        or UUID(branch_id) in actor.agent_read_branch_ids
        or UUID(branch_id) in actor.agent_manage_branch_ids
    )


def _case_access_allowed(
    actor: ActorContext, case: dict[str, Any], *, manage: bool = False
) -> bool:
    owner_id = case.get("owner_actor_id") or case.get("actor_id")
    if case.get("case_type", "INTERACTIVE") == "INTERACTIVE":
        return owner_id == actor.user_id
    if manage and owner_id != actor.user_id:
        return False
    return _branch_allowed(actor, case.get("branch_id"), manage=manage)


async def _authorized_case(
    actor: ActorContext, case_id: UUID, *, manage: bool = False
) -> dict[str, Any]:
    # Preserve the original owner-scoped lookup for interactive cases. Besides
    # keeping that security boundary explicit, this also keeps the existing
    # runtime seam stable for callers/tests that provide an owner case lookup.
    case = await get_case(case_id, _actor_uuid(actor))
    if case is None:
        case = await get_case_by_id(case_id)
    if case is None or not _case_access_allowed(actor, case, manage=manage):
        raise AppError(404, "AGENT_CASE_NOT_FOUND", "Agent case not found")
    return case


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
    actor_id = _actor_uuid(actor)

    if case_id is None:
        case = await create_case(actor_id, tuple(actor.audiences), branch_id)
    else:
        case = _require_case_branch(await _authorized_case(actor, case_id, manage=True), branch_id)
    case_actor = actor.model_copy(
        update={"audiences": tuple(case.get("audiences", actor.audiences))}
    )

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
            actor=case_actor,
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
        remaining_tokens = settings.AGENT_MAX_TOKENS_PER_CASE - previous_tokens - goal_tokens
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
                case_actor,
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
    knowledge = (
        None if graph_turn is not None else await answer_knowledge(case_actor, message, top_k=6)
    )
    graph_termination = graph_turn.termination_reason if graph_turn is not None else None
    rule_termination = (
        graph_termination if graph_termination is not AgentTerminationReason.GOAL_ACHIEVED else None
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
        tokens_used=previous_tokens + goal_tokens + (graph_turn.token_usage if graph_turn else 0),
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
    _actor_uuid(actor)
    await _authorized_case(actor, case_id)
    case = await get_case_overview_by_id(case_id)
    if case is None:
        raise AppError(404, "AGENT_CASE_NOT_FOUND", "Agent case not found")
    if branch_id is not None:
        _require_case_branch(case, branch_id)
    if not case.get("branch_id"):
        raise AppError(404, "AGENT_CASE_NOT_FOUND", "Agent case not found")
    return await _case_response(case_id, case)


async def _case_response(case_id: UUID, case: dict[str, Any]) -> AgentCaseResponse:
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
                analysis_id=(
                    UUID(confirmation["analysis_id"]) if confirmation.get("analysis_id") else None
                ),
                option_id=confirmation.get("option_id"),
                action=confirmation.get("action"),
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
        origin=case.get("origin"),
        case_type=case.get("case_type"),
        branch_id=UUID(case["branch_id"]) if case.get("branch_id") else None,
        owner_actor_id=(UUID(case["owner_actor_id"]) if case.get("owner_actor_id") else None),
        claimed_at=case.get("claimed_at"),
        deadline_at=case.get("deadline_at"),
        version=case.get("version"),
        finding=(AgentFinding.model_validate(case["finding"]) if case.get("finding") else None),
        analysis=(
            AgentReadinessAnalysis.model_validate(case["analysis"])
            if case.get("analysis")
            else None
        ),
    )


async def list_agent_cases(
    actor: ActorContext,
    *,
    branch_id: UUID | None,
    state: AgentCaseState | None,
    ownership: str,
    cursor: str | None,
    limit: int,
) -> AgentCaseListData:
    actor_id = _actor_uuid(actor)
    if actor.agent_read_all or actor.agent_manage_all:
        branch_ids = None
    else:
        branch_ids = tuple(
            dict.fromkeys((*actor.agent_read_branch_ids, *actor.agent_manage_branch_ids))
        )
    if branch_id is not None and branch_ids is not None and branch_id not in branch_ids:
        raise AppError(403, "FORBIDDEN", "Agent case branch is outside the actor scope")
    try:
        rows, next_cursor = await list_operational_cases(
            branch_ids, branch_id, state, ownership, actor_id, cursor, limit
        )
    except ValueError as error:
        raise AppError(400, "INVALID_CURSOR", "Agent case cursor is invalid") from error
    return AgentCaseListData(
        items=[await _case_response(UUID(row["id"]), row) for row in rows],
        next_cursor=next_cursor,
    )


async def claim_agent_case(
    actor: ActorContext, case_id: UUID, expected_version: int
) -> AgentCaseResponse:
    actor_id = _actor_uuid(actor)
    case = await get_case_by_id(case_id)
    if case is None or case.get("case_type") not in OPERATIONAL_CASE_TYPES:
        raise AppError(404, "AGENT_CASE_NOT_FOUND", "Agent case not found")
    if not _branch_allowed(actor, case.get("branch_id"), manage=True):
        raise AppError(403, "FORBIDDEN", "Agent case branch is outside the actor scope")
    try:
        await claim_case(case_id, actor_id, expected_version)
    except CaseVersionConflictError as error:
        raise AppError(409, "AGENT_CASE_VERSION_CONFLICT", str(error)) from error
    except CaseAlreadyClaimedError as error:
        raise AppError(409, "AGENT_CASE_ALREADY_CLAIMED", str(error)) from error
    except CaseReleaseForbiddenError as error:
        raise AppError(409, "AGENT_CASE_CLAIM_FORBIDDEN", str(error)) from error
    overview = await get_case_overview_by_id(case_id)
    if overview is None:
        raise AppError(404, "AGENT_CASE_NOT_FOUND", "Agent case not found")
    return await _case_response(case_id, overview)


async def release_agent_case(
    actor: ActorContext, case_id: UUID, expected_version: int
) -> AgentCaseResponse:
    actor_id = _actor_uuid(actor)
    await _authorized_case(actor, case_id, manage=True)
    try:
        await release_case(case_id, actor_id, expected_version)
    except CaseVersionConflictError as error:
        raise AppError(409, "AGENT_CASE_VERSION_CONFLICT", str(error)) from error
    except CaseAlreadyClaimedError as error:
        raise AppError(409, "AGENT_CASE_NOT_OWNER", str(error)) from error
    except CaseReleaseForbiddenError as error:
        raise AppError(409, "AGENT_CASE_RELEASE_FORBIDDEN", str(error)) from error
    overview = await get_case_overview_by_id(case_id)
    if overview is None:
        raise AppError(404, "AGENT_CASE_NOT_FOUND", "Agent case not found")
    return await _case_response(case_id, overview)


def _readiness_context_arguments(finding: dict[str, Any]) -> dict[str, object]:
    rule_code = str(finding.get("rule_code") or "")
    arguments: dict[str, object] = {
        "ruleCode": rule_code,
        "primaryOrderId": str(finding["primary_entity_id"]),
    }
    if finding.get("unit_id") is not None:
        arguments["unitId"] = str(finding["unit_id"])
    if rule_code == "PREVIOUS_RENTAL_NOT_RETURNED":
        arguments["affectedOrderId"] = str(finding["affected_entity_id"])
    return arguments


async def analyze_agent_case(
    actor: ActorContext, case_id: UUID, expected_version: int
) -> AgentCaseResponse:
    """Create a non-executable operational recommendation from a fresh live snapshot."""
    if not get_settings().AGENT_READINESS_ANALYSIS_ENABLED:
        raise AppError(
            503,
            "AGENT_READINESS_ANALYSIS_DISABLED",
            "Rental readiness analysis is disabled",
        )
    actor_id = _actor_uuid(actor)
    case = await _authorized_case(actor, case_id, manage=True)
    if case.get("case_type") not in OPERATIONAL_CASE_TYPES:
        raise AppError(409, "AGENT_ANALYSIS_NOT_SUPPORTED", "Case is not an operational case")
    try:
        started = await begin_readiness_analysis(case_id, actor_id, expected_version)
    except CaseVersionConflictError as error:
        raise AppError(409, "AGENT_CASE_VERSION_CONFLICT", str(error)) from error
    except AnalysisForbiddenError as error:
        message = str(error)
        code = (
            "AGENT_CASE_NOT_CLAIMED"
            if "claimed" in message
            else "AGENT_FINDING_NOT_OPEN"
            if "finding" in message
            else "AGENT_ANALYSIS_NOT_SUPPORTED"
        )
        raise AppError(409, code, str(error)) from error
    except LookupError as error:
        raise AppError(404, "AGENT_CASE_NOT_FOUND", str(error)) from error

    try:
        rule_code = started["rule_code"]
        if rule_code == "RENTAL_RETURN_OVERDUE":
            run_purpose = "rental-return-overdue-analysis"
        elif rule_code == "OPERATIONAL_CAPACITY_SHORTFALL":
            run_purpose = "operational-capacity-analysis"
        else:
            run_purpose = "rental-readiness-analysis"
        run_id = await create_run(case_id, run_purpose, _run_timeout_seconds())
    except CaseBusyError as error:
        raise AppError(409, "AGENT_CASE_BUSY", str(error)) from error
    try:
        overdue_analysis = started["rule_code"] == "RENTAL_RETURN_OVERDUE"
        capacity_analysis = started["rule_code"] == "OPERATIONAL_CAPACITY_SHORTFALL"
        context_arguments: dict[str, object]
        if overdue_analysis:
            context_tool = "get_overdue_rental_context"
            context_arguments = {"orderId": str(started["primary_entity_id"])}
            analysis_purpose = "rental-return-overdue-analysis"
        elif capacity_analysis:
            context_tool = "get_operational_capacity_context"
            context_arguments = {
                "branchId": str(started["primary_entity_id"]),
                "startsAt": started["window_start"].isoformat(),
                "endsAt": started["window_end"].isoformat(),
            }
            analysis_purpose = "operational-capacity-analysis"
        else:
            context_tool = "get_rental_readiness_context"
            context_arguments = _readiness_context_arguments(started)
            analysis_purpose = "rental-readiness-analysis"
        result = await observe_live_tool(
            actor,
            case_id,
            context_tool,
            context_arguments,
            analysis_purpose,
        )
        if result.status is not ToolExecutionStatus.OK or not isinstance(result.data, dict):
            raise ToolInvocationError(
                "TOOL_DEPENDENCY_UNAVAILABLE", "Readiness context is unavailable"
            )
        context = result.data
        observed_at = context.get("observedAt")
        if not isinstance(observed_at, str):
            raise ToolInvocationError(
                "TOOL_PROTOCOL_ERROR", "Readiness context is missing observedAt"
            )
        if context.get("riskStillPresent") is not True:
            # A read-only snapshot can prove the detector's finding obsolete.
            # Release the run before the existing resolve contract takes locks.
            await mark_run(run_id, AgentRunStatus.COMPLETED, step_count=1)
            await resolve_finding(
                {
                    "dedupe_key": started["dedupe_key"],
                    "rule_code": started["rule_code"],
                    "observed_at": datetime.fromisoformat(observed_at.replace("Z", "+00:00")),
                    "resolution_code": "RISK_NO_LONGER_PRESENT",
                    "evidence": {"source": context_tool},
                }
            )
            overview = await get_case_overview_by_id(case_id)
            if overview is None:
                raise AppError(404, "AGENT_CASE_NOT_FOUND", "Agent case not found")
            return await _case_response(case_id, overview)

        if overdue_analysis:
            simulator = simulate_overdue
            explainer = explain_overdue
        elif capacity_analysis:
            simulator = simulate_capacity
            explainer = explain_capacity
        else:
            simulator = simulate_readiness
            explainer = explain_readiness
        snapshot, options, recommended_option_id, outcome = simulator(context)
        narrative = await explainer(
            snapshot=snapshot,
            options=options,
            recommended_option_id=recommended_option_id,
        )
        await finalize_readiness_analysis(
            case_id=case_id,
            actor_id=actor_id,
            case_version_at_start=started["case_version"],
            finding_id=started["finding_id"],
            finding_source_observed_at=started["source_observed_at"],
            snapshot=snapshot,
            options=options,
            recommended_option_id=recommended_option_id,
            outcome=outcome,
            narrative=narrative.model_dump(by_alias=True),
            simulator_version=(
                "rental-return-overdue/v1"
                if overdue_analysis
                else "operational-capacity/v1"
                if capacity_analysis
                else "rental-readiness/v1"
            ),
            ranking_policy_version=(
                "overdue-response/v1"
                if overdue_analysis
                else "capacity-response/v1"
                if capacity_analysis
                else "same-branch/v1"
            ),
        )
        answer = narrative.summary
        await append_turn(
            case_id,
            (
                "Analyze overdue rental return finding"
                if overdue_analysis
                else "Analyze operational capacity finding"
                if capacity_analysis
                else "Analyze rental readiness finding"
            ),
            answer,
            [
                {
                    "source_type": "live_tool",
                    "source_id": context_tool,
                    "citation": None,
                    "observed_at": observed_at,
                    "payload": {"purpose": analysis_purpose.replace("-", "_")},
                }
            ],
            analysis_purpose.replace("-", "_"),
            "COMPLETED",
            answer,
        )
        await mark_run(run_id, AgentRunStatus.COMPLETED, step_count=1)
    except AnalysisStaleError as error:
        await mark_run(run_id, AgentRunStatus.FAILED, "AGENT_ANALYSIS_STALE", step_count=1)
        raise AppError(409, "AGENT_ANALYSIS_STALE", str(error)) from error
    except ToolInvocationError as error:
        await mark_run(run_id, AgentRunStatus.FAILED, error.code, step_count=1)
        raise AppError(503, "AGENT_ANALYSIS_DEPENDENCY_FAILURE", error.message) from error
    except Exception:
        await mark_run(run_id, AgentRunStatus.FAILED, "AGENT_ANALYSIS_FAILED", step_count=1)
        raise
    overview = await get_case_overview_by_id(case_id)
    if overview is None:
        raise AppError(404, "AGENT_CASE_NOT_FOUND", "Agent case not found")
    return await _case_response(case_id, overview)


def _readiness_action_from_context(
    *, case: dict[str, Any], analysis: dict[str, Any], context: dict[str, Any]
) -> tuple[str, dict[str, object], int]:
    option_id = analysis.get("recommended_option_id")
    options = analysis.get("options")
    if not isinstance(option_id, str) or not isinstance(options, list):
        raise AppError(409, "AGENT_RECOMMENDATION_NOT_EXECUTABLE", "No recommendation is available")
    option = next(
        (item for item in options if isinstance(item, dict) and item.get("optionId") == option_id),
        None,
    )
    if not isinstance(option, dict) or option.get("optionType") != "REALLOCATE_SAME_BRANCH":
        raise AppError(
            409, "AGENT_RECOMMENDATION_NOT_EXECUTABLE", "Recommendation is not executable"
        )
    target = option.get("targetUnit")
    preview = option.get("actionPreview")
    primary = context.get("primaryOrder")
    affected = context.get("affectedOrder")
    current = context.get("currentUnit")
    finding = case.get("finding")
    if (
        not isinstance(target, dict)
        or not isinstance(preview, dict)
        or not isinstance(primary, dict)
        or not isinstance(current, dict)
        or not isinstance(finding, dict)
    ):
        raise AppError(409, "AGENT_RECOMMENDATION_STALE", "Readiness context is incomplete")
    rule_code = finding.get("rule_code")
    if context.get("ruleCode") != rule_code:
        raise AppError(409, "AGENT_RECOMMENDATION_STALE", "Readiness rule changed")
    if rule_code == "PREVIOUS_RENTAL_NOT_RETURNED":
        if not isinstance(affected, dict) or affected.get("id") != finding.get(
            "affected_entity_id"
        ):
            raise AppError(409, "AGENT_RECOMMENDATION_STALE", "Affected rental changed")
    elif rule_code == "ALLOCATED_UNIT_NOT_READY":
        if affected is not None or current.get("id") != finding.get("affected_entity_id"):
            raise AppError(409, "AGENT_RECOMMENDATION_STALE", "Affected unit changed")
    else:
        raise AppError(409, "AGENT_RECOMMENDATION_STALE", "Readiness rule is unsupported")
    arguments = preview.get("arguments")
    if not isinstance(arguments, dict):
        raise AppError(409, "AGENT_RECOMMENDATION_STALE", "Recommendation preview is invalid")
    # The recommendation is tied to the exact order/item/current unit that was
    # simulated. A new version must be analyzed again rather than silently
    # reusing the old ranking.
    if (
        primary.get("id") != arguments.get("orderId")
        or primary.get("item", {}).get("id") != arguments.get("orderItemId")
        or primary.get("version") != preview.get("expectedVersion")
        or current.get("id") != finding.get("unit_id")
        or primary.get("pickupBranchId") != case.get("branch_id")
    ):
        raise AppError(409, "AGENT_RECOMMENDATION_STALE", "Recommendation inputs changed")
    target_id = target.get("id")
    replacement_ids = {
        item.get("id")
        for item in context.get("replacementUnits", [])
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    }
    if not isinstance(target_id, str) or target_id not in replacement_ids:
        raise AppError(409, "AGENT_RECOMMENDATION_STALE", "Replacement unit is no longer available")
    version = primary.get("version")
    if not isinstance(version, int) or version < 1:
        raise AppError(409, "AGENT_RECOMMENDATION_STALE", "Primary order version is invalid")
    return (
        option_id,
        {
            "orderId": str(primary["id"]),
            "orderItemId": str(primary["item"]["id"]),
            "unitId": target_id,
            "reason": "Rental readiness recommendation",
        },
        version,
    )


async def prepare_readiness_confirmation(
    actor: ActorContext, case_id: UUID, analysis_id: UUID, expected_version: int
) -> AgentCaseResponse:
    """Revalidate the deterministic recommendation and freeze a write snapshot."""
    settings = get_settings()
    if not settings.AGENT_READINESS_EXECUTION_ENABLED:
        raise AppError(
            503,
            "AGENT_READINESS_EXECUTION_DISABLED",
            "Rental readiness execution is disabled",
        )
    actor_id = _actor_uuid(actor)
    case = await _authorized_case(actor, case_id, manage=True)
    if case.get("case_type") in {"RENTAL_RETURN", "OPERATIONAL_CAPACITY"}:
        raise AppError(
            409,
            "AGENT_RECOMMENDATION_NOT_EXECUTABLE",
            "This operational guidance cannot be prepared for execution",
        )
    if case.get("case_type") != "RENTAL_READINESS":
        raise AppError(409, "AGENT_RECOMMENDATION_NOT_READY", "Case is not a rental readiness case")
    if case["state"] is AgentCaseState.WAITING_CONFIRMATION:
        pending = await pending_actions(case_id)
        confirmation = pending.get("confirmation")
        if (
            confirmation is not None
            and confirmation.get("analysis_id") == str(analysis_id)
            and confirmation.get("prepared_from_case_version") == expected_version
        ):
            overview = await get_case_overview_by_id(case_id)
            if overview is None:
                raise AppError(404, "AGENT_CASE_NOT_FOUND", "Agent case not found")
            return await _case_response(case_id, overview)
    if case["state"] is not AgentCaseState.PLAN_READY:
        raise AppError(409, "AGENT_RECOMMENDATION_NOT_READY", "Case is not ready for confirmation")
    if int(case.get("version") or 0) != expected_version:
        raise AppError(409, "AGENT_CASE_VERSION_CONFLICT", "Agent case version is stale")
    overview = await get_case_overview_by_id(case_id)
    if overview is None or not isinstance(overview.get("analysis"), dict):
        raise AppError(409, "AGENT_RECOMMENDATION_NOT_READY", "Active analysis is missing")
    analysis = overview["analysis"]
    if str(analysis.get("analysis_id")) != str(analysis_id):
        raise AppError(
            409, "AGENT_RECOMMENDATION_NOT_READY", "Analysis is not active for this case"
        )
    finding = overview.get("finding")
    if not isinstance(finding, dict) or finding.get("status") != "OPEN":
        raise AppError(409, "AGENT_FINDING_NOT_OPEN", "Agent finding is not open")
    try:
        run_id = await create_run(case_id, "rental-readiness-confirmation", _run_timeout_seconds())
    except CaseBusyError as error:
        raise AppError(409, "AGENT_CASE_BUSY", str(error)) from error
    try:
        context_result = await observe_live_tool(
            actor,
            case_id,
            "get_rental_readiness_context",
            _readiness_context_arguments(finding),
            "rental-readiness-confirmation",
        )
        if context_result.status is not ToolExecutionStatus.OK or not isinstance(
            context_result.data, dict
        ):
            raise ToolInvocationError(
                "TOOL_DEPENDENCY_UNAVAILABLE", "Readiness context is unavailable"
            )
        context = context_result.data
        observed_at = context.get("observedAt")
        if not isinstance(observed_at, str):
            raise ToolInvocationError(
                "TOOL_PROTOCOL_ERROR", "Readiness context is missing observedAt"
            )
        if context.get("riskStillPresent") is not True:
            await mark_run(run_id, AgentRunStatus.COMPLETED, step_count=1)
            await resolve_finding(
                {
                    "dedupe_key": finding["dedupe_key"],
                    "rule_code": finding["rule_code"],
                    "observed_at": datetime.fromisoformat(observed_at.replace("Z", "+00:00")),
                    "resolution_code": "RISK_NO_LONGER_PRESENT",
                    "evidence": {"source": "get_rental_readiness_context"},
                }
            )
            resolved = await get_case_overview_by_id(case_id)
            if resolved is None:
                raise AppError(404, "AGENT_CASE_NOT_FOUND", "Agent case not found")
            return await _case_response(case_id, resolved)
        option_id, arguments, order_version = _readiness_action_from_context(
            case=overview, analysis=analysis, context=context
        )
        frozen = _freeze_action("reallocate_rental_item", arguments, order_version)
        frozen["recommendation"] = {
            "analysisId": str(analysis_id),
            "optionId": option_id,
            "findingId": finding["finding_id"],
            "findingSourceObservedAt": analysis["source_observed_at"],
        }
        unsigned = {key: value for key, value in frozen.items() if key != "payloadHash"}
        frozen["payloadHash"] = sha256(
            json.dumps(unsigned, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        confirmation = await create_readiness_confirmation(
            case_id=case_id,
            actor_id=actor_id,
            analysis_id=analysis_id,
            option_id=option_id,
            expected_version=expected_version,
            summary="Xác nhận đổi unit theo phương án sẵn sàng thuê đã đề xuất",
            action_snapshot=frozen,
            ttl_minutes=settings.AGENT_CONFIRMATION_TTL_MINUTES,
        )
        await append_turn(
            case_id,
            "Prepare rental readiness confirmation",
            confirmation["summary"],
            [
                {
                    "source_type": "live_tool",
                    "source_id": "get_rental_readiness_context",
                    "citation": None,
                    "observed_at": observed_at,
                    "payload": {"purpose": "rental_readiness_confirmation"},
                }
            ],
            "rental_readiness_confirmation",
            "PAUSED",
            confirmation["summary"],
        )
        await mark_run(run_id, AgentRunStatus.PAUSED, step_count=1)
    except AppError as error:
        if error.code == "AGENT_RECOMMENDATION_STALE":
            with contextlib.suppress(CaseVersionConflictError, AnalysisForbiddenError):
                await begin_readiness_analysis(case_id, actor_id, expected_version)
        await mark_run(run_id, AgentRunStatus.FAILED, error.code, step_count=1)
        raise
    except CaseVersionConflictError as error:
        await mark_run(run_id, AgentRunStatus.FAILED, "AGENT_CASE_VERSION_CONFLICT", step_count=1)
        raise AppError(409, "AGENT_CASE_VERSION_CONFLICT", str(error)) from error
    except ReadinessConfirmationError as error:
        await mark_run(
            run_id, AgentRunStatus.FAILED, "AGENT_RECOMMENDATION_NOT_READY", step_count=1
        )
        raise AppError(409, "AGENT_RECOMMENDATION_NOT_READY", str(error)) from error
    except ToolInvocationError as error:
        await mark_run(run_id, AgentRunStatus.FAILED, error.code, step_count=1)
        raise AppError(
            503, "AGENT_READINESS_EXECUTION_DEPENDENCY_FAILURE", error.message
        ) from error
    except Exception:
        await mark_run(
            run_id, AgentRunStatus.FAILED, "AGENT_CONFIRMATION_PREPARE_FAILED", step_count=1
        )
        raise
    refreshed = await get_case_overview_by_id(case_id)
    if refreshed is None:
        raise AppError(404, "AGENT_CASE_NOT_FOUND", "Agent case not found")
    return await _case_response(case_id, refreshed)


async def prepare_overdue_follow_up_confirmation(
    actor: ActorContext,
    case_id: UUID,
    body: AgentOverdueFollowUpConfirmationInput,
) -> AgentCaseResponse:
    """Freeze one structured, PII-free CRM follow-up record after live revalidation."""
    settings = get_settings()
    if not settings.AGENT_CRM_WRITE_ENABLED:
        raise AppError(
            503,
            "AGENT_CRM_WRITE_DISABLED",
            "CRM write execution is disabled",
        )
    actor_id = _actor_uuid(actor)
    case = await _authorized_case(actor, case_id, manage=True)
    if case.get("case_type") != "RENTAL_RETURN":
        raise AppError(409, "AGENT_OVERDUE_FOLLOW_UP_NOT_SUPPORTED", "Case is not overdue-return")
    option_signature = sha256(
        json.dumps(
            body.model_dump(mode="json", exclude={"analysis_id", "expected_version"}),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()[:24]
    option_id = f"record-overdue-follow-up:{option_signature}"
    if case["state"] is AgentCaseState.WAITING_CONFIRMATION:
        pending = await pending_actions(case_id)
        confirmation = pending.get("confirmation")
        if (
            confirmation is not None
            and confirmation.get("analysis_id") == str(body.analysis_id)
            and confirmation.get("option_id") == option_id
            and confirmation.get("prepared_from_case_version") == body.expected_version
        ):
            overview = await get_case_overview_by_id(case_id)
            if overview is None:
                raise AppError(404, "AGENT_CASE_NOT_FOUND", "Agent case not found")
            return await _case_response(case_id, overview)
    if case["state"] is not AgentCaseState.PLAN_READY:
        raise AppError(409, "AGENT_RECOMMENDATION_NOT_READY", "Case is not ready for confirmation")
    if int(case.get("version") or 0) != body.expected_version:
        raise AppError(409, "AGENT_CASE_VERSION_CONFLICT", "Agent case version is stale")
    overview = await get_case_overview_by_id(case_id)
    if overview is None or not isinstance(overview.get("analysis"), dict):
        raise AppError(409, "AGENT_RECOMMENDATION_NOT_READY", "Active analysis is missing")
    analysis = overview["analysis"]
    if str(analysis.get("analysis_id")) != str(body.analysis_id):
        raise AppError(409, "AGENT_RECOMMENDATION_NOT_READY", "Analysis is not active")
    finding = overview.get("finding")
    if (
        not isinstance(finding, dict)
        or finding.get("status") != "OPEN"
        or finding.get("rule_code") != "RENTAL_RETURN_OVERDUE"
    ):
        raise AppError(409, "AGENT_FINDING_NOT_OPEN", "Overdue-return finding is not open")
    try:
        run_id = await create_run(case_id, "overdue-follow-up-confirmation", _run_timeout_seconds())
    except CaseBusyError as error:
        raise AppError(409, "AGENT_CASE_BUSY", str(error)) from error
    try:
        context_result = await observe_live_tool(
            actor,
            case_id,
            "get_overdue_rental_context",
            {"orderId": str(finding["primary_entity_id"])},
            "overdue-follow-up-confirmation",
        )
        if context_result.status is not ToolExecutionStatus.OK or not isinstance(
            context_result.data, dict
        ):
            raise ToolInvocationError(
                "TOOL_DEPENDENCY_UNAVAILABLE", "Overdue context is unavailable"
            )
        context = context_result.data
        observed_at = context.get("observedAt")
        if not isinstance(observed_at, str):
            raise ToolInvocationError(
                "TOOL_PROTOCOL_ERROR", "Overdue context is missing observedAt"
            )
        if context.get("riskStillPresent") is not True:
            await mark_run(run_id, AgentRunStatus.COMPLETED, step_count=1)
            await resolve_finding(
                {
                    "dedupe_key": finding["dedupe_key"],
                    "rule_code": finding["rule_code"],
                    "observed_at": datetime.fromisoformat(observed_at.replace("Z", "+00:00")),
                    "resolution_code": "RISK_NO_LONGER_PRESENT",
                    "evidence": {"source": "get_overdue_rental_context"},
                }
            )
            resolved = await get_case_overview_by_id(case_id)
            if resolved is None:
                raise AppError(404, "AGENT_CASE_NOT_FOUND", "Agent case not found")
            return await _case_response(case_id, resolved)
        primary = context.get("primaryOrder")
        if (
            context.get("ruleCode") != "RENTAL_RETURN_OVERDUE"
            or not isinstance(primary, dict)
            or primary.get("id") != finding.get("primary_entity_id")
            or primary.get("pickupBranchId") != overview.get("branch_id")
        ):
            raise AppError(409, "AGENT_RECOMMENDATION_STALE", "Overdue context changed")
        arguments: dict[str, object] = {
            "orderId": str(primary["id"]),
            "channel": body.channel,
            "outcome": body.outcome,
            "occurredAt": body.occurred_at.isoformat(),
        }
        if body.promised_return_at is not None:
            arguments["promisedReturnAt"] = body.promised_return_at.isoformat()
        if body.next_follow_up_at is not None:
            arguments["nextFollowUpAt"] = body.next_follow_up_at.isoformat()
        frozen = _freeze_action("record_overdue_follow_up", arguments, None)
        frozen["recommendation"] = {
            "analysisId": str(body.analysis_id),
            "findingId": finding["finding_id"],
            "findingSourceObservedAt": analysis["source_observed_at"],
        }
        unsigned = {key: value for key, value in frozen.items() if key != "payloadHash"}
        frozen["payloadHash"] = sha256(
            json.dumps(unsigned, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        summary = f"Record overdue follow-up outcome: {body.outcome} via {body.channel}"
        confirmation = await create_overdue_follow_up_confirmation(
            case_id=case_id,
            actor_id=actor_id,
            analysis_id=body.analysis_id,
            option_id=option_id,
            expected_version=body.expected_version,
            summary=summary,
            action_snapshot=frozen,
            ttl_minutes=settings.AGENT_CONFIRMATION_TTL_MINUTES,
        )
        await append_turn(
            case_id,
            "Prepare overdue follow-up confirmation",
            confirmation["summary"],
            [
                {
                    "source_type": "live_tool",
                    "source_id": "get_overdue_rental_context",
                    "citation": None,
                    "observed_at": observed_at,
                    "payload": {"purpose": "overdue_follow_up_confirmation"},
                }
            ],
            "overdue_follow_up_confirmation",
            "PAUSED",
            confirmation["summary"],
        )
        await mark_run(run_id, AgentRunStatus.PAUSED, step_count=1)
    except AppError as error:
        await mark_run(run_id, AgentRunStatus.FAILED, error.code, step_count=1)
        raise
    except CaseVersionConflictError as error:
        await mark_run(run_id, AgentRunStatus.FAILED, "AGENT_CASE_VERSION_CONFLICT", step_count=1)
        raise AppError(409, "AGENT_CASE_VERSION_CONFLICT", str(error)) from error
    except ReadinessConfirmationError as error:
        await mark_run(
            run_id, AgentRunStatus.FAILED, "AGENT_RECOMMENDATION_NOT_READY", step_count=1
        )
        raise AppError(409, "AGENT_RECOMMENDATION_NOT_READY", str(error)) from error
    except ToolInvocationError as error:
        await mark_run(run_id, AgentRunStatus.FAILED, error.code, step_count=1)
        raise AppError(
            503, "AGENT_READINESS_EXECUTION_DEPENDENCY_FAILURE", error.message
        ) from error
    except Exception:
        await mark_run(
            run_id, AgentRunStatus.FAILED, "AGENT_CONFIRMATION_PREPARE_FAILED", step_count=1
        )
        raise
    refreshed = await get_case_overview_by_id(case_id)
    if refreshed is None:
        raise AppError(404, "AGENT_CASE_NOT_FOUND", "Agent case not found")
    return await _case_response(case_id, refreshed)


async def upsert_agent_finding(body: AgentFindingUpsertInput) -> AgentCaseResponse:
    if body.window_start >= body.window_end:
        raise AppError(400, "INVALID_FINDING_WINDOW", "Finding window must be increasing")
    case_id = await upsert_finding(body.model_dump())
    overview = await get_case_overview_by_id(case_id)
    if overview is None:
        raise AppError(500, "AGENT_CASE_PERSISTENCE_ERROR", "Agent case could not be read")
    return await _case_response(case_id, overview)


async def list_agent_findings(
    *, rule_code: str, status: str, cursor: str | None, limit: int
) -> AgentInternalFindingListData:
    try:
        rows, next_cursor = await list_findings(rule_code, status, cursor, limit)
    except ValueError as error:
        raise AppError(400, "INVALID_CURSOR", "Agent finding cursor is invalid") from error
    return AgentInternalFindingListData(
        items=[AgentInternalFinding.model_validate(row) for row in rows],
        next_cursor=next_cursor,
    )


async def resolve_agent_finding(body: AgentFindingResolveInput) -> AgentFindingResolveData:
    try:
        result = await resolve_finding(body.model_dump())
    except LookupError as error:
        raise AppError(404, "AGENT_FINDING_NOT_FOUND", str(error)) from error
    except FindingResolutionConflictError as error:
        raise AppError(409, "AGENT_FINDING_RESOLUTION_CONFLICT", str(error)) from error
    return AgentFindingResolveData.model_validate(result)


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


async def _decide_readiness_confirmation_runtime(
    *,
    actor: ActorContext,
    case_id: UUID,
    confirmation_id: UUID,
    approve: bool,
    reason: str | None,
) -> AgentCaseResponse:
    actor_id = _actor_uuid(actor)
    decided = await decide_readiness_confirmation(
        case_id=case_id,
        confirmation_id=confirmation_id,
        actor_id=actor_id,
        approve=approve,
        reason=reason,
    )
    if not approve:
        overview = await get_case_overview_by_id(case_id)
        if overview is None:
            raise AppError(404, "AGENT_CASE_NOT_FOUND", "Agent case not found")
        return await _case_response(case_id, overview)
    if decided["idempotent"] and decided["state"] in {
        AgentCaseState.SUCCEEDED.value,
        AgentCaseState.MONITORING.value,
    }:
        overview = await get_case_overview_by_id(case_id)
        if overview is None:
            raise AppError(404, "AGENT_CASE_NOT_FOUND", "Agent case not found")
        return await _case_response(case_id, overview)
    try:
        run_id = await create_run(case_id, "rental-readiness-execution", _run_timeout_seconds())
    except CaseBusyError as error:
        raise AppError(409, "AGENT_CASE_BUSY", str(error)) from error
    snapshot = decided["action_snapshot"]
    if not isinstance(snapshot, dict):
        await mark_run(run_id, AgentRunStatus.FAILED, "STALE_ACTION_SNAPSHOT", step_count=1)
        raise AppError(409, "STALE_ACTION_SNAPSHOT", "Frozen action is invalid")
    try:
        execution = await execute_frozen_action(
            actor=actor,
            case_id=case_id,
            snapshot=snapshot,
            stored_hash=str(decided["payload_hash"]),
            confirmation_id=confirmation_id,
        )
        if execution.status is ToolExecutionStatus.OK:
            observed_at = (
                execution.readback_result.observed_at
                if execution.readback_result is not None and execution.readback_result.observed_at
                else datetime.now(UTC)
            )
            await finalize_readiness_execution(
                case_id=case_id,
                actor_id=actor_id,
                confirmation_id=confirmation_id,
                observed_at=observed_at,
                evidence={
                    "toolName": snapshot.get("toolName"),
                    "readbackSource": "get_rental_order",
                },
            )
            await _append_execution_turn(
                case_id=case_id,
                prompt="Readiness recommendation confirmed",
                execution=execution,
                step_type="rental_readiness_execution",
            )
            await mark_run(run_id, AgentRunStatus.COMPLETED, step_count=2)
        elif execution.status is ToolExecutionStatus.VERSION_CONFLICT:
            await replan_readiness_execution(case_id, actor_id)
            await _append_execution_turn(
                case_id=case_id,
                prompt="Readiness recommendation conflicted",
                execution=execution,
                step_type="rental_readiness_execution",
            )
            await mark_run(
                run_id, AgentRunStatus.COMPLETED, "AGENT_RECOMMENDATION_STALE", step_count=2
            )
            raise AppError(
                409,
                "AGENT_RECOMMENDATION_STALE",
                "Live rental data changed; analyze the case again",
            )
        elif execution.status is ToolExecutionStatus.UNKNOWN_OUTCOME:
            await transition_case(case_id, actor_id, AgentCaseState.MONITORING)
            await _append_execution_turn(
                case_id=case_id,
                prompt="Readiness write outcome is unknown",
                execution=execution,
                step_type="rental_readiness_execution",
            )
            await mark_run(run_id, AgentRunStatus.COMPLETED, "TOOL_OUTCOME_UNKNOWN", step_count=2)
        else:
            await replan_readiness_execution(case_id, actor_id)
            await _append_execution_turn(
                case_id=case_id,
                prompt="Readiness write could not be completed",
                execution=execution,
                step_type="rental_readiness_execution",
            )
            await mark_run(run_id, AgentRunStatus.COMPLETED, execution.status.value, step_count=2)
    except AppError:
        raise
    except Exception:
        await mark_run(
            run_id, AgentRunStatus.FAILED, "AGENT_READINESS_EXECUTION_FAILED", step_count=2
        )
        raise
    overview = await get_case_overview_by_id(case_id)
    if overview is None:
        raise AppError(404, "AGENT_CASE_NOT_FOUND", "Agent case not found")
    return await _case_response(case_id, overview)


async def _decide_overdue_follow_up_confirmation_runtime(
    *,
    actor: ActorContext,
    case_id: UUID,
    confirmation_id: UUID,
    approve: bool,
    reason: str | None,
) -> AgentCaseResponse:
    actor_id = _actor_uuid(actor)
    decided = await decide_overdue_follow_up_confirmation(
        case_id=case_id,
        confirmation_id=confirmation_id,
        actor_id=actor_id,
        approve=approve,
        reason=reason,
    )
    if not approve:
        overview = await get_case_overview_by_id(case_id)
        if overview is None:
            raise AppError(404, "AGENT_CASE_NOT_FOUND", "Agent case not found")
        return await _case_response(case_id, overview)
    if decided["idempotent"] and decided["state"] == AgentCaseState.MONITORING.value:
        overview = await get_case_overview_by_id(case_id)
        if overview is None:
            raise AppError(404, "AGENT_CASE_NOT_FOUND", "Agent case not found")
        return await _case_response(case_id, overview)
    try:
        run_id = await create_run(case_id, "overdue-follow-up-execution", _run_timeout_seconds())
    except CaseBusyError as error:
        raise AppError(409, "AGENT_CASE_BUSY", str(error)) from error
    snapshot = decided["action_snapshot"]
    if not isinstance(snapshot, dict) or snapshot.get("toolName") != "record_overdue_follow_up":
        await mark_run(run_id, AgentRunStatus.FAILED, "STALE_ACTION_SNAPSHOT", step_count=1)
        raise AppError(409, "STALE_ACTION_SNAPSHOT", "Frozen overdue follow-up action is invalid")
    try:
        execution = await execute_frozen_action(
            actor=actor,
            case_id=case_id,
            snapshot=snapshot,
            stored_hash=str(decided["payload_hash"]),
            confirmation_id=confirmation_id,
        )
        if execution.status is ToolExecutionStatus.OK:
            await finalize_overdue_follow_up_execution(
                case_id=case_id,
                actor_id=actor_id,
                confirmation_id=confirmation_id,
            )
            await _append_execution_turn(
                case_id=case_id,
                prompt="Overdue follow-up record confirmed",
                execution=execution,
                step_type="overdue_follow_up_execution",
            )
            await mark_run(run_id, AgentRunStatus.COMPLETED, step_count=2)
        elif execution.status is ToolExecutionStatus.UNKNOWN_OUTCOME:
            await transition_case(case_id, actor_id, AgentCaseState.MONITORING)
            await _append_execution_turn(
                case_id=case_id,
                prompt="Overdue follow-up write outcome is unknown",
                execution=execution,
                step_type="overdue_follow_up_execution",
            )
            await mark_run(run_id, AgentRunStatus.COMPLETED, "TOOL_OUTCOME_UNKNOWN", step_count=2)
        else:
            await replan_readiness_execution(case_id, actor_id)
            await _append_execution_turn(
                case_id=case_id,
                prompt="Overdue follow-up could not be recorded",
                execution=execution,
                step_type="overdue_follow_up_execution",
            )
            await mark_run(run_id, AgentRunStatus.COMPLETED, execution.status.value, step_count=2)
    except AppError:
        raise
    except Exception:
        await mark_run(
            run_id, AgentRunStatus.FAILED, "AGENT_OVERDUE_FOLLOW_UP_FAILED", step_count=2
        )
        raise
    overview = await get_case_overview_by_id(case_id)
    if overview is None:
        raise AppError(404, "AGENT_CASE_NOT_FOUND", "Agent case not found")
    return await _case_response(case_id, overview)


async def decide_case_confirmation(
    actor: ActorContext,
    case_id: UUID,
    confirmation_id: UUID,
    approve: bool,
    reason: str | None = None,
    branch_id: UUID | None = None,
) -> AgentCaseResponse:
    """Record requester confirmation and synchronously continue the frozen action."""
    actor_id = _actor_uuid(actor)
    case = await _authorized_case(actor, case_id, manage=True)
    if branch_id is not None:
        _require_case_branch(case, branch_id)
    if case.get("case_type") == "RENTAL_RETURN":
        try:
            return await _decide_overdue_follow_up_confirmation_runtime(
                actor=actor,
                case_id=case_id,
                confirmation_id=confirmation_id,
                approve=approve,
                reason=reason,
            )
        except ReadinessConfirmationError as error:
            raise AppError(409, "CONFIRMATION_NOT_PENDING", str(error)) from error
    if case.get("case_type") == "RENTAL_READINESS":
        try:
            return await _decide_readiness_confirmation_runtime(
                actor=actor,
                case_id=case_id,
                confirmation_id=confirmation_id,
                approve=approve,
                reason=reason,
            )
        except ReadinessConfirmationError as error:
            raise AppError(409, "CONFIRMATION_NOT_PENDING", str(error)) from error
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
    if case.get("case_type") in OPERATIONAL_CASE_TYPES and not _case_access_allowed(
        actor, case, manage=True
    ):
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
        overview = await get_case_overview_by_id(case_id)
        if overview is None:
            raise AppError(404, "AGENT_CASE_NOT_FOUND", "Agent case not found")
        return await _case_response(case_id, overview)
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
    actor_id = _actor_uuid(actor)
    case = await _authorized_case(actor, case_id, manage=True)
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
