from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, cast

import aws_cdk as cdk

DEFAULT_DEV_VALUES: Mapping[str, Any] = {
    "application_name": "agentic-workflow",
    "foundation_model_id": "openai.gpt-oss-20b-1:0",
    "minimum_auto_route_confidence": 0.80,
    "agent_timeout_seconds": 30,
    "log_retention_days": 14,
    "enable_agent_trace": True,
    "queue_visibility_timeout_seconds": 120,
    "queue_max_receive_count": 5,
    "allow_destroy_in_dev": False,
}


class ConfigurationError(ValueError):
    """Raised when deployment configuration is absent or unsafe."""


@dataclass(frozen=True, slots=True)
class EnvironmentConfig:
    environment: str
    account: str
    region: str
    application_name: str
    foundation_model_id: str
    foundation_model_arn: str
    minimum_auto_route_confidence: float
    agent_timeout_seconds: int
    log_retention_days: int
    enable_agent_trace: bool
    queue_visibility_timeout_seconds: int = 120
    queue_max_receive_count: int = 5
    allow_destroy_in_dev: bool = False

    def stack_environment(self) -> cdk.Environment | None:
        """Use an explicit CDK environment only after real account details are supplied."""
        if cdk.Token.is_unresolved(self.account) or cdk.Token.is_unresolved(self.region):
            return None
        return cdk.Environment(account=self.account, region=self.region)

    @classmethod
    def from_context(cls, app: cdk.App) -> EnvironmentConfig:
        environment_value = app.node.try_get_context("environment")
        environment = "dev" if environment_value is None else _required_string(
            environment_value, "environment"
        )
        if environment != "dev":
            raise ConfigurationError("Only the dev environment is currently configured")

        environments = app.node.try_get_context("environments")
        raw = environments.get(environment) if isinstance(environments, Mapping) else None
        values = (
            cast(Mapping[str, Any], raw)
            if isinstance(raw, Mapping)
            else DEFAULT_DEV_VALUES
        )

        account_value = app.node.try_get_context("account")
        region_value = app.node.try_get_context("region")
        account = (
            cdk.Aws.ACCOUNT_ID
            if account_value is None
            else _required_string(account_value, "account")
        )
        region = (
            cdk.Aws.REGION
            if region_value is None
            else _required_string(region_value, "region")
        )
        model_id = _required_string(values.get("foundation_model_id"), "foundation_model_id")
        if model_id == "REQUIRED":
            raise ConfigurationError(
                f"foundation_model_id is not configured for environment '{environment}'"
            )

        confidence = float(values.get("minimum_auto_route_confidence", 0.80))
        if not 0.0 <= confidence <= 1.0:
            raise ConfigurationError("minimum_auto_route_confidence must be between 0 and 1")

        trace_requested = bool(values.get("enable_agent_trace", environment == "dev"))
        return cls(
            environment=environment,
            account=account,
            region=region,
            application_name=_required_string(values.get("application_name"), "application_name"),
            foundation_model_id=model_id,
            foundation_model_arn=(
                f"arn:{cdk.Aws.PARTITION}:bedrock:{region}::foundation-model/{model_id}"
            ),
            minimum_auto_route_confidence=confidence,
            agent_timeout_seconds=_positive_int(
                values.get("agent_timeout_seconds", 30), "agent_timeout_seconds"
            ),
            log_retention_days=_positive_int(
                values.get("log_retention_days", 14), "log_retention_days"
            ),
            enable_agent_trace=trace_requested,
            queue_visibility_timeout_seconds=_positive_int(
                values.get("queue_visibility_timeout_seconds", 120),
                "queue_visibility_timeout_seconds",
            ),
            queue_max_receive_count=_positive_int(
                values.get("queue_max_receive_count", 5), "queue_max_receive_count"
            ),
            allow_destroy_in_dev=bool(values.get("allow_destroy_in_dev", False)),
        )


def _required_string(value: object, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ConfigurationError(f"Required CDK context value '{name}' is missing")
    return value.strip()


def _positive_int(value: object, name: str) -> int:
    if isinstance(value, bool):
        raise ConfigurationError(f"{name} must be a positive integer")
    try:
        parsed = int(cast(Any, value))
    except (TypeError, ValueError) as error:
        raise ConfigurationError(f"{name} must be a positive integer") from error
    if parsed <= 0:
        raise ConfigurationError(f"{name} must be a positive integer")
    return parsed
