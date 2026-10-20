from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import psycopg
import pytest
from psycopg import sql
from psycopg.rows import dict_row

from app.agent_tools import (
    case_repository,
    cases,
    decision_repository,
    finding_repository,
    readiness_repository,
    run_repository,
)
from app.agent_tools.cases import (
    CaseAlreadyClaimedError,
    CaseReleaseForbiddenError,
    FindingResolutionConflictError,
)
from app.agent_tools.models import AgentRunStatus
from app.config import get_settings


class _SchemaPool:
    def __init__(self, connection_url: str, schema_name: str) -> None:
        self.connection_url = connection_url
        self.schema_name = schema_name

    @contextmanager
    def connection(self) -> Iterator[psycopg.Connection[dict[str, Any]]]:
        with psycopg.connect(self.connection_url, row_factory=dict_row) as connection:
            connection.execute(
                sql.SQL("SET search_path TO {}, public").format(sql.Identifier(self.schema_name))
            )
            yield connection


@pytest.fixture
def proactive_repository(monkeypatch: pytest.MonkeyPatch) -> Iterator[tuple[_SchemaPool, str]]:
    root = Path(__file__).resolve().parents[1]
    connection_url = get_settings().AI_DATABASE_URL
    schema_name = f"test_agent_repository_{uuid4().hex}"
    migrations = [
        root / "sql" / "002_agent_cases.sql",
        root / "sql" / "003_agent_runtime.sql",
        root / "sql" / "004_agent_run_budgets.sql",
        root / "sql" / "005_agent_sync_runtime.sql",
        root / "sql" / "006_proactive_agent_cases.sql",
        root / "sql" / "007_finding_observation_ordering.sql",
        root / "sql" / "008_rental_readiness_analysis.sql",
        root / "sql" / "009_rental_readiness_execution.sql",
        root / "sql" / "010_order_preparation_delay.sql",
        root / "sql" / "011_rental_return_overdue.sql",
        root / "sql" / "012_operational_capacity_shortfall.sql",
    ]
    with psycopg.connect(connection_url, row_factory=dict_row) as connection:
        connection.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema_name)))
        connection.execute(
            sql.SQL("SET search_path TO {}, public").format(sql.Identifier(schema_name))
        )
        for migration in migrations:
            connection.execute(migration.read_text(encoding="utf-8"), prepare=False)

    pool = _SchemaPool(connection_url, schema_name)
    for repository in (
        case_repository,
        decision_repository,
        finding_repository,
        readiness_repository,
        run_repository,
    ):
        monkeypatch.setattr(repository, "_require_pool", lambda: pool)
    try:
        yield pool, schema_name
    finally:
        with psycopg.connect(connection_url) as connection:
            connection.execute(
                sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema_name))
            )


def _finding_input(branch_id: UUID, dedupe_key: str = "return-risk:one") -> dict[str, Any]:
    start = datetime.now(UTC) + timedelta(hours=1)
    return {
        "rule_code": "PREVIOUS_RENTAL_NOT_RETURNED",
        "rule_version": "v1",
        "dedupe_key": dedupe_key,
        "branch_id": branch_id,
        "primary_entity_id": uuid4(),
        "affected_entity_id": uuid4(),
        "unit_id": uuid4(),
        "window_start": start,
        "window_end": start + timedelta(hours=2),
        "severity": "HIGH",
        "deadline_at": start + timedelta(minutes=30),
        "evidence": {"source": "integration-test"},
    }


def _plan_ready_case(
    dedupe_key: str,
) -> tuple[UUID, UUID, UUID, int, dict[str, Any]]:
    actor_id = uuid4()
    input_data = {
        **_finding_input(uuid4(), dedupe_key),
        "observed_at": datetime.now(UTC),
    }
    case_id = cases._upsert_finding(input_data)
    claimed = cases._claim_case(case_id, actor_id, 1)
    started = cases._begin_readiness_analysis(case_id, actor_id, int(claimed["version"]))
    option_id = "reallocate-replacement-unit"
    analysis_id = cases._finalize_readiness_analysis(
        case_id=case_id,
        actor_id=actor_id,
        case_version_at_start=started["case_version"],
        finding_id=started["finding_id"],
        finding_source_observed_at=started["source_observed_at"],
        snapshot={"before": {"unitId": started["unit_id"]}},
        options=[
            {
                "optionId": option_id,
                "optionType": "REALLOCATE_SAME_BRANCH",
                "feasible": True,
            }
        ],
        recommended_option_id=option_id,
        outcome="READY",
        narrative={
            "summary": "Use the available replacement unit.",
            "rationale": [],
            "risks": [],
            "nextStep": "Confirm the recommendation.",
            "fallback": True,
        },
    )
    ready = cases._get_case_by_id(case_id)
    assert ready is not None
    action = {
        "toolName": "reallocate_rental_item",
        "arguments": {
            "orderId": str(input_data["primary_entity_id"]),
            "orderItemId": str(uuid4()),
            "unitId": str(uuid4()),
            "reason": "Rental readiness recommendation",
        },
        "expectedVersion": 7,
        "readbackTool": "get_rental_order",
        "payloadHash": "preview-only",
    }
    return case_id, actor_id, analysis_id, int(ready["version"]), action


def test_concurrent_finding_upserts_create_one_case_and_preserve_claimed_owner(
    proactive_repository: tuple[_SchemaPool, str],
) -> None:
    pool, _ = proactive_repository
    input_data = _finding_input(uuid4())
    with ThreadPoolExecutor(max_workers=2) as executor:
        case_ids = list(executor.map(lambda _: cases._upsert_finding(input_data), range(2)))

    assert case_ids[0] == case_ids[1]
    with pool.connection() as connection:
        counts = connection.execute(
            "SELECT (SELECT count(*) FROM agent_cases) AS cases, "
            "(SELECT count(*) FROM agent_findings) AS findings"
        ).fetchone()
    assert counts == {"cases": 1, "findings": 1}

    owner_id = uuid4()
    current = cases._get_case_by_id(case_ids[0])
    assert current is not None
    claimed = cases._claim_case(case_ids[0], owner_id, int(current["version"]))
    refreshed_input = {**input_data, "severity": "CRITICAL", "evidence": {"late": True}}
    cases._upsert_finding(refreshed_input)
    refreshed = cases._get_case_by_id(case_ids[0])
    assert refreshed is not None
    assert refreshed["owner_actor_id"] == str(owner_id)
    assert refreshed["version"] == claimed["version"] + 1


def test_allocated_unit_not_ready_uses_the_existing_readiness_case_contract(
    proactive_repository: tuple[_SchemaPool, str],
) -> None:
    pool, _ = proactive_repository
    input_data = {
        **_finding_input(uuid4(), "allocated-unit-not-ready:one"),
        "rule_code": "ALLOCATED_UNIT_NOT_READY",
    }

    case_id = cases._upsert_finding(input_data)

    with pool.connection() as connection:
        row = connection.execute(
            "SELECT c.case_type, c.origin, c.owner_actor_id, f.rule_code "
            "FROM agent_cases c JOIN agent_findings f ON f.case_id = c.id "
            "WHERE c.id = %s",
            (case_id,),
        ).fetchone()
    assert row == {
        "case_type": "RENTAL_READINESS",
        "origin": "SYSTEM",
        "owner_actor_id": None,
        "rule_code": "ALLOCATED_UNIT_NOT_READY",
    }


def test_order_preparation_delay_supports_an_order_level_finding(
    proactive_repository: tuple[_SchemaPool, str],
) -> None:
    pool, _ = proactive_repository
    input_data = {
        **_finding_input(uuid4(), "order-preparation-delay:one"),
        "rule_code": "ORDER_PREPARATION_DELAYED",
        "affected_entity_id": None,
        "unit_id": None,
    }

    case_id = cases._upsert_finding(input_data)

    with pool.connection() as connection:
        row = connection.execute(
            "SELECT c.case_type, f.rule_code, f.affected_entity_id, f.unit_id "
            "FROM agent_cases c JOIN agent_findings f ON f.case_id = c.id "
            "WHERE c.id = %s",
            (case_id,),
        ).fetchone()
    assert row == {
        "case_type": "RENTAL_READINESS",
        "rule_code": "ORDER_PREPARATION_DELAYED",
        "affected_entity_id": None,
        "unit_id": None,
    }


def test_overdue_return_creates_a_claimable_rental_return_case(
    proactive_repository: tuple[_SchemaPool, str],
) -> None:
    pool, _ = proactive_repository
    input_data = {
        **_finding_input(uuid4(), "rental-return-overdue:one"),
        "rule_code": "RENTAL_RETURN_OVERDUE",
        "affected_entity_id": None,
        "unit_id": None,
    }

    case_id = cases._upsert_finding(input_data)
    actor_id = uuid4()
    case = cases._claim_case(case_id, actor_id, 1)
    queued, _ = cases._list_operational_cases(None, None, None, "all", actor_id, None, 100)
    started = cases._begin_readiness_analysis(case_id, actor_id, int(case["version"]))
    analysis_id = cases._finalize_readiness_analysis(
        case_id=case_id,
        actor_id=actor_id,
        case_version_at_start=started["case_version"],
        finding_id=started["finding_id"],
        finding_source_observed_at=started["source_observed_at"],
        snapshot={"ruleCode": "RENTAL_RETURN_OVERDUE", "before": {}},
        options=[{"optionId": "contact-customer-for-return", "executable": False}],
        recommended_option_id="contact-customer-for-return",
        outcome="READY",
        narrative={"summary": "Overdue", "nextStep": "Contact customer"},
        simulator_version="rental-return-overdue/v1",
        ranking_policy_version="overdue-response/v1",
    )

    with pool.connection() as connection:
        row = connection.execute(
            "SELECT c.case_type, c.state, f.rule_code, f.affected_entity_id, f.unit_id, "
            "a.simulator_version, a.ranking_policy_version "
            "FROM agent_cases c JOIN agent_findings f ON f.case_id = c.id "
            "JOIN agent_case_analyses a ON a.case_id = c.id "
            "WHERE c.id = %s",
            (case_id,),
        ).fetchone()
    assert case["case_type"] == "RENTAL_RETURN"
    assert any(item["id"] == str(case_id) for item in queued)
    assert row == {
        "case_type": "RENTAL_RETURN",
        "state": "PLAN_READY",
        "rule_code": "RENTAL_RETURN_OVERDUE",
        "affected_entity_id": None,
        "unit_id": None,
        "simulator_version": "rental-return-overdue/v1",
        "ranking_policy_version": "overdue-response/v1",
    }
    assert analysis_id is not None
    with pytest.raises(cases.ReadinessConfirmationError):
        cases._create_readiness_confirmation(
            case_id=case_id,
            actor_id=actor_id,
            analysis_id=analysis_id,
            option_id="contact-customer-for-return",
            expected_version=int(started["case_version"]) + 1,
            summary="Contact the customer",
            action_snapshot={"toolName": "not-executable", "arguments": {}},
            ttl_minutes=30,
        )


def test_capacity_shortfall_creates_non_executable_operational_case(
    proactive_repository: tuple[_SchemaPool, str],
) -> None:
    pool, _ = proactive_repository
    branch_id = uuid4()
    input_data = {
        **_finding_input(branch_id, "capacity-shortfall:one"),
        "rule_code": "OPERATIONAL_CAPACITY_SHORTFALL",
        "primary_entity_id": branch_id,
        "affected_entity_id": None,
        "unit_id": None,
    }

    case_id = cases._upsert_finding(input_data)
    actor_id = uuid4()
    case = cases._claim_case(case_id, actor_id, 1)
    started = cases._begin_readiness_analysis(case_id, actor_id, int(case["version"]))
    analysis_id = cases._finalize_readiness_analysis(
        case_id=case_id,
        actor_id=actor_id,
        case_version_at_start=started["case_version"],
        finding_id=started["finding_id"],
        finding_source_observed_at=started["source_observed_at"],
        snapshot={"ruleCode": "OPERATIONAL_CAPACITY_SHORTFALL", "before": {}},
        options=[{"optionId": "reprioritize-operational-tasks", "executable": False}],
        recommended_option_id="reprioritize-operational-tasks",
        outcome="READY",
        narrative={"summary": "Capacity shortfall", "nextStep": "Review priorities"},
        simulator_version="operational-capacity/v1",
        ranking_policy_version="capacity-response/v1",
    )

    with pool.connection() as connection:
        row = connection.execute(
            "SELECT c.case_type, c.state, f.rule_code, f.primary_entity_id "
            "FROM agent_cases c JOIN agent_findings f ON f.case_id = c.id "
            "WHERE c.id = %s",
            (case_id,),
        ).fetchone()
    assert row == {
        "case_type": "OPERATIONAL_CAPACITY",
        "state": "PLAN_READY",
        "rule_code": "OPERATIONAL_CAPACITY_SHORTFALL",
        "primary_entity_id": branch_id,
    }
    with pytest.raises(cases.ReadinessConfirmationError):
        cases._create_readiness_confirmation(
            case_id=case_id,
            actor_id=actor_id,
            analysis_id=analysis_id,
            option_id="reprioritize-operational-tasks",
            expected_version=int(started["case_version"]) + 1,
            summary="Review priorities",
            action_snapshot={"toolName": "not-executable", "arguments": {}},
            ttl_minutes=30,
        )


def test_concurrent_claim_has_one_winner_and_reports_other_owner(
    proactive_repository: tuple[_SchemaPool, str],
) -> None:
    del proactive_repository
    case_id = cases._upsert_finding(_finding_input(uuid4()))
    actors = (uuid4(), uuid4())

    def claim(actor_id: UUID) -> tuple[str, str]:
        try:
            result = cases._claim_case(case_id, actor_id, 1)
            return "claimed", str(result["owner_actor_id"])
        except CaseAlreadyClaimedError:
            return "already_claimed", str(actor_id)

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(claim, actors))

    assert sorted(result[0] for result in results) == ["already_claimed", "claimed"]


def test_finding_refresh_reanalyzes_and_expires_pending_decisions(
    proactive_repository: tuple[_SchemaPool, str],
) -> None:
    pool, _ = proactive_repository
    input_data = _finding_input(uuid4())
    case_id = cases._upsert_finding(input_data)
    owner_id = uuid4()
    claimed = cases._claim_case(case_id, owner_id, 1)
    with pool.connection() as connection:
        connection.execute(
            "UPDATE agent_cases SET state = 'WAITING_CONFIRMATION' WHERE id = %s",
            (case_id,),
        )
        connection.execute(
            """
            INSERT INTO agent_confirmations
              (case_id, summary, action_snapshot, payload_hash, expected_case_version, expires_at)
            VALUES (%s, 'Confirm', '{}'::jsonb, %s, %s, now() + interval '1 hour')
            """,
            (case_id, uuid4().hex, claimed["version"]),
        )

    cases._upsert_finding({**input_data, "evidence": {"changed": True}})
    with pool.connection() as connection:
        case = connection.execute(
            "SELECT state, version, owner_actor_id FROM agent_cases WHERE id = %s",
            (case_id,),
        ).fetchone()
        confirmation = connection.execute(
            "SELECT status FROM agent_confirmations WHERE case_id = %s", (case_id,)
        ).fetchone()
    assert confirmation is not None
    assert case == {
        "state": "ANALYZING",
        "version": claimed["version"] + 1,
        "owner_actor_id": owner_id,
    }
    assert confirmation["status"] == "EXPIRED"


def test_confirmation_and_finding_refresh_use_consistent_lock_order(
    proactive_repository: tuple[_SchemaPool, str],
) -> None:
    pool, _ = proactive_repository
    input_data = _finding_input(uuid4())
    case_id = cases._upsert_finding(input_data)
    owner_id = uuid4()
    claimed = cases._claim_case(case_id, owner_id, 1)
    confirmation_id = uuid4()
    with pool.connection() as connection:
        connection.execute(
            "UPDATE agent_cases SET state = 'WAITING_CONFIRMATION' WHERE id = %s",
            (case_id,),
        )
        connection.execute(
            """
            INSERT INTO agent_confirmations
              (id, case_id, summary, action_snapshot, payload_hash,
               expected_case_version, expires_at)
            VALUES (%s, %s, 'Confirm', '{}'::jsonb, %s, %s, now() + interval '1 hour')
            """,
            (confirmation_id, case_id, uuid4().hex, claimed["version"]),
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        decision = executor.submit(
            cases._decide_confirmation,
            confirmation_id,
            case_id,
            owner_id,
            True,
            None,
        )
        refresh = executor.submit(cases._upsert_finding, input_data)
        decision.result(timeout=10)
        assert refresh.result(timeout=10) == case_id


@pytest.mark.parametrize("state", ["EXECUTING", "SUCCEEDED"])
def test_release_rejects_executing_and_terminal_cases(
    proactive_repository: tuple[_SchemaPool, str], state: str
) -> None:
    pool, _ = proactive_repository
    case_id = cases._upsert_finding(_finding_input(uuid4()))
    owner_id = uuid4()
    claimed = cases._claim_case(case_id, owner_id, 1)
    with pool.connection() as connection:
        connection.execute("UPDATE agent_cases SET state = %s WHERE id = %s", (state, case_id))

    with pytest.raises(CaseReleaseForbiddenError):
        cases._release_case(case_id, owner_id, int(claimed["version"]))


def test_finding_list_paginates_open_findings(
    proactive_repository: tuple[_SchemaPool, str],
) -> None:
    del proactive_repository
    first = _finding_input(uuid4(), "return-risk:list-one")
    second = _finding_input(uuid4(), "return-risk:list-two")
    first["observed_at"] = datetime.now(UTC)
    second["observed_at"] = first["observed_at"] + timedelta(seconds=1)
    cases._upsert_finding(first)
    cases._upsert_finding(second)

    page, cursor = cases._list_findings("PREVIOUS_RENTAL_NOT_RETURNED", "OPEN", None, 1)
    assert [row["dedupe_key"] for row in page] == ["return-risk:list-one"]
    assert cursor is not None
    assert cursor != "1"
    next_page, next_cursor = cases._list_findings("PREVIOUS_RENTAL_NOT_RETURNED", "OPEN", cursor, 1)
    assert [row["dedupe_key"] for row in next_page] == ["return-risk:list-two"]
    assert next_cursor is None


def test_finding_keyset_pagination_does_not_skip_after_prior_item_is_resolved(
    proactive_repository: tuple[_SchemaPool, str],
) -> None:
    del proactive_repository
    observed_at = datetime.now(UTC)
    first = {
        **_finding_input(uuid4(), "return-risk:keyset-one"),
        "observed_at": observed_at,
    }
    second = {
        **_finding_input(uuid4(), "return-risk:keyset-two"),
        "observed_at": observed_at + timedelta(seconds=1),
    }
    cases._upsert_finding(first)
    cases._upsert_finding(second)
    page, cursor = cases._list_findings("PREVIOUS_RENTAL_NOT_RETURNED", "OPEN", None, 1)
    assert [row["dedupe_key"] for row in page] == ["return-risk:keyset-one"]
    assert cursor is not None
    cases._resolve_finding(
        {
            "dedupe_key": first["dedupe_key"],
            "rule_code": first["rule_code"],
            "observed_at": observed_at + timedelta(seconds=2),
            "resolution_code": "RISK_NO_LONGER_PRESENT",
            "evidence": {},
        }
    )

    next_page, _ = cases._list_findings("PREVIOUS_RENTAL_NOT_RETURNED", "OPEN", cursor, 1)
    assert [row["dedupe_key"] for row in next_page] == ["return-risk:keyset-two"]


def test_stale_upsert_does_not_overwrite_newer_observation_or_case(
    proactive_repository: tuple[_SchemaPool, str],
) -> None:
    pool, _ = proactive_repository
    observed_at = datetime.now(UTC)
    input_data = {
        **_finding_input(uuid4(), "return-risk:stale-upsert"),
        "observed_at": observed_at,
        "evidence": {"version": "new"},
    }
    case_id = cases._upsert_finding(input_data)
    returned_case_id = cases._upsert_finding(
        {
            **input_data,
            "observed_at": observed_at - timedelta(seconds=1),
            "evidence": {"version": "old"},
        }
    )

    assert returned_case_id == case_id
    with pool.connection() as connection:
        finding = connection.execute(
            "SELECT evidence, source_observed_at FROM agent_findings WHERE case_id = %s",
            (case_id,),
        ).fetchone()
        count = connection.execute("SELECT count(*) AS count FROM agent_cases").fetchone()
    assert finding is not None
    assert count is not None
    assert finding["evidence"] == {"version": "new"}
    assert finding["source_observed_at"] == observed_at
    assert count["count"] == 1


def test_resolve_finding_closes_nonterminal_case_and_expires_decisions(
    proactive_repository: tuple[_SchemaPool, str],
) -> None:
    pool, _ = proactive_repository
    observed_at = datetime.now(UTC)
    input_data = {
        **_finding_input(uuid4(), "return-risk:resolve"),
        "observed_at": observed_at,
    }
    case_id = cases._upsert_finding(input_data)
    with pool.connection() as connection:
        connection.execute(
            "UPDATE agent_cases SET state = 'WAITING_CONFIRMATION' WHERE id = %s",
            (case_id,),
        )
        connection.execute(
            """
            INSERT INTO agent_confirmations
              (case_id, summary, action_snapshot, payload_hash, expected_case_version, expires_at)
            VALUES (%s, 'Confirm', '{}'::jsonb, %s, 1, now() + interval '1 hour')
            """,
            (case_id, uuid4().hex),
        )

    result = cases._resolve_finding(
        {
            "dedupe_key": input_data["dedupe_key"],
            "rule_code": input_data["rule_code"],
            "observed_at": observed_at + timedelta(seconds=1),
            "resolution_code": "RISK_NO_LONGER_PRESENT",
            "evidence": {"reason": "returned"},
        }
    )

    assert result["outcome"] == "RESOLVED"
    with pool.connection() as connection:
        finding = connection.execute(
            "SELECT status, evidence, resolved_at FROM agent_findings WHERE case_id = %s",
            (case_id,),
        ).fetchone()
        case = connection.execute(
            "SELECT state, completed_at, version FROM agent_cases WHERE id = %s", (case_id,)
        ).fetchone()
        confirmation = connection.execute(
            "SELECT status FROM agent_confirmations WHERE case_id = %s", (case_id,)
        ).fetchone()
    assert finding is not None
    assert case is not None
    assert confirmation is not None
    assert finding["status"] == "RESOLVED"
    assert finding["resolved_at"] is not None
    assert finding["evidence"]["resolution"]["code"] == "RISK_NO_LONGER_PRESENT"
    assert case["state"] == "SUCCEEDED"
    assert case["completed_at"] is not None
    assert case["version"] == 2
    assert confirmation["status"] == "EXPIRED"


def test_resolve_is_idempotent_and_stale_resolution_is_ignored(
    proactive_repository: tuple[_SchemaPool, str],
) -> None:
    del proactive_repository
    observed_at = datetime.now(UTC)
    input_data = {
        **_finding_input(uuid4(), "return-risk:idempotent-resolve"),
        "observed_at": observed_at,
    }
    cases._upsert_finding(input_data)
    request = {
        "dedupe_key": input_data["dedupe_key"],
        "rule_code": input_data["rule_code"],
        "observed_at": observed_at + timedelta(seconds=2),
        "resolution_code": "RISK_NO_LONGER_PRESENT",
        "evidence": {},
    }
    assert cases._resolve_finding(request)["outcome"] == "RESOLVED"
    assert cases._resolve_finding(request)["outcome"] == "ALREADY_RESOLVED"
    assert (
        cases._resolve_finding({**request, "observed_at": observed_at + timedelta(seconds=1)})[
            "outcome"
        ]
        == "STALE"
    )


def test_newer_idempotent_resolve_advances_watermark_and_blocks_delayed_upsert(
    proactive_repository: tuple[_SchemaPool, str],
) -> None:
    pool, _ = proactive_repository
    base = datetime.now(UTC)
    input_data = {
        **_finding_input(uuid4(), "return-risk:resolve-watermark"),
        "observed_at": base,
    }
    case_id = cases._upsert_finding(input_data)
    resolve_input = {
        "dedupe_key": input_data["dedupe_key"],
        "rule_code": input_data["rule_code"],
        "resolution_code": "RISK_NO_LONGER_PRESENT",
        "evidence": {},
    }
    assert (
        cases._resolve_finding({**resolve_input, "observed_at": base + timedelta(seconds=2)})[
            "outcome"
        ]
        == "RESOLVED"
    )
    latest = cases._resolve_finding(
        {
            **resolve_input,
            "observed_at": base + timedelta(seconds=4),
            "evidence": {"source": "reconciliation"},
        }
    )
    assert latest["outcome"] == "ALREADY_RESOLVED"
    assert latest["source_observed_at"] == base + timedelta(seconds=4)

    delayed_case_id = cases._upsert_finding(
        {**input_data, "observed_at": base + timedelta(seconds=3)}
    )
    assert delayed_case_id == case_id
    with pool.connection() as connection:
        counts = connection.execute("SELECT count(*) AS cases FROM agent_cases").fetchone()
        finding = connection.execute(
            "SELECT status, source_observed_at, evidence FROM agent_findings WHERE case_id = %s",
            (case_id,),
        ).fetchone()
    assert counts is not None
    assert finding is not None
    assert counts["cases"] == 1
    assert finding["status"] == "RESOLVED"
    assert finding["source_observed_at"] == base + timedelta(seconds=4)
    assert finding["evidence"]["resolution"]["evidence"] == {"source": "reconciliation"}


def test_resolve_rejects_executing_case_and_preserves_open_finding(
    proactive_repository: tuple[_SchemaPool, str],
) -> None:
    pool, _ = proactive_repository
    observed_at = datetime.now(UTC)
    input_data = {
        **_finding_input(uuid4(), "return-risk:executing"),
        "observed_at": observed_at,
    }
    case_id = cases._upsert_finding(input_data)
    with pool.connection() as connection:
        connection.execute("UPDATE agent_cases SET state = 'EXECUTING' WHERE id = %s", (case_id,))

    with pytest.raises(FindingResolutionConflictError):
        cases._resolve_finding(
            {
                "dedupe_key": input_data["dedupe_key"],
                "rule_code": input_data["rule_code"],
                "observed_at": observed_at + timedelta(seconds=1),
                "resolution_code": "RISK_NO_LONGER_PRESENT",
                "evidence": {},
            }
        )
    with pool.connection() as connection:
        finding = connection.execute(
            "SELECT status FROM agent_findings WHERE case_id = %s", (case_id,)
        ).fetchone()
    assert finding is not None
    assert finding["status"] == "OPEN"


def test_resolve_rejects_analyzing_case_with_live_active_run(
    proactive_repository: tuple[_SchemaPool, str],
) -> None:
    pool, _ = proactive_repository
    observed_at = datetime.now(UTC)
    input_data = {
        **_finding_input(uuid4(), "return-risk:live-run"),
        "observed_at": observed_at,
    }
    case_id = cases._upsert_finding(input_data)
    with pool.connection() as connection:
        connection.execute("UPDATE agent_cases SET state = 'ANALYZING' WHERE id = %s", (case_id,))
    cases._create_run(case_id, None, 60)

    with pytest.raises(FindingResolutionConflictError):
        cases._resolve_finding(
            {
                "dedupe_key": input_data["dedupe_key"],
                "rule_code": input_data["rule_code"],
                "observed_at": observed_at + timedelta(seconds=1),
                "resolution_code": "RISK_NO_LONGER_PRESENT",
                "evidence": {},
            }
        )


@pytest.mark.parametrize("run_mode", ["stale", "cleared"])
def test_resolve_allows_analyzing_case_without_live_run(
    proactive_repository: tuple[_SchemaPool, str], run_mode: str
) -> None:
    pool, _ = proactive_repository
    observed_at = datetime.now(UTC)
    input_data = {
        **_finding_input(uuid4(), f"return-risk:{run_mode}-run"),
        "observed_at": observed_at,
    }
    case_id = cases._upsert_finding(input_data)
    with pool.connection() as connection:
        connection.execute("UPDATE agent_cases SET state = 'ANALYZING' WHERE id = %s", (case_id,))
    run_id = cases._create_run(case_id, None, -1 if run_mode == "stale" else 60)
    if run_mode == "cleared":
        cases._mark_run(run_id, AgentRunStatus.COMPLETED)

    result = cases._resolve_finding(
        {
            "dedupe_key": input_data["dedupe_key"],
            "rule_code": input_data["rule_code"],
            "observed_at": observed_at + timedelta(seconds=1),
            "resolution_code": "RISK_NO_LONGER_PRESENT",
            "evidence": {},
        }
    )
    assert result["outcome"] == "RESOLVED"
    with pool.connection() as connection:
        case = connection.execute(
            "SELECT state, active_run_id, active_run_deadline FROM agent_cases WHERE id = %s",
            (case_id,),
        ).fetchone()
        run = connection.execute(
            "SELECT status, error_code FROM agent_runs WHERE id = %s", (run_id,)
        ).fetchone()
    assert case == {
        "state": "SUCCEEDED",
        "active_run_id": None,
        "active_run_deadline": None,
    }
    if run_mode == "stale":
        assert run == {"status": "FAILED", "error_code": "RUN_DEADLINE_EXPIRED"}
    else:
        assert run is not None
        assert run["status"] == "COMPLETED"


def test_newer_upsert_after_resolution_creates_new_case(
    proactive_repository: tuple[_SchemaPool, str],
) -> None:
    del proactive_repository
    observed_at = datetime.now(UTC)
    input_data = {
        **_finding_input(uuid4(), "return-risk:reappeared"),
        "observed_at": observed_at,
    }
    first_case_id = cases._upsert_finding(input_data)
    cases._resolve_finding(
        {
            "dedupe_key": input_data["dedupe_key"],
            "rule_code": input_data["rule_code"],
            "observed_at": observed_at + timedelta(seconds=1),
            "resolution_code": "RISK_NO_LONGER_PRESENT",
            "evidence": {},
        }
    )
    second_case_id = cases._upsert_finding(
        {**input_data, "observed_at": observed_at + timedelta(seconds=2)}
    )
    assert second_case_id != first_case_id


def test_resolve_finding_does_not_change_terminal_case_state_or_version(
    proactive_repository: tuple[_SchemaPool, str],
) -> None:
    pool, _ = proactive_repository
    observed_at = datetime.now(UTC)
    input_data = {
        **_finding_input(uuid4(), "return-risk:terminal"),
        "observed_at": observed_at,
    }
    case_id = cases._upsert_finding(input_data)
    with pool.connection() as connection:
        connection.execute(
            "UPDATE agent_cases SET state = 'FAILED', completed_at = now() WHERE id = %s",
            (case_id,),
        )

    result = cases._resolve_finding(
        {
            "dedupe_key": input_data["dedupe_key"],
            "rule_code": input_data["rule_code"],
            "observed_at": observed_at + timedelta(seconds=1),
            "resolution_code": "RISK_NO_LONGER_PRESENT",
            "evidence": {},
        }
    )

    assert result["outcome"] == "RESOLVED"
    with pool.connection() as connection:
        case = connection.execute(
            "SELECT state, version FROM agent_cases WHERE id = %s", (case_id,)
        ).fetchone()
        finding = connection.execute(
            "SELECT status FROM agent_findings WHERE case_id = %s", (case_id,)
        ).fetchone()
    assert case == {"state": "FAILED", "version": 1}
    assert finding is not None
    assert finding["status"] == "RESOLVED"


def test_concurrent_readiness_confirmation_prepare_is_idempotent_and_rejects_cleanly(
    proactive_repository: tuple[_SchemaPool, str],
) -> None:
    pool, _ = proactive_repository
    case_id, actor_id, analysis_id, version, action = _plan_ready_case(
        "return-risk:concurrent-prepare"
    )
    kwargs = {
        "case_id": case_id,
        "actor_id": actor_id,
        "analysis_id": analysis_id,
        "option_id": "reallocate-replacement-unit",
        "expected_version": version,
        "summary": "Move the rental to the replacement unit.",
        "action_snapshot": action,
        "ttl_minutes": 30,
    }

    with ThreadPoolExecutor(max_workers=2) as executor:
        prepared = list(
            executor.map(
                lambda _: cases._create_readiness_confirmation(**kwargs),  # type: ignore[arg-type]
                range(2),
            )
        )

    assert prepared[0]["id"] == prepared[1]["id"]
    assert {item["idempotent"] for item in prepared} == {False, True}
    confirmation_id = UUID(prepared[0]["id"])
    rejected = cases._decide_readiness_confirmation(
        case_id=case_id,
        confirmation_id=confirmation_id,
        actor_id=actor_id,
        approve=False,
        reason="Use the current unit instead.",
    )
    assert rejected["state"] == "PLAN_READY"

    with pool.connection() as connection:
        case = connection.execute(
            "SELECT state FROM agent_cases WHERE id = %s", (case_id,)
        ).fetchone()
        finding = connection.execute(
            "SELECT status FROM agent_findings WHERE case_id = %s", (case_id,)
        ).fetchone()
        analysis = connection.execute(
            "SELECT status FROM agent_case_analyses WHERE id = %s", (analysis_id,)
        ).fetchone()
        confirmations = connection.execute(
            "SELECT count(*) AS count, min(status) AS status "
            "FROM agent_confirmations WHERE case_id = %s",
            (case_id,),
        ).fetchone()
    assert case is not None
    assert finding is not None
    assert analysis is not None
    assert case["state"] == "PLAN_READY"
    assert finding["status"] == "OPEN"
    assert analysis["status"] == "ACTIVE"
    assert confirmations == {"count": 1, "status": "REJECTED"}


def test_readiness_confirmation_success_finalizes_case_finding_and_analysis_atomically(
    proactive_repository: tuple[_SchemaPool, str],
) -> None:
    pool, _ = proactive_repository
    case_id, actor_id, analysis_id, version, action = _plan_ready_case(
        "return-risk:execution-success"
    )
    prepared = cases._create_readiness_confirmation(
        case_id=case_id,
        actor_id=actor_id,
        analysis_id=analysis_id,
        option_id="reallocate-replacement-unit",
        expected_version=version,
        summary="Move the rental to the replacement unit.",
        action_snapshot=action,
        ttl_minutes=30,
    )
    confirmation_id = UUID(prepared["id"])
    confirmed = cases._decide_readiness_confirmation(
        case_id=case_id,
        confirmation_id=confirmation_id,
        actor_id=actor_id,
        approve=True,
        reason=None,
    )
    assert confirmed["state"] == "EXECUTING"

    observed_at = datetime.now(UTC)
    cases._finalize_readiness_execution(
        case_id=case_id,
        actor_id=actor_id,
        confirmation_id=confirmation_id,
        observed_at=observed_at,
        evidence={"readbackMatched": True},
    )

    with pool.connection() as connection:
        row = connection.execute(
            """
            SELECT c.state, c.completed_at, f.status AS finding_status,
                   f.evidence, a.status AS analysis_status
            FROM agent_cases c
            JOIN agent_findings f ON f.case_id = c.id
            JOIN agent_case_analyses a ON a.case_id = c.id
            WHERE c.id = %s
            """,
            (case_id,),
        ).fetchone()
    assert row is not None
    assert row["state"] == "SUCCEEDED"
    assert row["completed_at"] is not None
    assert row["finding_status"] == "RESOLVED"
    assert row["analysis_status"] == "STALE"
    assert row["evidence"]["resolution"]["code"] == "RECOMMENDATION_EXECUTED"
    assert row["evidence"]["resolution"]["confirmationId"] == str(confirmation_id)
