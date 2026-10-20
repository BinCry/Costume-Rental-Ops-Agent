-- Case 6 is a unit-level readiness finding: both orders and the shared unit
-- are required to make the conflict explainable and safely re-checkable.

ALTER TABLE agent_findings
  DROP CONSTRAINT IF EXISTS agent_findings_entity_shape_check;

ALTER TABLE agent_findings
  ADD CONSTRAINT agent_findings_entity_shape_check CHECK (
    (
      rule_code IN (
        'PREVIOUS_RENTAL_NOT_RETURNED',
        'ALLOCATED_UNIT_NOT_READY',
        'UNIT_SCHEDULE_CONFLICT'
      )
      AND affected_entity_id IS NOT NULL
      AND unit_id IS NOT NULL
    )
    OR (
      rule_code IN (
        'ORDER_PREPARATION_DELAYED',
        'RENTAL_RETURN_OVERDUE',
        'OPERATIONAL_CAPACITY_SHORTFALL'
      )
      AND affected_entity_id IS NULL
      AND unit_id IS NULL
    )
    OR rule_code NOT IN (
      'PREVIOUS_RENTAL_NOT_RETURNED',
      'ALLOCATED_UNIT_NOT_READY',
      'UNIT_SCHEDULE_CONFLICT',
      'ORDER_PREPARATION_DELAYED',
      'RENTAL_RETURN_OVERDUE',
      'OPERATIONAL_CAPACITY_SHORTFALL'
    )
  );
