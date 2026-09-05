from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from app.config import Settings
from app.models import TranscriptionMetadata

logger = logging.getLogger(__name__)


class TranscriptionError(RuntimeError):
    pass


@dataclass(frozen=True)
class TranscriptionOutput:
    transcript: str
    metadata: TranscriptionMetadata
    warnings: list[str]


class Transcriber(Protocol):
    def transcribe(
        self, audio_path: Path, duration_seconds: float
    ) -> TranscriptionOutput: ...


class FasterWhisperTranscriber:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def transcribe(self, audio_path: Path, duration_seconds: float) -> TranscriptionOutput:
        device = self._resolve_device()
        compute_type = self._resolve_compute_type(device)
        warnings: list[str] = []

        try:
            transcript, processing_seconds = self._transcribe_once(
                audio_path, device, compute_type
            )
        except Exception as exc:
            if self._settings.whisper_device != "auto" or device != "cuda":
                raise TranscriptionError(f"Transcription failed on {device}: {exc}") from exc
            logger.warning("CUDA transcription failed; retrying on CPU: %s", exc)
            warnings.append("CUDA transcription failed; CPU INT8 fallback was used")
            device = "cpu"
            compute_type = "int8"
            try:
                transcript, processing_seconds = self._transcribe_once(
                    audio_path, device, compute_type
                )
            except Exception as fallback_exc:
                raise TranscriptionError(
                    f"Transcription failed on CUDA and CPU fallback: {fallback_exc}"
                ) from fallback_exc

        if not transcript:
            raise TranscriptionError("Transcription completed without detecting speech")

        realtime_factor = (
            processing_seconds / duration_seconds if duration_seconds > 0 else 0.0
        )
        metadata = TranscriptionMetadata(
            model=self._settings.whisper_model,
            device=device,
            compute_type=compute_type,
            duration_seconds=round(duration_seconds, 3),
            processing_seconds=round(processing_seconds, 3),
            realtime_factor=round(realtime_factor, 4),
        )
        return TranscriptionOutput(transcript, metadata, warnings)

    def _resolve_device(self) -> str:
        configured = self._settings.whisper_device.lower()
        if configured != "auto":
            return configured
        try:
            import ctranslate2

            return "cuda" if ctranslate2.get_cuda_device_count() > 0 else "cpu"
        except Exception:
            return "cpu"

    def _resolve_compute_type(self, device: str) -> str:
        configured = self._settings.whisper_compute_type.lower()
        if configured != "auto":
            return configured
        return "float16" if device == "cuda" else "int8"

    def _transcribe_once(
        self, audio_path: Path, device: str, compute_type: str
    ) -> tuple[str, float]:
        from faster_whisper import WhisperModel

        model_options: dict[str, Any] = {
            "device": device,
            "compute_type": compute_type,
            "download_root": str(self._settings.model_cache_dir),
        }
        if self._settings.whisper_cpu_threads > 0:
            model_options["cpu_threads"] = self._settings.whisper_cpu_threads

        started = time.perf_counter()
        model = WhisperModel(self._settings.whisper_model, **model_options)
        segments, _ = model.transcribe(
            str(audio_path),
            beam_size=self._settings.whisper_beam_size,
            language="en",
            vad_filter=self._settings.whisper_vad_filter,
        )
        transcript = " ".join(
            text for segment in segments if (text := segment.text.strip())
        )
        return transcript, time.perf_counter() - started
