"""Persistence operations for turns, tool calls, goals, runs, and budgets."""

import asyncio
import json
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from app.agent_tools.models import (
    AgentGoalSpec,
    AgentRunStatus,
)
from app.agent_tools.repository_errors import CaseBusyError
from app.knowledge.repository import _require_pool


def _append_turn(
    case_id: UUID,
    user_message: str,
    assistant_message: str,
    evidence: list[dict[str, Any]],
    step_kind: str = "agent_answer",
    step_status: str = "COMPLETED",
    step_summary: str = "Agent turn completed",
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
            VALUES (%s, %s, %s, %s, %s)
            """,
            (case_id, step_index, step_kind, step_status, step_summary),
        )
        for item in evidence:
            connection.execute(
                """
                INSERT INTO agent_evidence
                  (case_id, source_type, source_id, citation, observed_at, payload)
                VALUES (%s, %s, %s, %s, %s, %s::jsonb)
                """,
                (
                    case_id,
                    item["source_type"],
                    item["source_id"],
                    item.get("citation"),
                    item.get("observed_at"),
                    json.dumps(item["payload"]),
                ),
            )


async def append_turn(
    case_id: UUID,
    user_message: str,
    assistant_message: str,
    evidence: list[dict[str, Any]],
    step_kind: str = "agent_answer",
    step_status: str = "COMPLETED",
    step_summary: str = "Agent turn completed",
) -> None:
    await asyncio.to_thread(
        _append_turn,
        case_id,
        user_message,
        assistant_message,
        evidence,
        step_kind,
        step_status,
        step_summary,
    )


def _start_tool_call(
    case_id: UUID,
    tool_call_id: UUID,
    tool_name: str,
    request_id: UUID,
    idempotency_key: str,
    payload_hash: str | None = None,
    expected_version: int | None = None,
    confirmation_id: UUID | None = None,
    approval_id: UUID | None = None,
) -> None:
    with _require_pool().connection() as connection:
        connection.execute(
            """
            INSERT INTO agent_tool_calls
              (case_id, tool_call_id, tool_name, status, request_id, idempotency_key,
               payload_hash, expected_version, confirmation_id, approval_id)
            VALUES (%s, %s, %s, 'RUNNING', %s, %s, %s, %s, %s, %s)
            ON CONFLICT (tool_call_id) DO NOTHING
            """,
            (
                case_id,
                tool_call_id,
                tool_name,
                request_id,
                idempotency_key,
                payload_hash,
                expected_version,
                confirmation_id,
                approval_id,
            ),
        )


async def start_tool_call(
    case_id: UUID,
    tool_call_id: UUID,
    tool_name: str,
    request_id: UUID,
    idempotency_key: str,
    payload_hash: str | None = None,
    expected_version: int | None = None,
    confirmation_id: UUID | None = None,
    approval_id: UUID | None = None,
) -> None:
    await asyncio.to_thread(
        _start_tool_call,
        case_id,
        tool_call_id,
        tool_name,
        request_id,
        idempotency_key,
        payload_hash,
        expected_version,
        confirmation_id,
        approval_id,
    )


def _finish_tool_call(tool_call_id: UUID, status: str, outcome: dict[str, Any]) -> None:
    with _require_pool().connection() as connection:
        connection.execute(
            """
            UPDATE agent_tool_calls
            SET status = %s, outcome = %s::jsonb, updated_at = now(), finished_at = now()
            WHERE tool_call_id = %s
            """,
            (status, json.dumps(outcome, default=str), tool_call_id),
        )


async def finish_tool_call(tool_call_id: UUID, status: str, outcome: dict[str, Any]) -> None:
    await asyncio.to_thread(_finish_tool_call, tool_call_id, status, outcome)


def _get_tool_call(tool_call_id: UUID) -> dict[str, Any] | None:
    with _require_pool().connection() as connection:
        row = connection.execute(
            "SELECT status, outcome FROM agent_tool_calls WHERE tool_call_id = %s", (tool_call_id,)
        ).fetchone()
    return None if row is None else {"status": row["status"], "outcome": row["outcome"]}


async def get_tool_call(tool_call_id: UUID) -> dict[str, Any] | None:
    return await asyncio.to_thread(_get_tool_call, tool_call_id)


def _set_goal(case_id: UUID, actor_id: UUID, goal: AgentGoalSpec) -> None:
    with _require_pool().connection() as connection:
        connection.execute(
            "UPDATE agent_cases SET goal = %s::jsonb, updated_at = now(), version = version + 1 "
            "WHERE id = %s AND owner_actor_id = %s",
            (goal.model_dump_json(), case_id, actor_id),
        )


async def set_goal(case_id: UUID, actor_id: UUID, goal: AgentGoalSpec) -> None:
    await asyncio.to_thread(_set_goal, case_id, actor_id, goal)


def _set_goal_status(case_id: UUID, actor_id: UUID, status: str) -> None:
    with _require_pool().connection() as connection:
        connection.execute(
            """
            UPDATE agent_cases
            SET goal = jsonb_set(goal, '{status}', to_jsonb(%s::text), true),
                updated_at = now(), version = version + 1
            WHERE id = %s AND owner_actor_id = %s AND goal IS NOT NULL
            """,
            (status, case_id, actor_id),
        )


async def set_goal_status(case_id: UUID, actor_id: UUID, status: str) -> None:
    await asyncio.to_thread(_set_goal_status, case_id, actor_id, status)


def _create_run(case_id: UUID, message: str | None, timeout_seconds: float) -> UUID:
    run_id = uuid4()
    with _require_pool().connection() as connection, connection.transaction():
        current = connection.execute(
            "SELECT active_run_id, active_run_deadline FROM agent_cases WHERE id = %s FOR UPDATE",
            (case_id,),
        ).fetchone()
        if current is None:
            raise LookupError("Agent case not found")
        deadline = current["active_run_deadline"]
        if current["active_run_id"] is not None and (
            deadline is None or deadline > datetime.now(UTC)
        ):
            raise CaseBusyError("An agent request is already running for this case")
        if current["active_run_id"] is not None:
            connection.execute(
                "UPDATE agent_runs SET status = 'FAILED', error_code = 'RUN_DEADLINE_EXPIRED', "
                "completed_at = now() WHERE id = %s AND status = 'RUNNING'",
                (current["active_run_id"],),
            )
        case = connection.execute(
            """
            UPDATE agent_cases
            SET active_run_id = %s,
                active_run_deadline = now() + (%s * interval '1 second'),
                last_run_status = %s,
                updated_at = now()
            WHERE id = %s
            RETURNING id
            """,
            (run_id, timeout_seconds, AgentRunStatus.RUNNING.value, case_id),
        ).fetchone()
        if case is None:
            raise LookupError("Agent case not found")
        row = connection.execute(
            """
            INSERT INTO agent_runs (id, case_id, status, input_message, started_at, deadline_at)
            VALUES (%s, %s, %s, %s, now(), now() + (%s * interval '1 second'))
            RETURNING id
            """,
            (run_id, case_id, AgentRunStatus.RUNNING.value, message, timeout_seconds),
        ).fetchone()
    if row is None:
        raise RuntimeError("Could not create agent run")
    return UUID(str(row["id"]))


async def create_run(case_id: UUID, message: str | None, timeout_seconds: float) -> UUID:
    return await asyncio.to_thread(_create_run, case_id, message, timeout_seconds)


def _mark_run(
    run_id: UUID,
    status: AgentRunStatus,
    error_code: str | None = None,
    token_usage: int = 0,
    step_count: int = 0,
) -> None:
    with _require_pool().connection() as connection:
        connection.execute(
            "UPDATE agent_runs SET status = %s, error_code = %s, "
            "token_usage = %s, step_count = %s, "
            "completed_at = CASE WHEN %s IN ('PAUSED', 'COMPLETED', 'FAILED', 'CANCELLED') "
            "THEN now() ELSE completed_at END "
            "WHERE id = %s",
            (
                status.value,
                error_code,
                token_usage,
                step_count,
                status.value,
                run_id,
            ),
        )
        connection.execute(
            "UPDATE agent_cases SET last_run_status = %s, active_run_id = NULL, "
            "active_run_deadline = NULL, updated_at = now() "
            "WHERE id = (SELECT case_id FROM agent_runs WHERE id = %s) "
            "AND active_run_id = %s",
            (status.value, run_id, run_id),
        )


async def mark_run(
    run_id: UUID,
    status: AgentRunStatus,
    error_code: str | None = None,
    token_usage: int = 0,
    step_count: int = 0,
) -> None:
    await asyncio.to_thread(_mark_run, run_id, status, error_code, token_usage, step_count)


def _get_case_budget_usage(case_id: UUID) -> tuple[int, int]:
    with _require_pool().connection() as connection:
        row = connection.execute(
            """
            SELECT COALESCE(SUM(token_usage), 0) AS tokens,
                   COALESCE(SUM(step_count), 0) AS steps
            FROM agent_runs
    WHERE case_id = %s AND status IN ('PAUSED', 'COMPLETED')
            """,
            (case_id,),
        ).fetchone()
    if row is None:
        return 0, 0
    return int(row["tokens"]), int(row["steps"])


async def get_case_budget_usage(case_id: UUID) -> tuple[int, int]:
    return await asyncio.to_thread(_get_case_budget_usage, case_id)
