"""Chunked live running-summary via ``ai.semantic_analysis``."""

from __future__ import annotations

import logging
import re
import time
from collections.abc import Callable
from dataclasses import dataclass
from threading import Lock, Thread

from modules.capabilities.registry import CapabilityRegistry
from modules.capabilities.semantic_analysis import (
    CAPABILITY_ID,
    CONTRACT_VERSION,
    KIND_RUNNING_SUMMARY,
    AnalysisRequest,
)

log = logging.getLogger(__name__)

# Cap per delta-chunk (prompt-explosie bij lange stilte + burst).
_MAX_DELTA_CHARS = 12_000
_DEFAULT_BULLET_LIMIT = 5


def summary_points(text: str, *, limit: int = _DEFAULT_BULLET_LIMIT) -> list[str]:
    """Split a running summary into up to ``limit`` points.

    Prefers explicit lines (stripping bullet markers); falls back to sentence
    splitting for a single paragraph.
    """
    cleaned = (text or "").strip()
    if not cleaned:
        return []
    lines = [
        re.sub(r"^\s*(?:[-*•]|\d+[.)])\s*", "", line).strip()
        for line in cleaned.splitlines()
        if line.strip()
    ]
    if len(lines) > 1:
        return lines[:limit]
    base = lines[0] if lines else cleaned
    base = re.sub(r"^\s*(?:[-*•]|\d+[.)])\s*", "", base).strip() or base
    sentences = [part.strip() for part in re.split(r"(?<=[.!?])\s+", base) if part.strip()]
    if len(sentences) > 1:
        return sentences[:limit]
    return [base] if base else []


def normalize_running_summary(text: str, *, limit: int = _DEFAULT_BULLET_LIMIT) -> str:
    """Return a canonical ``- `` bullet block (max ``limit``), or empty."""
    points = summary_points(text, limit=limit)
    if not points:
        return ""
    return "\n".join(f"- {point}" for point in points)


@dataclass
class LiveSummarySettings:
    enabled: bool = False
    interval_s: float = 45.0
    min_new_chars: int = 120
    language: str = "nl"


class LiveSummaryCoordinator:
    """Schedules running-summary LLM calls when time AND text thresholds are met."""

    def __init__(
        self,
        *,
        capabilities: CapabilityRegistry,
        settings: LiveSummarySettings,
        on_summary: Callable[[str], None] | None = None,
    ) -> None:
        self._capabilities = capabilities
        self._settings = settings
        self._on_summary = on_summary
        self._lock = Lock()
        self._summary = ""
        self._delta = ""
        self._chars_since = 0
        self._last_run_at = time.monotonic()
        self._busy = False

    @property
    def summary(self) -> str:
        with self._lock:
            return self._summary

    def update_settings(self, settings: LiveSummarySettings) -> None:
        with self._lock:
            self._settings = settings

    def reset(self) -> None:
        with self._lock:
            self._summary = ""
            self._delta = ""
            self._chars_since = 0
            # Startinterval: eerste LLM-run wacht ook op interval_s.
            self._last_run_at = time.monotonic()
            self._busy = False

    def on_final_text(self, text: str, *, now: float | None = None) -> None:
        chunk = text.strip()
        if not chunk:
            return
        with self._lock:
            if not self._settings.enabled:
                return
            self._delta = f"{self._delta} {chunk}".strip()
            if len(self._delta) > _MAX_DELTA_CHARS:
                self._delta = self._delta[-_MAX_DELTA_CHARS:]
            self._chars_since += len(chunk)
            should = self._should_run_unlocked(now=now if now is not None else time.monotonic())
            if not should:
                return
            self._busy = True
            snapshot_delta = self._delta
            snapshot_previous = self._summary
            language = self._settings.language
            log.info(
                "Live summary starten (%s tekens delta, interval ok)",
                len(snapshot_delta),
            )
        Thread(
            target=self._run_analyze,
            args=(snapshot_delta, snapshot_previous, language),
            name="meeting-buddy-live-summary",
            daemon=True,
        ).start()

    def _should_run_unlocked(self, *, now: float) -> bool:
        if self._busy:
            return False
        if self._chars_since < self._settings.min_new_chars:
            return False
        if (now - self._last_run_at) < self._settings.interval_s:
            return False
        provider = self._capabilities.get(
            CAPABILITY_ID,
            minimum_contract_version=CONTRACT_VERSION,
        )
        return provider is not None

    def _run_analyze(self, delta: str, previous: str, language: str) -> None:
        provider = self._capabilities.get(
            CAPABILITY_ID,
            minimum_contract_version=CONTRACT_VERSION,
        )
        try:
            if provider is None:
                log.warning("Live summary: geen ai.semantic_analysis capability")
                return
            if hasattr(provider, "is_ready") and not provider.is_ready():
                log.warning("Live summary: Local LLM niet klaar (Ollama/model)")
                with self._lock:
                    self._last_run_at = time.monotonic()
                return
            result = provider.analyze(
                AnalysisRequest(
                    kind=KIND_RUNNING_SUMMARY,
                    transcript=delta,
                    previous_summary=previous or None,
                    language=language,
                )
            )
            text = normalize_running_summary((result.text or "").strip())
            if not text:
                log.warning("Live summary: leeg of onbruikbaar antwoord van model")
                return
            with self._lock:
                self._summary = text
                # Succes: verstuurde delta weg; tekst tijdens de run blijft.
                if self._delta.startswith(delta):
                    self._delta = self._delta[len(delta) :].strip()
                else:
                    self._delta = ""
                self._chars_since = len(self._delta)
                self._last_run_at = time.monotonic()
            log.info("Live summary bijgewerkt (%s tekens)", len(text))
            if self._on_summary is not None:
                self._on_summary(text)
        except Exception:
            log.exception("Live summary analyse mislukt")
            with self._lock:
                self._last_run_at = time.monotonic()
        finally:
            with self._lock:
                self._busy = False
