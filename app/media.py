from __future__ import annotations

import math
import re
import subprocess
from datetime import date
from pathlib import Path

from app.config import Settings

_LEADING_DATE = re.compile(r"^(?P<date>\d{4}-\d{2}-\d{2})(?:\D|$)")
_ALLOWED_VIDEO_SUFFIXES = {
    ".avi",
    ".m4v",
    ".mkv",
    ".mov",
    ".mp4",
    ".mpeg",
    ".mpg",
    ".webm",
    ".wmv",
}


class MediaError(RuntimeError):
    pass


def parse_filename_date(filename: str | Path) -> date | None:
    match = _LEADING_DATE.match(Path(filename).name)
    if match is None:
        return None
    try:
        return date.fromisoformat(match.group("date"))
    except ValueError:
        return None


def validate_source_file(source: Path, max_source_bytes: int) -> Path:
    try:
        resolved = source.expanduser().resolve(strict=True)
    except OSError as exc:
        raise MediaError(f"Source file is not accessible: {source}") from exc

    if not resolved.is_file():
        raise MediaError(f"Source path is not a regular file: {source}")
    if resolved.suffix.lower() not in _ALLOWED_VIDEO_SUFFIXES:
        raise MediaError(f"Unsupported video extension: {resolved.suffix or '<none>'}")
    if resolved.stat().st_size > max_source_bytes:
        raise MediaError(
            f"Source file exceeds the configured {max_source_bytes}-byte limit"
        )
    return resolved


def validate_http_source(source: Path, settings: Settings) -> Path:
    resolved = validate_source_file(source, settings.max_source_bytes)
    roots = [root.expanduser().resolve(strict=False) for root in settings.local_source_roots]
    if not roots:
        raise MediaError("LOCAL_SOURCE_ROOTS is empty; local-path API access is disabled")
    if not any(resolved.is_relative_to(root) for root in roots):
        raise MediaError("Source path is outside the configured local source roots")
    return resolved


def probe_duration(source: Path, settings: Settings) -> float:
    command = [
        settings.ffprobe_path,
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        str(source),
    ]
    completed = _run_media_command(command, settings.process_timeout_seconds, "ffprobe")
    try:
        duration = float(completed.stdout.strip())
    except ValueError as exc:
        raise MediaError("ffprobe did not return a valid media duration") from exc
    if not math.isfinite(duration) or duration <= 0:
        raise MediaError("Source media has no positive finite duration")
    return duration


def normalize_audio(source: Path, destination: Path, settings: Settings) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    command = [
        settings.ffmpeg_path,
        "-hide_banner",
        "-loglevel",
        "error",
        "-nostdin",
        "-y",
        "-i",
        str(source),
        "-map",
        "0:a:0",
        "-vn",
        "-ac",
        "1",
        "-ar",
        "16000",
        "-c:a",
        "pcm_s16le",
        str(destination),
    ]
    _run_media_command(command, settings.process_timeout_seconds, "ffmpeg")
    if not destination.is_file() or destination.stat().st_size == 0:
        raise MediaError("ffmpeg completed without producing normalized audio")


def _run_media_command(
    command: list[str], timeout_seconds: float, program_name: str
) -> subprocess.CompletedProcess[str]:
    try:
        completed = subprocess.run(
            command,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
            shell=False,
        )
    except FileNotFoundError as exc:
        raise MediaError(f"{program_name} executable was not found") from exc
    except subprocess.TimeoutExpired as exc:
        raise MediaError(f"{program_name} exceeded the processing timeout") from exc

    if completed.returncode != 0:
        detail = completed.stderr.strip()[-2_000:] or "no diagnostic output"
        raise MediaError(f"{program_name} failed: {detail}")
    return completed
