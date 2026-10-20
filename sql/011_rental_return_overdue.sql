-- Distinguish overdue-return operations from pickup-readiness operations while
-- keeping both in the same branch-scoped queue and claim workflow.

ALTER TABLE agent_cases
  DROP CONSTRAINT IF EXISTS agent_cases_type_check,
  DROP CONSTRAINT IF EXISTS agent_cases_readiness_branch_check,
  DROP CONSTRAINT IF EXISTS agent_cases_operational_branch_check;

ALTER TABLE agent_cases
  ADD CONSTRAINT agent_cases_type_check
    CHECK (case_type IN ('INTERACTIVE', 'RENTAL_READINESS', 'RENTAL_RETURN')),
  ADD CONSTRAINT agent_cases_operational_branch_check
    CHECK (case_type = 'INTERACTIVE' OR branch_id IS NOT NULL);

DROP INDEX IF EXISTS agent_cases_branch_queue_idx;

CREATE INDEX agent_cases_branch_queue_idx
  ON agent_cases (branch_id, state, deadline_at, updated_at DESC)
  WHERE case_type IN ('RENTAL_READINESS', 'RENTAL_RETURN');

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
      rule_code IN ('ORDER_PREPARATION_DELAYED', 'RENTAL_RETURN_OVERDUE')
      AND affected_entity_id IS NULL
      AND unit_id IS NULL
    )
    OR rule_code NOT IN (
      'PREVIOUS_RENTAL_NOT_RETURNED',
      'ALLOCATED_UNIT_NOT_READY',
      'ORDER_PREPARATION_DELAYED',
      'RENTAL_RETURN_OVERDUE'
    )
  );
