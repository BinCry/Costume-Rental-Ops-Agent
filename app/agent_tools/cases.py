"""Persisted, bounded case history for the agent runtime.

The database contains user-visible messages, execution summaries, and evidence
only.  It intentionally never stores model reasoning or provider prompts.
"""

import asyncio
import hashlib
import json
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

from app.agent_tools.models import (
    AgentCaseState,
    AgentGoalSpec,
    AgentRunStatus,
    AgentTerminationReason,
)
from app.agent_tools.state import require_transition
from app.knowledge.repository import _require_pool


class CaseBusyError(RuntimeError):
    """Raised when another synchronous HTTP request owns a case run."""


def _case_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(row["id"]),
        "actor_id": str(row["actor_id"]),
        "audiences": tuple(row["audiences"]),
        "state": AgentCaseState(row["state"]),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "completed_at": row["completed_at"],
        "goal": row.get("goal"),
        "version": row.get("version", 1),
        "termination_reason": row.get("termination_reason"),
        "last_run_status": row.get("last_run_status"),
        "active_run_id": str(row["active_run_id"]) if row.get("active_run_id") else None,
        "active_run_deadline": row.get("active_run_deadline"),
    }


def _create_case(actor_id: UUID, audiences: tuple[str, ...]) -> dict[str, Any]:
    with _require_pool().connection() as connection:
        row = connection.execute(
            """
            INSERT INTO agent_cases (actor_id, audiences, state)
            VALUES (%s, %s, %s)
            RETURNING id, actor_id, audiences, state, created_at, updated_at, completed_at,
              goal, version, termination_reason, last_run_status, active_run_id, active_run_deadline
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
            SELECT id, actor_id, audiences, state, created_at, updated_at, completed_at,
              goal, version, termination_reason, last_run_status, active_run_id, active_run_deadline
            FROM agent_cases
            WHERE id = %s AND actor_id = %s
            """,
            (case_id, actor_id),
        ).fetchone()
    return None if row is None else _case_row(row)


async def get_case(case_id: UUID, actor_id: UUID) -> dict[str, Any] | None:
    return await asyncio.to_thread(_get_case, case_id, actor_id)


def _get_case_by_id(case_id: UUID) -> dict[str, Any] | None:
    with _require_pool().connection() as connection:
        row = connection.execute(
            """
            SELECT id, actor_id, audiences, state, created_at, updated_at, completed_at,
              goal, version, termination_reason, last_run_status, active_run_id, active_run_deadline
            FROM agent_cases WHERE id = %s
            """,
            (case_id,),
        ).fetchone()
    return None if row is None else _case_row(row)


async def get_case_by_id(case_id: UUID) -> dict[str, Any] | None:
    return await asyncio.to_thread(_get_case_by_id, case_id)


def _transition_case(
    case_id: UUID,
    actor_id: UUID,
    target: AgentCaseState,
    termination_reason: AgentTerminationReason | None = None,
) -> AgentCaseState:
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
            "UPDATE agent_cases SET state = %s, updated_at = now(), version = version + 1, "
            "completed_at = %s, termination_reason = COALESCE(%s, termination_reason) "
            "WHERE id = %s",
            (
                target.value,
                completed_at,
                termination_reason.value if termination_reason else None,
                case_id,
            ),
        )
        if target is AgentCaseState.CANCELLED:
            connection.execute(
                "UPDATE agent_confirmations SET status = 'REJECTED', decided_at = now() "
                "WHERE case_id = %s AND status = 'PENDING'",
                (case_id,),
            )
            connection.execute(
                "UPDATE agent_approvals SET status = 'REJECTED', decided_at = now() "
                "WHERE case_id = %s AND status = 'PENDING'",
                (case_id,),
            )
    return target


async def transition_case(
    case_id: UUID,
    actor_id: UUID,
    target: AgentCaseState,
    termination_reason: AgentTerminationReason | None = None,
) -> AgentCaseState:
    return await asyncio.to_thread(_transition_case, case_id, actor_id, target, termination_reason)


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
    tokens_used, steps_used = _get_case_budget_usage(case_id)
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
        "tokens_used": tokens_used,
        "steps_used": steps_used,
    }


async def get_case_overview(case_id: UUID, actor_id: UUID) -> dict[str, Any] | None:
    return await asyncio.to_thread(_get_case_overview, case_id, actor_id)


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


def _set_goal(case_id: UUID, actor_id: UUID, goal: AgentGoalSpec) -> None:
    with _require_pool().connection() as connection:
        connection.execute(
            "UPDATE agent_cases SET goal = %s::jsonb, updated_at = now(), version = version + 1 "
            "WHERE id = %s AND actor_id = %s",
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
            WHERE id = %s AND actor_id = %s AND goal IS NOT NULL
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


def _create_confirmation(
    case_id: UUID,
    summary: str,
    action_snapshot: dict[str, Any],
    expected_case_version: int,
    ttl_minutes: int,
) -> dict[str, Any]:
    payload = json.dumps(action_snapshot, sort_keys=True, separators=(",", ":"))
    payload_hash = hashlib.sha256(payload.encode()).hexdigest()
    expires_at = datetime.now(UTC) + timedelta(minutes=ttl_minutes)
    with _require_pool().connection() as connection:
        row = connection.execute(
            """
            INSERT INTO agent_confirmations
              (case_id, summary, action_snapshot, payload_hash, expected_case_version, expires_at)
            VALUES (%s, %s, %s::jsonb, %s, %s, %s)
            ON CONFLICT (case_id, payload_hash) WHERE status = 'PENDING'
            DO UPDATE SET summary = EXCLUDED.summary
            RETURNING id, summary, expires_at
            """,
            (case_id, summary, payload, payload_hash, expected_case_version, expires_at),
        ).fetchone()
    if row is None:
        raise RuntimeError("Could not create confirmation")
    return {"id": str(row["id"]), "summary": row["summary"], "expires_at": row["expires_at"]}


async def create_confirmation(
    case_id: UUID,
    summary: str,
    action_snapshot: dict[str, Any],
    expected_case_version: int,
    ttl_minutes: int,
) -> dict[str, Any]:
    return await asyncio.to_thread(
        _create_confirmation, case_id, summary, action_snapshot, expected_case_version, ttl_minutes
    )


def _pending_actions(case_id: UUID) -> dict[str, Any]:
    with _require_pool().connection() as connection:
        confirmation = connection.execute(
            "SELECT id, summary, expires_at FROM agent_confirmations WHERE case_id = %s "
            "AND status = 'PENDING' AND expires_at > now() ORDER BY created_at DESC LIMIT 1",
            (case_id,),
        ).fetchone()
        approval = connection.execute(
            "SELECT id, summary, required_permission, expires_at FROM agent_approvals "
            "WHERE case_id = %s "
            "AND status = 'PENDING' AND expires_at > now() ORDER BY created_at DESC LIMIT 1",
            (case_id,),
        ).fetchone()
    return {
        "confirmation": (
            None
            if confirmation is None
            else {
                "id": str(confirmation["id"]),
                "summary": confirmation["summary"],
                "expires_at": confirmation["expires_at"],
            }
        ),
        "approval": (
            None
            if approval is None
            else {
                "id": str(approval["id"]),
                "summary": approval["summary"],
                "required_permission": approval["required_permission"],
                "expires_at": approval["expires_at"],
            }
        ),
    }


async def pending_actions(case_id: UUID) -> dict[str, Any]:
    return await asyncio.to_thread(_pending_actions, case_id)


def _decide_confirmation(
    confirmation_id: UUID, case_id: UUID, actor_id: UUID, approve: bool, reason: str | None
) -> dict[str, Any] | None:
    with _require_pool().connection() as connection, connection.transaction():
        row = connection.execute(
            "SELECT status, expires_at, action_snapshot, payload_hash, expected_case_version, "
            "decided_by "
            "FROM agent_confirmations "
            "WHERE id = %s AND case_id = %s FOR UPDATE",
            (confirmation_id, case_id),
        ).fetchone()
        if row is None:
            raise LookupError("Confirmation not found")
        expected_status = "CONFIRMED" if approve else "REJECTED"
        if row["status"] == expected_status and row["decided_by"] == actor_id:
            return {
                "action_snapshot": row["action_snapshot"],
                "payload_hash": row["payload_hash"],
                "expected_case_version": row["expected_case_version"],
            }
        if row["status"] != "PENDING":
            return None
        if row["expires_at"] <= datetime.now(UTC):
            connection.execute(
                "UPDATE agent_confirmations SET status = 'EXPIRED', decided_at = now() "
                "WHERE id = %s",
                (confirmation_id,),
            )
            return None
        case = connection.execute(
            "SELECT version FROM agent_cases WHERE id = %s FOR UPDATE", (case_id,)
        ).fetchone()
        if case is None or int(case["version"]) != int(row["expected_case_version"]):
            return None
        connection.execute(
            "UPDATE agent_confirmations SET status = %s, decided_by = %s, "
            "decision_reason = %s, decided_at = now() WHERE id = %s",
            ("CONFIRMED" if approve else "REJECTED", actor_id, reason, confirmation_id),
        )
    return {
        "action_snapshot": row["action_snapshot"],
        "payload_hash": row["payload_hash"],
        "expected_case_version": row["expected_case_version"],
    }


async def decide_confirmation(
    confirmation_id: UUID, case_id: UUID, actor_id: UUID, approve: bool, reason: str | None = None
) -> dict[str, Any] | None:
    return await asyncio.to_thread(
        _decide_confirmation, confirmation_id, case_id, actor_id, approve, reason
    )


def _create_approval(
    case_id: UUID,
    confirmation_id: UUID | None,
    summary: str,
    required_permission: str,
    risk_level: str,
    action_snapshot: dict[str, Any],
    branch_ids: tuple[UUID, ...],
    ttl_hours: int,
) -> dict[str, Any]:
    payload = json.dumps(action_snapshot, sort_keys=True, separators=(",", ":"))
    payload_hash = hashlib.sha256(payload.encode()).hexdigest()
    expires_at = datetime.now(UTC) + timedelta(hours=ttl_hours)
    with _require_pool().connection() as connection:
        row = connection.execute(
            """
            INSERT INTO agent_approvals
              (case_id, confirmation_id, summary, required_permission, risk_level,
               action_snapshot, payload_hash, required_branch_ids, expires_at)
            VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s, %s, %s)
            ON CONFLICT (case_id, payload_hash) WHERE status = 'PENDING'
            DO UPDATE SET summary = EXCLUDED.summary
            RETURNING id, summary, required_permission, expires_at
            """,
            (
                case_id,
                confirmation_id,
                summary,
                required_permission,
                risk_level,
                payload,
                payload_hash,
                list(branch_ids),
                expires_at,
            ),
        ).fetchone()
    if row is None:
        raise RuntimeError("Could not create approval")
    return {
        "id": str(row["id"]),
        "summary": row["summary"],
        "required_permission": row["required_permission"],
        "expires_at": row["expires_at"],
    }


async def create_approval(
    case_id: UUID,
    confirmation_id: UUID | None,
    summary: str,
    required_permission: str,
    risk_level: str,
    action_snapshot: dict[str, Any],
    branch_ids: tuple[UUID, ...],
    ttl_hours: int,
) -> dict[str, Any]:
    return await asyncio.to_thread(
        _create_approval,
        case_id,
        confirmation_id,
        summary,
        required_permission,
        risk_level,
        action_snapshot,
        branch_ids,
        ttl_hours,
    )


def _get_pending_approval(
    approval_id: UUID,
    actor_id: UUID | None = None,
    approve: bool | None = None,
) -> dict[str, Any] | None:
    with _require_pool().connection() as connection:
        row = connection.execute(
            """
            SELECT id, case_id, status, expires_at, required_permission,
                   required_branch_ids, action_snapshot, payload_hash, decided_by
            FROM agent_approvals WHERE id = %s
            """,
            (approval_id,),
        ).fetchone()
        if (
            row is not None
            and row["status"] == "PENDING"
            and row["expires_at"] <= datetime.now(UTC)
        ):
            connection.execute(
                "UPDATE agent_approvals SET status = 'EXPIRED', decided_at = now() WHERE id = %s",
                (approval_id,),
            )
            return None
    resumable_status = None if approve is None else ("APPROVED" if approve else "REJECTED")
    resumable = (
        row is not None
        and actor_id is not None
        and row["status"] == resumable_status
        and row["decided_by"] == actor_id
    )
    if row is None or (row["status"] != "PENDING" and not resumable):
        return None
    return {
        "case_id": UUID(str(row["case_id"])),
        "required_permission": row["required_permission"],
        "required_branch_ids": tuple(UUID(str(value)) for value in row["required_branch_ids"]),
        "action_snapshot": row["action_snapshot"],
        "payload_hash": row["payload_hash"],
    }


async def get_pending_approval(
    approval_id: UUID,
    actor_id: UUID | None = None,
    approve: bool | None = None,
) -> dict[str, Any] | None:
    return await asyncio.to_thread(_get_pending_approval, approval_id, actor_id, approve)


def _decide_approval(
    approval_id: UUID, actor_id: UUID, approve: bool, reason: str | None
) -> dict[str, Any] | None:
    with _require_pool().connection() as connection, connection.transaction():
        row = connection.execute(
            """
            SELECT id, case_id, status, expires_at, required_permission, required_branch_ids,
                   action_snapshot, decided_by
            FROM agent_approvals WHERE id = %s FOR UPDATE
            """,
            (approval_id,),
        ).fetchone()
        expected_status = "APPROVED" if approve else "REJECTED"
        if row is not None and row["status"] == expected_status and row["decided_by"] == actor_id:
            return {
                "case_id": UUID(str(row["case_id"])),
                "required_permission": row["required_permission"],
                "required_branch_ids": tuple(
                    UUID(str(value)) for value in row["required_branch_ids"]
                ),
                "action_snapshot": row["action_snapshot"],
            }
        if row is None or row["status"] != "PENDING":
            return None
        if row["expires_at"] <= datetime.now(UTC):
            connection.execute(
                "UPDATE agent_approvals SET status = 'EXPIRED', decided_at = now() WHERE id = %s",
                (approval_id,),
            )
            return None
        connection.execute(
            "UPDATE agent_approvals SET status = %s, decided_by = %s, decision_reason = %s, "
            "decided_at = now() WHERE id = %s",
            ("APPROVED" if approve else "REJECTED", actor_id, reason, approval_id),
        )
    return {
        "case_id": UUID(str(row["case_id"])),
        "required_permission": row["required_permission"],
        "required_branch_ids": tuple(UUID(str(value)) for value in row["required_branch_ids"]),
        "action_snapshot": row["action_snapshot"],
    }


async def decide_approval(
    approval_id: UUID, actor_id: UUID, approve: bool, reason: str | None = None
) -> dict[str, Any] | None:
    return await asyncio.to_thread(_decide_approval, approval_id, actor_id, approve, reason)
