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
    "border": "#E1E5EA",
    "danger": "#C42B1C",
    "warn": "#FDE7E9",
    "ok": "#107C10",
}


def build_qss(tokens: dict[str, str] | None = None) -> str:
    """Build the shared stylesheet from the supplied colour tokens."""
    t = tokens or TOKENS
    return f"""
    QWidget {{ color: {t["text"]}; font-size: 13px; }}
    QDialog, QMainWindow {{ background: {t["page"]}; }}
    QPushButton#primary {{
        background: {t["accent"]}; color: white; border: none;
        border-radius: 6px; padding: 6px 14px;
    }}
    QPushButton#primary:hover {{ background: {t["accent_hover"]}; }}
    """


def apply_theme(app: QApplication) -> None:
    """Apply praatMaar's shared stylesheet to ``app``."""
    app.setStyleSheet(build_qss())
