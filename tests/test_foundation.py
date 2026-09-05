from __future__ import annotations

from pathlib import Path

import pytest

from app.cleanup import managed_work_directory
from app.config import Settings
from app.media import parse_filename_date


def test_parse_leading_filename_date() -> None:
    assert str(parse_filename_date("2021-08-19 12.01 P_T (SCS).mp4")) == "2021-08-19"


@pytest.mark.parametrize(
    "filename",
    [
        "training 2021-08-19.mp4",
        "2021-02-29 training.mp4",
        "20210819-training.mp4",
    ],
)
def test_reject_missing_or_invalid_leading_date(filename: str) -> None:
    assert parse_filename_date(filename) is None


def test_environment_overrides(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("WHISPER_MODEL", "tiny.en")
    monkeypatch.setenv("WHISPER_DEVICE", "cpu")
    monkeypatch.setenv("WHISPER_COMPUTE_TYPE", "int8")
    monkeypatch.setenv("TEMP_DIR", str(tmp_path / "work"))
    monkeypatch.setenv("LOCAL_SOURCE_ROOTS", f'["{tmp_path.as_posix()}"]')
    monkeypatch.setenv("ANALYSIS_API_KEY", "")

    settings = Settings(_env_file=None)

    assert settings.whisper_model == "tiny.en"
    assert settings.whisper_device == "cpu"
    assert settings.whisper_compute_type == "int8"
    assert settings.temp_dir == tmp_path / "work"
    assert settings.local_source_roots == [tmp_path]
    assert settings.analysis_api_key is None


def test_managed_work_directory_cleans_after_failure(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError):
        with managed_work_directory(tmp_path) as work_dir:
            (work_dir / "audio.wav").write_bytes(b"temporary")
            raise RuntimeError("processing failed")

    assert list(tmp_path.iterdir()) == []
