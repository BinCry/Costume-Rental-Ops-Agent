-- Existing cases remain without a branch and are deliberately inaccessible through
-- branch-scoped requests. Do not guess a branch for historical cases.
ALTER TABLE agent_cases
  ADD COLUMN IF NOT EXISTS branch_id UUID;

CREATE INDEX IF NOT EXISTS agent_cases_actor_branch_updated_idx
  ON agent_cases (actor_id, branch_id, updated_at DESC);
