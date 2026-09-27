from __future__ import annotations

import hashlib
import os
import re
import time
from typing import Any

import boto3
from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.metrics import MetricUnit

from functions.bedrock_adapter.invoke_agent import invoke_agent
from functions.bedrock_adapter.response_parser import assemble_completion, parse_agent_decision
from shared.errors import InvalidAgentResponseError, WorkflowError

logger = Logger(service="bedrock-adapter")
metrics = Metrics(namespace="AgenticWorkflow", service="bedrock-adapter")
tracer = Tracer(service="bedrock-adapter")
_client = boto3.client("bedrock-agent-runtime")


def _session_id(request_id: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9._:-]", "-", request_id)[:80]
    return f"{safe}-{hashlib.sha256(request_id.encode()).hexdigest()[:8]}"


@logger.inject_lambda_context(clear_state=True)
@tracer.capture_lambda_handler
@metrics.log_metrics(capture_cold_start_metric=True)
def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    del context
    request = event["request"]
    request_id = request["requestId"]
    session_id = _session_id(request_id)
    started = time.perf_counter()
    try:
        response = invoke_agent(
            _client,
            agent_id=os.environ["AGENT_ID"],
            alias_id=os.environ["AGENT_ALIAS_ID"],
            session_id=session_id,
            request=request,
            enable_trace=os.environ.get("ENABLE_AGENT_TRACE", "false").lower() == "true",
        )
        output, trace_count = assemble_completion(response["completion"])
        decision = parse_agent_decision(output, expected_request_id=request_id)
    except InvalidAgentResponseError:
        metrics.add_metric(name="InvalidAgentResponses", unit=MetricUnit.Count, value=1)
        metrics.add_metric(name="AgentInvocationErrors", unit=MetricUnit.Count, value=1)
        raise
    except WorkflowError:
        metrics.add_metric(name="AgentInvocationErrors", unit=MetricUnit.Count, value=1)
        raise
    latency_ms = round((time.perf_counter() - started) * 1_000)
    metrics.add_metric(name="AgentInvocationCount", unit=MetricUnit.Count, value=1)
    metrics.add_metric(
        name="AgentInvocationLatency", unit=MetricUnit.Milliseconds, value=latency_ms
    )
    logger.info(
        "AgentDecisionReceived",
        requestId=request_id,
        classification=decision.classification.category,
        destination=decision.routing.destination,
        confidence=decision.classification.confidence,
        latencyMs=latency_ms,
        traceEventCount=trace_count,
    )
    return {
        "decision": decision.model_dump(mode="json", by_alias=True),
        "metadata": {
            "agentId": os.environ["AGENT_ID"],
            "agentAliasId": os.environ["AGENT_ALIAS_ID"],
            "sessionId": session_id,
            "latencyMs": latency_ms,
            "traceEventCount": trace_count,
        },
    }
