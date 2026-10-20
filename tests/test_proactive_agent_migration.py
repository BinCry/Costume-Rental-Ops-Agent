from pathlib import Path
from uuid import uuid4

import psycopg
from psycopg import sql
from psycopg.rows import dict_row

from app.config import get_settings


def test_proactive_case_migration_backfills_legacy_cases_and_is_rerunnable() -> None:
    """Exercise the real SQL in an isolated schema without touching application data."""
    root = Path(__file__).resolve().parents[1]
    migrations = [
        root / "sql" / "002_agent_cases.sql",
        root / "sql" / "003_agent_runtime.sql",
        root / "sql" / "004_agent_run_budgets.sql",
        root / "sql" / "005_agent_sync_runtime.sql",
    ]
    proactive = root / "sql" / "006_proactive_agent_cases.sql"
    schema_name = f"test_agent_phase1_{uuid4().hex}"
    actor_id = uuid4()

    with (
        psycopg.connect(get_settings().AI_DATABASE_URL, row_factory=dict_row) as connection,
        connection.transaction(),
    ):
        connection.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema_name)))
        connection.execute(
            sql.SQL("SET LOCAL search_path TO {}, public").format(sql.Identifier(schema_name))
        )
        for migration in migrations:
            connection.execute(migration.read_text(encoding="utf-8"), prepare=False)
        case_row = connection.execute(
            """
                INSERT INTO agent_cases (actor_id, audiences, state)
                VALUES (%s, ARRAY['customer', 'shared'], 'NEW')
                RETURNING id
                """,
            (actor_id,),
        ).fetchone()
        assert case_row is not None
        case_id = case_row["id"]

        migration_sql = proactive.read_text(encoding="utf-8")
        connection.execute(migration_sql, prepare=False)
        connection.execute(migration_sql, prepare=False)

        case = connection.execute(
            """
                SELECT owner_actor_id, created_by_actor_id, origin, case_type, branch_id
                FROM agent_cases WHERE id = %s
                """,
            (case_id,),
        ).fetchone()
        assert case == {
            "owner_actor_id": actor_id,
            "created_by_actor_id": actor_id,
            "origin": "USER",
            "case_type": "INTERACTIVE",
            "branch_id": None,
        }
        indexes = {
            row["indexname"]
            for row in connection.execute(
                "SELECT indexname FROM pg_indexes WHERE schemaname = %s",
                (schema_name,),
            ).fetchall()
        }
        assert "agent_cases_branch_queue_idx" in indexes
        assert "agent_findings_open_dedupe_idx" in indexes
        connection.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema_name)))


def test_finding_observation_migration_backfills_and_is_rerunnable() -> None:
    root = Path(__file__).resolve().parents[1]
    migrations = [
        root / "sql" / "002_agent_cases.sql",
        root / "sql" / "003_agent_runtime.sql",
        root / "sql" / "004_agent_run_budgets.sql",
        root / "sql" / "005_agent_sync_runtime.sql",
        root / "sql" / "006_proactive_agent_cases.sql",
    ]
    observation_migration = root / "sql" / "007_finding_observation_ordering.sql"
    schema_name = f"test_agent_phase2_{uuid4().hex}"

    with (
        psycopg.connect(get_settings().AI_DATABASE_URL, row_factory=dict_row) as connection,
        connection.transaction(),
    ):
        connection.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema_name)))
        connection.execute(
            sql.SQL("SET LOCAL search_path TO {}, public").format(sql.Identifier(schema_name))
        )
        for migration in migrations:
            connection.execute(migration.read_text(encoding="utf-8"), prepare=False)
        branch_id = uuid4()
        case_row = connection.execute(
            """
            INSERT INTO agent_cases
              (audiences, state, origin, case_type, branch_id)
            VALUES (ARRAY['staff_internal', 'shared'], 'NEW', 'SYSTEM',
                    'RENTAL_READINESS', %s)
            RETURNING id
            """,
            (branch_id,),
        ).fetchone()
        assert case_row is not None
        case_id = case_row["id"]
        finding_row = connection.execute(
            """
            INSERT INTO agent_findings
              (case_id, rule_code, rule_version, dedupe_key, branch_id,
               primary_entity_id, affected_entity_id, unit_id, window_start,
               window_end, severity, last_detected_at)
            VALUES (%s, 'PREVIOUS_RENTAL_NOT_RETURNED', 'v1', 'migration:test', %s,
                    %s, %s, %s, now(), now() + interval '1 hour', 'HIGH',
                    now() - interval '5 minutes')
            RETURNING id
            """,
            (case_id, branch_id, uuid4(), uuid4(), uuid4()),
        ).fetchone()
        assert finding_row is not None
        finding_id = finding_row["id"]

        migration_sql = observation_migration.read_text(encoding="utf-8")
        connection.execute(migration_sql, prepare=False)
        connection.execute(migration_sql, prepare=False)
        finding = connection.execute(
            """
            SELECT source_observed_at = last_detected_at AS backfilled
            FROM agent_findings WHERE id = %s
            """,
            (finding_id,),
        ).fetchone()
        nullable = connection.execute(
            """
            SELECT is_nullable FROM information_schema.columns
            WHERE table_schema = %s AND table_name = 'agent_findings'
              AND column_name = 'source_observed_at'
            """,
            (schema_name,),
        ).fetchone()
        assert finding is not None
        assert nullable is not None
        assert finding["backfilled"] is True
        assert nullable["is_nullable"] == "NO"
        connection.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema_name)))


def test_readiness_analysis_migration_is_rerunnable() -> None:
    root = Path(__file__).resolve().parents[1]
    migrations = [
        root / "sql" / "002_agent_cases.sql",
        root / "sql" / "003_agent_runtime.sql",
        root / "sql" / "004_agent_run_budgets.sql",
        root / "sql" / "005_agent_sync_runtime.sql",
        root / "sql" / "006_proactive_agent_cases.sql",
        root / "sql" / "007_finding_observation_ordering.sql",
    ]
    analysis_migration = root / "sql" / "008_rental_readiness_analysis.sql"
    schema_name = f"test_agent_phase3_{uuid4().hex}"
    with (
        psycopg.connect(get_settings().AI_DATABASE_URL, row_factory=dict_row) as connection,
        connection.transaction(),
    ):
        connection.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema_name)))
        connection.execute(
            sql.SQL("SET LOCAL search_path TO {}, public").format(sql.Identifier(schema_name))
        )
        for migration in migrations:
            connection.execute(migration.read_text(encoding="utf-8"), prepare=False)
        migration_sql = analysis_migration.read_text(encoding="utf-8")
        connection.execute(migration_sql, prepare=False)
        connection.execute(migration_sql, prepare=False)
        indexes = {
            row["indexname"]
            for row in connection.execute(
                "SELECT indexname FROM pg_indexes WHERE schemaname = %s", (schema_name,)
            ).fetchall()
        }
        assert "agent_case_analyses_active_case_idx" in indexes
        connection.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema_name)))


def test_order_preparation_delay_migration_is_rerunnable_and_allows_null_references() -> None:
    root = Path(__file__).resolve().parents[1]
    migrations = [
        root / "sql" / f"{number:03d}_{name}.sql"
        for number, name in [
            (2, "agent_cases"),
            (3, "agent_runtime"),
            (4, "agent_run_budgets"),
            (5, "agent_sync_runtime"),
            (6, "proactive_agent_cases"),
            (7, "finding_observation_ordering"),
            (8, "rental_readiness_analysis"),
            (9, "rental_readiness_execution"),
        ]
    ]
    migration = root / "sql" / "010_order_preparation_delay.sql"
    schema_name = f"test_agent_case3_{uuid4().hex}"
    with (
        psycopg.connect(get_settings().AI_DATABASE_URL, row_factory=dict_row) as connection,
        connection.transaction(),
    ):
        connection.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema_name)))
        connection.execute(
            sql.SQL("SET LOCAL search_path TO {}, public").format(sql.Identifier(schema_name))
        )
        for item in migrations:
            connection.execute(item.read_text(encoding="utf-8"), prepare=False)
        migration_sql = migration.read_text(encoding="utf-8")
        connection.execute(migration_sql, prepare=False)
        connection.execute(migration_sql, prepare=False)
        nullable = {
            row["column_name"]: row["is_nullable"]
            for row in connection.execute(
                """
                SELECT column_name, is_nullable FROM information_schema.columns
                WHERE table_schema = %s AND table_name = 'agent_findings'
                  AND column_name IN ('affected_entity_id', 'unit_id')
                """,
                (schema_name,),
            ).fetchall()
        }
        assert nullable == {"affected_entity_id": "YES", "unit_id": "YES"}
        connection.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema_name)))


def test_overdue_return_migration_is_rerunnable_and_adds_operational_case_type() -> None:
    root = Path(__file__).resolve().parents[1]
    migrations = [
        root / "sql" / f"{number:03d}_{name}.sql"
        for number, name in [
            (2, "agent_cases"),
            (3, "agent_runtime"),
            (4, "agent_run_budgets"),
            (5, "agent_sync_runtime"),
            (6, "proactive_agent_cases"),
            (7, "finding_observation_ordering"),
            (8, "rental_readiness_analysis"),
            (9, "rental_readiness_execution"),
            (10, "order_preparation_delay"),
        ]
    ]
    migration = root / "sql" / "011_rental_return_overdue.sql"
    schema_name = f"test_agent_case4_{uuid4().hex}"
    with (
        psycopg.connect(get_settings().AI_DATABASE_URL, row_factory=dict_row) as connection,
        connection.transaction(),
    ):
        connection.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema_name)))
        connection.execute(
            sql.SQL("SET LOCAL search_path TO {}, public").format(sql.Identifier(schema_name))
        )
        for item in migrations:
            connection.execute(item.read_text(encoding="utf-8"), prepare=False)
        migration_sql = migration.read_text(encoding="utf-8")
        connection.execute(migration_sql, prepare=False)
        connection.execute(migration_sql, prepare=False)
        case_id = uuid4()
        connection.execute(
            "INSERT INTO agent_cases "
            "(id, audiences, state, origin, case_type, branch_id) "
            "VALUES (%s, %s, 'NEW', 'SYSTEM', 'RENTAL_RETURN', %s)",
            (case_id, ["staff_internal"], uuid4()),
        )
        row = connection.execute(
            "SELECT case_type FROM agent_cases WHERE id = %s", (case_id,)
        ).fetchone()
        assert row == {"case_type": "RENTAL_RETURN"}
        connection.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema_name)))


def test_readiness_execution_migration_is_rerunnable() -> None:
    root = Path(__file__).resolve().parents[1]
    migrations = [
        root / "sql" / "002_agent_cases.sql",
        root / "sql" / "003_agent_runtime.sql",
        root / "sql" / "004_agent_run_budgets.sql",
        root / "sql" / "005_agent_sync_runtime.sql",
        root / "sql" / "006_proactive_agent_cases.sql",
        root / "sql" / "007_finding_observation_ordering.sql",
        root / "sql" / "008_rental_readiness_analysis.sql",
    ]
    execution_migration = root / "sql" / "009_rental_readiness_execution.sql"
    schema_name = f"test_agent_phase4_{uuid4().hex}"
    with (
        psycopg.connect(get_settings().AI_DATABASE_URL, row_factory=dict_row) as connection,
        connection.transaction(),
    ):
        connection.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema_name)))
        connection.execute(
            sql.SQL("SET LOCAL search_path TO {}, public").format(sql.Identifier(schema_name))
        )
        for migration in migrations:
            connection.execute(migration.read_text(encoding="utf-8"), prepare=False)
        migration_sql = execution_migration.read_text(encoding="utf-8")
        connection.execute(migration_sql, prepare=False)
        connection.execute(migration_sql, prepare=False)

        columns = {
            row["column_name"]
            for row in connection.execute(
                """
                SELECT column_name FROM information_schema.columns
                WHERE table_schema = %s AND table_name = 'agent_confirmations'
                """,
                (schema_name,),
            ).fetchall()
        }
        indexes = {
            row["indexname"]
            for row in connection.execute(
                "SELECT indexname FROM pg_indexes WHERE schemaname = %s", (schema_name,)
            ).fetchall()
        }
        assert {
            "analysis_id",
            "option_id",
            "prepared_from_case_version",
        } <= columns
        assert "agent_confirmations_pending_readiness_option_idx" in indexes
        connection.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema_name)))


def test_capacity_migration_is_rerunnable_and_adds_branch_level_case_type() -> None:
    root = Path(__file__).resolve().parents[1]
    migrations = [
        root / "sql" / f"{number:03d}_{name}.sql"
        for number, name in [
            (2, "agent_cases"),
            (3, "agent_runtime"),
            (4, "agent_run_budgets"),
            (5, "agent_sync_runtime"),
            (6, "proactive_agent_cases"),
            (7, "finding_observation_ordering"),
            (8, "rental_readiness_analysis"),
            (9, "rental_readiness_execution"),
            (10, "order_preparation_delay"),
            (11, "rental_return_overdue"),
        ]
    ]
    migration = root / "sql" / "012_operational_capacity_shortfall.sql"
    schema_name = f"test_agent_case5_{uuid4().hex}"
    with (
        psycopg.connect(get_settings().AI_DATABASE_URL, row_factory=dict_row) as connection,
        connection.transaction(),
    ):
        connection.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema_name)))
        connection.execute(
            sql.SQL("SET LOCAL search_path TO {}, public").format(sql.Identifier(schema_name))
        )
        for item in migrations:
            connection.execute(item.read_text(encoding="utf-8"), prepare=False)
        migration_sql = migration.read_text(encoding="utf-8")
        connection.execute(migration_sql, prepare=False)
        connection.execute(migration_sql, prepare=False)
        branch_id = uuid4()
        case_id = uuid4()
        connection.execute(
            "INSERT INTO agent_cases "
            "(id, audiences, state, origin, case_type, branch_id) "
            "VALUES (%s, %s, 'NEW', 'SYSTEM', 'OPERATIONAL_CAPACITY', %s)",
            (case_id, ["staff_internal"], branch_id),
        )
        connection.execute(
            "INSERT INTO agent_findings "
            "(case_id, rule_code, rule_version, dedupe_key, branch_id, primary_entity_id, "
            " affected_entity_id, unit_id, window_start, window_end, severity, evidence, "
            " source_observed_at) "
            "VALUES (%s, 'OPERATIONAL_CAPACITY_SHORTFALL', 'v1', %s, %s, %s, NULL, NULL, "
            " now(), now() + interval '4 hours', 'HIGH', '{}'::jsonb, now())",
            (case_id, f"capacity:{case_id}", branch_id, branch_id),
        )
        row = connection.execute(
            "SELECT case_type FROM agent_cases WHERE id = %s", (case_id,)
        ).fetchone()
        assert row == {"case_type": "OPERATIONAL_CAPACITY"}
        connection.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema_name)))
