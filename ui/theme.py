"""Shared Qt stylesheet tokens for praatMaar (canvas-aligned)."""

from __future__ import annotations

import os
import tempfile

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QApplication

_check_icon_path: str | None = None


def _checkbox_check_icon() -> str | None:
    """Paint the white checkmark to a cached PNG and return its QSS-safe path.

    QSS has no reliable checkmark for a styled ``::indicator``; a runtime PNG
    works in dev and packaged builds without shipping assets.
    """
    global _check_icon_path
    if _check_icon_path is not None and os.path.exists(_check_icon_path):
        return _check_icon_path
    image = QImage(16, 16, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    pen = QPen(QColor("white"))
    pen.setWidthF(2.0)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    path = QPainterPath()
    path.moveTo(3.5, 8.2)
    path.lineTo(6.6, 11.2)
    path.lineTo(12.0, 4.5)
    painter.drawPath(path)
    painter.end()
    try:
        cache = os.path.join(tempfile.gettempdir(), "praatMaar-ui")
        os.makedirs(cache, exist_ok=True)
        out = os.path.join(cache, "checkbox-check.png")
        if image.save(out):
            _check_icon_path = out.replace("\\", "/")
            return _check_icon_path
    except OSError:
        return None
    return None


_chevron_icon_path: str | None = None


def _combo_chevron_icon() -> str | None:
    """Paint the muted down-chevron for QComboBox to a cached PNG."""
    global _chevron_icon_path
    if _chevron_icon_path is not None and os.path.exists(_chevron_icon_path):
        return _chevron_icon_path
    image = QImage(12, 12, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    pen = QPen(QColor(TOKENS["muted_soft"]))
    pen.setWidthF(1.5)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    path = QPainterPath()
    path.moveTo(3.0, 4.8)
    path.lineTo(6.0, 7.8)
    path.lineTo(9.0, 4.8)
    painter.drawPath(path)
    painter.end()
    try:
        cache = os.path.join(tempfile.gettempdir(), "praatMaar-ui")
        os.makedirs(cache, exist_ok=True)
        out = os.path.join(cache, "combo-chevron.png")
        if image.save(out):
            _chevron_icon_path = out.replace("\\", "/")
            return _chevron_icon_path
    except OSError:
        return None
    return None


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
    # Bestemmingen (#3a) — tabel, badges, amber-hints en iconen.
    "muted_label": "#7A8494",
    "icon_muted": "#A9B2BD",
    "row_system": "#F6F7F9",
    "row_active": "#EFF6FD",
    "row_active_border": "#E1EDF8",
    "row_divider": "#F0F2F5",
    "col_header_bg": "#FAFBFC",
    "system_badge_bg": "#E7EAEE",
    "amber_bg": "#FFF6E5",
    "amber_border": "#F2DBA8",
    "amber_text": "#7A5200",
    "amber_icon": "#9A6700",
    "danger_text": "#A8261A",
    "danger_border_soft": "#E7C7C2",
    "mono": "Consolas, 'Courier New', monospace",
    # Meeting Buddy (#1a) — succes/info banners.
    "success_bg": "#EAF6EE",
    "success_border": "#BCE0C9",
    "success_text": "#0C5B2E",
}


def build_qss(
    tokens: dict[str, str] | None = None,
    check_icon: str | None = None,
    chevron_icon: str | None = None,
) -> str:
    """Build the shared stylesheet from the supplied colour tokens."""
    t = tokens or TOKENS
    check_image = f"image: url({check_icon});" if check_icon else ""
    chevron = (
        f"QComboBox::drop-down {{ subcontrol-origin: padding; subcontrol-position: center right;"
        f" width: 24px; border: none; background: transparent; }}"
        f" QComboBox::down-arrow {{ image: url({chevron_icon}); width: 12px; height: 12px; }}"
        if chevron_icon
        else ""
    )
    return f"""
    {chevron}
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
        background: {t["surface_footer"]}; border-top: 1px solid {t["border_subtle"]};
    }}
    QFrame#settingsSection {{
        border: none; border-top: 1px solid #F0F2F5;
    }}
    QLabel#fieldLabel {{
        color: {t["text_secondary"]}; font-size: 12.5px;
    }}
    QLabel#hintLabel {{
        color: {t["muted_soft"]}; font-size: 11.5px;
    }}
    QLabel#keycap {{
        min-width: 34px; min-height: 26px; padding: 0 8px;
        border: 1px solid {t["border_strong"]}; border-bottom-width: 2px;
        border-radius: 4px; background: {t["page"]};
        color: {t["text_secondary"]}; font-size: 11.5px; font-weight: 600;
    }}
    QLabel#keycapPlus {{
        color: #A9B2BD; font-size: 11px; padding: 0 2px;
    }}
    QCheckBox::indicator {{
        width: 16px; height: 16px; border-radius: 3px;
        border: 1.5px solid {t["icon_muted"]}; background: {t["surface"]};
    }}
    QCheckBox::indicator:checked {{
        border: 1.5px solid {t["accent"]}; background: {t["accent"]}; {check_image}
    }}
    QCheckBox#switch::indicator {{
        width: 34px; height: 19px; border: none; image: none;
    }}
    QCheckBox#switch::indicator:unchecked {{
        border-radius: 10px; background: {t["border_strong"]}; image: none;
    }}
    QCheckBox#switch::indicator:checked {{
        border-radius: 10px; background: {t["accent"]}; image: none;
    }}
    QRadioButton::indicator {{
        width: 16px; height: 16px; border-radius: 9px;
        border: 1.5px solid {t["icon_muted"]}; background: {t["surface"]};
    }}
    QRadioButton::indicator:checked {{
        border: 1.5px solid {t["accent"]};
        background: qradialgradient(cx:0.5, cy:0.5, radius:0.5, fx:0.5, fy:0.5,
            stop:0 {t["accent"]}, stop:0.42 {t["accent"]},
            stop:0.5 {t["surface"]}, stop:1 {t["surface"]});
    }}

    /* --- Bestemmingen #3a --- */
    QFrame#destIntro {{
        background: {t["page"]}; border: none;
        border-bottom: 1px solid {t["border_subtle"]};
    }}
    QLabel#introBadge {{
        min-width: 26px; max-width: 26px; min-height: 26px; max-height: 26px;
        border-radius: 13px; background: {t["accent_soft"]};
        color: {t["accent"]}; font-size: 13px; font-weight: 700;
    }}
    QLabel#introLine {{ color: {t["text_secondary"]}; font-size: 12.5px; }}
    QLabel#introLineMuted {{ color: {t["muted_soft"]}; font-size: 12.5px; }}

    QFrame#destColHeaderRow {{
        background: {t["col_header_bg"]};
        border-bottom: 1px solid {t["border_card"]};
    }}
    QLabel#destColHead {{
        color: {t["muted_label"]}; font-size: 11px; font-weight: 600;
        letter-spacing: 0.06em;
    }}

    QFrame#destRow {{
        background: transparent; border: 2px solid transparent; border-radius: 4px;
    }}
    QFrame#destRow[rowKind="system"] {{ background: {t["row_system"]}; }}
    QFrame#destRow[rowKind="active"] {{ background: {t["row_active"]}; }}
    QFrame#destRow[selected="true"] {{ border: 2px solid {t["accent"]}; }}
    QFrame#destDivider {{ background: {t["row_divider"]}; border: none; }}
    QFrame#destStrip {{ background: {t["accent"]}; border: none; }}

    QLabel#destName {{ font-size: 13.5px; font-weight: 600; color: {t["text"]}; }}
    QLabel#destNameMuted {{
        font-size: 13.5px; font-weight: 600; color: {t["text_secondary"]};
    }}
    QLabel#destPath {{
        font-size: 11.5px; color: {t["muted"]}; font-family: {t["mono"]};
    }}
    QLabel#destPathMuted {{ font-size: 11.5px; color: {t["muted_soft"]}; }}
    QLabel#destCell {{ font-size: 12.5px; color: {t["text_secondary"]}; }}
    QLabel#destCellMuted {{ font-size: 12.5px; color: {t["muted"]}; }}
    QLabel#systemBadge {{
        color: {t["muted_soft"]}; background: {t["system_badge_bg"]};
        font-size: 10px; font-weight: 600; letter-spacing: 0.04em;
        padding: 2px 5px; border-radius: 3px;
    }}
    QLabel#activePill {{
        color: white; background: {t["accent"]};
        font-size: 10.5px; font-weight: 600;
        padding: 2px 8px; border-radius: 10px;
    }}

    QFrame#destActions {{
        background: {t["surface_card_off"]};
        border-top: 1px solid {t["border_subtle"]};
    }}
    QPushButton#danger {{
        background: {t["surface"]}; border: 1px solid {t["border_strong"]};
        border-radius: {t["radius_button"]}; color: {t["danger"]};
    }}
    QPushButton#danger:hover {{
        background: {t["danger_hover"]}; border-color: {t["danger_border_soft"]};
    }}
    QPushButton#danger:disabled {{
        color: {t["icon_muted"]}; background: {t["surface_card_off"]};
        border-color: {t["border_card"]};
    }}
    QPushButton#link {{
        background: transparent; border: none; color: {t["accent"]};
        padding: 2px 2px; min-height: 0; text-align: left;
    }}
    QPushButton#link:hover {{ color: {t["accent_hover"]}; }}
    QPushButton#link:disabled {{ color: {t["muted_soft"]}; }}
    QLabel#footerNote {{ color: {t["muted_soft"]}; font-size: 11.5px; }}

    QLabel#fieldTitle {{ font-size: 12.5px; font-weight: 600; color: {t["text"]}; }}
    QLabel#reqStar {{ color: {t["danger"]}; font-size: 12.5px; font-weight: 600; }}
    QLabel#fieldError {{ color: {t["danger_text"]}; font-size: 11.5px; }}
    QLineEdit[error="true"] {{ border: 1px solid {t["danger"]}; }}
    QFrame#appendGroup {{
        border: none; border-left: 1px solid {t["row_active_border"]};
    }}
    QFrame#reservedInfo {{
        background: {t["amber_bg"]}; border: 1px solid {t["amber_border"]};
        border-radius: {t["radius_button"]};
    }}
    QLabel#reservedInfoText {{ color: {t["amber_text"]}; font-size: 11.5px; }}
    QLabel#emptyTitle {{ font-size: 13.5px; font-weight: 600; color: {t["text"]}; }}
    QLabel#emptyBody {{ font-size: 12.5px; color: {t["muted"]}; }}

    /* --- Meeting Buddy #1a banners --- */
    QFrame#successBanner {{
        background: {t["success_bg"]}; border: 1px solid {t["success_border"]};
        border-radius: {t["radius_button"]};
    }}
    QLabel#successText {{ color: {t["success_text"]}; font-size: 12px; }}
    QLabel#mbTitle {{ font-size: 13px; font-weight: 600; color: {t["text"]}; }}
    QLabel#mbDesc {{ color: {t["muted_soft"]}; font-size: 11.5px; }}
    """


def apply_theme(app: QApplication) -> None:
    """Apply praatMaar's shared stylesheet to ``app``."""
    app.setStyleSheet(
        build_qss(check_icon=_checkbox_check_icon(), chevron_icon=_combo_chevron_icon())
    )
