"""Settings loaded from environment (see .env.example) plus sources.yaml."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

import yaml

from .synthesize.router import DEFAULT_LOCAL_MODEL


def _find_repo_root() -> Path:
    """The directory holding config/, data/ and reports/ -- the repo root,
    not the package. Found by walking up from this file so run_daily.py works
    from any cwd. A non-editable install (site-packages) has no such
    ancestor and falls back to cwd, which a container satisfies by setting
    WORKDIR to the repo root."""
    for parent in Path(__file__).resolve().parents:
        if (parent / "config" / "sources.yaml").is_file():
            return parent
    return Path.cwd()


REPO_ROOT = _find_repo_root()


def _repo_path(env_var: str, default: str) -> Path:
    """Relative paths, from env or default, resolve against REPO_ROOT rather
    than cwd. Absolute paths pass through unchanged -- joining onto an
    absolute path discards the left side."""
    return REPO_ROOT / os.environ.get(env_var, default)


class Settings:
    """Deliberately plain (no pydantic-settings dependency yet -- v4 stays
    minimal-deps until a stage actually needs more than os.environ)."""

    def __init__(self) -> None:
        self.data_dir = _repo_path("ARGUS_DATA_DIR", "data")
        self.reports_dir = _repo_path("ARGUS_REPORTS_DIR", "reports")
        self.sources_file = _repo_path("ARGUS_SOURCES_FILE", "config/sources.yaml")

        self.max_stories = int(os.environ.get("ARGUS_MAX_STORIES", "15"))
        self.cluster_window_hours = int(os.environ.get("ARGUS_CLUSTER_WINDOW_HOURS", "48"))

        self.anthropic_api_key: str | None = os.environ.get("ANTHROPIC_API_KEY")
        backend = os.environ.get("ARGUS_SYNTHESIS_BACKEND", "auto")
        self.synthesis_backend: Literal["auto", "anthropic", "local", "stub"] = backend  # type: ignore[assignment]
        self.local_llm_host = os.environ.get("ARGUS_LOCAL_LLM_HOST", "http://localhost:11434")
        # Single local model; local routing is not tiered (see synthesize/router.py).
        self.local_llm_model = os.environ.get("ARGUS_LOCAL_LLM_MODEL") or DEFAULT_LOCAL_MODEL
        self.local_llm_timeout_seconds = float(os.environ.get("ARGUS_LOCAL_LLM_TIMEOUT_SECONDS", "180"))


def load_sources(settings: Settings) -> list[dict]:
    """Load config/sources.yaml -> list of {name, url, category_hint}."""
    raw = yaml.safe_load(settings.sources_file.read_text())
    return raw.get("sources", [])
