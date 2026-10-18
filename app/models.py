from typing import Any, Generic, Literal, TypeVar
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


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


class AgentMessageInput(RequestModel):
    message: str = Field(min_length=2, max_length=2_000)
    branch_id: UUID
    case_id: UUID | None = None


class AgentDecisionInput(RequestModel):
    reason: str | None = Field(default=None, max_length=2_000)


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


class AgentMessageData(ApiModel):
    result: AgentCaseResponse
