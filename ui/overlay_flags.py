"""Shared Qt window configuration for non-activating HUDs."""

from __future__ import annotations

import sys

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget


def apply_hud_window_flags(widget: QWidget) -> None:
    """Configure ``widget`` as a frameless, always-on-top, non-activating HUD.

    macOS may still require a thin native ``NSPanel`` seam if a live acceptance
    check shows that the application activates despite these Qt flags.
    """
    widget.setWindowFlags(
        Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.WindowDoesNotAcceptFocus
    )
    widget.setAttribute(Qt.WA_ShowWithoutActivating)
    if sys.platform == "darwin":
        widget.setAttribute(Qt.WA_MacAlwaysShowToolWindow)
