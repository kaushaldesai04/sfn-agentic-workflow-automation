from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path
from typing import Any


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def _percentile(values: list[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(round((len(ordered) - 1) * fraction), len(ordered) - 1)
    return ordered[index]


def score(
    labels: list[dict[str, Any]],
    results: list[dict[str, Any]],
    *,
    input_cost_per_million: float,
    output_cost_per_million: float,
) -> dict[str, float | int]:
    expected = {row["id"]: row for row in labels}
    actual = {row["id"]: row for row in results}
    total = len(expected)
    valid = [
        row for row in results if row.get("id") in expected and row.get("validJson", False)
    ]
    classification_correct = 0
    routing_correct = 0
    true_positive = false_positive = false_negative = false_auto_routes = 0
    latency: list[float] = []
    total_cost = 0.0

    for identifier, label in expected.items():
        result = actual.get(identifier, {})
        if result.get("classification") == label["expectedCategory"]:
            classification_correct += 1
        if result.get("destination") == label["expectedDestination"]:
            routing_correct += 1
        expected_review = bool(label["expectedManualReview"])
        actual_review = bool(result.get("requiresHumanReview", False))
        true_positive += int(expected_review and actual_review)
        false_positive += int(not expected_review and actual_review)
        false_negative += int(expected_review and not actual_review)
        false_auto_routes += int(expected_review and not actual_review)
        if "latencyMs" in result:
            latency.append(float(result["latencyMs"]))
        total_cost += float(result.get("inputTokens", 0)) * input_cost_per_million / 1_000_000
        total_cost += float(result.get("outputTokens", 0)) * output_cost_per_million / 1_000_000

    return {
        "examples": total,
        "classificationAccuracy": classification_correct / total,
        "routingAccuracy": routing_correct / total,
        "invalidJsonRate": 1 - (len(valid) / total),
        "manualReviewPrecision": true_positive / max(true_positive + false_positive, 1),
        "manualReviewRecall": true_positive / max(true_positive + false_negative, 1),
        "falseAutoRouteRate": false_auto_routes / total,
        "medianLatencyMs": statistics.median(latency) if latency else 0.0,
        "p95LatencyMs": _percentile(latency, 0.95),
        "approximateInvocationCost": round(total_cost, 6),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Score captured Bedrock Agent evaluation results")
    parser.add_argument("--labels", type=Path, required=True)
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--input-cost-per-million", type=float, default=0.0)
    parser.add_argument("--output-cost-per-million", type=float, default=0.0)
    args = parser.parse_args()
    report = score(
        _read_jsonl(args.labels),
        _read_jsonl(args.results),
        input_cost_per_million=args.input_cost_per_million,
        output_cost_per_million=args.output_cost_per_million,
    )
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
