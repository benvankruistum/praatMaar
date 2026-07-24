"""Design tokens and light helpers for praatMaar Tk dialogs (canvas UI)."""

from __future__ import annotations

from typing import Any

# --- Surfaces ---
COLOR_PAGE = "#E9EDF2"
COLOR_SURFACE = "#FFFFFF"
COLOR_SURFACE_MUTED = "#F7F9FB"
COLOR_SURFACE_FOOTER = "#F6F8FA"
COLOR_CARD_OFF = "#FCFDFD"
COLOR_CARD_OFF_BORDER = "#E4E7EC"

# --- Text ---
COLOR_TEXT = "#1B1F24"
COLOR_TEXT_SECONDARY = "#3B4652"
COLOR_TEXT_MUTED = "#5A6572"
COLOR_TEXT_DIM = "#8A94A0"
COLOR_TEXT_FAINT = "#A9B2BD"

# --- Borders ---
COLOR_BORDER = "#E1E5EA"
COLOR_BORDER_SOFT = "#EDEFF3"
COLOR_BORDER_DIALOG = "#D6DBE1"

# --- Accent (Windows 11 blue family) ---
COLOR_ACCENT = "#0F6CBD"
COLOR_ACCENT_HOVER = "#0A5CA3"
COLOR_ACCENT_SOFT = "#EAF3FC"
COLOR_ACCENT_BORDER = "#BCD9F5"
COLOR_ACCENT_DARK = "#0A4C86"

# --- Status ---
COLOR_OK = "#0F7B3E"
COLOR_OK_TEXT = "#0C5B2E"
COLOR_WARN = "#9A6700"
COLOR_WARN_BG = "#FFF6E5"
COLOR_WARN_BORDER = "#F2DBA8"
COLOR_DANGER = "#C42B1C"
COLOR_DANGER_SOFT = "#FFEBEE"
COLOR_DANGER_TEXT = "#B71C1C"
COLOR_AMBER = "#FFB020"

# --- Pill (dark HUD) ---
COLOR_PILL_BG = "#1C1F23"
COLOR_PILL_TEXT = "#F1F3F4"
COLOR_PILL_MUTED = "#9AA0A6"
COLOR_PILL_RECORDING = "#FF4D4D"
COLOR_PILL_TRANSCRIBING = "#FFB020"
COLOR_PILL_ERROR = "#FF5252"
COLOR_PILL_MEETING = "#0F6CBD"

# --- Typography ---
FONT_UI = ("Segoe UI", 10)
FONT_UI_BOLD = ("Segoe UI Semibold", 10)
FONT_UI_SMALL = ("Segoe UI", 9)
FONT_UI_SMALL_BOLD = ("Segoe UI Semibold", 9)
FONT_UI_TINY = ("Segoe UI", 8)
FONT_UI_TINY_BOLD = ("Segoe UI Semibold", 8)
FONT_TITLE = ("Segoe UI Semibold", 11)
FONT_SECTION = ("Segoe UI Semibold", 8)
FONT_NAME = ("Segoe UI Semibold", 10)

EXPERIMENTAL_MODULE_IDS = frozenset({"meeting-buddy", "local-llm"})

MODULE_DEPENDENCY_HINT_KEYS = {
    "meeting-buddy": "modules.meeting_buddy.dependency_hint",
    "local-llm": "modules.local_llm.dependency_hint",
}


def apply_dialog_style(root: Any) -> None:
    """Apply a light ttk theme tuned to the canvas tokens (best-effort)."""

    from tkinter import ttk

    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except Exception:
        pass

    style.configure("TFrame", background=COLOR_SURFACE)
    style.configure("TLabel", background=COLOR_SURFACE, foreground=COLOR_TEXT, font=FONT_UI)
    style.configure("TCheckbutton", background=COLOR_SURFACE, foreground=COLOR_TEXT, font=FONT_UI)
    style.configure("TRadiobutton", background=COLOR_SURFACE, foreground=COLOR_TEXT, font=FONT_UI)
    style.configure("TButton", font=FONT_UI, padding=(10, 4))
    style.configure(
        "Primary.TButton",
        font=FONT_UI_BOLD,
        background=COLOR_ACCENT,
        foreground="#FFFFFF",
        padding=(14, 5),
    )
    style.map(
        "Primary.TButton",
        background=[("active", COLOR_ACCENT_HOVER), ("pressed", COLOR_ACCENT_HOVER)],
        foreground=[("disabled", "#FFFFFF")],
    )
    style.configure("Ghost.TButton", font=FONT_UI, padding=(10, 4))
    style.configure(
        "Muted.TLabel",
        background=COLOR_SURFACE,
        foreground=COLOR_TEXT_MUTED,
        font=FONT_UI_SMALL,
    )
    style.configure(
        "Dim.TLabel",
        background=COLOR_SURFACE,
        foreground=COLOR_TEXT_DIM,
        font=FONT_UI_TINY,
    )
    style.configure(
        "Section.TLabel",
        background=COLOR_SURFACE,
        foreground=COLOR_TEXT_DIM,
        font=FONT_SECTION,
    )
    style.configure(
        "Title.TLabel",
        background=COLOR_SURFACE,
        foreground=COLOR_TEXT,
        font=FONT_TITLE,
    )
    style.configure("TNotebook", background=COLOR_SURFACE, borderwidth=0)
    style.configure("TNotebook.Tab", font=FONT_UI, padding=(12, 6))
    style.map(
        "TNotebook.Tab",
        background=[("selected", COLOR_SURFACE), ("!selected", COLOR_SURFACE_MUTED)],
        foreground=[("selected", COLOR_ACCENT), ("!selected", COLOR_TEXT_MUTED)],
    )
    style.configure("TEntry", fieldbackground=COLOR_SURFACE, foreground=COLOR_TEXT)
    style.configure("TCombobox", fieldbackground=COLOR_SURFACE, foreground=COLOR_TEXT)


def section_label(parent: Any, text: str, *, row: int, column: int = 0, **grid_opts: Any) -> Any:
    """Uppercase-ish section heading used across dialogs."""

    from tkinter import ttk

    label = ttk.Label(parent, text=text.upper(), style="Section.TLabel")
    opts = {"sticky": "w", "pady": (8, 4)}
    opts.update(grid_opts)
    label.grid(row=row, column=column, **opts)
    return label


def footer_bar(
    parent: Any,
    *,
    on_cancel: Any,
    on_save: Any,
    cancel_text: str,
    save_text: str,
    status_var: Any | None = None,
) -> Any:
    """Standard Annuleren + Opslaan footer; optional status label on the left."""

    import tkinter as tk
    from tkinter import ttk

    bar = tk.Frame(parent, background=COLOR_SURFACE_FOOTER, highlightthickness=0)
    bar.columnconfigure(0, weight=1)

    if status_var is not None:
        ttk.Label(
            bar,
            textvariable=status_var,
            foreground=COLOR_OK_TEXT,
            background=COLOR_SURFACE_FOOTER,
            font=FONT_UI_TINY,
        ).grid(row=0, column=0, sticky="w", padx=12, pady=10)

    btns = ttk.Frame(bar)
    btns.grid(row=0, column=1, sticky="e", padx=12, pady=8)
    ttk.Button(btns, text=cancel_text, style="Ghost.TButton", command=on_cancel).grid(
        row=0, column=0, padx=(0, 8)
    )
    ttk.Button(btns, text=save_text, style="Primary.TButton", command=on_save).grid(row=0, column=1)
    return bar
