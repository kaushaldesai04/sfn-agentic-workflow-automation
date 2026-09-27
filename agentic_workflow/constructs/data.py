from __future__ import annotations

from aws_cdk import Duration, RemovalPolicy
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import aws_sqs as sqs
from constructs import Construct

from agentic_workflow.config import EnvironmentConfig
from shared.contracts.agent_decision import Destination


class DataConstruct(Construct):
    def __init__(self, scope: Construct, construct_id: str, *, config: EnvironmentConfig) -> None:
        super().__init__(scope, construct_id)
        removal_policy = (
            RemovalPolicy.DESTROY
            if config.environment == "dev" and config.allow_destroy_in_dev
            else RemovalPolicy.RETAIN
        )

        self.results_table = dynamodb.Table(
            self,
            "ResultsTable",
            table_name=f"{config.application_name}-{config.environment}-results",
            partition_key=dynamodb.Attribute(
                name="requestId", type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(name="executionId", type=dynamodb.AttributeType.STRING),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            encryption=dynamodb.TableEncryption.AWS_MANAGED,
            point_in_time_recovery_specification=dynamodb.PointInTimeRecoverySpecification(
                point_in_time_recovery_enabled=config.environment == "prod"
            ),
            deletion_protection=config.environment == "prod",
            time_to_live_attribute="expiresAt",
            removal_policy=removal_policy,
        )

        self.dead_letter_queues: dict[Destination, sqs.Queue] = {}
        self.queues: dict[Destination, sqs.Queue] = {}
        for destination, slug in (
            (Destination.FINANCE_OPERATIONS, "finance-operations"),
            (Destination.TECHNICAL_SUPPORT, "technical-support"),
            (Destination.CUSTOMER_SERVICE, "customer-service"),
            (Destination.MANUAL_REVIEW, "manual-review"),
        ):
            dlq = sqs.Queue(
                self,
                f"{_pascal(slug)}Dlq",
                queue_name=f"{config.application_name}-{config.environment}-{slug}-dlq",
                encryption=sqs.QueueEncryption.SQS_MANAGED,
                enforce_ssl=True,
                retention_period=Duration.days(14),
                removal_policy=removal_policy,
            )
            queue = sqs.Queue(
                self,
                f"{_pascal(slug)}Queue",
                queue_name=f"{config.application_name}-{config.environment}-{slug}",
                encryption=sqs.QueueEncryption.SQS_MANAGED,
                enforce_ssl=True,
                receive_message_wait_time=Duration.seconds(20),
                visibility_timeout=Duration.seconds(config.queue_visibility_timeout_seconds),
                dead_letter_queue=sqs.DeadLetterQueue(
                    queue=dlq, max_receive_count=config.queue_max_receive_count
                ),
                removal_policy=removal_policy,
            )
            self.dead_letter_queues[destination] = dlq
            self.queues[destination] = queue


def _pascal(value: str) -> str:
    return "".join(word.title() for word in value.split("-"))
