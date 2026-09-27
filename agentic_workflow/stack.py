from __future__ import annotations

from typing import Any

from aws_cdk import Stack, Tags
from constructs import Construct

from agentic_workflow.config import EnvironmentConfig
from agentic_workflow.constructs.bedrock_agent import BedrockAgentConstruct
from agentic_workflow.constructs.api import ApiConstruct
from agentic_workflow.constructs.data import DataConstruct
from agentic_workflow.constructs.monitoring import MonitoringConstruct
from agentic_workflow.constructs.workflow import WorkflowConstruct


class AgenticWorkflowStack(Stack):
    """Single environment stack. Service constructs are added phase by phase."""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        config: EnvironmentConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)
        self.config = config

        Tags.of(self).add("Application", config.application_name)
        Tags.of(self).add("Environment", config.environment)
        Tags.of(self).add("Owner", "PlatformEngineering")
        Tags.of(self).add("ManagedBy", "CDK")

        self.data = DataConstruct(self, "Data", config=config)
        self.bedrock_agent = BedrockAgentConstruct(self, "BedrockAgent", config=config)
        self.workflow = WorkflowConstruct(
            self,
            "Workflow",
            config=config,
            data=self.data,
            bedrock_agent=self.bedrock_agent,
        )
        self.api = ApiConstruct(self, "Api", config=config, workflow=self.workflow)
        self.monitoring = MonitoringConstruct(
            self,
            "Monitoring",
            config=config,
            data=self.data,
            workflow=self.workflow,
            api=self.api,
        )
