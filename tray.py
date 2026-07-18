"""
Systeemvak-icoon voor praatMaar (pystray).

Toont een microfoon-icoon dat per dicteertoestand kleurt (grijs = idle,
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

from indicator import RecordingState

# Kleuren per toestand (RGBA), consistent met de pill.
_STATE_COLORS: dict[RecordingState, tuple[int, int, int, int]] = {
    RecordingState.IDLE: (200, 204, 208, 255),        # #c8ccd0 grijs
    RecordingState.RECORDING: (255, 82, 82, 255),     # #ff5252 rood
    RecordingState.TRANSCRIBING: (255, 176, 32, 255),  # #ffb020 amber
    RecordingState.CANCELLED: (154, 160, 166, 255),   # #9aa0a6 grijs
    RecordingState.ERROR: (255, 82, 82, 255),         # rood
}

_STATE_TOOLTIPS: dict[RecordingState, str] = {
    RecordingState.IDLE: "praatMaar — gereed",
    RecordingState.RECORDING: "praatMaar — opname",
    RecordingState.TRANSCRIBING: "praatMaar — transcriberen",
    RecordingState.CANCELLED: "praatMaar — geannuleerd",
    RecordingState.ERROR: "praatMaar — fout",
}

ICON_SIZE = 64


def _make_icon(color: tuple[int, int, int, int]) -> Image.Image:
    """Tekent een microfoon-silhouet in `color` op een transparante achtergrond."""

    img = Image.new("RGBA", (ICON_SIZE, ICON_SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    scale = ICON_SIZE / 24.0  # het ontwerp is in een 24px-raster

    def s(value: float) -> float:
        return value * scale

    width = max(1, int(s(2)))

    # Microfoon-capsule (afgeronde rechthoek).
    draw.rounded_rectangle(
        [s(9), s(3), s(15), s(14)], radius=s(3), fill=color
    )
    # Beugel: onderste halve cirkel rond de capsule.
    draw.arc([s(6), s(5), s(18), s(17)], start=0, end=180, fill=color, width=width)
    # Standaard.
    draw.line([s(12), s(17), s(12), s(20)], fill=color, width=width)
    # Voet.
    draw.line([s(9), s(20), s(15), s(20)], fill=color, width=width)

    return img


class TrayIcon:
    """Het systeemvak-icoon. `start()`/`stop()` beheren de detached tray-thread."""

    def __init__(
        self,
        on_quit: Callable[[], None],
        on_settings: Callable[[], None],
    ) -> None:
        self._on_quit = on_quit
        self._on_settings = on_settings

        # Iconen vooraf renderen (één per toestand).
        self._icons = {
            state: _make_icon(color) for state, color in _STATE_COLORS.items()
        }

        menu = Menu(
            MenuItem("Instellingen", self._handle_settings, default=True),
            Menu.SEPARATOR,
            MenuItem("Afsluiten", self._handle_quit),
        )

        self._icon = pystray.Icon(
            "praatmaar",
            icon=self._icons[RecordingState.IDLE],
            title=_STATE_TOOLTIPS[RecordingState.IDLE],
            menu=menu,
        )

    # ----- menu-callbacks (draaien op de tray-thread) -----

    def _handle_settings(self, icon: "pystray.Icon", item: "MenuItem") -> None:
        self._on_settings()

    def _handle_quit(self, icon: "pystray.Icon", item: "MenuItem") -> None:
        self._on_quit()

    # ----- levenscyclus -----

    def start(self) -> None:
        """Start de tray op een eigen thread (niet-blokkerend)."""

        self._icon.run_detached()

    def stop(self) -> None:
        try:
            self._icon.stop()
        except Exception:
            pass

    # ----- statusweergave (aangeroepen vanaf de hoofdthread via de pill) -----

    def set_state(self, state: RecordingState, mode: str = "toggle") -> None:
        try:
            self._icon.icon = self._icons.get(
                state, self._icons[RecordingState.IDLE]
            )
            self._icon.title = _STATE_TOOLTIPS.get(state, "praatMaar")
        except Exception:
            pass
