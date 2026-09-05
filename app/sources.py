from __future__ import annotations

from collections.abc import Iterator
from contextlib import AbstractContextManager, contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from app.media import validate_source_file


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
