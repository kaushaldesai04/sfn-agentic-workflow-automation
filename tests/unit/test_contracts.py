from datetime import datetime

import pytest
from pydantic import ValidationError

from shared.contracts.agent_decision import AgentDecision
from shared.contracts.workflow_request import WorkflowRequest


def _request() -> dict[str, object]:
    return {
        "source": "customer-portal",
        "submittedAt": "2026-09-26T10:00:00Z",
        "payload": {
            "subject": "Refund for duplicated payment",
            "description": "I was charged twice for invoice INV-1024",
            "customerId": "cust-788",
            "amount": 125.50,
            "currency": "USD",
        },
    }


def _decision() -> dict[str, object]:
    return {
        "schemaVersion": "1.0",
        "requestId": "req-12345",
        "classification": {"category": "BILLING_REFUND", "confidence": 0.94},
        "validation": {"status": "VALID", "missingFields": [], "violations": []},
        "routing": {
            "destination": "FINANCE_OPERATIONS",
            "priority": "HIGH",
            "requiresHumanReview": False,
        },
        "reasonCode": "DUPLICATE_PAYMENT",
        "explanation": "The request describes two charges for the same invoice.",
    }


def test_request_generates_ids_and_parses_iso_timestamp() -> None:
    request = WorkflowRequest.model_validate(_request())

    assert request.request_id.startswith("req-")
    assert request.metadata.correlation_id.startswith("corr-")
    assert isinstance(request.submitted_at, datetime)


@pytest.mark.parametrize(
    ("field", "value"),
    [("subject", ""), ("description", ""), ("currency", "dollars")],
)
def test_request_rejects_invalid_payload_fields(field: str, value: str) -> None:
    raw = _request()
    payload = raw["payload"]
    assert isinstance(payload, dict)
    payload[field] = value

    with pytest.raises(ValidationError):
        WorkflowRequest.model_validate(raw)


def test_contracts_reject_unknown_fields() -> None:
    raw = _request()
    raw["unexpected"] = True
    with pytest.raises(ValidationError):
        WorkflowRequest.model_validate(raw)

    decision = _decision()
    decision["queueUrl"] = "https://attacker.invalid/queue"
    with pytest.raises(ValidationError):
        AgentDecision.model_validate(decision)


@pytest.mark.parametrize("confidence", [-0.1, 1.1])
def test_decision_rejects_out_of_range_confidence(confidence: float) -> None:
    raw = _decision()
    classification = raw["classification"]
    assert isinstance(classification, dict)
    classification["confidence"] = confidence

    with pytest.raises(ValidationError):
        AgentDecision.model_validate(raw)


def test_decision_serializes_with_camel_case_aliases() -> None:
    decision = AgentDecision.model_validate(_decision())
    serialized = decision.model_dump(by_alias=True, mode="json")

    assert serialized["schemaVersion"] == "1.0"
    assert serialized["routing"]["requiresHumanReview"] is False
