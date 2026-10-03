"""Safe subprocess execution for FFmpeg/FFprobe.

All media commands go through `run()` which:
  * only accepts argument lists (never a shell string) -> no shell injection
  * only allows the configured ffmpeg/ffprobe binaries
  * rejects arguments that start with ``-`` where a *path* is expected (handled by callers via `safe_path`)
"""
from __future__ import annotations

import logging
import re
import subprocess
from pathlib import Path
from typing import Callable, Sequence

from .config import get_settings
from .logging import get_logger, log

logger = get_logger("proc")


class MediaCommandError(RuntimeError):
    def __init__(self, cmd: Sequence[str], code: int, stderr: str):
        tail = stderr.strip().splitlines()[-12:]
        super().__init__(f"{Path(cmd[0]).name} exited {code}: " + " | ".join(tail))
        self.cmd, self.code, self.stderr = list(cmd), code, stderr


def _check_binary(cmd: Sequence[str]) -> None:
    s = get_settings()
    if not cmd or cmd[0] not in (s.ffmpeg, s.ffprobe):
        raise ValueError(f"refusing to execute non-media binary: {cmd[:1]}")
    for a in cmd:
        if not isinstance(a, str):
            raise TypeError(f"argument must be str, got {type(a)}")
        if "\x00" in a:
            raise ValueError("NUL byte in argument")


def run(cmd: Sequence[str], timeout: float | None = None, check: bool = True, input_bytes: bytes | None = None) -> subprocess.CompletedProcess:
    _check_binary(cmd)
    log(logger, "exec", logging.DEBUG, argv0=Path(cmd[0]).name, n_args=len(cmd))
    # every media process has a timeout (EDITOR_PROCESS_TIMEOUT when the caller gives none) — no unbounded FFmpeg runs
    p = subprocess.run(list(cmd), capture_output=True, timeout=timeout or get_settings().process_timeout_s, input=input_bytes)
    if check and p.returncode != 0:
        raise MediaCommandError(cmd, p.returncode, p.stderr.decode("utf-8", "replace"))
    return p


def ff_path(p: Path | str) -> str:
    """A filesystem path as a quoted FFmpeg *filter option value* (lut3d=file=…, ass=…, fontsdir=…, vidstab input=…).
    FFmpeg unquotes filtergraph arguments once before splitting options on ':', so the colon of a Windows drive letter
    must be escaped inside the quotes ('C\\:/x', as documented in ffmpeg-filters "Notes on filtergraph escaping").
    Paths containing an apostrophe cannot be quoted safely and are rejected."""
    s = Path(p).as_posix()
    if "'" in s:
        raise ValueError(f"path contains an apostrophe, which FFmpeg filter arguments cannot carry safely: {s!r} — move the data directory")
    return "'" + s.replace(":", "\\:") + "'"


_TIME_RE = re.compile(r"out_time_us=(\d+)")


def run_ffmpeg_progress(cmd: Sequence[str], total_seconds: float, on_progress: Callable[[float], None] | None = None) -> None:
    """Run ffmpeg with `-progress pipe:1` and report real progress (0..1) from its own out_time counter."""
    _check_binary(cmd)
    full = [cmd[0], "-progress", "pipe:1", "-nostats", *cmd[1:]]
    log(logger, "exec-progress", n_args=len(full), total_s=round(total_seconds, 2))
    p = subprocess.Popen(full, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    assert p.stdout is not None
    stderr_chunks: list[str] = []
    import threading

    def _drain():
        assert p.stderr is not None
        for line in p.stderr:
            stderr_chunks.append(line)

    t = threading.Thread(target=_drain, daemon=True)
    t.start()
    limit = get_settings().process_timeout_s
    watchdog = threading.Timer(limit, p.kill)  # hard wall-clock limit for the encode
    watchdog.daemon = True
    watchdog.start()
    for line in p.stdout:
        m = _TIME_RE.match(line.strip())
        if m and on_progress and total_seconds > 0:
            on_progress(min(1.0, int(m.group(1)) / 1e6 / total_seconds))
    p.wait()
    watchdog.cancel()
    t.join(timeout=5)
    if p.returncode != 0:
        raise MediaCommandError(full, p.returncode, "".join(stderr_chunks[-200:]) or f"killed after {limit}s timeout")


def replace_file(src: Path, dst: Path, attempts: int = 8) -> None:
    """os.replace with retries: on Windows a file that another process (a player, the download handler, an antivirus
    scan) still has open cannot be replaced immediately."""
    import time as _t

    for k in range(attempts):
        try:
            Path(src).replace(dst)
            return
        except PermissionError:
            if k == attempts - 1:
                raise
            _t.sleep(0.25 * (k + 1))


_SAFE_NAME = re.compile(r"[^A-Za-z0-9._-]+")


def safe_filename(name: str, max_len: int = 120) -> str:
    base = Path(name).name  # strip any directory components
    base = _SAFE_NAME.sub("_", base).strip("._") or "file"
    return base[-max_len:]


def safe_path(p: Path, root: Path) -> Path:
    """Resolve `p` and make sure it stays inside `root` (prevents path traversal)."""
    rp = Path(p).resolve()
    root = Path(root).resolve()
    if rp != root and root not in rp.parents:
        raise ValueError(f"path escapes storage root: {p}")
    return rp
