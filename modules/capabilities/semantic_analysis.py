"""
Contract voor capability ``ai.semantic_analysis``.

Provider: module ``local-llm`` (Ollama). Consumers o.a. Meeting Buddy.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

CAPABILITY_ID = "ai.semantic_analysis"
CONTRACT_VERSION = 2

KIND_RUNNING_SUMMARY = "running_summary"
KIND_AGENDA_REVIEW = "agenda_review"


@dataclass(frozen=True)
class AnalysisRequest:
    """Gestructureerd analyseverzoek van een consumer-module."""

    kind: str
    transcript: str
    previous_summary: str | None = None
    language: str = "nl"
    context: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AnalysisResult:
    """Resultaat van een gestructureerde analyse."""

    kind: str
    text: str
    data: dict[str, Any] | None = None


@runtime_checkable
class SemanticAnalysisCapability(Protocol):
    """Lokale semantische analyse (LLM via local-llm-module)."""

    def is_ready(self) -> bool:
        """True wanneer de runtime/model bereikbaar is voor analyse."""

    def analyze(self, request: AnalysisRequest) -> AnalysisResult:
        """Voer een analyse uit; raise bij fout of onbekend kind."""

    def analyze_delta(self, delta: Any, state_snapshot: Any) -> list[Any]:
        """Legacy MVP-hook; mag een lege lijst teruggeven."""
