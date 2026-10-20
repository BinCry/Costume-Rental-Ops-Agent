ALTER TABLE agent_findings
  ADD COLUMN IF NOT EXISTS source_observed_at TIMESTAMPTZ(6);

UPDATE agent_findings
SET source_observed_at = last_detected_at
WHERE source_observed_at IS NULL;

ALTER TABLE agent_findings
  ALTER COLUMN source_observed_at SET NOT NULL;

CREATE INDEX IF NOT EXISTS agent_findings_rule_status_observed_idx
  ON agent_findings (rule_code, status, source_observed_at, id);
