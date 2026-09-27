from scripts.evaluate_agent import score


def test_scores_safety_weighted_evaluation_results() -> None:
    labels = [
        {
            "id": "one",
            "expectedCategory": "UNKNOWN",
            "expectedDestination": "MANUAL_REVIEW",
            "expectedManualReview": True,
        },
        {
            "id": "two",
            "expectedCategory": "GENERAL_INQUIRY",
            "expectedDestination": "CUSTOMER_SERVICE",
            "expectedManualReview": False,
        },
    ]
    results = [
        {
            "id": "one",
            "validJson": True,
            "classification": "UNKNOWN",
            "destination": "CUSTOMER_SERVICE",
            "requiresHumanReview": False,
            "latencyMs": 100,
            "inputTokens": 1_000,
            "outputTokens": 100,
        },
        {
            "id": "two",
            "validJson": True,
            "classification": "GENERAL_INQUIRY",
            "destination": "CUSTOMER_SERVICE",
            "requiresHumanReview": False,
            "latencyMs": 200,
            "inputTokens": 1_000,
            "outputTokens": 100,
        },
    ]

    report = score(
        labels,
        results,
        input_cost_per_million=1.0,
        output_cost_per_million=2.0,
    )

    assert report["classificationAccuracy"] == 1.0
    assert report["routingAccuracy"] == 0.5
    assert report["falseAutoRouteRate"] == 0.5
    assert report["medianLatencyMs"] == 150
    assert report["approximateInvocationCost"] == 0.0024
