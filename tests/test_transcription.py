from __future__ import annotations

from pathlib import Path

import pytest

from app.config import Settings
from app.transcription import FasterWhisperTranscriber


def _stub_cuda_types(monkeypatch, supported: list[str]) -> None:
    import ctranslate2

    monkeypatch.setattr(
        ctranslate2, "get_supported_compute_types", lambda device: supported
    )


def test_auto_cuda_failure_falls_back_to_cpu_int8(monkeypatch, tmp_path: Path) -> None:
    settings = Settings(
        _env_file=None,
        whisper_device="auto",
        whisper_compute_type="auto",
        model_cache_dir=tmp_path / "models",
    )
    transcriber = FasterWhisperTranscriber(settings)
    monkeypatch.setattr(transcriber, "_resolve_device", lambda: "cuda")
    _stub_cuda_types(monkeypatch, ["float16", "int8_float16", "float32"])
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


@pytest.mark.parametrize(
    ("supported", "expected"),
    [
        (["float32", "int8", "int8_float32"], "float32"),  # Pascal (Quadro P2000)
        (["float16", "int8_float16", "float32", "int8"], "float16"),  # Turing+
        (["int8_float16", "float32"], "int8_float16"),
    ],
)
def test_auto_cuda_compute_type_respects_device_support(
    monkeypatch, tmp_path: Path, supported: list[str], expected: str
) -> None:
    settings = Settings(
        _env_file=None, whisper_compute_type="auto", model_cache_dir=tmp_path
    )
    _stub_cuda_types(monkeypatch, supported)

    assert FasterWhisperTranscriber(settings)._resolve_compute_type("cuda") == expected


def test_explicit_compute_type_is_not_overridden(tmp_path: Path) -> None:
    settings = Settings(
        _env_file=None, whisper_compute_type="int8_float32", model_cache_dir=tmp_path
    )
    assert FasterWhisperTranscriber(settings)._resolve_compute_type("cuda") == "int8_float32"
