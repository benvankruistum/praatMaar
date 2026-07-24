"""Shared Qt stylesheet tokens for praatMaar (canvas-aligned)."""

from __future__ import annotations

from PySide6.QtWidgets import QApplication

# Hex values from docs/design/canvas/praatMaar-ui.dc.html (#5a and family).
TOKENS: dict[str, str] = {
    "accent": "#0F6CBD",
    "accent_hover": "#0A5CA3",
    "accent_soft": "#EAF3FC",
    "accent_border": "#CFE2F4",
    "accent_border_strong": "#BCD9F5",
    "text": "#1B1F24",
    "text_secondary": "#3B4652",
    "muted": "#5A6572",
    "muted_soft": "#8A94A0",
    "surface": "#FFFFFF",
    "surface_card_off": "#FCFDFD",
    "page": "#F7F9FB",
    "page_canvas": "#E9EDF2",
    "surface_footer": "#F6F8FA",
    "border": "#E1E5EA",
    "border_card": "#E4E7EC",
    "border_strong": "#D2D8DF",
    "border_dialog": "#D6DBE1",
    "border_subtle": "#EDEFF3",
    "hover": "#EFF2F6",
    "danger": "#C42B1C",
    "danger_hover": "#FDECEA",
    "warn": "#FDE7E9",
    "ok": "#0F7B3E",
    "ok_legacy": "#107C10",
    "radius_card": "6px",
    "radius_button": "5px",
}


def build_qss(tokens: dict[str, str] | None = None) -> str:
    """Build the shared stylesheet from the supplied colour tokens."""
    t = tokens or TOKENS
    return f"""
    QWidget {{ color: {t["text"]}; font-size: 13px; }}
    QDialog, QMainWindow {{ background: {t["surface"]}; }}
    QLineEdit, QComboBox, QTextEdit {{
        background: {t["surface"]}; border: 1px solid {t["border_strong"]};
        border-radius: {t["radius_button"]}; padding: 5px 8px;
    }}
    QLineEdit:focus, QComboBox:focus, QTextEdit:focus {{
        border-color: {t["accent"]};
    }}
    QPushButton {{
        background: {t["surface"]}; border: 1px solid {t["border_strong"]};
        border-radius: {t["radius_button"]}; padding: 6px 12px;
        min-height: 28px;
    }}
    QPushButton:hover {{ background: {t["hover"]}; }}
    QPushButton#primary {{
        background: {t["accent"]}; color: white; border: 1px solid {t["accent"]};
        border-radius: {t["radius_button"]}; padding: 6px 20px;
        font-weight: 600;
    }}
    QPushButton#primary:hover {{ background: {t["accent_hover"]}; border-color: {t["accent_hover"]}; }}
    QPushButton#ghost {{
        background: transparent; border: 1px solid transparent; color: {t["muted"]};
        border-radius: {t["radius_button"]}; padding: 6px 12px;
    }}
    QPushButton#ghost:hover {{
        background: {t["page_canvas"]}; color: {t["text"]};
    }}
    QPushButton#secondary {{
        background: {t["surface"]}; border: 1px solid {t["border_strong"]};
        border-radius: {t["radius_button"]}; color: {t["text_secondary"]};
    }}
    QLabel#sectionLabel {{
        color: {t["muted"]}; font-size: 11px; font-weight: 700;
        letter-spacing: 0.08em;
    }}
    QLabel#badgeExperimental {{
        color: {t["muted_soft"]}; background: {t["border_subtle"]};
        font-size: 10px; font-weight: 600; letter-spacing: 0.04em;
        padding: 2px 5px; border-radius: 3px;
    }}
    QLabel#runningDot {{
        color: {t["ok"]}; font-size: 10.5px;
    }}
    QFrame#moduleCardOff {{
        background: {t["surface_card_off"]}; border: 1px solid {t["border_card"]};
        border-radius: {t["radius_card"]};
    }}
    QFrame#moduleCardOn {{
        background: {t["surface"]}; border: 1px solid {t["accent_border"]};
        border-radius: {t["radius_card"]};
    }}
    QFrame#incrementalBox {{
        background: {t["surface"]}; border: 1px solid {t["border"]};
        border-radius: {t["radius_card"]};
    }}
    QFrame#incrementalBoxOn {{
        background: {t["accent_soft"]}; border: 1px solid {t["accent_border_strong"]};
        border-radius: {t["radius_card"]};
    }}
    QFrame#dialogFooter {{
        background: {t["surface_footer"]}; border-top: 1px solid {t["border"]};
    }}
    QCheckBox::indicator {{
        width: 34px; height: 19px;
    }}
    QCheckBox::indicator:unchecked {{
        border-radius: 10px; background: {t["border_strong"]};
    }}
    QCheckBox::indicator:checked {{
        border-radius: 10px; background: {t["accent"]};
    }}
    """


def apply_theme(app: QApplication) -> None:
    """Apply praatMaar's shared stylesheet to ``app``."""
    app.setStyleSheet(build_qss())
