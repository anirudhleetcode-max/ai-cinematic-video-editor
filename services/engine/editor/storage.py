"""Storage abstraction. LocalStorage is used for development; an S3-compatible backend can implement
the same interface (put/open/path_for/delete/url) without touching the rest of the engine."""
from __future__ import annotations

import hashlib
import shutil
from abc import ABC, abstractmethod
from pathlib import Path
from typing import BinaryIO

from .config import get_settings
from .proc import replace_file, safe_filename, safe_path


class Storage(ABC):
    @abstractmethod
    def project_dir(self, project_id: str) -> Path: ...

    @abstractmethod
    def save_upload(self, project_id: str, kind: str, filename: str, stream: BinaryIO, max_bytes: int) -> Path: ...

    @abstractmethod
    def work_path(self, project_id: str, *parts: str) -> Path: ...

    @abstractmethod
    def delete_project(self, project_id: str) -> None: ...


class UploadTooLarge(ValueError):
    pass


class LocalStorage(Storage):
    def __init__(self, root: Path | None = None):
        self.root = (root or get_settings().projects_dir).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def project_dir(self, project_id: str) -> Path:
        d = safe_path(self.root / safe_filename(project_id), self.root)
        d.mkdir(parents=True, exist_ok=True)
        return d

    def work_path(self, project_id: str, *parts: str) -> Path:
        base = self.project_dir(project_id)
        p = safe_path(base.joinpath(*[safe_filename(x) for x in parts]), base)
        p.parent.mkdir(parents=True, exist_ok=True)
        return p

    def save_upload(self, project_id: str, kind: str, filename: str, stream: BinaryIO, max_bytes: int) -> Path:
        name = safe_filename(filename)
        dest = self.work_path(project_id, "media", kind, name)
        stem, suf, i = dest.stem, dest.suffix, 1
        while dest.exists():
            dest = dest.with_name(f"{stem}_{i}{suf}")
            i += 1
        written = 0
        tmp = dest.with_suffix(dest.suffix + ".part")
        with open(tmp, "wb") as f:
            while chunk := stream.read(1 << 20):
                written += len(chunk)
                if written > max_bytes:
                    f.close()
                    tmp.unlink(missing_ok=True)
                    raise UploadTooLarge(f"{filename} exceeds {max_bytes // (1 << 20)} MB")
                f.write(chunk)
        replace_file(tmp, dest)
        return dest

    def delete_project(self, project_id: str) -> None:
        shutil.rmtree(self.project_dir(project_id), ignore_errors=True)


def fingerprint(path: Path) -> str:
    """Fast content fingerprint used as the analysis cache key (size + first/last 4 MB)."""
    h = hashlib.sha256()
    size = path.stat().st_size
    h.update(str(size).encode())
    with open(path, "rb") as f:
        h.update(f.read(4 << 20))
        if size > 8 << 20:
            f.seek(-(4 << 20), 2)
            h.update(f.read())
    return h.hexdigest()[:32]


_storage: Storage | None = None


def get_storage() -> Storage:
    global _storage
    if _storage is None:
        _storage = LocalStorage()
    return _storage


def reset_storage() -> None:
    global _storage
    _storage = None
