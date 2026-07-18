"""
Instellingen-dialoog voor praatMaar (tkinter `Toplevel`).

Geopend vanuit het systeemvak-menu. Bevat o.a. microfoon, sneltoets, Whisper-
model, spraakherkenningstaal en interfacetaal. Bij Opslaan: `on_apply(...)`.
"""

from __future__ import annotations

import queue
import tkinter as tk
from tkinter import ttk
from typing import Any, Callable

import sounddevice as sd

import hotkeys
import i18n

MODELS = ["base", "small", "medium"]

# Voorkomt dat er meerdere dialogen tegelijk openen.
_open_dialog: "tk.Toplevel | None" = None


def _positions() -> list[tuple[str, str]]:
    return [
        (i18n.t("settings.position.top"), "boven-midden"),
        (i18n.t("settings.position.bottom"), "onder-midden"),
    ]


def _modes() -> list[tuple[str, str]]:
    return [
        (i18n.t("settings.mode.toggle"), "toggle"),
        (i18n.t("settings.mode.ptt"), "ptt"),
    ]


def _language_choices() -> list[tuple[str, str]]:
    return [
        (i18n.LANGUAGE_LABELS[code], code) for code in i18n.SUPPORTED_UI_LANGUAGES
    ]


def _input_devices() -> list[tuple[str, "int | None"]]:
    """(label, device-index) voor elk invoerapparaat; index None = Windows-standaard."""

    options: list[tuple[str, int | None]] = [(i18n.t("settings.mic.default"), None)]
    try:
        for index, device in enumerate(sd.query_devices()):
            if device.get("max_input_channels", 0) > 0:
                options.append((f"{index}: {device['name']}", index))
    except Exception:
        pass
    return options


def open_settings_dialog(
    root: "tk.Misc",
    current: dict[str, Any],
    on_apply: Callable[[dict[str, Any]], None],
    set_capture: "Callable[[Any | None], None] | None" = None,
) -> None:
    global _open_dialog

    if _open_dialog is not None and _open_dialog.winfo_exists():
        _open_dialog.lift()
        _open_dialog.focus_force()
        return

    win = tk.Toplevel(root)
    win.withdraw()
    _open_dialog = win
    win.title(i18n.t("settings.title"))
    win.resizable(False, False)
    win.configure(padx=18, pady=16)
    win.columnconfigure(0, weight=1)

    devices = _input_devices()
    device_labels = [label for label, _ in devices]
    current_device = current.get("microphone_device")
    device_label_by_value = {value: label for label, value in devices}
    current_device_label = device_label_by_value.get(
        current_device, device_labels[0]
    )

    row = 0

    def _section_label(text: str) -> None:
        nonlocal row
        ttk.Label(win, text=text).grid(row=row, column=0, sticky="w", pady=(0, 2))
        row += 1

    # Microfoon.
    _section_label(i18n.t("settings.microphone"))
    mic_var = tk.StringVar(value=current_device_label)
    ttk.Combobox(
        win, textvariable=mic_var, values=device_labels, state="readonly", width=42
    ).grid(row=row, column=0, sticky="ew", pady=(0, 12))
    row += 1

    # Pill-positie.
    positions = _positions()
    _section_label(i18n.t("settings.indicator_position"))
    pos_labels = [label for label, _ in positions]
    pos_value_by_label = {label: value for label, value in positions}
    pos_label_by_value = {value: label for label, value in positions}
    pos_var = tk.StringVar(
        value=pos_label_by_value.get(
            current.get("indicator_position"), pos_labels[0]
        )
    )
    ttk.Combobox(
        win, textvariable=pos_var, values=pos_labels, state="readonly", width=42
    ).grid(row=row, column=0, sticky="ew", pady=(0, 12))
    row += 1

    # Bedieningsmodus.
    modes = _modes()
    _section_label(i18n.t("settings.mode"))
    mode_labels = [label for label, _ in modes]
    mode_value_by_label = {label: value for label, value in modes}
    mode_label_by_value = {value: label for label, value in modes}
    mode_var = tk.StringVar(
        value=mode_label_by_value.get(current.get("mode"), mode_labels[0])
    )
    ttk.Combobox(
        win, textvariable=mode_var, values=mode_labels, state="readonly", width=42
    ).grid(row=row, column=0, sticky="ew", pady=(0, 12))
    row += 1

    # Spraakherkenning.
    lang_choices = _language_choices()
    lang_labels = [label for label, _ in lang_choices]
    lang_value_by_label = {label: value for label, value in lang_choices}
    lang_label_by_value = {value: label for label, value in lang_choices}
    speech_code = i18n.normalize_language(
        current.get("speech_language"),
        allowed=i18n.SUPPORTED_SPEECH_LANGUAGES,
    )
    _section_label(i18n.t("settings.speech_language"))
    speech_var = tk.StringVar(value=lang_label_by_value.get(speech_code, lang_labels[0]))
    ttk.Combobox(
        win, textvariable=speech_var, values=lang_labels, state="readonly", width=42
    ).grid(row=row, column=0, sticky="ew", pady=(0, 12))
    row += 1

    # Interfacetaal.
    ui_code = i18n.normalize_language(
        current.get("ui_language"),
        allowed=i18n.SUPPORTED_UI_LANGUAGES,
    )
    _section_label(i18n.t("settings.ui_language"))
    ui_var = tk.StringVar(value=lang_label_by_value.get(ui_code, lang_labels[0]))
    ttk.Combobox(
        win, textvariable=ui_var, values=lang_labels, state="readonly", width=42
    ).grid(row=row, column=0, sticky="ew", pady=(0, 12))
    row += 1

    # Sneltoets.
    _section_label(i18n.t("settings.hotkey"))
    hotkey_tokens = list(current.get("hotkey") or hotkeys.DEFAULT_HOTKEY)
    capture: dict[str, Any] = {
        "active": False,
        "pressed": set(),
        "best": set(),
        "queue": queue.Queue(),
        "poll_id": None,
    }

    hk_frame = ttk.Frame(win)
    hk_frame.grid(row=row, column=0, sticky="ew", pady=(0, 12))
    hk_frame.columnconfigure(0, weight=1)
    row += 1

    hk_var = tk.StringVar(value=hotkeys.format_hotkey(hotkey_tokens))
    ttk.Label(
        hk_frame, textvariable=hk_var, relief="groove", padding=(8, 4), anchor="w"
    ).grid(row=0, column=0, sticky="ew", padx=(0, 8))
    record_btn = ttk.Button(hk_frame, text=i18n.t("settings.hotkey.record"))
    record_btn.grid(row=0, column=1)

    def _drain_capture() -> None:
        try:
            while True:
                event, token = capture["queue"].get_nowait()
                if token is None:
                    continue
                if event == "press":
                    capture["pressed"].add(token)
                    if len(capture["pressed"]) >= len(capture["best"]):
                        capture["best"] = set(capture["pressed"])
                else:
                    capture["pressed"].discard(token)
        except queue.Empty:
            pass

        shown = capture["best"] or capture["pressed"]
        if shown:
            hk_var.set(hotkeys.format_hotkey(shown))

        if capture["active"]:
            capture["poll_id"] = win.after(50, _drain_capture)

    def _capture_cb(event: str, key: Any) -> None:
        capture["queue"].put((event, hotkeys.key_to_token(key)))

    def _start_capture() -> None:
        if set_capture is None:
            return
        capture["active"] = True
        capture["pressed"] = set()
        capture["best"] = set()
        while not capture["queue"].empty():
            capture["queue"].get_nowait()
        hk_var.set(i18n.t("settings.hotkey.press"))
        record_btn.config(text=i18n.t("settings.hotkey.use"))
        set_capture(_capture_cb)
        capture["poll_id"] = win.after(50, _drain_capture)

    def _stop_capture(confirm: bool) -> None:
        if not capture["active"]:
            return
        capture["active"] = False
        if set_capture is not None:
            set_capture(None)
        if capture["poll_id"] is not None:
            win.after_cancel(capture["poll_id"])
            capture["poll_id"] = None
        if confirm and capture["best"]:
            normalized = hotkeys.normalize(capture["best"])
            if any(token not in hotkeys.MODIFIER_TOKENS for token in normalized):
                hotkey_tokens[:] = normalized
            else:
                print(i18n.t("settings.hotkey.modifiers_only"))
        hk_var.set(hotkeys.format_hotkey(hotkey_tokens))
        record_btn.config(text=i18n.t("settings.hotkey.record"))

    def _toggle_capture() -> None:
        if capture["active"]:
            _stop_capture(confirm=True)
        else:
            _start_capture()

    record_btn.config(command=_toggle_capture)
    if set_capture is None:
        record_btn.state(["disabled"])

    autostart_var = tk.BooleanVar(value=bool(current.get("autostart", False)))
    ttk.Checkbutton(
        win,
        text=i18n.t("settings.autostart"),
        variable=autostart_var,
    ).grid(row=row, column=0, sticky="w", pady=(0, 12))
    row += 1

    paste_var = tk.BooleanVar(value=bool(current.get("auto_paste", True)))
    ttk.Checkbutton(
        win, text=i18n.t("settings.auto_paste"), variable=paste_var
    ).grid(row=row, column=0, sticky="w", pady=(0, 12))
    row += 1

    warm_var = tk.BooleanVar(value=bool(current.get("warm_microphone", False)))
    ttk.Checkbutton(
        win, text=i18n.t("settings.warm_microphone"), variable=warm_var
    ).grid(row=row, column=0, sticky="w", pady=(0, 12))
    row += 1

    _section_label(i18n.t("settings.model"))
    model_var = tk.StringVar(value=str(current.get("model", "small")))
    ttk.Combobox(
        win, textvariable=model_var, values=MODELS, state="readonly", width=42
    ).grid(row=row, column=0, sticky="ew", pady=(0, 2))
    row += 1
    ttk.Label(
        win, text=i18n.t("settings.model.restart"),
        foreground="#888888",
    ).grid(row=row, column=0, sticky="w", pady=(0, 14))
    row += 1

    buttons = ttk.Frame(win)
    buttons.grid(row=row, column=0, sticky="e")

    def close() -> None:
        global _open_dialog
        _stop_capture(confirm=False)
        _open_dialog = None
        win.destroy()

    def save() -> None:
        if capture["active"]:
            _stop_capture(confirm=True)

        new_settings = {
            "microphone_device": dict(devices).get(mic_var.get()),
            "indicator_position": pos_value_by_label.get(
                pos_var.get(), "boven-midden"
            ),
            "mode": mode_value_by_label.get(mode_var.get(), "toggle"),
            "hotkey": list(hotkey_tokens),
            "autostart": bool(autostart_var.get()),
            "auto_paste": bool(paste_var.get()),
            "warm_microphone": bool(warm_var.get()),
            "model": model_var.get(),
            "speech_language": lang_value_by_label.get(speech_var.get(), "nl"),
            "ui_language": lang_value_by_label.get(ui_var.get(), "nl"),
        }
        try:
            on_apply(new_settings)
        finally:
            close()

    ttk.Button(buttons, text=i18n.t("settings.cancel"), command=close).grid(
        row=0, column=0, padx=(0, 8)
    )
    ttk.Button(buttons, text=i18n.t("settings.save"), command=save).grid(
        row=0, column=1
    )

    win.protocol("WM_DELETE_WINDOW", close)

    win.update_idletasks()
    width = win.winfo_reqwidth()
    height = win.winfo_reqheight()
    x = (win.winfo_screenwidth() - width) // 2
    y = (win.winfo_screenheight() - height) // 3
    win.geometry(f"{width}x{height}+{x}+{y}")

    win.deiconify()
    win.lift()
    win.attributes("-topmost", True)
    win.after(300, lambda: win.attributes("-topmost", False))
    win.focus_force()
