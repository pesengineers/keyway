from __future__ import annotations

import json
from pathlib import Path
import pytest

from app.analysis import parse_analysis_content
from app.models import Sensitivity


def test_sensitivity_evaluation_dataset_contract() -> None:
    eval_file = Path(__file__).parent / "data" / "sensitivity_eval_set.json"
    assert eval_file.exists()

    cases = json.loads(eval_file.read_text(encoding="utf-8"))
    assert len(cases) >= 6

    for case in cases:
        assert "id" in case
        assert "transcript" in case
        assert case["expected_sensitivity"] in {s.value for s in Sensitivity}

        # Simulate analysis engine result parsing for this test case
        mock_response = json.dumps({
            "title": f"Test {case['id']}",
            "synopsis": case["description"],
            "sensitivity": case["expected_sensitivity"],
            "sensitivity_reason": case["reasoning"],
            "presentation_date": None,
        })
        result = parse_analysis_content(mock_response)
        assert result.sensitivity.value == case["expected_sensitivity"]
