"""Minimal LLM client. Uses the Anthropic Messages API when ANTHROPIC_API_KEY is set,
otherwise returns None so callers fall back to deterministic templates (the project runs
end-to-end offline, in CI, with no key)."""
from __future__ import annotations

import os
from dataclasses import dataclass

import requests

API_URL = "https://api.anthropic.com/v1/messages"


@dataclass
class LLMClient:
    provider: str = "auto"
    model: str | None = None
    api_key: str | None = None
    timeout: int = 60
    calls: int = 0
    failures: int = 0

    def __post_init__(self):
        self.api_key = self.api_key or os.environ.get("ANTHROPIC_API_KEY") or None
        self.model = self.model or os.environ.get("ANTHROPIC_MODEL") or "claude-sonnet-5-5"
        if self.provider == "auto":
            self.provider = "anthropic" if self.api_key else "offline"

    @property
    def online(self) -> bool:
        return self.provider == "anthropic" and bool(self.api_key)

    def complete(self, system: str, prompt: str, max_tokens: int = 900, temperature: float = 0.2) -> str | None:
        if not self.online:
            return None
        self.calls += 1
        try:
            r = requests.post(API_URL, timeout=self.timeout, headers={
                "x-api-key": self.api_key, "anthropic-version": "2023-06-01",
                "content-type": "application/json"}, json={
                "model": self.model, "max_tokens": max_tokens, "temperature": temperature,
                "system": system, "messages": [{"role": "user", "content": prompt}]})
            r.raise_for_status()
            blocks = r.json().get("content", [])
            text = "".join(b.get("text", "") for b in blocks if b.get("type") == "text").strip()
            return text or None
        except (requests.RequestException, ValueError, KeyError):
            self.failures += 1
            return None
