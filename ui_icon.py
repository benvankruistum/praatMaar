"""Shared praatMaar mic icon for tkinter windows and tray."""

from __future__ import annotations

from typing import Any

from PIL import Image, ImageDraw, ImageTk


def make_mic_image(
    color: tuple[int, int, int, int] = (32, 33, 36, 255),
    *,
    size: int = 64,
) -> Image.Image:
    """Draw a microphone silhouette in ``color`` on a transparent background."""

    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    scale = size / 24.0

    def s(value: float) -> float:
        return value * scale

    width = max(1, int(s(2)))

    draw.rounded_rectangle([s(9), s(3), s(15), s(14)], radius=s(3), fill=color)
    draw.arc([s(6), s(5), s(18), s(17)], start=0, end=180, fill=color, width=width)
    draw.line([s(12), s(17), s(12), s(20)], fill=color, width=width)
    draw.line([s(9), s(20), s(15), s(20)], fill=color, width=width)

    return img


def apply_window_icon(window: Any) -> None:
    """Set the praatMaar mic icon on a tkinter ``Toplevel`` or ``Tk``."""

    photo = ImageTk.PhotoImage(make_mic_image())
    window._praatmaar_icon = photo
    window.iconphoto(True, photo)
