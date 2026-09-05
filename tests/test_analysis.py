from __future__ import annotations

import json

import pytest

from app.analysis import AnalysisError, parse_analysis_content
from app.models import Sensitivity


def test_parse_structured_analysis() -> None:
    content = json.dumps(
        {
            "title": "Steel Connection Design Fundamentals",
            "synopsis": "An overview of practical steel connection design methods.",
            "sensitivity": "safe",
            "sensitivity_reason": "Routine engineering instruction with no private data.",
            "presentation_date": "2021-08-19",
        }
    )

    result = parse_analysis_content(content)

    assert result.title == "Steel Connection Design Fundamentals"
    assert result.sensitivity is Sensitivity.SAFE
    assert str(result.presentation_date) == "2021-08-19"


def test_reject_unknown_analysis_fields() -> None:
    content = json.dumps(
        {
            "title": "Training",
            "synopsis": "Technical training.",
            "sensitivity": "safe",
            "sensitivity_reason": "No sensitive content.",
            "presentation_date": None,
            "confidence": 0.99,
        }
    )

    with pytest.raises(AnalysisError):
        parse_analysis_content(content)


def test_reject_invalid_sensitivity() -> None:
    content = json.dumps(
        {
            "title": "Training",
            "synopsis": "Technical training.",
            "sensitivity": "confidential",
            "sensitivity_reason": "Unrecognized classification.",
            "presentation_date": None,
        }
    )

    with pytest.raises(AnalysisError):
        parse_analysis_content(content)
