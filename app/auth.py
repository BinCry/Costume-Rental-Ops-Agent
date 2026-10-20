from secrets import compare_digest
from typing import Annotated, cast
from uuid import UUID

from fastapi import Header, Security
from fastapi.security import APIKeyHeader

from app.config import get_settings
from app.errors import AppError
from app.knowledge.types import RetrievalAudience
from app.models import ActorContext

internal_service_scheme = APIKeyHeader(
    name="X-AI-Service-Key",
    scheme_name="InternalServiceKey",
    auto_error=False,
)


def require_internal_service(
    x_ai_service_key: Annotated[str | None, Security(internal_service_scheme)] = None,
) -> None:
    expected = get_settings().AI_INTERNAL_API_KEY
    if not expected:
        raise AppError(
            503, "INTERNAL_AUTH_NOT_CONFIGURED", "Internal authentication is not configured"
        )
    if not x_ai_service_key or not compare_digest(x_ai_service_key, expected):
        raise AppError(401, "INVALID_SERVICE_CREDENTIALS", "Invalid service credentials")


def resolve_actor(
    x_actor_id: Annotated[str | None, Header()] = None,
    x_knowledge_audiences: Annotated[str | None, Header()] = None,
    x_agent_read_branch_ids: Annotated[str | None, Header()] = None,
    x_agent_manage_branch_ids: Annotated[str | None, Header()] = None,
    x_agent_read_all: Annotated[str | None, Header()] = None,
    x_agent_manage_all: Annotated[str | None, Header()] = None,
) -> ActorContext:
    if not x_actor_id or not x_knowledge_audiences:
        raise AppError(400, "INVALID_ACTOR_CONTEXT", "Trusted actor context is required")

    raw_audiences = tuple(item.strip() for item in x_knowledge_audiences.split(",") if item.strip())
    allowed = {"customer", "staff_internal", "shared"}
    if (
        not raw_audiences
        or len(raw_audiences) != len(set(raw_audiences))
        or not set(raw_audiences) <= allowed
    ):
        raise AppError(400, "INVALID_ACTOR_CONTEXT", "Trusted actor context is invalid")

    audience_set = set(raw_audiences)
    valid_sets = ({"customer", "shared"}, {"staff_internal", "shared"})
    if audience_set not in valid_sets:
        raise AppError(400, "INVALID_ACTOR_CONTEXT", "Trusted actor context is invalid")
    if x_actor_id == "guest" and audience_set != {"customer", "shared"}:
        raise AppError(400, "INVALID_ACTOR_CONTEXT", "Guest actor context is invalid")

    audiences = cast(tuple[RetrievalAudience, ...], raw_audiences)

    def branch_ids(value: str | None) -> tuple[UUID, ...]:
        if not value:
            return ()
        try:
            parsed = tuple(UUID(item.strip()) for item in value.split(",") if item.strip())
        except ValueError as error:
            raise AppError(400, "INVALID_ACTOR_CONTEXT", "Agent branch scope is invalid") from error
        if len(parsed) != len(set(parsed)):
            raise AppError(400, "INVALID_ACTOR_CONTEXT", "Agent branch scope is invalid")
        return parsed

    def boolean(value: str | None) -> bool:
        if value is None:
            return False
        if value not in {"true", "false"}:
            raise AppError(400, "INVALID_ACTOR_CONTEXT", "Agent global scope is invalid")
        return value == "true"

    return ActorContext(
        user_id=x_actor_id,
        audiences=audiences,
        agent_read_branch_ids=branch_ids(x_agent_read_branch_ids),
        agent_manage_branch_ids=branch_ids(x_agent_manage_branch_ids),
        agent_read_all=boolean(x_agent_read_all),
        agent_manage_all=boolean(x_agent_manage_all),
    )


def require_actor(actor: Annotated[ActorContext, Security(resolve_actor)]) -> ActorContext:
    if actor.user_id == "guest":
        raise AppError(401, "AUTHENTICATED_ACTOR_REQUIRED", "An authenticated actor is required")
    return actor
