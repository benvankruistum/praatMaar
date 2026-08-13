"""Sneltoets-opname: thread-veilig en één tokenbron (pynput)."""

from __future__ import annotations

import threading
from typing import Any

from ui.app import ensure_app


def _make_dialog(set_capture: Any = lambda cb: None):
    from ui.dialogs.settings import SettingsDialog

    ensure_app([])
    return SettingsDialog(
        parent=None,
        current={"hotkey": ["ctrl", "alt"]},
        on_apply=lambda values: None,
        set_capture=set_capture,
        on_retranscribe=None,
        on_parent_retranscribe=None,
    )


def test_capture_callback_marshals_off_the_listener_thread(monkeypatch) -> None:
    # Regression: de pynput-listenerthread riep _refresh_keycaps (widgetbouw)
    # direct aan. De callback moet het werk via ui_dispatch marshallen.
    import ui.dialogs.settings as settings_mod

    queued: list[Any] = []
    monkeypatch.setattr(settings_mod, "ui_dispatch", queued.append)
    monkeypatch.setattr(settings_mod.threading, "current_thread", lambda: object())

    dialog = _make_dialog()
    try:
        dialog._capture_active = True

        class FakeKey:
            praatmaar_token = "f9"

        dialog._capture_callback("press", FakeKey())
        # Niets synchroon gemuteerd op de aanroepende (listener-)thread ...
        assert dialog._capture_pressed == set()
        assert len(queued) == 1
        # ... en het gequeuede werk voert de tokenupdate op de GUI-thread uit.
        queued[0]()
        assert "f9" in dialog._capture_pressed
    finally:
        dialog.close()


def test_capture_callback_updates_immediately_on_main_thread(monkeypatch) -> None:
    # macOS QuartzKeyListener: callbacks komen op de Qt-mainthread binnen.
    import ui.dialogs.settings as settings_mod

    main = threading.main_thread()
    monkeypatch.setattr(settings_mod.threading, "current_thread", lambda: main)
    dispatched: list[Any] = []
    monkeypatch.setattr(settings_mod, "ui_dispatch", dispatched.append)

    dialog = _make_dialog()
    try:
        dialog._capture_active = True

        class FakeKey:
            praatmaar_token = "space"

        dialog._capture_callback("press", FakeKey())
        assert "space" in dialog._capture_pressed
        assert dispatched == []
    finally:
        dialog.close()


def test_queued_capture_binds_press_and_release_tokens(monkeypatch) -> None:
    # Regression: lambda zonder default-args liet alle queued updates de
    # laatste (event, token)-waarde delen → _capture_best bleef leeg.
    import ui.dialogs.settings as settings_mod

    queued: list[Any] = []
    monkeypatch.setattr(settings_mod, "ui_dispatch", queued.append)
    monkeypatch.setattr(settings_mod.threading, "current_thread", lambda: object())

    dialog = _make_dialog()
    try:
        dialog._capture_active = True

        class FakeKey:
            def __init__(self, token: str) -> None:
                self.praatmaar_token = token

        dialog._capture_callback("press", FakeKey("ctrl"))
        dialog._capture_callback("press", FakeKey("space"))
        dialog._capture_callback("release", FakeKey("space"))
        dialog._capture_callback("release", FakeKey("ctrl"))

        for fn in queued:
            fn()

        assert dialog._capture_best == {"ctrl", "space"}
    finally:
        dialog.close()


def test_stop_capture_accepts_single_key() -> None:
    dialog = _make_dialog()
    try:
        dialog._capture_active = True
        dialog._capture_best = {"f5"}
        dialog._stop_capture(confirm=True)
        assert dialog._hotkey_tokens == ["f5"]
    finally:
        dialog.close()


def test_stop_capture_uses_pressed_fallback() -> None:
    dialog = _make_dialog()
    try:
        dialog._capture_active = True
        dialog._capture_pressed = {"shift", "a"}
        dialog._stop_capture(confirm=True)
        assert dialog._hotkey_tokens == ["shift", "a"]
    finally:
        dialog.close()


def test_qt_keypress_is_suppressed_while_global_capture_listens(monkeypatch) -> None:
    # Regression: pynput ("enter") en Qt ("num_enter") voedden allebei
    # _capture_token, waardoor een onmogelijke combinatie werd opgeslagen.
    # Met een actieve globale listener mag Qt geen tokens meer toevoegen.
    from PySide6.QtCore import QEvent, Qt
    from PySide6.QtGui import QKeyEvent

    dialog = _make_dialog(set_capture=lambda cb: None)
    try:
        dialog._capture_active = True
        event = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Enter, Qt.KeyboardModifier.NoModifier)
        dialog.keyPressEvent(event)
        assert dialog._capture_pressed == set()
        assert event.isAccepted()
    finally:
        dialog.close()


def test_qt_keypress_still_captures_without_global_listener() -> None:
    # Zonder globale listener (set_capture=None) blijft het Qt-pad de bron.
    from PySide6.QtCore import QEvent, Qt
    from PySide6.QtGui import QKeyEvent

    dialog = _make_dialog(set_capture=None)
    try:
        dialog._capture_active = True
        event = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_F9, Qt.KeyboardModifier.NoModifier)
        dialog.keyPressEvent(event)
        assert "f9" in dialog._capture_pressed
    finally:
        dialog.close()
