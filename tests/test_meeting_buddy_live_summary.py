"""Tests for Meeting Buddy live-summary chunk scheduler."""

from __future__ import annotations

import time

from modules._builtin.meeting_buddy.live_summary import LiveSummaryCoordinator, LiveSummarySettings
from modules.capabilities.registry import CapabilityRegistry
from modules.capabilities.semantic_analysis import (
    CAPABILITY_ID,
    CONTRACT_VERSION,
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
    coord.on_final_text("kort", now=100.0)
    assert provider.calls == []
    coord.on_final_text("x" * 60, now=100.0)
    # first run: last_run_at was 0 so interval ok
    deadline = time.time() + 2
    while not seen and time.time() < deadline:
        time.sleep(0.05)
    assert seen == ["Samenvatting X"]
    assert len(provider.calls) == 1

    # too soon + not enough new chars
    coord.on_final_text("nog wat", now=110.0)
    time.sleep(0.1)
    assert len(provider.calls) == 1
