"""Qt system tray icon and a visible fallback for desktops without one."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PIL import Image, ImageDraw
from PySide6.QtCore import QPoint
from PySide6.QtGui import QAction, QIcon, QImage, QPixmap
from PySide6.QtWidgets import (
    QLabel,
    QMenu,
    QSystemTrayIcon,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

import i18n
from indicator import RecordingState
from modules._contract import ModuleAction, PraatMaarModule
from ui.app import ensure_app
from ui.theme import TOKENS

_STATE_COLORS: dict[RecordingState, tuple[int, int, int, int]] = {
    RecordingState.IDLE: (32, 33, 36, 255),
    RecordingState.RECORDING: (255, 82, 82, 255),
    RecordingState.TRANSCRIBING: (255, 176, 32, 255),
    RecordingState.CANCELLED: (154, 160, 166, 255),
    RecordingState.ERROR: (255, 82, 82, 255),
}
_TOOLTIP_KEYS: dict[RecordingState, str] = {
    RecordingState.IDLE: "tray.tooltip.idle",
    RecordingState.RECORDING: "tray.tooltip.recording",
    RecordingState.TRANSCRIBING: "tray.tooltip.transcribing",
    RecordingState.CANCELLED: "tray.tooltip.cancelled",
    RecordingState.ERROR: "tray.tooltip.error",
}
ICON_SIZE = 64
MenuEntry = tuple[Any, ...]
ModuleActionCallback = Callable[[str, str], Callable[[], None]]


def _group_module_actions(
    module_entries: list[tuple[PraatMaarModule, ModuleAction]],
) -> list[tuple[PraatMaarModule, list[ModuleAction]]]:
    by_module: dict[str, tuple[PraatMaarModule, list[ModuleAction]]] = {}
    for module, action in module_entries:
        by_module.setdefault(module.id, (module, []))[1].append(action)
    return list(by_module.values())


def _module_action_menu_entries(
    module: PraatMaarModule,
    actions: list[ModuleAction],
    module_action_callback: ModuleActionCallback,
) -> list[MenuEntry]:
    return [
        ("item", i18n.t(action.label_key), module_action_callback(module.id, action.id))
        for action in actions
    ]


def _module_tray_cascade_entries(
    module_entries: list[tuple[PraatMaarModule, ModuleAction]],
    module_action_callback: ModuleActionCallback,
) -> list[MenuEntry]:
    return [
        (
            "submenu",
            i18n.t(module.display_name_key()),
            _module_action_menu_entries(module, actions, module_action_callback),
        )
        for module, actions in _group_module_actions(module_entries)
    ]


def _module_tray_root_entries(
    root_entries: list[tuple[PraatMaarModule, ModuleAction]],
    module_action_callback: ModuleActionCallback,
) -> list[MenuEntry]:
    entries: list[MenuEntry] = []
    for module, actions in _group_module_actions(root_entries):
        if len(actions) == 1:
            action = actions[0]
            entries.append(
                ("item", i18n.t(action.label_key), module_action_callback(module.id, action.id))
            )
        else:
            entries.append(
                (
                    "submenu",
                    i18n.t(module.display_name_key()),
                    _module_action_menu_entries(module, actions, module_action_callback),
                )
            )
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
    """Build the shared tray and recording-pill context-menu model."""
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
    entries.extend(
        [
            ("item", i18n.t("tray.modules"), on_modules),
            ("item", i18n.t("tray.help"), on_help),
            ("separator",),
            ("item", i18n.t("tray.quit"), on_quit),
        ]
    )
    return entries


def _make_icon(color: tuple[int, int, int, int]) -> Image.Image:
    """Draw a microphone silhouette on a transparent Pillow image."""
    image = Image.new("RGBA", (ICON_SIZE, ICON_SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle([24, 8, 40, 38], radius=8, fill=color)
    draw.arc([16, 14, 48, 46], start=0, end=180, fill=color, width=5)
    draw.line([32, 46, 32, 54], fill=color, width=5)
    draw.line([23, 54, 41, 54], fill=color, width=5)
    return image


def _draw_attention_badge(base: Image.Image) -> Image.Image:
    """Add the attention-required badge without changing the source image."""
    image = base.copy()
    draw = ImageDraw.Draw(image)
    draw.ellipse([38, 38, 62, 62], fill=(255, 176, 32, 255))
    draw.rectangle([48, 43, 52, 52], fill=(255, 255, 255, 255))
    draw.rectangle([48, 55, 52, 58], fill=(255, 255, 255, 255))
    return image


def _tooltip(state: RecordingState) -> str:
    return i18n.t(_TOOLTIP_KEYS.get(state, "tray.tooltip.idle"))


def _to_qicon(image: Image.Image) -> QIcon:
    rgba = image.convert("RGBA")
    qimage = QImage(
        rgba.tobytes("raw", "RGBA"), rgba.width, rgba.height, QImage.Format.Format_RGBA8888
    ).copy()
    return QIcon(QPixmap.fromImage(qimage))


class TrayIcon:
    """System tray icon with a Qt window fallback if the desktop has no tray."""

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
        ensure_app()
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
        self._icons = {state: _make_icon(color) for state, color in _STATE_COLORS.items()}
        self._menu = self._build_menu()
        self._tray_available = QSystemTrayIcon.isSystemTrayAvailable()
        self._icon = QSystemTrayIcon(_to_qicon(self._icons[RecordingState.IDLE]))
        self._icon.setContextMenu(self._menu)
        self._fallback_window = None if self._tray_available else self._build_fallback_window()
        self._apply_icon_and_title()

    def _module_action_callback(self, module_id: str, action_id: str) -> Callable[[], None]:
        return lambda: self._handle_module_action(module_id, action_id)

    def context_menu_entries(self) -> list[MenuEntry]:
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

    def _build_menu(self) -> QMenu:
        def populate(menu: QMenu, entries: list[MenuEntry]) -> None:
            for entry in entries:
                if entry[0] == "separator":
                    menu.addSeparator()
                elif entry[0] == "item":
                    action = QAction(entry[1], menu)
                    action.triggered.connect(entry[2])
                    menu.addAction(action)
                else:
                    submenu = menu.addMenu(entry[1])
                    populate(submenu, entry[2])

        menu = QMenu()
        populate(menu, self.context_menu_entries())
        return menu

    def _build_fallback_window(self) -> QWidget:
        window = QWidget()
        window.setWindowTitle("praatMaar")
        window.setWindowIcon(_to_qicon(self._icons[RecordingState.IDLE]))
        layout = QVBoxLayout(window)
        label = QLabel("praatMaar")
        label.setStyleSheet(f"font-weight: 600; color: {TOKENS['text']};")
        button = QToolButton()
        button.setText(i18n.t("tray.settings"))
        button.setMenu(self._menu)
        button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        layout.addWidget(label)
        layout.addWidget(button)
        return window

    def popup_menu(self, x: int, y: int, *, tk_parent: Any | None = None) -> None:
        """Show the same menu used by the tray and fallback controls."""
        del tk_parent
        self._menu.popup(QPoint(int(x), int(y)))

    def refresh_language(self) -> None:
        self._replace_menu()
        self._apply_icon_and_title()

    def refresh_modules_menu(self) -> None:
        self._replace_menu()

    def _replace_menu(self) -> None:
        old_menu = self._menu
        self._menu = self._build_menu()
        self._icon.setContextMenu(self._menu)
        if self._fallback_window is not None:
            button = self._fallback_window.findChild(QToolButton)
            if button is not None:
                button.setMenu(self._menu)
        old_menu.deleteLater()

    def _handle_module_action(self, module_id: str, action_id: str) -> None:
        if self._on_module_action is not None:
            self._on_module_action(module_id, action_id)

    def start(self) -> None:
        if self._tray_available:
            self._icon.show()
        elif self._fallback_window is not None:
            self._fallback_window.show()

    def stop(self) -> None:
        self._icon.hide()
        if self._fallback_window is not None:
            self._fallback_window.close()

    def set_attention_needed(
        self, active: bool, *, tooltip_key: str = "tray.tooltip.attention_mic"
    ) -> None:
        self._attention = active
        self._attention_tooltip_key = tooltip_key
        self._apply_icon_and_title()

    def _tooltip_for(self) -> str:
        return i18n.t(self._attention_tooltip_key) if self._attention else _tooltip(self._state)

    def _icon_for(self, state: RecordingState) -> Image.Image:
        base = self._icons.get(state, self._icons[RecordingState.IDLE])
        return _draw_attention_badge(base) if self._attention else base

    def _apply_icon_and_title(self) -> None:
        self._icon.setIcon(_to_qicon(self._icon_for(self._state)))
        self._icon.setToolTip(self._tooltip_for())

    def set_state(self, state: RecordingState, mode: str = "toggle") -> None:
        del mode
        self._state = state
        self._apply_icon_and_title()
