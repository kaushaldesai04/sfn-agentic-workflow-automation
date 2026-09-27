from __future__ import annotations

import base64
import hashlib
import json
import os
import re
from datetime import datetime, timezone
from typing import Any

import boto3
from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.metrics import MetricUnit
from botocore.exceptions import ClientError
from pydantic import ValidationError

from shared.contracts.workflow_request import WorkflowRequest

logger = Logger(service="request-handler")
metrics = Metrics(namespace="AgenticWorkflow", service="request-handler")
tracer = Tracer(service="request-handler")
_sfn = boto3.client("stepfunctions")


def _response(status_code: int, body: dict[str, Any]) -> dict[str, Any]:
    return {
        "statusCode": status_code,
        "headers": {"content-type": "application/json"},
        "body": json.dumps(body, separators=(",", ":")),
    }


def _execution_name(request_id: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_-]", "-", request_id)[:54]
    digest = hashlib.sha256(request_id.encode()).hexdigest()[:10]
    return f"{safe}-{digest}"


def _execution_arn(state_machine_arn: str, execution_name: str) -> str:
    return state_machine_arn.replace(":stateMachine:", ":execution:") + f":{execution_name}"


@logger.inject_lambda_context(clear_state=True)
@tracer.capture_lambda_handler
@metrics.log_metrics(capture_cold_start_metric=True)
def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    del context
    try:
        encoded = event.get("body") or "{}"
        if event.get("isBase64Encoded"):
            encoded = base64.b64decode(encoded, validate=True).decode("utf-8")
        raw = json.loads(encoded)
        request = WorkflowRequest.model_validate(raw)
    except (ValueError, TypeError, json.JSONDecodeError, ValidationError) as error:
        logger.info("RequestValidationFailed", extra={"errorType": type(error).__name__})
        return _response(400, {"status": "INVALID_REQUEST", "message": "Request is invalid"})

    state_machine_arn = os.environ["STATE_MACHINE_ARN"]
    name = _execution_name(request.request_id)
    input_document = {
        "request": request.model_dump(mode="json", by_alias=True),
        "receiptTimestamp": datetime.now(timezone.utc).isoformat(),
    }
    try:
        result = _sfn.start_execution(
            stateMachineArn=state_machine_arn,
            name=name,
            input=json.dumps(input_document, separators=(",", ":")),
        )
        execution_arn = result["executionArn"]
        metrics.add_metric(name="RequestsStarted", unit=MetricUnit.Count, value=1)
    except ClientError as error:
        code = error.response.get("Error", {}).get("Code", "")
        if code == "ExecutionAlreadyExists":
            execution_arn = _execution_arn(state_machine_arn, name)
            logger.info("DuplicateRequestAccepted", requestId=request.request_id)
        elif code in {"ThrottlingException", "TooManyRequestsException"}:
            return _response(429, {"status": "THROTTLED", "message": "Try again later"})
        else:
            logger.exception("StartExecutionFailed", requestId=request.request_id)
            return _response(500, {"status": "ERROR", "message": "Unable to accept request"})

    return _response(
        202,
        {
            "requestId": request.request_id,
            "executionArn": execution_arn,
            "status": "ACCEPTED",
        },
    )
