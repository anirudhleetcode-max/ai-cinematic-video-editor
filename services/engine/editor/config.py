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
