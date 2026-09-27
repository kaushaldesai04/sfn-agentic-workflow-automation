from __future__ import annotations

from typing import Any

from aws_lambda_powertools import Logger, Tracer

from shared.contracts.workflow_request import WorkflowRequest

logger = Logger(service="request-validator")
tracer = Tracer(service="request-validator")


@logger.inject_lambda_context(clear_state=True)
@tracer.capture_lambda_handler
def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    del context
    request = WorkflowRequest.model_validate(event["request"])
    logger.info("WorkflowRequestValidated", requestId=request.request_id)
    return {
        "request": request.model_dump(mode="json", by_alias=True),
        "receiptTimestamp": event["receiptTimestamp"],
    }
