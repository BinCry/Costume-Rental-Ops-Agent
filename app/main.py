import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.agent_tools.routes import router as agent_router
from app.config import get_settings
from app.errors import AppError
from app.knowledge.repository import close_pool, open_pool, ping_database
from app.knowledge.routes import router as knowledge_router
from app.models import ErrorBody, ErrorResponse

settings = get_settings()
logging.basicConfig(level=settings.LOG_LEVEL)
logger = logging.getLogger("costume_ops_api")


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    open_pool()
    yield
    close_pool()


app = FastAPI(
    title="Costume Rental Ops Agent API",
    version="0.1.0",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.AI_WEB_ALLOWED_ORIGINS),
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.middleware("http")
async def request_id(request: Request, call_next):  # type: ignore[no-untyped-def]
    current_request_id = request.headers.get("X-Request-Id") or str(uuid4())
    request.state.request_id = current_request_id
    response = await call_next(request)
    response.headers["X-Request-Id"] = current_request_id
    return response


@app.exception_handler(AppError)
async def app_error_handler(
    request: Request,
    error: AppError,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    current_request_id = getattr(request.state, "request_id", "unknown")
    response = ErrorResponse(
        success=False,
        error=ErrorBody(
            code=error.code,
            message=error.message,
            details=error.details,
        ),
        status_code=error.status_code,
        timestamp=datetime.now(UTC).isoformat(),
        path=request.url.path,
        request_id=current_request_id,
    )
    json_response = JSONResponse(
        status_code=error.status_code,
        content=response.model_dump(by_alias=True, exclude_none=True),
        headers=headers,
    )
    json_response.headers["X-Request-Id"] = current_request_id
    return json_response


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, error: RequestValidationError) -> JSONResponse:
    logger.warning(
        "Request validation failed",
        extra={"request_id": getattr(request.state, "request_id", "unknown")},
    )
    if any(issue.get("type") == "json_invalid" for issue in error.errors()):
        app_error = AppError(400, "INVALID_JSON", "Request body contains invalid JSON")
    else:
        messages = {
            "/api/v1/knowledge/answer": "Invalid knowledge answer request",
            "/api/v1/knowledge/search": "Invalid knowledge search request",
            "/api/v1/agent/messages": "Invalid agent message request",
        }
        app_error = AppError(
            400,
            "VALIDATION_ERROR",
            messages.get(request.url.path, "Request validation failed"),
        )
    return await app_error_handler(request, app_error)


@app.exception_handler(StarletteHTTPException)
async def http_error_handler(request: Request, error: StarletteHTTPException) -> JSONResponse:
    errors = {
        404: ("NOT_FOUND", "Route not found"),
        405: ("METHOD_NOT_ALLOWED", "Method not allowed"),
    }
    code, message = errors.get(
        error.status_code,
        ("HTTP_ERROR", error.detail if isinstance(error.detail, str) else "Request failed"),
    )
    return await app_error_handler(
        request,
        AppError(error.status_code, code, message),
        headers=dict(error.headers or {}),
    )


@app.exception_handler(Exception)
async def unexpected_error_handler(request: Request, error: Exception) -> JSONResponse:
    logger.exception("Unhandled request error", exc_info=error)
    return await app_error_handler(
        request,
        AppError(500, "INTERNAL_SERVER_ERROR", "An unexpected error occurred"),
    )


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "costume-ops-api"}


@app.get("/health/ready")
async def readiness() -> dict[str, str]:
    if not await ping_database():
        raise AppError(503, "DATABASE_UNAVAILABLE", "Knowledge database is not ready")
    return {"status": "ready", "service": "costume-ops-api", "database": "connected"}


app.include_router(knowledge_router, prefix="/api/v1/knowledge", tags=["Knowledge"])
app.include_router(agent_router, prefix="/api/v1/agent", tags=["Agent"])


def custom_openapi() -> dict[str, Any]:
    if app.openapi_schema is not None:
        return app.openapi_schema

    schema = get_openapi(
        title=app.title,
        version=app.version,
        routes=app.routes,
    )
    paths = schema.get("paths", {})
    if isinstance(paths, dict):
        knowledge_security: dict[str, list[dict[str, list[str]]]] = {
            "/api/v1/knowledge/answer": [{"InternalServiceKey": []}],
            "/api/v1/knowledge/search": [{"InternalServiceKey": []}],
            "/api/v1/agent/messages": [{"InternalServiceKey": []}],
            "/api/v1/agent/cases/{case_id}": [{"InternalServiceKey": []}],
        }
        for path, security in knowledge_security.items():
            path_item = paths.get(path)
            if not isinstance(path_item, dict):
                continue
            operation = path_item.get("post")
            if not isinstance(operation, dict):
                continue
            responses = operation.get("responses")
            if isinstance(responses, dict):
                responses.pop("422", None)
            parameters = operation.get("parameters")
            if isinstance(parameters, list):
                for parameter in parameters:
                    if (
                        isinstance(parameter, dict)
                        and parameter.get("in") == "header"
                        and parameter.get("name") in {"x-actor-id", "x-knowledge-audiences"}
                    ):
                        parameter["required"] = True
            operation["security"] = security

    app.openapi_schema = schema
    return schema


app.openapi = custom_openapi  # type: ignore[method-assign]
