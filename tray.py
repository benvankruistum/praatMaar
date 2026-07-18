"""
Systeemvak-icoon voor praatMaar (pystray).

Toont een microfoon-icoon dat per dicteertoestand kleurt (donker = gereed,
rood = opname, amber = transcriberen), met een rechtsklik-menu (Instellingen,
Afsluiten). Draait op een **eigen thread** via `Icon.run_detached()`; de
tkinter-mainloop houdt de hoofdthread.

Regel: menu-callbacks draaien op de tray-thread en doen géén tkinter-werk. Ze
zetten alleen een vlag (`request_stop`) of marshalen naar de hoofdthread
(`indicator.call_on_main`). Icoon-/tooltip-updates komen van de pill op de
hoofdthread via `set_state`.
"""

from __future__ import annotations

from typing import Callable

import pystray
from PIL import Image, ImageDraw
from pystray import Menu, MenuItem

import i18n
from indicator import RecordingState

# Kleuren per toestand (RGBA), afgestemd op de pill.
# Idle is bewust donker (niet lichtgrijs): op de Windows-taakbalk oogt
# lichtgrijs als "uitgeschakeld", terwijl de app wél draait.
_STATE_COLORS: dict[RecordingState, tuple[int, int, int, int]] = {
    RecordingState.IDLE: (32, 33, 36, 255),          # #202124 donker — gereed
    RecordingState.RECORDING: (255, 82, 82, 255),     # #ff5252 rood
    RecordingState.TRANSCRIBING: (255, 176, 32, 255),  # #ffb020 amber
    RecordingState.CANCELLED: (154, 160, 166, 255),   # #9aa0a6 grijs
    RecordingState.ERROR: (255, 82, 82, 255),         # rood
}

_TOOLTIP_KEYS: dict[RecordingState, str] = {
    RecordingState.IDLE: "tray.tooltip.idle",
    RecordingState.RECORDING: "tray.tooltip.recording",
    RecordingState.TRANSCRIBING: "tray.tooltip.transcribing",
    RecordingState.CANCELLED: "tray.tooltip.cancelled",
    RecordingState.ERROR: "tray.tooltip.error",
}

ICON_SIZE = 64


def _make_icon(color: tuple[int, int, int, int]) -> Image.Image:
    """Tekent een microfoon-silhouet in `color` op een transparante achtergrond."""

    img = Image.new("RGBA", (ICON_SIZE, ICON_SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    scale = ICON_SIZE / 24.0

    def s(value: float) -> float:
        return value * scale

    width = max(1, int(s(2)))

    draw.rounded_rectangle(
        [s(9), s(3), s(15), s(14)], radius=s(3), fill=color
    )
    draw.arc([s(6), s(5), s(18), s(17)], start=0, end=180, fill=color, width=width)
    draw.line([s(12), s(17), s(12), s(20)], fill=color, width=width)
    draw.line([s(9), s(20), s(15), s(20)], fill=color, width=width)

    return img


def _tooltip(state: RecordingState) -> str:
    return i18n.t(_TOOLTIP_KEYS.get(state, "tray.tooltip.idle"))


class TrayIcon:
    """Het systeemvak-icoon. `start()`/`stop()` beheren de detached tray-thread."""

    def __init__(
        self,
        on_quit: Callable[[], None],
        on_settings: Callable[[], None],
        on_destinations: Callable[[], None],
        on_help: Callable[[], None],
    ) -> None:
        self._on_quit = on_quit
        self._on_settings = on_settings
        self._on_destinations = on_destinations
        self._on_help = on_help
        self._state = RecordingState.IDLE

        self._icons = {
            state: _make_icon(color) for state, color in _STATE_COLORS.items()
        }

        self._icon = pystray.Icon(
            "praatMaar",
            icon=self._icons[RecordingState.IDLE],
            title=_tooltip(RecordingState.IDLE),
            menu=self._build_menu(),
        )

    def _build_menu(self) -> Menu:
        return Menu(
            MenuItem(i18n.t("tray.settings"), self._handle_settings, default=True),
            MenuItem(i18n.t("tray.destinations"), self._handle_destinations),
            MenuItem(i18n.t("tray.help"), self._handle_help),
            Menu.SEPARATOR,
            MenuItem(i18n.t("tray.quit"), self._handle_quit),
        )

    def refresh_language(self) -> None:
        """Vernieuwt menu + tooltip na een UI-taalwissel."""

        try:
            self._icon.menu = self._build_menu()
            self._icon.title = _tooltip(self._state)
            self._icon.update_menu()
        except Exception:
            pass

    def _handle_settings(self, icon: "pystray.Icon", item: "MenuItem") -> None:
        self._on_settings()

    def _handle_destinations(self, icon: "pystray.Icon", item: "MenuItem") -> None:
        self._on_destinations()

    def _handle_help(self, icon: "pystray.Icon", item: "MenuItem") -> None:
        self._on_help()

    def _handle_quit(self, icon: "pystray.Icon", item: "MenuItem") -> None:
        self._on_quit()

    def start(self) -> None:
        """Start de tray op een eigen thread (niet-blokkerend)."""

        self._icon.run_detached()

    def stop(self) -> None:
        try:
            self._icon.stop()
        except Exception:
            pass

    def set_state(self, state: RecordingState, mode: str = "toggle") -> None:
        self._state = state
        try:
            self._icon.icon = self._icons.get(
                state, self._icons[RecordingState.IDLE]
            )
            self._icon.title = _tooltip(state)
        except Exception:
            pass
