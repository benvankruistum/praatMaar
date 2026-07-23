"""Minimal HTTP client for a local Ollama server."""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from typing import Any

log = logging.getLogger("praatmaar.local_llm.ollama")


class OllamaError(RuntimeError):
    """Ollama HTTP or protocol failure."""


class OllamaClient:
    """Talks to Ollama's HTTP API on localhost (or a configured base URL)."""

    def __init__(
        self, base_url: str = "http://127.0.0.1:11434", *, timeout_s: float = 120.0
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_s = timeout_s

    def tags(self) -> list[str]:
        payload = self._get_json("/api/tags")
        models = payload.get("models") or []
        names: list[str] = []
        for entry in models:
            if isinstance(entry, dict) and entry.get("name"):
                names.append(str(entry["name"]))
        return names

    def has_model(self, model: str) -> bool:
        target = model.strip()
        if not target:
            return False
        for name in self.tags():
            if name == target or name.startswith(f"{target}:"):
                return True
        return False

    def chat(
        self,
        *,
        model: str,
        messages: list[dict[str, str]],
        temperature: float = 0.2,
        format_json: bool = False,
    ) -> str:
        body: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": False,
            "options": {"temperature": temperature},
        }
        if format_json:
            body["format"] = "json"
        payload = self._post_json("/api/chat", body)
        message = payload.get("message") or {}
        content = message.get("content")
        if not isinstance(content, str):
            raise OllamaError("Ollama chat response missing message.content")
        return content

    def _get_json(self, path: str) -> dict[str, Any]:
        req = urllib.request.Request(f"{self.base_url}{path}", method="GET")
        return self._request_json(req)

    def _post_json(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        data = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(
            f"{self.base_url}{path}",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        return self._request_json(req)

    def _request_json(self, req: urllib.request.Request) -> dict[str, Any]:
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_s) as resp:
                raw = resp.read().decode("utf-8")
        except urllib.error.URLError as exc:
            raise OllamaError(f"Ollama niet bereikbaar ({self.base_url}): {exc}") from exc
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise OllamaError("Ollama gaf ongeldige JSON terug") from exc
        if not isinstance(payload, dict):
            raise OllamaError("Ollama JSON root moet een object zijn")
        return payload
