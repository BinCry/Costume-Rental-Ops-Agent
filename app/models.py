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
    case_id: UUID | None = None


class AgentEvidence(ApiModel):
    source_type: Literal["knowledge", "live_tool"]
    source_id: str
    citation: str | None = None
    observed_at: str | None = None


class AgentCaseResponse(ApiModel):
    case_id: UUID
    state: str
    message: str
    evidence: list[AgentEvidence]
    pending_confirmation: None = None
    pending_approval: None = None
    completed: bool


class AgentMessageData(ApiModel):
    result: AgentCaseResponse
