from __future__ import annotations

import argparse
import json

import boto3


def main() -> None:
    parser = argparse.ArgumentParser(description="Inspect a Step Functions execution")
    parser.add_argument("--execution-arn", required=True)
    parser.add_argument("--region")
    args = parser.parse_args()

    client = boto3.client("stepfunctions", region_name=args.region)
    response = client.describe_execution(executionArn=args.execution_arn)
    safe = {
        "executionArn": response["executionArn"],
        "stateMachineArn": response["stateMachineArn"],
        "status": response["status"],
        "startDate": response["startDate"].isoformat(),
        "stopDate": response.get("stopDate").isoformat() if response.get("stopDate") else None,
    }
    print(json.dumps(safe, indent=2))


if __name__ == "__main__":
    main()
