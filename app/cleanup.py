from __future__ import annotations

import shutil
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path


@contextmanager
def managed_work_directory(root: Path) -> Iterator[Path]:
    root.mkdir(parents=True, exist_ok=True)
    work_dir = Path(tempfile.mkdtemp(prefix="job-", dir=root))
    try:
        yield work_dir
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)
