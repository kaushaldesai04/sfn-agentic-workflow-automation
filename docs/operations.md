# Operations

## Before deployment

1. Install Python 3.12 into the PC's default environment and install the project dependencies.
2. Create an AWS account, configure credentials, and bootstrap the chosen account/region.
3. Confirm the configured model is available and invocable in that region.
4. Review retention, authentication, CORS, KMS, and notification settings before production use.

## Quality gate

```powershell
python -m pip install -e ".[dev]"
python scripts/build_lambda_layer.py
ruff check .
ruff format --check .
mypy
pytest --cov=agentic_workflow --cov=functions --cov=shared
cdk synth
```

The account-less command uses CloudFormation account and region tokens. Supplying real account and
region context is required only when preparing to diff or deploy against AWS.

CDK uploads the Lambda source and shared dependency layer as direct assets. Docker is not required.
The layer builder downloads Python 3.12 Linux ARM64 wheels locally before synthesis. No AWS
deployment is performed by tests or CI synthesis.

## Failure behavior

Transient Bedrock and Lambda service failures retry three times with exponential backoff. Final
agent failures and invalid output become a bounded manual-review decision. Persistence failures
retry and then fail the workflow. DLQ and oldest-message alarms indicate downstream problems.

Alarm subscriptions are intentionally absent until a real notification destination is supplied.
