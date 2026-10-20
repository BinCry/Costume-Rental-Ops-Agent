"""Persistence operations for generic confirmations and approvals."""

import asyncio
import hashlib
import json
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from app.knowledge.repository import _require_pool


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
            "SELECT id, summary, expires_at, analysis_id, option_id, "
            "prepared_from_case_version, action_snapshot "
            "FROM agent_confirmations WHERE case_id = %s "
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
                "analysis_id": (
                    str(confirmation["analysis_id"]) if confirmation["analysis_id"] else None
                ),
                "option_id": confirmation["option_id"],
                "prepared_from_case_version": confirmation["prepared_from_case_version"],
                "action": (
                    confirmation["action_snapshot"]
                    if confirmation["analysis_id"] is not None
                    else None
                ),
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
        # Always lock the case before its pending decisions. Finding refresh,
        # release, and lifecycle transitions use the same order.
        case = connection.execute(
            "SELECT version FROM agent_cases WHERE id = %s FOR UPDATE", (case_id,)
        ).fetchone()
        if case is None:
            raise LookupError("Agent case not found")
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
        if int(case["version"]) != int(row["expected_case_version"]):
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
