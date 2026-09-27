from __future__ import annotations

import os
from typing import Any

from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.metrics import MetricUnit, single_metric

from shared.contracts.agent_decision import AgentDecision, Destination
from shared.policy import validate_decision

logger = Logger(service="decision-validator")
metrics = Metrics(namespace="AgenticWorkflow", service="decision-validator")
tracer = Tracer(service="decision-validator")


@logger.inject_lambda_context(clear_state=True)
@tracer.capture_lambda_handler
@metrics.log_metrics(capture_cold_start_metric=True)
def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    del context
    decision = AgentDecision.model_validate(event["agentResult"]["decision"])
    result = validate_decision(
        decision,
        request_id=event["request"]["requestId"],
        minimum_confidence=float(os.environ.get("MINIMUM_CONFIDENCE", "0.80")),
    )
    destination = result.decision.routing.destination
    metric_name = (
        "ManualReviewCount"
        if destination is Destination.MANUAL_REVIEW
        else "RejectedRequestCount"
        if destination is Destination.REJECTED
        else "AutoRouteCount"
    )
    metrics.add_metric(name=metric_name, unit=MetricUnit.Count, value=1)
    with single_metric(
        name="RouteCount",
        unit=MetricUnit.Count,
        value=1,
        namespace="AgenticWorkflow",
    ) as route_metric:
        route_metric.add_dimension(name="Destination", value=destination.value)
        route_metric.add_dimension(
            name="Category", value=decision.classification.category.value
        )
    if decision.classification.confidence < float(
        os.environ.get("MINIMUM_CONFIDENCE", "0.80")
    ):
        metrics.add_metric(name="LowConfidenceDecisions", unit=MetricUnit.Count, value=1)
    logger.info(
        "DecisionValidated",
        requestId=result.decision.request_id,
        destination=destination,
        policyOverridden=result.policy_overridden,
    )
    return result.model_dump(mode="json", by_alias=True)
