"""
Systeemvak-/menubalk-icoon voor praatMaar (pystray).

Toont een microfoon-icoon dat per dicteertoestand kleurt (donker = gereed,
rood = opname, amber = transcriberen), met een menu (Instellingen,
Bestemmingen, Modules, Help, Afsluiten).

Threading:
- **Windows:** `Icon.run_detached()` op een eigen thread; tkinter houdt de
  hoofdthread.
- **macOS:** AppKit eist de main-thread-runloop. `start()` is daar een no-op;
  `run()` blokkeert met `Icon.run()` (Cocoa). De indicator plant een NSTimer
  op dezelfde runloop (zie `indicator._mac`).

Regel: menu-callbacks doen géén tkinter-werk. Ze zetten een vlag
(`request_stop`) of marshalen naar de hoofdthread (`indicator.call_on_main`).
Icoon-/tooltip-updates komen van de pill via `set_state`.
"""

from __future__ import annotations

import sys
from collections.abc import Callable

import pystray
from PIL import Image, ImageDraw
from pystray import Menu, MenuItem

import i18n
from indicator import RecordingState
from modules._contract import ModuleAction, PraatMaarModule

# Kleuren per toestand (RGBA), afgestemd op de pill.
# Idle is bewust donker (niet lichtgrijs): op de Windows-taakbalk oogt
# lichtgrijs als "uitgeschakeld", terwijl de app wél draait.
_STATE_COLORS: dict[RecordingState, tuple[int, int, int, int]] = {
    RecordingState.IDLE: (32, 33, 36, 255),  # #202124 donker — gereed
    RecordingState.RECORDING: (255, 82, 82, 255),  # #ff5252 rood
    RecordingState.TRANSCRIBING: (255, 176, 32, 255),  # #ffb020 amber
    RecordingState.CANCELLED: (154, 160, 166, 255),  # #9aa0a6 grijs
    RecordingState.ERROR: (255, 82, 82, 255),  # rood
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

    draw.rounded_rectangle([s(9), s(3), s(15), s(14)], radius=s(3), fill=color)
    draw.arc([s(6), s(5), s(18), s(17)], start=0, end=180, fill=color, width=width)
    draw.line([s(12), s(17), s(12), s(20)], fill=color, width=width)
    draw.line([s(9), s(20), s(15), s(20)], fill=color, width=width)

    return img


def _tooltip(state: RecordingState) -> str:
    return i18n.t(_TOOLTIP_KEYS.get(state, "tray.tooltip.idle"))


class TrayIcon:
    """Systeemvak-/menubalk-icoon. Zie module-doc voor threading per OS."""

    def __init__(
        self,
        on_quit: Callable[[], None],
        on_settings: Callable[[], None],
        on_destinations: Callable[[], None],
        on_modules: Callable[[], None],
        on_help: Callable[[], None],
        *,
        on_module_action: Callable[[str, str], None] | None = None,
        get_module_tray_actions: Callable[[], list[tuple[PraatMaarModule, ModuleAction]]]
        | None = None,
    ) -> None:
        self._on_quit = on_quit
        self._on_settings = on_settings
        self._on_destinations = on_destinations
        self._on_modules = on_modules
        self._on_help = on_help
        self._on_module_action = on_module_action
        self._get_module_tray_actions = get_module_tray_actions
        self._state = RecordingState.IDLE
        self._running_main = False

        self._icons = {state: _make_icon(color) for state, color in _STATE_COLORS.items()}

        self._icon = pystray.Icon(
            "praatMaar",
            icon=self._icons[RecordingState.IDLE],
            title=_tooltip(RecordingState.IDLE),
            menu=self._build_menu(),
        )

    def _build_modules_menu(self) -> MenuItem:
        entries = self._get_module_tray_actions() if self._get_module_tray_actions else []
        if not entries:
            return MenuItem(i18n.t("tray.modules"), self._handle_modules)

        by_module: dict[str, tuple[PraatMaarModule, list[ModuleAction]]] = {}
        for module, action in entries:
            bucket = by_module.setdefault(module.id, (module, []))
            bucket[1].append(action)

        items: list[MenuItem | pystray.Menu] = [
            MenuItem(i18n.t("modules.manage"), self._handle_modules, default=True),
            Menu.SEPARATOR,
        ]

        for module, actions in by_module.values():
            if len(actions) == 1:
                action = actions[0]
                items.append(
                    MenuItem(
                        i18n.t(action.label_key),
                        lambda _i, _it, mid=module.id, aid=action.id: self._handle_module_action(
                            mid, aid
                        ),
                    )
                )
                continue

            action_items = [
                MenuItem(
                    i18n.t(action.label_key),
                    lambda _i, _it, mid=module.id, aid=action.id: self._handle_module_action(
                        mid, aid
                    ),
                )
                for action in actions
            ]
            items.append(MenuItem(i18n.t(module.display_name_key()), Menu(*action_items)))

        return MenuItem(i18n.t("tray.modules"), Menu(*items))

    def _build_menu(self) -> Menu:
        return Menu(
            MenuItem(i18n.t("tray.settings"), self._handle_settings, default=True),
            MenuItem(i18n.t("tray.destinations"), self._handle_destinations),
            self._build_modules_menu(),
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

    def refresh_modules_menu(self) -> None:
        """Vernieuwt het Modules-submenu na wijziging van ingeschakelde modules."""

        try:
            self._icon.menu = self._build_menu()
            self._icon.update_menu()
        except Exception:
            pass

    @property
    def owns_main_thread(self) -> bool:
        """True op macOS: de menubalk moet de Cocoa-mainloop op de hoofdthread."""

        return sys.platform == "darwin"

    def _handle_settings(self, icon: pystray.Icon, item: MenuItem) -> None:
        self._on_settings()

    def _handle_destinations(self, icon: pystray.Icon, item: MenuItem) -> None:
        self._on_destinations()

    def _handle_modules(self, icon: pystray.Icon, item: MenuItem) -> None:
        self._on_modules()

    def _handle_help(self, icon: pystray.Icon, item: MenuItem) -> None:
        self._on_help()

    def _handle_module_action(self, module_id: str, action_id: str) -> None:
        if self._on_module_action is not None:
            self._on_module_action(module_id, action_id)

    def _handle_quit(self, icon: pystray.Icon, item: MenuItem) -> None:
        self._on_quit()
        # Zorg dat een blokkerende `run()` (Darwin) terugkeert.
        try:
            self._icon.stop()
        except Exception:
            pass

    def start(self) -> None:
        """
        Start de tray.

        Windows: niet-blokkerend op een eigen thread.
        macOS: no-op — bel daarna `run()` op de hoofdthread.
        """

        if self.owns_main_thread:
            return
        self._icon.run_detached()

    def run(self) -> None:
        """Blokkerende Cocoa-/menubalk-runloop (macOS). Op Windows: no-op."""

        if not self.owns_main_thread:
            return
        self._running_main = True
        try:
            self._icon.run()
        finally:
            self._running_main = False

    def stop(self) -> None:
        try:
            self._icon.stop()
        except Exception:
            pass

    def set_state(self, state: RecordingState, mode: str = "toggle") -> None:
        self._state = state
        try:
            self._icon.icon = self._icons.get(state, self._icons[RecordingState.IDLE])
            self._icon.title = _tooltip(state)
        except Exception:
            pass
