"""Internal API called only by Studio after it authenticates the user."""

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends

from app.agent_tools.runtime import answer_agent_message, read_agent_case
from app.auth import require_actor, require_internal_service
from app.models import (
    ActorContext,
    AgentCaseResponse,
    AgentMessageData,
    AgentMessageInput,
    ErrorResponse,
    SuccessResponse,
)

router = APIRouter(dependencies=[Depends(require_internal_service)])

ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    400: {"model": ErrorResponse, "description": "Invalid request"},
    401: {"model": ErrorResponse, "description": "Authentication failed"},
    403: {"model": ErrorResponse, "description": "Access denied"},
    404: {"model": ErrorResponse, "description": "Case not found"},
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
) -> SuccessResponse[AgentMessageData]:
    result = await answer_agent_message(actor, body.message, body.case_id)
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
) -> SuccessResponse[AgentCaseResponse]:
    result = await read_agent_case(actor, case_id)
    return SuccessResponse(success=True, data=result, message="Agent case retrieved")
