from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

SENSITIVE_KEYS = frozenset(
    {
        "authorization",
        "cookie",
        "description",
        "prompt",
        "rawtrace",
        "secret",
        "token",
    }
)


def redact(value: Any) -> Any:
    """Return a log-safe copy of nested structures."""
    if isinstance(value, Mapping):
        return {
            str(key): "[REDACTED]" if str(key).lower() in SENSITIVE_KEYS else redact(item)
            for key, item in value.items()
        }
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [redact(item) for item in value]
    return value
