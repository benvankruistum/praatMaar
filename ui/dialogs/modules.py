"""Qt implementation of the built-in modules dialog."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

import i18n
from modules._contract import module_actions
from modules.registry import all_builtin_modules, modules_config_for_settings
from ui.app import ensure_app
from ui.theme import TOKENS

_open_dialog: QDialog | None = None


def module_shows_action_buttons(
    module_id: str,
    *,
    has_actions: bool,
    on_module_action: Callable[[str, str], None] | None,
    enabled_module_ids: set[str],
) -> bool:
    """Return whether action buttons should appear for ``module_id``."""
    return has_actions and on_module_action is not None and module_id in enabled_module_ids


def _dialog_parent(parent: Any) -> QWidget | None:
    return parent if isinstance(parent, QWidget) else None


def _enabled_module_ids_from_settings(settings: dict[str, Any]) -> set[str]:
    modules = settings.get("modules") or {}
    return {module_id for module_id, cfg in modules.items() if cfg.get("enabled")}


class ModulesDialog(QDialog):
    """Editable module configuration that remains open after saving."""

    def __init__(
        self,
        parent: QWidget | None,
        current: dict[str, Any],
        on_apply: Callable[[dict[str, Any]], None],
        *,
        on_module_action: Callable[[str, str], None] | None,
        enabled_module_ids: set[str] | None,
        get_enabled_module_ids: Callable[[], set[str]] | None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(i18n.t("modules.title"))
        self.setMinimumSize(560, 420)
        self._settings = dict(current)
        self._on_apply = on_apply
        self._on_module_action = on_module_action
        self._get_enabled_module_ids = get_enabled_module_ids
        self._running_ids = set(enabled_module_ids or ())
        self._module_checks: dict[str, QCheckBox] = {}
        self._action_hosts: dict[str, QHBoxLayout] = {}

        outer = QVBoxLayout(self)
        header = QFrame()
        header.setStyleSheet(
            f"background: {TOKENS['surface']}; border: 1px solid {TOKENS['border']};"
        )
        header_layout = QVBoxLayout(header)
        intro = QLabel(i18n.t("modules.intro_short"))
        intro.setWordWrap(True)
        header_layout.addWidget(intro)
        self._incremental = QCheckBox(i18n.t("modules.incremental_title"))
        self._incremental.setChecked(bool(current.get("incremental_transcription", False)))
        header_layout.addWidget(self._incremental)
        hint = QLabel(i18n.t("modules.incremental_hint"))
        hint.setWordWrap(True)
        hint.setStyleSheet(f"color: {TOKENS['muted']};")
        header_layout.addWidget(hint)
        outer.addWidget(header)

        heading = QLabel(i18n.t("modules.list_heading").upper())
        heading.setStyleSheet(f"font-weight: 600; color: {TOKENS['muted']};")
        outer.addWidget(heading)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        cards = QWidget()
        cards_layout = QVBoxLayout(cards)
        cards_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        modules_config = modules_config_for_settings(current.get("modules") or {})
        for module in all_builtin_modules():
            enabled = bool(
                modules_config.get(module.id, {}).get("enabled", module.default_enabled())
            )
            cards_layout.addWidget(self._module_card(module, enabled))
        scroll.setWidget(cards)
        outer.addWidget(scroll, 1)

        self._status = QLabel()
        self._status.setStyleSheet(f"color: {TOKENS['ok']};")
        outer.addWidget(self._status)
        buttons = QDialogButtonBox()
        self._close_button = buttons.addButton(
            i18n.t("modules.cancel"), QDialogButtonBox.ButtonRole.RejectRole
        )
        save = buttons.addButton(i18n.t("modules.save"), QDialogButtonBox.ButtonRole.AcceptRole)
        save.setObjectName("primary")
        self._close_button.clicked.connect(self.reject)
        save.clicked.connect(self._save)
        outer.addWidget(buttons)

    def _module_card(self, module: Any, enabled: bool) -> QFrame:
        card = QFrame()
        card.setFrameShape(QFrame.Shape.StyledPanel)
        card.setStyleSheet(
            f"QFrame {{ background: {TOKENS['surface']}; border: 1px solid {TOKENS['border']};"
            " border-radius: 6px; }"
        )
        layout = QVBoxLayout(card)
        title_row = QHBoxLayout()
        title = QLabel(i18n.t(module.display_name_key()))
        title.setStyleSheet("font-weight: 600;")
        title_row.addWidget(title)
        title_row.addStretch()
        check = QCheckBox()
        check.setAccessibleName(i18n.t(module.display_name_key()))
        check.setChecked(enabled)
        self._module_checks[module.id] = check
        title_row.addWidget(check)
        layout.addLayout(title_row)
        description = QLabel(i18n.t(module.description_key()))
        description.setWordWrap(True)
        description.setStyleSheet(f"color: {TOKENS['muted']};")
        layout.addWidget(description)
        actions_layout = QHBoxLayout()
        actions_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self._action_hosts[module.id] = actions_layout
        layout.addLayout(actions_layout)
        self._rebuild_actions(module)
        return card

    def _rebuild_actions(self, module: Any) -> None:
        layout = self._action_hosts[module.id]
        while layout.count():
            item = layout.takeAt(0)
            if item.widget() is not None:
                item.widget().deleteLater()
        if not module_shows_action_buttons(
            module.id,
            has_actions=bool(module_actions(module)),
            on_module_action=self._on_module_action,
            enabled_module_ids=self._running_ids,
        ):
            return
        assert self._on_module_action is not None
        for index, action in enumerate(module_actions(module)):
            button = QPushButton(i18n.t(action.label_key))
            if index == 0:
                button.setObjectName("primary")
            button.clicked.connect(
                lambda _checked=False, mid=module.id, aid=action.id: self._on_module_action(
                    mid, aid
                )
            )
            layout.addWidget(button)

    def _save(self) -> None:
        updated = {
            **self._settings,
            "incremental_transcription": self._incremental.isChecked(),
            "modules": {
                module_id: {"enabled": check.isChecked()}
                for module_id, check in self._module_checks.items()
            },
        }
        self._on_apply(updated)
        self._settings = updated
        self._running_ids = (
            self._get_enabled_module_ids()
            if self._get_enabled_module_ids is not None
            else _enabled_module_ids_from_settings(updated)
        )
        for module in all_builtin_modules():
            self._rebuild_actions(module)
        self._status.setText(i18n.t("modules.saved_actions_ready"))
        self._close_button.setText(i18n.t("modules.close"))


def open_modules_dialog(
    parent: Any,
    current: dict[str, Any],
    on_apply: Callable[[dict[str, Any]], None],
    *,
    wait: bool = False,
    on_module_action: Callable[[str, str], None] | None = None,
    enabled_module_ids: set[str] | None = None,
    get_enabled_module_ids: Callable[[], set[str]] | None = None,
) -> None:
    """Open the singleton module settings dialog."""
    global _open_dialog
    ensure_app()
    if _open_dialog is not None:
        _open_dialog.raise_()
        _open_dialog.activateWindow()
        if wait:
            _open_dialog.exec()
        return
    dialog = ModulesDialog(
        _dialog_parent(parent),
        current,
        on_apply,
        on_module_action=on_module_action,
        enabled_module_ids=enabled_module_ids,
        get_enabled_module_ids=get_enabled_module_ids,
    )
    _open_dialog = dialog
    dialog.finished.connect(lambda _result: _clear_open_dialog(dialog))
    if wait:
        dialog.exec()
    else:
        dialog.show()


def _clear_open_dialog(dialog: QDialog) -> None:
    global _open_dialog
    if _open_dialog is dialog:
        _open_dialog = None
