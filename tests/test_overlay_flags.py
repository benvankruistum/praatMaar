import sys

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget

from ui.app import ensure_app
from ui.overlay_flags import apply_hud_window_flags


def test_apply_hud_window_flags_configures_non_activating_hud():
    ensure_app([])
    widget = QWidget()

    apply_hud_window_flags(widget)

    flags = widget.windowFlags()
    assert flags & Qt.Tool
    assert flags & Qt.FramelessWindowHint
    assert flags & Qt.WindowStaysOnTopHint
    assert flags & Qt.WindowDoesNotAcceptFocus
    assert widget.testAttribute(Qt.WA_ShowWithoutActivating)
    if sys.platform == "darwin":
        assert widget.testAttribute(Qt.WA_MacAlwaysShowToolWindow)
