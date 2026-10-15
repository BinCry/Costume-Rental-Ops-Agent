"""Versioned wire models for the fixed Studio internal agent-tool contract."""

from datetime import datetime
from enum import StrEnum
from typing import Any, Literal
from uuid import UUID

from pydantic import Field, field_validator

from app.models import ApiModel

AGENT_TOOLS_CONTRACT_VERSION = "agent-tools/v1"


class AgentCaseState(StrEnum):
    NEW = "NEW"
    ANALYZING = "ANALYZING"
    PLAN_READY = "PLAN_READY"
    WAITING_INPUT = "WAITING_INPUT"
    WAITING_CONFIRMATION = "WAITING_CONFIRMATION"
    WAITING_APPROVAL = "WAITING_APPROVAL"
    EXECUTING = "EXECUTING"
    MONITORING = "MONITORING"
    SUCCEEDED = "SUCCEEDED"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    HANDED_OFF = "HANDED_OFF"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class AgentRunStatus(StrEnum):
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class AgentTerminationReason(StrEnum):
    GOAL_ACHIEVED = "GOAL_ACHIEVED"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    HUMAN_INPUT_REQUIRED = "HUMAN_INPUT_REQUIRED"
    CONFIRMATION_REJECTED = "CONFIRMATION_REJECTED"
    APPROVAL_REJECTED = "APPROVAL_REJECTED"
    BUDGET_EXHAUSTED = "BUDGET_EXHAUSTED"
    LOOP_DETECTED = "LOOP_DETECTED"
    NO_PROGRESS = "NO_PROGRESS"
    TOOL_OUTCOME_UNKNOWN = "TOOL_OUTCOME_UNKNOWN"
    DEPENDENCY_FAILURE = "DEPENDENCY_FAILURE"
    POLICY_VIOLATION = "POLICY_VIOLATION"
    INVALID_TOOL_ARGUMENTS = "INVALID_TOOL_ARGUMENTS"
    VERIFICATION_FAILED = "VERIFICATION_FAILED"
    CANCELLED_BY_USER = "CANCELLED_BY_USER"


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


class AgentGoalType(StrEnum):
    KNOWLEDGE_ANSWER = "KNOWLEDGE_ANSWER"
    RENTAL_ORDER_LOOKUP = "RENTAL_ORDER_LOOKUP"
    RENTAL_ORDER_SEARCH = "RENTAL_ORDER_SEARCH"
    PAYMENT_SUMMARY = "PAYMENT_SUMMARY"
    AVAILABILITY_CHECK = "AVAILABILITY_CHECK"
    UNIT_SCHEDULE = "UNIT_SCHEDULE"
    STOCK_TRANSFER_LOOKUP = "STOCK_TRANSFER_LOOKUP"
    UNIT_BLOCK_CHANGE = "UNIT_BLOCK_CHANGE"
    RENTAL_EXTENSION = "RENTAL_EXTENSION"
    RENTAL_REALLOCATION = "RENTAL_REALLOCATION"
    RENTAL_CANCELLATION = "RENTAL_CANCELLATION"
    STOCK_TRANSFER_CREATE = "STOCK_TRANSFER_CREATE"
    STOCK_TRANSFER_DECISION = "STOCK_TRANSFER_DECISION"
    PAYMENT_CHECKOUT = "PAYMENT_CHECKOUT"
    REFUND_REQUEST = "REFUND_REQUEST"
    GENERAL_ASSISTANCE = "GENERAL_ASSISTANCE"


class AgentGoalConstraints(ApiModel):
    """Deterministic boundaries attached to a case goal."""

    allowed_tools: tuple[str, ...] = ()
    requires_confirmation: bool = False
    requires_approval: bool = False
    max_steps: int = Field(default=6, ge=1, le=24)


class AgentPlanStep(ApiModel):
    order: int = Field(ge=1, le=24)
    action: str = Field(min_length=1, max_length=500)
    tool_name: str | None = None
    verification: str = Field(min_length=1, max_length=500)


class AgentGoalSpec(ApiModel):
    summary: str
    goal_type: AgentGoalType
    status: str = "active"
    required_tools: tuple[str, ...] = ()
    required_identifiers: tuple[str, ...] = ()
    extracted_inputs: dict[str, Any] = Field(default_factory=dict)
    missing_inputs: tuple[str, ...] = ()
    success_criteria: tuple[str, ...] = ()
    resolution_source: Literal["rule", "model", "fallback", "continuation"] = "rule"
    confidence: float = Field(default=1.0, ge=0, le=1)
    skill_name: str | None = None
    constraints: AgentGoalConstraints = Field(default_factory=AgentGoalConstraints)
    plan: tuple[AgentPlanStep, ...] = ()


class GoalEntities(ApiModel):
    """Typed values that a goal classifier may extract but never execute directly."""

    order_id: UUID | None = None
    transfer_id: UUID | None = None
    unit_id: UUID | None = None
    variant_id: UUID | None = None
    pickup_branch_id: UUID | None = None
    planned_start_at: datetime | None = None
    planned_due_at: datetime | None = None
    new_due_at: datetime | None = None
    order_item_id: UUID | None = None
    payment_id: UUID | None = None
    block_id: UUID | None = None
    from_branch_id: UUID | None = None
    to_branch_id: UUID | None = None
    unit_ids: tuple[UUID, ...] = ()
    reason: str | None = Field(default=None, max_length=1_000)
    amount_vnd: int | None = Field(default=None, gt=0)
    purpose: str | None = Field(default=None, max_length=500)
    search: str | None = Field(default=None, max_length=500)


class GoalDraft(ApiModel):
    """Untrusted structured interpretation returned by a language model."""

    goal_type: AgentGoalType
    confidence: float = Field(ge=0, le=1)
    summary: str = Field(min_length=1, max_length=2_000)
    entities: GoalEntities = Field(default_factory=GoalEntities)
    missing_inputs: tuple[str, ...] = ()
    explicit_write_intent: bool = False


class ActionProposal(ApiModel):
    """Untrusted model proposal; it becomes executable only after being frozen."""

    tool_name: str = Field(pattern=r"^[a-z][a-z0-9_]{1,79}$")
    arguments: dict[str, Any] = Field(default_factory=dict)
    expected_version: int | None = Field(default=None, ge=1)
    summary: str = Field(min_length=1, max_length=2_000)


class FrozenAction(ActionProposal):
    payload_hash: str = Field(min_length=64, max_length=64)
    readback_tool: str
    confirmation_id: UUID | None = None
    approval_id: UUID | None = None


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
