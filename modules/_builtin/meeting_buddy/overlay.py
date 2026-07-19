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
        parent: Any = None,
    ) -> None:
        import tkinter as tk
        from tkinter import ttk

        self._tk = tk
        self._ttk = ttk
        self._elapsed_seconds = elapsed_seconds
        self._on_dismiss = on_dismiss
        self._on_confirm = on_confirm
        self._hint_widgets: list[Any] = []

        self.window = tk.Toplevel(parent)
        self.window.withdraw()
        self.window.title(i18n.t("modules.meeting_buddy.overlay.title"))
        self.window.resizable(False, False)
        self.window.attributes("-topmost", True)
        self.window.configure(background="#F4F7FA", padx=12, pady=10)
        self.window.protocol("WM_DELETE_WINDOW", self.minimize)

        self._timer = tk.StringVar(value="00:00:00")
        self._status = tk.StringVar()

        header = tk.Frame(self.window, background="#F4F7FA")
        header.pack(fill="x")
        tk.Label(
            header,
            text=i18n.t("modules.meeting_buddy.overlay.active"),
            background="#F4F7FA",
            foreground="#15334A",
            font=("Segoe UI Semibold", 10),
        ).pack(side="left")
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
        self._status.set(
            "  ·  ".join(
                (
                    self._status_text("capture", capture_status),
                    self._status_text("stt", transcription_status),
                    i18n.t("modules.meeting_buddy.overlay.session.active"),
                )
            )
        )
        if self.window.state() == "withdrawn":
            self.window.deiconify()
            self._place_top_right()

    def minimize(self) -> None:
        self.window.iconify()

    def close(self) -> None:
        if self.window.winfo_exists():
            self.window.destroy()

    def _render_hints(self, hints: Sequence[Hint], emphasis_id: str | None) -> None:
        for widget in self._hint_widgets:
            widget.destroy()
        self._hint_widgets.clear()

        if not hints:
            empty = self._tk.Label(
                self._hints,
                text=i18n.t("modules.meeting_buddy.overlay.no_hints"),
                anchor="w",
                background="#F4F7FA",
                foreground="#6C7C87",
                font=("Segoe UI", 9),
            )
            empty.pack(fill="x")
            self._hint_widgets.append(empty)
            return

        for hint in hints:
            emphasized = hint.id == emphasis_id
            background = "#DCEEFF" if emphasized else "#FFFFFF"
            border = "#4A90C2" if emphasized else "#CFD9E0"
            card = self._tk.Frame(
                self._hints,
                background=background,
                highlightbackground=border,
                highlightthickness=2 if emphasized else 1,
                padx=8,
                pady=7,
            )
            card.pack(fill="x", pady=(0, 5))
            self._tk.Label(
                card,
                text=hint.message,
                anchor="w",
                justify="left",
                wraplength=350,
                background=background,
                foreground="#132B3A",
                font=("Segoe UI Semibold" if emphasized else "Segoe UI", 9),
            ).pack(fill="x")
            controls = self._tk.Frame(card, background=background)
            controls.pack(fill="x", pady=(5, 0))
            self._ttk.Button(
                controls,
                text=i18n.t("modules.meeting_buddy.overlay.dismiss"),
                command=lambda hint_id=hint.id: self._on_dismiss(hint_id),
            ).pack(side="right")
            if _enum_value(hint.type) == HintType.CANDIDATE_ACTION_WITHOUT_OWNER.value:
                self._ttk.Button(
                    controls,
                    text=i18n.t("modules.meeting_buddy.overlay.confirm"),
                    command=lambda hint_id=hint.id: self._on_confirm(hint_id),
                ).pack(side="right", padx=(0, 6))
            self._hint_widgets.append(card)

    def _tick(self) -> None:
        if not self.window.winfo_exists():
            return
        self._timer.set(format_elapsed(self._elapsed_seconds()))
        self.window.after(1000, self._tick)

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


def _enum_value(value: object) -> object:
    return getattr(value, "value", value)
