"""Meeting Buddy properties dialog: loopback output and transcript folder."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import i18n

from .devices import list_loopback_output_devices
from .transcript_journal import transcripts_dir


@dataclass(frozen=True)
class PropertiesResult:
    enable_loopback: bool
    loopback_device: int | None
    transcripts_directory: str | None


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
    transcripts_directory: str | None,
) -> PropertiesResult:
    selected_device = device_value_by_label.get(selected_device_label, fallback_device)
    folder = transcripts_directory.strip() if transcripts_directory else None
    return PropertiesResult(
        enable_loopback=enable_loopback,
        loopback_device=selected_device if enable_loopback else None,
        transcripts_directory=folder or None,
    )


def show_properties_dialog(
    *,
    enable_loopback: bool,
    loopback_device: int | None,
    transcripts_directory: str | None = None,
    app_dir: Path | None = None,
    parent: Any = None,
) -> PropertiesResult | None:
    """Show loopback + transcript folder settings; return ``None`` on cancel."""

    import tkinter as tk
    from tkinter import filedialog, ttk

    devices = list_loopback_output_devices()
    device_labels, device_value_by_label, _, current_device_label = device_selection_maps(
        devices,
        loopback_device,
    )
    default_transcripts = str(transcripts_dir(app_dir)) if app_dir is not None else ""

    from ui_icon import apply_window_icon

    dlg = tk.Toplevel(parent)
    dlg.withdraw()
    dlg.title(i18n.t("modules.meeting_buddy.dialog.title"))
    apply_window_icon(dlg)
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

    ttk.Label(
        frame,
        text=i18n.t("modules.meeting_buddy.settings.transcripts_directory"),
    ).grid(row=3, column=0, sticky="w", pady=(0, 2))
    folder_row = ttk.Frame(frame)
    folder_row.grid(row=4, column=0, sticky="ew", pady=(0, 4))
    folder_row.columnconfigure(0, weight=1)
    folder_var = tk.StringVar(value=transcripts_directory or "")
    folder_entry = ttk.Entry(folder_row, textvariable=folder_var, width=44)
    folder_entry.grid(row=0, column=0, sticky="ew", padx=(0, 8))

    def browse_folder() -> None:
        initial = folder_var.get().strip() or default_transcripts or None
        chosen = filedialog.askdirectory(
            parent=dlg,
            title=i18n.t("modules.meeting_buddy.settings.transcripts_browse"),
            initialdir=initial or None,
        )
        if chosen:
            folder_var.set(chosen)

    ttk.Button(
        folder_row,
        text=i18n.t("modules.meeting_buddy.settings.transcripts_browse"),
        command=browse_folder,
    ).grid(row=0, column=1)

    ttk.Label(
        frame,
        text=i18n.t(
            "modules.meeting_buddy.settings.transcripts_directory_hint",
            path=default_transcripts or "…/meeting-buddy/transcripts",
        ),
        wraplength=420,
        foreground="#5f6368",
    ).grid(row=5, column=0, sticky="w", pady=(0, 10))

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
            transcripts_directory=folder_var.get(),
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
        text=i18n.t("modules.meeting_buddy.dialog.save"),
        command=confirm,
    ).grid(row=0, column=1)

    dlg.protocol("WM_DELETE_WINDOW", cancel)
    dlg.bind("<Escape>", lambda _event: cancel())
    dlg.bind("<Control-Return>", lambda _event: confirm())

    dlg.update_idletasks()
    width = max(dlg.winfo_reqwidth(), 480)
    height = max(dlg.winfo_reqheight(), 220)
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
