"""OpenAI-compatible Chat Completions client (key from .env)."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx

from ..core.env_loader import LLMSettings, get_llm_settings

logger = logging.getLogger(__name__)


class LLMClient:
    def __init__(self, settings: Optional[LLMSettings] = None):
        self.settings = settings or get_llm_settings()

    @property
    def available(self) -> bool:
        return self.settings.available

    def chat_json(
        self,
        system: str,
        user: str,
        trace_path: Optional[Path] = None,
    ) -> Dict[str, Any]:
        """Call chat completions and parse JSON object from assistant content."""
        if not self.available:
            raise RuntimeError("LLM not configured (set LLM_API_KEY in .env)")

        url = f"{self.settings.api_base}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.settings.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.settings.model,
            "temperature": self.settings.temperature,
            "max_tokens": self.settings.max_tokens,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "response_format": {"type": "json_object"},
        }

        with httpx.Client(timeout=self.settings.timeout_seconds) as client:
            resp = client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()

        content = data["choices"][0]["message"]["content"]
        if trace_path is not None:
            trace_path.parent.mkdir(parents=True, exist_ok=True)
            # Redact key from any accidental echo
            safe = {
                "model": self.settings.model,
                "api_base": self.settings.api_base,
                "system": system,
                "user": user,
                "raw_response": data,
            }
            trace_path.write_text(json.dumps(safe, ensure_ascii=False, indent=2), encoding="utf-8")

        return self._parse_json_content(content)

    @staticmethod
    def _parse_json_content(content: str) -> Dict[str, Any]:
        text = content.strip()
        if text.startswith("```"):
            # strip markdown fence
            lines = text.splitlines()
            if lines and lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            text = "\n".join(lines)
        return json.loads(text)
