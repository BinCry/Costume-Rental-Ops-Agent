# Agent termination verification

## Context

Read-agent completion was verified after the LangGraph ReAct loop, but a successful
`GraphTurn` represented termination implicitly with `termination_reason=None`.

## What happened

- Added invariants to `CompletionVerification`: success cannot carry a failure reason,
  and failure must carry a reason.
- Successful graph completion now records `GOAL_ACHIEVED` explicitly.
- Runtime treats only non-success reasons as handoff conditions.
- Successful turns do not generate handoff context.
- Added graph and runtime integration coverage for the explicit success path.

## Reflection

An explicit terminal reason removes the need for callers to infer success from a
combination of nullable fields. Verification remains deterministic and outside model
control; failed verification stops safely instead of triggering an unbounded retry.

## Decisions

- Keep read-loop retries bounded by LangGraph and `ExecutionGuard`.
- Do not automatically re-run a failed final answer in this scope.
- Keep write confirmation and approval in the separate durable workflow.

## Next

- Consider file-backed skill loading only as a separate configuration change.
