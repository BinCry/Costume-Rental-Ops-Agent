"""The persisted, non-reasoning case-state transition policy."""

from collections.abc import Mapping

from app.agent_tools.models import AgentCaseState
from app.errors import AppError

_ALLOWED_TRANSITIONS: Mapping[AgentCaseState, frozenset[AgentCaseState]] = {
    AgentCaseState.NEW: frozenset(
        {AgentCaseState.ANALYZING, AgentCaseState.CANCELLED, AgentCaseState.FAILED}
    ),
    AgentCaseState.ANALYZING: frozenset(
        {
            AgentCaseState.PLAN_READY,
            AgentCaseState.INSUFFICIENT_DATA,
            AgentCaseState.HANDED_OFF,
            AgentCaseState.FAILED,
            AgentCaseState.CANCELLED,
        }
    ),
    AgentCaseState.PLAN_READY: frozenset(
        {
            AgentCaseState.EXECUTING,
            AgentCaseState.WAITING_CONFIRMATION,
            AgentCaseState.WAITING_APPROVAL,
            AgentCaseState.INSUFFICIENT_DATA,
            AgentCaseState.HANDED_OFF,
            AgentCaseState.FAILED,
            AgentCaseState.CANCELLED,
        }
    ),
    AgentCaseState.WAITING_CONFIRMATION: frozenset(
        {AgentCaseState.EXECUTING, AgentCaseState.FAILED, AgentCaseState.CANCELLED}
    ),
    AgentCaseState.WAITING_APPROVAL: frozenset(
        {AgentCaseState.EXECUTING, AgentCaseState.FAILED, AgentCaseState.CANCELLED}
    ),
    AgentCaseState.EXECUTING: frozenset(
        {
            AgentCaseState.MONITORING,
            AgentCaseState.SUCCEEDED,
            AgentCaseState.HANDED_OFF,
            AgentCaseState.FAILED,
        }
    ),
    AgentCaseState.MONITORING: frozenset(
        {AgentCaseState.SUCCEEDED, AgentCaseState.HANDED_OFF, AgentCaseState.FAILED}
    ),
    AgentCaseState.SUCCEEDED: frozenset(),
    AgentCaseState.INSUFFICIENT_DATA: frozenset(),
    AgentCaseState.HANDED_OFF: frozenset(),
    AgentCaseState.FAILED: frozenset(),
    AgentCaseState.CANCELLED: frozenset(),
}


def is_terminal(state: AgentCaseState) -> bool:
    """Return whether a case has reached a state that cannot be resumed."""
    return not _ALLOWED_TRANSITIONS[state]


def can_transition(current: AgentCaseState, target: AgentCaseState) -> bool:
    """Return whether the exact state transition is permitted."""
    return target in _ALLOWED_TRANSITIONS[current]


def require_transition(current: AgentCaseState, target: AgentCaseState) -> None:
    """Raise a stable client error instead of allowing invalid case progression."""
    if not can_transition(current, target):
        raise AppError(
            409,
            "INVALID_CASE_TRANSITION",
            f"Cannot transition agent case from {current} to {target}",
            details={"currentState": current, "targetState": target},
        )
