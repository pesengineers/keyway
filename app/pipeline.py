from __future__ import annotations

import os
import tempfile
import time
from pathlib import Path

from app.analysis import AnalysisBackend, build_analysis_backend
from app.cleanup import managed_work_directory
from app.config import Settings
from app.media import (
    normalize_audio,
    parse_filename_date,
    probe_duration,
    validate_source_file,
)
from app.models import PresentationDateSource, ProcessingResult
from app.transcription import FasterWhisperTranscriber


class VideoProcessor:
    def __init__(
        self,
        settings: Settings,
        *,
        transcriber: FasterWhisperTranscriber | None = None,
        analyzer: AnalysisBackend | None = None,
    ) -> None:
        self._settings = settings
        self._transcriber = transcriber or FasterWhisperTranscriber(settings)
        self._analyzer = analyzer or build_analysis_backend(settings)

    def process(self, source: Path, output_dir: Path) -> ProcessingResult:
        started = time.perf_counter()
        source = validate_source_file(source, self._settings.max_source_bytes)
        self._settings.prepare_directories()
        output_dir.mkdir(parents=True, exist_ok=True)

        with managed_work_directory(self._settings.temp_dir) as work_dir:
            duration = probe_duration(source, self._settings)
            audio_path = work_dir / "normalized.wav"
            normalize_audio(source, audio_path, self._settings)
            transcription = self._transcriber.transcribe(audio_path, duration)

        _atomic_write_text(output_dir / "transcript.txt", transcription.transcript + "\n")
        analysis = self._analyzer.analyze(transcription.transcript, source.name)

        filename_date = parse_filename_date(source.name)
        if filename_date is not None:
            presentation_date = filename_date
            presentation_date_source = PresentationDateSource.FILENAME
        elif analysis.result.presentation_date is not None:
            presentation_date = analysis.result.presentation_date
            presentation_date_source = PresentationDateSource.MODEL
        else:
            presentation_date = None
            presentation_date_source = PresentationDateSource.UNKNOWN

        result = ProcessingResult(
            source_filename=source.name,
            presentation_date=presentation_date,
            presentation_date_source=presentation_date_source,
            title=analysis.result.title,
            synopsis=analysis.result.synopsis,
            sensitivity=analysis.result.sensitivity,
            sensitivity_reason=analysis.result.sensitivity_reason,
            transcription=transcription.metadata,
            total_processing_seconds=round(time.perf_counter() - started, 3),
            warnings=[*transcription.warnings, *analysis.warnings],
        )
        _atomic_write_text(
            output_dir / "result.json",
            result.model_dump_json(indent=2) + "\n",
        )
        return result


def _atomic_write_text(destination: Path, content: str) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            prefix=f".{destination.name}.",
            suffix=".tmp",
            dir=destination.parent,
            delete=False,
        ) as handle:
            handle.write(content)
            temporary_path = Path(handle.name)
        os.replace(temporary_path, destination)
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
