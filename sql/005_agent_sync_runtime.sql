-- Synchronous agent runtime hardening.  This migration is additive and can be
-- applied to databases that already contain the earlier agent-case schema.

ALTER TABLE agent_cases
  DROP CONSTRAINT IF EXISTS agent_cases_state_check;

ALTER TABLE agent_cases
  ADD CONSTRAINT agent_cases_state_check CHECK (
    state IN (
      'NEW', 'ANALYZING', 'PLAN_READY', 'WAITING_INPUT',
      'WAITING_CONFIRMATION', 'WAITING_APPROVAL', 'EXECUTING',
      'MONITORING', 'SUCCEEDED', 'INSUFFICIENT_DATA', 'HANDED_OFF',
      'FAILED', 'CANCELLED'
    )
  );

ALTER TABLE agent_cases
  ADD COLUMN IF NOT EXISTS active_run_id UUID,
  ADD COLUMN IF NOT EXISTS active_run_deadline TIMESTAMPTZ(6);

ALTER TABLE agent_runs
  DROP CONSTRAINT IF EXISTS agent_runs_status_check;

ALTER TABLE agent_runs
  ADD CONSTRAINT agent_runs_status_check CHECK (
    status IN ('RUNNING', 'PAUSED', 'COMPLETED', 'FAILED', 'CANCELLED')
  );

ALTER TABLE agent_runs
  ADD COLUMN IF NOT EXISTS deadline_at TIMESTAMPTZ(6),
  ADD COLUMN IF NOT EXISTS resumed_from_run_id UUID REFERENCES agent_runs(id) ON DELETE SET NULL;

CREATE UNIQUE INDEX IF NOT EXISTS agent_runs_one_active_per_case_idx
  ON agent_runs (case_id)
  WHERE status = 'RUNNING';

DROP INDEX IF EXISTS agent_runs_queue_idx;

ALTER TABLE agent_tool_calls
  ADD COLUMN IF NOT EXISTS payload_hash VARCHAR(64),
  ADD COLUMN IF NOT EXISTS expected_version INTEGER,
  ADD COLUMN IF NOT EXISTS confirmation_id UUID REFERENCES agent_confirmations(id) ON DELETE SET NULL,
  ADD COLUMN IF NOT EXISTS approval_id UUID REFERENCES agent_approvals(id) ON DELETE SET NULL,
  ADD COLUMN IF NOT EXISTS finished_at TIMESTAMPTZ(6);

ALTER TABLE agent_approvals
  ADD COLUMN IF NOT EXISTS payload_hash VARCHAR(64),
  ADD COLUMN IF NOT EXISTS required_branch_ids UUID[] NOT NULL DEFAULT '{}';

CREATE UNIQUE INDEX IF NOT EXISTS agent_confirmations_pending_snapshot_idx
  ON agent_confirmations (case_id, payload_hash)
  WHERE status = 'PENDING';

CREATE UNIQUE INDEX IF NOT EXISTS agent_approvals_pending_snapshot_idx
  ON agent_approvals (case_id, payload_hash)
  WHERE status = 'PENDING';
