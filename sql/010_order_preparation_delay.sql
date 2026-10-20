-- Order-level readiness findings do not point at one affected order or unit.
-- Existing unit-level findings remain unchanged.

ALTER TABLE agent_findings
  ALTER COLUMN affected_entity_id DROP NOT NULL,
  ALTER COLUMN unit_id DROP NOT NULL;

ALTER TABLE agent_findings
  DROP CONSTRAINT IF EXISTS agent_findings_entity_shape_check;

ALTER TABLE agent_findings
  ADD CONSTRAINT agent_findings_entity_shape_check CHECK (
    (
      rule_code IN ('PREVIOUS_RENTAL_NOT_RETURNED', 'ALLOCATED_UNIT_NOT_READY')
      AND affected_entity_id IS NOT NULL
      AND unit_id IS NOT NULL
    )
    OR (
      rule_code = 'ORDER_PREPARATION_DELAYED'
      AND affected_entity_id IS NULL
      AND unit_id IS NULL
    )
    OR rule_code NOT IN (
      'PREVIOUS_RENTAL_NOT_RETURNED',
      'ALLOCATED_UNIT_NOT_READY',
      'ORDER_PREPARATION_DELAYED'
    )
  );
