from unittest.mock import Mock

import pytest
from botocore.exceptions import ClientError, ReadTimeoutError

from functions.bedrock_adapter.invoke_agent import invoke_agent
from shared.errors import AgentAccessDeniedError, AgentThrottledError, AgentTimeoutError


def _invoke(client: Mock) -> dict[str, object]:
    return invoke_agent(
        client,
        agent_id="agent-id",
        alias_id="alias-id",
        session_id="session-id",
        request={"requestId": "req-1", "payload": {"subject": "Help"}},
        enable_trace=False,
    )


def test_invokes_agent_without_infrastructure_details_in_prompt() -> None:
    client = Mock()
    client.invoke_agent.return_value = {"completion": []}

    response = _invoke(client)

    assert response == {"completion": []}
    call = client.invoke_agent.call_args.kwargs
    assert call["agentId"] == "agent-id"
    assert "queueUrl" not in call["inputText"]
    assert call["enableTrace"] is False


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        ("ThrottlingException", AgentThrottledError),
        ("AccessDeniedException", AgentAccessDeniedError),
        ("ModelTimeoutException", AgentTimeoutError),
    ],
)
def test_translates_client_errors(code: str, expected: type[Exception]) -> None:
    client = Mock()
    client.invoke_agent.side_effect = ClientError(
        {"Error": {"Code": code, "Message": "test"}}, "InvokeAgent"
    )

    with pytest.raises(expected):
        _invoke(client)


def test_translates_read_timeout() -> None:
    client = Mock()
    client.invoke_agent.side_effect = ReadTimeoutError(endpoint_url="https://example.invalid")

    with pytest.raises(AgentTimeoutError):
        _invoke(client)
