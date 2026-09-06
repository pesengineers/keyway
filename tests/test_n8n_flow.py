from __future__ import annotations

import json
from pathlib import Path
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.models import Sensitivity, ProcessingResult


def test_n8n_local_source_flow(tmp_path: Path, monkeypatch) -> None:
    # Set up mock media environment
    media_dir = tmp_path / "media"
    media_dir.mkdir()
    sample_video = media_dir / "2021-08-19 12.01 P_T (SCS).mp4"
    sample_video.write_bytes(b"dummy-video-data")

    # Mock media duration and normalization
    monkeypatch.setattr("app.pipeline.probe_duration", lambda source, config: 120.0)
    monkeypatch.setattr("app.pipeline.normalize_audio", lambda src, dst, cfg: dst.write_bytes(b"fake-pcm"))

    # Mock transcription
    class MockTranscriber:
        def transcribe(self, audio_path: Path, duration_seconds: float):
            from app.models import TranscriptionMetadata
            from app.transcription import TranscriptionOutput
            return TranscriptionOutput(
                transcript="Revit Dynamo parameters workflow training session.",
                metadata=TranscriptionMetadata(
                    model="small.en",
                    device="cpu",
                    compute_type="int8",
                    duration_seconds=duration_seconds,
                    processing_seconds=5.0,
                    realtime_factor=0.0417,
                ),
                warnings=[],
            )

    # Mock analysis backend
    class MockAnalyzer:
        def analyze(self, transcript: str, source_filename: str):
            from app.analysis import AnalysisOutput
            from app.models import AnalysisResult
            return AnalysisOutput(
                result=AnalysisResult(
                    title="Revit Dynamo Parameters Session",
                    synopsis="Training session covering Revit and Dynamo automation.",
                    sensitivity=Sensitivity.SAFE,
                    sensitivity_reason="Routine technical instruction with no confidential content.",
                    presentation_date=None,
                ),
                warnings=[],
            )

    executable = Path(tmp_path / "dummy_bin")
    executable.touch()
    settings = Settings(
        _env_file=None,
        ffmpeg_path=str(executable),
        ffprobe_path=str(executable),
        temp_dir=tmp_path / "tmp",
        model_cache_dir=tmp_path / "models",
        output_dir=tmp_path / "output",
        local_source_roots=[media_dir],
        analysis_api_key="mock-key",
    )

    app = create_app(settings)
    monkeypatch.setattr(
        "app.main.VideoProcessor",
        lambda cfg: __import__("app.pipeline", fromlist=["VideoProcessor"]).VideoProcessor(
            cfg,
            transcriber=MockTranscriber(),
            analyzer=MockAnalyzer(),
        ),
    )

    with TestClient(app) as client:
        # Simulate n8n calling Keyway
        n8n_payload = {
            "job_id": "n8n-exec-98765",
            "source_path": str(sample_video),
        }
        response = client.post("/v1/process/local", json=n8n_payload)

    assert response.status_code == 200
    data = response.json()

    # Validate schema fields required by n8n downstream logic
    assert data["success"] is True
    assert data["source_filename"] == "2021-08-19 12.01 P_T (SCS).mp4"
    assert data["presentation_date"] == "2021-08-19"
    assert data["presentation_date_source"] == "filename"
    assert data["title"] == "Revit Dynamo Parameters Session"
    assert data["sensitivity"] == "safe"
    assert data["sensitivity_reason"] == "Routine technical instruction with no confidential content."
    assert data["transcription"]["realtime_factor"] > 0
    assert (tmp_path / "output" / "n8n-exec-98765" / "transcript.txt").exists()
    assert (tmp_path / "output" / "n8n-exec-98765" / "result.json").exists()
