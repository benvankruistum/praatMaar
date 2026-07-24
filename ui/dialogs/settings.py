"""Qt implementation of praatMaar's settings dialog."""

from __future__ import annotations

import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMessageBox,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

import destinations
import hotkeys
import i18n
import recovery
from ui.app import ensure_app
from ui.marshal import ui_dispatch
from ui.theme import TOKENS

MODELS = ["base", "small", "medium"]
_open_dialog: QDialog | None = None


def _positions() -> list[tuple[str, str]]:
    return [
        (i18n.t("settings.position.top"), "boven-midden"),
        (i18n.t("settings.position.bottom"), "onder-midden"),
        (i18n.t("settings.position.last"), "laatst-geplaatst"),
    ]


def _modes() -> list[tuple[str, str]]:
    return [(i18n.t("settings.mode.toggle"), "toggle"), (i18n.t("settings.mode.ptt"), "ptt")]


def _language_choices() -> list[tuple[str, str]]:
    return [(i18n.LANGUAGE_LABELS[code], code) for code in i18n.SUPPORTED_UI_LANGUAGES]


def _input_devices() -> list[tuple[str, int | None]]:
    """Return input device labels and indices, including the system default."""
    options: list[tuple[str, int | None]] = [(i18n.t("settings.mic.default"), None)]
    try:
        import sounddevice as sd

        for index, device in enumerate(sd.query_devices()):
            if device.get("max_input_channels", 0) > 0:
                options.append((f"{index}: {device['name']}", index))
    except Exception:
        pass
    return options


def _dialog_parent(parent: Any) -> QWidget | None:
    return parent if isinstance(parent, QWidget) else None


def _combo(items: list[tuple[str, Any]], selected: Any) -> QComboBox:
    combo = QComboBox()
    for label, value in items:
        combo.addItem(label, value)
    index = combo.findData(selected)
    combo.setCurrentIndex(index if index >= 0 else 0)
    return combo


class SettingsDialog(QDialog):
    """Settings dialog with general, language, and recovery-audio tabs."""

    def __init__(
        self,
        parent: QWidget | None,
        current: dict[str, Any],
        on_apply: Callable[[dict[str, Any]], None],
        set_capture: Callable[[Any | None], None] | None,
        on_retranscribe: Callable[[Path], str] | None,
        on_parent_retranscribe: Callable[[Path], None] | None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(i18n.t("settings.title"))
        self.setMinimumWidth(540)
        self._current = current
        self._on_apply = on_apply
        self._set_capture = set_capture
        self._on_retranscribe = on_retranscribe
        self._on_parent_retranscribe = on_parent_retranscribe
        self._capture_active = False
        self._capture_pressed: set[str] = set()
        self._capture_best: set[str] = set()
        self._hotkey_tokens = list(current.get("hotkey") or hotkeys.DEFAULT_HOTKEY)
        self._recovery_paths: list[Path] = []

        layout = QVBoxLayout(self)
        tabs = QTabWidget()
        self._general_tab = QWidget()
        self._language_tab = QWidget()
        self._advanced_tab = QWidget()
        tabs.addTab(self._general_tab, i18n.t("settings.tab.general"))
        tabs.addTab(self._language_tab, i18n.t("settings.tab.language"))
        tabs.addTab(self._advanced_tab, i18n.t("settings.tab.advanced"))
        self._build_general()
        self._build_language()
        self._build_advanced()
        layout.addWidget(tabs)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
        save = buttons.addButton(i18n.t("settings.save"), QDialogButtonBox.ButtonRole.AcceptRole)
        save.setObjectName("primary")
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self._save)
        layout.addWidget(buttons)

    def _build_general(self) -> None:
        form = QFormLayout(self._general_tab)
        devices = _input_devices()
        self._devices = devices
        self.mic = _combo(devices, self._current.get("microphone_device"))
        self.position = _combo(_positions(), self._current.get("indicator_position"))
        self.mode = _combo(_modes(), self._current.get("mode"))
        form.addRow(i18n.t("settings.microphone"), self.mic)
        form.addRow(i18n.t("settings.indicator_position"), self.position)
        form.addRow(i18n.t("settings.mode"), self.mode)
        self.hotkey_label = QLabel(hotkeys.format_hotkey(self._hotkey_tokens))
        self.hotkey_label.setStyleSheet(f"border: 1px solid {TOKENS['border']}; padding: 6px;")
        self.capture_button = QPushButton(i18n.t("settings.hotkey.record"))
        self.capture_button.clicked.connect(self._toggle_capture)
        hotkey_row = QHBoxLayout()
        hotkey_row.addWidget(self.hotkey_label, 1)
        hotkey_row.addWidget(self.capture_button)
        form.addRow(i18n.t("settings.hotkey"), hotkey_row)
        self.autostart = QCheckBox(i18n.t("settings.autostart"))
        self.auto_paste = QCheckBox(i18n.t("settings.auto_paste"))
        self.warm_microphone = QCheckBox(i18n.t("settings.warm_microphone"))
        self.autostart.setChecked(bool(self._current.get("autostart", False)))
        self.auto_paste.setChecked(bool(self._current.get("auto_paste", True)))
        self.warm_microphone.setChecked(bool(self._current.get("warm_microphone", False)))
        form.addRow("", self.autostart)
        form.addRow("", self.auto_paste)
        form.addRow("", self.warm_microphone)

    def _build_language(self) -> None:
        form = QFormLayout(self._language_tab)
        choices = _language_choices()
        speech = i18n.normalize_language(
            self._current.get("speech_language"), allowed=i18n.SUPPORTED_SPEECH_LANGUAGES
        )
        ui = i18n.normalize_language(
            self._current.get("ui_language"), allowed=i18n.SUPPORTED_UI_LANGUAGES
        )
        self.speech_language = _combo(choices, speech)
        self.ui_language = _combo(choices, ui)
        form.addRow(i18n.t("settings.speech_language"), self.speech_language)
        form.addRow(i18n.t("settings.ui_language"), self.ui_language)

    def _build_advanced(self) -> None:
        layout = QVBoxLayout(self._advanced_tab)
        form = QFormLayout()
        self.model = _combo(
            [(model, model) for model in MODELS], str(self._current.get("model", "small"))
        )
        form.addRow(i18n.t("settings.model"), self.model)
        layout.addLayout(form)
        restart = QLabel(i18n.t("settings.model.restart"))
        restart.setStyleSheet(f"color: {TOKENS['muted']};")
        layout.addWidget(restart)
        layout.addWidget(QLabel(i18n.t("recovery.section").upper()))
        self.recovery_list = QListWidget()
        self.recovery_list.setMinimumHeight(120)
        layout.addWidget(self.recovery_list)
        self.recovery_empty = QLabel()
        self.recovery_empty.setStyleSheet(f"color: {TOKENS['muted']};")
        layout.addWidget(self.recovery_empty)
        self.recovery_status = QLabel()
        layout.addWidget(self.recovery_status)
        actions = QHBoxLayout()
        open_folder = QPushButton(i18n.t("recovery.open_folder"))
        delete = QPushButton(i18n.t("recovery.delete"))
        delete_all = QPushButton(i18n.t("recovery.delete_all"))
        retranscribe = QPushButton(i18n.t("recovery.retranscribe"))
        open_folder.clicked.connect(self._open_recovery_folder)
        delete.clicked.connect(self._delete_selected)
        delete_all.clicked.connect(self._delete_all)
        retranscribe.clicked.connect(self._retranscribe_selected)
        for button in (open_folder, delete, delete_all, retranscribe):
            actions.addWidget(button)
        layout.addLayout(actions)
        self._refresh_recovery()

    def _toggle_capture(self) -> None:
        if self._capture_active:
            self._stop_capture(confirm=True)
            return
        self._capture_active = True
        self._capture_pressed.clear()
        self._capture_best.clear()
        self.hotkey_label.setText(i18n.t("settings.hotkey.press"))
        self.capture_button.setText(i18n.t("settings.hotkey.use"))
        self._set_capture(self._capture_callback)
        self.setFocus(Qt.FocusReason.ActiveWindowFocusReason)

    def _capture_callback(self, event: str, key: Any) -> None:
        token = hotkeys.key_to_token(key)
        if token is not None:
            self._capture_token(event, token)

    def _capture_token(self, event: str, token: str) -> None:
        if event == "press":
            self._capture_pressed.add(token)
            if len(self._capture_pressed) >= len(self._capture_best):
                self._capture_best = set(self._capture_pressed)
        else:
            self._capture_pressed.discard(token)
        visible = self._capture_best or self._capture_pressed
        if visible:
            self.hotkey_label.setText(hotkeys.format_hotkey(visible))

    def keyPressEvent(self, event: Any) -> None:
        if self._capture_active:
            modifiers = event.modifiers()
            for flag, token in (
                (Qt.KeyboardModifier.ControlModifier, "ctrl"),
                (Qt.KeyboardModifier.ShiftModifier, "shift"),
                (Qt.KeyboardModifier.AltModifier, "alt"),
                (Qt.KeyboardModifier.MetaModifier, "cmd"),
            ):
                if modifiers & flag:
                    self._capture_token("press", token)
            token = hotkeys.qt_key_to_token(event.key(), event.text())
            if token is not None:
                self._capture_token("press", token)
            event.accept()
            return
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event: Any) -> None:
        if self._capture_active:
            token = hotkeys.qt_key_to_token(event.key(), event.text())
            if token is not None:
                self._capture_token("release", token)
            event.accept()
            return
        super().keyReleaseEvent(event)

    def _stop_capture(self, *, confirm: bool) -> None:
        if not self._capture_active:
            return
        self._capture_active = False
        if self._set_capture is not None:
            self._set_capture(None)
        if confirm and self._capture_best:
            normalized = hotkeys.normalize(self._capture_best)
            if any(token not in hotkeys.MODIFIER_TOKENS for token in normalized):
                self._hotkey_tokens = normalized
        self.hotkey_label.setText(hotkeys.format_hotkey(self._hotkey_tokens))
        self.capture_button.setText(i18n.t("settings.hotkey.record"))

    def _refresh_recovery(self) -> None:
        self._recovery_paths = recovery.list_recovery_wavs()
        self.recovery_list.clear()
        self.recovery_list.addItems(
            [recovery.recovery_list_label(path) for path in self._recovery_paths]
        )
        self.recovery_empty.setText("" if self._recovery_paths else i18n.t("recovery.empty"))

    def _selected_recovery(self) -> Path | None:
        index = self.recovery_list.currentRow()
        return self._recovery_paths[index] if 0 <= index < len(self._recovery_paths) else None

    def _open_recovery_folder(self) -> None:
        try:
            destinations.open_in_explorer(recovery.recovery_dir())
        except OSError as exc:
            QMessageBox.critical(self, i18n.t("settings.title"), str(exc))

    def _delete_selected(self) -> None:
        path = self._selected_recovery()
        if path is None:
            QMessageBox.information(self, i18n.t("settings.title"), i18n.t("recovery.select_first"))
            return
        if (
            QMessageBox.question(
                self, i18n.t("settings.title"), i18n.t("recovery.confirm_delete", name=path.name)
            )
            != QMessageBox.StandardButton.Yes
        ):
            return
        try:
            recovery.delete_recovery_file(path)
        except (OSError, ValueError) as exc:
            QMessageBox.critical(self, i18n.t("settings.title"), str(exc))
        self._refresh_recovery()

    def _delete_all(self) -> None:
        if not self._recovery_paths:
            QMessageBox.information(self, i18n.t("settings.title"), i18n.t("recovery.empty"))
            return
        if (
            QMessageBox.question(
                self,
                i18n.t("settings.title"),
                i18n.t("recovery.confirm_delete_all", count=len(self._recovery_paths)),
            )
            == QMessageBox.StandardButton.Yes
        ):
            recovery.delete_all_recovery_files()
            self._refresh_recovery()

    def _retranscribe_selected(self) -> None:
        path = self._selected_recovery()
        if path is None:
            QMessageBox.information(self, i18n.t("settings.title"), i18n.t("recovery.select_first"))
            return
        if self._on_parent_retranscribe is not None:
            self._on_parent_retranscribe(path)
            self.reject()
            return
        if self._on_retranscribe is None:
            QMessageBox.information(self, i18n.t("settings.title"), i18n.t("recovery.unavailable"))
            return
        self.recovery_status.setText(i18n.t("recovery.busy_status"))

        def worker() -> None:
            error: str | None = None
            try:
                self._on_retranscribe(path)
            except Exception as exc:
                error = str(exc)

            def done() -> None:
                self.recovery_status.clear()
                if error is not None:
                    QMessageBox.critical(self, i18n.t("settings.title"), error)
                    return
                if (
                    path.exists()
                    and QMessageBox.question(
                        self,
                        i18n.t("settings.title"),
                        i18n.t("recovery.ask_delete_after", name=path.name),
                    )
                    == QMessageBox.StandardButton.Yes
                ):
                    recovery.delete_recovery_file(path)
                self._refresh_recovery()

            ui_dispatch(done)

        threading.Thread(target=worker, daemon=True).start()

    def _save(self) -> None:
        self._stop_capture(confirm=True)
        self._on_apply(
            {
                "microphone_device": self.mic.currentData(),
                "indicator_position": self.position.currentData(),
                "mode": self.mode.currentData(),
                "hotkey": list(self._hotkey_tokens),
                "autostart": self.autostart.isChecked(),
                "auto_paste": self.auto_paste.isChecked(),
                "warm_microphone": self.warm_microphone.isChecked(),
                "model": self.model.currentData(),
                "speech_language": self.speech_language.currentData(),
                "ui_language": self.ui_language.currentData(),
            }
        )
        self.accept()

    def reject(self) -> None:
        self._stop_capture(confirm=False)
        super().reject()


def open_settings_dialog(
    root: Any,
    current: dict[str, Any],
    on_apply: Callable[[dict[str, Any]], None],
    set_capture: Callable[[Any | None], None] | None = None,
    *,
    wait: bool = False,
    use_tk_capture: bool = False,
    on_retranscribe: Callable[[Path], str] | None = None,
    on_parent_retranscribe: Callable[[Path], None] | None = None,
) -> None:
    """Open the singleton settings dialog; Tk-only capture is intentionally ignored."""
    del use_tk_capture
    global _open_dialog
    ensure_app()
    if _open_dialog is not None:
        _open_dialog.raise_()
        _open_dialog.activateWindow()
        if wait:
            _open_dialog.exec()
        return
    dialog = SettingsDialog(
        _dialog_parent(root),
        current,
        on_apply,
        set_capture,
        on_retranscribe,
        on_parent_retranscribe,
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
