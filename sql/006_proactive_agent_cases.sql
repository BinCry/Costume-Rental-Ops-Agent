-- Proactive, branch-scoped Agent Cases and deduplicated operational findings.

DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = current_schema()
      AND table_name = 'agent_cases' AND column_name = 'actor_id'
  ) AND NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = current_schema()
      AND table_name = 'agent_cases' AND column_name = 'owner_actor_id'
  ) THEN
    ALTER TABLE agent_cases RENAME COLUMN actor_id TO owner_actor_id;
  END IF;
END $$;

ALTER TABLE agent_cases
  ALTER COLUMN owner_actor_id DROP NOT NULL,
  ADD COLUMN IF NOT EXISTS created_by_actor_id UUID,
  ADD COLUMN IF NOT EXISTS origin VARCHAR(16) NOT NULL DEFAULT 'USER',
  ADD COLUMN IF NOT EXISTS case_type VARCHAR(32) NOT NULL DEFAULT 'INTERACTIVE',
  ADD COLUMN IF NOT EXISTS branch_id UUID,
  ADD COLUMN IF NOT EXISTS claimed_at TIMESTAMPTZ(6),
  ADD COLUMN IF NOT EXISTS deadline_at TIMESTAMPTZ(6);

UPDATE agent_cases
SET created_by_actor_id = owner_actor_id
WHERE created_by_actor_id IS NULL AND owner_actor_id IS NOT NULL;

ALTER TABLE agent_cases
  DROP CONSTRAINT IF EXISTS agent_cases_origin_check,
  DROP CONSTRAINT IF EXISTS agent_cases_type_check,
  DROP CONSTRAINT IF EXISTS agent_cases_user_owner_check,
  DROP CONSTRAINT IF EXISTS agent_cases_system_branch_check,
  DROP CONSTRAINT IF EXISTS agent_cases_readiness_branch_check;

ALTER TABLE agent_cases
  ADD CONSTRAINT agent_cases_origin_check
    CHECK (origin IN ('USER', 'SYSTEM')),
  ADD CONSTRAINT agent_cases_type_check
    CHECK (case_type IN ('INTERACTIVE', 'RENTAL_READINESS')),
  ADD CONSTRAINT agent_cases_user_owner_check
    CHECK (origin <> 'USER' OR (owner_actor_id IS NOT NULL AND created_by_actor_id IS NOT NULL)),
  ADD CONSTRAINT agent_cases_system_branch_check
    CHECK (origin <> 'SYSTEM' OR branch_id IS NOT NULL),
  ADD CONSTRAINT agent_cases_readiness_branch_check
    CHECK (case_type <> 'RENTAL_READINESS' OR branch_id IS NOT NULL);

DROP INDEX IF EXISTS agent_cases_actor_updated_idx;

CREATE INDEX IF NOT EXISTS agent_cases_owner_updated_idx
  ON agent_cases (owner_actor_id, updated_at DESC);

CREATE INDEX IF NOT EXISTS agent_cases_branch_queue_idx
  ON agent_cases (branch_id, state, deadline_at, updated_at DESC)
  WHERE case_type = 'RENTAL_READINESS';

CREATE TABLE IF NOT EXISTS agent_findings (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  case_id UUID NOT NULL UNIQUE REFERENCES agent_cases(id) ON DELETE CASCADE,
  rule_code VARCHAR(100) NOT NULL,
  rule_version VARCHAR(50) NOT NULL,
  dedupe_key VARCHAR(255) NOT NULL,
  branch_id UUID NOT NULL,
  primary_entity_id UUID NOT NULL,
  affected_entity_id UUID NOT NULL,
  unit_id UUID NOT NULL,
  window_start TIMESTAMPTZ(6) NOT NULL,
  window_end TIMESTAMPTZ(6) NOT NULL,
  severity VARCHAR(16) NOT NULL CHECK (severity IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')),
  status VARCHAR(16) NOT NULL DEFAULT 'OPEN' CHECK (status IN ('OPEN', 'RESOLVED')),
  evidence JSONB NOT NULL DEFAULT '{}'::jsonb,
  first_detected_at TIMESTAMPTZ(6) NOT NULL DEFAULT now(),
  last_detected_at TIMESTAMPTZ(6) NOT NULL DEFAULT now(),
  resolved_at TIMESTAMPTZ(6),
  CONSTRAINT agent_findings_window_check CHECK (window_start < window_end),
  CONSTRAINT agent_findings_resolution_check CHECK (
    (status = 'OPEN' AND resolved_at IS NULL)
    OR (status = 'RESOLVED' AND resolved_at IS NOT NULL)
  )
);

CREATE UNIQUE INDEX IF NOT EXISTS agent_findings_open_dedupe_idx
  ON agent_findings (dedupe_key)
  WHERE status = 'OPEN';

CREATE INDEX IF NOT EXISTS agent_findings_branch_status_idx
  ON agent_findings (branch_id, status, last_detected_at DESC);
