"""Safe primitives for calling allowlisted Studio agent tools.

This package deliberately contains no LLM orchestration.  The Studio API stays
the authorization and execution authority for every business operation.
"""

from app.agent_tools.client import AgentToolClient, ToolInvocationError
from app.agent_tools.models import (
    AgentCaseState,
    AgentToolExecutionRequest,
    AgentToolExecutionResult,
    ToolExecutionStatus,
)
from app.agent_tools.state import can_transition, require_transition

__all__ = [
    "AgentCaseState",
    "AgentToolClient",
    "AgentToolExecutionRequest",
    "AgentToolExecutionResult",
    "ToolExecutionStatus",
    "ToolInvocationError",
    "can_transition",
    "require_transition",
]
