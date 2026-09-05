from __future__ import annotations

import tempfile
from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    whisper_model: str = "small.en"
    whisper_device: str = "auto"
    whisper_compute_type: str = "auto"
    whisper_beam_size: int = Field(default=5, ge=1, le=20)
    whisper_cpu_threads: int = Field(default=0, ge=0)
    whisper_vad_filter: bool = True

    ffmpeg_path: str = "ffmpeg"
    ffprobe_path: str = "ffprobe"
    temp_dir: Path = Field(
        default_factory=lambda: Path(tempfile.gettempdir()) / "video-review-worker"
    )
    model_cache_dir: Path = Field(default=Path.home() / ".cache" / "huggingface")
    output_dir: Path = Path("/output")

    analysis_backend: str = "openai"
    analysis_base_url: str = "https://api.openai.com/v1"
    analysis_api_key: SecretStr | None = None
    analysis_model: str = "gpt-4.1-mini"
    analysis_timeout_seconds: float = Field(default=120.0, gt=0)
    analysis_max_characters: int = Field(default=120_000, ge=1_000)

    local_source_roots: list[Path] = Field(default_factory=list)
    max_source_bytes: int = Field(default=50 * 1024**3, gt=0)
    process_timeout_seconds: float = Field(default=7_200.0, gt=0)
    max_concurrent_jobs: int = Field(default=1, ge=1, le=16)

    log_level: str = "INFO"

    def prepare_directories(self) -> None:
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        self.model_cache_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
