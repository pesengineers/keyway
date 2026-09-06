from __future__ import annotations

import pytest

from app.analysis import AnalysisError
from app.main import _to_http
from app.media import MediaError
from app.sources import SourceError
from app.transcription import NoSpeechDetected, TranscriptionError


@pytest.mark.parametrize(
    ("exc", "code"),
    [
        (NoSpeechDetected("silent"), 422),  # terminal: do not retry
        (MediaError("bad container"), 422),  # terminal: do not retry
        (SourceError("graph 503"), 502),  # upstream: retry later
        (AnalysisError("ollama timeout"), 502),  # upstream: retry later
        (TranscriptionError("cuda crashed"), 500),  # worker fault
        (RuntimeError("unexpected"), 500),  # never leak internals
    ],
)
def test_pipeline_errors_map_to_actionable_status(exc: Exception, code: int) -> None:
    http = _to_http(exc)
    assert http.status_code == code
    if isinstance(exc, RuntimeError) and type(exc) is RuntimeError:
        assert "unexpected" not in http.detail
    else:
        assert str(exc).split(":")[-1].strip() in http.detail
