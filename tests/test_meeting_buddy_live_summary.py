"""Tests for Meeting Buddy live-summary chunk scheduler."""

from __future__ import annotations

import time

from modules._builtin.meeting_buddy.live_summary import (
    LiveSummaryCoordinator,
    LiveSummarySettings,
    normalize_running_summary,
    summary_points,
)
from modules.capabilities.registry import CapabilityRegistry
from modules.capabilities.semantic_analysis import (
    CAPABILITY_ID,
    CONTRACT_VERSION,
    KIND_FINAL_SUMMARY,
    KIND_RUNNING_SUMMARY,
    AnalysisRequest,
    AnalysisResult,
)


class FakeProvider:
    def __init__(self) -> None:
        self.calls: list[AnalysisRequest] = []

    def is_ready(self) -> bool:
        return True

    def analyze(self, request: AnalysisRequest) -> AnalysisResult:
        self.calls.append(request)
        return AnalysisResult(kind=KIND_RUNNING_SUMMARY, text="Samenvatting X")

    def analyze_delta(self, delta, state_snapshot):
        return []


def _wait_calls(provider: FakeProvider, n: int, *, timeout: float = 2.0) -> None:
    deadline = time.time() + timeout
    while len(provider.calls) < n and time.time() < deadline:
        time.sleep(0.05)
    assert len(provider.calls) >= n


def test_live_summary_requires_time_and_chars() -> None:
    caps = CapabilityRegistry()
    provider = FakeProvider()
    caps.register(
        capability_id=CAPABILITY_ID,
        provider=provider,
        owner_module_id="local-llm",
        contract_version=CONTRACT_VERSION,
    )
    seen: list[str] = []
    coord = LiveSummaryCoordinator(
        capabilities=caps,
        settings=LiveSummarySettings(enabled=True, interval_s=30, min_new_chars=50),
        on_summary=seen.append,
    )
    # Simuleer start van meeting: timer vanaf t=100.
    coord.reset()
    with coord._lock:
        coord._last_run_at = 100.0

    coord.on_final_text("kort", now=110.0)
    assert provider.calls == []
    # genoeg tekens, maar interval nog niet voorbij
    coord.on_final_text("x" * 60, now=120.0)
    time.sleep(0.1)
    assert provider.calls == []

    # interval + tekens: eerste run
    coord.on_final_text("y" * 60, now=135.0)
    deadline = time.time() + 2
    while not seen and time.time() < deadline:
        time.sleep(0.05)
    assert seen == ["- Samenvatting X"]
    assert len(provider.calls) == 1

    # te vroeg + te weinig nieuwe tekens
    coord.on_final_text("nog wat", now=140.0)
    time.sleep(0.1)
    assert len(provider.calls) == 1


def test_live_summary_sends_delta_and_previous_bullets() -> None:
    caps = CapabilityRegistry()
    results = [
        "- punt A\n- punt B\n- punt C",
        "- punt A\n- punt B\n- punt C\n- punt D",
    ]

    class SequencedProvider(FakeProvider):
        def analyze(self, request: AnalysisRequest) -> AnalysisResult:
            self.calls.append(request)
            text = results[min(len(self.calls) - 1, len(results) - 1)]
            return AnalysisResult(kind=KIND_RUNNING_SUMMARY, text=text)

    provider = SequencedProvider()
    caps.register(
        capability_id=CAPABILITY_ID,
        provider=provider,
        owner_module_id="local-llm",
        contract_version=CONTRACT_VERSION,
    )
    seen: list[str] = []
    coord = LiveSummaryCoordinator(
        capabilities=caps,
        settings=LiveSummarySettings(enabled=True, interval_s=10, min_new_chars=20),
        on_summary=seen.append,
    )
    coord.reset()
    with coord._lock:
        coord._last_run_at = 100.0

    first = "alpha " * 10
    coord.on_final_text(first, now=120.0)
    _wait_calls(provider, 1)
    assert provider.calls[0].transcript == first.strip()
    assert provider.calls[0].previous_summary is None
    deadline = time.time() + 2
    while len(seen) < 1 and time.time() < deadline:
        time.sleep(0.05)
    assert seen
    assert seen[0].startswith("- ")
    with coord._lock:
        coord._last_run_at = 120.0
        coord._busy = False

    second = "beta " * 10
    coord.on_final_text(second, now=140.0)
    _wait_calls(provider, 2)
    assert provider.calls[1].transcript == second.strip()
    assert provider.calls[1].previous_summary == seen[0]
    assert "alpha" not in provider.calls[1].transcript


def test_summary_points_caps_at_five() -> None:
    assert summary_points("a\nb\nc\nd\ne\nf") == ["a", "b", "c", "d", "e"]


def test_normalize_running_summary_bullets() -> None:
    assert normalize_running_summary("First. Second. Third.") == ("- First.\n- Second.\n- Third.")
    assert normalize_running_summary("- already\n- bullets") == "- already\n- bullets"
    assert normalize_running_summary("") == ""


def test_run_final_summary_uses_final_kind_and_context() -> None:
    caps = CapabilityRegistry()
    provider = FakeProvider()
    caps.register(
        capability_id=CAPABILITY_ID,
        provider=provider,
        owner_module_id="local-llm",
        contract_version=CONTRACT_VERSION,
    )
    coord = LiveSummaryCoordinator(
        capabilities=caps,
        settings=LiveSummarySettings(enabled=True, interval_s=30, min_new_chars=50),
        on_summary=lambda _text: None,
    )
    context = {"agenda": [{"title": "Budget", "status": "open"}], "open_titles": ["Budget"]}
    result = coord.run_final_summary(
        transcript="We bespraken het budget voor Q3.",
        previous="- Opening",
        context=context,
        language="nl",
    )
    assert result.startswith("- ")
    assert len(provider.calls) == 1
    assert provider.calls[0].kind == KIND_FINAL_SUMMARY
    assert provider.calls[0].transcript == "We bespraken het budget voor Q3."
    assert provider.calls[0].previous_summary == "- Opening"
    assert provider.calls[0].context == context
