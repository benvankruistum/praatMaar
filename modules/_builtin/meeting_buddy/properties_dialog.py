"""Meeting Buddy properties dialog: loopback output selection."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import i18n

from .devices import list_loopback_output_devices


@dataclass(frozen=True)
class PropertiesResult:
    enable_loopback: bool
    loopback_device: int | None


def device_selection_maps(
    devices: list[tuple[str, int | None]],
    loopback_device: int | None,
) -> tuple[list[str], dict[str, int | None], dict[int | None, str], str]:
    device_labels = [label for label, _ in devices]
    device_value_by_label = {label: value for label, value in devices}
    device_label_by_value = {value: label for label, value in devices}
    default_label = device_labels[0] if device_labels else ""
    current_device_label = device_label_by_value.get(loopback_device, default_label)
    return device_labels, device_value_by_label, device_label_by_value, current_device_label


def build_properties_result(
    *,
    enable_loopback: bool,
    selected_device_label: str,
    device_value_by_label: dict[str, int | None],
    fallback_device: int | None,
) -> PropertiesResult:
    selected_device = device_value_by_label.get(selected_device_label, fallback_device)
    return PropertiesResult(
        enable_loopback=enable_loopback,
        loopback_device=selected_device if enable_loopback else None,
    )


def show_properties_dialog(
    *,
    enable_loopback: bool,
    loopback_device: int | None,
    parent: Any = None,
) -> PropertiesResult | None:
    """Show loopback settings; return ``None`` when the user cancels."""

    import tkinter as tk
    from tkinter import ttk

    devices = list_loopback_output_devices()
    device_labels, device_value_by_label, _, current_device_label = device_selection_maps(
        devices,
        loopback_device,
    )

    dlg = tk.Toplevel(parent)
    dlg.withdraw()
    dlg.title(i18n.t("modules.meeting_buddy.dialog.title"))
    dlg.resizable(False, False)
    dlg.columnconfigure(0, weight=1)

    frame = ttk.Frame(dlg, padding=12)
    frame.grid(row=0, column=0, sticky="nsew")
    frame.columnconfigure(0, weight=1)

    loopback_var = tk.BooleanVar(value=enable_loopback)
    ttk.Checkbutton(
        frame,
        text=i18n.t("modules.meeting_buddy.settings.enable_loopback"),
        variable=loopback_var,
    ).grid(row=0, column=0, sticky="w", pady=(0, 4))

    ttk.Label(
        frame,
        text=i18n.t("modules.meeting_buddy.settings.loopback_output"),
    ).grid(row=1, column=0, sticky="w", pady=(0, 2))

    device_var = tk.StringVar(value=current_device_label)
    device_combo = ttk.Combobox(
        frame,
        textvariable=device_var,
        values=device_labels,
        state="readonly",
        width=48,
    )
    device_combo.grid(row=2, column=0, sticky="ew", pady=(0, 10))

    def _sync_loopback_controls() -> None:
        state = "readonly" if loopback_var.get() else "disabled"
        device_combo.configure(state=state)

    loopback_var.trace_add("write", lambda *_args: _sync_loopback_controls())
    _sync_loopback_controls()

    result: PropertiesResult | None = None

    def confirm() -> None:
        nonlocal result
        result = build_properties_result(
            enable_loopback=bool(loopback_var.get()),
            selected_device_label=device_var.get(),
            device_value_by_label=device_value_by_label,
            fallback_device=loopback_device,
        )
        dlg.destroy()

    def cancel() -> None:
        dlg.destroy()

    buttons = ttk.Frame(frame)
    buttons.grid(row=3, column=0, sticky="e")
    ttk.Button(buttons, text=i18n.t("modules.meeting_buddy.dialog.cancel"), command=cancel).grid(
        row=0, column=0, padx=(0, 8)
    )
    ttk.Button(
        buttons,
        text=i18n.t("modules.meeting_buddy.dialog.save"),
        command=confirm,
    ).grid(row=0, column=1)

    dlg.protocol("WM_DELETE_WINDOW", cancel)
    dlg.bind("<Escape>", lambda _event: cancel())
    dlg.bind("<Control-Return>", lambda _event: confirm())

    dlg.update_idletasks()
    width = max(dlg.winfo_reqwidth(), 460)
    height = max(dlg.winfo_reqheight(), 160)
    x = (dlg.winfo_screenwidth() - width) // 2
    y = (dlg.winfo_screenheight() - height) // 3
    dlg.geometry(f"{width}x{height}+{x}+{y}")
    dlg.deiconify()
    dlg.lift()
    dlg.attributes("-topmost", True)
    dlg.after(300, lambda: dlg.attributes("-topmost", False))
    dlg.grab_set()
    dlg.focus_force()
    device_combo.focus_set()
    dlg.wait_window()
    return result
