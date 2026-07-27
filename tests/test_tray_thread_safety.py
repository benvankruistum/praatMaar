"""Tray: GUI-mutaties gemarshald naar de main-thread; geen tray-object zonder tray."""

from __future__ import annotations

import threading
from unittest.mock import patch

from PySide6.QtWidgets import QSystemTrayIcon

from indicator import RecordingState
from ui.app import ensure_app
from ui.tray import TrayIcon


def _make_tray() -> TrayIcon:
    ensure_app([])
    return TrayIcon(
        on_quit=lambda: None,
        on_settings=lambda: None,
        on_destinations=lambda: None,
        on_modules=lambda: None,
        on_help=lambda: None,
    )


def test_set_attention_from_worker_thread_applies_on_main_thread() -> None:
    # Regression: _report_user_error riep set_attention_needed direct vanaf
    # de hotkey-thread aan (QSystemTrayIcon.setIcon buiten de GUI-thread).
    from PySide6.QtCore import QThread

    app = ensure_app([])
    tray = _make_tray()
    idle = tray._icons[RecordingState.IDLE]

    apply_threads: list[QThread] = []
    original_apply = tray._apply_icon_and_title

    def recording_apply() -> None:
        apply_threads.append(QThread.currentThread())
        original_apply()

    tray._apply_icon_and_title = recording_apply  # type: ignore[method-assign]

    worker = threading.Thread(target=lambda: tray.set_attention_needed(True))
    worker.start()
    worker.join(timeout=5)

    for _ in range(5):
        app.processEvents()
    assert tray._attention is True
    assert tray._icon_for(RecordingState.IDLE).tobytes() != idle.tobytes()
    assert apply_threads, "_apply_icon_and_title is nooit aangeroepen"
    assert all(thread is app.thread() for thread in apply_threads)
    tray.stop()


def test_no_qsystemtrayicon_constructed_without_desktop_tray() -> None:
    # Hardening: op tray-loze desktops (headless CI, kale Linux-sessies)
    # crashte de onvoorwaardelijke QSystemTrayIcon-constructie native.
    ensure_app([])
    with patch.object(QSystemTrayIcon, "isSystemTrayAvailable", return_value=False):
        tray = _make_tray()

    assert tray._icon is None
    assert tray._fallback_window is not None
    # Alle publieke paden blijven werken zonder tray-object.
    tray.set_state(RecordingState.RECORDING)
    tray.set_attention_needed(True)
    tray.refresh_language()
    tray.start()
    tray.stop()
