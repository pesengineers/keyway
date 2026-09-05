from __future__ import annotations

import logging
import os
import tempfile
import time
from pathlib import Path

from app.analysis import AnalysisBackend, build_analysis_backend
from app.cleanup import managed_work_directory
from app.config import Settings
from app.media import normalize_audio, parse_filename_date, probe_duration
from app.models import PresentationDateSource, ProcessingResult
from app.sources import MediaSource
from app.transcription import FasterWhisperTranscriber, Transcriber
logger = logging.getLogger(__name__)



class VideoProcessor:
    def __init__(
        self,
        settings: Settings,
        *,
        transcriber: Transcriber | None = None,
        analyzer: AnalysisBackend | None = None,
    ) -> None:
        self._settings = settings
        self._transcriber = transcriber or FasterWhisperTranscriber(settings)
        self._analyzer = analyzer or build_analysis_backend(settings)

    def process(self, source: MediaSource, output_dir: Path) -> ProcessingResult:
        started = time.perf_counter()
        logger.info("processing_started source=%r", source.filename)
        self._settings.prepare_directories()
        output_dir.mkdir(parents=True, exist_ok=True)

        with managed_work_directory(self._settings.temp_dir) as work_dir:
            with source.materialize(work_dir) as local_path:
                duration = probe_duration(local_path, self._settings)
                audio_path = work_dir / "normalized.wav"
                normalize_audio(local_path, audio_path, self._settings)
                transcription = self._transcriber.transcribe(audio_path, duration)

        _atomic_write_text(output_dir / "transcript.txt", transcription.transcript + "\n")
        analysis = self._analyzer.analyze(transcription.transcript, source.filename)

        filename_date = parse_filename_date(source.filename)
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
            source_filename=source.filename,
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
        logger.info(
            "processing_completed source=%r duration_seconds=%.3f "
            "transcription_seconds=%.3f realtime_factor=%.4f total_seconds=%.3f "
            "device=%s compute_type=%s warnings=%d",
            result.source_filename,
            result.transcription.duration_seconds,
            result.transcription.processing_seconds,
            result.transcription.realtime_factor,
            result.total_processing_seconds,
            result.transcription.device,
            result.transcription.compute_type,
            len(result.warnings),
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
