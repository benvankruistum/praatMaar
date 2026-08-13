"""Post-meeting recap dialog — agenda, summary, open questions."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

import i18n
from ui.app import ensure_app
from ui.theme import TOKENS

from .live_summary import summary_points
from .overlay import format_topic_line
from .state import MeetingState, QuestionStatus


def show_recap_dialog(
    state: MeetingState,
    transcript_path: Path,
    *,
    parent: Any = None,
) -> None:
    ensure_app()
    dialog = QDialog(parent if isinstance(parent, QWidget) else None)
    dialog.setWindowTitle(i18n.t("modules.meeting_buddy.recap.title"))
    dialog.setMinimumSize(520, 420)
    dialog.setStyleSheet(
        f"QDialog {{ background: {TOKENS['surface']}; "
        f"border: 1px solid {TOKENS['border_dialog']}; }}"
    )

    outer = QVBoxLayout(dialog)
    outer.setContentsMargins(0, 0, 0, 0)

    body = QScrollArea()
    body.setWidgetResizable(True)
    body.setFrameShape(QFrame.Shape.NoFrame)
    host = QWidget()
    col = QVBoxLayout(host)
    col.setContentsMargins(18, 16, 18, 16)
    col.setSpacing(14)

    if state.topics:
        col.addWidget(_section_label(i18n.t("modules.meeting_buddy.overlay.agenda")))
        for topic in state.topics:
            line = QLabel(format_topic_line(topic))
            line.setWordWrap(True)
            col.addWidget(line)

    summary = (state.live_summary or "").strip()
    if summary:
        col.addWidget(_section_label(i18n.t("modules.meeting_buddy.overlay.summary")))
        for point in summary_points(summary):
            bullet = QLabel(f"• {point}")
            bullet.setWordWrap(True)
            col.addWidget(bullet)

    open_questions = [
        question.text for question in state.questions if question.status == QuestionStatus.OPEN
    ]
    if open_questions:
        col.addWidget(_section_label(i18n.t("modules.meeting_buddy.overlay.questions")))
        for text in open_questions[:8]:
            line = QLabel(f"? {text}")
            line.setWordWrap(True)
            col.addWidget(line)

    path_label = QLabel(
        i18n.t("modules.meeting_buddy.recap.transcript_path", path=str(transcript_path))
    )
    path_label.setWordWrap(True)
    path_label.setObjectName("overlayFooterText")
    col.addWidget(path_label)
    col.addStretch(1)
    body.setWidget(host)
    outer.addWidget(body, 1)

    footer = QFrame()
    footer.setObjectName("dialogFooter")
    row = QHBoxLayout(footer)
    row.setContentsMargins(18, 12, 18, 12)
    row.addStretch(1)
    close = QPushButton(i18n.t("modules.meeting_buddy.recap.close"))
    close.setObjectName("primary")
    close.clicked.connect(dialog.accept)
    row.addWidget(close)
    outer.addWidget(footer)

    dialog.exec()


def _section_label(text: str) -> QLabel:
    label = QLabel(text.upper())
    label.setObjectName("sectionLabel")
    return label
