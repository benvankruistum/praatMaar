"""Qt Meeting Buddy properties dialog: loopback output and transcript folder."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

import i18n
from ui.app import ensure_app
from ui.theme import TOKENS
from ui.widgets import ToggleSwitch

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
        self.setWindowTitle(i18n.t("modules.meeting_buddy.dialog.properties_title"))
        self.setMinimumWidth(620)
        self.setStyleSheet(
            f"QDialog {{ background: {TOKENS['surface']}; "
            f"border: 1px solid {TOKENS['border_dialog']}; }}"
        )

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        body = QWidget()
        col = QVBoxLayout(body)
        col.setContentsMargins(18, 16, 18, 18)
        col.setSpacing(0)

        # --- Audio ---
        col.addWidget(self._section(i18n.t("modules.meeting_buddy.settings.section.audio")))
        self._loopback = ToggleSwitch()
        self._loopback.setChecked(enable_loopback)
        col.addLayout(
            self._toggle_row(
                i18n.t("modules.meeting_buddy.settings.loopback_title"),
                i18n.t("modules.meeting_buddy.settings.loopback_desc"),
                self._loopback,
            )
        )
        self._device = QComboBox()
        self._device.addItems(labels)
        self._device.setCurrentText(current)
        col.addLayout(
            self._field_row(i18n.t("modules.meeting_buddy.settings.output_device"), self._device)
        )

        # --- Opslag ---
        col.addWidget(
            self._section(i18n.t("modules.meeting_buddy.settings.section.storage"), top=True)
        )
        self._folder = QLineEdit(transcripts_directory or "")
        browse = QPushButton(i18n.t("modules.meeting_buddy.settings.transcripts_browse"))
        browse.setObjectName("secondary")
        browse.clicked.connect(lambda: self._browse_folder(app_dir))
        col.addLayout(
            self._field_row(
                i18n.t("modules.meeting_buddy.settings.transcript_label"),
                self._folder,
                trailing=browse,
            )
        )

        # --- Samenvatting ---
        col.addWidget(
            self._section(i18n.t("modules.meeting_buddy.settings.section.summary"), top=True)
        )
        self._summary = ToggleSwitch()
        self._summary.setChecked(live_summary_enabled)
        col.addLayout(
            self._toggle_row(
                i18n.t("modules.meeting_buddy.settings.live_summary_enabled"),
                i18n.t("modules.meeting_buddy.settings.live_summary_hint"),
                self._summary,
            )
        )
        self._interval = QLineEdit(str(int(llm_chunk_interval_s)))
        self._interval.setFixedWidth(72)
        self._chars = QLineEdit(str(int(llm_chunk_min_new_chars)))
        self._chars.setFixedWidth(88)
        col.addLayout(self._interval_row())

        # --- Privacy-banner ---
        banner = QFrame()
        banner.setObjectName("successBanner")
        banner_row = QHBoxLayout(banner)
        banner_row.setContentsMargins(11, 9, 11, 9)
        banner_row.setSpacing(9)
        check = QLabel("✓")
        check.setStyleSheet(
            f"background: {TOKENS['ok']}; color: white; font-size: 9px; font-weight: 700;"
            " border-radius: 7px; min-width: 14px; max-width: 14px; min-height: 14px;"
            " max-height: 14px;"
        )
        check.setAlignment(Qt.AlignmentFlag.AlignCenter)
        note = QLabel(i18n.t("modules.meeting_buddy.settings.privacy_note"))
        note.setObjectName("successText")
        note.setWordWrap(True)
        banner_row.addWidget(check, 0, Qt.AlignmentFlag.AlignTop)
        banner_row.addWidget(note, 1)
        col.addSpacing(14)
        col.addWidget(banner)

        outer.addWidget(body, 1)

        footer = QFrame()
        footer.setObjectName("dialogFooter")
        footer_row = QHBoxLayout(footer)
        footer_row.setContentsMargins(18, 12, 18, 12)
        footer_row.addStretch(1)
        cancel = QPushButton(i18n.t("modules.meeting_buddy.dialog.cancel"))
        cancel.setObjectName("ghost")
        cancel.clicked.connect(self.reject)
        save = QPushButton(i18n.t("modules.meeting_buddy.dialog.save"))
        save.setObjectName("primary")
        save.clicked.connect(self._confirm)
        footer_row.addWidget(cancel)
        footer_row.addWidget(save)
        outer.addWidget(footer)

        self._loopback.toggled.connect(self._device.setEnabled)
        self._device.setEnabled(enable_loopback)

    # -- shell helpers ---------------------------------------------------
    def _section(self, text: str, *, top: bool = False) -> QWidget:
        wrap = QWidget()
        box = QVBoxLayout(wrap)
        box.setContentsMargins(0, 16 if top else 0, 0, 4)
        box.setSpacing(0)
        if top:
            divider = QFrame()
            divider.setObjectName("destDivider")
            divider.setFixedHeight(1)
            box.addWidget(divider)
            box.addSpacing(12)
        label = QLabel(text.upper())
        label.setObjectName("sectionLabel")
        box.addWidget(label)
        return wrap

    def _toggle_row(self, title: str, desc: str, toggle: ToggleSwitch) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setContentsMargins(0, 10, 0, 12)
        row.setSpacing(16)
        text = QVBoxLayout()
        text.setSpacing(3)
        title_label = QLabel(title)
        title_label.setObjectName("mbTitle")
        desc_label = QLabel(desc)
        desc_label.setObjectName("mbDesc")
        desc_label.setWordWrap(True)
        text.addWidget(title_label)
        text.addWidget(desc_label)
        row.addLayout(text, 1)
        row.addWidget(toggle, 0, Qt.AlignmentFlag.AlignTop)
        return row

    def _field_row(
        self, label_text: str, field: QWidget, *, trailing: QWidget | None = None
    ) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 12)
        row.setSpacing(16)
        label = QLabel(label_text)
        label.setObjectName("fieldLabel")
        label.setFixedWidth(150)
        row.addWidget(label)
        row.addWidget(field, 1)
        if trailing is not None:
            row.addWidget(trailing)
        return row

    def _interval_row(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(24)
        spacer = QLabel()
        spacer.setFixedWidth(150)
        row.addWidget(spacer)
        every = QHBoxLayout()
        every.setSpacing(10)
        every.addWidget(QLabel(i18n.t("modules.meeting_buddy.settings.summary_every")))
        every.addWidget(self._interval)
        every.addWidget(QLabel(i18n.t("modules.meeting_buddy.settings.summary_seconds")))
        after = QHBoxLayout()
        after.setSpacing(10)
        after.addWidget(QLabel(i18n.t("modules.meeting_buddy.settings.summary_or_after")))
        after.addWidget(self._chars)
        after.addWidget(QLabel(i18n.t("modules.meeting_buddy.settings.summary_chars")))
        row.addLayout(every)
        row.addLayout(after)
        row.addStretch(1)
        return row

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
