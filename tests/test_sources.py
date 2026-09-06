from __future__ import annotations

import pytest
import httpx
from pathlib import Path

from app.sources import SharePointMediaSource, SourceError
from app.config import Settings
from app.main import create_app
from fastapi.testclient import TestClient


def test_sharepoint_source_materialize_success(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        # OAuth token request
        if request.url.host == "login.microsoftonline.com":
            assert request.url.path == "/tenant-123/oauth2/v2.0/token"
            return httpx.Response(200, json={"access_token": "mock-token-xyz"})
        # Graph content download
        if request.url.host == "graph.microsoft.com":
            assert request.url.path == "/v1.0/sites/site-abc/drives/drive-def/items/item-ghi/content"
            assert request.headers["authorization"] == "Bearer mock-token-xyz"
            return httpx.Response(200, content=b"fake-video-bytes-123")
        return httpx.Response(404)

    mock_transport = httpx.MockTransport(handler)

    source = SharePointMediaSource(
        site_id="site-abc",
        drive_id="drive-def",
        item_id="item-ghi",
        expected_filename="test_video.mp4",
        max_source_bytes=10000,
        tenant_id="tenant-123",
        client_id="client-456",
        client_secret="secret-789",
        transport=mock_transport,
    )

    work_dir = tmp_path / "work"
    work_dir.mkdir()

    with source.materialize(work_dir) as local_path:
        assert local_path.is_file()
        assert local_path.name == "test_video.mp4"
        assert local_path.read_bytes() == b"fake-video-bytes-123"

    # Verify temp file cleaned up after context exit
    assert not (work_dir / "test_video.mp4").exists()


def test_sharepoint_source_rejects_exceeded_size(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "login.microsoftonline.com":
            return httpx.Response(200, json={"access_token": "mock-token-xyz"})
        return httpx.Response(200, content=b"123456789012345")

    mock_transport = httpx.MockTransport(handler)

    source = SharePointMediaSource(
        site_id="site-abc",
        drive_id="drive-def",
        item_id="item-ghi",
        expected_filename="test_video.mp4",
        max_source_bytes=10,  # Max 10 bytes, payload is 15
        tenant_id="tenant-123",
        client_id="client-456",
        client_secret="secret-789",
        transport=mock_transport,
    )

    work_dir = tmp_path / "work"
    work_dir.mkdir()

    with pytest.raises(SourceError, match="exceeded maximum allowed size"):
        with source.materialize(work_dir):
            pass

    assert not (work_dir / "test_video.mp4").exists()


def test_sharepoint_endpoint_rejects_unconfigured_credentials(tmp_path: Path) -> None:
    executable = Path(tmp_path / "dummy_bin")
    executable.touch()
    settings = Settings(
        _env_file=None,
        ffmpeg_path=str(executable),
        ffprobe_path=str(executable),
        temp_dir=tmp_path / "tmp",
        model_cache_dir=tmp_path / "models",
        output_dir=tmp_path / "output",
        analysis_api_key="key",
    )
    app = create_app(settings)

    with TestClient(app) as client:
        response = client.post(
            "/v1/process/sharepoint",
            json={
                "job_id": "sp-job-1",
                "site_id": "site1",
                "drive_id": "drive1",
                "item_id": "item1",
                "filename": "video.mp4",
            },
        )

    assert response.status_code == 503
    assert "not configured" in response.json()["detail"]


def test_sharepoint_endpoint_rejects_path_traversal_filename(tmp_path: Path) -> None:
    executable = Path(tmp_path / "dummy_bin")
    executable.touch()
    settings = Settings(
        _env_file=None,
        ffmpeg_path=str(executable),
        ffprobe_path=str(executable),
        temp_dir=tmp_path / "tmp",
        model_cache_dir=tmp_path / "models",
        output_dir=tmp_path / "output",
        analysis_api_key="key",
        graph_tenant_id="tenant",
        graph_client_id="client",
        graph_client_secret="secret",
    )
    app = create_app(settings)

    with TestClient(app) as client:
        response = client.post(
            "/v1/process/sharepoint",
            json={
                "job_id": "sp-job-1",
                "site_id": "site1",
                "drive_id": "drive1",
                "item_id": "item1",
                "filename": "../evil.mp4",
            },
        )

    assert response.status_code == 422
