"""Qt Meeting Buddy properties dialog: loopback output and transcript folder."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

import i18n
from ui.app import ensure_app

from .devices import list_loopback_output_devices
from .transcript_journal import transcripts_dir


@dataclass(frozen=True)
class PropertiesResult:
    enable_loopback: bool
    loopback_device: int | None
    transcripts_directory: str | None
    live_summary_enabled: bool = False
    llm_chunk_interval_s: float = 45.0
    llm_chunk_min_new_chars: int = 120


def device_selection_maps(
    devices: list[tuple[str, int | None]], loopback_device: int | None
) -> tuple[list[str], dict[str, int | None], dict[int | None, str], str]:
    labels = [label for label, _ in devices]
    values = {label: value for label, value in devices}
    labels_by_value = {value: label for label, value in devices}
    return (
        labels,
        values,
        labels_by_value,
        labels_by_value.get(loopback_device, labels[0] if labels else ""),
    )


def build_properties_result(
    *,
    enable_loopback: bool,
    selected_device_label: str,
    device_value_by_label: dict[str, int | None],
    fallback_device: int | None,
    transcripts_directory: str | None,
    live_summary_enabled: bool = False,
    llm_chunk_interval_s: float = 45.0,
    llm_chunk_min_new_chars: int = 120,
) -> PropertiesResult:
    return PropertiesResult(
        enable_loopback=enable_loopback,
        loopback_device=device_value_by_label.get(selected_device_label, fallback_device)
        if enable_loopback
        else None,
        transcripts_directory=transcripts_directory.strip()
        if transcripts_directory and transcripts_directory.strip()
        else None,
        live_summary_enabled=bool(live_summary_enabled),
        llm_chunk_interval_s=max(15.0, float(llm_chunk_interval_s)),
        llm_chunk_min_new_chars=max(50, int(llm_chunk_min_new_chars)),
    )


class _PropertiesDialog(QDialog):
    def __init__(
        self,
        *,
        enable_loopback: bool,
        loopback_device: int | None,
        transcripts_directory: str | None,
        live_summary_enabled: bool,
        llm_chunk_interval_s: float,
        llm_chunk_min_new_chars: int,
        app_dir: Path | None,
        parent: QWidget | None,
    ) -> None:
        super().__init__(parent)
        self._loopback_device = loopback_device
        devices = list_loopback_output_devices()
        labels, self._device_values, _, current = device_selection_maps(devices, loopback_device)
        self._result: PropertiesResult | None = None
        self.setWindowTitle(i18n.t("modules.meeting_buddy.dialog.title"))
        self.setMinimumWidth(480)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self._loopback = QCheckBox(i18n.t("modules.meeting_buddy.settings.enable_loopback"))
        self._loopback.setChecked(enable_loopback)
        form.addRow(self._loopback)
        self._device = QComboBox()
        self._device.addItems(labels)
        self._device.setCurrentText(current)
        form.addRow(i18n.t("modules.meeting_buddy.settings.loopback_output"), self._device)
        folder = QHBoxLayout()
        self._folder = QLineEdit(transcripts_directory or "")
        browse = QPushButton(i18n.t("modules.meeting_buddy.settings.transcripts_browse"))
        browse.clicked.connect(lambda: self._browse_folder(app_dir))
        folder.addWidget(self._folder, 1)
        folder.addWidget(browse)
        form.addRow(i18n.t("modules.meeting_buddy.settings.transcripts_directory"), folder)
        default_dir = (
            str(transcripts_dir(app_dir)) if app_dir is not None else "…/meeting-buddy/transcripts"
        )
        hint = QLabel(
            i18n.t("modules.meeting_buddy.settings.transcripts_directory_hint", path=default_dir)
        )
        hint.setWordWrap(True)
        form.addRow(hint)
        self._summary = QCheckBox(i18n.t("modules.meeting_buddy.settings.live_summary_enabled"))
        self._summary.setChecked(live_summary_enabled)
        form.addRow(self._summary)
        summary_hint = QLabel(i18n.t("modules.meeting_buddy.settings.live_summary_hint"))
        summary_hint.setWordWrap(True)
        form.addRow(summary_hint)
        self._interval = QLineEdit(str(int(llm_chunk_interval_s)))
        self._chars = QLineEdit(str(int(llm_chunk_min_new_chars)))
        form.addRow(i18n.t("modules.meeting_buddy.settings.llm_chunk_interval_s"), self._interval)
        form.addRow(i18n.t("modules.meeting_buddy.settings.llm_chunk_min_new_chars"), self._chars)
        layout.addLayout(form)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Save
        )
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self._confirm)
        layout.addWidget(buttons)
        self._loopback.toggled.connect(self._device.setEnabled)
        self._device.setEnabled(enable_loopback)

    @property
    def result(self) -> PropertiesResult | None:
        return self._result

    def _browse_folder(self, app_dir: Path | None) -> None:
        initial = self._folder.text().strip() or (str(transcripts_dir(app_dir)) if app_dir else "")
        chosen = QFileDialog.getExistingDirectory(
            self, i18n.t("modules.meeting_buddy.settings.transcripts_browse"), initial
        )
        if chosen:
            self._folder.setText(chosen)

    def _confirm(self) -> None:
        try:
            interval = float(self._interval.text().strip() or "60")
        except ValueError:
            interval = 60.0
        try:
            chars = int(self._chars.text().strip() or "200")
        except ValueError:
            chars = 200
        self._result = build_properties_result(
            enable_loopback=self._loopback.isChecked(),
            selected_device_label=self._device.currentText(),
            device_value_by_label=self._device_values,
            fallback_device=self._loopback_device,
            transcripts_directory=self._folder.text(),
            live_summary_enabled=self._summary.isChecked(),
            llm_chunk_interval_s=interval,
            llm_chunk_min_new_chars=chars,
        )
        self.accept()


def show_properties_dialog(
    *,
    enable_loopback: bool,
    loopback_device: int | None,
    transcripts_directory: str | None = None,
    live_summary_enabled: bool = False,
    llm_chunk_interval_s: float = 45.0,
    llm_chunk_min_new_chars: int = 120,
    app_dir: Path | None = None,
    parent: Any = None,
) -> PropertiesResult | None:
    """Show loopback + transcript folder settings; return ``None`` on cancel."""
    ensure_app()
    dialog = _PropertiesDialog(
        enable_loopback=enable_loopback,
        loopback_device=loopback_device,
        transcripts_directory=transcripts_directory,
        live_summary_enabled=live_summary_enabled,
        llm_chunk_interval_s=llm_chunk_interval_s,
        llm_chunk_min_new_chars=llm_chunk_min_new_chars,
        app_dir=app_dir,
        parent=parent if isinstance(parent, QWidget) else None,
    )
    dialog.exec()
    return dialog.result
