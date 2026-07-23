"""Chunked live running-summary via ``ai.semantic_analysis``."""

from __future__ import annotations

import logging
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


@dataclass
class LiveSummarySettings:
    enabled: bool = True
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
        self._buffer = ""
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
            self._buffer = ""
            self._chars_since = 0
            # Startinterval: eerste LLM-run wacht ook op interval_s (niet meteen bij 200 tekens).
            self._last_run_at = time.monotonic()
            self._busy = False

    def on_final_text(self, text: str, *, now: float | None = None) -> None:
        chunk = text.strip()
        if not chunk:
            return
        with self._lock:
            if not self._settings.enabled:
                return
            self._buffer = f"{self._buffer} {chunk}".strip()
            self._chars_since += len(chunk)
            should = self._should_run_unlocked(now=now if now is not None else time.monotonic())
            if not should:
                return
            self._busy = True
            snapshot_transcript = self._buffer
            snapshot_previous = self._summary
            language = self._settings.language
            log.info(
                "Live summary starten (%s tekens, interval ok)",
                len(snapshot_transcript),
            )
        Thread(
            target=self._run_analyze,
            args=(snapshot_transcript, snapshot_previous, language),
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
        # Alleen registry-lookup hier; geen HTTP. Ready-check gebeurt in de worker.
        provider = self._capabilities.get(
            CAPABILITY_ID,
            minimum_contract_version=CONTRACT_VERSION,
        )
        return provider is not None

    def _run_analyze(self, transcript: str, previous: str, language: str) -> None:
        provider = self._capabilities.get(
            CAPABILITY_ID,
            minimum_contract_version=CONTRACT_VERSION,
        )
        try:
            if provider is None:
                log.warning("Live summary: geen ai.semantic_analysis capability")
                return
            if hasattr(provider, "is_ready") and not provider.is_ready():
                # Back-off: voorkom een worker per final-chunk als Ollama nog niet klaar is.
                log.warning("Live summary: Local LLM niet klaar (Ollama/model)")
                with self._lock:
                    self._last_run_at = time.monotonic()
                return
            result = provider.analyze(
                AnalysisRequest(
                    kind=KIND_RUNNING_SUMMARY,
                    transcript=transcript,
                    previous_summary=previous or None,
                    language=language,
                )
            )
            text = (result.text or "").strip()
            if not text:
                log.warning("Live summary: leeg antwoord van model")
                return
            with self._lock:
                self._summary = text
                self._chars_since = 0
                self._last_run_at = time.monotonic()
            log.info("Live summary bijgewerkt (%s tekens)", len(text))
            if self._on_summary is not None:
                self._on_summary(text)
        except Exception:
            log.exception("Live summary analyse mislukt")
        finally:
            with self._lock:
                self._busy = False
