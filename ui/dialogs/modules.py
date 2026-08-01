"""Qt Modules dialog — canvas frame #5a fidelity."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

import i18n
from chunk_transcription import normalize_chunk_mode
from modules._contract import module_actions
from modules.registry import all_builtin_modules, modules_config_for_settings
from ui.app import ensure_app
from ui.theme import TOKENS
from ui.widgets import FlowLayout, ToggleSwitch

_open_dialog: QDialog | None = None

_EXPERIMENTAL_IDS = frozenset({"meeting_buddy", "local_llm"})


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
        self.setMinimumSize(620, 520)
        self.resize(620, 640)
        self.setStyleSheet(
            f"QDialog {{ background: {TOKENS['surface']}; "
            f"border: 1px solid {TOKENS['border_dialog']}; }}"
        )
        self._settings = dict(current)
        self._on_apply = on_apply
        self._on_module_action = on_module_action
        self._get_enabled_module_ids = get_enabled_module_ids
        self._running_ids = set(enabled_module_ids or ())
        self._module_checks: dict[str, ToggleSwitch] = {}
        self._action_hosts: dict[str, QWidget] = {}
        self._action_layouts: dict[str, FlowLayout] = {}
        self._cards: dict[str, QFrame] = {}
        self._running_labels: dict[str, QLabel] = {}

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        body = QWidget()
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(20, 18, 20, 12)
        body_layout.setSpacing(14)

        intro = QLabel(i18n.t("modules.intro_short"))
        intro.setWordWrap(True)
        intro.setStyleSheet(f"color: {TOKENS['text_secondary']}; font-size: 12.5px;")
        body_layout.addWidget(intro)

        self._incremental_box = QFrame()
        self._incremental_box.setObjectName("incrementalBox")
        inc_outer = QVBoxLayout(self._incremental_box)
        inc_outer.setContentsMargins(12, 10, 12, 10)
        inc_outer.setSpacing(10)
        inc_layout = QHBoxLayout()
        inc_layout.setSpacing(9)
        self._incremental = ToggleSwitch()
        self._incremental.setChecked(bool(current.get("incremental_transcription", False)))
        self._incremental.toggled.connect(self._sync_incremental_style)
        inc_text = QVBoxLayout()
        inc_title = QLabel(i18n.t("modules.incremental_title"))
        inc_title.setStyleSheet("font-weight: 600; font-size: 13px;")
        inc_hint = QLabel(i18n.t("modules.incremental_hint"))
        inc_hint.setWordWrap(True)
        inc_hint.setStyleSheet(f"color: {TOKENS['muted']}; font-size: 12px;")
        inc_text.addWidget(inc_title)
        inc_text.addWidget(inc_hint)
        inc_layout.addLayout(inc_text, 1)
        inc_layout.addWidget(self._incremental, 0, Qt.AlignmentFlag.AlignTop)
        inc_outer.addLayout(inc_layout)

        opts = QHBoxLayout()
        opts.setSpacing(12)
        mode_col = QVBoxLayout()
        mode_col.setSpacing(4)
        mode_label = QLabel(i18n.t("modules.incremental_mode"))
        mode_label.setStyleSheet(f"color: {TOKENS['muted']}; font-size: 11.5px;")
        self._chunk_mode = QComboBox()
        for value, key in (
            ("hybrid", "modules.incremental_mode.hybrid"),
            ("fixed", "modules.incremental_mode.fixed"),
            ("vad", "modules.incremental_mode.vad"),
        ):
            self._chunk_mode.addItem(i18n.t(key), value)
        mode_idx = self._chunk_mode.findData(
            normalize_chunk_mode(current.get("incremental_chunk_mode", "hybrid"))
        )
        self._chunk_mode.setCurrentIndex(mode_idx if mode_idx >= 0 else 0)
        mode_col.addWidget(mode_label)
        mode_col.addWidget(self._chunk_mode)
        opts.addLayout(mode_col, 1)

        vad_col = QVBoxLayout()
        vad_col.setSpacing(4)
        vad_label = QLabel(i18n.t("modules.incremental_vad_ms"))
        vad_label.setStyleSheet(f"color: {TOKENS['muted']}; font-size: 11.5px;")
        self._vad_ms = QSpinBox()
        self._vad_ms.setRange(200, 10000)
        self._vad_ms.setSingleStep(100)
        self._vad_ms.setSuffix(" ms")
        try:
            self._vad_ms.setValue(max(200, int(current.get("incremental_vad_ms", 2000))))
        except (TypeError, ValueError):
            self._vad_ms.setValue(2000)
        vad_col.addWidget(vad_label)
        vad_col.addWidget(self._vad_ms)
        opts.addLayout(vad_col, 1)

        chunk_col = QVBoxLayout()
        chunk_col.setSpacing(4)
        chunk_label = QLabel(i18n.t("modules.incremental_chunk_seconds"))
        chunk_label.setStyleSheet(f"color: {TOKENS['muted']}; font-size: 11.5px;")
        self._chunk_seconds = QDoubleSpinBox()
        self._chunk_seconds.setRange(5.0, 600.0)
        self._chunk_seconds.setSingleStep(5.0)
        self._chunk_seconds.setDecimals(0)
        self._chunk_seconds.setSuffix(" s")
        try:
            self._chunk_seconds.setValue(
                max(5.0, float(current.get("incremental_chunk_seconds", 30.0)))
            )
        except (TypeError, ValueError):
            self._chunk_seconds.setValue(30.0)
        chunk_col.addWidget(chunk_label)
        chunk_col.addWidget(self._chunk_seconds)
        opts.addLayout(chunk_col, 1)
        inc_outer.addLayout(opts)

        seam = QLabel(i18n.t("modules.incremental_seam_note"))
        seam.setWordWrap(True)
        seam.setStyleSheet(f"color: {TOKENS['muted']}; font-size: 11.5px;")
        inc_outer.addWidget(seam)

        body_layout.addWidget(self._incremental_box)
        self._sync_incremental_style()

        heading = QLabel(i18n.t("modules.list_heading").upper())
        heading.setObjectName("sectionLabel")
        body_layout.addWidget(heading)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        # Clamp content to the viewport width so long descriptions wrap instead
        # of being clipped when the vertical scrollbar appears.
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet(f"QScrollArea {{ background: {TOKENS['surface']}; border: none; }}")
        cards = QWidget()
        # Scope to the host so the bare background does not cascade onto the
        # cards' primary action buttons (white-on-white = invisible label).
        cards.setObjectName("modulesCardsHost")
        cards.setStyleSheet(f"QWidget#modulesCardsHost {{ background: {TOKENS['surface']}; }}")
        self._cards_layout = QVBoxLayout(cards)
        self._cards_layout.setContentsMargins(0, 0, 0, 0)
        self._cards_layout.setSpacing(8)
        self._cards_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        modules_config = modules_config_for_settings(current.get("modules") or {})
        for module in all_builtin_modules():
            enabled = bool(
                modules_config.get(module.id, {}).get("enabled", module.default_enabled())
            )
            self._cards_layout.addWidget(self._module_card(module, enabled))
        scroll.setWidget(cards)
        body_layout.addWidget(scroll, 1)

        self._status = QLabel()
        self._status.setStyleSheet(f"color: {TOKENS['ok']}; font-size: 12px;")
        self._status.setWordWrap(True)
        body_layout.addWidget(self._status)

        outer.addWidget(body, 1)

        footer = QFrame()
        footer.setObjectName("dialogFooter")
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(16, 10, 16, 10)
        footer_layout.addStretch(1)
        self._close_button = QPushButton(i18n.t("modules.cancel"))
        self._close_button.setObjectName("ghost")
        save = QPushButton(i18n.t("modules.save"))
        save.setObjectName("primary")
        self._close_button.clicked.connect(self.reject)
        save.clicked.connect(self._save)
        footer_layout.addWidget(self._close_button)
        footer_layout.addWidget(save)
        outer.addWidget(footer)

    def _sync_incremental_style(self) -> None:
        on = self._incremental.isChecked()
        self._incremental_box.setObjectName("incrementalBoxOn" if on else "incrementalBox")
        self._incremental_box.style().unpolish(self._incremental_box)
        self._incremental_box.style().polish(self._incremental_box)
        self._chunk_mode.setEnabled(on)
        self._vad_ms.setEnabled(on)
        self._chunk_seconds.setEnabled(on)

    def _module_card(self, module: Any, enabled: bool) -> QFrame:
        card = QFrame()
        self._cards[module.id] = card
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(14, 12, 14, 12)
        card_layout.setSpacing(8)

        top = QHBoxLayout()
        top.setSpacing(12)
        left = QVBoxLayout()
        left.setSpacing(4)
        name_row = QHBoxLayout()
        name_row.setSpacing(8)
        title = QLabel(i18n.t(module.display_name_key()))
        title.setStyleSheet(
            f"font-weight: 600; font-size: 13px; color: {TOKENS['text_secondary']};"
        )
        name_row.addWidget(title)
        if module.id in _EXPERIMENTAL_IDS:
            badge = QLabel(i18n.t("modules.badge.experimental").upper())
            badge.setObjectName("badgeExperimental")
            name_row.addWidget(badge)
        running = QLabel()
        running.setObjectName("runningDot")
        self._running_labels[module.id] = running
        name_row.addWidget(running)
        name_row.addStretch(1)
        left.addLayout(name_row)
        description = QLabel(i18n.t(module.description_key()))
        description.setWordWrap(True)
        description.setStyleSheet(f"color: {TOKENS['muted']}; font-size: 12px;")
        left.addWidget(description)
        top.addLayout(left, 1)

        check = ToggleSwitch()
        check.setAccessibleName(i18n.t(module.display_name_key()))
        check.setChecked(enabled)
        check.toggled.connect(lambda _checked, mid=module.id: self._on_toggle(mid))
        self._module_checks[module.id] = check
        top.addWidget(check, 0, Qt.AlignmentFlag.AlignTop)
        card_layout.addLayout(top)

        actions_host = QWidget()
        actions_host.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
        # FlowLayout so the action row wraps to a second line (canvas M2) instead
        # of forcing the card — and the whole list — wider than the dialog.
        actions_layout = FlowLayout(actions_host, margin=0, hspacing=6, vspacing=6)
        self._action_hosts[module.id] = actions_host
        self._action_layouts[module.id] = actions_layout
        card_layout.addWidget(actions_host)

        self._apply_card_state(module.id)
        self._rebuild_actions(module)
        return card

    def _on_toggle(self, module_id: str) -> None:
        self._apply_card_state(module_id)

    def _apply_card_state(self, module_id: str) -> None:
        card = self._cards[module_id]
        enabled = self._module_checks[module_id].isChecked()
        running = module_id in self._running_ids and enabled
        card.setObjectName("moduleCardOn" if enabled else "moduleCardOff")
        card.style().unpolish(card)
        card.style().polish(card)
        label = self._running_labels[module_id]
        if running:
            label.setText("●  " + i18n.t("modules.running").lstrip("• ").strip())
            label.show()
        else:
            label.clear()
            label.hide()

    def _rebuild_actions(self, module: Any) -> None:
        layout = self._action_layouts[module.id]
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
            self._action_hosts[module.id].hide()
            return
        self._action_hosts[module.id].show()
        assert self._on_module_action is not None
        for index, action in enumerate(module_actions(module)):
            button = QPushButton(i18n.t(action.label_key))
            button.setObjectName("primary" if index == 0 else "secondary")
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
            "incremental_chunk_mode": normalize_chunk_mode(self._chunk_mode.currentData()),
            "incremental_vad_ms": int(self._vad_ms.value()),
            "incremental_chunk_seconds": float(self._chunk_seconds.value()),
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
            self._apply_card_state(module.id)
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
    # Ook de C++-widgetboom vrijgeven: de dialoog hangt onder de pill en bleef
    # anders tot app-exit bestaan (accumulatie bij herhaald openen).
    dialog.deleteLater()
