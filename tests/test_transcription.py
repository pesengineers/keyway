from __future__ import annotations

from pathlib import Path

from app.config import Settings
from app.transcription import FasterWhisperTranscriber


def test_auto_cuda_failure_falls_back_to_cpu_int8(monkeypatch, tmp_path: Path) -> None:
    settings = Settings(
        _env_file=None,
        whisper_device="auto",
        whisper_compute_type="auto",
        model_cache_dir=tmp_path / "models",
    )
    transcriber = FasterWhisperTranscriber(settings)
    monkeypatch.setattr(transcriber, "_resolve_device", lambda: "cuda")
    attempts: list[tuple[str, str]] = []

    def transcribe_once(audio_path: Path, device: str, compute_type: str):
        attempts.append((device, compute_type))
        if device == "cuda":
            raise RuntimeError("CUDA runtime unavailable")
        return "Recovered transcript", 4.0

    monkeypatch.setattr(transcriber, "_transcribe_once", transcribe_once)

    output = transcriber.transcribe(tmp_path / "audio.wav", 20.0)

    assert attempts == [("cuda", "float16"), ("cpu", "int8")]
    assert output.transcript == "Recovered transcript"
    assert output.metadata.device == "cpu"
    assert output.metadata.compute_type == "int8"
    assert output.metadata.realtime_factor == 0.2
    assert output.warnings == [
        "CUDA transcription failed; CPU INT8 fallback was used"
    ]
