"""Tests for shared mic window icon."""

from __future__ import annotations

import tkinter as tk

from ui_icon import apply_window_icon, make_mic_image


def test_make_mic_image_default_size_and_alpha() -> None:
    img = make_mic_image()
    assert img.size == (64, 64)
    assert img.mode == "RGBA"
    assert img.getpixel((0, 0))[3] == 0
    assert img.getpixel((32, 32))[3] == 255


def test_make_mic_image_custom_color_and_size() -> None:
    img = make_mic_image((255, 0, 0, 128), size=32)
    assert img.size == (32, 32)
    assert img.getpixel((16, 16)) == (255, 0, 0, 128)


def test_apply_window_icon_sets_photo_reference() -> None:
    root = tk.Tk()
    root.withdraw()
    try:
        apply_window_icon(root)
        assert hasattr(root, "_praatmaar_icon")
        assert root._praatmaar_icon is not None
    finally:
        root.destroy()
