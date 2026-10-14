"""Persisted, bounded case history for the agent runtime.

The database contains user-visible messages, execution summaries, and evidence
only.  It intentionally never stores model reasoning or provider prompts.
"""

import asyncio
import json
from datetime import datetime
from typing import Any
from uuid import UUID

from app.agent_tools.models import AgentCaseState
from app.agent_tools.state import require_transition
from app.knowledge.repository import _require_pool


def _case_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(row["id"]),
        "actor_id": str(row["actor_id"]),
        "audiences": tuple(row["audiences"]),
        "state": AgentCaseState(row["state"]),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "completed_at": row["completed_at"],
    }


def _create_case(actor_id: UUID, audiences: tuple[str, ...]) -> dict[str, Any]:
    with _require_pool().connection() as connection:
        row = connection.execute(
            """
            INSERT INTO agent_cases (actor_id, audiences, state)
            VALUES (%s, %s, %s)
            RETURNING id, actor_id, audiences, state, created_at, updated_at, completed_at
            """,
            (actor_id, list(audiences), AgentCaseState.NEW.value),
        ).fetchone()
    if row is None:
        raise RuntimeError("Could not create agent case")
    return _case_row(row)


async def create_case(actor_id: UUID, audiences: tuple[str, ...]) -> dict[str, Any]:
    return await asyncio.to_thread(_create_case, actor_id, audiences)


def _get_case(case_id: UUID, actor_id: UUID) -> dict[str, Any] | None:
    with _require_pool().connection() as connection:
        row = connection.execute(
            """
            SELECT id, actor_id, audiences, state, created_at, updated_at, completed_at
            FROM agent_cases
            WHERE id = %s AND actor_id = %s
            """,
            (case_id, actor_id),
        ).fetchone()
    return None if row is None else _case_row(row)


async def get_case(case_id: UUID, actor_id: UUID) -> dict[str, Any] | None:
    return await asyncio.to_thread(_get_case, case_id, actor_id)


def _transition_case(case_id: UUID, actor_id: UUID, target: AgentCaseState) -> AgentCaseState:
    with _require_pool().connection() as connection, connection.transaction():
        row = connection.execute(
            "SELECT state FROM agent_cases WHERE id = %s AND actor_id = %s FOR UPDATE",
            (case_id, actor_id),
        ).fetchone()
        if row is None:
            raise LookupError("Agent case not found")
        current = AgentCaseState(row["state"])
        require_transition(current, target)
        completed_at: datetime | None = (
            datetime.now().astimezone()
            if target
            in {
                AgentCaseState.SUCCEEDED,
                AgentCaseState.INSUFFICIENT_DATA,
                AgentCaseState.HANDED_OFF,
                AgentCaseState.FAILED,
                AgentCaseState.CANCELLED,
            }
            else None
        )
        connection.execute(
            "UPDATE agent_cases SET state = %s, updated_at = now(), "
            "completed_at = %s WHERE id = %s",
            (target.value, completed_at, case_id),
        )
    return target


async def transition_case(case_id: UUID, actor_id: UUID, target: AgentCaseState) -> AgentCaseState:
    return await asyncio.to_thread(_transition_case, case_id, actor_id, target)


def _get_case_overview(case_id: UUID, actor_id: UUID) -> dict[str, Any] | None:
    case = _get_case(case_id, actor_id)
    if case is None:
        return None
    with _require_pool().connection() as connection:
        message = connection.execute(
            """
            SELECT content FROM agent_messages
            WHERE case_id = %s AND role = 'assistant'
            ORDER BY created_at DESC LIMIT 1
            """,
            (case_id,),
        ).fetchone()
        evidence_rows = connection.execute(
            """
            SELECT source_type, source_id, citation, observed_at
            FROM agent_evidence WHERE case_id = %s
            ORDER BY created_at ASC
            """,
            (case_id,),
        ).fetchall()
    return {
        **case,
        "message": message["content"] if message is not None else "Case is being analyzed.",
        "evidence": [
            {
                "source_type": row["source_type"],
                "source_id": row["source_id"],
                "citation": row["citation"],
                "observed_at": (
                    row["observed_at"].isoformat() if row["observed_at"] is not None else None
                ),
            }
            for row in evidence_rows
        ],
    }


async def get_case_overview(case_id: UUID, actor_id: UUID) -> dict[str, Any] | None:
    return await asyncio.to_thread(_get_case_overview, case_id, actor_id)


def _append_turn(
    case_id: UUID,
    user_message: str,
    assistant_message: str,
    evidence: list[dict[str, Any]],
) -> None:
    with _require_pool().connection() as connection, connection.transaction():
        step_row = connection.execute(
            "SELECT COALESCE(MAX(step_index), 0) + 1 AS next_step "
            "FROM agent_steps WHERE case_id = %s",
            (case_id,),
        ).fetchone()
        step_index = int(step_row["next_step"])
        connection.execute(
            "INSERT INTO agent_messages (case_id, role, content) "
            "VALUES (%s, 'user', %s), (%s, 'assistant', %s)",
            (case_id, user_message, case_id, assistant_message),
        )
        connection.execute(
            """
            INSERT INTO agent_steps (case_id, step_index, kind, status, summary)
            VALUES (%s, %s, 'rag_answer', %s, %s)
            """,
            (case_id, step_index, "COMPLETED", "Answered from retrieved knowledge evidence"),
        )
        for item in evidence:
            connection.execute(
                """
                INSERT INTO agent_evidence (case_id, source_type, source_id, citation, payload)
                VALUES (%s, %s, %s, %s, %s::jsonb)
                """,
                (
                    case_id,
                    item["source_type"],
                    item["source_id"],
                    item.get("citation"),
                    json.dumps(item["payload"]),
                ),
            )


async def append_turn(
    case_id: UUID,
    user_message: str,
    assistant_message: str,
    evidence: list[dict[str, Any]],
) -> None:
    await asyncio.to_thread(
        _append_turn, case_id, user_message, assistant_message, evidence
    )
