from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from app.analysis import AnalysisOutput
from app.config import Settings
from app.models import AnalysisResult, Sensitivity, TranscriptionMetadata
from app.pipeline import VideoProcessor
from app.sources import LocalMediaSource
from app.transcription import TranscriptionOutput


class FakeTranscriber:
    def transcribe(self, audio_path: Path, duration_seconds: float) -> TranscriptionOutput:
        assert audio_path.read_bytes() == b"normalized audio"
        return TranscriptionOutput(
            transcript="Routine structural engineering training.",
            metadata=TranscriptionMetadata(
                model="fake-whisper",
                device="cpu",
                compute_type="int8",
                duration_seconds=duration_seconds,
                processing_seconds=2.0,
                realtime_factor=0.02,
            ),
            warnings=[],
        )


class FakeAnalyzer:
    def analyze(self, transcript: str, source_filename: str) -> AnalysisOutput:
        assert transcript == "Routine structural engineering training."
        return AnalysisOutput(
            result=AnalysisResult(
                title="Structural Engineering Training",
                synopsis="Routine instruction for structural engineers.",
                sensitivity=Sensitivity.SAFE,
                sensitivity_reason="Contains routine technical instruction only.",
                presentation_date=date(2020, 1, 1),
            ),
            warnings=[],
        )


def test_pipeline_writes_artifacts_and_prefers_filename_date(
    monkeypatch, tmp_path: Path
) -> None:
    source_path = tmp_path / "2021-08-19 training.mp4"
    source_path.write_bytes(b"video")
    settings = Settings(
        _env_file=None,
        temp_dir=tmp_path / "tmp",
        model_cache_dir=tmp_path / "models",
        output_dir=tmp_path / "unused-output",
    )

    monkeypatch.setattr("app.pipeline.probe_duration", lambda source, config: 100.0)

    def fake_normalize(source: Path, destination: Path, config: Settings) -> None:
        destination.write_bytes(b"normalized audio")

    monkeypatch.setattr("app.pipeline.normalize_audio", fake_normalize)
    output = tmp_path / "artifacts"
    processor = VideoProcessor(
        settings,
        transcriber=FakeTranscriber(),
        analyzer=FakeAnalyzer(),
    )

    result = processor.process(
        LocalMediaSource(source_path, settings.max_source_bytes), output
    )

    assert (output / "transcript.txt").read_text(encoding="utf-8") == (
        "Routine structural engineering training.\n"
    )
    persisted = json.loads((output / "result.json").read_text(encoding="utf-8"))
    assert persisted["success"] is True
    assert persisted["presentation_date"] == "2021-08-19"
    assert persisted["presentation_date_source"] == "filename"
    assert persisted["sensitivity"] == "safe"
    assert result.source_filename == source_path.name
    assert list(settings.temp_dir.iterdir()) == []
