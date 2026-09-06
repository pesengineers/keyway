from __future__ import annotations

from collections.abc import Iterator
from contextlib import AbstractContextManager, contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from app.media import validate_source_file


class SourceError(RuntimeError):
    pass

class MediaSource(Protocol):
    @property
    def filename(self) -> str: ...

    def materialize(self, work_dir: Path) -> AbstractContextManager[Path]: ...


@dataclass(frozen=True, slots=True)
class LocalMediaSource:
    path: Path
    max_source_bytes: int

    @property
    def filename(self) -> str:
        return self.path.name

    @contextmanager
    def materialize(self, work_dir: Path) -> Iterator[Path]:
        del work_dir
        yield validate_source_file(self.path, self.max_source_bytes)


@dataclass(frozen=True, slots=True)
class SharePointMediaSource:
    site_id: str
    drive_id: str
    item_id: str
    expected_filename: str
    max_source_bytes: int
    tenant_id: str
    client_id: str
    client_secret: str
    base_url: str = "https://graph.microsoft.com/v1.0"
    timeout_seconds: float = 300.0
    transport: object | None = None

    @property
    def filename(self) -> str:
        return self.expected_filename

    @contextmanager
    def materialize(self, work_dir: Path) -> Iterator[Path]:
        import httpx

        target_path = work_dir / self.expected_filename
        token = self._get_access_token()

        # Constrained Microsoft Graph endpoint:
        # GET /sites/{site-id}/drives/{drive-id}/items/{item-id}/content
        download_url = (
            f"{self.base_url.rstrip('/')}/sites/{self.site_id}"
            f"/drives/{self.drive_id}/items/{self.item_id}/content"
        )
        headers = {
            "Authorization": f"Bearer {token}",
            "User-Agent": "Keyway-Worker/0.1.0",
        }

        total_bytes = 0
        transport = self.transport if isinstance(self.transport, httpx.BaseTransport) else None
        try:
            with httpx.Client(
                timeout=self.timeout_seconds,
                follow_redirects=True,
                transport=transport,
            ) as client:
                with client.stream("GET", download_url, headers=headers) as response:
                    response.raise_for_status()
                    with open(target_path, "wb") as file_out:
                        for chunk in response.iter_bytes(chunk_size=65536):
                            total_bytes += len(chunk)
                            if total_bytes > self.max_source_bytes:
                                raise SourceError(
                                    f"Remote file exceeded maximum allowed size ({self.max_source_bytes} bytes)"
                                )
                            file_out.write(chunk)
        except httpx.TimeoutException as exc:
            target_path.unlink(missing_ok=True)
            raise SourceError("Download from SharePoint timed out") from exc
        except httpx.HTTPStatusError as exc:
            target_path.unlink(missing_ok=True)
            raise SourceError(f"SharePoint Graph returned HTTP {exc.response.status_code}") from exc
        except httpx.RequestError as exc:
            target_path.unlink(missing_ok=True)
            raise SourceError(f"SharePoint Graph request failed: {exc}") from exc
        except Exception:
            target_path.unlink(missing_ok=True)
            raise

        try:
            yield validate_source_file(target_path, self.max_source_bytes)
        finally:
            target_path.unlink(missing_ok=True)

    def _get_access_token(self) -> str:
        import httpx

        token_url = f"https://login.microsoftonline.com/{self.tenant_id}/oauth2/v2.0/token"
        payload = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "scope": "https://graph.microsoft.com/.default",
            "grant_type": "client_credentials",
        }
        transport = self.transport if isinstance(self.transport, httpx.BaseTransport) else None
        try:
            with httpx.Client(
                timeout=30.0,
                transport=transport,
            ) as client:
                res = client.post(token_url, data=payload)
                res.raise_for_status()
                token_data = res.json()
                token = token_data.get("access_token")
                if not token or not isinstance(token, str):
                    raise SourceError("OAuth token endpoint returned invalid token payload")
                return token
        except httpx.HTTPStatusError as exc:
            raise SourceError(f"OAuth token request failed with HTTP {exc.response.status_code}") from exc
        except Exception as exc:
            raise SourceError(f"Failed to acquire Microsoft Graph OAuth token: {exc}") from exc
