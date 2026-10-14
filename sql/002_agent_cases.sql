CREATE TABLE IF NOT EXISTS agent_cases (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  actor_id UUID NOT NULL,
  audiences TEXT[] NOT NULL,
  state VARCHAR(32) NOT NULL,
  created_at TIMESTAMPTZ(6) NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ(6) NOT NULL DEFAULT now(),
  completed_at TIMESTAMPTZ(6),
  CONSTRAINT agent_cases_state_check CHECK (
    state IN (
      'NEW', 'ANALYZING', 'PLAN_READY', 'WAITING_CONFIRMATION',
      'WAITING_APPROVAL', 'EXECUTING', 'MONITORING', 'SUCCEEDED',
      'INSUFFICIENT_DATA', 'HANDED_OFF', 'FAILED', 'CANCELLED'
    )
  )
);

CREATE INDEX IF NOT EXISTS agent_cases_actor_updated_idx
  ON agent_cases (actor_id, updated_at DESC);

CREATE TABLE IF NOT EXISTS agent_messages (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  case_id UUID NOT NULL REFERENCES agent_cases(id) ON DELETE CASCADE,
  role VARCHAR(16) NOT NULL CHECK (role IN ('user', 'assistant')),
  content TEXT NOT NULL,
  created_at TIMESTAMPTZ(6) NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS agent_messages_case_created_idx
  ON agent_messages (case_id, created_at);

CREATE TABLE IF NOT EXISTS agent_steps (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  case_id UUID NOT NULL REFERENCES agent_cases(id) ON DELETE CASCADE,
  step_index INTEGER NOT NULL,
  kind VARCHAR(32) NOT NULL,
  status VARCHAR(32) NOT NULL,
  summary TEXT NOT NULL,
  created_at TIMESTAMPTZ(6) NOT NULL DEFAULT now(),
  CONSTRAINT agent_steps_case_index_key UNIQUE (case_id, step_index)
);

CREATE TABLE IF NOT EXISTS agent_tool_calls (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  case_id UUID NOT NULL REFERENCES agent_cases(id) ON DELETE CASCADE,
  tool_call_id UUID NOT NULL UNIQUE,
  tool_name VARCHAR(80) NOT NULL,
  status VARCHAR(32) NOT NULL,
  request_id UUID,
  idempotency_key VARCHAR(255) NOT NULL,
  outcome JSONB,
  created_at TIMESTAMPTZ(6) NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ(6) NOT NULL DEFAULT now(),
  CONSTRAINT agent_tool_calls_case_idempotency_key UNIQUE (case_id, idempotency_key)
);

CREATE TABLE IF NOT EXISTS agent_evidence (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  case_id UUID NOT NULL REFERENCES agent_cases(id) ON DELETE CASCADE,
  source_type VARCHAR(32) NOT NULL,
  source_id TEXT NOT NULL,
  citation TEXT,
  observed_at TIMESTAMPTZ(6),
  payload JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ(6) NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS agent_evidence_case_idx ON agent_evidence (case_id);
