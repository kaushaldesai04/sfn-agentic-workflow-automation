from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints
from pydantic.alias_generators import to_camel


class Category(StrEnum):
    BILLING_REFUND = "BILLING_REFUND"
    TECHNICAL_SUPPORT = "TECHNICAL_SUPPORT"
    ACCOUNT_ACCESS = "ACCOUNT_ACCESS"
    GENERAL_INQUIRY = "GENERAL_INQUIRY"
    UNKNOWN = "UNKNOWN"


class Destination(StrEnum):
    FINANCE_OPERATIONS = "FINANCE_OPERATIONS"
    TECHNICAL_SUPPORT = "TECHNICAL_SUPPORT"
    CUSTOMER_SERVICE = "CUSTOMER_SERVICE"
    MANUAL_REVIEW = "MANUAL_REVIEW"
    REJECTED = "REJECTED"


class ValidationStatus(StrEnum):
    VALID = "VALID"
    INVALID = "INVALID"
    REJECTED = "REJECTED"


class Priority(StrEnum):
    LOW = "LOW"
    NORMAL = "NORMAL"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class StrictCamelModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        extra="forbid",
        str_strip_whitespace=True,
    )


class Classification(StrictCamelModel):
    category: Category
    confidence: float = Field(ge=0.0, le=1.0)


class DecisionValidation(StrictCamelModel):
    status: ValidationStatus
    missing_fields: list[Annotated[str, StringConstraints(max_length=100)]] = Field(
        default_factory=list, max_length=25
    )
    violations: list[Annotated[str, StringConstraints(max_length=200)]] = Field(
        default_factory=list, max_length=25
    )


class Routing(StrictCamelModel):
    destination: Destination
    priority: Priority
    requires_human_review: bool


class AgentDecision(StrictCamelModel):
    schema_version: Literal["1.0"]
    request_id: Annotated[str, StringConstraints(min_length=1, max_length=128)]
    classification: Classification
    validation: DecisionValidation
    routing: Routing
    reason_code: Annotated[str, StringConstraints(min_length=1, max_length=100)]
    explanation: Annotated[str, StringConstraints(min_length=1, max_length=1_000)]


class ValidatedDecision(StrictCamelModel):
    decision: AgentDecision
    policy_overridden: bool = False
    policy_override_reason: Annotated[str, StringConstraints(max_length=500)] | None = None
