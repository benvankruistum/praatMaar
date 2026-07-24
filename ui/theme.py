"""Shared Qt stylesheet tokens for praatMaar."""

from __future__ import annotations

from PySide6.QtWidgets import QApplication

TOKENS: dict[str, str] = {
    "accent": "#0F6CBD",
    "accent_hover": "#0A5CA3",
    "text": "#1B1F24",
    "muted": "#5A6572",
    "muted_soft": "#8A94A0",
    "surface": "#FFFFFF",
    "page": "#F7F9FB",
    "page_canvas": "#E9EDF2",
    "surface_footer": "#F6F8FA",
    "border": "#E1E5EA",
    "border_strong": "#D2D8DF",
    "border_subtle": "#EDEFF3",
    "text_secondary": "#3B4652",
    "hover": "#EFF2F6",
    "danger": "#C42B1C",
    "danger_hover": "#FDECEA",
    "warn": "#FDE7E9",
    "ok": "#107C10",
}


def build_qss(tokens: dict[str, str] | None = None) -> str:
    """Build the shared stylesheet from the supplied colour tokens."""
    t = tokens or TOKENS
    return f"""
    QWidget {{ color: {t["text"]}; font-size: 13px; }}
    QDialog, QMainWindow {{ background: {t["page"]}; }}
    QLineEdit, QComboBox, QTextEdit {{
        background: {t["surface"]}; border: 1px solid {t["border_strong"]};
        border-radius: 5px; padding: 5px 8px;
    }}
    QLineEdit:focus, QComboBox:focus, QTextEdit:focus {{
        border-color: {t["accent"]};
    }}
    QPushButton {{
        background: {t["surface"]}; border: 1px solid {t["border_strong"]};
        border-radius: 5px; padding: 6px 12px;
    }}
    QPushButton:hover {{ background: {t["hover"]}; }}
    QPushButton#primary {{
        background: {t["accent"]}; color: white; border: none;
        border-radius: 6px; padding: 6px 14px;
    }}
    QPushButton#primary:hover {{ background: {t["accent_hover"]}; }}
    """


def apply_theme(app: QApplication) -> None:
    """Apply praatMaar's shared stylesheet to ``app``."""
    app.setStyleSheet(build_qss())
