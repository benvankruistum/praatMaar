"""Pill/hotkey mag Meeting Buddy niet stoppen via stop_active_meeting."""

from __future__ import annotations

import ast
from pathlib import Path

from app.hotkey_router import HotkeyRouter


def test_hotkey_router_source_has_no_stop_active_meeting() -> None:
    src = Path("app/hotkey_router.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    imported: set[str] = set()
    called: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                imported.add(alias.name)
        elif isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name):
                called.add(func.id)
            elif isinstance(func, ast.Attribute):
                called.add(func.attr)
    assert "stop_active_meeting" not in imported
    assert "stop_active_meeting" not in called
    assert "stop_routing" not in src


def test_dictation_source_has_no_stop_active_meeting() -> None:
    src = Path("dictation.py").read_text(encoding="utf-8")
    assert "stop_active_meeting" not in src


def test_pill_and_hotkey_do_not_call_stop_active_meeting(monkeypatch) -> None:
    calls: list[str] = []

    class _Session:
        is_recording = False
        is_processing = False

        def start(self) -> None:
            calls.append("start")

        def stop_and_transcribe(self) -> None:
            calls.append("stop")

    def boom(*_args, **_kwargs):
        raise AssertionError("stop_active_meeting must not be called")

    monkeypatch.setattr(
        "modules._builtin.meeting_buddy.stop_routing.stop_active_meeting",
        boom,
        raising=False,
    )

    router = HotkeyRouter(
        get_session=lambda: _Session(),
        get_mode=lambda: "toggle",
        get_hotkey_tokens=lambda: {"ctrl", "space"},
        keys_physically_down=lambda _tokens: None,
        signal_processing_busy=lambda: None,
    )
    router.pill_control_press()
    assert calls == ["start"]

    session = _Session()
    session.is_recording = True
    router = HotkeyRouter(
        get_session=lambda: session,
        get_mode=lambda: "toggle",
        get_hotkey_tokens=lambda: {"ctrl", "space"},
        keys_physically_down=lambda _tokens: None,
        signal_processing_busy=lambda: None,
    )
    router.pill_control_press()
    assert calls == ["start", "stop"]
