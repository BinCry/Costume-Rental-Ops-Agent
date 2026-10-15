"""Durable outer LangGraph for human-gated write workflows.

The ReAct graph in :mod:`graph` decides how to answer read requests.  This
graph owns the write lifecycle: it pauses before every human decision and only
runs deterministic side effects after LangGraph has been resumed.
"""

from collections.abc import Awaitable, Callable
from typing import Any, Literal, TypedDict, cast

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Command, interrupt

from app.agent_tools.graph import _ensure_checkpoint_tables
from app.config import get_settings


class WriteWorkflowState(TypedDict, total=False):
    case_id: str
    entry_gate: Literal["confirmation", "approval"]
    owner_actor: dict[str, Any]
    confirmation_id: str
    confirmation_snapshot: dict[str, Any]
    approval_id: str
    approval_snapshot: dict[str, Any]
    decision: dict[str, Any]
    next_gate: Literal["approval", "done"]
    workflow_status: str
    message: str


WriteHandler = Callable[[WriteWorkflowState], Awaitable[dict[str, Any]]]


def build_write_workflow(
    *,
    checkpointer: BaseCheckpointSaver[Any],
    after_confirmation: WriteHandler,
    after_approval: WriteHandler,
) -> CompiledStateGraph[WriteWorkflowState, None, WriteWorkflowState, WriteWorkflowState]:
    """Compile the write graph with side-effect handlers supplied by runtime."""

    def entry_route(state: WriteWorkflowState) -> str:
        return state.get("entry_gate", "confirmation")

    def confirmation_gate(state: WriteWorkflowState) -> dict[str, Any]:
        decision = interrupt(
            {
                "kind": "confirmation",
                "caseId": state["case_id"],
                "confirmationId": state["confirmation_id"],
                "action": state["confirmation_snapshot"],
            }
        )
        if not isinstance(decision, dict):
            raise ValueError("Confirmation resume payload must be an object")
        return {"decision": decision}

    def approval_gate(state: WriteWorkflowState) -> dict[str, Any]:
        decision = interrupt(
            {
                "kind": "approval",
                "caseId": state["case_id"],
                "approvalId": state["approval_id"],
                "action": state["approval_snapshot"],
            }
        )
        if not isinstance(decision, dict):
            raise ValueError("Approval resume payload must be an object")
        return {"decision": decision}

    def after_confirmation_route(state: WriteWorkflowState) -> str:
        return "approval" if state.get("next_gate") == "approval" else "done"

    builder = StateGraph(WriteWorkflowState)
    builder.add_node("confirmation_gate", confirmation_gate)
    builder.add_node("apply_confirmation", cast(Any, after_confirmation))
    builder.add_node("approval_gate", approval_gate)
    builder.add_node("apply_approval", cast(Any, after_approval))
    builder.add_conditional_edges(
        START,
        entry_route,
        {"confirmation": "confirmation_gate", "approval": "approval_gate"},
    )
    builder.add_edge("confirmation_gate", "apply_confirmation")
    builder.add_conditional_edges(
        "apply_confirmation",
        after_confirmation_route,
        {"approval": "approval_gate", "done": END},
    )
    builder.add_edge("approval_gate", "apply_approval")
    builder.add_edge("apply_approval", END)
    return builder.compile(checkpointer=checkpointer, name="agent-write-workflow")


async def run_write_workflow(
    *,
    case_id: str,
    value: WriteWorkflowState | Command[Any],
    after_confirmation: WriteHandler,
    after_approval: WriteHandler,
    bootstrap_state: WriteWorkflowState | None = None,
) -> dict[str, Any]:
    """Start or resume a durable workflow, bootstrapping pre-graph cases safely."""
    settings = get_settings()
    config: RunnableConfig = {
        "configurable": {
            "thread_id": case_id,
            "checkpoint_ns": "agent-write-workflow",
        }
    }
    async with AsyncPostgresSaver.from_conn_string(settings.AI_DATABASE_URL) as checkpointer:
        await _ensure_checkpoint_tables(checkpointer)
        workflow = build_write_workflow(
            checkpointer=checkpointer,
            after_confirmation=after_confirmation,
            after_approval=after_approval,
        )
        if isinstance(value, Command):
            snapshot = await workflow.aget_state(config)
            if not snapshot.next:
                if bootstrap_state is None:
                    raise RuntimeError("Write workflow checkpoint is missing")
                await workflow.ainvoke(bootstrap_state, config=config)
        result = await workflow.ainvoke(value, config=config)
    return dict(result)
