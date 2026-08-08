"""Load `.env` and expose LLM settings. Secrets never come from YAML."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv


def load_project_env(project_root: Optional[Path] = None) -> Path:
    """Load nearest `.env` (project root preferred). Returns path used or cwd."""
    if project_root is None:
        # src/trading_system/core/env_loader.py → parents[3] = project root
        project_root = Path(__file__).resolve().parents[3]
    env_path = project_root / ".env"
    if env_path.exists():
        load_dotenv(env_path, override=False)
        return env_path
    # Also allow cwd .env when running from elsewhere
    load_dotenv(override=False)
    return Path.cwd() / ".env"


@dataclass(frozen=True)
class LLMSettings:
    api_key: str
    api_base: str
    model: str
    timeout_seconds: float
    max_tokens: int
    temperature: float
    disabled: bool

    @property
    def available(self) -> bool:
        return (not self.disabled) and bool(self.api_key.strip()) and bool(self.model.strip())


def get_llm_settings() -> LLMSettings:
    load_project_env()
    return LLMSettings(
        api_key=os.getenv("LLM_API_KEY", "").strip(),
        api_base=os.getenv("LLM_API_BASE", "https://api.openai.com/v1").rstrip("/"),
        model=os.getenv("LLM_MODEL", "gpt-4o-mini").strip(),
        timeout_seconds=float(os.getenv("LLM_TIMEOUT_SECONDS", "90")),
        max_tokens=int(os.getenv("LLM_MAX_TOKENS", "2048")),
        temperature=float(os.getenv("LLM_TEMPERATURE", "0.3")),
        disabled=os.getenv("LLM_DISABLED", "0").strip() in {"1", "true", "True", "yes"},
    )
