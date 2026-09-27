from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

import boto3
from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.metrics import MetricUnit

logger = Logger(service="persist-result")
metrics = Metrics(namespace="AgenticWorkflow", service="persist-result")
tracer = Tracer(service="persist-result")
_table = boto3.resource("dynamodb").Table(os.environ.get("RESULTS_TABLE_NAME", "not-configured"))


def _decimal_safe(value: Any) -> Any:
    return json.loads(json.dumps(value), parse_float=Decimal)


@logger.inject_lambda_context(clear_state=True)
@tracer.capture_lambda_handler
@metrics.log_metrics(capture_cold_start_metric=True)
def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    del context
    now = datetime.now(timezone.utc).isoformat()
    request = event["request"]
    validated = event["validated"]
    decision = validated["decision"]
    item = {
        "requestId": request["requestId"],
        "executionId": event["executionId"],
        "status": event.get("status", "ROUTED"),
        "category": decision["classification"]["category"],
        "confidence": decision["classification"]["confidence"],
        "destination": decision["routing"]["destination"],
        "requiresHumanReview": decision["routing"]["requiresHumanReview"],
        "reasonCode": decision["reasonCode"],
        "agentDecision": decision,
        "policyOverrideReason": validated.get("policyOverrideReason"),
        "createdAt": event.get("receiptTimestamp", now),
        "updatedAt": now,
    }
    _table.put_item(Item=_decimal_safe(item))
    metrics.add_metric(name="RequestsSucceeded", unit=MetricUnit.Count, value=1)
    logger.info("ResultPersisted", requestId=request["requestId"], status=item["status"])
    return {"requestId": request["requestId"], "status": item["status"]}
