"""Internal API called only by Studio after it authenticates the user."""

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Header

from app.agent_tools.runtime import (
    answer_agent_message,
    cancel_agent_case,
    decide_case_approval,
    decide_case_confirmation,
    read_agent_case,
)
from app.auth import require_actor, require_internal_service
from app.errors import AppError
from app.models import (
    ActorContext,
    AgentCaseResponse,
    AgentDecisionInput,
    AgentMessageData,
    AgentMessageInput,
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
