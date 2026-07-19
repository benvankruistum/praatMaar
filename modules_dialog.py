"""
Modules-dialoog voor praatMaar (tkinter `Toplevel`).

Overzicht van ingebouwde modules (aan/uit) en incrementele transcriptie.
"""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from tkinter import ttk
from typing import Any

import i18n
from modules.registry import all_builtin_modules, modules_config_for_settings

_open_dialog: tk.Toplevel | None = None


def open_modules_dialog(
    parent: tk.Misc,
    current: dict[str, Any],
    on_apply: Callable[[dict[str, Any]], None],
    *,
    wait: bool = False,
) -> None:
    """Opent het modules-overzicht; bij Opslaan roept `on_apply` de bijgewerkte settings aan."""

    global _open_dialog

    if _open_dialog is not None and _open_dialog.winfo_exists():
        _open_dialog.lift()
        _open_dialog.focus_force()
        return

    modules_config = modules_config_for_settings(current.get("modules") or {})
    incremental = bool(current.get("incremental_transcription", False))

    dlg = tk.Toplevel(parent)
    _open_dialog = dlg
    dlg.withdraw()
    dlg.title(i18n.t("modules.title"))
    dlg.resizable(False, False)
    dlg.transient(parent)
    dlg.columnconfigure(0, weight=1)

    frame = ttk.Frame(dlg, padding=12)
    frame.grid(row=0, column=0, sticky="nsew")
    frame.columnconfigure(0, weight=1)

    ttk.Label(frame, text=i18n.t("modules.intro"), wraplength=420).grid(
        row=0, column=0, sticky="w", pady=(0, 12)
    )

    incremental_var = tk.BooleanVar(value=incremental)
    ttk.Checkbutton(
        frame,
        text=i18n.t("modules.incremental"),
        variable=incremental_var,
    ).grid(row=1, column=0, sticky="w", pady=(0, 8))

    ttk.Label(frame, text=i18n.t("modules.list_heading")).grid(
        row=2, column=0, sticky="w", pady=(4, 6)
    )

    module_vars: dict[str, tk.BooleanVar] = {}
    row = 3
    for module in all_builtin_modules():
        enabled = bool(modules_config.get(module.id, {}).get("enabled", module.default_enabled()))
        var = tk.BooleanVar(value=enabled)
        module_vars[module.id] = var

        box = ttk.LabelFrame(frame, text=i18n.t(module.display_name_key()), padding=8)
        box.grid(row=row, column=0, sticky="ew", pady=(0, 8))
        box.columnconfigure(0, weight=1)

        ttk.Checkbutton(
            box,
            text=i18n.t("modules.enabled"),
            variable=var,
        ).grid(row=0, column=0, sticky="w")
        ttk.Label(
            box,
            text=i18n.t(module.description_key()),
            wraplength=400,
            foreground="#5f6368",
        ).grid(row=1, column=0, sticky="w", pady=(4, 0))
        row += 1

    def save() -> None:
        updated_modules = {
            module_id: {"enabled": bool(var.get())} for module_id, var in module_vars.items()
        }
        on_apply(
            {
                **current,
                "incremental_transcription": bool(incremental_var.get()),
                "modules": updated_modules,
            }
        )
        dlg.destroy()

    def cancel() -> None:
        dlg.destroy()

    buttons = ttk.Frame(frame)
    buttons.grid(row=row, column=0, sticky="e", pady=(8, 0))
    ttk.Button(buttons, text=i18n.t("modules.cancel"), command=cancel).grid(
        row=0, column=0, padx=(0, 8)
    )
    ttk.Button(buttons, text=i18n.t("modules.save"), command=save).grid(row=0, column=1)

    dlg.protocol("WM_DELETE_WINDOW", cancel)

    def _on_destroy(_event: tk.Event) -> None:
        global _open_dialog
        if _open_dialog is dlg:
            _open_dialog = None

    dlg.bind("<Destroy>", _on_destroy)

    dlg.update_idletasks()
    dlg.deiconify()
    if wait:
        parent.wait_window(dlg)
