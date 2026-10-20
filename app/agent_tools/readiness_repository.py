"""Persistence operations for rental-readiness analysis and execution."""

import asyncio
import hashlib
import json
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

from app.agent_tools.models import (
    OPERATIONAL_CASE_TYPES,
    AgentCaseState,
    AgentCaseType,
)
from app.agent_tools.repository_errors import (
    AnalysisForbiddenError,
    AnalysisStaleError,
    CaseVersionConflictError,
    ReadinessConfirmationError,
)
from app.agent_tools.state import require_transition
from app.knowledge.repository import _require_pool


def _begin_readiness_analysis(
    case_id: UUID, actor_id: UUID, expected_version: int
) -> dict[str, Any]:
    with _require_pool().connection() as connection, connection.transaction():
        case = connection.execute(
            """
            SELECT id, owner_actor_id, case_type, state, version
            FROM agent_cases WHERE id = %s FOR UPDATE
            """,
            (case_id,),
        ).fetchone()
        if case is None or case["case_type"] not in OPERATIONAL_CASE_TYPES:
            raise LookupError("Agent case not found")
        if case["owner_actor_id"] != actor_id:
            raise AnalysisForbiddenError("Agent case must be claimed by the current actor")
        if int(case["version"]) != expected_version:
            raise CaseVersionConflictError("Agent case version is stale")
        if case["state"] not in {
            AgentCaseState.NEW.value,
            AgentCaseState.ANALYZING.value,
            AgentCaseState.PLAN_READY.value,
            AgentCaseState.MONITORING.value,
        }:
            raise AnalysisForbiddenError("Agent case cannot be analyzed in its current state")
        finding = connection.execute(
            """
            SELECT id, rule_code, dedupe_key, source_observed_at, status, primary_entity_id,
                   affected_entity_id, unit_id, window_start, window_end
            FROM agent_findings WHERE case_id = %s FOR UPDATE
            """,
            (case_id,),
        ).fetchone()
        if finding is None or finding["status"] != "OPEN":
            raise AnalysisForbiddenError("Agent finding is not open")
        if case["state"] != AgentCaseState.ANALYZING.value:
            require_transition(AgentCaseState(case["state"]), AgentCaseState.ANALYZING)
            if case["state"] in {
                AgentCaseState.PLAN_READY.value,
                AgentCaseState.MONITORING.value,
            }:
                connection.execute(
                    "UPDATE agent_case_analyses SET status = 'STALE', invalidated_at = now() "
                    "WHERE case_id = %s AND status = 'ACTIVE'",
                    (case_id,),
                )
            case = connection.execute(
                """
                UPDATE agent_cases
                SET state = 'ANALYZING', updated_at = now(), version = version + 1
                WHERE id = %s
                RETURNING version
                """,
                (case_id,),
            ).fetchone()
        return {
            "case_version": int(case["version"]),
            "finding_id": UUID(str(finding["id"])),
            "rule_code": str(finding["rule_code"]),
            "dedupe_key": str(finding["dedupe_key"]),
            "source_observed_at": finding["source_observed_at"],
            "primary_entity_id": str(finding["primary_entity_id"]),
            "affected_entity_id": (
                str(finding["affected_entity_id"])
                if finding["affected_entity_id"] is not None
                else None
            ),
            "unit_id": str(finding["unit_id"]) if finding["unit_id"] is not None else None,
            "window_start": finding["window_start"],
            "window_end": finding["window_end"],
        }


async def begin_readiness_analysis(
    case_id: UUID, actor_id: UUID, expected_version: int
) -> dict[str, Any]:
    return await asyncio.to_thread(_begin_readiness_analysis, case_id, actor_id, expected_version)


def _finalize_readiness_analysis(
    *,
    case_id: UUID,
    actor_id: UUID,
    case_version_at_start: int,
    finding_id: UUID,
    finding_source_observed_at: datetime,
    snapshot: dict[str, Any],
    options: list[dict[str, Any]],
    recommended_option_id: str | None,
    outcome: str,
    narrative: dict[str, Any],
    simulator_version: str = "rental-readiness/v1",
    ranking_policy_version: str = "same-branch/v1",
) -> UUID:
    analysis_id = uuid4()
    with _require_pool().connection() as connection, connection.transaction():
        case = connection.execute(
            "SELECT owner_actor_id, state, version FROM agent_cases WHERE id = %s FOR UPDATE",
            (case_id,),
        ).fetchone()
        finding = connection.execute(
            "SELECT source_observed_at, status FROM agent_findings WHERE id = %s FOR UPDATE",
            (finding_id,),
        ).fetchone()
        if case is None or finding is None:
            raise AnalysisStaleError("Agent case or finding no longer exists")
        if case["owner_actor_id"] != actor_id:
            raise AnalysisStaleError("Agent case ownership changed")
        if (
            finding["status"] != "OPEN"
            or finding["source_observed_at"] != finding_source_observed_at
        ):
            raise AnalysisStaleError("Agent finding changed during analysis")
        if int(case["version"]) != case_version_at_start:
            raise AnalysisStaleError("Agent case changed during analysis")
        if case["state"] != AgentCaseState.ANALYZING.value:
            raise AnalysisStaleError("Agent case is no longer analyzing")
        connection.execute(
            "UPDATE agent_case_analyses SET status = 'STALE', invalidated_at = now() "
            "WHERE case_id = %s AND status = 'ACTIVE'",
            (case_id,),
        )
        connection.execute(
            """
            INSERT INTO agent_case_analyses
              (id, case_id, finding_id, created_by_actor_id, case_version_at_start,
               finding_source_observed_at, simulator_version, ranking_policy_version,
               status, outcome, snapshot, options, recommended_option_id, narrative)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s,
                    'ACTIVE', %s, %s::jsonb, %s::jsonb, %s, %s::jsonb)
            """,
            (
                analysis_id,
                case_id,
                finding_id,
                actor_id,
                case_version_at_start,
                finding_source_observed_at,
                simulator_version,
                ranking_policy_version,
                outcome,
                json.dumps(snapshot, default=str),
                json.dumps(options, default=str),
                recommended_option_id,
                json.dumps(narrative, default=str),
            ),
        )
        connection.execute(
            "UPDATE agent_cases SET state = 'PLAN_READY', updated_at = now(), "
            "version = version + 1 "
            "WHERE id = %s",
            (case_id,),
        )
    return analysis_id


async def finalize_readiness_analysis(**kwargs: Any) -> UUID:
    return await asyncio.to_thread(_finalize_readiness_analysis, **kwargs)


def _create_readiness_confirmation(
    *,
    case_id: UUID,
    actor_id: UUID,
    analysis_id: UUID,
    option_id: str,
    expected_version: int,
    summary: str,
    action_snapshot: dict[str, Any],
    ttl_minutes: int,
) -> dict[str, Any]:
    payload = json.dumps(action_snapshot, sort_keys=True, separators=(",", ":"))
    payload_hash = hashlib.sha256(payload.encode()).hexdigest()
    expires_at = datetime.now(UTC) + timedelta(minutes=ttl_minutes)
    with _require_pool().connection() as connection, connection.transaction():
        case = connection.execute(
            "SELECT owner_actor_id, case_type, state, version FROM agent_cases "
            "WHERE id = %s FOR UPDATE",
            (case_id,),
        ).fetchone()
        if case is None:
            raise LookupError("Agent case not found")
        if case["owner_actor_id"] != actor_id:
            raise ReadinessConfirmationError("Agent case must be claimed by the current actor")
        if case["case_type"] != AgentCaseType.RENTAL_READINESS.value:
            raise ReadinessConfirmationError("Agent case is not a rental readiness case")
        existing = connection.execute(
            """
            SELECT id, summary, expires_at, action_snapshot
            FROM agent_confirmations
            WHERE case_id = %s AND analysis_id = %s AND option_id = %s
              AND prepared_from_case_version = %s AND status = 'PENDING'
            FOR UPDATE
            """,
            (case_id, analysis_id, option_id, expected_version),
        ).fetchone()
        if existing is not None:
            return {
                "id": str(existing["id"]),
                "summary": existing["summary"],
                "expires_at": existing["expires_at"],
                "action": existing["action_snapshot"],
                "idempotent": True,
            }
        if int(case["version"]) != expected_version:
            raise CaseVersionConflictError("Agent case version is stale")
        if case["state"] != AgentCaseState.PLAN_READY.value:
            raise ReadinessConfirmationError("Agent case is not ready for confirmation")
        analysis = connection.execute(
            """
            SELECT id, finding_id, status, outcome, recommended_option_id
            FROM agent_case_analyses WHERE id = %s AND case_id = %s FOR UPDATE
            """,
            (analysis_id, case_id),
        ).fetchone()
        if (
            analysis is None
            or analysis["status"] != "ACTIVE"
            or analysis["outcome"] != "READY"
            or analysis["recommended_option_id"] != option_id
        ):
            raise ReadinessConfirmationError("Recommendation is no longer actionable")
        finding = connection.execute(
            "SELECT status FROM agent_findings WHERE id = %s FOR UPDATE",
            (analysis["finding_id"],),
        ).fetchone()
        if finding is None or finding["status"] != "OPEN":
            raise ReadinessConfirmationError("Agent finding is not open")
        next_version = int(case["version"]) + 1
        row = connection.execute(
            """
            INSERT INTO agent_confirmations
              (case_id, summary, action_snapshot, payload_hash, expected_case_version, expires_at,
               analysis_id, option_id, prepared_from_case_version)
            VALUES (%s, %s, %s::jsonb, %s, %s, %s, %s, %s, %s)
            RETURNING id, summary, expires_at, action_snapshot
            """,
            (
                case_id,
                summary,
                payload,
                payload_hash,
                next_version,
                expires_at,
                analysis_id,
                option_id,
                expected_version,
            ),
        ).fetchone()
        connection.execute(
            "UPDATE agent_cases SET state = 'WAITING_CONFIRMATION', version = version + 1, "
            "updated_at = now() WHERE id = %s",
            (case_id,),
        )
    if row is None:
        raise RuntimeError("Could not create readiness confirmation")
    return {
        "id": str(row["id"]),
        "summary": row["summary"],
        "expires_at": row["expires_at"],
        "action": row["action_snapshot"],
        "idempotent": False,
    }


async def create_readiness_confirmation(**kwargs: Any) -> dict[str, Any]:
    return await asyncio.to_thread(_create_readiness_confirmation, **kwargs)


def _decide_readiness_confirmation(
    *, case_id: UUID, confirmation_id: UUID, actor_id: UUID, approve: bool, reason: str | None
) -> dict[str, Any]:
    """Atomically decide an operational confirmation and move its case.

    This deliberately does not reuse the generic decision helper: rejecting a
    readiness recommendation leaves the risk open and returns to PLAN_READY.
    """
    with _require_pool().connection() as connection, connection.transaction():
        case = connection.execute(
            "SELECT owner_actor_id, case_type, state, version FROM agent_cases "
            "WHERE id = %s FOR UPDATE",
            (case_id,),
        ).fetchone()
        if case is None:
            raise LookupError("Agent case not found")
        if case["owner_actor_id"] != actor_id:
            raise ReadinessConfirmationError("Agent case must be claimed by the current actor")
        if case["case_type"] != AgentCaseType.RENTAL_READINESS.value:
            raise ReadinessConfirmationError("Agent case is not a rental readiness case")
        confirmation = connection.execute(
            """
            SELECT status, expires_at, action_snapshot, payload_hash, expected_case_version,
                   decided_by, analysis_id, option_id
            FROM agent_confirmations WHERE id = %s AND case_id = %s FOR UPDATE
            """,
            (confirmation_id, case_id),
        ).fetchone()
        if confirmation is None or confirmation["analysis_id"] is None:
            raise LookupError("Readiness confirmation not found")
        expected_status = "CONFIRMED" if approve else "REJECTED"
        if confirmation["status"] == expected_status and confirmation["decided_by"] == actor_id:
            return {
                "action_snapshot": confirmation["action_snapshot"],
                "payload_hash": confirmation["payload_hash"],
                "idempotent": True,
                "state": case["state"],
            }
        if confirmation["status"] != "PENDING":
            raise ReadinessConfirmationError("Confirmation is no longer pending")
        if confirmation["expires_at"] <= datetime.now(UTC):
            connection.execute(
                "UPDATE agent_confirmations SET status = 'EXPIRED', decided_at = now() "
                "WHERE id = %s",
                (confirmation_id,),
            )
            raise ReadinessConfirmationError("Confirmation is no longer pending")
        if case["state"] != AgentCaseState.WAITING_CONFIRMATION.value:
            raise ReadinessConfirmationError("Case is not waiting for confirmation")
        if int(case["version"]) != int(confirmation["expected_case_version"]):
            raise ReadinessConfirmationError("Confirmation snapshot is stale")
        connection.execute(
            "UPDATE agent_confirmations SET status = %s, decided_by = %s, decision_reason = %s, "
            "decided_at = now() WHERE id = %s",
            (expected_status, actor_id, reason, confirmation_id),
        )
        if approve:
            connection.execute(
                "UPDATE agent_cases SET state = 'EXECUTING', version = version + 1, "
                "updated_at = now() "
                "WHERE id = %s",
                (case_id,),
            )
        else:
            connection.execute(
                "UPDATE agent_cases SET state = 'PLAN_READY', version = version + 1, "
                "updated_at = now() "
                "WHERE id = %s",
                (case_id,),
            )
    return {
        "action_snapshot": confirmation["action_snapshot"],
        "payload_hash": confirmation["payload_hash"],
        "idempotent": False,
        "state": "EXECUTING" if approve else "PLAN_READY",
    }


async def decide_readiness_confirmation(**kwargs: Any) -> dict[str, Any]:
    return await asyncio.to_thread(_decide_readiness_confirmation, **kwargs)


def _create_overdue_follow_up_confirmation(
    *,
    case_id: UUID,
    actor_id: UUID,
    analysis_id: UUID,
    option_id: str,
    expected_version: int,
    summary: str,
    action_snapshot: dict[str, Any],
    ttl_minutes: int,
) -> dict[str, Any]:
    payload = json.dumps(action_snapshot, sort_keys=True, separators=(",", ":"))
    payload_hash = hashlib.sha256(payload.encode()).hexdigest()
    expires_at = datetime.now(UTC) + timedelta(minutes=ttl_minutes)
    with _require_pool().connection() as connection, connection.transaction():
        case = connection.execute(
            "SELECT owner_actor_id, case_type, state, version FROM agent_cases "
            "WHERE id = %s FOR UPDATE",
            (case_id,),
        ).fetchone()
        if case is None:
            raise LookupError("Agent case not found")
        if case["owner_actor_id"] != actor_id:
            raise ReadinessConfirmationError("Agent case must be claimed by the current actor")
        if case["case_type"] != AgentCaseType.RENTAL_RETURN.value:
            raise ReadinessConfirmationError("Agent case is not an overdue-return case")
        existing = connection.execute(
            """
            SELECT id, summary, expires_at, action_snapshot
            FROM agent_confirmations
            WHERE case_id = %s AND analysis_id = %s AND option_id = %s
              AND prepared_from_case_version = %s AND status = 'PENDING'
            FOR UPDATE
            """,
            (case_id, analysis_id, option_id, expected_version),
        ).fetchone()
        if existing is not None:
            return {
                "id": str(existing["id"]),
                "summary": existing["summary"],
                "expires_at": existing["expires_at"],
                "action": existing["action_snapshot"],
                "idempotent": True,
            }
        if int(case["version"]) != expected_version:
            raise CaseVersionConflictError("Agent case version is stale")
        if case["state"] != AgentCaseState.PLAN_READY.value:
            raise ReadinessConfirmationError("Agent case is not ready for confirmation")
        analysis = connection.execute(
            """
            SELECT id, finding_id, status, outcome
            FROM agent_case_analyses WHERE id = %s AND case_id = %s FOR UPDATE
            """,
            (analysis_id, case_id),
        ).fetchone()
        if analysis is None or analysis["status"] != "ACTIVE" or analysis["outcome"] != "READY":
            raise ReadinessConfirmationError("Overdue-return analysis is no longer actionable")
        finding = connection.execute(
            "SELECT status, rule_code FROM agent_findings WHERE id = %s FOR UPDATE",
            (analysis["finding_id"],),
        ).fetchone()
        if (
            finding is None
            or finding["status"] != "OPEN"
            or finding["rule_code"] != "RENTAL_RETURN_OVERDUE"
        ):
            raise ReadinessConfirmationError("Overdue-return finding is not open")
        next_version = int(case["version"]) + 1
        row = connection.execute(
            """
            INSERT INTO agent_confirmations
              (case_id, summary, action_snapshot, payload_hash, expected_case_version, expires_at,
               analysis_id, option_id, prepared_from_case_version)
            VALUES (%s, %s, %s::jsonb, %s, %s, %s, %s, %s, %s)
            RETURNING id, summary, expires_at, action_snapshot
            """,
            (
                case_id,
                summary,
                payload,
                payload_hash,
                next_version,
                expires_at,
                analysis_id,
                option_id,
                expected_version,
            ),
        ).fetchone()
        connection.execute(
            "UPDATE agent_cases SET state = 'WAITING_CONFIRMATION', version = version + 1, "
            "updated_at = now() WHERE id = %s",
            (case_id,),
        )
    if row is None:
        raise RuntimeError("Could not create overdue follow-up confirmation")
    return {
        "id": str(row["id"]),
        "summary": row["summary"],
        "expires_at": row["expires_at"],
        "action": row["action_snapshot"],
        "idempotent": False,
    }


async def create_overdue_follow_up_confirmation(**kwargs: Any) -> dict[str, Any]:
    return await asyncio.to_thread(_create_overdue_follow_up_confirmation, **kwargs)


def _decide_overdue_follow_up_confirmation(
    *, case_id: UUID, confirmation_id: UUID, actor_id: UUID, approve: bool, reason: str | None
) -> dict[str, Any]:
    with _require_pool().connection() as connection, connection.transaction():
        case = connection.execute(
            "SELECT owner_actor_id, case_type, state, version FROM agent_cases "
            "WHERE id = %s FOR UPDATE",
            (case_id,),
        ).fetchone()
        if case is None:
            raise LookupError("Agent case not found")
        if case["owner_actor_id"] != actor_id:
            raise ReadinessConfirmationError("Agent case must be claimed by the current actor")
        if case["case_type"] != AgentCaseType.RENTAL_RETURN.value:
            raise ReadinessConfirmationError("Agent case is not an overdue-return case")
        confirmation = connection.execute(
            """
            SELECT status, expires_at, action_snapshot, payload_hash, expected_case_version,
                   decided_by, analysis_id
            FROM agent_confirmations WHERE id = %s AND case_id = %s FOR UPDATE
            """,
            (confirmation_id, case_id),
        ).fetchone()
        if confirmation is None or confirmation["analysis_id"] is None:
            raise LookupError("Overdue follow-up confirmation not found")
        snapshot = confirmation["action_snapshot"]
        if not isinstance(snapshot, dict) or snapshot.get("toolName") != "record_overdue_follow_up":
            raise ReadinessConfirmationError("Confirmation is not an overdue follow-up action")
        expected_status = "CONFIRMED" if approve else "REJECTED"
        if confirmation["status"] == expected_status and confirmation["decided_by"] == actor_id:
            return {
                "action_snapshot": snapshot,
                "payload_hash": confirmation["payload_hash"],
                "idempotent": True,
                "state": case["state"],
            }
        if confirmation["status"] != "PENDING":
            raise ReadinessConfirmationError("Confirmation is no longer pending")
        if confirmation["expires_at"] <= datetime.now(UTC):
            connection.execute(
                "UPDATE agent_confirmations SET status = 'EXPIRED', decided_at = now() "
                "WHERE id = %s",
                (confirmation_id,),
            )
            raise ReadinessConfirmationError("Confirmation is no longer pending")
        if case["state"] != AgentCaseState.WAITING_CONFIRMATION.value:
            raise ReadinessConfirmationError("Case is not waiting for confirmation")
        if int(case["version"]) != int(confirmation["expected_case_version"]):
            raise ReadinessConfirmationError("Confirmation snapshot is stale")
        connection.execute(
            "UPDATE agent_confirmations SET status = %s, decided_by = %s, decision_reason = %s, "
            "decided_at = now() WHERE id = %s",
            (expected_status, actor_id, reason, confirmation_id),
        )
        next_state = "EXECUTING" if approve else "PLAN_READY"
        connection.execute(
            "UPDATE agent_cases SET state = %s, version = version + 1, updated_at = now() "
            "WHERE id = %s",
            (next_state, case_id),
        )
    return {
        "action_snapshot": snapshot,
        "payload_hash": confirmation["payload_hash"],
        "idempotent": False,
        "state": next_state,
    }


async def decide_overdue_follow_up_confirmation(**kwargs: Any) -> dict[str, Any]:
    return await asyncio.to_thread(_decide_overdue_follow_up_confirmation, **kwargs)


def _finalize_overdue_follow_up_execution(
    *, case_id: UUID, actor_id: UUID, confirmation_id: UUID
) -> None:
    with _require_pool().connection() as connection, connection.transaction():
        case = connection.execute(
            "SELECT owner_actor_id, case_type, state FROM agent_cases WHERE id = %s FOR UPDATE",
            (case_id,),
        ).fetchone()
        if case is None or case["owner_actor_id"] != actor_id:
            raise LookupError("Agent case not found")
        if case["case_type"] != AgentCaseType.RENTAL_RETURN.value:
            raise ReadinessConfirmationError("Agent case is not an overdue-return case")
        if case["state"] != AgentCaseState.EXECUTING.value:
            raise ReadinessConfirmationError("Agent case is not executing")
        confirmation = connection.execute(
            "SELECT action_snapshot FROM agent_confirmations "
            "WHERE id = %s AND case_id = %s AND status = 'CONFIRMED' FOR UPDATE",
            (confirmation_id, case_id),
        ).fetchone()
        snapshot = confirmation["action_snapshot"] if confirmation is not None else None
        if not isinstance(snapshot, dict) or snapshot.get("toolName") != "record_overdue_follow_up":
            raise ReadinessConfirmationError("Confirmation is not executable")
        connection.execute(
            "UPDATE agent_cases SET state = 'MONITORING', completed_at = NULL, "
            "termination_reason = NULL, updated_at = now(), version = version + 1 WHERE id = %s",
            (case_id,),
        )


async def finalize_overdue_follow_up_execution(**kwargs: Any) -> None:
    await asyncio.to_thread(_finalize_overdue_follow_up_execution, **kwargs)


def _finalize_readiness_execution(
    *,
    case_id: UUID,
    actor_id: UUID,
    confirmation_id: UUID,
    observed_at: datetime,
    evidence: dict[str, Any],
) -> None:
    with _require_pool().connection() as connection, connection.transaction():
        case = connection.execute(
            "SELECT owner_actor_id, state FROM agent_cases WHERE id = %s FOR UPDATE", (case_id,)
        ).fetchone()
        if case is None or case["owner_actor_id"] != actor_id:
            raise LookupError("Agent case not found")
        if case["state"] != AgentCaseState.EXECUTING.value:
            raise ReadinessConfirmationError("Agent case is not executing")
        confirmation = connection.execute(
            "SELECT analysis_id, option_id FROM agent_confirmations "
            "WHERE id = %s AND case_id = %s AND status = 'CONFIRMED' FOR UPDATE",
            (confirmation_id, case_id),
        ).fetchone()
        if confirmation is None or confirmation["analysis_id"] is None:
            raise ReadinessConfirmationError("Confirmation is not executable")
        analysis = connection.execute(
            "SELECT finding_id FROM agent_case_analyses WHERE id = %s FOR UPDATE",
            (confirmation["analysis_id"],),
        ).fetchone()
        if analysis is None:
            raise ReadinessConfirmationError("Recommendation is missing")
        finding = connection.execute(
            "SELECT evidence FROM agent_findings WHERE id = %s FOR UPDATE",
            (analysis["finding_id"],),
        ).fetchone()
        if finding is None:
            raise ReadinessConfirmationError("Finding is missing")
        finding_evidence = dict(finding["evidence"] or {})
        finding_evidence["resolution"] = {
            "code": "RECOMMENDATION_EXECUTED",
            "confirmationId": str(confirmation_id),
            "analysisId": str(confirmation["analysis_id"]),
            "optionId": confirmation["option_id"],
            "evidence": evidence,
            "observedAt": observed_at.isoformat(),
        }
        connection.execute(
            "UPDATE agent_findings SET status = 'RESOLVED', evidence = %s::jsonb, "
            "resolved_at = now(), "
            "source_observed_at = %s WHERE id = %s",
            (json.dumps(finding_evidence, default=str), observed_at, analysis["finding_id"]),
        )
        connection.execute(
            "UPDATE agent_case_analyses SET status = 'STALE', invalidated_at = now() "
            "WHERE id = %s AND status = 'ACTIVE'",
            (confirmation["analysis_id"],),
        )
        connection.execute(
            "UPDATE agent_cases SET state = 'SUCCEEDED', completed_at = now(), updated_at = now(), "
            "version = version + 1 WHERE id = %s",
            (case_id,),
        )


async def finalize_readiness_execution(**kwargs: Any) -> None:
    await asyncio.to_thread(_finalize_readiness_execution, **kwargs)


def _replan_readiness_execution(case_id: UUID, actor_id: UUID) -> None:
    with _require_pool().connection() as connection, connection.transaction():
        case = connection.execute(
            "SELECT owner_actor_id, state FROM agent_cases WHERE id = %s FOR UPDATE", (case_id,)
        ).fetchone()
        if case is None or case["owner_actor_id"] != actor_id:
            raise LookupError("Agent case not found")
        if case["state"] != AgentCaseState.EXECUTING.value:
            return
        connection.execute(
            "UPDATE agent_case_analyses SET status = 'STALE', invalidated_at = now() "
            "WHERE case_id = %s AND status = 'ACTIVE'",
            (case_id,),
        )
        connection.execute(
            "UPDATE agent_cases SET state = 'ANALYZING', version = version + 1, updated_at = now() "
            "WHERE id = %s",
            (case_id,),
        )


async def replan_readiness_execution(case_id: UUID, actor_id: UUID) -> None:
    await asyncio.to_thread(_replan_readiness_execution, case_id, actor_id)
