"""Authentication, ownership, rate limits, quotas and job limits for the HTTP API.

EDITOR_AUTH=token (default when EDITOR_ENV != development): every request except /health carries
`Authorization: Bearer <token>` (or `?access_token=` on GET media/download/event URLs, which browsers cannot send
headers for). Tokens are random 256-bit values; only their SHA-256 is stored. Create users with:

    python -m editor.auth create-user "Alice" [--admin]

EDITOR_AUTH=none is for a single local user on localhost (development only) — the server refuses it in production.
"""
from __future__ import annotations

import argparse
import hashlib
import secrets
import threading
import time
from collections import defaultdict
from dataclasses import dataclass

from . import db
from .config import get_settings


@dataclass
class User:
    id: str
    name: str
    is_admin: bool


LOCAL_USER = User("local", "local user", True)


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def create_user(name: str, admin: bool = False) -> tuple[dict, str]:
    token = "ctr_" + secrets.token_urlsafe(32)
    uid = db.new_id("usr")
    db.insert("users", id=uid, name=name.strip()[:80] or "user", token_hash=_hash(token), is_admin=int(admin), created=time.time(), disabled=0)
    return db.get("users", uid), token  # type: ignore[return-value]


def authenticate(token: str | None) -> User | None:
    if not token:
        return None
    rows = db.query("SELECT id, name, is_admin, disabled FROM users WHERE token_hash=?", (_hash(token.strip()),))
    if not rows or rows[0]["disabled"]:
        return None
    r = rows[0]
    return User(r["id"], r["name"], bool(r["is_admin"]))


def check_config() -> None:
    s = get_settings()
    if s.env != "development" and s.auth != "token":
        raise RuntimeError("EDITOR_AUTH=none is only allowed with EDITOR_ENV=development — set EDITOR_AUTH=token for any shared deployment")
    if "'" in s.data_dir.as_posix():
        raise RuntimeError("EDITOR_DATA_DIR must not contain an apostrophe (FFmpeg filter arguments cannot carry it safely)")


# ---- ownership -----------------------------------------------------------------------------------------------------
_OWNER_SQL = {
    "pid": "SELECT owner_id FROM projects WHERE id=?",
    "aid": "SELECT p.owner_id FROM assets a JOIN projects p ON p.id=a.project_id WHERE a.id=?",
    "vid": "SELECT p.owner_id FROM versions v JOIN projects p ON p.id=v.project_id WHERE v.id=?",
    "rid": "SELECT p.owner_id FROM renders r JOIN projects p ON p.id=r.project_id WHERE r.id=?",
    "jid": "SELECT COALESCE(j.owner_id, p.owner_id) AS owner_id FROM jobs j LEFT JOIN projects p ON p.id=j.project_id WHERE j.id=?",
}


def may_access(user: User, param: str, value: str) -> bool | None:
    """True/False for an ownership-checked path parameter; None if the object does not exist (→ 404 later)."""
    sql = _OWNER_SQL.get(param)
    if sql is None:
        return True
    rows = db.query(sql, (value,))
    if not rows:
        return None
    owner = rows[0]["owner_id"]
    return user.is_admin or (owner is not None and owner == user.id) or (owner is None and get_settings().auth == "none")


# ---- rate limits (in-process token buckets) ------------------------------------------------------------------------
class RateLimiter:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._b: dict[tuple[str, str], tuple[float, float]] = defaultdict(lambda: (0.0, 0.0))

    def allow(self, key: str, bucket: str, per_min: int) -> bool:
        if per_min <= 0:
            return True
        now = time.monotonic()
        with self._lock:
            tokens, last = self._b[(key, bucket)]
            if last == 0.0:
                tokens = float(per_min)
            tokens = min(float(per_min), tokens + (now - last) * per_min / 60.0) if last else tokens
            if tokens < 1.0:
                self._b[(key, bucket)] = (tokens, now)
                return False
            self._b[(key, bucket)] = (tokens - 1.0, now)
            return True


limiter = RateLimiter()


def active_jobs(user: User) -> int:
    rows = db.query("SELECT COUNT(*) AS n FROM jobs j LEFT JOIN projects p ON p.id=j.project_id "
                    "WHERE j.status IN ('queued','running') AND COALESCE(j.owner_id, p.owner_id)=?", (user.id,))
    return int(rows[0]["n"]) if rows else 0


def storage_used_bytes(user: User) -> int:
    rows = db.query("SELECT COALESCE(SUM(a.size),0) AS n FROM assets a JOIN projects p ON p.id=a.project_id WHERE p.owner_id=?", (user.id,))
    return int(rows[0]["n"]) if rows else 0


def main() -> int:
    ap = argparse.ArgumentParser(prog="python -m editor.auth")
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("create-user")
    c.add_argument("name")
    c.add_argument("--admin", action="store_true")
    d = sub.add_parser("disable-user")
    d.add_argument("user_id")
    sub.add_parser("list-users")
    a = ap.parse_args()
    db.connect()
    if a.cmd == "create-user":
        u, token = create_user(a.name, a.admin)
        print(f"user {u['id']} ({u['name']}{', admin' if a.admin else ''})\ntoken (shown once — store it now): {token}")
    elif a.cmd == "disable-user":
        db.update("users", a.user_id, disabled=1)
        print("disabled", a.user_id)
    else:
        for r in db.query("SELECT id, name, is_admin, disabled, created FROM users ORDER BY created"):
            print(r)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
