"""Bounded agent turn runtime.

This initial runtime deliberately handles RAG-only turns.  It persists a case
and evidence now, while write-capable tools remain unavailable until their
confirmation, approval, idempotency, and read-back contracts are installed.
"""

from uuid import UUID

from app.agent_tools.cases import (
    append_turn,
    create_case,
    get_case,
    get_case_overview,
    transition_case,
)
from app.agent_tools.models import AgentCaseState
from app.errors import AppError
from app.knowledge.service import answer_knowledge
from app.models import ActorContext, AgentCaseResponse, AgentEvidence


async def answer_agent_message(
    actor: ActorContext,
    message: str,
    case_id: UUID | None,
) -> AgentCaseResponse:
    try:
        actor_id = UUID(actor.user_id)
    except ValueError as error:
        raise AppError(400, "INVALID_ACTOR_CONTEXT", "Trusted actor context is invalid") from error

    if case_id is None:
        case = await create_case(actor_id, tuple(actor.audiences))
    else:
        existing_case = await get_case(case_id, actor_id)
        if existing_case is None:
            # Do not reveal whether another actor owns the requested case.
            raise AppError(404, "AGENT_CASE_NOT_FOUND", "Agent case not found")
        case = existing_case

    current = case["state"]
    if current != AgentCaseState.NEW:
        raise AppError(
            409,
            "INVALID_CASE_TRANSITION",
            "This agent case cannot accept another message",
        )
    resolved_case_id = UUID(case["id"])
    await transition_case(resolved_case_id, actor_id, AgentCaseState.ANALYZING)

    knowledge = await answer_knowledge(actor, message, top_k=6)
    if knowledge.outcome == "answered":
        await transition_case(resolved_case_id, actor_id, AgentCaseState.PLAN_READY)
        await transition_case(resolved_case_id, actor_id, AgentCaseState.EXECUTING)
        state = await transition_case(resolved_case_id, actor_id, AgentCaseState.SUCCEEDED)
    else:
        state = await transition_case(resolved_case_id, actor_id, AgentCaseState.INSUFFICIENT_DATA)
    evidence = [
        AgentEvidence(
            source_type="knowledge",
            source_id=source.document_id,
            citation=source.citation,
        )
        for source in knowledge.sources
    ]
    await append_turn(
        resolved_case_id,
        message,
        knowledge.answer,
        [
            {
                "source_type": item.source_type,
                "source_id": item.source_id,
                "citation": item.citation,
                "payload": {"citation": item.citation},
            }
            for item in evidence
        ],
    )
    return AgentCaseResponse(
        case_id=resolved_case_id,
        state=state.value,
        message=knowledge.answer,
        evidence=evidence,
        completed=True,
    )


async def read_agent_case(actor: ActorContext, case_id: UUID) -> AgentCaseResponse:
    try:
        actor_id = UUID(actor.user_id)
    except ValueError as error:
        raise AppError(400, "INVALID_ACTOR_CONTEXT", "Trusted actor context is invalid") from error
    case = await get_case_overview(case_id, actor_id)
    if case is None:
        raise AppError(404, "AGENT_CASE_NOT_FOUND", "Agent case not found")
    terminal = {
        AgentCaseState.SUCCEEDED,
        AgentCaseState.INSUFFICIENT_DATA,
        AgentCaseState.HANDED_OFF,
        AgentCaseState.FAILED,
        AgentCaseState.CANCELLED,
    }
    return AgentCaseResponse(
        case_id=case_id,
        state=case["state"].value,
        message=case["message"],
        evidence=[AgentEvidence(**item) for item in case["evidence"]],
        completed=case["state"] in terminal,
    )
