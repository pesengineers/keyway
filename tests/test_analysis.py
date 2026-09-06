from __future__ import annotations

import json
import httpx

import pytest

from app.analysis import (
    AnalysisError,
    OllamaAnalysisBackend,
    OpenAICompatibleAnalysisBackend,
    build_analysis_backend,
    parse_analysis_content,
)
from app.config import Settings
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


def test_openai_compatible_backend_uses_structured_output() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/chat/completions"
        assert request.headers["authorization"] == "Bearer test-key"
        payload = json.loads(request.content)
        assert payload["response_format"]["json_schema"]["strict"] is True
        assert set(payload["response_format"]["json_schema"]["schema"]["required"]) == {
            "title",
            "synopsis",
            "sensitivity",
            "sensitivity_reason",
            "presentation_date",
            "presentation_date_evidence",
        }
        content = json.dumps(
            {
                "title": "Revit Parameters",
                "synopsis": "Technical instruction about Revit parameters.",
                "sensitivity": "safe",
                "sensitivity_reason": "Routine software instruction only.",
                "presentation_date": None,
            }
        )
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": content}}]},
        )

    settings = Settings(
        _env_file=None,
        analysis_api_key="test-key",
        analysis_base_url="https://analysis.example/v1",
    )
    backend = OpenAICompatibleAnalysisBackend(
        settings, transport=httpx.MockTransport(handler)
    )

    output = backend.analyze("Revit training transcript.", "training.mp4")

    assert output.result.title == "Revit Parameters"
    assert output.result.sensitivity is Sensitivity.SAFE



def test_ollama_backend_uses_format_schema() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/chat"
        payload = json.loads(request.content)
        assert payload["model"] == "llama3.2:latest"
        assert payload["stream"] is False
        assert "properties" in payload["format"]
        # llama.cpp grammar compiler rejects string length bounds (HTTP 400)
        for prop in payload["format"]["properties"].values():
            assert not {"minLength", "maxLength", "format"} & prop.keys()
        assert set(payload["format"]["required"]) == {
            "title",
            "synopsis",
            "sensitivity",
            "sensitivity_reason",
            "presentation_date",
            "presentation_date_evidence",
        }
        content = json.dumps(
            {
                "title": "Local Ollama Analysis",
                "synopsis": "Technical training analyzed locally via Ollama.",
                "sensitivity": "internal_only",
                "sensitivity_reason": "Contains internal architectural workflows.",
                "presentation_date": "2023-05-10",
            }
        )
        return httpx.Response(
            200,
            json={"message": {"role": "assistant", "content": content}},
        )

    settings = Settings(
        _env_file=None,
        analysis_backend="ollama",
        analysis_base_url="http://localhost:11434",
        analysis_model="llama3.2:latest",
    )
    backend = OllamaAnalysisBackend(
        settings, transport=httpx.MockTransport(handler)
    )

    output = backend.analyze("Internal workflow overview.", "2023-05-10 workflow.mp4")

    assert output.result.title == "Local Ollama Analysis"
    assert output.result.sensitivity is Sensitivity.INTERNAL_ONLY
    # Date came back without evidence in the transcript: discarded, not trusted.
    assert output.result.presentation_date is None
    assert any("presentation_date discarded" in w for w in output.warnings)


def _openai_backend_returning(payload: dict) -> OpenAICompatibleAnalysisBackend:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json={"choices": [{"message": {"content": json.dumps(payload)}}]}
        )

    settings = Settings(
        _env_file=None, analysis_api_key="k", analysis_base_url="https://x.example/v1"
    )
    return OpenAICompatibleAnalysisBackend(settings, transport=httpx.MockTransport(handler))


_BASE = {
    "title": "Wood Design Update",
    "synopsis": "Spreadsheet changes.",
    "sensitivity": "safe",
    "sensitivity_reason": "No listed category was present.",
}


def test_date_kept_when_evidence_is_verbatim_in_transcript() -> None:
    transcript = "Welcome everyone, today is November 18th, 2021 and we're covering wood."
    backend = _openai_backend_returning(
        {**_BASE, "presentation_date": "2021-11-18",
         "presentation_date_evidence": "today is November 18th, 2021"}
    )
    out = backend.analyze(transcript, "x.mp4")
    assert str(out.result.presentation_date) == "2021-11-18"
    assert out.warnings == []


def test_date_discarded_when_evidence_not_in_transcript() -> None:
    transcript = "Welcome everyone, we're covering wood spreadsheets this session."
    backend = _openai_backend_returning(
        {**_BASE, "presentation_date": "2023-10-01",
         "presentation_date_evidence": "the October 2023 release"}
    )
    out = backend.analyze(transcript, "x.mp4")
    assert out.result.presentation_date is None
    assert out.result.presentation_date_evidence is None
    assert any("discarded" in w for w in out.warnings)


def test_date_discarded_when_evidence_missing() -> None:
    backend = _openai_backend_returning(
        {**_BASE, "presentation_date": "2023-10-01", "presentation_date_evidence": None}
    )
    out = backend.analyze("no dates here at all", "x.mp4")
    assert out.result.presentation_date is None


def test_build_analysis_backend_selects_ollama() -> None:
    settings = Settings(
        _env_file=None,
        analysis_backend="ollama",
        analysis_base_url="http://localhost:11434",
    )
    backend = build_analysis_backend(settings)
    assert isinstance(backend, OllamaAnalysisBackend)


def test_ollama_backend_handles_http_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="Internal Ollama Error")

    settings = Settings(
        _env_file=None,
        analysis_backend="ollama",
        analysis_base_url="http://localhost:11434",
    )
    backend = OllamaAnalysisBackend(
        settings, transport=httpx.MockTransport(handler)
    )

    with pytest.raises(AnalysisError, match="HTTP 500"):
        backend.analyze("Some text", "test.mp4")

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
