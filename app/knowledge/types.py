from dataclasses import dataclass
from typing import Final, Literal, get_args

DocumentStatus = Literal[
    "approved",
    "verified_from_system",
    "draft_from_code",
    "needs_business_confirmation",
    "deprecated",
]
DocumentAudience = Literal["customer", "staff_internal", "shared", "internal"]
RetrievalAudience = Literal["customer", "staff_internal", "shared"]

# Runtime validation sets are derived from the static Literal types so the
# accepted vocabulary has one source of truth.
ALLOWED_STATUSES: Final[frozenset[str]] = frozenset(get_args(DocumentStatus))
ALLOWED_AUDIENCES: Final[frozenset[str]] = frozenset(get_args(DocumentAudience))


@dataclass(frozen=True)
class KnowledgeDocument:
    document_id: str
    title: str
    domain: str
    status: DocumentStatus
    business_authority: bool
    audience: DocumentAudience
    retrieval_enabled: bool
    source_path: str
    body: str


@dataclass(frozen=True)
class KnowledgeChunk:
    chunk_id: str
    document_id: str
    title: str
    heading: str
    citation_label: str
    domain: str
    status: DocumentStatus
    business_authority: bool
    audience: RetrievalAudience
    content: str
    content_hash: str
    chunk_index: int
