#!/usr/bin/env python3
import aws_cdk as cdk

from agentic_workflow.config import EnvironmentConfig
from agentic_workflow.stack import AgenticWorkflowStack


app = cdk.App()
config = EnvironmentConfig.from_context(app)

AgenticWorkflowStack(
    app,
    "AgenticWorkflowStack",
    config=config,
    env=config.stack_environment(),
    description=f"Agentic request-processing workflow ({config.environment})",
)

app.synth()
