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
from typing import Any

import pystray
from PIL import Image, ImageDraw
from pystray import Menu, MenuItem

import i18n
from indicator import RecordingState
from modules._contract import ModuleAction, PraatMaarModule
from ui_icon import make_mic_image

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

# Contextmenuregels voor tray én pill (rechtsklik).
# ("separator",) | ("item", label, callback) | ("submenu", label, [entries])
MenuEntry = tuple[Any, ...]

ModuleActionCallback = Callable[[str, str], Callable[[], None]]


def _group_module_actions(
    module_entries: list[tuple[PraatMaarModule, ModuleAction]],
) -> list[tuple[PraatMaarModule, list[ModuleAction]]]:
    by_module: dict[str, tuple[PraatMaarModule, list[ModuleAction]]] = {}
    for module, action in module_entries:
        bucket = by_module.setdefault(module.id, (module, []))
        bucket[1].append(action)
    return list(by_module.values())


def _module_action_menu_entries(
    module: PraatMaarModule,
    actions: list[ModuleAction],
    module_action_callback: ModuleActionCallback,
) -> list[MenuEntry]:
    return [
        (
            "item",
            i18n.t(action.label_key),
            module_action_callback(module.id, action.id),
        )
        for action in actions
    ]


def _module_tray_cascade_entries(
    module_entries: list[tuple[PraatMaarModule, ModuleAction]],
    module_action_callback: ModuleActionCallback,
) -> list[MenuEntry]:
    cascades: list[MenuEntry] = []
    for module, actions in _group_module_actions(module_entries):
        action_children = _module_action_menu_entries(module, actions, module_action_callback)
        cascades.append(("submenu", i18n.t(module.display_name_key()), action_children))
    return cascades


def _module_tray_root_entries(
    root_entries: list[tuple[PraatMaarModule, ModuleAction]],
    module_action_callback: ModuleActionCallback,
) -> list[MenuEntry]:
    entries: list[MenuEntry] = []
    for module, actions in _group_module_actions(root_entries):
        if len(actions) == 1:
            action = actions[0]
            entries.append(
                (
                    "item",
                    i18n.t(action.label_key),
                    module_action_callback(module.id, action.id),
                )
            )
            continue
        action_children = _module_action_menu_entries(module, actions, module_action_callback)
        entries.append(("submenu", i18n.t(module.display_name_key()), action_children))
    return entries


def build_context_menu_entries(
    *,
    on_settings: Callable[[], None],
    on_destinations: Callable[[], None],
    on_modules: Callable[[], None],
    on_help: Callable[[], None],
    on_quit: Callable[[], None],
    module_tray_actions: list[tuple[PraatMaarModule, ModuleAction]],
    module_tray_root_actions: list[tuple[PraatMaarModule, ModuleAction]],
    module_action_callback: ModuleActionCallback,
) -> list[MenuEntry]:
    """Bouwt tray-/pill-contextmenu-items (Instellingen t/m Afsluiten)."""

    entries: list[MenuEntry] = [
        ("item", i18n.t("tray.settings"), on_settings),
        ("item", i18n.t("tray.destinations"), on_destinations),
    ]

    module_section = _module_tray_cascade_entries(module_tray_actions, module_action_callback)
    module_section.extend(
        _module_tray_root_entries(module_tray_root_actions, module_action_callback)
    )
    if module_section:
        entries.extend(module_section)
        entries.append(("separator",))

    entries.append(("item", i18n.t("tray.modules"), on_modules))
    entries.append(("item", i18n.t("tray.help"), on_help))
    entries.append(("separator",))
    entries.append(("item", i18n.t("tray.quit"), on_quit))
    return entries


def _make_icon(color: tuple[int, int, int, int]) -> Image.Image:
    """Tekent een microfoon-silhouet in `color` op een transparante achtergrond."""

    return make_mic_image(color, size=ICON_SIZE)


def _draw_attention_badge(base: Image.Image) -> Image.Image:
    """Voegt een amber uitroepteken-badge toe (actie vereist)."""

    img = base.copy()
    draw = ImageDraw.Draw(img)
    cx = ICON_SIZE - 14
    cy = ICON_SIZE - 14
    radius = 12
    draw.ellipse(
        [cx - radius, cy - radius, cx + radius, cy + radius],
        fill=(255, 176, 32, 255),
    )
    draw.rectangle([cx - 2, cy - 7, cx + 2, cy + 2], fill=(255, 255, 255, 255))
    draw.rectangle([cx - 2, cy + 4, cx + 2, cy + 7], fill=(255, 255, 255, 255))
    return img


def _tooltip(state: RecordingState) -> str:
    return i18n.t(_TOOLTIP_KEYS.get(state, "tray.tooltip.idle"))


def _populate_tk_menu(menu: Any, entries: list[MenuEntry]) -> None:
    import tkinter as tk

    for entry in entries:
        kind = entry[0]
        if kind == "separator":
            menu.add_separator()
        elif kind == "item":
            _label, callback = entry[1], entry[2]
            menu.add_command(label=_label, command=callback)
        elif kind == "submenu":
            _label, children = entry[1], entry[2]
            submenu = tk.Menu(menu, tearoff=0)
            _populate_tk_menu(submenu, children)
            menu.add_cascade(label=_label, menu=submenu)


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
        get_module_tray_root_actions: Callable[[], list[tuple[PraatMaarModule, ModuleAction]]]
        | None = None,
    ) -> None:
        self._on_quit = on_quit
        self._on_settings = on_settings
        self._on_destinations = on_destinations
        self._on_modules = on_modules
        self._on_help = on_help
        self._on_module_action = on_module_action
        self._get_module_tray_actions = get_module_tray_actions
        self._get_module_tray_root_actions = get_module_tray_root_actions
        self._state = RecordingState.IDLE
        self._attention = False
        self._attention_tooltip_key = "tray.tooltip.attention_mic"
        self._running_main = False

        self._icons = {state: _make_icon(color) for state, color in _STATE_COLORS.items()}

        self._icon = pystray.Icon(
            "praatMaar",
            icon=self._icons[RecordingState.IDLE],
            title=_tooltip(RecordingState.IDLE),
            menu=self._build_menu(),
        )

    def _module_action_callback(self, module_id: str, action_id: str) -> Callable[[], None]:
        def callback() -> None:
            self._handle_module_action(module_id, action_id)

        return callback

    def context_menu_entries(self) -> list[MenuEntry]:
        """Zelfde items als het tray-menu, bruikbaar voor de pill-rechtsklik."""

        return build_context_menu_entries(
            on_settings=self._on_settings,
            on_destinations=self._on_destinations,
            on_modules=self._on_modules,
            on_help=self._on_help,
            on_quit=self._on_quit,
            module_tray_actions=(
                self._get_module_tray_actions() if self._get_module_tray_actions else []
            ),
            module_tray_root_actions=(
                self._get_module_tray_root_actions() if self._get_module_tray_root_actions else []
            ),
            module_action_callback=self._module_action_callback,
        )

    def popup_menu(self, x: int, y: int, *, tk_parent: Any | None = None) -> None:
        """Toont het contextmenu op schermpositie `(x, y)` (pill-rechtsklik)."""

        if sys.platform == "win32":
            self._popup_tk(tk_parent, x, y)
        elif sys.platform == "darwin":
            self._popup_ns()

    def _popup_tk(self, parent: Any | None, x: int, y: int) -> None:
        if parent is None:
            return
        import tkinter as tk

        menu = tk.Menu(parent, tearoff=0)
        _populate_tk_menu(menu, self.context_menu_entries())
        try:
            menu.tk_popup(int(x), int(y))
        finally:
            menu.grab_release()

    def _popup_ns(self) -> None:
        try:
            from AppKit import NSEvent, NSMenu, NSMenuItem  # type: ignore[import-not-found]
            from Foundation import NSObject  # type: ignore[import-not-found]
        except Exception:
            return

        # Houd een target-object levend voor AppKit-selectors.
        if not hasattr(self, "_ns_menu_target"):

            class _MenuTarget(NSObject):
                _owner = None

                def praatMaarMenuAction_(self, sender: Any) -> None:  # noqa: N802
                    callback = sender.representedObject()
                    if callable(callback):
                        callback()

            target = _MenuTarget.alloc().init()
            target._owner = self
            self._ns_menu_target = target

        def build(entries: list[MenuEntry]) -> Any:
            menu = NSMenu.alloc().init()
            menu.setAutoenablesItems_(False)
            for entry in entries:
                kind = entry[0]
                if kind == "separator":
                    menu.addItem_(NSMenuItem.separatorItem())
                    continue
                if kind == "item":
                    label, callback = entry[1], entry[2]
                    item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
                        label, "praatMaarMenuAction:", ""
                    )
                    item.setEnabled_(True)
                    item.setRepresentedObject_(callback)
                    item.setTarget_(self._ns_menu_target)
                    menu.addItem_(item)
                    continue
                if kind == "submenu":
                    label, children = entry[1], entry[2]
                    item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(label, None, "")
                    item.setSubmenu_(build(children))
                    menu.addItem_(item)
            return menu

        menu = build(self.context_menu_entries())
        point = NSEvent.mouseLocation()
        menu.popUpMenuPositioningItem_atLocation_inView_(None, point, None)

    def _entries_to_pystray(self, entries: list[MenuEntry]) -> list[MenuItem | Menu]:
        items: list[MenuItem | Menu] = []
        for entry in entries:
            kind = entry[0]
            if kind == "separator":
                items.append(Menu.SEPARATOR)
            elif kind == "item":
                label, callback = entry[1], entry[2]

                def action(
                    _icon: pystray.Icon | None = None,
                    _item: MenuItem | None = None,
                    *,
                    _cb: Callable[[], None] = callback,
                ) -> None:
                    _cb()

                default = callback is self._on_settings
                items.append(MenuItem(label, action, default=default))
            elif kind == "submenu":
                label, children = entry[1], entry[2]
                items.append(MenuItem(label, Menu(*self._entries_to_pystray(children))))
        return items

    def _build_menu(self) -> Menu:
        return Menu(*self._entries_to_pystray(self.context_menu_entries()))

    def refresh_language(self) -> None:
        """Vernieuwt menu + tooltip na een UI-taalwissel."""

        try:
            self._icon.menu = self._build_menu()
            self._apply_icon_and_title()
            self._icon.update_menu()
        except Exception:
            pass

    def refresh_modules_menu(self) -> None:
        """Vernieuwt module-cascades in het tray-menu na wijziging van ingeschakelde modules."""

        try:
            self._icon.menu = self._build_menu()
            self._icon.update_menu()
        except Exception:
            pass

    @property
    def owns_main_thread(self) -> bool:
        """True op macOS: de menubalk moet de Cocoa-mainloop op de hoofdthread."""

        return sys.platform == "darwin"

    def _handle_module_action(self, module_id: str, action_id: str) -> None:
        if self._on_module_action is not None:
            self._on_module_action(module_id, action_id)

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

    def set_attention_needed(
        self,
        active: bool,
        *,
        tooltip_key: str = "tray.tooltip.attention_mic",
    ) -> None:
        """Toont een uitroepteken op het icoon zolang actie nodig is (bijv. microfoon)."""

        self._attention = active
        self._attention_tooltip_key = tooltip_key
        try:
            self._apply_icon_and_title()
        except Exception:
            pass

    def _tooltip_for(self) -> str:
        if self._attention:
            return i18n.t(self._attention_tooltip_key)
        return _tooltip(self._state)

    def _icon_for(self, state: RecordingState) -> Image.Image:
        base = self._icons.get(state, self._icons[RecordingState.IDLE])
        if self._attention:
            return _draw_attention_badge(base)
        return base

    def _apply_icon_and_title(self) -> None:
        self._icon.icon = self._icon_for(self._state)
        self._icon.title = self._tooltip_for()

    def set_state(self, state: RecordingState, mode: str = "toggle") -> None:
        self._state = state
        try:
            self._apply_icon_and_title()
        except Exception:
            pass
