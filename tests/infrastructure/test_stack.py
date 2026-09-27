import aws_cdk as cdk
from aws_cdk.assertions import Match, Template

from agentic_workflow.config import EnvironmentConfig
from agentic_workflow.stack import AgenticWorkflowStack


def _template(environment: str = "dev") -> Template:
    app = cdk.App()
    config = EnvironmentConfig(
        environment=environment,
        account="111122223333",
        region="us-east-1",
        application_name="agentic-workflow",
        foundation_model_id="openai.gpt-oss-20b-1:0",
        foundation_model_arn=(
            "arn:aws:bedrock:us-east-1::foundation-model/openai.gpt-oss-20b-1:0"
        ),
        minimum_auto_route_confidence=0.8,
        agent_timeout_seconds=30,
        log_retention_days=14,
        enable_agent_trace=environment == "dev",
    )
    stack = AgenticWorkflowStack(
        app,
        "AgenticWorkflowStack",
        config=config,
        env=cdk.Environment(account=config.account, region=config.region),
    )
    return Template.from_stack(stack)


def test_creates_results_table_and_four_queue_dlq_pairs() -> None:
    template = _template()

    template.resource_count_is("AWS::DynamoDB::Table", 1)
    template.resource_count_is("AWS::SQS::Queue", 8)
    template.has_resource_properties(
        "AWS::DynamoDB::Table",
        {
            "BillingMode": "PAY_PER_REQUEST",
            "SSESpecification": {"SSEEnabled": True},
            "TimeToLiveSpecification": {"AttributeName": "expiresAt", "Enabled": True},
        },
    )
    template.has_resource_properties(
        "AWS::SQS::Queue",
        {
            "ReceiveMessageWaitTimeSeconds": 20,
            "RedrivePolicy": {
                "deadLetterTargetArn": Match.any_value(),
                "maxReceiveCount": 5,
            },
        },
    )


def test_production_table_is_protected() -> None:
    template = _template("prod")

    template.has_resource(
        "AWS::DynamoDB::Table",
        {
            "DeletionPolicy": "Retain",
            "UpdateReplacePolicy": "Retain",
            "Properties": {
                "DeletionProtectionEnabled": True,
                "PointInTimeRecoverySpecification": {
                    "PointInTimeRecoveryEnabled": True
                },
            },
        },
    )


def test_creates_bedrock_agent_alias_and_scoped_model_permission() -> None:
    template = _template()

    template.resource_count_is("AWS::Bedrock::Agent", 1)
    template.resource_count_is("AWS::Bedrock::AgentAlias", 1)
    template.has_resource_properties(
        "AWS::Bedrock::Agent",
        {
            "AutoPrepare": True,
            "FoundationModel": "openai.gpt-oss-20b-1:0",
            "Instruction": Match.string_like_regexp("Return exactly one JSON object"),
        },
    )
    template.has_resource_properties(
        "AWS::IAM::Role",
        {
            "Policies": Match.array_with(
                [
                    {
                        "PolicyDocument": {
                            "Statement": Match.array_with(
                                [
                                    Match.object_like(
                                        {
                                            "Action": "bedrock:InvokeModel",
                                            "Effect": "Allow",
                                            "Resource": (
                                                "arn:aws:bedrock:us-east-1::foundation-model/"
                                                "openai.gpt-oss-20b-1:0"
                                            ),
                                        }
                                    )
                                ]
                            )
                        }
                    }
                ]
            )
        },
    )


def test_workflow_api_and_monitoring_are_enabled() -> None:
    template = _template()

    template.resource_count_is("AWS::Lambda::Function", 5)
    template.resource_count_is("AWS::Lambda::LayerVersion", 1)
    template.resource_count_is("AWS::StepFunctions::StateMachine", 1)
    template.has_resource_properties(
        "AWS::StepFunctions::StateMachine",
        {
            "LoggingConfiguration": {
                "IncludeExecutionData": True,
                "Level": "ALL",
                "Destinations": Match.any_value(),
            },
            "TracingConfiguration": {"Enabled": True},
            "StateMachineType": "STANDARD",
        },
    )
    template.has_resource_properties(
        "AWS::Lambda::Function",
        {
            "Runtime": "python3.12",
            "TracingConfig": {"Mode": "Active"},
            "Timeout": Match.any_value(),
            "Layers": Match.any_value(),
        },
    )
    template.resource_count_is("AWS::ApiGateway::RestApi", 1)
    template.resource_count_is("AWS::CloudWatch::Dashboard", 1)
    template.resource_count_is("AWS::SNS::Topic", 1)
    template.resource_count_is("AWS::CloudWatch::Alarm", 23)
