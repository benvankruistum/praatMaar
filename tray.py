"""Compatibility facade for the Qt system-tray implementation."""

from ui.tray import (
    TrayIcon,
    _draw_attention_badge,
    _make_icon,
    build_context_menu_entries,
)

__all__ = [
    "TrayIcon",
    "_draw_attention_badge",
    "_make_icon",
    "build_context_menu_entries",
]
