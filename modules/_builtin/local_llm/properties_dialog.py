"""Qt Local LLM properties: bundled defaults vs custom Ollama endpoint."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from PySide6.QtWidgets import (
    QButtonGroup,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

import i18n
from ui.app import ensure_app
from ui.theme import TOKENS

from .config import (
    DEFAULT_BASE_URL,
    DEFAULT_MODEL,
    ENDPOINT_MODE_BUNDLED,
    ENDPOINT_MODE_CUSTOM,
    LocalLlmConfigError,
    validate_base_url,
    validate_model_name,
)


@dataclass(frozen=True)
class LocalLlmPropertiesResult:
    endpoint_mode: str
    ollama_base_url: str
    ollama_model: str


def build_properties_result(
    *,
    endpoint_mode: str,
    base_url: str,
    model: str,
) -> LocalLlmPropertiesResult:
    mode = (
        ENDPOINT_MODE_CUSTOM
        if str(endpoint_mode).strip().lower() == ENDPOINT_MODE_CUSTOM
        else ENDPOINT_MODE_BUNDLED
    )
    if mode == ENDPOINT_MODE_BUNDLED:
        return LocalLlmPropertiesResult(
            endpoint_mode=ENDPOINT_MODE_BUNDLED,
            ollama_base_url=DEFAULT_BASE_URL,
            ollama_model=DEFAULT_MODEL,
        )
    return LocalLlmPropertiesResult(
        endpoint_mode=ENDPOINT_MODE_CUSTOM,
        ollama_base_url=validate_base_url(base_url),
        ollama_model=validate_model_name(model),
    )


class _PropertiesDialog(QDialog):
    def __init__(
        self,
        *,
        endpoint_mode: str,
        custom_base_url: str,
        custom_model: str,
        parent: QWidget | None,
    ) -> None:
        super().__init__(parent)
        self._result: LocalLlmPropertiesResult | None = None
        self.setWindowTitle(i18n.t("modules.local_llm.dialog.properties_title"))
        self.setMinimumWidth(560)
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
        col.setSpacing(12)

        section = QLabel(i18n.t("modules.local_llm.settings.section.endpoint").upper())
        section.setObjectName("sectionLabel")
        col.addWidget(section)

        self._mode_bundled = QRadioButton(i18n.t("modules.local_llm.settings.mode.bundled"))
        self._mode_custom = QRadioButton(i18n.t("modules.local_llm.settings.mode.custom"))
        group = QButtonGroup(self)
        group.addButton(self._mode_bundled)
        group.addButton(self._mode_custom)
        if endpoint_mode == ENDPOINT_MODE_CUSTOM:
            self._mode_custom.setChecked(True)
        else:
            self._mode_bundled.setChecked(True)
        col.addWidget(self._mode_bundled)
        hint_bundled = QLabel(i18n.t("modules.local_llm.settings.mode.bundled_hint"))
        hint_bundled.setWordWrap(True)
        hint_bundled.setStyleSheet(f"color: {TOKENS['muted']}; font-size: 12px;")
        col.addWidget(hint_bundled)
        col.addWidget(self._mode_custom)
        hint_custom = QLabel(i18n.t("modules.local_llm.settings.mode.custom_hint"))
        hint_custom.setWordWrap(True)
        hint_custom.setStyleSheet(f"color: {TOKENS['muted']}; font-size: 12px;")
        col.addWidget(hint_custom)

        self._url = QLineEdit(custom_base_url or DEFAULT_BASE_URL)
        self._url.setPlaceholderText(DEFAULT_BASE_URL)
        self._model = QLineEdit(custom_model or DEFAULT_MODEL)
        self._model.setPlaceholderText(DEFAULT_MODEL)
        col.addLayout(self._field_row(i18n.t("modules.local_llm.settings.base_url"), self._url))
        col.addLayout(self._field_row(i18n.t("modules.local_llm.settings.model"), self._model))

        self._error = QLabel()
        self._error.setWordWrap(True)
        self._error.setStyleSheet(f"color: {TOKENS['danger']}; font-size: 12px;")
        self._error.hide()
        col.addWidget(self._error)

        col.addStretch(1)
        outer.addWidget(body, 1)

        footer = QFrame()
        footer.setObjectName("dialogFooter")
        footer.setStyleSheet(
            f"#dialogFooter {{ background: {TOKENS['surface_footer']}; "
            f"border-top: 1px solid {TOKENS['border']}; }}"
        )
        foot = QHBoxLayout(footer)
        foot.setContentsMargins(18, 12, 18, 12)
        foot.addStretch(1)
        cancel = QPushButton(i18n.t("modules.local_llm.dialog.cancel"))
        cancel.setObjectName("ghost")
        cancel.clicked.connect(self.reject)
        save = QPushButton(i18n.t("modules.local_llm.dialog.save"))
        save.setObjectName("primary")
        save.setDefault(True)
        save.clicked.connect(self._confirm)
        foot.addWidget(cancel)
        foot.addWidget(save)
        outer.addWidget(footer)

        self._mode_bundled.toggled.connect(self._sync_fields_enabled)
        self._sync_fields_enabled()

    def _field_row(self, title: str, field: QWidget) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(16)
        label = QLabel(title)
        label.setObjectName("fieldLabel")
        label.setFixedWidth(140)
        row.addWidget(label)
        row.addWidget(field, 1)
        return row

    def _sync_fields_enabled(self) -> None:
        custom = self._mode_custom.isChecked()
        self._url.setEnabled(custom)
        self._model.setEnabled(custom)

    @property
    def result(self) -> LocalLlmPropertiesResult | None:
        return self._result

    def _confirm(self) -> None:
        mode = ENDPOINT_MODE_CUSTOM if self._mode_custom.isChecked() else ENDPOINT_MODE_BUNDLED
        try:
            self._result = build_properties_result(
                endpoint_mode=mode,
                base_url=self._url.text(),
                model=self._model.text(),
            )
        except LocalLlmConfigError as exc:
            key = {
                "empty_url": "modules.local_llm.settings.error.empty_url",
                "invalid_url": "modules.local_llm.settings.error.invalid_url",
                "empty_model": "modules.local_llm.settings.error.empty_model",
            }.get(str(exc), "modules.local_llm.settings.error.invalid_url")
            self._error.setText(i18n.t(key))
            self._error.show()
            return
        self.accept()


def show_properties_dialog(
    *,
    endpoint_mode: str = ENDPOINT_MODE_BUNDLED,
    custom_base_url: str = DEFAULT_BASE_URL,
    custom_model: str = DEFAULT_MODEL,
    parent: Any = None,
) -> LocalLlmPropertiesResult | None:
    """Toon endpoint-keuze; ``None`` bij annuleren."""

    ensure_app()
    dialog = _PropertiesDialog(
        endpoint_mode=endpoint_mode,
        custom_base_url=custom_base_url,
        custom_model=custom_model,
        parent=parent if isinstance(parent, QWidget) else None,
    )
    dialog.exec()
    return dialog.result
