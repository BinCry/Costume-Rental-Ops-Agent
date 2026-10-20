import hashlib
from pathlib import Path

import psycopg

from app.config import get_settings

MIGRATIONS = (
    ("001_init_pgvector_python", "001_init_pgvector.sql"),
    ("002_agent_cases_python", "002_agent_cases.sql"),
    ("003_agent_runtime_python", "003_agent_runtime.sql"),
    ("004_agent_run_budgets_python", "004_agent_run_budgets.sql"),
    ("005_agent_sync_runtime_python", "005_agent_sync_runtime.sql"),
    ("006_agent_case_branch_scope_python", "006_agent_case_branch_scope.sql"),
    ("007_proactive_agent_cases_python", "006_proactive_agent_cases.sql"),
    ("008_finding_observation_ordering_python", "007_finding_observation_ordering.sql"),
    ("009_rental_readiness_analysis_python", "008_rental_readiness_analysis.sql"),
    ("010_rental_readiness_execution_python", "009_rental_readiness_execution.sql"),
    ("011_order_preparation_delay_python", "010_order_preparation_delay.sql"),
    ("012_rental_return_overdue_python", "011_rental_return_overdue.sql"),
    ("013_operational_capacity_shortfall_python", "012_operational_capacity_shortfall.sql"),
)


def main() -> None:
    settings = get_settings()
    with psycopg.connect(settings.AI_DATABASE_URL) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS knowledge_schema_migrations (
              migration_id VARCHAR(100) PRIMARY KEY,
              checksum VARCHAR(64) NOT NULL,
              applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """
        )
        sql_directory = Path(__file__).resolve().parents[1] / "sql"
        for migration_id, filename in MIGRATIONS:
            sql = (sql_directory / filename).read_text(encoding="utf-8")
            checksum = hashlib.sha256(sql.encode("utf-8")).hexdigest()
            existing = connection.execute(
                "SELECT checksum FROM knowledge_schema_migrations WHERE migration_id = %s",
                (migration_id,),
            ).fetchone()
            if existing is not None:
                if existing[0] != checksum:
                    raise RuntimeError(f"Migration checksum mismatch: {migration_id}")
                print(f"Knowledge migration already applied: {migration_id}")
                continue
            connection.execute(sql)
            connection.execute(
                "INSERT INTO knowledge_schema_migrations (migration_id, checksum) VALUES (%s, %s)",
                (migration_id, checksum),
            )
            print(f"Knowledge migration applied: {migration_id}")


if __name__ == "__main__":
    main()
