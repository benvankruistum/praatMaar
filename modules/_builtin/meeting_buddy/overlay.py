"""Compact Meeting Buddy overlay; deliberately contains no transcript view."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

import i18n

from .hints import HintType
from .state import Hint, HintStatus, MeetingState


def format_elapsed(seconds: float) -> str:
    """Format elapsed seconds as a stable ``HH:MM:SS`` timer."""

    total = max(0, int(seconds))
    hours, remainder = divmod(total, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def pick_emphasis(hints: Sequence[Hint]) -> str | None:
    """Return the id of the highest-priority active hint."""

    active = [hint for hint in hints if hint.status == HintStatus.ACTIVE]
    if not active:
        return None
    return max(active, key=lambda hint: (hint.priority, hint.confidence, hint.id)).id


class MeetingBuddyOverlay:
    """Small always-on-top status and hints window.

    The overlay is the Windows/Linux action surface. On macOS the Modules dialog
    does not expose action buttons, so tray actions remain the leading controls.
    """

    def __init__(
        self,
        *,
        elapsed_seconds: Callable[[], float],
        on_dismiss: Callable[[str], None],
        on_confirm: Callable[[str], None],
        on_reconnect: Callable[[], None],
        parent: Any = None,
    ) -> None:
        import tkinter as tk
        from tkinter import ttk

        self._tk = tk
        self._ttk = ttk
        self._elapsed_seconds = elapsed_seconds
        self._on_dismiss = on_dismiss
        self._on_confirm = on_confirm
        self._on_reconnect = on_reconnect
        self._hint_cards: dict[str, Any] = {}
        self._empty_label: Any | None = None
        self._visible_hint_ids: tuple[str, ...] = ()
        self._shown_once = False

        self.window = tk.Toplevel(parent)
        self.window.withdraw()
        self.window.title(i18n.t("modules.meeting_buddy.overlay.title"))
        self.window.resizable(False, False)
        self.window.attributes("-topmost", True)
        self.window.configure(background="#F4F7FA", padx=12, pady=10)
        self.window.protocol("WM_DELETE_WINDOW", self.minimize)

        self._timer = tk.StringVar(value="00:00:00")
        self._status = tk.StringVar()
        self._listening = tk.StringVar()
        self._recording_banner = tk.StringVar()
        self._capture_status: object = None
        self._pulse_on = False

        header = tk.Frame(self.window, background="#F4F7FA")
        header.pack(fill="x")
        self._listening_dot = tk.Label(
            header,
            text="●",
            background="#F4F7FA",
            foreground="#9AA0A6",
            font=("Segoe UI", 12, "bold"),
        )
        self._listening_dot.pack(side="left")
        tk.Label(
            header,
            textvariable=self._listening,
            background="#F4F7FA",
            foreground="#15334A",
            font=("Segoe UI Semibold", 10),
        ).pack(side="left", padx=(4, 0))
        tk.Label(
            header,
            textvariable=self._timer,
            background="#F4F7FA",
            foreground="#15334A",
            font=("Consolas", 11, "bold"),
        ).pack(side="left", padx=(8, 0))
        ttk.Button(
            header,
            text=i18n.t("modules.meeting_buddy.overlay.minimize"),
            command=self.minimize,
        ).pack(side="right")

        self._recording_frame = tk.Frame(self.window, background="#FFEBEE", padx=8, pady=6)
        self._recording_label = tk.Label(
            self._recording_frame,
            textvariable=self._recording_banner,
            anchor="w",
            background="#FFEBEE",
            foreground="#B71C1C",
            font=("Segoe UI Semibold", 10),
        )
        self._recording_label.pack(fill="x")

        self._hints = tk.Frame(self.window, background="#F4F7FA")
        self._hints.pack(fill="x", pady=(9, 7))
        tk.Label(
            self.window,
            textvariable=self._status,
            anchor="w",
            background="#F4F7FA",
            foreground="#536674",
            font=("Segoe UI", 8),
        ).pack(fill="x")
        self._reconnect_button = ttk.Button(
            self.window,
            text=i18n.t("modules.meeting_buddy.overlay.reconnect"),
            command=self._on_reconnect,
        )

        self._tick()

    def update(
        self,
        state: MeetingState,
        *,
        capture_status: object,
        transcription_status: object,
    ) -> None:
        """Render one immutable state snapshot, capped at three active hints."""

        active = [hint for hint in state.emitted_hints if hint.status == HintStatus.ACTIVE]
        active.sort(key=lambda hint: (-hint.priority, -hint.confidence, hint.id))
        visible = active[:3]
        emphasis_id = pick_emphasis(visible)
        self._render_hints(visible, emphasis_id)
        self._capture_status = capture_status
        self._listening.set(self._listening_text(capture_status, transcription_status))
        self._update_recording_banner(capture_status, transcription_status)
        self._update_listening_dot(capture_status, transcription_status)
        self._status.set(
            "  ·  ".join(
                (
                    self._status_text("capture", capture_status),
                    self._status_text("stt", transcription_status),
                )
            )
        )
        if _enum_value(capture_status) == "error":
            if not self._reconnect_button.winfo_manager():
                self._reconnect_button.pack(fill="x", pady=(7, 0))
        else:
            self._reconnect_button.pack_forget()
        if self.window.state() == "withdrawn":
            self.window.deiconify()
        if not self._shown_once:
            self._shown_once = True
            self._place_top_right()

    def minimize(self) -> None:
        self.window.iconify()

    def close(self) -> None:
        if self.window.winfo_exists():
            self.window.destroy()

    def _render_hints(self, hints: Sequence[Hint], emphasis_id: str | None) -> None:
        hint_ids = tuple(hint.id for hint in hints)
        if hint_ids == self._visible_hint_ids and all(
            hint.id in self._hint_cards for hint in hints
        ):
            for hint in hints:
                self._update_hint_card(hint, emphasized=hint.id == emphasis_id)
            return

        for hint_id in list(self._hint_cards):
            if hint_id not in hint_ids:
                self._hint_cards[hint_id].destroy()
                del self._hint_cards[hint_id]

        if self._empty_label is not None:
            self._empty_label.destroy()
            self._empty_label = None

        if not hints:
            self._empty_label = self._tk.Label(
                self._hints,
                text=i18n.t("modules.meeting_buddy.overlay.no_hints"),
                anchor="w",
                background="#F4F7FA",
                foreground="#6C7C87",
                font=("Segoe UI", 9),
            )
            self._empty_label.pack(fill="x")
            self._visible_hint_ids = ()
            return

        for hint in hints:
            if hint.id not in self._hint_cards:
                self._hint_cards[hint.id] = self._create_hint_card(hint)
            self._update_hint_card(hint, emphasized=hint.id == emphasis_id)

        self._visible_hint_ids = hint_ids

    def _create_hint_card(self, hint: Hint) -> Any:
        card = self._tk.Frame(
            self._hints,
            background="#FFFFFF",
            highlightbackground="#CFD9E0",
            highlightthickness=1,
            padx=8,
            pady=7,
        )
        card.pack(fill="x", pady=(0, 5))
        card.message_label = self._tk.Label(
            card,
            anchor="w",
            justify="left",
            wraplength=350,
            background="#FFFFFF",
            foreground="#132B3A",
            font=("Segoe UI", 9),
        )
        card.message_label.pack(fill="x")
        controls = self._tk.Frame(card, background="#FFFFFF")
        controls.pack(fill="x", pady=(5, 0))
        card.dismiss_button = self._ttk.Button(
            controls,
            text=i18n.t("modules.meeting_buddy.overlay.dismiss"),
            command=lambda hint_id=hint.id: self._on_dismiss(hint_id),
        )
        card.dismiss_button.pack(side="right")
        card.confirm_button = None
        if _enum_value(hint.type) == HintType.CANDIDATE_ACTION_WITHOUT_OWNER.value:
            card.confirm_button = self._ttk.Button(
                controls,
                text=i18n.t("modules.meeting_buddy.overlay.confirm"),
                command=lambda hint_id=hint.id: self._on_confirm(hint_id),
            )
            card.confirm_button.pack(side="right", padx=(0, 6))
        return card

    def _update_hint_card(self, hint: Hint, *, emphasized: bool) -> None:
        card = self._hint_cards[hint.id]
        background = "#DCEEFF" if emphasized else "#FFFFFF"
        border = "#4A90C2" if emphasized else "#CFD9E0"
        thickness = 2 if emphasized else 1
        card.configure(
            background=background, highlightbackground=border, highlightthickness=thickness
        )
        card.message_label.configure(
            text=hint.message,
            background=background,
            font=("Segoe UI Semibold" if emphasized else "Segoe UI", 9),
        )
        for child in card.winfo_children():
            if isinstance(child, self._tk.Frame):
                child.configure(background=background)

    def _tick(self) -> None:
        if not self.window.winfo_exists():
            return
        self._timer.set(format_elapsed(self._elapsed_seconds()))
        if _enum_value(self._capture_status) == "active":
            self._pulse_on = not self._pulse_on
            self._listening_dot.configure(foreground="#E53935" if self._pulse_on else "#FF8A80")
        self.window.after(1000, self._tick)

    def _update_recording_banner(
        self, capture_status: object, transcription_status: object
    ) -> None:
        capture = _enum_value(capture_status)
        if capture == "active":
            stt = _enum_value(transcription_status)
            if stt == "delayed":
                text = i18n.t("modules.meeting_buddy.overlay.recording.active_delayed")
            else:
                text = i18n.t("modules.meeting_buddy.overlay.recording.active")
            self._recording_banner.set(text)
            if not self._recording_frame.winfo_manager():
                self._recording_frame.pack(fill="x", pady=(0, 8), before=self._hints)
            return
        if capture in {"starting", "reconnecting"}:
            self._recording_banner.set(i18n.t("modules.meeting_buddy.overlay.recording.starting"))
            if not self._recording_frame.winfo_manager():
                self._recording_frame.pack(fill="x", pady=(0, 8), before=self._hints)
            return
        if capture == "error":
            self._recording_banner.set(i18n.t("modules.meeting_buddy.overlay.recording.error"))
            self._recording_frame.configure(background="#FFEBEE")
            self._recording_label.configure(background="#FFEBEE", foreground="#B71C1C")
            if not self._recording_frame.winfo_manager():
                self._recording_frame.pack(fill="x", pady=(0, 8), before=self._hints)
            return
        self._recording_frame.pack_forget()

    def _update_listening_dot(self, capture_status: object, transcription_status: object) -> None:
        if _enum_value(capture_status) == "active":
            return
        self._listening_dot.configure(
            foreground=self._listening_color(capture_status, transcription_status)
        )

    def _place_top_right(self) -> None:
        self.window.update_idletasks()
        width = self.window.winfo_reqwidth()
        x = max(0, self.window.winfo_screenwidth() - width - 24)
        self.window.geometry(f"+{x}+24")

    @staticmethod
    def _status_text(kind: str, status: object) -> str:
        value = _enum_value(status)
        key = f"modules.meeting_buddy.overlay.{kind}.{value}"
        translated = i18n.t(key)
        if translated == key:
            translated = str(value)
        label = i18n.t(f"modules.meeting_buddy.overlay.{kind}")
        return f"{label}: {translated}"

    @staticmethod
    def _listening_text(capture_status: object, transcription_status: object) -> str:
        capture = _enum_value(capture_status)
        stt = _enum_value(transcription_status)
        if capture == "error":
            return i18n.t("modules.meeting_buddy.overlay.listening.error")
        if capture in {"starting", "reconnecting"}:
            return i18n.t("modules.meeting_buddy.overlay.listening.starting")
        if capture == "active" and stt == "delayed":
            return i18n.t("modules.meeting_buddy.overlay.listening.delayed")
        if capture == "active" and stt == "active":
            return i18n.t("modules.meeting_buddy.overlay.listening.active")
        if capture == "active":
            return i18n.t("modules.meeting_buddy.overlay.listening.active")
        return i18n.t("modules.meeting_buddy.overlay.listening.idle")

    @staticmethod
    def _listening_color(capture_status: object, transcription_status: object) -> str:
        capture = _enum_value(capture_status)
        stt = _enum_value(transcription_status)
        if capture == "error":
            return "#E53935"
        if capture in {"starting", "reconnecting"}:
            return "#FFB020"
        if capture == "active" and stt in {"active", "delayed"}:
            return "#43A047"
        if capture == "active":
            return "#43A047"
        return "#9AA0A6"


def _enum_value(value: object) -> object:
    return getattr(value, "value", value)
