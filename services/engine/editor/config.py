"""Runtime configuration. Everything is driven by environment variables (see .env.example)."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]


def _env_path(name: str, default: Path) -> Path:
    return Path(os.environ.get(name, str(default))).expanduser().resolve()


@dataclass(frozen=True)
class Settings:
    data_dir: Path = field(default_factory=lambda: _env_path("EDITOR_DATA_DIR", REPO_ROOT / "data"))
    fonts_dir: Path = field(default_factory=lambda: _env_path("EDITOR_FONTS_DIR", REPO_ROOT / "packages" / "fonts"))
    templates_dir: Path = field(default_factory=lambda: _env_path("EDITOR_TEMPLATES_DIR", REPO_ROOT / "packages" / "templates"))
    ffmpeg: str = field(default_factory=lambda: os.environ.get("FFMPEG_BIN", "ffmpeg"))
    ffprobe: str = field(default_factory=lambda: os.environ.get("FFPROBE_BIN", "ffprobe"))
    max_upload_mb: int = field(default_factory=lambda: int(os.environ.get("EDITOR_MAX_UPLOAD_MB", "4096")))
    workers: int = field(default_factory=lambda: int(os.environ.get("EDITOR_WORKERS", "1")))
    # process role: "all" (API + workers in one process, local default), "api" (HTTP only), "worker" (jobs only)
    role: str = field(default_factory=lambda: os.environ.get("EDITOR_ROLE", "all"))
    job_max_attempts: int = field(default_factory=lambda: int(os.environ.get("EDITOR_JOB_MAX_ATTEMPTS", "2")))
    analysis_threads: int = field(default_factory=lambda: int(os.environ.get("EDITOR_ANALYSIS_THREADS", str(max(1, (os.cpu_count() or 2) - 1)))))
    qc_max_retries: int = field(default_factory=lambda: int(os.environ.get("EDITOR_QC_MAX_RETRIES", "2")))
    ai_provider: str = field(default_factory=lambda: os.environ.get("EDITOR_AI_PROVIDER", "auto"))
    anthropic_api_key: str | None = field(default_factory=lambda: os.environ.get("ANTHROPIC_API_KEY") or None)
    anthropic_model: str = field(default_factory=lambda: os.environ.get("ANTHROPIC_MODEL", "claude-opus-5-5"))
    openai_base_url: str | None = field(default_factory=lambda: os.environ.get("OPENAI_BASE_URL") or None)
    openai_api_key: str | None = field(default_factory=lambda: os.environ.get("OPENAI_API_KEY") or None)
    openai_model: str = field(default_factory=lambda: os.environ.get("OPENAI_MODEL", "gpt-4o-mini"))
    stt_model_dir: Path | None = field(
        default_factory=lambda: Path(os.environ["EDITOR_STT_MODEL_DIR"]) if os.environ.get("EDITOR_STT_MODEL_DIR") else None
    )
    env: str = field(default_factory=lambda: os.environ.get("EDITOR_ENV", "development"))
    # auth: "token" (API tokens, required in production) or "none" (single local user; development only)
    auth: str = field(default_factory=lambda: os.environ.get("EDITOR_AUTH", "none" if os.environ.get("EDITOR_ENV", "development") == "development" else "token"))
    rate_limit_per_min: int = field(default_factory=lambda: int(os.environ.get("EDITOR_RATE_LIMIT_PER_MIN", "240")))
    upload_rate_per_min: int = field(default_factory=lambda: int(os.environ.get("EDITOR_UPLOAD_RATE_PER_MIN", "120")))
    job_rate_per_min: int = field(default_factory=lambda: int(os.environ.get("EDITOR_JOB_RATE_PER_MIN", "20")))
    max_jobs_per_user: int = field(default_factory=lambda: int(os.environ.get("EDITOR_MAX_JOBS_PER_USER", "3")))
    max_projects_per_user: int = field(default_factory=lambda: int(os.environ.get("EDITOR_MAX_PROJECTS_PER_USER", "50")))
    user_quota_gb: float = field(default_factory=lambda: float(os.environ.get("EDITOR_USER_QUOTA_GB", "50")))
    process_timeout_s: int = field(default_factory=lambda: int(os.environ.get("EDITOR_PROCESS_TIMEOUT", "7200")))
    retention_days: int = field(default_factory=lambda: int(os.environ.get("EDITOR_RETENTION_DAYS", "30")))
    session_days: float = field(default_factory=lambda: float(os.environ.get("EDITOR_SESSION_DAYS", "14")))
    allow_registration: bool = field(default_factory=lambda: os.environ.get("EDITOR_ALLOW_REGISTRATION", "1") == "1")
    login_rate_per_min: int = field(default_factory=lambda: int(os.environ.get("EDITOR_LOGIN_RATE_PER_MIN", "10")))
    cors_origins: tuple[str, ...] = field(
        default_factory=lambda: tuple(o.strip() for o in os.environ.get("EDITOR_CORS_ORIGINS", "http://localhost:3000").split(",") if o.strip())
    )

    @property
    def db_path(self) -> Path:
        return self.data_dir / "editor.sqlite3"

    @property
    def projects_dir(self) -> Path:
        return self.data_dir / "projects"

    @property
    def cache_dir(self) -> Path:
        return self.data_dir / "cache"

    @property
    def brand_dir(self) -> Path:
        return self.data_dir / "brand"


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
        for d in (_settings.data_dir, _settings.projects_dir, _settings.cache_dir, _settings.brand_dir):
            d.mkdir(parents=True, exist_ok=True)
    return _settings


def reset_settings() -> None:
    """Used by tests after changing environment variables."""
    global _settings
    _settings = None
