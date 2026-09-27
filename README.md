# Agentic Workflow Automation

AWS CDK v2/Python implementation of a request-processing workflow in which an Amazon
Bedrock Agent recommends a bounded business decision and deterministic application code
validates that decision before any routing side effect.

The project is implemented incrementally from `../details.md`. The repository now contains the
single-stack infrastructure, contracts and policy, Bedrock Agent adapter, Standard Workflow,
API, persistence, queues, baseline monitoring, tests, CI, and a 50-example evaluation dataset.
AWS deployment and live evaluation remain pending until an account is available. See
`IMPLEMENTATION_CHECKLIST.md` for exact status.

## Requirements

- Python 3.12
- Node.js 20 or later
- AWS CDK CLI v2 (`npm install --global aws-cdk@2`)
- AWS credentials only when diffing or deploying

## Windows setup (default PC environment)

```powershell
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
python scripts/build_lambda_layer.py
```

This project does not require or create a virtual environment. These commands install into
the Python environment selected by the PC's default `python` command.

The final command builds one shared Lambda layer using Linux ARM64 wheels. Docker is not used.
Re-run it after changing `lambda_layer/requirements.txt`.

## Quality checks

```powershell
ruff check .
ruff format --check .
mypy
pytest --cov=agentic_workflow --cov=functions --cov=shared
bandit -c pyproject.toml -r agentic_workflow functions shared
pip-audit
```

## CDK configuration

The project currently defaults to development only. Account IDs and regions are deliberately not
committed. When neither value is provided, the stack is synthesized as an environment-agnostic
CDK template using CloudFormation account and region tokens. `cdk.json` uses
`openai.gpt-oss-20b-1:0` as the initial development model.

No context arguments or AWS account are required for local synthesis:

```powershell
python scripts/build_lambda_layer.py
cdk synth
```

After obtaining an AWS account, an explicit environment can be selected with:

```powershell
cdk synth -c environment=dev -c account=111122223333 -c region=us-east-1
```

Do not put secrets in CDK context. Account bootstrap, model access, authentication,
notifications, deployment, and operations are documented under `docs/`.

Amazon Bedrock Agents Classic is in maintenance mode and AWS states it is not open to new
customers. This repository follows the supplied `CfnAgent` specification, but a newly created AWS
account may need an AgentCore migration before it can deploy. That migration is intentionally not
mixed into the current architecture without an explicit design decision.

## Architecture invariant

All environment resources belong to one `AgenticWorkflowStack`. Internal custom constructs
group data, Bedrock, workflow, API, and monitoring resources without creating service-specific
CloudFormation stacks. The agent never chooses ARNs, queue URLs, Lambda names, or other AWS
resource identifiers.
