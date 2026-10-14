"""Versioned wire models for the fixed Studio internal agent-tool contract."""

from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import Field, field_validator

from app.models import ApiModel

AGENT_TOOLS_CONTRACT_VERSION = "agent-tools/v1"


class AgentCaseState(StrEnum):
    NEW = "NEW"
    ANALYZING = "ANALYZING"
    PLAN_READY = "PLAN_READY"
    WAITING_CONFIRMATION = "WAITING_CONFIRMATION"
    WAITING_APPROVAL = "WAITING_APPROVAL"
    EXECUTING = "EXECUTING"
    MONITORING = "MONITORING"
    SUCCEEDED = "SUCCEEDED"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    HANDED_OFF = "HANDED_OFF"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class ToolExecutionStatus(StrEnum):
    OK = "ok"
    NOT_FOUND = "not_found"
    FORBIDDEN = "forbidden"
    VALIDATION_ERROR = "validation_error"
    APPROVAL_REQUIRED = "approval_required"
    APPROVAL_EXPIRED = "approval_expired"
    VERSION_CONFLICT = "version_conflict"
    DEPENDENCY_UNAVAILABLE = "dependency_unavailable"
    UNKNOWN_OUTCOME = "unknown_outcome"


class AgentToolExecutionRequest(ApiModel):
    """A call to one named tool; it can never carry an arbitrary URL or method."""

    case_id: UUID
    tool_call_id: UUID
    tool_name: str = Field(pattern=r"^[a-z][a-z0-9_]{1,79}$")
    arguments: dict[str, Any] = Field(default_factory=dict)
    expected_version: int | None = Field(default=None, ge=0)
    idempotency_key: str = Field(min_length=1, max_length=255)
    approval_id: UUID | None = None

    @field_validator("idempotency_key")
    @classmethod
    def reject_whitespace_idempotency_key(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("idempotency_key must not be blank")
        return value


class AgentToolExecutionResult(ApiModel):
    """Normalized outcome from the Studio internal tool endpoint."""

    status: ToolExecutionStatus
    data: dict[str, Any] | None = None
    source: str = "studio-api"
    observed_at: datetime | None = None
    request_id: str | None = None
    record_version: int | None = Field(default=None, ge=0)
    details: dict[str, Any] | None = None
