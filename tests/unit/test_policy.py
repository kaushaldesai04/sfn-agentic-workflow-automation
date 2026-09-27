import pytest

from shared.contracts.agent_decision import AgentDecision, Destination
from shared.policy import validate_decision


def _decision(
    *,
    category: str = "BILLING_REFUND",
    destination: str = "FINANCE_OPERATIONS",
    confidence: float = 0.94,
    status: str = "VALID",
    human_review: bool = False,
) -> AgentDecision:
    return AgentDecision.model_validate(
        {
            "schemaVersion": "1.0",
            "requestId": "req-123",
            "classification": {"category": category, "confidence": confidence},
            "validation": {"status": status},
            "routing": {
                "destination": destination,
                "priority": "NORMAL",
                "requiresHumanReview": human_review,
            },
            "reasonCode": "TEST",
            "explanation": "Test decision",
        }
    )


def test_allows_policy_compliant_automatic_route() -> None:
    result = validate_decision(_decision(), request_id="req-123")

    assert result.policy_overridden is False
    assert result.decision.routing.destination is Destination.FINANCE_OPERATIONS


@pytest.mark.parametrize(
    "decision",
    [
        _decision(confidence=0.79),
        _decision(category="UNKNOWN", destination="MANUAL_REVIEW"),
        _decision(category="ACCOUNT_ACCESS", destination="MANUAL_REVIEW"),
        _decision(status="INVALID"),
        _decision(destination="CUSTOMER_SERVICE"),
        _decision(human_review=True),
    ],
)
def test_forces_manual_review(decision: AgentDecision) -> None:
    result = validate_decision(decision, request_id="req-123")

    assert result.policy_overridden is True
    assert result.decision.routing.destination is Destination.MANUAL_REVIEW
    assert result.decision.routing.requires_human_review is True
    assert result.policy_override_reason


def test_treats_rejected_as_terminal() -> None:
    result = validate_decision(_decision(status="REJECTED"), request_id="req-123")

    assert result.decision.routing.destination is Destination.REJECTED
    assert result.decision.routing.requires_human_review is False


def test_rejects_mismatched_request_id() -> None:
    with pytest.raises(ValueError, match="does not match"):
        validate_decision(_decision(), request_id="req-other")
