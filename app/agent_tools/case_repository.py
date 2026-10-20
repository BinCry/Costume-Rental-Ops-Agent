"""Persistence operations for agent cases and the operational branch queue."""

import asyncio
from datetime import datetime
from typing import Any
from uuid import UUID

from app.agent_tools.models import (
    OPERATIONAL_CASE_TYPES,
    AgentCaseOrigin,
    AgentCaseState,
    AgentCaseType,
    AgentTerminationReason,
)
from app.agent_tools.repository_errors import (
    CaseAlreadyClaimedError,
    CaseReleaseForbiddenError,
    CaseVersionConflictError,
)
from app.agent_tools.run_repository import _get_case_budget_usage
from app.agent_tools.state import require_transition
from app.knowledge.repository import _require_pool


def _case_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(row["id"]),
        "actor_id": str(row["owner_actor_id"]) if row.get("owner_actor_id") else None,
        "owner_actor_id": (str(row["owner_actor_id"]) if row.get("owner_actor_id") else None),
        "created_by_actor_id": (
            str(row["created_by_actor_id"]) if row.get("created_by_actor_id") else None
        ),
        "origin": row.get("origin", AgentCaseOrigin.USER.value),
        "case_type": row.get("case_type", AgentCaseType.INTERACTIVE.value),
        "branch_id": str(row["branch_id"]) if row.get("branch_id") else None,
        "claimed_at": row.get("claimed_at"),
        "deadline_at": row.get("deadline_at"),
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


def _create_case(actor_id: UUID, audiences: tuple[str, ...], branch_id: UUID) -> dict[str, Any]:
    with _require_pool().connection() as connection:
        row = connection.execute(
            """
            INSERT INTO agent_cases
              (owner_actor_id, created_by_actor_id, audiences, state, origin, case_type, branch_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING id, owner_actor_id, created_by_actor_id, origin, case_type, branch_id,
              claimed_at, deadline_at, audiences, state, created_at, updated_at, completed_at,
              goal, version, termination_reason, last_run_status, active_run_id, active_run_deadline
            """,
            (
                actor_id,
                actor_id,
                list(audiences),
                AgentCaseState.NEW.value,
                AgentCaseOrigin.USER.value,
                AgentCaseType.INTERACTIVE.value,
                branch_id,
            ),
        ).fetchone()
    if row is None:
        raise RuntimeError("Could not create agent case")
    return _case_row(row)


async def create_case(
    actor_id: UUID, audiences: tuple[str, ...], branch_id: UUID
) -> dict[str, Any]:
    return await asyncio.to_thread(_create_case, actor_id, audiences, branch_id)


def _get_case(case_id: UUID, actor_id: UUID) -> dict[str, Any] | None:
    with _require_pool().connection() as connection:
        row = connection.execute(
            """
            SELECT id, owner_actor_id, created_by_actor_id, origin, case_type, branch_id,
              claimed_at, deadline_at, audiences, state, created_at, updated_at, completed_at,
              goal, version, termination_reason, last_run_status, active_run_id, active_run_deadline
            FROM agent_cases
            WHERE id = %s AND owner_actor_id = %s
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
            SELECT id, owner_actor_id, created_by_actor_id, origin, case_type, branch_id,
              claimed_at, deadline_at, audiences, state, created_at, updated_at, completed_at,
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
            "SELECT state FROM agent_cases WHERE id = %s AND owner_actor_id = %s FOR UPDATE",
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
        if target is AgentCaseState.ANALYZING and current in {
            AgentCaseState.MONITORING,
            AgentCaseState.WAITING_CONFIRMATION,
            AgentCaseState.WAITING_APPROVAL,
        }:
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
    return _enrich_case_overview(case_id, case)


def _enrich_case_overview(case_id: UUID, case: dict[str, Any]) -> dict[str, Any]:
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
        finding = connection.execute(
            """
            SELECT id, rule_code, rule_version, dedupe_key, primary_entity_id,
                   affected_entity_id, unit_id, window_start, window_end, severity,
                   status, evidence, first_detected_at, last_detected_at,
                   source_observed_at, resolved_at
            FROM agent_findings WHERE case_id = %s
            """,
            (case_id,),
        ).fetchone()
        analysis = connection.execute(
            """
            SELECT id, status, outcome, finding_source_observed_at, simulator_version,
                   ranking_policy_version, snapshot, options, recommended_option_id,
                   narrative, created_at
            FROM agent_case_analyses
            WHERE case_id = %s
            ORDER BY CASE WHEN status = 'ACTIVE' THEN 0 ELSE 1 END, created_at DESC LIMIT 1
            """,
            (case_id,),
        ).fetchone()
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
        "finding": (
            None
            if finding is None
            else {
                "finding_id": str(finding["id"]),
                "rule_code": finding["rule_code"],
                "rule_version": finding["rule_version"],
                "dedupe_key": finding["dedupe_key"],
                "primary_entity_id": str(finding["primary_entity_id"]),
                "affected_entity_id": (
                    str(finding["affected_entity_id"])
                    if finding["affected_entity_id"] is not None
                    else None
                ),
                "unit_id": str(finding["unit_id"]) if finding["unit_id"] is not None else None,
                "window_start": finding["window_start"],
                "window_end": finding["window_end"],
                "severity": finding["severity"],
                "status": finding["status"],
                "evidence": finding["evidence"],
                "first_detected_at": finding["first_detected_at"],
                "last_detected_at": finding["last_detected_at"],
                "source_observed_at": finding["source_observed_at"],
                "resolved_at": finding["resolved_at"],
            }
        ),
        "analysis": (
            None
            if analysis is None
            else {
                "analysis_id": str(analysis["id"]),
                "status": analysis["status"],
                "outcome": analysis["outcome"],
                "observed_at": analysis["created_at"],
                "source_observed_at": analysis["finding_source_observed_at"],
                "simulator_version": analysis["simulator_version"],
                "ranking_policy_version": analysis["ranking_policy_version"],
                "before": (analysis["snapshot"] or {}).get("before", {}),
                "options": analysis["options"] or [],
                "recommended_option_id": analysis["recommended_option_id"],
                "narrative": analysis["narrative"] or {},
            }
        ),
    }


async def get_case_overview(case_id: UUID, actor_id: UUID) -> dict[str, Any] | None:
    return await asyncio.to_thread(_get_case_overview, case_id, actor_id)


def _get_case_overview_by_id(case_id: UUID) -> dict[str, Any] | None:
    case = _get_case_by_id(case_id)
    return None if case is None else _enrich_case_overview(case_id, case)


async def get_case_overview_by_id(case_id: UUID) -> dict[str, Any] | None:
    return await asyncio.to_thread(_get_case_overview_by_id, case_id)


def _list_operational_cases(
    branch_ids: tuple[UUID, ...] | None,
    branch_id: UUID | None,
    state: AgentCaseState | None,
    ownership: str,
    actor_id: UUID,
    cursor: str | None,
    limit: int,
) -> tuple[list[dict[str, Any]], str | None]:
    offset = 0
    if cursor is not None:
        try:
            offset = int(cursor)
        except ValueError as error:
            raise ValueError("Invalid case-list cursor") from error
        if offset < 0:
            raise ValueError("Invalid case-list cursor")
    filters = ["case_type = ANY(%s)"]
    parameters: list[Any] = [list(OPERATIONAL_CASE_TYPES)]
    if branch_ids is not None:
        if not branch_ids:
            return [], None
        filters.append("branch_id = ANY(%s)")
        parameters.append(list(branch_ids))
    if branch_id is not None:
        filters.append("branch_id = %s")
        parameters.append(branch_id)
    if state is not None:
        filters.append("state = %s")
        parameters.append(state.value)
    if ownership == "unassigned":
        filters.append("owner_actor_id IS NULL")
    elif ownership == "mine":
        filters.append("owner_actor_id = %s")
        parameters.append(actor_id)
    parameters.extend((limit + 1, offset))
    with _require_pool().connection() as connection:
        rows = connection.execute(
            f"""
            SELECT id, owner_actor_id, created_by_actor_id, origin, case_type, branch_id,
                   claimed_at, deadline_at, audiences, state, created_at, updated_at,
                   completed_at, goal, version, termination_reason, last_run_status,
                   active_run_id, active_run_deadline
            FROM agent_cases
            WHERE {" AND ".join(filters)}
            ORDER BY deadline_at ASC NULLS LAST, updated_at DESC, id ASC
            LIMIT %s OFFSET %s
            """,
            tuple(parameters),
        ).fetchall()
    page = rows[:limit]
    items = [_enrich_case_overview(UUID(str(row["id"])), _case_row(row)) for row in page]
    next_cursor = str(offset + limit) if len(rows) > limit else None
    return items, next_cursor


async def list_operational_cases(
    branch_ids: tuple[UUID, ...] | None,
    branch_id: UUID | None,
    state: AgentCaseState | None,
    ownership: str,
    actor_id: UUID,
    cursor: str | None,
    limit: int,
) -> tuple[list[dict[str, Any]], str | None]:
    return await asyncio.to_thread(
        _list_operational_cases,
        branch_ids,
        branch_id,
        state,
        ownership,
        actor_id,
        cursor,
        limit,
    )


def _claim_case(case_id: UUID, actor_id: UUID, expected_version: int) -> dict[str, Any]:
    with _require_pool().connection() as connection, connection.transaction():
        row = connection.execute(
            "SELECT owner_actor_id, version, case_type FROM agent_cases WHERE id = %s FOR UPDATE",
            (case_id,),
        ).fetchone()
        if row is None:
            raise LookupError("Agent case not found")
        if row["case_type"] not in OPERATIONAL_CASE_TYPES:
            raise CaseReleaseForbiddenError("Interactive cases cannot be claimed")
        owner = row["owner_actor_id"]
        owned_by_actor = owner is not None and UUID(str(owner)) == actor_id
        if owner is not None and not owned_by_actor:
            raise CaseAlreadyClaimedError("Agent case is already claimed")
        if not owned_by_actor:
            if int(row["version"]) != expected_version:
                raise CaseVersionConflictError("Agent case version changed")
            connection.execute(
                "UPDATE agent_cases SET owner_actor_id = %s, claimed_at = now(), "
                "updated_at = now(), version = version + 1 WHERE id = %s",
                (actor_id, case_id),
            )
    case = _get_case_by_id(case_id)
    if case is None:
        raise LookupError("Agent case not found")
    return case


async def claim_case(case_id: UUID, actor_id: UUID, expected_version: int) -> dict[str, Any]:
    return await asyncio.to_thread(_claim_case, case_id, actor_id, expected_version)


def _release_case(case_id: UUID, actor_id: UUID, expected_version: int) -> dict[str, Any]:
    terminal = {
        AgentCaseState.SUCCEEDED.value,
        AgentCaseState.INSUFFICIENT_DATA.value,
        AgentCaseState.HANDED_OFF.value,
        AgentCaseState.FAILED.value,
        AgentCaseState.CANCELLED.value,
    }
    with _require_pool().connection() as connection, connection.transaction():
        row = connection.execute(
            "SELECT owner_actor_id, version, state, case_type FROM agent_cases "
            "WHERE id = %s FOR UPDATE",
            (case_id,),
        ).fetchone()
        if row is None:
            raise LookupError("Agent case not found")
        if row["case_type"] not in OPERATIONAL_CASE_TYPES:
            raise CaseReleaseForbiddenError("Interactive cases cannot be released")
        if row["owner_actor_id"] is None or UUID(str(row["owner_actor_id"])) != actor_id:
            raise CaseAlreadyClaimedError("Only the current owner can release this case")
        if int(row["version"]) != expected_version:
            raise CaseVersionConflictError("Agent case version changed")
        if row["state"] == AgentCaseState.EXECUTING.value or row["state"] in terminal:
            raise CaseReleaseForbiddenError("Agent case cannot be released in its current state")
        connection.execute(
            "UPDATE agent_cases SET owner_actor_id = NULL, claimed_at = NULL, "
            "updated_at = now(), version = version + 1 WHERE id = %s",
            (case_id,),
        )
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
    case = _get_case_by_id(case_id)
    if case is None:
        raise LookupError("Agent case not found")
    return case


async def release_case(case_id: UUID, actor_id: UUID, expected_version: int) -> dict[str, Any]:
    return await asyncio.to_thread(_release_case, case_id, actor_id, expected_version)
