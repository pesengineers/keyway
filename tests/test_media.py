from __future__ import annotations

from pathlib import Path

import pytest

from app.config import Settings
from app.media import MediaError, validate_http_source, validate_source_file


def test_http_source_must_be_inside_configured_root(tmp_path: Path) -> None:
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    source = tmp_path / "outside.mp4"
    source.write_bytes(b"video")
    settings = Settings(_env_file=None, local_source_roots=[allowed])

    with pytest.raises(MediaError, match="outside"):
        validate_http_source(source, settings)


def test_reject_unsupported_media_extension(tmp_path: Path) -> None:
    source = tmp_path / "notes.txt"
    source.write_text("not video", encoding="utf-8")

    with pytest.raises(MediaError, match="Unsupported"):
        validate_source_file(source, 1_000)
