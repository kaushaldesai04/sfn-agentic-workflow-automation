from __future__ import annotations

import hashlib
from pathlib import Path

from aws_cdk import Duration, RemovalPolicy, Stack
from aws_cdk import aws_iam as iam
from aws_cdk import aws_kms as kms
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_logs as logs
from aws_cdk import aws_stepfunctions as sfn
from aws_cdk import aws_stepfunctions_tasks as tasks
from constructs import Construct

from agentic_workflow.config import EnvironmentConfig
from agentic_workflow.constructs.bedrock_agent import BedrockAgentConstruct
from agentic_workflow.constructs.data import DataConstruct
from shared.contracts.agent_decision import Destination


class WorkflowConstruct(Construct):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        config: EnvironmentConfig,
        data: DataConstruct,
        bedrock_agent: BedrockAgentConstruct,
    ) -> None:
        super().__init__(scope, construct_id)
        self._config = config
        self._lambda_log_key = kms.Key(
            self,
            "LambdaLogKey",
            enable_key_rotation=True,
            removal_policy=RemovalPolicy.RETAIN,
        )
        project_root = Path(__file__).parents[2]
        layer_root = project_root / "lambda_layer"
        layer_marker = layer_root / ".built"
        requirements_hash = hashlib.sha256(
            (layer_root / "requirements.txt").read_bytes()
        ).hexdigest()
        if (
            not layer_marker.is_file()
            or layer_marker.read_text(encoding="utf-8").strip() != requirements_hash
        ):
            raise RuntimeError(
                "Lambda dependency layer is missing or stale. Run: "
                "python scripts/build_lambda_layer.py"
            )
        self.dependencies_layer = lambda_.LayerVersion(
            self,
            "PythonDependenciesLayer",
            code=lambda_.Code.from_asset(str(layer_root)),
            compatible_runtimes=[lambda_.Runtime.PYTHON_3_12],
            compatible_architectures=[lambda_.Architecture.ARM_64],
            description="Pydantic and AWS Lambda Powertools for workflow functions",
        )
        self.dependencies_layer.apply_removal_policy(RemovalPolicy.RETAIN)
        self._lambda_code = lambda_.Code.from_asset(
            str(project_root),
            exclude=[
                ".git",
                ".venv",
                ".github",
                "cdk.out",
                "docs",
                "lambda_layer",
                "scripts",
                "tests",
                "*.egg-info",
                "README.md",
                "pyproject.toml",
            ],
        )
        self.request_handler = self._function(
            "RequestHandler",
            "functions.request_handler.handler.handler",
            timeout=Duration.seconds(10),
        )
        validate_request = self._function(
            "ValidateRequest",
            "functions.validate_request.handler.handler",
            timeout=Duration.seconds(10),
        )
        adapter = self._function(
            "BedrockAdapter",
            "functions.bedrock_adapter.handler.handler",
            timeout=Duration.seconds(config.agent_timeout_seconds + 5),
            memory_size=512,
            environment={
                "AGENT_ID": bedrock_agent.agent_id,
                "AGENT_ALIAS_ID": bedrock_agent.alias_id,
                "ENABLE_AGENT_TRACE": str(config.enable_agent_trace).lower(),
            },
        )
        validate_decision = self._function(
            "ValidateDecision",
            "functions.validate_decision.handler.handler",
            timeout=Duration.seconds(10),
            environment={
                "MINIMUM_CONFIDENCE": str(config.minimum_auto_route_confidence),
            },
        )
        persist = self._function(
            "PersistResult",
            "functions.persist_result.handler.handler",
            timeout=Duration.seconds(15),
            environment={"RESULTS_TABLE_NAME": data.results_table.table_name},
        )
        self.functions = [
            self.request_handler,
            validate_request,
            adapter,
            validate_decision,
            persist,
        ]

        alias_arn = Stack.of(self).format_arn(
            service="bedrock",
            resource="agent-alias",
            resource_name=f"{bedrock_agent.agent_id}/{bedrock_agent.alias_id}",
        )
        adapter.add_to_role_policy(
            iam.PolicyStatement(actions=["bedrock:InvokeAgent"], resources=[alias_arn])
        )
        data.results_table.grant_write_data(persist)

        validate_input = tasks.LambdaInvoke(
            self,
            "Validate and normalize request",
            lambda_function=validate_request,
            payload_response_only=True,
            result_path="$",
        )
        invoke = tasks.LambdaInvoke(
            self,
            "Invoke Bedrock Agent",
            lambda_function=adapter,
            payload=sfn.TaskInput.from_object(
                {"request": sfn.JsonPath.object_at("$.request")}
            ),
            payload_response_only=True,
            result_path="$.agentResult",
        )
        invoke.add_retry(
            errors=[
                "AgentThrottledError",
                "AgentTimeoutError",
                "AgentServiceError",
                "Lambda.ServiceException",
                "Lambda.AWSLambdaException",
                "Lambda.SdkClientException",
            ],
            interval=Duration.seconds(2),
            backoff_rate=2,
            max_attempts=3,
        )
        deterministic_validation = tasks.LambdaInvoke(
            self,
            "Apply deterministic decision policy",
            lambda_function=validate_decision,
            payload=sfn.TaskInput.from_object(
                {
                    "request": sfn.JsonPath.object_at("$.request"),
                    "agentResult": sfn.JsonPath.object_at("$.agentResult"),
                }
            ),
            payload_response_only=True,
            result_path="$.validated",
        )
        fallback = sfn.Pass(
            self,
            "Build manual review fallback",
            parameters={
                "decision": {
                    "schemaVersion": "1.0",
                    "requestId.$": "$.request.requestId",
                    "classification": {"category": "UNKNOWN", "confidence": 0},
                    "validation": {
                        "status": "INVALID",
                        "missingFields": [],
                        "violations": ["Agent invocation or response validation failed"],
                    },
                    "routing": {
                        "destination": "MANUAL_REVIEW",
                        "priority": "NORMAL",
                        "requiresHumanReview": True,
                    },
                    "reasonCode": "AGENT_FAILURE",
                    "explanation": "The agent decision was unavailable or invalid.",
                },
                "policyOverridden": True,
                "policyOverrideReason": "Agent invocation or response validation failed",
            },
            result_path="$.validated",
        )
        invoke.add_catch(fallback, result_path=sfn.JsonPath.DISCARD)
        invalid_context = sfn.Pass(
            self,
            "Normalize invalid request for rejection",
            parameters={
                "request": {
                    "requestId.$": "States.UUID()",
                    "source": "workflow-validation",
                    "submittedAt.$": "$.receiptTimestamp",
                    "payload": {
                        "subject": "Invalid request",
                        "description": "The request failed schema validation.",
                    },
                    "metadata": {"correlationId.$": "States.UUID()"},
                },
                "receiptTimestamp.$": "$.receiptTimestamp",
            },
        )
        invalid_decision = sfn.Pass(
            self,
            "Build rejected input decision",
            parameters={
                "decision": {
                    "schemaVersion": "1.0",
                    "requestId.$": "$.request.requestId",
                    "classification": {"category": "UNKNOWN", "confidence": 0},
                    "validation": {
                        "status": "REJECTED",
                        "missingFields": [],
                        "violations": ["Workflow input failed schema validation"],
                    },
                    "routing": {
                        "destination": "REJECTED",
                        "priority": "NORMAL",
                        "requiresHumanReview": False,
                    },
                    "reasonCode": "INVALID_REQUEST",
                    "explanation": "The workflow input did not match the request contract.",
                },
                "policyOverridden": True,
                "policyOverrideReason": "Workflow input failed schema validation",
            },
            result_path="$.validated",
        )

        route_choice = sfn.Choice(self, "Route allowlisted destination")
        routed_persist = self._persist_task(persist, "Persist routed result", "ROUTED")
        rejected_persist = self._persist_task(persist, "Persist rejected result", "REJECTED")
        success = sfn.Succeed(self, "Workflow succeeded")
        routed_persist.next(success)
        rejected_persist.next(success)
        validate_input.add_catch(invalid_context, result_path=sfn.JsonPath.DISCARD)
        invalid_context.next(invalid_decision.next(rejected_persist))

        queue_tasks: dict[Destination, tasks.SqsSendMessage] = {}
        for destination in (
            Destination.FINANCE_OPERATIONS,
            Destination.TECHNICAL_SUPPORT,
            Destination.CUSTOMER_SERVICE,
            Destination.MANUAL_REVIEW,
        ):
            task = tasks.SqsSendMessage(
                self,
                f"Send to {destination.value}",
                queue=data.queues[destination],
                message_body=sfn.TaskInput.from_object(
                    {
                        "schemaVersion": "1.0",
                        "requestId": sfn.JsonPath.string_at("$.request.requestId"),
                        "correlationId": sfn.JsonPath.string_at(
                            "$.request.metadata.correlationId"
                        ),
                        "destination": sfn.JsonPath.string_at(
                            "$.validated.decision.routing.destination"
                        ),
                        "priority": sfn.JsonPath.string_at(
                            "$.validated.decision.routing.priority"
                        ),
                        "decision": sfn.JsonPath.object_at("$.validated.decision"),
                    }
                ),
                result_path=sfn.JsonPath.DISCARD,
            )
            task.next(routed_persist)
            queue_tasks[destination] = task

        route_choice.when(
            sfn.Condition.string_equals(
                "$.validated.decision.routing.destination", Destination.REJECTED.value
            ),
            rejected_persist,
        )
        for destination, task in queue_tasks.items():
            if destination is Destination.MANUAL_REVIEW:
                continue
            route_choice.when(
                sfn.Condition.string_equals(
                    "$.validated.decision.routing.destination", destination.value
                ),
                task,
            )
        route_choice.otherwise(queue_tasks[Destination.MANUAL_REVIEW])
        deterministic_validation.next(route_choice)
        fallback.next(route_choice)
        definition = validate_input.next(invoke.next(deterministic_validation))

        log_key = kms.Key(
            self,
            "WorkflowLogKey",
            enable_key_rotation=True,
            removal_policy=RemovalPolicy.RETAIN,
        )
        log_group = logs.LogGroup(
            self,
            "WorkflowLogs",
            encryption_key=log_key,
            retention=log_retention(config.log_retention_days),
            removal_policy=RemovalPolicy.RETAIN,
        )
        self.state_machine = sfn.StateMachine(
            self,
            "StateMachine",
            state_machine_name=f"{config.application_name}-{config.environment}",
            definition_body=sfn.DefinitionBody.from_chainable(definition),
            state_machine_type=sfn.StateMachineType.STANDARD,
            timeout=Duration.minutes(5),
            tracing_enabled=True,
            logs=sfn.LogOptions(
                destination=log_group,
                level=(
                    sfn.LogLevel.ALL if config.environment == "dev" else sfn.LogLevel.ERROR
                ),
                include_execution_data=config.environment == "dev",
            ),
        )
        self.state_machine.grant_start_execution(self.request_handler)
        self.request_handler.add_environment(
            "STATE_MACHINE_ARN", self.state_machine.state_machine_arn
        )

    def _function(
        self,
        construct_id: str,
        handler: str,
        *,
        timeout: Duration,
        memory_size: int = 256,
        environment: dict[str, str] | None = None,
    ) -> lambda_.Function:
        function_logs = logs.LogGroup(
            self,
            f"{construct_id}Logs",
            encryption_key=self._lambda_log_key,
            retention=log_retention(self._config.log_retention_days),
            removal_policy=RemovalPolicy.RETAIN,
        )
        return lambda_.Function(
            self,
            construct_id,
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler=handler,
            code=self._lambda_code,
            architecture=lambda_.Architecture.ARM_64,
            timeout=timeout,
            memory_size=memory_size,
            tracing=lambda_.Tracing.ACTIVE,
            log_group=function_logs,
            layers=[self.dependencies_layer],
            environment={"POWERTOOLS_LOG_LEVEL": "INFO", **(environment or {})},
        )

    def _persist_task(
        self, function: lambda_.IFunction, construct_id: str, status: str
    ) -> tasks.LambdaInvoke:
        task = tasks.LambdaInvoke(
            self,
            construct_id,
            lambda_function=function,
            payload=sfn.TaskInput.from_object(
                {
                    "request": sfn.JsonPath.object_at("$.request"),
                    "validated": sfn.JsonPath.object_at("$.validated"),
                    "receiptTimestamp": sfn.JsonPath.string_at("$.receiptTimestamp"),
                    "executionId": sfn.JsonPath.string_at("$$.Execution.Name"),
                    "status": status,
                }
            ),
            payload_response_only=True,
            result_path="$",
        )
        task.add_retry(
            errors=[
                "Lambda.ServiceException",
                "Lambda.AWSLambdaException",
                "Lambda.SdkClientException",
            ],
            interval=Duration.seconds(2),
            backoff_rate=2,
            max_attempts=3,
        )
        return task


def log_retention(days: int) -> logs.RetentionDays:
    supported = {
        1: logs.RetentionDays.ONE_DAY,
        3: logs.RetentionDays.THREE_DAYS,
        5: logs.RetentionDays.FIVE_DAYS,
        7: logs.RetentionDays.ONE_WEEK,
        14: logs.RetentionDays.TWO_WEEKS,
        30: logs.RetentionDays.ONE_MONTH,
        90: logs.RetentionDays.THREE_MONTHS,
        365: logs.RetentionDays.ONE_YEAR,
    }
    if days not in supported:
        raise ValueError(f"Unsupported CloudWatch Logs retention: {days} days")
    return supported[days]
