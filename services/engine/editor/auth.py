"""Authentication, ownership, rate limits, quotas and job limits for the HTTP API.

EDITOR_AUTH=token (default when EDITOR_ENV != development): every request except /health carries
`Authorization: Bearer <token>` (or `?access_token=` on GET media/download/event URLs, which browsers cannot send
headers for). Tokens are random 256-bit values; only their SHA-256 is stored. Create users with:

    python -m editor.auth create-user "Alice" [--admin]

Accounts: POST /auth/register (email + password, when EDITOR_ALLOW_REGISTRATION=1) and POST /auth/login issue a
session token (expires after EDITOR_SESSION_DAYS). Passwords are hashed with scrypt (N=2^14, r=8, p=1, 16-byte salt);
session tokens, like API tokens, are stored only as SHA-256 hashes.

EDITOR_AUTH=none is for a single local user on localhost (development only) — the server refuses it in production.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import os
import re
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


# ---- passwords and sessions ----------------------------------------------------------------------------------------
_SCRYPT = (2**14, 8, 1)
EMAIL_RE = re.compile(r"^[^@\s]{1,64}@[^@\s]{1,190}\.[^@\s]{2,}$")
MIN_PASSWORD = 10


class AuthError(ValueError):
    pass


def hash_password(pw: str) -> str:
    n, r, p = _SCRYPT
    salt = secrets.token_bytes(16)
    dk = hashlib.scrypt(pw.encode(), salt=salt, n=n, r=r, p=p, dklen=32)
    return f"scrypt${n}${r}${p}${base64.b64encode(salt).decode()}${base64.b64encode(dk).decode()}"


def verify_password(pw: str, stored: str | None) -> bool:
    try:
        algo, n, r, p, salt, dk = (stored or "").split("$")
        if algo != "scrypt":
            return False
        got = hashlib.scrypt(pw.encode(), salt=base64.b64decode(salt), n=int(n), r=int(r), p=int(p), dklen=32)
        return hmac.compare_digest(got, base64.b64decode(dk))
    except (ValueError, TypeError):
        return False


_DUMMY_HASH = hash_password(secrets.token_urlsafe(16))  # equalises timing for unknown emails


def register(email: str, password: str, name: str | None = None) -> dict:
    email = (email or "").strip().lower()
    if not EMAIL_RE.match(email):
        raise AuthError("enter a valid email address")
    if len(password or "") < MIN_PASSWORD:
        raise AuthError(f"the password must be at least {MIN_PASSWORD} characters")
    if len(password) > 256:
        raise AuthError("the password is too long")
    if db.query("SELECT id FROM users WHERE email=?", (email,)):
        raise AuthError("an account with this email already exists")
    uid = db.new_id("usr")
    db.insert("users", id=uid, name=(name or email.split("@")[0]).strip()[:80] or "user", email=email,
              password_hash=hash_password(password), token_hash=_hash(secrets.token_urlsafe(32)), is_admin=0, created=time.time(), disabled=0)
    return db.get("users", uid)  # type: ignore[return-value]


def login(email: str, password: str) -> tuple[User, str, float] | None:
    rows = db.query("SELECT id, name, is_admin, disabled, password_hash FROM users WHERE email=?", ((email or "").strip().lower(),))
    if not rows:
        verify_password(password or "", _DUMMY_HASH)
        return None
    r = rows[0]
    if not verify_password(password or "", r["password_hash"]) or r["disabled"]:
        return None
    token = "cts_" + secrets.token_urlsafe(32)
    now = time.time()
    expires = now + get_settings().session_days * 86400
    db.insert("sessions", id=db.new_id("ses"), user_id=r["id"], token_hash=_hash(token), created=now, expires=expires, last_used=now)
    return User(r["id"], r["name"], bool(r["is_admin"])), token, expires


def logout(token: str | None) -> None:
    if token:
        db.execute("DELETE FROM sessions WHERE token_hash=?", (_hash(token.strip()),))


def authenticate(token: str | None) -> User | None:
    if not token:
        return None
    th = _hash(token.strip())
    if token.startswith("cts_"):
        rows = db.query("SELECT u.id, u.name, u.is_admin, u.disabled, s.id AS sid, s.expires, s.last_used FROM sessions s "
                        "JOIN users u ON u.id=s.user_id WHERE s.token_hash=?", (th,))
        if not rows or rows[0]["disabled"] or (rows[0]["expires"] or 0) < time.time():
            return None
        r = rows[0]
        if time.time() - (r["last_used"] or 0) > 300:
            db.update("sessions", r["sid"], last_used=time.time())
        return User(r["id"], r["name"], bool(r["is_admin"]))
    rows = db.query("SELECT id, name, is_admin, disabled FROM users WHERE token_hash=?", (th,))
    if not rows or rows[0]["disabled"]:
        return None
    r = rows[0]
    return User(r["id"], r["name"], bool(r["is_admin"]))


def config_problems() -> list[str]:
    """Unsafe settings the server refuses to start with outside development."""
    s = get_settings()
    out = []
    if s.env == "development":
        return out
    if s.auth != "token":
        out.append("EDITOR_AUTH=none is only allowed with EDITOR_ENV=development — set EDITOR_AUTH=token for any shared deployment")
    if not os.environ.get("EDITOR_CORS_ORIGINS", "").strip():
        out.append("EDITOR_CORS_ORIGINS must be set explicitly in production (the web app's origin)")
    if any(o == "*" for o in s.cors_origins):
        out.append("EDITOR_CORS_ORIGINS must list the web app's origin(s), not '*'")
    if any(o.startswith("http://") and not re.match(r"^http://(localhost|127\.0\.0\.1)(:\d+)?$", o) for o in s.cors_origins):
        out.append("EDITOR_CORS_ORIGINS must use https:// origins in production")
    if s.session_days <= 0 or s.session_days > 90:
        out.append("EDITOR_SESSION_DAYS must be between 0 and 90")
    if s.rate_limit_per_min <= 0 or s.login_rate_per_min <= 0:
        out.append("rate limits cannot be disabled in production (EDITOR_RATE_LIMIT_PER_MIN / EDITOR_LOGIN_RATE_PER_MIN)")
    return out


def check_config() -> None:
    s = get_settings()
    problems = config_problems()
    if problems:
        raise RuntimeError("refusing to start: " + "; ".join(problems))
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
        db.execute("DELETE FROM sessions WHERE user_id=?", (a.user_id,))
        print("disabled", a.user_id)
    else:
        for r in db.query("SELECT id, name, email, is_admin, disabled, created FROM users ORDER BY created"):
            print(r)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
