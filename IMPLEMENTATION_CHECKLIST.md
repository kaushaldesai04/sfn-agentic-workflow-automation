# Implementation checklist

- [x] Phase 1: Python CDK project scaffold
- [x] Phase 1: immutable typed environment configuration
- [x] Phase 1: lint, type-check, test, coverage, and CI configuration
- [x] Phase 1: single-stack entry point and mandatory resource tags
- [ ] Phase 1 verification: blocked locally until Python 3.12 is available through the PC's
  default `python` command; CI is configured to run the full quality gate
- [x] Phase 2: Pydantic contracts and deterministic routing policy
- [x] Phase 2: DynamoDB, processing queues, and DLQs
- [x] Phase 3: Bedrock Agent, role, and alias
- [x] Phase 4: runtime Lambda functions and unit tests
- [x] Phase 5: Step Functions workflow
- [x] Phase 6: API Gateway and baseline monitoring
- [ ] Phase 7: AWS deployment and live integration tests (requires an AWS account)
- [x] Phase 7: 50-example labeled evaluation dataset and offline scorer

## Manual prerequisites

- AWS account ID and deployment region - skip this for now keep placeholder
- A Bedrock foundation model ID enabled in that region - use openai entry level model availbale at the time
- Confirmation that the account can invoke the selected model - currently dont have an aws account so keep as a placeholder
- Production API authentication choice and allowed CORS origins - this is the personal projec so you can skip this point
- Alarm notification subscribers - skip this for now
- Environment retention/removal and optional KMS key requirements - can be skipped for now

## Resolved implementation defaults and known blockers

- Model default: `openai.gpt-oss-20b-1:0` (the smaller OpenAI open-weight Bedrock model).
- Development synthesis defaults to account/region tokens, so no AWS account is required locally.
  Real account and region values remain required only for deployment; no IDs were invented.
- AWS documents Bedrock Agents Classic as unavailable to new customers. Because no AWS account
  exists yet, deployment of the specification's `CfnAgent` may require migrating this design to
  Bedrock AgentCore when an account is created.
