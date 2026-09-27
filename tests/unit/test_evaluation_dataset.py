import json
from pathlib import Path


def test_evaluation_dataset_has_at_least_fifty_labeled_examples() -> None:
    path = Path(__file__).parents[1] / "fixtures" / "evaluation" / "requests.jsonl"
    examples = [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line
    ]

    assert len(examples) >= 50
    assert len({example["id"] for example in examples}) == len(examples)
    assert all(
        {
            "subject",
            "description",
            "expectedCategory",
            "expectedDestination",
            "expectedManualReview",
        }
        <= example.keys()
        for example in examples
    )
