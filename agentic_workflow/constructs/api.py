from __future__ import annotations

from aws_cdk import CfnOutput, RemovalPolicy
from aws_cdk import aws_apigateway as apigateway
from aws_cdk import aws_kms as kms
from aws_cdk import aws_logs as logs
from constructs import Construct

from agentic_workflow.config import EnvironmentConfig
from agentic_workflow.constructs.workflow import WorkflowConstruct, log_retention


class ApiConstruct(Construct):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        config: EnvironmentConfig,
        workflow: WorkflowConstruct,
    ) -> None:
        super().__init__(scope, construct_id)
        access_log_key = kms.Key(
            self,
            "AccessLogKey",
            enable_key_rotation=True,
            removal_policy=RemovalPolicy.RETAIN,
        )
        access_logs = logs.LogGroup(
            self,
            "AccessLogs",
            encryption_key=access_log_key,
            retention=log_retention(config.log_retention_days),
            removal_policy=RemovalPolicy.RETAIN,
        )
        self.api = apigateway.RestApi(
            self,
            "Api",
            rest_api_name=f"{config.application_name}-{config.environment}",
            cloud_watch_role=True,
            deploy_options=apigateway.StageOptions(
                stage_name=config.environment,
                tracing_enabled=True,
                logging_level=apigateway.MethodLoggingLevel.ERROR,
                data_trace_enabled=False,
                metrics_enabled=True,
                throttling_rate_limit=20,
                throttling_burst_limit=40,
                access_log_destination=apigateway.LogGroupLogDestination(access_logs),
                access_log_format=apigateway.AccessLogFormat.json_with_standard_fields(
                    caller=False,
                    http_method=True,
                    ip=False,
                    protocol=True,
                    request_time=True,
                    resource_path=True,
                    response_length=True,
                    status=True,
                    user=True,
                ),
            ),
        )
        requests = self.api.root.add_resource("requests")
        requests.add_method(
            "POST",
            apigateway.LambdaIntegration(workflow.request_handler, proxy=True),
        )
        CfnOutput(self, "RequestsEndpoint", value=f"{self.api.url}requests")
