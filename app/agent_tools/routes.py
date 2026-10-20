"""Internal API called only by Studio after it authenticates the user."""

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query

from app.agent_tools.models import AgentCaseState
from app.agent_tools.runtime import (
    analyze_agent_case,
    answer_agent_message,
    cancel_agent_case,
    claim_agent_case,
    decide_case_approval,
    decide_case_confirmation,
    list_agent_cases,
    list_agent_findings,
    prepare_overdue_follow_up_confirmation,
    prepare_readiness_confirmation,
    read_agent_case,
    release_agent_case,
    resolve_agent_finding,
    upsert_agent_finding,
)
from app.auth import require_actor, require_internal_service
from app.errors import AppError
from app.models import (
    ActorContext,
    AgentCaseListData,
    AgentCaseResponse,
    AgentCaseVersionInput,
    AgentDecisionInput,
    AgentFindingResolveData,
    AgentFindingResolveInput,
    AgentFindingUpsertInput,
    AgentInternalFindingListData,
    AgentMessageData,
    AgentMessageInput,
    AgentOverdueFollowUpConfirmationInput,
    AgentReadinessConfirmationInput,
    ErrorResponse,
    SuccessResponse,
)

router = APIRouter(dependencies=[Depends(require_internal_service)])
CaseBranch = Annotated[UUID, Header(alias="X-Case-Branch-Id")]

ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    400: {"model": ErrorResponse, "description": "Invalid request"},
    401: {"model": ErrorResponse, "description": "Authentication failed"},
    403: {"model": ErrorResponse, "description": "Access denied"},
    404: {"model": ErrorResponse, "description": "Case not found"},
    409: {"model": ErrorResponse, "description": "Case state conflict"},
    504: {"model": ErrorResponse, "description": "Dependency timeout"},
    503: {"model": ErrorResponse, "description": "Dependency unavailable"},
}


@router.post(
    "/messages",
    response_model=SuccessResponse[AgentMessageData],
    responses=ERROR_RESPONSES,
)
async def message(
    body: AgentMessageInput,
    actor: Annotated[ActorContext, Depends(require_actor)],
    case_branch_id: CaseBranch,
) -> SuccessResponse[AgentMessageData]:
    if body.branch_id != case_branch_id:
        raise AppError(403, "AGENT_BRANCH_MISMATCH", "Selected branch does not match the request")
    result = await answer_agent_message(actor, body.message, body.case_id, case_branch_id)
    return SuccessResponse(
        success=True,
        data=AgentMessageData(result=result),
        message="Agent message completed",
    )


@router.get(
    "/cases",
    response_model=SuccessResponse[AgentCaseListData],
    responses=ERROR_RESPONSES,
)
async def list_case_queue(
    actor: Annotated[ActorContext, Depends(require_actor)],
    branch_id: Annotated[UUID | None, Query(alias="branchId")] = None,
    state: AgentCaseState | None = None,
    ownership: Annotated[str, Query(pattern="^(unassigned|mine|all)$")] = "all",
    cursor: str | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 30,
) -> SuccessResponse[AgentCaseListData]:
    result = await list_agent_cases(
        actor,
        branch_id=branch_id,
        state=state,
        ownership=ownership,
        cursor=cursor,
        limit=limit,
    )
    return SuccessResponse(success=True, data=result, message="Agent case queue retrieved")


@router.get(
    "/cases/{case_id}",
    response_model=SuccessResponse[AgentCaseResponse],
    responses=ERROR_RESPONSES,
)
async def get_case_state(
    case_id: UUID,
    actor: Annotated[ActorContext, Depends(require_actor)],
    case_branch_id: CaseBranch,
) -> SuccessResponse[AgentCaseResponse]:
    result = await read_agent_case(actor, case_id, case_branch_id)
    return SuccessResponse(success=True, data=result, message="Agent case retrieved")


@router.post(
    "/cases/{case_id}/claim",
    response_model=SuccessResponse[AgentCaseResponse],
    responses=ERROR_RESPONSES,
)
async def claim_case_action(
    case_id: UUID,
    body: AgentCaseVersionInput,
    actor: Annotated[ActorContext, Depends(require_actor)],
) -> SuccessResponse[AgentCaseResponse]:
    result = await claim_agent_case(actor, case_id, body.expected_version)
    return SuccessResponse(success=True, data=result, message="Agent case claimed")


@router.post(
    "/cases/{case_id}/release",
    response_model=SuccessResponse[AgentCaseResponse],
    responses=ERROR_RESPONSES,
)
async def release_case_action(
    case_id: UUID,
    body: AgentCaseVersionInput,
    actor: Annotated[ActorContext, Depends(require_actor)],
) -> SuccessResponse[AgentCaseResponse]:
    result = await release_agent_case(actor, case_id, body.expected_version)
    return SuccessResponse(success=True, data=result, message="Agent case released")


@router.post(
    "/cases/{case_id}/analyze",
    response_model=SuccessResponse[AgentCaseResponse],
    responses=ERROR_RESPONSES,
)
async def analyze_case_action(
    case_id: UUID,
    body: AgentCaseVersionInput,
    actor: Annotated[ActorContext, Depends(require_actor)],
) -> SuccessResponse[AgentCaseResponse]:
    result = await analyze_agent_case(actor, case_id, body.expected_version)
    return SuccessResponse(success=True, data=result, message="Agent case analysis completed")


@router.post(
    "/cases/{case_id}/confirmations",
    response_model=SuccessResponse[AgentCaseResponse],
    responses=ERROR_RESPONSES,
)
async def prepare_readiness_confirmation_action(
    case_id: UUID,
    body: AgentReadinessConfirmationInput,
    actor: Annotated[ActorContext, Depends(require_actor)],
) -> SuccessResponse[AgentCaseResponse]:
    result = await prepare_readiness_confirmation(
        actor, case_id, body.analysis_id, body.expected_version
    )
    return SuccessResponse(success=True, data=result, message="Agent confirmation prepared")


@router.post(
    "/cases/{case_id}/overdue-follow-ups/confirmations",
    response_model=SuccessResponse[AgentCaseResponse],
    responses=ERROR_RESPONSES,
)
async def prepare_overdue_follow_up_confirmation_action(
    case_id: UUID,
    body: AgentOverdueFollowUpConfirmationInput,
    actor: Annotated[ActorContext, Depends(require_actor)],
) -> SuccessResponse[AgentCaseResponse]:
    result = await prepare_overdue_follow_up_confirmation(actor, case_id, body)
    return SuccessResponse(
        success=True,
        data=result,
        message="Overdue follow-up confirmation prepared",
    )


@router.post(
    "/internal/findings/upsert",
    response_model=SuccessResponse[AgentCaseResponse],
    responses=ERROR_RESPONSES,
)
async def upsert_finding_action(
    body: AgentFindingUpsertInput,
) -> SuccessResponse[AgentCaseResponse]:
    result = await upsert_agent_finding(body)
    return SuccessResponse(success=True, data=result, message="Agent finding upserted")


@router.get(
    "/internal/findings",
    response_model=SuccessResponse[AgentInternalFindingListData],
    responses=ERROR_RESPONSES,
)
async def list_findings_action(
    rule_code: Annotated[
        str,
        Query(
            alias="ruleCode",
            pattern=(
                "^(PREVIOUS_RENTAL_NOT_RETURNED|ALLOCATED_UNIT_NOT_READY|"
                "ORDER_PREPARATION_DELAYED|RENTAL_RETURN_OVERDUE|"
                "OPERATIONAL_CAPACITY_SHORTFALL|UNIT_SCHEDULE_CONFLICT)$"
            ),
        ),
    ],
    status: Annotated[str, Query(pattern="^OPEN$")] = "OPEN",
    cursor: str | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 100,
) -> SuccessResponse[AgentInternalFindingListData]:
    result = await list_agent_findings(
        rule_code=rule_code,
        status=status,
        cursor=cursor,
        limit=limit,
    )
    return SuccessResponse(success=True, data=result, message="Agent findings retrieved")


@router.post(
    "/internal/findings/resolve",
    response_model=SuccessResponse[AgentFindingResolveData],
    responses=ERROR_RESPONSES,
)
async def resolve_finding_action(
    body: AgentFindingResolveInput,
) -> SuccessResponse[AgentFindingResolveData]:
    result = await resolve_agent_finding(body)
    return SuccessResponse(success=True, data=result, message="Agent finding resolved")


@router.post(
    "/cases/{case_id}/confirmations/{confirmation_id}/confirm",
    response_model=SuccessResponse[AgentCaseResponse],
    responses=ERROR_RESPONSES,
)
async def confirm_case_action(
    case_id: UUID,
    confirmation_id: UUID,
    actor: Annotated[ActorContext, Depends(require_actor)],
    case_branch_id: CaseBranch,
    body: AgentDecisionInput | None = None,
) -> SuccessResponse[AgentCaseResponse]:
    result = await decide_case_confirmation(
        actor, case_id, confirmation_id, True, body.reason if body else None, case_branch_id
    )
    return SuccessResponse(success=True, data=result, message="Agent confirmation recorded")


@router.post(
    "/cases/{case_id}/confirmations/{confirmation_id}/reject",
    response_model=SuccessResponse[AgentCaseResponse],
    responses=ERROR_RESPONSES,
)
async def reject_case_action(
    case_id: UUID,
    confirmation_id: UUID,
    actor: Annotated[ActorContext, Depends(require_actor)],
    case_branch_id: CaseBranch,
    body: AgentDecisionInput | None = None,
) -> SuccessResponse[AgentCaseResponse]:
    result = await decide_case_confirmation(
        actor, case_id, confirmation_id, False, body.reason if body else None, case_branch_id
    )
    return SuccessResponse(success=True, data=result, message="Agent confirmation rejected")


@router.post(
    "/approvals/{approval_id}/approve",
    response_model=SuccessResponse[AgentCaseResponse],
    responses=ERROR_RESPONSES,
)
async def approve_case_action(
    approval_id: UUID,
    actor: Annotated[ActorContext, Depends(require_actor)],
    case_branch_id: CaseBranch,
    body: AgentDecisionInput | None = None,
) -> SuccessResponse[AgentCaseResponse]:
    result = await decide_case_approval(
        actor, approval_id, True, body.reason if body else None, case_branch_id
    )
    return SuccessResponse(success=True, data=result, message="Agent approval recorded")


@router.post(
    "/approvals/{approval_id}/reject",
    response_model=SuccessResponse[AgentCaseResponse],
    responses=ERROR_RESPONSES,
)
async def reject_approval_action(
    approval_id: UUID,
    actor: Annotated[ActorContext, Depends(require_actor)],
    case_branch_id: CaseBranch,
    body: AgentDecisionInput | None = None,
) -> SuccessResponse[AgentCaseResponse]:
    result = await decide_case_approval(
        actor, approval_id, False, body.reason if body else None, case_branch_id
    )
    return SuccessResponse(success=True, data=result, message="Agent approval rejected")


@router.post(
    "/cases/{case_id}/cancel",
    response_model=SuccessResponse[AgentCaseResponse],
    responses=ERROR_RESPONSES,
)
async def cancel_case_action(
    case_id: UUID,
    actor: Annotated[ActorContext, Depends(require_actor)],
    case_branch_id: CaseBranch,
) -> SuccessResponse[AgentCaseResponse]:
    result = await cancel_agent_case(actor, case_id, case_branch_id)
    return SuccessResponse(success=True, data=result, message="Agent case cancelled")
