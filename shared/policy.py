from __future__ import annotations

from shared.contracts.agent_decision import (
    AgentDecision,
    Category,
    Destination,
    ValidatedDecision,
    ValidationStatus,
)

AUTOMATIC_DESTINATIONS: dict[Category, Destination] = {
    Category.BILLING_REFUND: Destination.FINANCE_OPERATIONS,
    Category.TECHNICAL_SUPPORT: Destination.TECHNICAL_SUPPORT,
    Category.ACCOUNT_ACCESS: Destination.MANUAL_REVIEW,
    Category.GENERAL_INQUIRY: Destination.CUSTOMER_SERVICE,
    Category.UNKNOWN: Destination.MANUAL_REVIEW,
}


def validate_decision(
    decision: AgentDecision,
    *,
    request_id: str,
    minimum_confidence: float = 0.80,
) -> ValidatedDecision:
    """Apply deterministic routing policy to an already schema-valid agent response."""
    if decision.request_id != request_id:
        raise ValueError("agent decision requestId does not match workflow requestId")

    if decision.validation.status is ValidationStatus.REJECTED:
        return _override(decision, Destination.REJECTED, "Agent validation rejected the request")

    reasons: list[str] = []
    expected = AUTOMATIC_DESTINATIONS[decision.classification.category]
    if decision.classification.confidence < minimum_confidence:
        reasons.append("Confidence is below the automatic-routing threshold")
    if decision.classification.category is Category.UNKNOWN:
        reasons.append("Unknown category requires manual review")
    if decision.classification.category is Category.ACCOUNT_ACCESS:
        reasons.append("Account access is a sensitive category")
    if decision.validation.status is ValidationStatus.INVALID:
        reasons.append("Required information is missing or invalid")
    if decision.routing.destination is not expected:
        reasons.append("Destination does not match category policy")
    if decision.routing.requires_human_review:
        reasons.append("Agent requested human review")

    if reasons:
        return _override(decision, Destination.MANUAL_REVIEW, "; ".join(reasons))
    return ValidatedDecision(decision=decision)


def _override(
    decision: AgentDecision, destination: Destination, reason: str
) -> ValidatedDecision:
    routing = decision.routing.model_copy(
        update={
            "destination": destination,
            "requires_human_review": destination is not Destination.REJECTED,
        }
    )
    sanitized = decision.model_copy(update={"routing": routing})
    return ValidatedDecision(
        decision=sanitized,
        policy_overridden=True,
        policy_override_reason=reason,
    )
