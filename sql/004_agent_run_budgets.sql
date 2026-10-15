ALTER TABLE agent_runs
  ADD COLUMN IF NOT EXISTS step_count INTEGER NOT NULL DEFAULT 0;

CREATE INDEX IF NOT EXISTS agent_runs_case_budget_idx
  ON agent_runs (case_id, status);
