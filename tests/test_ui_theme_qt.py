from PySide6.QtCore import Qt
from PySide6.QtGui import QPalette

from ui.app import ensure_app
from ui.theme import TOKENS, apply_theme, build_qss, light_palette


def test_tokens_include_canvas_accent():
    assert TOKENS["accent"].upper() == "#0F6CBD"


def test_tokens_include_canvas_control_colours():
    assert TOKENS["border_strong"].upper() == "#D2D8DF"
    assert TOKENS["hover"].upper() == "#EFF2F6"
    assert TOKENS["text_secondary"].upper() == "#3B4652"


def test_build_qss_mentions_accent():
    qss = build_qss(TOKENS)
    assert "#0F6CBD" in qss or TOKENS["accent"] in qss
    assert TOKENS["border_strong"] in qss
    assert TOKENS["hover"] in qss


def test_build_qss_covers_tabs_and_checks():
    qss = build_qss(TOKENS)
    assert "QTabWidget::pane" in qss
    assert "QCheckBox, QRadioButton" in qss
    assert "QLabel#optionTitle" in qss


def test_light_palette_uses_canvas_surface():
    palette = light_palette()
    assert palette.color(QPalette.ColorRole.Window).name().upper() == TOKENS["surface"].upper()
    assert palette.color(QPalette.ColorRole.WindowText).name().upper() == TOKENS["text"].upper()


def test_apply_theme_pins_light_color_scheme():
    app = ensure_app([])
    apply_theme(app)
    hints = app.styleHints()
    if hasattr(hints, "colorScheme"):
        assert hints.colorScheme() == Qt.ColorScheme.Light
    assert (
        app.palette().color(QPalette.ColorRole.Window).name().upper() == TOKENS["surface"].upper()
    )
    assert TOKENS["text"] in app.styleSheet()
