import pytest

from functions.bedrock_adapter.response_parser import (
    assemble_completion,
    parse_agent_decision,
)
from shared.errors import AgentThrottledError, InvalidAgentResponseError

VALID = (
    '{"schemaVersion":"1.0","requestId":"req-1",'
    '"classification":{"category":"GENERAL_INQUIRY","confidence":0.91},'
    '"validation":{"status":"VALID","missingFields":[],"violations":[]},'
    '"routing":{"destination":"CUSTOMER_SERVICE","priority":"NORMAL",'
    '"requiresHumanReview":false},"reasonCode":"GENERAL",'
    '"explanation":"A general inquiry."}'
)


def test_assembles_completion_chunks_in_order_and_counts_trace() -> None:
    output, traces = assemble_completion(
        [
            {"chunk": {"bytes": VALID[:50].encode()}},
            {"trace": {"trace": {}}},
            {"chunk": {"bytes": VALID[50:].encode()}},
        ]
    )

    assert output == VALID
    assert traces == 1


@pytest.mark.parametrize(
    "output",
    [
        f"```json\n{VALID}\n```",
        f"Here is the result: {VALID}",
        f"{VALID} trailing",
        f"{VALID}{VALID}",
        "[]",
        "not-json",
    ],
)
def test_rejects_non_strict_json(output: str) -> None:
    with pytest.raises(InvalidAgentResponseError):
        parse_agent_decision(output, expected_request_id="req-1")


def test_rejects_mismatched_request_id() -> None:
    with pytest.raises(InvalidAgentResponseError, match="does not match"):
        parse_agent_decision(VALID, expected_request_id="different")


def test_translates_stream_error_event() -> None:
    with pytest.raises(AgentThrottledError, match="throttled"):
        assemble_completion([{"throttlingException": {"message": "slow down"}}])
