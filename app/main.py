from __future__ import annotations

import asyncio
import logging
import os
import shutil
import tempfile
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field

from app.analysis import AnalysisError
from app.config import Settings, get_settings
from app.media import MediaError, validate_http_source
from app.models import ProcessingResult
from app.pipeline import VideoProcessor
from app.sources import LocalMediaSource, SharePointMediaSource, SourceError
from app.transcription import TranscriptionError


class LocalProcessRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_path: Path
    job_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


class SharePointProcessRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
    site_id: str = Field(min_length=1, max_length=256)
    drive_id: str = Field(min_length=1, max_length=256)
    item_id: str = Field(min_length=1, max_length=256)
    filename: str = Field(pattern=r"^[^/\\?%*:|\"<>\r\n]+\.[A-Za-z0-9]+$")


def create_app(settings: Settings | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        active_settings = settings or get_settings()
        logging.getLogger("httpx").setLevel(logging.WARNING)
        logging.getLogger("httpcore").setLevel(logging.WARNING)
        active_settings.prepare_directories()
        application.state.settings = active_settings
        application.state.job_slots = asyncio.Semaphore(
            active_settings.max_concurrent_jobs
        )
        yield

    application = FastAPI(
        title="keyway",
        version="0.1.0",
        lifespan=lifespan,
    )

    @application.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @application.get("/ready")
    def ready(request: Request) -> dict[str, str]:
        active_settings: Settings = request.app.state.settings
        problems = _readiness_problems(active_settings)
        if problems:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=problems,
            )
        return {"status": "ready"}

    @application.post("/v1/process/local", response_model=ProcessingResult)
    async def process_local(
        body: LocalProcessRequest, request: Request
    ) -> ProcessingResult:
        active_settings: Settings = request.app.state.settings
        try:
            source = validate_http_source(body.source_path, active_settings)
        except MediaError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
            ) from exc

        output_dir = active_settings.output_dir / body.job_id
        semaphore: asyncio.Semaphore = request.app.state.job_slots
        async with semaphore:
            try:
                media_source = LocalMediaSource(
                    source, active_settings.max_source_bytes
                )
                return await asyncio.to_thread(
                    VideoProcessor(active_settings).process,
                    media_source,
                    output_dir,
                )
            except MediaError as exc:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail=str(exc),
                ) from exc
            except AnalysisError as exc:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)
                ) from exc
            except TranscriptionError as exc:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=str(exc),
                ) from exc

    @application.post("/v1/process/sharepoint", response_model=ProcessingResult)
    async def process_sharepoint(
        body: SharePointProcessRequest, request: Request
    ) -> ProcessingResult:
        active_settings: Settings = request.app.state.settings
        if not (
            active_settings.graph_tenant_id
            and active_settings.graph_client_id
            and active_settings.graph_client_secret
        ):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="SharePoint integration credentials are not configured",
            )

        media_source = SharePointMediaSource(
            site_id=body.site_id,
            drive_id=body.drive_id,
            item_id=body.item_id,
            expected_filename=body.filename,
            max_source_bytes=active_settings.max_source_bytes,
            tenant_id=active_settings.graph_tenant_id,
            client_id=active_settings.graph_client_id,
            client_secret=active_settings.graph_client_secret.get_secret_value(),
            base_url=active_settings.graph_base_url,
            timeout_seconds=active_settings.graph_timeout_seconds,
        )

        output_dir = active_settings.output_dir / body.job_id
        semaphore: asyncio.Semaphore = request.app.state.job_slots
        async with semaphore:
            try:
                return await asyncio.to_thread(
                    VideoProcessor(active_settings).process,
                    media_source,
                    output_dir,
                )
            except SourceError as exc:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=f"SharePoint source failed: {exc}",
                ) from exc
            except MediaError as exc:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail=str(exc),
                ) from exc
            except AnalysisError as exc:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)
                ) from exc
            except TranscriptionError as exc:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=str(exc),
                ) from exc

    return application


def _readiness_problems(settings: Settings) -> list[str]:
    problems: list[str] = []
    for name, executable in (
        ("ffmpeg", settings.ffmpeg_path),
        ("ffprobe", settings.ffprobe_path),
    ):
        if not _executable_exists(executable):
            problems.append(f"{name} executable is unavailable")
    for name, directory in (
        ("temporary", settings.temp_dir),
        ("model cache", settings.model_cache_dir),
        ("output", settings.output_dir),
    ):
        try:
            directory.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(dir=directory):
                pass
        except OSError:
            problems.append(f"{name} directory is not writable")
    backend = settings.analysis_backend.lower()
    if backend not in {"openai", "ollama"}:
        problems.append(f"analysis backend is unsupported: {settings.analysis_backend}")
    elif backend == "openai" and settings.analysis_api_key is None:
        problems.append("analysis API key is not configured")
    return problems


def _executable_exists(executable: str) -> bool:
    if os.path.dirname(executable):
        return Path(executable).is_file()
    return shutil.which(executable) is not None


app = create_app()
