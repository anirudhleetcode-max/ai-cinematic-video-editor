"""SQLite persistence (repository layer). Tables keep JSON payloads so the schema maps directly to
PostgreSQL (JSONB) later — only `connect()` and the DDL dialect would change."""
from __future__ import annotations

import json
import sqlite3
import threading
import time
import uuid
from contextlib import contextmanager
from typing import Any, Iterator

from .config import get_settings

DDL = """
CREATE TABLE IF NOT EXISTS projects (
  id TEXT PRIMARY KEY, name TEXT NOT NULL, created REAL, updated REAL, settings TEXT DEFAULT '{}'
);
CREATE TABLE IF NOT EXISTS assets (
  id TEXT PRIMARY KEY, project_id TEXT NOT NULL, kind TEXT NOT NULL, role TEXT NOT NULL,
  filename TEXT NOT NULL, path TEXT NOT NULL, fingerprint TEXT, size INTEGER,
  meta TEXT DEFAULT '{}', thumb TEXT, created REAL, ordinal INTEGER DEFAULT 0,
  analysis TEXT, proxy TEXT, status TEXT DEFAULT 'uploaded'
);
CREATE INDEX IF NOT EXISTS ix_assets_project ON assets(project_id);
CREATE TABLE IF NOT EXISTS analysis_cache (
  fingerprint TEXT NOT NULL, analyzer TEXT NOT NULL, version TEXT NOT NULL, result TEXT NOT NULL, created REAL,
  PRIMARY KEY (fingerprint, analyzer, version)
);
CREATE TABLE IF NOT EXISTS jobs (
  id TEXT PRIMARY KEY, project_id TEXT, kind TEXT NOT NULL, status TEXT NOT NULL, stage TEXT,
  progress REAL, params TEXT DEFAULT '{}', result TEXT, error TEXT, log TEXT DEFAULT '[]',
  created REAL, started REAL, finished REAL
);
CREATE INDEX IF NOT EXISTS ix_jobs_project ON jobs(project_id);
CREATE TABLE IF NOT EXISTS versions (
  id TEXT PRIMARY KEY, project_id TEXT NOT NULL, number INTEGER NOT NULL, parent_id TEXT,
  prompt TEXT, kind TEXT, plan TEXT NOT NULL, bible TEXT, changes TEXT DEFAULT '[]', created REAL
);
CREATE INDEX IF NOT EXISTS ix_versions_project ON versions(project_id);
CREATE TABLE IF NOT EXISTS renders (
  id TEXT PRIMARY KEY, project_id TEXT NOT NULL, version_id TEXT, kind TEXT NOT NULL, path TEXT,
  report TEXT, created REAL
);
CREATE TABLE IF NOT EXISTS brand_kits (
  id TEXT PRIMARY KEY, name TEXT NOT NULL, data TEXT NOT NULL, created REAL
);
CREATE TABLE IF NOT EXISTS users (
  id TEXT PRIMARY KEY, name TEXT NOT NULL, token_hash TEXT UNIQUE NOT NULL, is_admin INTEGER DEFAULT 0, created REAL, disabled INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS sessions (
  id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE, token_hash TEXT UNIQUE NOT NULL,
  created REAL, expires REAL, last_used REAL
);
CREATE INDEX IF NOT EXISTS ix_sessions_user ON sessions(user_id);
CREATE INDEX IF NOT EXISTS ix_renders_project ON renders(project_id);
CREATE INDEX IF NOT EXISTS ix_renders_version ON renders(version_id);
CREATE INDEX IF NOT EXISTS ix_jobs_status ON jobs(status);
CREATE TABLE IF NOT EXISTS benchmarks (
  id TEXT PRIMARY KEY, label TEXT, n_clips INTEGER, metrics TEXT NOT NULL, created REAL
);
"""

_JSON_COLS = {"analysis", "settings", "meta", "result", "params", "log", "plan", "bible", "changes", "report", "data", "metrics"}
_lock = threading.RLock()
_conn: sqlite3.Connection | None = None


def connect() -> sqlite3.Connection:
    global _conn
    with _lock:
        if _conn is None:
            path = get_settings().db_path
            path.parent.mkdir(parents=True, exist_ok=True)
            _conn = sqlite3.connect(str(path), check_same_thread=False, isolation_level=None)
            _conn.row_factory = sqlite3.Row
            _conn.execute("PRAGMA journal_mode=WAL")
            _conn.execute("PRAGMA foreign_keys=ON")
            _conn.executescript(DDL)
            _migrate(_conn)
        return _conn


MIGRATIONS = [("projects", "owner_id", "TEXT"), ("brand_kits", "owner_id", "TEXT"), ("jobs", "owner_id", "TEXT"),
              ("users", "email", "TEXT"), ("users", "password_hash", "TEXT")]
# indexes on migrated columns (created after the columns exist)
POST_MIGRATION_DDL = """
CREATE INDEX IF NOT EXISTS ix_projects_owner ON projects(owner_id);
CREATE INDEX IF NOT EXISTS ix_jobs_owner ON jobs(owner_id);
CREATE INDEX IF NOT EXISTS ix_brand_kits_owner ON brand_kits(owner_id);
CREATE UNIQUE INDEX IF NOT EXISTS ux_users_email ON users(email) WHERE email IS NOT NULL;
"""


def _migrate(conn: sqlite3.Connection) -> None:
    """Additive, idempotent column migrations for databases created by earlier versions."""
    for table, col, typ in MIGRATIONS:
        cols = {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}
        if col not in cols:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {typ}")
    conn.executescript(POST_MIGRATION_DDL)


def reset_db() -> None:
    global _conn
    with _lock:
        if _conn is not None:
            _conn.close()
        _conn = None


@contextmanager
def tx() -> Iterator[sqlite3.Connection]:
    c = connect()
    with _lock:
        c.execute("BEGIN")
        try:
            yield c
            c.execute("COMMIT")
        except Exception:
            c.execute("ROLLBACK")
            raise


def _decode(row: sqlite3.Row | None) -> dict | None:
    if row is None:
        return None
    d = dict(row)
    for k in _JSON_COLS & d.keys():
        if isinstance(d[k], str):
            try:
                d[k] = json.loads(d[k])
            except json.JSONDecodeError:
                pass
    return d


def _encode(v: Any) -> Any:
    return json.dumps(v, default=str) if isinstance(v, (dict, list)) else v


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def insert(table: str, **values) -> dict:
    cols = ", ".join(values)
    qs = ", ".join("?" for _ in values)
    with tx() as c:
        c.execute(f"INSERT INTO {table} ({cols}) VALUES ({qs})", [_encode(v) for v in values.values()])
    return values


def update(table: str, id_: str, **values) -> None:
    sets = ", ".join(f"{k}=?" for k in values)
    with tx() as c:
        c.execute(f"UPDATE {table} SET {sets} WHERE id=?", [*[_encode(v) for v in values.values()], id_])


def get(table: str, id_: str) -> dict | None:
    with _lock:
        return _decode(connect().execute(f"SELECT * FROM {table} WHERE id=?", (id_,)).fetchone())


def query(sql: str, params: tuple = ()) -> list[dict]:
    with _lock:
        return [_decode(r) for r in connect().execute(sql, params).fetchall()]  # type: ignore[misc]


def execute(sql: str, params: tuple = ()) -> None:
    with tx() as c:
        c.execute(sql, params)


# ---- analysis cache -------------------------------------------------------------------------
_cache_stats = {"hits": 0, "misses": 0}


def cache_get(fp: str, analyzer: str, version: str) -> dict | None:
    rows = query("SELECT result FROM analysis_cache WHERE fingerprint=? AND analyzer=? AND version=?", (fp, analyzer, version))
    if rows:
        _cache_stats["hits"] += 1
        return rows[0]["result"]
    _cache_stats["misses"] += 1
    return None


def cache_put(fp: str, analyzer: str, version: str, result: dict) -> None:
    with tx() as c:
        c.execute(
            "INSERT OR REPLACE INTO analysis_cache (fingerprint, analyzer, version, result, created) VALUES (?,?,?,?,?)",
            (fp, analyzer, version, json.dumps(result, default=float), time.time()),
        )


def cache_stats() -> dict:
    n = query("SELECT COUNT(*) AS n FROM analysis_cache")[0]["n"]
    return {**_cache_stats, "entries": n}
