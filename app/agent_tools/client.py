"""Narrow HTTP client for the Studio allowlisted agent-tool endpoint."""

from typing import Final

import httpx
from pydantic import ValidationError

from app.agent_tools.models import (
    AGENT_TOOLS_CONTRACT_VERSION,
    AgentToolExecutionRequest,
    AgentToolExecutionResult,
    ToolExecutionStatus,
)

_EXECUTE_PATH: Final = "/api/v1/internal/agent-tools/execute"


class ToolInvocationError(Exception):
    """A transport or contract error; callers must not infer write success from it."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class AgentToolClient:
    """Call one fixed, internal Studio endpoint with trusted actor context.

    The client intentionally has no generic request method. This prevents future
    callers (including an LLM runtime) from selecting arbitrary Studio routes.
    """

    def __init__(
        self,
        *,
        base_url: str,
        service_key: str,
        timeout_seconds: float = 15,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        if not base_url.strip():
            raise ValueError("base_url is required")
        if not service_key.strip():
            raise ValueError("service_key is required")
        self._base_url = base_url.rstrip("/")
        self._service_key = service_key
        self._timeout_seconds = timeout_seconds
        self._client = client

    async def execute(
        self,
        *,
        actor_id: str,
        request_id: str,
        invocation: AgentToolExecutionRequest,
    ) -> AgentToolExecutionResult:
        """Execute a registered tool; unknown transport outcomes are never retried here."""
        if not actor_id.strip() or actor_id == "guest":
            raise ToolInvocationError("INVALID_ACTOR", "An authenticated actor is required")
        if not request_id.strip():
            raise ToolInvocationError("INVALID_REQUEST_ID", "request_id is required")

        headers = {
            "X-AI-Service-Key": self._service_key,
            "X-Actor-Id": actor_id,
            "X-Request-Id": request_id,
            "X-Agent-Tools-Contract": AGENT_TOOLS_CONTRACT_VERSION,
        }
        payload = invocation.model_dump(mode="json", by_alias=True)

        if self._client is not None:
            return await self._post(self._client, headers, payload)

        timeout = httpx.Timeout(self._timeout_seconds)
        async with httpx.AsyncClient(base_url=self._base_url, timeout=timeout) as client:
            return await self._post(client, headers, payload)

    async def _post(
        self,
        client: httpx.AsyncClient,
        headers: dict[str, str],
        payload: dict[str, object],
    ) -> AgentToolExecutionResult:
        try:
            response = await client.post(_EXECUTE_PATH, headers=headers, json=payload)
        except httpx.TimeoutException as error:
            raise ToolInvocationError(
                "TOOL_OUTCOME_UNKNOWN", "Studio tool request timed out; outcome is unknown"
            ) from error
        except httpx.HTTPError as error:
            raise ToolInvocationError(
                "TOOL_DEPENDENCY_UNAVAILABLE", "Studio tool API is unavailable"
            ) from error

        if response.status_code >= 500:
            raise ToolInvocationError(
                "TOOL_DEPENDENCY_UNAVAILABLE", "Studio tool API is unavailable"
            )

        try:
            body = response.json()
        except ValueError as error:
            raise ToolInvocationError(
                "TOOL_PROTOCOL_ERROR", "Studio tool API returned invalid JSON"
            ) from error

        if not isinstance(body, dict):
            raise ToolInvocationError(
                "TOOL_PROTOCOL_ERROR", "Studio tool API returned an invalid response"
            )

        # Studio's public envelope nests a successful result in ``data``;
        # the internal endpoint may also return the tool result directly.
        result_body = body.get("data") if body.get("success") is True else body
        try:
            result = AgentToolExecutionResult.model_validate(result_body)
        except ValidationError as error:
            raise ToolInvocationError(
                "TOOL_PROTOCOL_ERROR", "Studio tool API returned an invalid contract"
            ) from error

        if response.status_code >= 400 and result.status is ToolExecutionStatus.OK:
            raise ToolInvocationError(
                "TOOL_PROTOCOL_ERROR", "Studio tool API returned inconsistent status"
            )
        return result
