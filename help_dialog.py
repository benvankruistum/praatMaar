"""
Help-venster voor praatMaar (tkinter `Toplevel`).

Laadt gebruikersdocumentatie uit `docs/user/help.<taal>.md`, zet een beperkt
markdown-subset om naar leesbare tekst, en toont die in een readonly
ScrolledText. Geopend vanuit het systeemvak-menu.
"""

from __future__ import annotations

import re
import sys
import tkinter as tk
from pathlib import Path
from tkinter import scrolledtext, ttk

import i18n

_open_dialog: tk.Toplevel | None = None

_BOLD_RE = re.compile(r"\*\*(.+?)\*\*")
_ITALIC_RE = re.compile(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)")
_CODE_RE = re.compile(r"`([^`]+)`")
_LINK_RE = re.compile(r"\[([^\]]+)\]\([^)]+\)")


def user_docs_dir() -> Path:
    """Pad naar `docs/user/` — PyInstaller-bundle of repo-root."""

    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / "docs" / "user"  # type: ignore[attr-defined]
    return Path(__file__).resolve().parent / "docs" / "user"


def help_file_path(language: str | None = None) -> Path:
    code = i18n.normalize_language(language or i18n.ui_language())
    return user_docs_dir() / f"help.{code}.md"


def _inline_markdown(text: str) -> str:
    """Verwijdert inline markdown-markeringen (bold/italic/code/links)."""

    text = _BOLD_RE.sub(r"\1", text)
    text = _ITALIC_RE.sub(r"\1", text)
    text = _CODE_RE.sub(r"\1", text)
    text = _LINK_RE.sub(r"\1", text)
    return text


def markdown_to_plain(source: str) -> str:
    """
    Zet een beperkt markdown-subset om naar leesbare platte tekst.

    Ondersteunt: koppen, lijsten, tabellen, bold/italic/code/links.
    Bewust geen volledige markdown-parser (geen extra dependency).
    """

    out: list[str] = []
    for raw in source.splitlines():
        stripped = raw.strip()
        if not stripped:
            if out and out[-1] != "":
                out.append("")
            continue

        if stripped.startswith("|") and stripped.endswith("|"):
            cells = [cell.strip() for cell in stripped.strip("|").split("|")]
            if cells and all(re.fullmatch(r":?-{3,}:?", cell or "") for cell in cells):
                continue
            out.append(" — ".join(_inline_markdown(cell) for cell in cells if cell))
            continue

        if stripped.startswith("#"):
            title = stripped.lstrip("#").strip()
            if out and out[-1] != "":
                out.append("")
            out.append(_inline_markdown(title))
            out.append("")
            continue

        if stripped.startswith("- "):
            out.append(f"• {_inline_markdown(stripped[2:])}")
            continue

        if set(stripped) <= {"-", "*", "_"} and len(stripped) >= 3:
            continue

        out.append(_inline_markdown(stripped))

    while out and out[-1] == "":
        out.pop()
    return "\n".join(out)


def load_help_text(language: str | None = None) -> str:
    """Leest help-markdown voor `language`; fallback naar korte i18n-string."""

    path = help_file_path(language)
    try:
        return markdown_to_plain(path.read_text(encoding="utf-8"))
    except OSError:
        return i18n.t("help.fallback")


def _help_font() -> tuple:
    if sys.platform == "darwin":
        return ("Helvetica Neue", 12)
    return ("Segoe UI", 10)


def open_help(parent: tk.Misc, *, wait: bool = False) -> None:
    global _open_dialog

    if _open_dialog is not None and _open_dialog.winfo_exists():
        _open_dialog.lift()
        _open_dialog.focus_force()
        if wait:
            parent.wait_window(_open_dialog)
        return

    win = tk.Toplevel(parent)
    win.withdraw()
    _open_dialog = win
    win.title(i18n.t("help.title"))
    win.resizable(True, True)
    win.minsize(480, 360)
    win.configure(padx=12, pady=12)
    win.columnconfigure(0, weight=1)
    win.rowconfigure(0, weight=1)

    text = scrolledtext.ScrolledText(
        win,
        wrap="word",
        font=_help_font(),
        state="disabled",
        borderwidth=1,
        relief="solid",
    )
    text.grid(row=0, column=0, sticky="nsew", pady=(0, 12))

    text.configure(state="normal")
    text.insert("1.0", load_help_text())
    text.configure(state="disabled")

    def close() -> None:
        global _open_dialog
        _open_dialog = None
        win.destroy()

    ttk.Button(win, text=i18n.t("help.close"), command=close).grid(row=1, column=0, sticky="e")

    win.protocol("WM_DELETE_WINDOW", close)

    win.update_idletasks()
    width = max(win.winfo_reqwidth(), 560)
    height = max(win.winfo_reqheight(), 480)
    x = (win.winfo_screenwidth() - width) // 2
    y = (win.winfo_screenheight() - height) // 3
    win.geometry(f"{width}x{height}+{x}+{y}")

    win.deiconify()
    win.lift()
    win.attributes("-topmost", True)
    win.after(300, lambda: win.attributes("-topmost", False))
    win.focus_force()

    if wait:
        parent.wait_window(win)
