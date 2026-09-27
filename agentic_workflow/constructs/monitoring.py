from __future__ import annotations

from aws_cdk import Duration
from aws_cdk import aws_cloudwatch as cloudwatch
from aws_cdk import aws_cloudwatch_actions as actions
from aws_cdk import aws_kms as kms
from aws_cdk import aws_sns as sns
from constructs import Construct

from agentic_workflow.config import EnvironmentConfig
from agentic_workflow.constructs.api import ApiConstruct
from agentic_workflow.constructs.data import DataConstruct
from agentic_workflow.constructs.workflow import WorkflowConstruct


class MonitoringConstruct(Construct):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        config: EnvironmentConfig,
        data: DataConstruct,
        workflow: WorkflowConstruct,
        api: ApiConstruct,
    ) -> None:
        super().__init__(scope, construct_id)
        topic_key = kms.Key(self, "AlarmTopicKey", enable_key_rotation=True)
        self.alarm_topic = sns.Topic(
            self,
            "AlarmTopic",
            topic_name=f"{config.application_name}-{config.environment}-alarms",
            master_key=topic_key,
        )
        alarm_action = actions.SnsAction(self.alarm_topic)

        alarms = [
            workflow.state_machine.metric_failed(period=Duration.minutes(5)).create_alarm(
                self, "WorkflowFailures", threshold=1, evaluation_periods=1
            ),
            api.api.metric_server_error(period=Duration.minutes(5)).create_alarm(
                self, "Api5xx", threshold=1, evaluation_periods=1
            ),
            cloudwatch.Metric(
                namespace="AWS/States",
                metric_name="ExecutionTime",
                dimensions_map={
                    "StateMachineArn": workflow.state_machine.state_machine_arn
                },
                statistic="Maximum",
                period=Duration.minutes(5),
            ).create_alarm(
                self,
                "WorkflowDurationNearTimeout",
                threshold=240_000,
                evaluation_periods=1,
            ),
            cloudwatch.Metric(
                namespace="AgenticWorkflow",
                metric_name="InvalidAgentResponses",
                dimensions_map={"service": "bedrock-adapter"},
                statistic="Sum",
                period=Duration.minutes(5),
            ).create_alarm(
                self,
                "InvalidAgentResponses",
                threshold=3,
                evaluation_periods=1,
            ),
            cloudwatch.Metric(
                namespace="AgenticWorkflow",
                metric_name="ManualReviewCount",
                dimensions_map={"service": "decision-validator"},
                statistic="Sum",
                period=Duration.minutes(5),
            ).create_alarm(
                self,
                "HighManualReviewVolume",
                threshold=20,
                evaluation_periods=2,
            ),
        ]
        for index, function in enumerate(workflow.functions):
            alarms.append(
                function.metric_errors(period=Duration.minutes(5)).create_alarm(
                    self,
                    f"LambdaErrors{index}",
                    threshold=1,
                    evaluation_periods=1,
                )
            )
            alarms.append(
                function.metric_throttles(period=Duration.minutes(5)).create_alarm(
                    self,
                    f"LambdaThrottles{index}",
                    threshold=1,
                    evaluation_periods=1,
                )
            )
        for destination, queue in data.queues.items():
            alarms.append(
                queue.metric_approximate_age_of_oldest_message().create_alarm(
                    self,
                    f"{destination.value}OldestMessage",
                    threshold=900,
                    evaluation_periods=2,
                )
            )
            alarms.append(
                data.dead_letter_queues[destination]
                .metric_approximate_number_of_messages_visible()
                .create_alarm(
                    self,
                    f"{destination.value}DlqMessages",
                    threshold=1,
                    evaluation_periods=1,
                )
            )
        for alarm in alarms:
            alarm.add_alarm_action(alarm_action)

        self.dashboard = cloudwatch.Dashboard(
            self,
            "Dashboard",
            dashboard_name=f"{config.application_name}-{config.environment}",
        )
        self.dashboard.add_widgets(
            cloudwatch.GraphWidget(
                title="Workflow executions",
                left=[
                    workflow.state_machine.metric_started(),
                    workflow.state_machine.metric_succeeded(),
                    workflow.state_machine.metric_failed(),
                ],
            ),
            cloudwatch.GraphWidget(
                title="API requests and errors",
                left=[
                    api.api.metric_count(),
                    api.api.metric_client_error(),
                    api.api.metric_server_error(),
                ],
            ),
            cloudwatch.GraphWidget(
                title="Queue depth",
                left=[
                    queue.metric_approximate_number_of_messages_visible()
                    for queue in data.queues.values()
                ],
            ),
            cloudwatch.GraphWidget(
                title="Agent quality and routing",
                left=[
                    cloudwatch.Metric(
                        namespace="AgenticWorkflow",
                        metric_name="InvalidAgentResponses",
                        dimensions_map={"service": "bedrock-adapter"},
                        statistic="Sum",
                    ),
                    cloudwatch.Metric(
                        namespace="AgenticWorkflow",
                        metric_name="AgentInvocationLatency",
                        dimensions_map={"service": "bedrock-adapter"},
                        statistic="Average",
                    ),
                    cloudwatch.Metric(
                        namespace="AgenticWorkflow",
                        metric_name="ManualReviewCount",
                        dimensions_map={"service": "decision-validator"},
                        statistic="Sum",
                    ),
                    cloudwatch.Metric(
                        namespace="AgenticWorkflow",
                        metric_name="AutoRouteCount",
                        dimensions_map={"service": "decision-validator"},
                        statistic="Sum",
                    ),
                ],
            ),
        )
