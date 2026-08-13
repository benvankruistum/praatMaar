"""Qt Settings dialog — canvas frame #4a fidelity."""

from __future__ import annotations

import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

import config
import destinations
import hotkeys
import i18n
import recovery
from ui.app import ensure_app
from ui.marshal import ui_dispatch

MODELS = ["base", "small", "medium"]
_LABEL_WIDTH = 150
_open_dialog: QDialog | None = None


def _positions() -> list[tuple[str, str]]:
    return [
        (i18n.t("settings.position.top"), "boven-midden"),
        (i18n.t("settings.position.bottom"), "onder-midden"),
        (i18n.t("settings.position.last"), "laatst-geplaatst"),
    ]


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


def _section_title(text: str) -> QLabel:
    label = QLabel(text.upper())
    label.setObjectName("sectionLabel")
    return label


def _field_label(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("fieldLabel")
    label.setFixedWidth(_LABEL_WIDTH)
    return label


def _hint(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("hintLabel")
    label.setWordWrap(True)
    return label


def _labeled_row(label: str, widget: QWidget) -> QWidget:
    row = QWidget()
    layout = QHBoxLayout(row)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(14)
    layout.addWidget(_field_label(label))
    layout.addWidget(widget, 1)
    return row


def _checkbox_with_hint(title: str, hint: str | None = None) -> tuple[QCheckBox, QWidget]:
    box = QWidget()
    layout = QHBoxLayout(box)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(9)
    check = QCheckBox()
    layout.addWidget(check, 0, Qt.AlignmentFlag.AlignTop)
    text_col = QVBoxLayout()
    text_col.setSpacing(2)
    text_col.setContentsMargins(0, 0, 0, 0)
    title_label = QLabel(title)
    title_label.setObjectName("optionTitle")
    text_col.addWidget(title_label)
    if hint:
        text_col.addWidget(_hint(hint))
    layout.addLayout(text_col, 1)
    return check, box


class SettingsDialog(QDialog):
    """Settings dialog aligned to canvas #4a."""

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
        self.setMinimumSize(620, 560)
        self.resize(620, 640)
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

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self._tabs = QTabWidget()
        self._general_tab = QWidget()
        self._language_tab = QWidget()
        self._whisper_tab = QWidget()
        self._advanced_tab = QWidget()
        self._tabs.addTab(self._general_tab, i18n.t("settings.tab.general"))
        self._tabs.addTab(self._language_tab, i18n.t("settings.tab.language"))
        self._tabs.addTab(self._whisper_tab, i18n.t("settings.tab.whisper"))
        self._tabs.addTab(self._advanced_tab, i18n.t("settings.tab.advanced"))
        self._build_general()
        self._build_language()
        self._build_whisper()
        self._build_advanced()
        outer.addWidget(self._tabs, 1)

        footer = QFrame()
        footer.setObjectName("dialogFooter")
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(18, 12, 18, 12)
        footer_layout.addStretch(1)
        cancel = QPushButton(i18n.t("settings.cancel"))
        cancel.setObjectName("ghost")
        save = QPushButton(i18n.t("settings.save"))
        save.setObjectName("primary")
        cancel.clicked.connect(self.reject)
        save.clicked.connect(self._save)
        footer_layout.addWidget(cancel)
        footer_layout.addWidget(save)
        outer.addWidget(footer)

    def _build_general(self) -> None:
        scroll = QScrollArea(self._general_tab)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        host = QWidget()
        layout = QVBoxLayout(host)
        layout.setContentsMargins(18, 18, 18, 20)
        layout.setSpacing(0)

        # MICROFOON
        mic_section = QVBoxLayout()
        mic_section.setSpacing(10)
        mic_section.addWidget(_section_title(i18n.t("settings.section.microphone")))
        devices = _input_devices()
        self._devices = devices
        self.mic = _combo(devices, self._current.get("microphone_device"))
        mic_section.addWidget(_labeled_row(i18n.t("settings.mic.device"), self.mic))
        self.warm_microphone, warm_row = _checkbox_with_hint(
            i18n.t("settings.warm_microphone"),
            i18n.t("settings.warm_microphone.hint"),
        )
        self.warm_microphone.setChecked(bool(self._current.get("warm_microphone", False)))
        warm_indent = QHBoxLayout()
        warm_indent.addSpacing(_LABEL_WIDTH + 14)
        warm_indent.addWidget(warm_row, 1)
        mic_section.addLayout(warm_indent)
        layout.addLayout(mic_section)

        # INDICATOR
        ind = QFrame()
        ind.setObjectName("settingsSection")
        ind_layout = QVBoxLayout(ind)
        ind_layout.setContentsMargins(0, 18, 0, 0)
        ind_layout.setSpacing(10)
        ind_layout.addWidget(_section_title(i18n.t("settings.section.indicator")))
        self.position = _combo(_positions(), self._current.get("indicator_position"))
        ind_layout.addWidget(_labeled_row(i18n.t("settings.indicator.position"), self.position))
        hint_row = QHBoxLayout()
        hint_row.addSpacing(_LABEL_WIDTH + 14)
        hint_row.addWidget(_hint(i18n.t("settings.indicator.position.hint")), 1)
        ind_layout.addLayout(hint_row)
        layout.addWidget(ind)

        # BEDIENING
        control = QFrame()
        control.setObjectName("settingsSection")
        control_layout = QVBoxLayout(control)
        control_layout.setContentsMargins(0, 18, 0, 0)
        control_layout.setSpacing(10)
        control_layout.addWidget(_section_title(i18n.t("settings.section.control")))

        mode_row = QHBoxLayout()
        mode_row.setSpacing(14)
        mode_row.addWidget(
            _field_label(i18n.t("settings.mode.label")), 0, Qt.AlignmentFlag.AlignTop
        )
        mode_col = QVBoxLayout()
        mode_col.setSpacing(9)
        self._mode_group = QButtonGroup(self)
        self.mode_toggle = QRadioButton(i18n.t("settings.mode.toggle"))
        self.mode_ptt = QRadioButton(i18n.t("settings.mode.ptt"))
        self._mode_group.addButton(self.mode_toggle)
        self._mode_group.addButton(self.mode_ptt)
        if self._current.get("mode") == "ptt":
            self.mode_ptt.setChecked(True)
        else:
            self.mode_toggle.setChecked(True)
        mode_col.addWidget(self.mode_toggle)
        mode_col.addWidget(self.mode_ptt)
        mode_row.addLayout(mode_col, 1)
        control_layout.addLayout(mode_row)

        hotkey_row = QHBoxLayout()
        hotkey_row.setSpacing(14)
        hotkey_row.addWidget(_field_label(i18n.t("settings.hotkey")))
        hotkey_host = QWidget()
        hotkey_layout = QHBoxLayout(hotkey_host)
        hotkey_layout.setContentsMargins(0, 0, 0, 0)
        hotkey_layout.setSpacing(10)
        self._keycaps = QWidget()
        self._keycaps_layout = QHBoxLayout(self._keycaps)
        self._keycaps_layout.setContentsMargins(0, 0, 0, 0)
        self._keycaps_layout.setSpacing(5)
        self.capture_button = QPushButton(i18n.t("settings.hotkey.record"))
        self.capture_button.setObjectName("secondary")
        self.capture_button.clicked.connect(self._toggle_capture)
        hotkey_layout.addWidget(self._keycaps)
        hotkey_layout.addWidget(self.capture_button)
        hotkey_layout.addStretch(1)
        hotkey_row.addWidget(hotkey_host, 1)
        control_layout.addLayout(hotkey_row)
        self._listening_hint = _hint("")
        self._listening_hint.hide()
        listen_row = QHBoxLayout()
        listen_row.addSpacing(_LABEL_WIDTH + 14)
        listen_row.addWidget(self._listening_hint, 1)
        control_layout.addLayout(listen_row)
        layout.addWidget(control)
        self._refresh_keycaps(self._hotkey_tokens)

        # OPTIES
        options = QFrame()
        options.setObjectName("settingsSection")
        options_layout = QVBoxLayout(options)
        options_layout.setContentsMargins(0, 18, 0, 0)
        options_layout.setSpacing(11)
        options_layout.addWidget(_section_title(i18n.t("settings.section.options")))
        self.autostart, autostart_row = _checkbox_with_hint(i18n.t("settings.autostart"))
        self.auto_paste, paste_row = _checkbox_with_hint(
            i18n.t("settings.auto_paste"),
            i18n.t("settings.auto_paste.hint"),
        )
        self.autostart.setChecked(bool(self._current.get("autostart", False)))
        self.auto_paste.setChecked(bool(self._current.get("auto_paste", True)))
        options_layout.addWidget(autostart_row)
        options_layout.addWidget(paste_row)
        layout.addWidget(options)

        layout.addStretch(1)
        scroll.setWidget(host)
        tab_layout = QVBoxLayout(self._general_tab)
        tab_layout.setContentsMargins(0, 0, 0, 0)
        tab_layout.addWidget(scroll)

    def _build_language(self) -> None:
        layout = QVBoxLayout(self._language_tab)
        layout.setContentsMargins(18, 18, 18, 20)
        layout.setSpacing(18)
        choices = _language_choices()
        speech = i18n.normalize_language(
            self._current.get("speech_language"), allowed=i18n.SUPPORTED_SPEECH_LANGUAGES
        )
        ui = i18n.normalize_language(
            self._current.get("ui_language"), allowed=i18n.SUPPORTED_UI_LANGUAGES
        )
        speech_box = QVBoxLayout()
        speech_box.setSpacing(10)
        speech_box.addWidget(_section_title(i18n.t("settings.speech_language")))
        self.speech_language = _combo(choices, speech)
        speech_box.addWidget(_labeled_row(i18n.t("settings.speech_language"), self.speech_language))
        layout.addLayout(speech_box)

        ui_box = QFrame()
        ui_box.setObjectName("settingsSection")
        ui_layout = QVBoxLayout(ui_box)
        ui_layout.setContentsMargins(0, 16, 0, 0)
        ui_layout.setSpacing(10)
        ui_layout.addWidget(_section_title(i18n.t("settings.ui_language")))
        self.ui_language = _combo(choices, ui)
        ui_layout.addWidget(_labeled_row(i18n.t("settings.ui_language"), self.ui_language))
        layout.addWidget(ui_box)
        layout.addStretch(1)

    def _build_whisper(self) -> None:
        whisper = config.whisper_settings_from_config(self._current)

        scroll = QScrollArea(self._whisper_tab)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        body = QWidget()
        layout = QVBoxLayout(body)
        layout.setContentsMargins(18, 18, 18, 20)
        layout.setSpacing(14)

        quality = QVBoxLayout()
        quality.setSpacing(10)
        quality.addWidget(_section_title(i18n.t("settings.whisper.section.quality")))
        self.whisper_beam_size = QSpinBox()
        self.whisper_beam_size.setRange(1, 10)
        self.whisper_beam_size.setValue(int(whisper["whisper_beam_size"]))
        quality.addWidget(
            _labeled_row(i18n.t("settings.whisper.beam_size"), self.whisper_beam_size)
        )
        quality.addWidget(_hint(i18n.t("settings.whisper.beam_size.hint")))
        self.whisper_condition_on_previous = QCheckBox()
        cond_row = QWidget()
        cond_layout = QHBoxLayout(cond_row)
        cond_layout.setContentsMargins(0, 0, 0, 0)
        cond_layout.setSpacing(9)
        cond_layout.addWidget(self.whisper_condition_on_previous, 0, Qt.AlignmentFlag.AlignTop)
        cond_text = QVBoxLayout()
        cond_text.setSpacing(2)
        cond_title = QLabel(i18n.t("settings.whisper.condition_on_previous"))
        cond_title.setObjectName("optionTitle")
        cond_text.addWidget(cond_title)
        cond_text.addWidget(_hint(i18n.t("settings.whisper.condition_on_previous.hint")))
        cond_layout.addLayout(cond_text, 1)
        self.whisper_condition_on_previous.setChecked(
            bool(whisper["whisper_condition_on_previous_text"])
        )
        quality.addWidget(cond_row)
        self.whisper_no_speech = QDoubleSpinBox()
        self.whisper_no_speech.setRange(0.0, 1.0)
        self.whisper_no_speech.setSingleStep(0.05)
        self.whisper_no_speech.setDecimals(2)
        self.whisper_no_speech.setValue(float(whisper["whisper_no_speech_threshold"]))
        quality.addWidget(
            _labeled_row(i18n.t("settings.whisper.no_speech_threshold"), self.whisper_no_speech)
        )
        quality.addWidget(_hint(i18n.t("settings.whisper.no_speech_threshold.hint")))
        layout.addLayout(quality)

        vad_box = QFrame()
        vad_box.setObjectName("settingsSection")
        vad_layout = QVBoxLayout(vad_box)
        vad_layout.setContentsMargins(0, 8, 0, 0)
        vad_layout.setSpacing(10)
        vad_layout.addWidget(_section_title(i18n.t("settings.whisper.section.vad")))
        self.whisper_vad_filter, vad_row = _checkbox_with_hint(
            i18n.t("settings.whisper.vad_filter"),
            i18n.t("settings.whisper.vad_filter.hint"),
        )
        self.whisper_vad_filter.setChecked(bool(whisper["whisper_vad_filter"]))
        vad_layout.addWidget(vad_row)
        self.whisper_vad_min_silence = QSpinBox()
        self.whisper_vad_min_silence.setRange(100, 5000)
        self.whisper_vad_min_silence.setSingleStep(50)
        self.whisper_vad_min_silence.setSuffix(" ms")
        self.whisper_vad_min_silence.setValue(int(whisper["whisper_vad_min_silence_ms"]))
        vad_layout.addWidget(
            _labeled_row(
                i18n.t("settings.whisper.vad_min_silence"),
                self.whisper_vad_min_silence,
            )
        )
        vad_layout.addWidget(_hint(i18n.t("settings.whisper.vad_min_silence.hint")))
        self.whisper_vad_filter.toggled.connect(self.whisper_vad_min_silence.setEnabled)
        self.whisper_vad_min_silence.setEnabled(self.whisper_vad_filter.isChecked())
        layout.addWidget(vad_box)

        prompt_box = QFrame()
        prompt_box.setObjectName("settingsSection")
        prompt_layout = QVBoxLayout(prompt_box)
        prompt_layout.setContentsMargins(0, 8, 0, 0)
        prompt_layout.setSpacing(10)
        prompt_layout.addWidget(_section_title(i18n.t("settings.whisper.section.prompt")))
        self.whisper_initial_prompt = QPlainTextEdit()
        self.whisper_initial_prompt.setPlaceholderText(
            i18n.t("settings.whisper.initial_prompt.placeholder")
        )
        self.whisper_initial_prompt.setPlainText(str(whisper["whisper_initial_prompt"]))
        self.whisper_initial_prompt.setFixedHeight(88)
        prompt_layout.addWidget(_field_label(i18n.t("settings.whisper.initial_prompt")))
        prompt_layout.addWidget(self.whisper_initial_prompt)
        prompt_layout.addWidget(_hint(i18n.t("settings.whisper.initial_prompt.hint")))
        self.whisper_hotwords = QLineEdit()
        self.whisper_hotwords.setPlaceholderText(i18n.t("settings.whisper.hotwords.placeholder"))
        self.whisper_hotwords.setText(str(whisper["whisper_hotwords"]))
        prompt_layout.addWidget(
            _labeled_row(i18n.t("settings.whisper.hotwords"), self.whisper_hotwords)
        )
        prompt_layout.addWidget(_hint(i18n.t("settings.whisper.hotwords.hint")))
        layout.addWidget(prompt_box)

        layout.addStretch(1)
        scroll.setWidget(body)
        tab_layout = QVBoxLayout(self._whisper_tab)
        tab_layout.setContentsMargins(0, 0, 0, 0)
        tab_layout.addWidget(scroll)

    def _build_advanced(self) -> None:
        layout = QVBoxLayout(self._advanced_tab)
        layout.setContentsMargins(18, 18, 18, 20)
        layout.setSpacing(12)

        layout.addWidget(_section_title(i18n.t("settings.preset.section")))
        layout.addWidget(_hint(i18n.t("settings.preset.intro")))
        self._preset_group = QButtonGroup(self)
        self._preset_group.setExclusive(True)
        self._preset_buttons: dict[str, QRadioButton] = {}
        preset_col = QVBoxLayout()
        preset_col.setSpacing(8)
        for preset_id in config.DICTATION_PRESET_IDS:
            radio = QRadioButton(i18n.t(f"settings.preset.{preset_id}"))
            radio.setProperty("preset_id", preset_id)
            self._preset_group.addButton(radio)
            self._preset_buttons[preset_id] = radio
            row = QVBoxLayout()
            row.setSpacing(2)
            row.addWidget(radio)
            row.addWidget(_hint(i18n.t(f"settings.preset.{preset_id}.hint")))
            preset_col.addLayout(row)
        layout.addLayout(preset_col)
        self._preset_custom_hint = _hint(i18n.t("settings.preset.custom"))
        self._preset_custom_hint.hide()
        layout.addWidget(self._preset_custom_hint)
        self._preset_group.buttonClicked.connect(self._on_preset_clicked)
        self._preset_updating = False

        model_box = QFrame()
        model_box.setObjectName("settingsSection")
        model_layout = QVBoxLayout(model_box)
        model_layout.setContentsMargins(0, 18, 0, 0)
        model_layout.setSpacing(10)
        model_layout.addWidget(_section_title(i18n.t("settings.model")))
        self.model = _combo(
            [(model, model) for model in MODELS], str(self._current.get("model", "small"))
        )
        model_layout.addWidget(_labeled_row(i18n.t("settings.model"), self.model))
        model_layout.addWidget(_hint(i18n.t("settings.model.restart")))
        layout.addWidget(model_box)

        recovery_box = QFrame()
        recovery_box.setObjectName("settingsSection")
        recovery_layout = QVBoxLayout(recovery_box)
        recovery_layout.setContentsMargins(0, 18, 0, 0)
        recovery_layout.setSpacing(10)
        recovery_layout.addWidget(_section_title(i18n.t("recovery.section")))
        self.recovery_list = QListWidget()
        self.recovery_list.setMinimumHeight(120)
        recovery_layout.addWidget(self.recovery_list)
        self.recovery_empty = _hint("")
        recovery_layout.addWidget(self.recovery_empty)
        self.recovery_status = QLabel()
        recovery_layout.addWidget(self.recovery_status)
        actions = QHBoxLayout()
        open_folder = QPushButton(i18n.t("recovery.open_folder"))
        delete = QPushButton(i18n.t("recovery.delete"))
        delete_all = QPushButton(i18n.t("recovery.delete_all"))
        retranscribe = QPushButton(i18n.t("recovery.retranscribe"))
        open_folder.setObjectName("secondary")
        delete.setObjectName("secondary")
        delete_all.setObjectName("secondary")
        retranscribe.setObjectName("secondary")
        open_folder.clicked.connect(self._open_recovery_folder)
        delete.clicked.connect(self._delete_selected)
        delete_all.clicked.connect(self._delete_all)
        retranscribe.clicked.connect(self._retranscribe_selected)
        for button in (open_folder, delete, delete_all, retranscribe):
            actions.addWidget(button)
        actions.addStretch(1)
        recovery_layout.addLayout(actions)
        layout.addWidget(recovery_box)
        layout.addStretch(1)
        self._refresh_recovery()
        self._sync_preset_selection_from_fields()
        self.model.currentIndexChanged.connect(self._on_preset_fields_changed)
        self.whisper_beam_size.valueChanged.connect(self._on_preset_fields_changed)
        self.whisper_vad_filter.toggled.connect(self._on_preset_fields_changed)
        self.whisper_vad_min_silence.valueChanged.connect(self._on_preset_fields_changed)

    def _preset_field_snapshot(self) -> dict[str, Any]:
        return {
            "model": self.model.currentData(),
            "whisper_beam_size": int(self.whisper_beam_size.value()),
            "whisper_vad_filter": self.whisper_vad_filter.isChecked(),
            "whisper_vad_min_silence_ms": int(self.whisper_vad_min_silence.value()),
        }

    def _set_combo_data(self, combo: QComboBox, value: Any) -> None:
        index = combo.findData(value)
        combo.setCurrentIndex(index if index >= 0 else 0)

    def _apply_preset_to_fields(self, preset_id: str) -> None:
        values = config.dictation_preset_values(preset_id)
        if values is None:
            return
        self._preset_updating = True
        try:
            self._set_combo_data(self.model, values["model"])
            self.whisper_beam_size.setValue(int(values["whisper_beam_size"]))
            self.whisper_vad_filter.setChecked(bool(values["whisper_vad_filter"]))
            self.whisper_vad_min_silence.setValue(int(values["whisper_vad_min_silence_ms"]))
            self.whisper_vad_min_silence.setEnabled(self.whisper_vad_filter.isChecked())
        finally:
            self._preset_updating = False
        self._sync_preset_selection_from_fields()

    def _on_preset_clicked(self, button: QRadioButton) -> None:
        preset_id = str(button.property("preset_id") or "")
        if preset_id in config.DICTATION_PRESET_IDS:
            self._apply_preset_to_fields(preset_id)

    def _clear_preset_radios(self) -> None:
        self._preset_group.setExclusive(False)
        for radio in self._preset_buttons.values():
            radio.setChecked(False)
        self._preset_group.setExclusive(True)

    def _sync_preset_selection_from_fields(self) -> None:
        matched = config.match_dictation_preset(self._preset_field_snapshot())
        self._preset_updating = True
        try:
            if matched is None:
                self._clear_preset_radios()
                self._preset_custom_hint.show()
            else:
                self._preset_custom_hint.hide()
                radio = self._preset_buttons.get(matched)
                if radio is not None and not radio.isChecked():
                    radio.setChecked(True)
        finally:
            self._preset_updating = False

    def _on_preset_fields_changed(self, *_args: Any) -> None:
        if self._preset_updating:
            return
        self._sync_preset_selection_from_fields()

    def _token_caption(self, token: str) -> str:
        special = {
            "ctrl": "Ctrl",
            "shift": "Shift",
            "alt": "Alt",
            "cmd": "Cmd",
            "space": "Space",
            "esc": "Esc",
        }
        return special.get(token.lower(), token.upper() if len(token) == 1 else token.title())

    def _refresh_keycaps(self, tokens: list[str] | set[str]) -> None:
        while self._keycaps_layout.count():
            item = self._keycaps_layout.takeAt(0)
            if item.widget() is not None:
                item.widget().deleteLater()
        ordered = list(tokens) if isinstance(tokens, list) else hotkeys.normalize(tokens)
        if not ordered:
            placeholder = QLabel("—")
            placeholder.setObjectName("hintLabel")
            self._keycaps_layout.addWidget(placeholder)
            return
        for index, token in enumerate(ordered):
            if index:
                plus = QLabel("+")
                plus.setObjectName("keycapPlus")
                self._keycaps_layout.addWidget(plus)
            cap = QLabel(self._token_caption(token))
            cap.setObjectName("keycap")
            cap.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._keycaps_layout.addWidget(cap)

    def _toggle_capture(self) -> None:
        if self._capture_active:
            self._stop_capture(confirm=True)
            return
        self._capture_active = True
        self._capture_pressed.clear()
        self._capture_best.clear()
        self._listening_hint.setText(i18n.t("settings.hotkey.press"))
        self._listening_hint.show()
        self.capture_button.setText(i18n.t("settings.hotkey.use"))
        if self._set_capture is not None:
            self._set_capture(self._capture_callback)
        self.setFocus(Qt.FocusReason.ActiveWindowFocusReason)

    def _capture_callback(self, event: str, key: Any) -> None:
        # pynput: listenerthread → marshal naar Qt. macOS QuartzKeyListener:
        # callbacks lopen al op de GUI-thread — direct bijwerken.
        token = hotkeys.key_to_token(key)
        if token is None:
            return
        if threading.current_thread() is threading.main_thread():
            self._capture_token(event, token)
            return
        ui_dispatch(lambda e=event, t=token: self._capture_token(e, t))

    def _capture_token(self, event: str, token: str) -> None:
        if event == "press":
            self._capture_pressed.add(token)
            if len(self._capture_pressed) >= len(self._capture_best):
                self._capture_best = set(self._capture_pressed)
        else:
            self._capture_pressed.discard(token)
        visible = self._capture_best or self._capture_pressed
        if visible:
            self._refresh_keycaps(visible)

    def keyPressEvent(self, event: Any) -> None:
        if self._capture_active:
            # Met een actieve globale listener (pynput) is díe de enige
            # tokenbron: Qt-tokens ("num_enter", event-text) wijken af van de
            # pynput-vocabulaire, en dubbel voeden levert combinaties op die
            # de listener nooit kan matchen. Qt onderdrukt hier alleen.
            if self._set_capture is None:
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
            if self._set_capture is None:
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
        if confirm:
            captured = self._capture_best or self._capture_pressed
            if captured:
                self._hotkey_tokens = hotkeys.normalize(captured)
        self._refresh_keycaps(self._hotkey_tokens)
        self._listening_hint.hide()
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
        snapshot = {
            "microphone_device": self.mic.currentData(),
            "indicator_position": self.position.currentData(),
            "mode": "ptt" if self.mode_ptt.isChecked() else "toggle",
            "hotkey": list(self._hotkey_tokens),
            "autostart": self.autostart.isChecked(),
            "auto_paste": self.auto_paste.isChecked(),
            "warm_microphone": self.warm_microphone.isChecked(),
            "model": self.model.currentData(),
            "speech_language": self.speech_language.currentData(),
            "ui_language": self.ui_language.currentData(),
            "whisper_beam_size": int(self.whisper_beam_size.value()),
            "whisper_vad_filter": self.whisper_vad_filter.isChecked(),
            "whisper_vad_min_silence_ms": int(self.whisper_vad_min_silence.value()),
            "whisper_condition_on_previous_text": (self.whisper_condition_on_previous.isChecked()),
            "whisper_no_speech_threshold": float(self.whisper_no_speech.value()),
            "whisper_initial_prompt": self.whisper_initial_prompt.toPlainText(),
            "whisper_hotwords": self.whisper_hotwords.text(),
        }
        matched = config.match_dictation_preset(snapshot)
        if matched is not None:
            snapshot["dictation_preset"] = matched
        else:
            snapshot["dictation_preset"] = None
        self._on_apply(snapshot)
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
    on_retranscribe: Callable[[Path], str] | None = None,
    on_parent_retranscribe: Callable[[Path], None] | None = None,
) -> None:
    """Open the singleton settings dialog."""
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
    # Ook de C++-widgetboom vrijgeven: de dialoog hangt onder de pill en bleef
    # anders tot app-exit bestaan (accumulatie bij herhaald openen).
    dialog.deleteLater()
