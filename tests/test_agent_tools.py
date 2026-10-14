import json
from uuid import uuid4

import httpx
import pytest
from pydantic import ValidationError

from app.agent_tools.client import AgentToolClient, ToolInvocationError
from app.agent_tools.models import AgentCaseState, AgentToolExecutionRequest, ToolExecutionStatus
from app.agent_tools.runtime import answer_agent_message
from app.agent_tools.state import can_transition, is_terminal, require_transition
from app.errors import AppError
from app.models import ActorContext, KnowledgeAnswer


def invocation() -> AgentToolExecutionRequest:
    return AgentToolExecutionRequest(
        case_id=uuid4(),
        tool_call_id=uuid4(),
        tool_name="get_rental_order",
        arguments={"orderId": "order-1"},
        expected_version=7,
        idempotency_key="case-1:call-1",
    )


def test_tool_call_model_rejects_arbitrary_route_shape() -> None:
    with pytest.raises(ValidationError):
        AgentToolExecutionRequest(
            case_id=uuid4(),
            tool_call_id=uuid4(),
            tool_name="../../payments",
            idempotency_key="call-1",
        )


def test_case_transitions_are_explicit_and_terminal_states_cannot_resume() -> None:
    assert can_transition(AgentCaseState.NEW, AgentCaseState.ANALYZING)
    assert not can_transition(AgentCaseState.SUCCEEDED, AgentCaseState.ANALYZING)
    assert is_terminal(AgentCaseState.SUCCEEDED)

    with pytest.raises(AppError) as error:
        require_transition(AgentCaseState.SUCCEEDED, AgentCaseState.ANALYZING)
    assert error.value.code == "INVALID_CASE_TRANSITION"


@pytest.mark.asyncio
async def test_client_sends_only_fixed_internal_endpoint_and_trusted_headers() -> None:
    seen: dict[str, object] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["headers"] = request.headers
        seen["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "status": "ok",
                "data": {"orderId": "order-1"},
                "source": "studio-api",
                "requestId": "request-1",
                "recordVersion": 7,
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="http://studio.test")
    tool_client = AgentToolClient(base_url="http://studio.test", service_key="key", client=client)

    result = await tool_client.execute(
        actor_id="staff-1",
        request_id="request-1",
        invocation=invocation(),
    )

    assert result.status is ToolExecutionStatus.OK
    assert seen["url"] == "http://studio.test/api/v1/internal/agent-tools/execute"
    headers = seen["headers"]
    assert isinstance(headers, httpx.Headers)
    assert headers["X-AI-Service-Key"] == "key"
    assert headers["X-Actor-Id"] == "staff-1"
    assert headers["X-Agent-Tools-Contract"] == "agent-tools/v1"
    body = seen["body"]
    assert isinstance(body, dict)
    assert body["toolName"] == "get_rental_order"
    await client.aclose()


@pytest.mark.asyncio
async def test_timeout_is_never_interpreted_as_a_successful_write() -> None:
    async def handler(_: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out")

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="http://studio.test")
    tool_client = AgentToolClient(base_url="http://studio.test", service_key="key", client=client)

    with pytest.raises(ToolInvocationError) as error:
        await tool_client.execute(
            actor_id="staff-1",
            request_id="request-1",
            invocation=invocation(),
        )
    assert error.value.code == "TOOL_OUTCOME_UNKNOWN"
    await client.aclose()


@pytest.mark.asyncio
async def test_rag_turn_persists_only_evidence_and_uses_guarded_state_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    case_id = uuid4()
    actor_id = uuid4()
    transitions: list[AgentCaseState] = []
    persisted: dict[str, object] = {}

    async def fake_create_case(_: object, __: object) -> dict[str, object]:
        return {"id": str(case_id), "state": AgentCaseState.NEW}

    async def fake_transition(_: object, __: object, state: AgentCaseState) -> AgentCaseState:
        transitions.append(state)
        return state

    async def fake_answer(_: object, __: str, top_k: int) -> KnowledgeAnswer:
        assert top_k == 6
        return KnowledgeAnswer(
            outcome="answered",
            answer="Có thể tra cứu đơn.",
            sources=[],
            provisional=False,
        )

    async def fake_append_turn(*args: object) -> None:
        persisted["args"] = args

    monkeypatch.setattr("app.agent_tools.runtime.create_case", fake_create_case)
    monkeypatch.setattr("app.agent_tools.runtime.transition_case", fake_transition)
    monkeypatch.setattr("app.agent_tools.runtime.answer_knowledge", fake_answer)
    monkeypatch.setattr("app.agent_tools.runtime.append_turn", fake_append_turn)

    result = await answer_agent_message(
        ActorContext(user_id=str(actor_id), audiences=("customer", "shared")),
        "Tôi muốn hỏi trạng thái đơn.",
        None,
    )

    assert result.case_id == case_id
    assert result.state == AgentCaseState.SUCCEEDED
    assert transitions == [
        AgentCaseState.ANALYZING,
        AgentCaseState.PLAN_READY,
        AgentCaseState.EXECUTING,
        AgentCaseState.SUCCEEDED,
    ]
    assert persisted["args"] is not None
