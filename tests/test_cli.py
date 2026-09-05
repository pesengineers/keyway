from __future__ import annotations

import json
from pathlib import Path

from app.cli import _process
from app.config import Settings


def test_processing_failure_writes_safe_result(tmp_path: Path) -> None:
    output = tmp_path / "output"
    settings = Settings(_env_file=None, analysis_api_key=None)

    exit_code = _process(tmp_path / "missing.mp4", output, settings)

    assert exit_code == 1
    result = json.loads((output / "result.json").read_text(encoding="utf-8"))
    assert result == {
        "success": False,
        "source_filename": "missing.mp4",
        "error": "ANALYSIS_API_KEY is required for the OpenAI backend",
        "warnings": [],
    }
