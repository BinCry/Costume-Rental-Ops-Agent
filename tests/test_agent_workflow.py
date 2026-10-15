from typing import Any

import pytest
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command, Interrupt

from app.agent_tools.workflow import WriteWorkflowState, build_write_workflow


def config(case_id: str) -> RunnableConfig:
    return {
        "configurable": {
            "thread_id": case_id,
            "checkpoint_ns": "agent-write-workflow",
        }
    }


@pytest.mark.asyncio
async def test_confirmation_interrupt_precedes_side_effect() -> None:
    calls: list[str] = []

    async def after_confirmation(state: WriteWorkflowState) -> dict[str, Any]:
        calls.append("confirmation")
        assert state["decision"]["approve"] is True
        return {"next_gate": "done", "workflow_status": "SUCCEEDED"}

    async def after_approval(_: WriteWorkflowState) -> dict[str, Any]:
        raise AssertionError("approval handler must not run")

    graph = build_write_workflow(
        checkpointer=MemorySaver(),
        after_confirmation=after_confirmation,
        after_approval=after_approval,
    )
    initial = WriteWorkflowState(
        case_id="case-1",
        entry_gate="confirmation",
        owner_actor={"user_id": "actor-1", "audiences": ["shared"]},
        confirmation_id="confirmation-1",
        confirmation_snapshot={"toolName": "cancel_rental_order"},
    )
    paused = await graph.ainvoke(initial, config=config("case-1"))

    assert calls == []
    interrupts = paused["__interrupt__"]
    assert isinstance(interrupts[0], Interrupt)
    assert interrupts[0].value["kind"] == "confirmation"

    completed = await graph.ainvoke(
        Command(
            resume={
                "kind": "confirmation",
                "decisionId": "confirmation-1",
                "approve": True,
            }
        ),
        config=config("case-1"),
    )

    assert calls == ["confirmation"]
    assert completed["workflow_status"] == "SUCCEEDED"


@pytest.mark.asyncio
async def test_confirmation_can_pause_again_for_approval() -> None:
    calls: list[str] = []

    async def after_confirmation(_: WriteWorkflowState) -> dict[str, Any]:
        calls.append("confirmation")
        return {
            "next_gate": "approval",
            "workflow_status": "WAITING_APPROVAL",
            "approval_id": "approval-1",
            "approval_snapshot": {"toolName": "request_refund"},
        }

    async def after_approval(state: WriteWorkflowState) -> dict[str, Any]:
        calls.append("approval")
        assert state["decision"]["decisionId"] == "approval-1"
        return {"next_gate": "done", "workflow_status": "SUCCEEDED"}

    graph = build_write_workflow(
        checkpointer=MemorySaver(),
        after_confirmation=after_confirmation,
        after_approval=after_approval,
    )
    initial = WriteWorkflowState(
        case_id="case-2",
        entry_gate="confirmation",
        owner_actor={"user_id": "actor-1", "audiences": ["shared"]},
        confirmation_id="confirmation-2",
        confirmation_snapshot={"toolName": "request_refund"},
    )
    await graph.ainvoke(initial, config=config("case-2"))
    awaiting_approval = await graph.ainvoke(
        Command(
            resume={
                "kind": "confirmation",
                "decisionId": "confirmation-2",
                "approve": True,
            }
        ),
        config=config("case-2"),
    )

    assert calls == ["confirmation"]
    assert awaiting_approval["__interrupt__"][0].value["kind"] == "approval"
    completed = await graph.ainvoke(
        Command(
            resume={
                "kind": "approval",
                "decisionId": "approval-1",
                "approve": True,
            }
        ),
        config=config("case-2"),
    )

    assert calls == ["confirmation", "approval"]
    assert completed["workflow_status"] == "SUCCEEDED"
