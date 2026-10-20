-- Link frozen operational confirmations to the immutable recommendation that
-- produced them. Interactive confirmations intentionally keep these nullable.
ALTER TABLE agent_confirmations
  ADD COLUMN IF NOT EXISTS analysis_id UUID REFERENCES agent_case_analyses(id) ON DELETE SET NULL,
  ADD COLUMN IF NOT EXISTS option_id VARCHAR(128),
  ADD COLUMN IF NOT EXISTS prepared_from_case_version INTEGER;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'agent_confirmations_readiness_link_check'
  ) THEN
    ALTER TABLE agent_confirmations
      ADD CONSTRAINT agent_confirmations_readiness_link_check CHECK (
        (analysis_id IS NULL AND option_id IS NULL AND prepared_from_case_version IS NULL)
        OR
        (analysis_id IS NOT NULL AND option_id IS NOT NULL AND prepared_from_case_version IS NOT NULL)
      );
  END IF;
END $$;

CREATE UNIQUE INDEX IF NOT EXISTS agent_confirmations_pending_readiness_option_idx
  ON agent_confirmations (case_id, analysis_id, option_id)
  WHERE status = 'PENDING' AND analysis_id IS NOT NULL;
