from __future__ import annotations

import json
from datetime import datetime, timezone
from decimal import Decimal
from typing import Annotated
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator
from pydantic.alias_generators import to_camel

MAX_REQUEST_BYTES = 32_768
ShortText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
Description = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=8_000)
]
Identifier = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=128)]


class StrictCamelModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        extra="forbid",
        str_strip_whitespace=True,
    )


class RequestPayload(StrictCamelModel):
    subject: ShortText
    description: Description
    customer_id: Identifier | None = None
    amount: Decimal | None = Field(default=None, ge=0, max_digits=16, decimal_places=2)
    currency: Annotated[str, StringConstraints(pattern=r"^[A-Z]{3}$")] | None = None


class RequestMetadata(StrictCamelModel):
    correlation_id: Identifier = Field(default_factory=lambda: f"corr-{uuid4()}")
    tenant_id: Identifier | None = None


class WorkflowRequest(StrictCamelModel):
    request_id: Identifier = Field(default_factory=lambda: f"req-{uuid4()}")
    source: ShortText
    submitted_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    payload: RequestPayload
    metadata: RequestMetadata = Field(default_factory=RequestMetadata)

    @model_validator(mode="after")
    def enforce_total_size(self) -> WorkflowRequest:
        serialized = json.dumps(self.model_dump(mode="json", by_alias=True), separators=(",", ":"))
        if len(serialized.encode("utf-8")) > MAX_REQUEST_BYTES:
            raise ValueError(f"request exceeds {MAX_REQUEST_BYTES} bytes")
        return self
