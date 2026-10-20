from datetime import UTC, datetime
from typing import Any, Generic, Literal, TypeVar
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def to_camel(value: str) -> str:
    first, *rest = value.split("_")
    return first + "".join(word.capitalize() for word in rest)


class ApiModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class RequestModel(ApiModel):
    model_config = ConfigDict(str_strip_whitespace=True)


class SearchInput(RequestModel):
    query: str = Field(min_length=2, max_length=1_000)
    top_k: int = Field(default=5, ge=1, le=8)


class AnswerInput(RequestModel):
    query: str = Field(min_length=2, max_length=1_000)
    top_k: int = Field(default=5, ge=1, le=6)


class SearchResult(ApiModel):
    document_id: str
    heading: str
    citation: str
    domain: str
    status: str
    business_authority: bool
    content: str
    score: float


class AnswerSource(ApiModel):
    document_id: str
    heading: str
    citation: str
    domain: str
    status: str
    business_authority: bool


class KnowledgeAnswer(ApiModel):
    outcome: Literal["answered", "insufficient_context"]
    answer: str
    sources: list[AnswerSource]
    provisional: bool


class KnowledgeSearchData(ApiModel):
    results: list[SearchResult]


class KnowledgeAnswerData(ApiModel):
    result: KnowledgeAnswer


ResponseData = TypeVar("ResponseData")


class SuccessResponse(ApiModel, Generic[ResponseData]):
    success: Literal[True]
    data: ResponseData
    message: str


class ErrorBody(ApiModel):
    code: str
    message: str
    details: dict[str, Any] | None = None


class ErrorResponse(ApiModel):
    success: Literal[False]
    error: ErrorBody
    status_code: int
    timestamp: str
    path: str
    request_id: str


class ActorContext(BaseModel):
    user_id: str
    audiences: tuple[Literal["customer", "staff_internal", "shared"], ...]
    agent_read_branch_ids: tuple[UUID, ...] = ()
    agent_manage_branch_ids: tuple[UUID, ...] = ()
    agent_read_all: bool = False
    agent_manage_all: bool = False


class AgentMessageInput(RequestModel):
    message: str = Field(min_length=2, max_length=2_000)
    branch_id: UUID
    case_id: UUID | None = None


class AgentDecisionInput(RequestModel):
    reason: str | None = Field(default=None, max_length=2_000)


class AgentCaseVersionInput(RequestModel):
    expected_version: int = Field(ge=1)


class AgentReadinessConfirmationInput(AgentCaseVersionInput):
    analysis_id: UUID


class AgentOverdueFollowUpConfirmationInput(AgentCaseVersionInput):
    model_config = ConfigDict(extra="forbid")

    analysis_id: UUID
    channel: Literal["IN_PERSON", "PHONE", "EMAIL", "CHAT", "SOCIAL"]
    outcome: Literal[
        "PROMISED_RETURN",
        "NO_ANSWER",
        "REQUESTED_EXTENSION",
        "REFUSED_RETURN",
        "CONTACTED",
        "OTHER",
    ]
    occurred_at: datetime
    promised_return_at: datetime | None = None
    next_follow_up_at: datetime | None = None

    @field_validator("occurred_at", "promised_return_at", "next_follow_up_at")
    @classmethod
    def normalize_follow_up_time(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Follow-up timestamps must include a timezone")
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def validate_follow_up_shape(self) -> "AgentOverdueFollowUpConfirmationInput":
        if self.occurred_at > datetime.now(UTC):
            raise ValueError("occurredAt cannot be in the future")
        if self.outcome == "PROMISED_RETURN":
            if self.promised_return_at is None:
                raise ValueError("promisedReturnAt is required for PROMISED_RETURN")
        elif self.promised_return_at is not None:
            raise ValueError("promisedReturnAt is only allowed for PROMISED_RETURN")
        if self.promised_return_at is not None and self.promised_return_at <= datetime.now(UTC):
            raise ValueError("promisedReturnAt must be in the future")
        requires_next_follow_up = {
            "NO_ANSWER",
            "REQUESTED_EXTENSION",
            "REFUSED_RETURN",
        }
        if self.outcome in requires_next_follow_up and self.next_follow_up_at is None:
            raise ValueError(f"nextFollowUpAt is required for {self.outcome}")
        if self.next_follow_up_at is not None and self.next_follow_up_at <= self.occurred_at:
            raise ValueError("nextFollowUpAt must be after occurredAt")
        return self


class AgentFindingUpsertInput(RequestModel):
    rule_code: Literal[
        "PREVIOUS_RENTAL_NOT_RETURNED",
        "ALLOCATED_UNIT_NOT_READY",
        "ORDER_PREPARATION_DELAYED",
        "RENTAL_RETURN_OVERDUE",
        "OPERATIONAL_CAPACITY_SHORTFALL",
        "UNIT_SCHEDULE_CONFLICT",
    ]
    rule_version: str = Field(min_length=1, max_length=50)
    dedupe_key: str = Field(min_length=1, max_length=255)
    branch_id: UUID
    primary_entity_id: UUID
    affected_entity_id: UUID | None = None
    unit_id: UUID | None = None
    window_start: datetime
    window_end: datetime
    severity: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    deadline_at: datetime
    evidence: dict[str, Any] = Field(default_factory=dict)
    observed_at: datetime | None = None

    @model_validator(mode="after")
    def validate_entity_shape(self) -> "AgentFindingUpsertInput":
        order_level = self.rule_code in {
            "ORDER_PREPARATION_DELAYED",
            "RENTAL_RETURN_OVERDUE",
            "OPERATIONAL_CAPACITY_SHORTFALL",
        }
        if order_level and (self.affected_entity_id is not None or self.unit_id is not None):
            raise ValueError("Order-level findings cannot reference one affected unit")
        if not order_level and (self.affected_entity_id is None or self.unit_id is None):
            raise ValueError("Unit-level readiness findings require affectedEntityId and unitId")
        return self

    @field_validator("observed_at")
    @classmethod
    def normalize_observed_at(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("observedAt must include a timezone offset")
        return value.astimezone(UTC)


class AgentFindingResolveInput(RequestModel):
    dedupe_key: str = Field(min_length=1, max_length=255)
    rule_code: Literal[
        "PREVIOUS_RENTAL_NOT_RETURNED",
        "ALLOCATED_UNIT_NOT_READY",
        "ORDER_PREPARATION_DELAYED",
        "RENTAL_RETURN_OVERDUE",
        "OPERATIONAL_CAPACITY_SHORTFALL",
        "UNIT_SCHEDULE_CONFLICT",
    ]
    observed_at: datetime
    resolution_code: Literal["RISK_NO_LONGER_PRESENT"]
    evidence: dict[str, Any] = Field(default_factory=dict)

    @field_validator("observed_at")
    @classmethod
    def normalize_observed_at(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("observedAt must include a timezone offset")
        return value.astimezone(UTC)


class AgentFinding(ApiModel):
    finding_id: UUID
    rule_code: str
    rule_version: str
    dedupe_key: str
    primary_entity_id: UUID
    affected_entity_id: UUID | None = None
    unit_id: UUID | None = None
    window_start: datetime
    window_end: datetime
    severity: str
    status: str
    evidence: dict[str, Any]
    first_detected_at: datetime
    last_detected_at: datetime
    source_observed_at: datetime
    resolved_at: datetime | None = None


class AgentInternalFinding(ApiModel):
    finding_id: UUID
    case_id: UUID
    branch_id: UUID
    rule_code: str
    rule_version: str
    dedupe_key: str
    primary_entity_id: UUID
    affected_entity_id: UUID | None = None
    unit_id: UUID | None = None
    window_start: datetime
    window_end: datetime
    severity: str
    status: str
    evidence: dict[str, Any]
    first_detected_at: datetime
    last_detected_at: datetime
    source_observed_at: datetime
    resolved_at: datetime | None = None


class AgentInternalFindingListData(ApiModel):
    items: list[AgentInternalFinding]
    next_cursor: str | None = None


class AgentFindingResolveData(ApiModel):
    case_id: UUID
    dedupe_key: str
    outcome: Literal["RESOLVED", "ALREADY_RESOLVED", "STALE"]
    source_observed_at: datetime


class AgentReadinessAnalysisNarrative(ApiModel):
    summary: str
    rationale: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    next_step: str
    fallback: bool = False


class AgentReadinessAnalysis(ApiModel):
    analysis_id: UUID
    status: Literal["ACTIVE", "STALE"]
    outcome: Literal["READY", "NO_FEASIBLE_OPTION"]
    observed_at: datetime
    source_observed_at: datetime
    simulator_version: str
    ranking_policy_version: str
    before: dict[str, Any]
    options: list[dict[str, Any]]
    recommended_option_id: str | None = None
    narrative: AgentReadinessAnalysisNarrative


class AgentEvidence(ApiModel):
    source_type: Literal["knowledge", "live_tool"]
    source_id: str
    citation: str | None = None
    observed_at: str | None = None


class AgentGoal(ApiModel):
    summary: str
    status: str = "active"
    goal_type: str | None = None
    skill_name: str | None = None
    constraints: dict[str, Any] = Field(default_factory=dict)
    plan: list[dict[str, Any]] = Field(default_factory=list)
    success_criteria: list[str] = Field(default_factory=list)


class AgentHandoff(ApiModel):
    reason: str
    goal: str | None = None
    attempted_tools: list[str] = Field(default_factory=list)
    successful_tools: list[str] = Field(default_factory=list)
    failed_tools: list[str] = Field(default_factory=list)
    evidence_count: int = 0
    next_action: str
    side_effects: str = "none"


class PendingConfirmation(ApiModel):
    confirmation_id: UUID
    summary: str
    expires_at: str
    analysis_id: UUID | None = None
    option_id: str | None = None
    action: dict[str, Any] | None = None


class PendingApproval(ApiModel):
    approval_id: UUID
    summary: str
    required_permission: str
    expires_at: str


class AgentCaseResponse(ApiModel):
    case_id: UUID
    state: str
    message: str
    evidence: list[AgentEvidence]
    run_status: str | None = None
    goal: AgentGoal | None = None
    steps_used: int = 0
    tokens_used: int = 0
    termination_reason: str | None = None
    pending_input: str | None = None
    pending_confirmation: PendingConfirmation | None = None
    pending_approval: PendingApproval | None = None
    handoff: AgentHandoff | None = None
    completed: bool
    origin: str | None = None
    case_type: str | None = None
    branch_id: UUID | None = None
    owner_actor_id: UUID | None = None
    claimed_at: datetime | None = None
    deadline_at: datetime | None = None
    version: int | None = None
    finding: AgentFinding | None = None
    analysis: AgentReadinessAnalysis | None = None


class AgentCaseListData(ApiModel):
    items: list[AgentCaseResponse]
    next_cursor: str | None = None


class AgentMessageData(ApiModel):
    result: AgentCaseResponse
