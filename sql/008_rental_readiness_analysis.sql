-- Immutable audit trail for deterministic readiness recommendations.
CREATE TABLE IF NOT EXISTS agent_case_analyses (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  case_id UUID NOT NULL REFERENCES agent_cases(id) ON DELETE CASCADE,
  finding_id UUID NOT NULL REFERENCES agent_findings(id) ON DELETE CASCADE,
  created_by_actor_id UUID NOT NULL,
  case_version_at_start INTEGER NOT NULL CHECK (case_version_at_start > 0),
  finding_source_observed_at TIMESTAMPTZ(6) NOT NULL,
  simulator_version VARCHAR(64) NOT NULL,
  ranking_policy_version VARCHAR(64) NOT NULL,
  status VARCHAR(16) NOT NULL DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE', 'STALE')),
  outcome VARCHAR(32) NOT NULL CHECK (outcome IN ('READY', 'NO_FEASIBLE_OPTION')),
  snapshot JSONB NOT NULL,
  options JSONB NOT NULL,
  recommended_option_id VARCHAR(128),
  narrative JSONB NOT NULL,
  created_at TIMESTAMPTZ(6) NOT NULL DEFAULT now(),
  invalidated_at TIMESTAMPTZ(6),
  CONSTRAINT agent_case_analyses_stale_at_check CHECK (
    (status = 'ACTIVE' AND invalidated_at IS NULL)
    OR (status = 'STALE' AND invalidated_at IS NOT NULL)
  )
);

CREATE UNIQUE INDEX IF NOT EXISTS agent_case_analyses_active_case_idx
  ON agent_case_analyses (case_id)
  WHERE status = 'ACTIVE';

CREATE INDEX IF NOT EXISTS agent_case_analyses_case_created_idx
  ON agent_case_analyses (case_id, created_at DESC);
