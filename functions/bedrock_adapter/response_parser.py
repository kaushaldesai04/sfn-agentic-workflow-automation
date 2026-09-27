from __future__ import annotations

import json
from typing import Any

from pydantic import ValidationError

from shared.contracts.agent_decision import AgentDecision
from shared.errors import (
    AgentAccessDeniedError,
    AgentServiceError,
    AgentThrottledError,
    AgentTimeoutError,
    InvalidAgentResponseError,
)

MAX_AGENT_OUTPUT_BYTES = 32_768


def assemble_completion(event_stream: Any) -> tuple[str, int]:
    chunks: list[bytes] = []
    trace_count = 0
    try:
        for event in event_stream:
            if "chunk" in event:
                chunks.append(event["chunk"]["bytes"])
            elif "trace" in event:
                trace_count += 1
            else:
                error_keys = [key for key in event if key.lower().endswith("exception")]
                if error_keys:
                    error_key = error_keys[0]
                    if "throttl" in error_key.lower():
                        raise AgentThrottledError("agent completion stream was throttled")
                    if "access" in error_key.lower() or "unauthorized" in error_key.lower():
                        raise AgentAccessDeniedError("agent completion stream access was denied")
                    if "timeout" in error_key.lower():
                        raise AgentTimeoutError("agent completion stream timed out")
                    raise AgentServiceError(f"agent completion stream failed: {error_key}")
    except (
        InvalidAgentResponseError,
        AgentThrottledError,
        AgentAccessDeniedError,
        AgentTimeoutError,
        AgentServiceError,
    ):
        raise
    except Exception as error:
        raise InvalidAgentResponseError("agent completion stream could not be consumed") from error

    output = b"".join(chunks)
    if not output or len(output) > MAX_AGENT_OUTPUT_BYTES:
        raise InvalidAgentResponseError("agent output is empty or oversized")
    try:
        return output.decode("utf-8"), trace_count
    except UnicodeDecodeError as error:
        raise InvalidAgentResponseError("agent output is not valid UTF-8") from error


def parse_agent_decision(output: str, *, expected_request_id: str) -> AgentDecision:
    if output != output.strip() or "```" in output:
        raise InvalidAgentResponseError("agent output must contain only one JSON object")
    decoder = json.JSONDecoder()
    try:
        raw, end = decoder.raw_decode(output)
    except json.JSONDecodeError as error:
        raise InvalidAgentResponseError("agent output is not valid JSON") from error
    if end != len(output) or not isinstance(raw, dict):
        raise InvalidAgentResponseError("agent output must contain exactly one JSON object")
    try:
        decision = AgentDecision.model_validate(raw)
    except ValidationError as error:
        raise InvalidAgentResponseError("agent output violates the decision schema") from error
    if decision.request_id != expected_request_id:
        raise InvalidAgentResponseError("agent response requestId does not match the request")
    return decision
