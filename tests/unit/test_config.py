import aws_cdk as cdk
import pytest

from agentic_workflow.config import ConfigurationError, EnvironmentConfig


def _app(context: dict[str, object]) -> cdk.App:
    return cdk.App(context=context)


def test_loads_typed_environment_configuration() -> None:
    app = _app(
        {
            "environment": "dev",
            "account": "111122223333",
            "region": "us-east-1",
            "environments": {
                "dev": {
                    "application_name": "agentic-workflow",
                    "foundation_model_id": "anthropic.claude-3-sonnet-20240229-v1:0",
                    "agent_timeout_seconds": 30,
                    "log_retention_days": 14,
                }
            },
        }
    )

    config = EnvironmentConfig.from_context(app)

    assert config.environment == "dev"
    assert config.minimum_auto_route_confidence == 0.8
    assert config.enable_agent_trace is True
    assert config.foundation_model_arn.endswith(
        "foundation-model/anthropic.claude-3-sonnet-20240229-v1:0"
    )


def test_defaults_to_accountless_dev_configuration() -> None:
    config = EnvironmentConfig.from_context(_app({}))

    assert config.environment == "dev"
    assert config.application_name == "agentic-workflow"
    assert config.foundation_model_id == "openai.gpt-oss-20b-1:0"
    assert cdk.Token.is_unresolved(config.account)
    assert cdk.Token.is_unresolved(config.region)
    assert config.stack_environment() is None


def test_rejects_non_dev_environment() -> None:
    with pytest.raises(ConfigurationError, match="Only the dev environment"):
        EnvironmentConfig.from_context(_app({"environment": "prod"}))


def test_rejects_placeholder_model_id() -> None:
    context = {
        "environment": "dev",
        "account": "111122223333",
        "region": "us-east-1",
        "environments": {
            "dev": {
                "application_name": "agentic-workflow",
                "foundation_model_id": "REQUIRED",
            }
        },
    }

    with pytest.raises(ConfigurationError, match="foundation_model_id"):
        EnvironmentConfig.from_context(_app(context))


def test_rejects_out_of_range_confidence() -> None:
    context = {
        "environment": "dev",
        "account": "111122223333",
        "region": "us-east-1",
        "environments": {
            "dev": {
                "application_name": "agentic-workflow",
                "foundation_model_id": "model-id",
                "minimum_auto_route_confidence": 1.1,
            }
        },
    }

    with pytest.raises(ConfigurationError, match="between 0 and 1"):
        EnvironmentConfig.from_context(_app(context))
