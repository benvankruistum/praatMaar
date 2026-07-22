"""Meeting prep dialog: agenda plus loopback output selection."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import i18n

from .devices import list_loopback_output_devices
from .prep import parse_agenda


@dataclass(frozen=True)
class MeetingPrepResult:
    agenda_text: str
    enable_loopback: bool
    loopback_device: int | None


def show_meeting_prep_dialog(
    *,
    agenda_text: str = "",
    enable_loopback: bool = True,
    loopback_device: int | None = None,
    parent: Any = None,
) -> MeetingPrepResult | None:
    """Show prep UI; return ``None`` when the user cancels."""

    import tkinter as tk
    from tkinter import scrolledtext, ttk

    devices = list_loopback_output_devices()
    device_labels = [label for label, _ in devices]
    device_value_by_label = {label: value for label, value in devices}
    device_label_by_value = {value: label for label, value in devices}
    current_device_label = device_label_by_value.get(loopback_device, device_labels[0])

    dlg = tk.Toplevel(parent)
    dlg.withdraw()
    dlg.title(i18n.t("modules.meeting_buddy.dialog.title"))
    dlg.resizable(False, False)
    dlg.columnconfigure(0, weight=1)

    frame = ttk.Frame(dlg, padding=12)
    frame.grid(row=0, column=0, sticky="nsew")
    frame.columnconfigure(0, weight=1)

    ttk.Label(
        frame,
        text=i18n.t("modules.meeting_buddy.dialog.agenda_heading"),
        wraplength=420,
    ).grid(row=0, column=0, sticky="w", pady=(0, 4))

    agenda = scrolledtext.ScrolledText(frame, width=52, height=8, wrap="word")
    agenda.grid(row=1, column=0, sticky="ew", pady=(0, 4))
    if agenda_text:
        agenda.insert("1.0", agenda_text)

    topic_count = tk.StringVar()
    ttk.Label(frame, textvariable=topic_count).grid(row=2, column=0, sticky="w", pady=(0, 10))

    def refresh_topic_count() -> None:
        count = len(parse_agenda(agenda.get("1.0", "end")))
        topic_count.set(i18n.t("modules.meeting_buddy.dialog.topic_count", count=count))

    agenda.bind("<KeyRelease>", lambda _event: refresh_topic_count())
    refresh_topic_count()

    loopback_var = tk.BooleanVar(value=enable_loopback)
    ttk.Checkbutton(
        frame,
        text=i18n.t("modules.meeting_buddy.settings.enable_loopback"),
        variable=loopback_var,
    ).grid(row=3, column=0, sticky="w", pady=(0, 4))

    ttk.Label(
        frame,
        text=i18n.t("modules.meeting_buddy.settings.loopback_output"),
    ).grid(row=4, column=0, sticky="w", pady=(0, 2))

    device_var = tk.StringVar(value=current_device_label)
    device_combo = ttk.Combobox(
        frame,
        textvariable=device_var,
        values=device_labels,
        state="readonly",
        width=48,
    )
    device_combo.grid(row=5, column=0, sticky="ew", pady=(0, 10))

    def _sync_loopback_controls() -> None:
        state = "readonly" if loopback_var.get() else "disabled"
        device_combo.configure(state=state)

    loopback_var.trace_add("write", lambda *_args: _sync_loopback_controls())
    _sync_loopback_controls()

    result: MeetingPrepResult | None = None

    def confirm() -> None:
        nonlocal result
        selected_device = device_value_by_label.get(device_var.get(), loopback_device)
        result = MeetingPrepResult(
            agenda_text=agenda.get("1.0", "end").strip(),
            enable_loopback=bool(loopback_var.get()),
            loopback_device=selected_device if loopback_var.get() else None,
        )
        dlg.destroy()

    def cancel() -> None:
        dlg.destroy()

    buttons = ttk.Frame(frame)
    buttons.grid(row=6, column=0, sticky="e")
    ttk.Button(buttons, text=i18n.t("modules.meeting_buddy.dialog.cancel"), command=cancel).grid(
        row=0, column=0, padx=(0, 8)
    )
    ttk.Button(
        buttons,
        text=i18n.t("modules.meeting_buddy.dialog.start"),
        command=confirm,
    ).grid(row=0, column=1)

    dlg.protocol("WM_DELETE_WINDOW", cancel)
    dlg.bind("<Escape>", lambda _event: cancel())
    dlg.bind("<Control-Return>", lambda _event: confirm())

    dlg.update_idletasks()
    width = max(dlg.winfo_reqwidth(), 460)
    height = max(dlg.winfo_reqheight(), 360)
    x = (dlg.winfo_screenwidth() - width) // 2
    y = (dlg.winfo_screenheight() - height) // 3
    dlg.geometry(f"{width}x{height}+{x}+{y}")
    dlg.deiconify()
    dlg.lift()
    dlg.attributes("-topmost", True)
    dlg.after(300, lambda: dlg.attributes("-topmost", False))
    dlg.grab_set()
    dlg.focus_force()
    agenda.focus_set()
    dlg.wait_window()
    return result
