from shared.observability import redact


def test_redacts_sensitive_fields_recursively() -> None:
    value = {
        "requestId": "req-1",
        "payload": {"description": "private", "subject": "safe"},
        "items": [{"token": "secret"}],
    }

    assert redact(value) == {
        "requestId": "req-1",
        "payload": {"description": "[REDACTED]", "subject": "safe"},
        "items": [{"token": "[REDACTED]"}],
    }
