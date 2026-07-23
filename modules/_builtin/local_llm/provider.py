"""Ollama-backed SemanticAnalysisCapability provider."""

from __future__ import annotations

import logging
import time
from typing import Any

from modules.capabilities.semantic_analysis import (
    KIND_RUNNING_SUMMARY,
    AnalysisRequest,
    AnalysisResult,
)

from .ollama_client import OllamaClient, OllamaError

log = logging.getLogger("praatmaar.local_llm.provider")

_LANG_LABEL = {"nl": "Nederlands", "en": "English", "de": "Deutsch"}
_READY_TTL_S = 30.0


class OllamaSemanticAnalysis:
    """Implements ``ai.semantic_analysis`` via a local Ollama model."""

    def __init__(self, client: OllamaClient, *, model: str) -> None:
        self._client = client
        self._model = model
        self._ready_cache: bool | None = None
        self._ready_checked_at = 0.0

    @property
    def model(self) -> str:
        return self._model

    def is_ready(self) -> bool:
        now = time.monotonic()
        if (
            self._ready_cache is not None
            and (now - self._ready_checked_at) < _READY_TTL_S
        ):
            return self._ready_cache
        try:
            ready = self._client.has_model(self._model)
        except OllamaError:
            ready = False
        self._ready_cache = ready
        self._ready_checked_at = now
        return ready

    def analyze(self, request: AnalysisRequest) -> AnalysisResult:
        if request.kind == KIND_RUNNING_SUMMARY:
            text = self._running_summary(request)
            return AnalysisResult(kind=KIND_RUNNING_SUMMARY, text=text)
        raise ValueError(f"Onbekend analyse-kind: {request.kind!r}")

    def analyze_delta(self, delta: Any, state_snapshot: Any) -> list[Any]:
        return []

    def _running_summary(self, request: AnalysisRequest) -> str:
        lang = _LANG_LABEL.get(request.language, request.language or "Nederlands")
        previous = (request.previous_summary or "").strip()
        transcript = request.transcript.strip()
        if not transcript:
            return previous

        system = (
            f"Je bent een beknopte notulist. Schrijf in het {lang}. "
            "Geef alleen de bijgewerkte lopende samenvatting als platte tekst, "
            "geen markdown-koppen, geen JSON, max ca. 8 zinnen."
        )
        user_parts = []
        if previous:
            user_parts.append(f"Vorige samenvatting:\n{previous}")
        user_parts.append(f"Transcript tot nu toe:\n{transcript}")
        user_parts.append(
            "Werk de lopende samenvatting bij op basis van het transcript."
        )
        content = self._client.chat(
            model=self._model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": "\n\n".join(user_parts)},
            ],
            temperature=0.2,
        )
        return content.strip()
