"""Tray context menu: module actions as root cascades."""

from __future__ import annotations

import i18n
from modules._contract import ModuleAction
from tray import TrayIcon, build_context_menu_entries


class TrayModule:
    id: str
    _name_key: str

    def __init__(self, module_id: str, name_key: str) -> None:
        self.id = module_id
        self._name_key = name_key

    def display_name_key(self) -> str:
        return self._name_key


def _noop() -> None:
    pass


def _find_submenu(entries: list[tuple], label: str) -> tuple | None:
    for entry in entries:
        if entry[0] == "submenu" and entry[1] == label:
            return entry
    return None


def _find_item(entries: list[tuple], label: str) -> tuple | None:
    for entry in entries:
        if entry[0] == "item" and entry[1] == label:
            return entry
    return None


def test_in_tray_actions_appear_as_root_cascade() -> None:
    i18n.set_ui_language("en")
    module = TrayModule("meeting-buddy", "modules.meeting_buddy.name")
    actions = [
        ModuleAction(
            id="start_meeting",
            label_key="modules.meeting_buddy.actions.start",
            handler=_noop,
            in_tray=True,
        ),
        ModuleAction(
            id="stop_meeting",
            label_key="modules.meeting_buddy.actions.stop",
            handler=_noop,
            in_tray=True,
        ),
    ]
    on_modules = _noop
    entries = build_context_menu_entries(
        on_settings=_noop,
        on_destinations=_noop,
        on_modules=on_modules,
        on_help=_noop,
        on_quit=_noop,
        module_tray_actions=[(module, action) for action in actions],
        module_tray_root_actions=[],
        module_action_callback=lambda module_id, action_id: _noop,
    )

    cascade = _find_submenu(entries, i18n.t("modules.meeting_buddy.name"))
    assert cascade is not None
    children = cascade[2]
    assert len(children) == 2
    assert all(child[0] == "item" for child in children)

    modules_entry = _find_item(entries, i18n.t("tray.modules"))
    assert modules_entry is not None
    assert modules_entry[2] is on_modules

    modules_submenu = _find_submenu(entries, i18n.t("tray.modules"))
    assert modules_submenu is None


def test_modules_entry_is_not_submenu_with_actions() -> None:
    i18n.set_ui_language("en")
    module = TrayModule("meeting-buddy", "modules.meeting_buddy.name")
    action = ModuleAction(
        id="start_meeting",
        label_key="modules.meeting_buddy.actions.start",
        handler=_noop,
        in_tray=True,
    )
    tray = TrayIcon(
        on_quit=_noop,
        on_settings=_noop,
        on_destinations=_noop,
        on_modules=_noop,
        on_help=_noop,
        get_module_tray_actions=lambda: [(module, action)],
        get_module_tray_root_actions=lambda: [],
    )
    entries = tray.context_menu_entries()

    assert _find_submenu(entries, i18n.t("modules.meeting_buddy.name")) is not None
    assert _find_submenu(entries, i18n.t("tray.modules")) is None


def test_single_in_tray_root_action_stays_flat() -> None:
    i18n.set_ui_language("en")
    module = TrayModule("demo", "modules.demo.name")
    action = ModuleAction(
        id="root",
        label_key="modules.demo.root",
        handler=_noop,
        in_tray_root=True,
    )
    entries = build_context_menu_entries(
        on_settings=_noop,
        on_destinations=_noop,
        on_modules=_noop,
        on_help=_noop,
        on_quit=_noop,
        module_tray_actions=[],
        module_tray_root_actions=[(module, action)],
        module_action_callback=lambda module_id, action_id: _noop,
    )

    root_item = _find_item(entries, i18n.t("modules.demo.root"))
    assert root_item is not None
    assert _find_submenu(entries, i18n.t("modules.demo.name")) is None


def test_multiple_in_tray_root_actions_group_into_submenu() -> None:
    i18n.set_ui_language("en")
    module = TrayModule("demo", "modules.demo.name")
    actions = [
        ModuleAction(
            id="root_a",
            label_key="modules.demo.root_a",
            handler=_noop,
            in_tray_root=True,
        ),
        ModuleAction(
            id="root_b",
            label_key="modules.demo.root_b",
            handler=_noop,
            in_tray_root=True,
        ),
    ]
    entries = build_context_menu_entries(
        on_settings=_noop,
        on_destinations=_noop,
        on_modules=_noop,
        on_help=_noop,
        on_quit=_noop,
        module_tray_actions=[],
        module_tray_root_actions=[(module, action) for action in actions],
        module_action_callback=lambda module_id, action_id: _noop,
    )

    cascade = _find_submenu(entries, i18n.t("modules.demo.name"))
    assert cascade is not None
    assert len(cascade[2]) == 2


def test_menu_order_with_module_cascade() -> None:
    i18n.set_ui_language("en")
    module = TrayModule("meeting-buddy", "modules.meeting_buddy.name")
    action = ModuleAction(
        id="start_meeting",
        label_key="modules.meeting_buddy.actions.start",
        handler=_noop,
        in_tray=True,
    )
    on_settings = _noop
    on_destinations = _noop
    on_modules = _noop
    on_help = _noop
    on_quit = _noop
    entries = build_context_menu_entries(
        on_settings=on_settings,
        on_destinations=on_destinations,
        on_modules=on_modules,
        on_help=on_help,
        on_quit=on_quit,
        module_tray_actions=[(module, action)],
        module_tray_root_actions=[],
        module_action_callback=lambda module_id, action_id: _noop,
    )

    labels = [entry[1] for entry in entries if entry[0] in {"item", "submenu"}]
    assert labels.index(i18n.t("tray.settings")) < labels.index(
        i18n.t("modules.meeting_buddy.name")
    )
    assert labels.index(i18n.t("modules.meeting_buddy.name")) < labels.index(i18n.t("tray.modules"))
    assert labels.index(i18n.t("tray.modules")) < labels.index(i18n.t("tray.help"))
    assert labels.index(i18n.t("tray.help")) < labels.index(i18n.t("tray.quit"))
