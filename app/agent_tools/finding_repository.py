"""Persistence operations for proactive findings and reconciliation."""

import asyncio
import base64
import json
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from app.agent_tools.models import (
    AgentCaseOrigin,
    AgentCaseState,
    AgentCaseType,
)
from app.agent_tools.repository_errors import FindingResolutionConflictError
from app.knowledge.repository import _require_pool


def _case_type_for_rule(rule_code: str) -> str:
    if rule_code == "RENTAL_RETURN_OVERDUE":
        return AgentCaseType.RENTAL_RETURN.value
    if rule_code == "OPERATIONAL_CAPACITY_SHORTFALL":
        return AgentCaseType.OPERATIONAL_CAPACITY.value
    return AgentCaseType.RENTAL_READINESS.value


def _upsert_finding(input_data: dict[str, Any]) -> UUID:
    observed_at = input_data.get("observed_at") or datetime.now(UTC)
    candidate_case_id = uuid4()
    with _require_pool().connection() as connection, connection.transaction():
        connection.execute(
            "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
            (input_data["dedupe_key"],),
        )
        existing = connection.execute(
            """
            SELECT case_id, status, source_observed_at
            FROM agent_findings
            WHERE dedupe_key = %s
            ORDER BY source_observed_at DESC, first_detected_at DESC, id DESC
            LIMIT 1
            FOR UPDATE
            """,
            (input_data["dedupe_key"],),
        ).fetchone()
        if existing is not None and observed_at <= existing["source_observed_at"]:
            return UUID(str(existing["case_id"]))

        if existing is not None and existing["status"] == "OPEN":
            case_id = UUID(str(existing["case_id"]))
            connection.execute(
                """
                UPDATE agent_findings
                SET severity = %s, evidence = %s::jsonb, last_detected_at = now(),
                    source_observed_at = %s
                WHERE case_id = %s AND status = 'OPEN'
                """,
                (
                    input_data["severity"],
                    json.dumps(input_data["evidence"], default=str),
                    observed_at,
                    case_id,
                ),
            )
            case = connection.execute(
                "SELECT state FROM agent_cases WHERE id = %s FOR UPDATE", (case_id,)
            ).fetchone()
            if case is None:
                raise RuntimeError("Finding references a missing agent case")
            reanalyze_states = {
                AgentCaseState.PLAN_READY.value,
                AgentCaseState.MONITORING.value,
                AgentCaseState.WAITING_CONFIRMATION.value,
                AgentCaseState.WAITING_APPROVAL.value,
            }
            next_state = (
                AgentCaseState.ANALYZING.value
                if case["state"] in reanalyze_states
                else case["state"]
            )
            connection.execute(
                "UPDATE agent_cases SET deadline_at = %s, state = %s, "
                "updated_at = now(), version = version + 1 WHERE id = %s",
                (input_data["deadline_at"], next_state, case_id),
            )
            # A recommendation is an immutable snapshot. Fresh detector evidence
            # never mutates it; it makes the snapshot visibly stale instead.
            connection.execute(
                "UPDATE agent_case_analyses SET status = 'STALE', invalidated_at = now() "
                "WHERE case_id = %s AND status = 'ACTIVE'",
                (case_id,),
            )
            if case["state"] in reanalyze_states:
                connection.execute(
                    "UPDATE agent_confirmations SET status = 'EXPIRED', decided_at = now() "
                    "WHERE case_id = %s AND status = 'PENDING'",
                    (case_id,),
                )
                connection.execute(
                    "UPDATE agent_approvals SET status = 'EXPIRED', decided_at = now() "
                    "WHERE case_id = %s AND status = 'PENDING'",
                    (case_id,),
                )
            return case_id

        connection.execute(
            """
            INSERT INTO agent_cases
              (id, owner_actor_id, created_by_actor_id, audiences, state, origin, case_type,
               branch_id, deadline_at)
            VALUES (%s, NULL, NULL, %s, %s, %s, %s, %s, %s)
            """,
            (
                candidate_case_id,
                ["staff_internal", "shared"],
                AgentCaseState.NEW.value,
                AgentCaseOrigin.SYSTEM.value,
                _case_type_for_rule(str(input_data["rule_code"])),
                input_data["branch_id"],
                input_data["deadline_at"],
            ),
        )
        finding = connection.execute(
            """
            INSERT INTO agent_findings
              (case_id, rule_code, rule_version, dedupe_key, branch_id, primary_entity_id,
               affected_entity_id, unit_id, window_start, window_end, severity, evidence,
               source_observed_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s)
            RETURNING case_id
            """,
            (
                candidate_case_id,
                input_data["rule_code"],
                input_data["rule_version"],
                input_data["dedupe_key"],
                input_data["branch_id"],
                input_data["primary_entity_id"],
                input_data["affected_entity_id"],
                input_data["unit_id"],
                input_data["window_start"],
                input_data["window_end"],
                input_data["severity"],
                json.dumps(input_data["evidence"], default=str),
                observed_at,
            ),
        ).fetchone()
        if finding is None:
            raise RuntimeError("Could not upsert agent finding")
    return candidate_case_id


async def upsert_finding(input_data: dict[str, Any]) -> UUID:
    return await asyncio.to_thread(_upsert_finding, input_data)


def _decode_finding_cursor(cursor: str) -> tuple[datetime, UUID]:
    try:
        padding = "=" * (-len(cursor) % 4)
        payload = json.loads(base64.urlsafe_b64decode(cursor + padding).decode("utf-8"))
        observed_at = datetime.fromisoformat(payload["firstDetectedAt"])
        finding_id = UUID(payload["findingId"])
        if observed_at.tzinfo is None or observed_at.utcoffset() is None:
            raise ValueError("Cursor timestamp has no timezone")
        return observed_at, finding_id
    except (KeyError, TypeError, ValueError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("Invalid finding-list cursor") from error


def _encode_finding_cursor(row: dict[str, Any]) -> str:
    payload = json.dumps(
        {
            "firstDetectedAt": row["first_detected_at"].isoformat(),
            "findingId": str(row["finding_id"]),
        },
        separators=(",", ":"),
    ).encode("utf-8")
    return base64.urlsafe_b64encode(payload).decode("ascii").rstrip("=")


def _list_findings(
    rule_code: str,
    status: str,
    cursor: str | None,
    limit: int,
) -> tuple[list[dict[str, Any]], str | None]:
    parameters: list[Any] = [rule_code, status]
    cursor_filter = ""
    if cursor is not None:
        cursor_detected_at, cursor_id = _decode_finding_cursor(cursor)
        cursor_filter = "AND (first_detected_at, id) > (%s, %s)"
        parameters.extend((cursor_detected_at, cursor_id))
    parameters.append(limit + 1)
    with _require_pool().connection() as connection:
        rows = connection.execute(
            f"""
            SELECT id AS finding_id, case_id, branch_id, rule_code, rule_version,
                   dedupe_key, primary_entity_id, affected_entity_id, unit_id,
                   window_start, window_end, severity, status, evidence,
                   first_detected_at, last_detected_at, source_observed_at, resolved_at
            FROM agent_findings
            WHERE rule_code = %s AND status = %s
              {cursor_filter}
            ORDER BY first_detected_at ASC, id ASC
            LIMIT %s
            """,
            tuple(parameters),
        ).fetchall()
    page = rows[:limit]
    items = [dict(row) for row in page]
    next_cursor = _encode_finding_cursor(items[-1]) if len(rows) > limit and items else None
    return items, next_cursor


async def list_findings(
    rule_code: str,
    status: str,
    cursor: str | None,
    limit: int,
) -> tuple[list[dict[str, Any]], str | None]:
    return await asyncio.to_thread(_list_findings, rule_code, status, cursor, limit)


def _resolve_finding(input_data: dict[str, Any]) -> dict[str, Any]:
    observed_at = input_data["observed_at"]
    with _require_pool().connection() as connection, connection.transaction():
        connection.execute(
            "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
            (input_data["dedupe_key"],),
        )
        finding = connection.execute(
            """
            SELECT id, case_id, status, evidence, source_observed_at
            FROM agent_findings
            WHERE dedupe_key = %s AND rule_code = %s
            ORDER BY source_observed_at DESC, first_detected_at DESC, id DESC
            LIMIT 1
            FOR UPDATE
            """,
            (input_data["dedupe_key"], input_data["rule_code"]),
        ).fetchone()
        if finding is None:
            raise LookupError("Agent finding not found")
        result = {
            "case_id": finding["case_id"],
            "dedupe_key": input_data["dedupe_key"],
            "source_observed_at": finding["source_observed_at"],
        }
        if observed_at < finding["source_observed_at"]:
            return {**result, "outcome": "STALE"}
        if finding["status"] == "RESOLVED":
            evidence = dict(finding["evidence"] or {})
            evidence["resolution"] = {
                "code": input_data["resolution_code"],
                "evidence": input_data["evidence"],
                "observedAt": observed_at.isoformat(),
            }
            connection.execute(
                """
                UPDATE agent_findings
                SET evidence = %s::jsonb, source_observed_at = %s
                WHERE id = %s
                """,
                (json.dumps(evidence, default=str), observed_at, finding["id"]),
            )
            return {
                **result,
                "outcome": "ALREADY_RESOLVED",
                "source_observed_at": observed_at,
            }

        case = connection.execute(
            """
            SELECT state, active_run_id, active_run_deadline
            FROM agent_cases WHERE id = %s FOR UPDATE
            """,
            (finding["case_id"],),
        ).fetchone()
        if case is None:
            raise RuntimeError("Finding references a missing agent case")
        active_run_id = case["active_run_id"]
        active_run_deadline = case["active_run_deadline"]
        live_run = active_run_id is not None and (
            active_run_deadline is None or active_run_deadline > datetime.now(UTC)
        )
        if case["state"] == AgentCaseState.EXECUTING.value or live_run:
            raise FindingResolutionConflictError(
                "Agent finding cannot be resolved while the case has active execution"
            )
        if active_run_id is not None:
            connection.execute(
                """
                UPDATE agent_runs
                SET status = 'FAILED', error_code = 'RUN_DEADLINE_EXPIRED', completed_at = now()
                WHERE id = %s AND status = 'RUNNING'
                """,
                (active_run_id,),
            )
            connection.execute(
                """
                UPDATE agent_cases
                SET active_run_id = NULL, active_run_deadline = NULL,
                    last_run_status = 'FAILED', updated_at = now()
                WHERE id = %s AND active_run_id = %s
                """,
                (finding["case_id"], active_run_id),
            )

        evidence = dict(finding["evidence"] or {})
        evidence["resolution"] = {
            "code": input_data["resolution_code"],
            "evidence": input_data["evidence"],
            "observedAt": observed_at.isoformat(),
        }
        connection.execute(
            """
            UPDATE agent_findings
            SET status = 'RESOLVED', evidence = %s::jsonb, resolved_at = now(),
                source_observed_at = %s
            WHERE id = %s
            """,
            (json.dumps(evidence, default=str), observed_at, finding["id"]),
        )
        terminal_states = {
            AgentCaseState.SUCCEEDED.value,
            AgentCaseState.INSUFFICIENT_DATA.value,
            AgentCaseState.HANDED_OFF.value,
            AgentCaseState.FAILED.value,
            AgentCaseState.CANCELLED.value,
        }
        if case["state"] not in terminal_states:
            connection.execute(
                """
                UPDATE agent_cases
                SET state = 'SUCCEEDED', completed_at = now(), updated_at = now(),
                    version = version + 1, active_run_id = NULL, active_run_deadline = NULL
                WHERE id = %s
                """,
                (finding["case_id"],),
            )
            connection.execute(
                "UPDATE agent_confirmations SET status = 'EXPIRED', decided_at = now() "
                "WHERE case_id = %s AND status = 'PENDING'",
                (finding["case_id"],),
            )
            connection.execute(
                "UPDATE agent_approvals SET status = 'EXPIRED', decided_at = now() "
                "WHERE case_id = %s AND status = 'PENDING'",
                (finding["case_id"],),
            )
        connection.execute(
            "UPDATE agent_case_analyses SET status = 'STALE', invalidated_at = now() "
            "WHERE case_id = %s AND status = 'ACTIVE'",
            (finding["case_id"],),
        )
        return {
            **result,
            "outcome": "RESOLVED",
            "source_observed_at": observed_at,
        }


async def resolve_finding(input_data: dict[str, Any]) -> dict[str, Any]:
    return await asyncio.to_thread(_resolve_finding, input_data)
