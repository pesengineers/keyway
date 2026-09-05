from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


def _settings(tmp_path: Path) -> Settings:
    executable = sys.executable
    return Settings(
        _env_file=None,
        ffmpeg_path=executable,
        ffprobe_path=executable,
        temp_dir=tmp_path / "tmp",
        model_cache_dir=tmp_path / "models",
        output_dir=tmp_path / "output",
        local_source_roots=[tmp_path / "media"],
    )


def test_health_and_readiness(tmp_path: Path) -> None:
    app = create_app(_settings(tmp_path))

    with TestClient(app) as client:
        assert client.get("/health").json() == {"status": "ok"}
        assert client.get("/ready").json() == {"status": "ready"}


def test_local_endpoint_rejects_path_outside_mount(tmp_path: Path) -> None:
    source = tmp_path / "outside.mp4"
    source.write_bytes(b"video")
    app = create_app(_settings(tmp_path))

    with TestClient(app) as client:
        response = client.post(
            "/v1/process/local",
            json={"source_path": str(source), "job_id": "path-check"},
        )

    assert response.status_code == 400
    assert "outside" in response.json()["detail"]


def test_local_endpoint_rejects_path_traversal_job_id(tmp_path: Path) -> None:
    app = create_app(_settings(tmp_path))

    with TestClient(app) as client:
        response = client.post(
            "/v1/process/local",
            json={"source_path": "ignored.mp4", "job_id": "../escape"},
        )

    assert response.status_code == 422
