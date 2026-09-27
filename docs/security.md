# Security

- The agent execution role can invoke only the configured foundation model.
- The agent role trust policy restricts assumption to Bedrock from the deployment account. Its
  source-agent ARN uses an account-scoped wildcard because the agent ID is unavailable until after
  the role is created; this is the only intentional resource wildcard in application IAM.
- The adapter can invoke only the CDK-created agent alias.
- The request Lambda can start only the CDK-created state machine.
- Queue delivery and table writes are granted to the exact workflow/function resources.
- DynamoDB, SQS, SNS, and workflow logs use encryption at rest; transport policies require TLS.
- Production DynamoDB data is retained, point-in-time recovery is enabled, and deletion protection
  is enabled.
- Agent output size, enums, fields, confidence, and request identity are validated before routing.
- Detailed traces and execution data are disabled outside development.
- API authentication is omitted only for this initial personal/demo scope. Add JWT/Cognito before
  exposing the endpoint beyond a controlled environment.

CloudTrail, GuardDuty, Security Hub, dependency scanning, CDK policy validation, and centralized
log monitoring are recommended before production use.
