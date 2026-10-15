ALTER TABLE agent_cases
  ADD COLUMN IF NOT EXISTS goal JSONB,
  ADD COLUMN IF NOT EXISTS version INTEGER NOT NULL DEFAULT 1,
  ADD COLUMN IF NOT EXISTS termination_reason VARCHAR(64),
  ADD COLUMN IF NOT EXISTS last_run_status VARCHAR(32);

CREATE TABLE IF NOT EXISTS agent_runs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  case_id UUID NOT NULL REFERENCES agent_cases(id) ON DELETE CASCADE,
  status VARCHAR(32) NOT NULL CHECK (status IN ('QUEUED', 'RUNNING', 'COMPLETED', 'FAILED')),
  input_message TEXT,
  lease_until TIMESTAMPTZ(6),
  attempt_count INTEGER NOT NULL DEFAULT 0,
  error_code VARCHAR(100),
  token_usage INTEGER NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ(6) NOT NULL DEFAULT now(),
  started_at TIMESTAMPTZ(6),
  completed_at TIMESTAMPTZ(6)
);

CREATE INDEX IF NOT EXISTS agent_runs_case_created_idx ON agent_runs (case_id, created_at DESC);
CREATE INDEX IF NOT EXISTS agent_runs_queue_idx ON agent_runs (status, created_at) WHERE status = 'QUEUED';

CREATE TABLE IF NOT EXISTS agent_confirmations (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  case_id UUID NOT NULL REFERENCES agent_cases(id) ON DELETE CASCADE,
  summary TEXT NOT NULL,
  action_snapshot JSONB NOT NULL,
  payload_hash VARCHAR(64) NOT NULL,
  status VARCHAR(32) NOT NULL DEFAULT 'PENDING' CHECK (status IN ('PENDING', 'CONFIRMED', 'REJECTED', 'EXPIRED')),
  expected_case_version INTEGER NOT NULL,
  decided_by UUID,
  decision_reason TEXT,
  expires_at TIMESTAMPTZ(6) NOT NULL,
  created_at TIMESTAMPTZ(6) NOT NULL DEFAULT now(),
  decided_at TIMESTAMPTZ(6)
);

CREATE INDEX IF NOT EXISTS agent_confirmations_case_idx ON agent_confirmations (case_id, status);

CREATE TABLE IF NOT EXISTS agent_approvals (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  case_id UUID NOT NULL REFERENCES agent_cases(id) ON DELETE CASCADE,
  confirmation_id UUID REFERENCES agent_confirmations(id) ON DELETE SET NULL,
  summary TEXT NOT NULL,
  required_permission VARCHAR(150) NOT NULL,
  risk_level VARCHAR(32) NOT NULL,
  action_snapshot JSONB NOT NULL,
  status VARCHAR(32) NOT NULL DEFAULT 'PENDING' CHECK (status IN ('PENDING', 'APPROVED', 'REJECTED', 'EXPIRED')),
  version INTEGER NOT NULL DEFAULT 1,
  decided_by UUID,
  decision_reason TEXT,
  expires_at TIMESTAMPTZ(6) NOT NULL,
  created_at TIMESTAMPTZ(6) NOT NULL DEFAULT now(),
  decided_at TIMESTAMPTZ(6)
);

CREATE INDEX IF NOT EXISTS agent_approvals_case_idx ON agent_approvals (case_id, status);
