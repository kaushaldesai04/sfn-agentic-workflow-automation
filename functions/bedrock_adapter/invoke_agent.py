from __future__ import annotations

import json
from typing import Any

from botocore.exceptions import BotoCoreError, ClientError, ReadTimeoutError

from shared.errors import (
    AgentAccessDeniedError,
    AgentServiceError,
    AgentThrottledError,
    AgentTimeoutError,
)


def invoke_agent(
    client: Any,
    *,
    agent_id: str,
    alias_id: str,
    session_id: str,
    request: dict[str, Any],
    enable_trace: bool,
) -> dict[str, Any]:
    prompt = json.dumps(
        {
            "task": "Classify, validate, and recommend routing using the required JSON schema.",
            "request": request,
        },
        separators=(",", ":"),
    )
    try:
        return client.invoke_agent(
            agentId=agent_id,
            agentAliasId=alias_id,
            sessionId=session_id,
            inputText=prompt,
            enableTrace=enable_trace,
        )
    except ReadTimeoutError as error:
        raise AgentTimeoutError("Bedrock Agent invocation timed out") from error
    except ClientError as error:
        code = error.response.get("Error", {}).get("Code", "")
        if code in {"ThrottlingException", "TooManyRequestsException"}:
            raise AgentThrottledError("Bedrock Agent throttled the invocation") from error
        if code in {"AccessDeniedException", "UnauthorizedException"}:
            raise AgentAccessDeniedError("Bedrock Agent invocation was denied") from error
        if code in {"ModelTimeoutException", "TimeoutException"}:
            raise AgentTimeoutError("Bedrock Agent invocation timed out") from error
        raise AgentServiceError(f"Bedrock Agent service error: {code or 'Unknown'}") from error
    except BotoCoreError as error:
        raise AgentServiceError("Bedrock Agent client error") from error
