"""
Instellingen-dialoog voor praatMaar (tkinter `Toplevel`).

Geopend vanuit het systeemvak-menu ("Instellingen"). Anders dan de pill mag dit
venster **wel** focus pakken — je typt/kiest erin. Draait op de hoofdthread
(gemarshald via `indicator.call_on_main`).

Bevat: microfoon, pill-positie, auto-plakken, bedieningsmodus (toggle/push-to-
talk), de sneltoets (opneembaar), automatisch meestarten en het Whisper-model.
Bij Opslaan roept het `on_apply(new_settings)` aan; `dictation.py` bewaart en
past toe (live waar kan; model pas na herstart).

Het opnemen van een sneltoets gebruikt de globale listener van de app (via de
`set_capture`-callback), zodat de opgeslagen combinatie exact overeenkomt met wat
de listener herkent. hotkeys.py verzorgt de omzetting toets ↔ token ↔ label.
"""

from __future__ import annotations

import queue
import tkinter as tk
from tkinter import ttk
from typing import Any, Callable

import sounddevice as sd

import hotkeys

MODELS = ["base", "small", "medium"]
POSITIONS = [("Boven-midden", "boven-midden"), ("Onder-midden", "onder-midden")]
MODES = [
    ("Toggle: indrukken start én stopt", "toggle"),
    ("Push-to-talk: ingedrukt houden", "ptt"),
]

# Voorkomt dat er meerdere dialogen tegelijk openen.
_open_dialog: "tk.Toplevel | None" = None


def _input_devices() -> list[tuple[str, "int | None"]]:
    """(label, device-index) voor elk invoerapparaat; index None = Windows-standaard."""

    options: list[tuple[str, int | None]] = [("Windows-standaard", None)]
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
    win.withdraw()  # verborgen opbouwen; pas tonen na het positioneren
    _open_dialog = win
    win.title("praatMaar — Instellingen")
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

    # Microfoon.
    ttk.Label(win, text="Microfoon").grid(row=row, column=0, sticky="w", pady=(0, 2))
    row += 1
    mic_var = tk.StringVar(value=current_device_label)
    mic_box = ttk.Combobox(
        win, textvariable=mic_var, values=device_labels, state="readonly", width=42
    )
    mic_box.grid(row=row, column=0, sticky="ew", pady=(0, 12))
    row += 1

    # Pill-positie.
    ttk.Label(win, text="Positie van de indicator").grid(
        row=row, column=0, sticky="w", pady=(0, 2)
    )
    row += 1
    pos_labels = [label for label, _ in POSITIONS]
    pos_value_by_label = {label: value for label, value in POSITIONS}
    pos_label_by_value = {value: label for label, value in POSITIONS}
    pos_var = tk.StringVar(
        value=pos_label_by_value.get(
            current.get("indicator_position"), pos_labels[0]
        )
    )
    pos_box = ttk.Combobox(
        win, textvariable=pos_var, values=pos_labels, state="readonly", width=42
    )
    pos_box.grid(row=row, column=0, sticky="ew", pady=(0, 12))
    row += 1

    # Bedieningsmodus.
    ttk.Label(win, text="Bediening").grid(row=row, column=0, sticky="w", pady=(0, 2))
    row += 1
    mode_labels = [label for label, _ in MODES]
    mode_value_by_label = {label: value for label, value in MODES}
    mode_label_by_value = {value: label for label, value in MODES}
    mode_var = tk.StringVar(
        value=mode_label_by_value.get(current.get("mode"), mode_labels[0])
    )
    mode_box = ttk.Combobox(
        win, textvariable=mode_var, values=mode_labels, state="readonly", width=42
    )
    mode_box.grid(row=row, column=0, sticky="ew", pady=(0, 12))
    row += 1

    # Sneltoets (opneembaar).
    ttk.Label(win, text="Sneltoets").grid(row=row, column=0, sticky="w", pady=(0, 2))
    row += 1

    hotkey_tokens = list(current.get("hotkey") or hotkeys.DEFAULT_HOTKEY)
    capture = {
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
    record_btn = ttk.Button(hk_frame, text="Opnemen…")
    record_btn.grid(row=0, column=1)

    def _drain_capture() -> None:
        try:
            while True:
                event, token = capture["queue"].get_nowait()
                if token is None:
                    continue
                if event == "press":
                    capture["pressed"].add(token)
                    # De grootste tegelijk-vastgehouden combinatie wint.
                    if len(capture["pressed"]) >= len(capture["best"]):
                        capture["best"] = set(capture["pressed"])
                else:  # release
                    capture["pressed"].discard(token)
        except queue.Empty:
            pass

        shown = capture["best"] or capture["pressed"]
        if shown:
            hk_var.set(hotkeys.format_hotkey(shown))

        if capture["active"]:
            capture["poll_id"] = win.after(50, _drain_capture)

    def _capture_cb(event: str, key: Any) -> None:
        # Loopt op de listener-thread; alleen data doorschuiven, geen Tk hier.
        capture["queue"].put((event, hotkeys.key_to_token(key)))

    def _start_capture() -> None:
        if set_capture is None:
            return
        capture["active"] = True
        capture["pressed"] = set()
        capture["best"] = set()
        while not capture["queue"].empty():
            capture["queue"].get_nowait()
        hk_var.set("Druk de combinatie in…")
        record_btn.config(text="Gebruik deze")
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
            # Alleen modifiers (Ctrl+Shift+Alt) is geen bruikbare sneltoets —
            # die gaat af bij elke willekeurige toetscombinatie met die mods.
            if any(token not in hotkeys.MODIFIER_TOKENS for token in normalized):
                hotkey_tokens[:] = normalized
            else:
                print(
                    "Sneltoets genegeerd: voeg minstens één gewone toets toe "
                    "(bijv. Spatie of een letter)."
                )
        hk_var.set(hotkeys.format_hotkey(hotkey_tokens))
        record_btn.config(text="Opnemen…")

    def _toggle_capture() -> None:
        if capture["active"]:
            _stop_capture(confirm=True)
        else:
            _start_capture()

    record_btn.config(command=_toggle_capture)
    if set_capture is None:
        record_btn.state(["disabled"])

    # Automatisch meestarten.
    autostart_var = tk.BooleanVar(value=bool(current.get("autostart", False)))
    ttk.Checkbutton(
        win,
        text="Automatisch meestarten met Windows",
        variable=autostart_var,
    ).grid(row=row, column=0, sticky="w", pady=(0, 12))
    row += 1

    # Auto-plakken.
    paste_var = tk.BooleanVar(value=bool(current.get("auto_paste", True)))
    ttk.Checkbutton(
        win, text="Automatisch plakken in het actieve invoerveld", variable=paste_var
    ).grid(row=row, column=0, sticky="w", pady=(0, 12))
    row += 1

    # Whisper-model.
    ttk.Label(win, text="Whisper-model").grid(row=row, column=0, sticky="w", pady=(0, 2))
    row += 1
    model_var = tk.StringVar(value=str(current.get("model", "small")))
    model_box = ttk.Combobox(
        win, textvariable=model_var, values=MODELS, state="readonly", width=42
    )
    model_box.grid(row=row, column=0, sticky="ew", pady=(0, 2))
    row += 1
    ttk.Label(
        win, text="Wijziging van het model werkt pas na herstart.",
        foreground="#888888",
    ).grid(row=row, column=0, sticky="w", pady=(0, 14))
    row += 1

    # Knoppen.
    buttons = ttk.Frame(win)
    buttons.grid(row=row, column=0, sticky="e")

    def close() -> None:
        global _open_dialog
        _stop_capture(confirm=False)  # listener nooit onderdrukt achterlaten
        _open_dialog = None
        win.destroy()

    def save() -> None:
        # Loopt het opnemen nog? Dan de huidige combinatie overnemen.
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
            "model": model_var.get(),
        }
        try:
            on_apply(new_settings)
        finally:
            close()

    ttk.Button(buttons, text="Annuleren", command=close).grid(row=0, column=0, padx=(0, 8))
    ttk.Button(buttons, text="Opslaan", command=save).grid(row=0, column=1)

    win.protocol("WM_DELETE_WINDOW", close)

    # Positioneren terwijl verborgen, dán tonen. Windows honoreert de geometrie
    # die vóór het eerste mappen is gezet; zet je 'm daarna, dan wint de
    # cascade-default (het venster negeert de positie).
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
