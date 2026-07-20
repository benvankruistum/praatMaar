"""
Contract voor capability ``ai.semantic_analysis``.

MVP: geen provider. Contract voor latere lokale AI.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

CAPABILITY_ID = "ai.semantic_analysis"
CONTRACT_VERSION = 1


@runtime_checkable
class SemanticAnalysisCapability(Protocol):
    """MVP: geen provider. Contract voor latere lokale AI."""

    def analyze_delta(self, delta: Any, state_snapshot: Any) -> list[Any]: ...
