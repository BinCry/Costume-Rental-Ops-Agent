from typing import Annotated, Any

from fastapi import APIRouter, Depends

from app.auth import require_actor, require_internal_service, resolve_actor
from app.knowledge.service import answer_knowledge, search_knowledge
from app.models import (
    ActorContext,
    AnswerInput,
    ErrorResponse,
    KnowledgeAnswerData,
    KnowledgeSearchData,
    SearchInput,
    SuccessResponse,
)

router = APIRouter(dependencies=[Depends(require_internal_service)])

ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    400: {"model": ErrorResponse, "description": "Invalid request"},
    401: {"model": ErrorResponse, "description": "Authentication failed"},
    403: {"model": ErrorResponse, "description": "Access denied"},
    429: {"model": ErrorResponse, "description": "Rate limited"},
    500: {"model": ErrorResponse, "description": "Unexpected service error"},
    503: {"model": ErrorResponse, "description": "Dependency unavailable"},
}


@router.post(
    "/search",
    response_model=SuccessResponse[KnowledgeSearchData],
    responses=ERROR_RESPONSES,
)
async def search(
    body: SearchInput,
    actor: Annotated[ActorContext, Depends(require_actor)],
) -> SuccessResponse[KnowledgeSearchData]:
    results = await search_knowledge(actor, body.query, body.top_k)
    return SuccessResponse(
        success=True,
        data=KnowledgeSearchData(results=results),
        message="Knowledge search completed",
    )


@router.post(
    "/answer",
    response_model=SuccessResponse[KnowledgeAnswerData],
    responses=ERROR_RESPONSES,
)
async def answer(
    body: AnswerInput,
    actor: Annotated[ActorContext, Depends(resolve_actor)],
) -> SuccessResponse[KnowledgeAnswerData]:
    result = await answer_knowledge(actor, body.query, body.top_k)
    return SuccessResponse(
        success=True,
        data=KnowledgeAnswerData(result=result),
        message="Knowledge answer completed",
    )
