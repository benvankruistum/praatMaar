"""Qt startup progress dialog with the reporter API used by ``dictation``."""

from __future__ import annotations

import threading
from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtWidgets import (
    QDialog,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
)

import i18n
from ui.app import ensure_app
from ui.theme import TOKENS

SPLASH_WIDTH = 400


class _ReporterSignals(QObject):
    status = Signal(str)
    progress = Signal(object, str)
    done = Signal()
    error = Signal(str)


class Splash(QDialog):
    """Non-modal Qt splash which accepts updates safely from worker threads."""

    def __init__(self, app_name: str = "praatMaar") -> None:
        ensure_app()
        super().__init__()
        self.setWindowTitle(app_name)
        self.setModal(False)
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        self.setFixedWidth(SPLASH_WIDTH)
        self._result: Any = None
        self._error: BaseException | None = None
        self._error_shown = False
        self._signals = _ReporterSignals()
        self._signals.status.connect(self._set_status)
        self._signals.progress.connect(self._set_progress)
        self._signals.done.connect(self.accept)
        self._signals.error.connect(self._show_error)
        self._build_window(app_name)

    def _build_window(self, app_name: str) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(12)
        title = QLabel(app_name)
        title.setStyleSheet("font-size: 16px; font-weight: 600;")
        self._status_label = QLabel(i18n.t("splash.starting"))
        self._status_label.setStyleSheet(f"color: {TOKENS['muted']};")
        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(0)
        self._detail_label = QLabel()
        self._detail_label.setStyleSheet(f"color: {TOKENS['muted']};")
        self._close_button = QPushButton(i18n.t("splash.close"))
        self._close_button.clicked.connect(self.reject)
        self._close_button.hide()
        layout.addWidget(title)
        layout.addWidget(self._status_label)
        layout.addWidget(self._progress_bar)
        layout.addWidget(self._detail_label)
        layout.addWidget(self._close_button, alignment=Qt.AlignmentFlag.AlignRight)

    def set_status(self, text: str) -> None:
        """Set the startup status from any thread."""
        self._signals.status.emit(text)

    def set_progress(self, fraction: float | None, detail: str = "") -> None:
        """Set determinate progress or an indeterminate busy animation."""
        self._signals.progress.emit(fraction, detail)

    def run(self, worker: Callable[[Splash], Any]) -> Any:
        """Run ``worker(self)`` in a thread and wait for its result."""
        thread = threading.Thread(target=self._run_worker, args=(worker,), daemon=True)
        thread.start()
        self.show()
        self.exec()
        self.close()
        if self._error is not None:
            raise self._error
        return self._result

    def _run_worker(self, worker: Callable[[Splash], Any]) -> None:
        try:
            self._result = worker(self)
        except BaseException as exc:  # noqa: BLE001 - re-raise after user acknowledges it.
            self._error = exc
            self._signals.error.emit(str(exc))
        else:
            self._signals.done.emit()

    def _set_status(self, text: str) -> None:
        self._status_label.setText(text)

    def _set_progress(self, fraction: object, detail: str) -> None:
        self._detail_label.setText(detail)
        if fraction is None:
            self._progress_bar.setRange(0, 0)
            return
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(round(max(0.0, min(1.0, float(fraction))) * 100))

    def _show_error(self, text: str) -> None:
        if self._error_shown:
            return
        self._error_shown = True
        self._status_label.setText(i18n.t("splash.model_failed"))
        self._status_label.setStyleSheet(f"color: {TOKENS['danger']};")
        self._detail_label.setText(_shorten(text))
        self._progress_bar.hide()
        self._close_button.show()


def _shorten(text: str, limit: int = 70) -> str:
    """Shorten an error to a single readable line."""
    text = " ".join(text.split())
    return text[: limit - 1] + "…" if len(text) > limit else text
