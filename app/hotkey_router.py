"""Hotkey / pill routing — stopt alleen de dicteercyclus (geen MB-stop)."""

from __future__ import annotations

import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import hotkeys
import i18n
from indicator import RecordingState, notify_state


@dataclass
class HotkeyRouter:
    """Toggle / PTT / cancel routing; Meeting Buddy heeft eigen stop-pad."""

    get_session: Callable[[], Any]
    get_mode: Callable[[], str]
    get_hotkey_tokens: Callable[[], set[str]]
    keys_physically_down: Callable[[set[str]], set[str] | None]
    signal_processing_busy: Callable[[], None]
    state_lock: threading.RLock = field(default_factory=threading.RLock)
    pressed_tokens: set[str] = field(default_factory=set)
    toggle_latched: bool = False
    capturing: bool = False
    capture_cb: Any | None = None

    def set_capture(self, callback: Any | None) -> None:
        """Zet sneltoets-opname aan (callback) of uit (None)."""

        with self.state_lock:
            self.capture_cb = callback
            self.capturing = callback is not None
            self.pressed_tokens.clear()
            self.toggle_latched = False

    def hotkey_is_pressed(self) -> bool:
        with self.state_lock:
            tokens = self.get_hotkey_tokens()
            if not tokens:
                return False
            if not tokens.issubset(self.pressed_tokens):
                return False
            wanted = set(tokens)

        try:
            down = self.keys_physically_down(wanted)
        except Exception:
            return True

        if down is None:
            return True

        stale = wanted - down
        if not stale:
            return True

        with self.state_lock:
            self.pressed_tokens.difference_update(stale)
        return False

    def wait_until_modifier_keys_released(self, timeout: float = 3.0) -> None:
        import time

        relevant = {"ctrl", "shift", "alt", "cmd"} | self.get_hotkey_tokens()
        started = time.monotonic()

        while True:
            with self.state_lock:
                still_pressed = set(self.pressed_tokens.intersection(relevant))

            if not still_pressed:
                return

            try:
                down = self.keys_physically_down(still_pressed)
            except Exception:
                down = None
            if down is not None:
                stale = still_pressed - down
                if stale:
                    with self.state_lock:
                        self.pressed_tokens.difference_update(stale)
                    continue

            if time.monotonic() - started >= timeout:
                return

            time.sleep(0.05)

    def on_press(self, key: Any) -> None:
        capture_cb = self.capture_cb
        if capture_cb is not None:
            capture_cb("press", key)
            return

        token = hotkeys.key_to_token(key)
        if token is not None:
            with self.state_lock:
                self.pressed_tokens.add(token)

        if not self.hotkey_is_pressed():
            return

        session = self.get_session()
        mode = self.get_mode()

        with self.state_lock:
            if self.toggle_latched:
                return
            self.toggle_latched = True
            is_recording = session.is_recording
            is_processing = session.is_processing

        if mode == "ptt":
            if is_processing:
                print("\n" + i18n.t("dictation.busy"))
                self.signal_processing_busy()
            elif not is_recording:
                print("\n" + i18n.t("dictation.ptt_started"))
                session.start()
        else:
            # Alleen dicteercyclus — Meeting Buddy heeft eigen overlay/tray-stop.
            if is_recording:
                print("\n" + i18n.t("dictation.stopped_hotkey"))
                session.stop_and_transcribe()
            elif is_processing:
                print("\n" + i18n.t("dictation.busy"))
                self.signal_processing_busy()
            else:
                print("\n" + i18n.t("dictation.started_hotkey"))
                session.start()

    def on_release(self, key: Any) -> None:
        capture_cb = self.capture_cb
        if capture_cb is not None:
            capture_cb("release", key)
            return

        token = hotkeys.key_to_token(key)
        if token is not None:
            with self.state_lock:
                self.pressed_tokens.discard(token)

        if not self.hotkey_is_pressed():
            with self.state_lock:
                was_latched = self.toggle_latched
                self.toggle_latched = False

            if self.get_mode() == "ptt" and was_latched:
                session = self.get_session()
                if session.is_recording:
                    print("\n" + i18n.t("dictation.ptt_stopped"))
                    session.stop_and_transcribe()

    def pill_control_press(self) -> None:
        """Start of stop via de pill-knop (zelfde regels als de sneltoets)."""

        session = self.get_session()
        mode = self.get_mode()
        if session.is_recording:
            print("\n" + i18n.t("dictation.stopped_hotkey"))
            session.stop_and_transcribe()
            return
        if session.is_processing:
            print("\n" + i18n.t("dictation.busy"))
            self.signal_processing_busy()
            return
        if mode == "ptt":
            print("\n" + i18n.t("dictation.ptt_started"))
        else:
            print("\n" + i18n.t("dictation.started_hotkey"))
        session.start()

    def pill_control_release(self) -> None:
        if self.get_mode() != "ptt":
            return
        session = self.get_session()
        if session.is_recording:
            print("\n" + i18n.t("dictation.ptt_stopped"))
            session.stop_and_transcribe()


def default_signal_processing_busy(mode: str, tray: Any | None = None) -> None:
    notify_state(RecordingState.TRANSCRIBING, mode)
    if tray is not None:
        tray.signal_busy()
