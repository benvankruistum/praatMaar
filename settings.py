"""
Instellingen-dialoog voor praatMaar (tkinter `Toplevel`).

Geopend vanuit het systeemvak-menu. Bevat o.a. microfoon, sneltoets, Whisper-
model, spraakherkenningstaal en interfacetaal. Bij Opslaan: `on_apply(...)`.

Op Windows draait het dialoog op de Tk-hoofdthread (gemarshald via
`indicator.call_on_main`). Op macOS opent Instellingen in een apart Tk-proces
(`settings_process.run_settings_subprocess`) — een Toplevel in dezelfde
Cocoa-runloop als pystray/NSApp crasht bij sluiten (`PyEval_RestoreThread` →
SIGABRT).
"""

from __future__ import annotations

import queue
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any

import sounddevice as sd

import destinations
import hotkeys
import i18n
import recovery

MODELS = ["base", "small", "medium"]

# Voorkomt dat er meerdere dialogen tegelijk openen.
_open_dialog: Any = None


def _positions() -> list[tuple[str, str]]:
    return [
        (i18n.t("settings.position.top"), "boven-midden"),
        (i18n.t("settings.position.bottom"), "onder-midden"),
        (i18n.t("settings.position.last"), "laatst-geplaatst"),
    ]


def _modes() -> list[tuple[str, str]]:
    return [
        (i18n.t("settings.mode.toggle"), "toggle"),
        (i18n.t("settings.mode.ptt"), "ptt"),
    ]


def _language_choices() -> list[tuple[str, str]]:
    return [(i18n.LANGUAGE_LABELS[code], code) for code in i18n.SUPPORTED_UI_LANGUAGES]


def _input_devices() -> list[tuple[str, int | None]]:
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
    root: Any,
    current: dict[str, Any],
    on_apply: Callable[[dict[str, Any]], None],
    set_capture: Callable[[Any | None], None] | None = None,
    *,
    wait: bool = False,
    use_tk_capture: bool = False,
    on_retranscribe: Callable[[Path], str] | None = None,
    on_parent_retranscribe: Callable[[Path], None] | None = None,
) -> None:
    """
    ``use_tk_capture``: neem sneltoetsen op via Tk KeyPress/KeyRelease
    (betrouwbaarder voor Windows-/PC-toetsenborden in het macOS-settingsproces).

    ``on_retranscribe``: live callback (Windows) — blokkerend, in achtergrondthread.
    ``on_parent_retranscribe``: macOS-kind — schrijft pad terug naar parent en sluit.
    """

    import tkinter as tk
    from tkinter import messagebox, ttk

    global _open_dialog

    if _open_dialog is not None and _open_dialog.winfo_exists():
        _open_dialog.lift()
        _open_dialog.focus_force()
        if wait:
            root.wait_window(_open_dialog)
        return

    win = tk.Toplevel(root)
    win.withdraw()
    _open_dialog = win
    win.title(i18n.t("settings.title"))
    win.resizable(False, False)
    win.configure(padx=18, pady=16)
    win.columnconfigure(0, weight=1)

    notebook = ttk.Notebook(win)
    notebook.grid(row=0, column=0, sticky="nsew")

    general_tab = ttk.Frame(notebook, padding=(4, 12, 4, 4))
    language_tab = ttk.Frame(notebook, padding=(4, 12, 4, 4))
    advanced_tab = ttk.Frame(notebook, padding=(4, 12, 4, 4))
    for tab in (general_tab, language_tab, advanced_tab):
        tab.columnconfigure(0, weight=1)

    notebook.add(general_tab, text=i18n.t("settings.tab.general"))
    notebook.add(language_tab, text=i18n.t("settings.tab.language"))
    notebook.add(advanced_tab, text=i18n.t("settings.tab.advanced"))

    tab_rows = {general_tab: 0, language_tab: 0, advanced_tab: 0}

    def _section_label(parent: Any, text: str) -> None:
        row = tab_rows[parent]
        ttk.Label(parent, text=text).grid(row=row, column=0, sticky="w", pady=(0, 2))
        tab_rows[parent] = row + 1

    def _next_row(parent: Any) -> int:
        row = tab_rows[parent]
        tab_rows[parent] = row + 1
        return row

    devices = _input_devices()
    device_labels = [label for label, _ in devices]
    current_device = current.get("microphone_device")
    device_label_by_value = {value: label for label, value in devices}
    current_device_label = device_label_by_value.get(current_device, device_labels[0])

    # --- Algemeen ---
    _section_label(general_tab, i18n.t("settings.microphone"))
    mic_var = tk.StringVar(value=current_device_label)
    ttk.Combobox(
        general_tab,
        textvariable=mic_var,
        values=device_labels,
        state="readonly",
        width=42,
    ).grid(row=_next_row(general_tab), column=0, sticky="ew", pady=(0, 12))

    positions = _positions()
    _section_label(general_tab, i18n.t("settings.indicator_position"))
    pos_labels = [label for label, _ in positions]
    pos_value_by_label = {label: value for label, value in positions}
    pos_label_by_value = {value: label for label, value in positions}
    pos_var = tk.StringVar(
        value=pos_label_by_value.get(current.get("indicator_position"), pos_labels[0])
    )
    ttk.Combobox(
        general_tab,
        textvariable=pos_var,
        values=pos_labels,
        state="readonly",
        width=42,
    ).grid(row=_next_row(general_tab), column=0, sticky="ew", pady=(0, 12))

    modes = _modes()
    _section_label(general_tab, i18n.t("settings.mode"))
    mode_labels = [label for label, _ in modes]
    mode_value_by_label = {label: value for label, value in modes}
    mode_label_by_value = {value: label for label, value in modes}
    mode_var = tk.StringVar(value=mode_label_by_value.get(current.get("mode"), mode_labels[0]))
    ttk.Combobox(
        general_tab,
        textvariable=mode_var,
        values=mode_labels,
        state="readonly",
        width=42,
    ).grid(row=_next_row(general_tab), column=0, sticky="ew", pady=(0, 12))

    # --- Taal ---
    lang_choices = _language_choices()
    lang_labels = [label for label, _ in lang_choices]
    lang_value_by_label = {label: value for label, value in lang_choices}
    lang_label_by_value = {value: label for label, value in lang_choices}
    speech_code = i18n.normalize_language(
        current.get("speech_language"),
        allowed=i18n.SUPPORTED_SPEECH_LANGUAGES,
    )
    _section_label(language_tab, i18n.t("settings.speech_language"))
    speech_var = tk.StringVar(value=lang_label_by_value.get(speech_code, lang_labels[0]))
    ttk.Combobox(
        language_tab,
        textvariable=speech_var,
        values=lang_labels,
        state="readonly",
        width=42,
    ).grid(row=_next_row(language_tab), column=0, sticky="ew", pady=(0, 12))

    ui_code = i18n.normalize_language(
        current.get("ui_language"),
        allowed=i18n.SUPPORTED_UI_LANGUAGES,
    )
    _section_label(language_tab, i18n.t("settings.ui_language"))
    ui_var = tk.StringVar(value=lang_label_by_value.get(ui_code, lang_labels[0]))
    ttk.Combobox(
        language_tab,
        textvariable=ui_var,
        values=lang_labels,
        state="readonly",
        width=42,
    ).grid(row=_next_row(language_tab), column=0, sticky="ew", pady=(0, 12))

    # Sneltoets (algemeen).
    _section_label(general_tab, i18n.t("settings.hotkey"))
    hotkey_tokens = list(current.get("hotkey") or hotkeys.DEFAULT_HOTKEY)
    capture: dict[str, Any] = {
        "active": False,
        "pressed": set(),
        "best": set(),
        "queue": queue.Queue(),
        "poll_id": None,
    }

    hk_frame = ttk.Frame(general_tab)
    hk_frame.grid(row=_next_row(general_tab), column=0, sticky="ew", pady=(0, 12))
    hk_frame.columnconfigure(0, weight=1)

    hk_var = tk.StringVar(value=hotkeys.format_hotkey(hotkey_tokens))
    ttk.Label(hk_frame, textvariable=hk_var, relief="groove", padding=(8, 4), anchor="w").grid(
        row=0, column=0, sticky="ew", padx=(0, 8)
    )
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

    def _tk_capture_event(event: Any) -> str:
        """Tk KeyPress/Release → queue; 'break' dempt verdere dialoog-afhandeling."""

        if not capture["active"]:
            return "break"

        type_name = getattr(event.type, "name", str(event.type))
        try:
            type_num = int(event.type)
        except (TypeError, ValueError):
            type_num = -1
        if type_name in ("KeyPress", "2") or type_num == 2:
            kind = "press"
        elif type_name in ("KeyRelease", "3") or type_num == 3:
            kind = "release"
        else:
            return "break"

        token = hotkeys.tk_keysym_to_token(str(event.keysym))
        mods = hotkeys.tk_event_modifier_tokens(int(event.state))
        if kind == "press":
            for mod in mods:
                capture["queue"].put(("press", mod))
            if token is not None and token not in mods:
                capture["queue"].put(("press", token))
        else:
            if token is not None:
                capture["queue"].put(("release", token))
            still = hotkeys.tk_event_modifier_tokens(int(event.state))
            for mod in ("ctrl", "shift", "alt", "cmd"):
                if mod not in still:
                    capture["queue"].put(("release", mod))
        return "break"

    def _bind_tk_capture() -> None:
        win.bind("<KeyPress>", _tk_capture_event)
        win.bind("<KeyRelease>", _tk_capture_event)
        try:
            win.focus_force()
        except Exception:
            pass

    def _unbind_tk_capture() -> None:
        try:
            win.unbind("<KeyPress>")
            win.unbind("<KeyRelease>")
        except Exception:
            pass

    def _start_capture() -> None:
        if set_capture is None and not use_tk_capture:
            return
        capture["active"] = True
        capture["pressed"] = set()
        capture["best"] = set()
        while not capture["queue"].empty():
            capture["queue"].get_nowait()
        hk_var.set(i18n.t("settings.hotkey.press"))
        record_btn.config(text=i18n.t("settings.hotkey.use"))
        if use_tk_capture:
            _bind_tk_capture()
        if set_capture is not None:
            set_capture(_capture_cb)
        capture["poll_id"] = win.after(50, _drain_capture)

    def _stop_capture(confirm: bool) -> None:
        if not capture["active"]:
            return
        capture["active"] = False
        if use_tk_capture:
            _unbind_tk_capture()
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
    if set_capture is None and not use_tk_capture:
        record_btn.state(["disabled"])

    autostart_var = tk.BooleanVar(value=bool(current.get("autostart", False)))
    ttk.Checkbutton(
        general_tab,
        text=i18n.t("settings.autostart"),
        variable=autostart_var,
    ).grid(row=_next_row(general_tab), column=0, sticky="w", pady=(0, 12))

    paste_var = tk.BooleanVar(value=bool(current.get("auto_paste", True)))
    ttk.Checkbutton(general_tab, text=i18n.t("settings.auto_paste"), variable=paste_var).grid(
        row=_next_row(general_tab), column=0, sticky="w", pady=(0, 12)
    )

    warm_var = tk.BooleanVar(value=bool(current.get("warm_microphone", False)))
    ttk.Checkbutton(
        general_tab,
        text=i18n.t("settings.warm_microphone"),
        variable=warm_var,
    ).grid(row=_next_row(general_tab), column=0, sticky="w", pady=(0, 12))

    # --- Geavanceerd ---
    _section_label(advanced_tab, i18n.t("settings.model"))
    model_var = tk.StringVar(value=str(current.get("model", "small")))
    ttk.Combobox(
        advanced_tab,
        textvariable=model_var,
        values=MODELS,
        state="readonly",
        width=42,
    ).grid(row=_next_row(advanced_tab), column=0, sticky="ew", pady=(0, 2))
    ttk.Label(
        advanced_tab,
        text=i18n.t("settings.model.restart"),
        foreground="#888888",
    ).grid(row=_next_row(advanced_tab), column=0, sticky="w", pady=(0, 14))

    _section_label(advanced_tab, i18n.t("recovery.section"))
    recovery_paths: list[Path] = []
    recovery_busy = {"active": False}

    list_frame = ttk.Frame(advanced_tab)
    list_frame.grid(row=_next_row(advanced_tab), column=0, sticky="ew", pady=(0, 4))
    list_frame.columnconfigure(0, weight=1)

    recovery_list = tk.Listbox(list_frame, height=5, exportselection=False, width=48)
    recovery_list.grid(row=0, column=0, sticky="ew")
    recovery_scroll = ttk.Scrollbar(list_frame, orient="vertical", command=recovery_list.yview)
    recovery_scroll.grid(row=0, column=1, sticky="ns")
    recovery_list.configure(yscrollcommand=recovery_scroll.set)

    empty_label = ttk.Label(
        advanced_tab,
        text=i18n.t("recovery.empty"),
        foreground="#888888",
    )
    empty_label.grid(row=_next_row(advanced_tab), column=0, sticky="w", pady=(0, 4))

    status_var = tk.StringVar(value="")
    status_label = ttk.Label(advanced_tab, textvariable=status_var, foreground="#555555")
    status_label.grid(row=_next_row(advanced_tab), column=0, sticky="w", pady=(0, 4))

    recovery_btns = ttk.Frame(advanced_tab)
    recovery_btns.grid(row=_next_row(advanced_tab), column=0, sticky="w", pady=(0, 14))

    def _refresh_recovery_list() -> None:
        recovery_paths.clear()
        recovery_list.delete(0, tk.END)
        for path in recovery.list_recovery_wavs():
            recovery_paths.append(path)
            recovery_list.insert(tk.END, recovery.recovery_list_label(path))
        empty_label.config(text="" if recovery_paths else i18n.t("recovery.empty"))

    def _selected_recovery_path() -> Path | None:
        selection = recovery_list.curselection()
        if not selection:
            return None
        index = int(selection[0])
        if index < 0 or index >= len(recovery_paths):
            return None
        return recovery_paths[index]

    def _set_recovery_controls_enabled(enabled: bool) -> None:
        state = ["!disabled"] if enabled else ["disabled"]
        for btn in (
            open_folder_btn,
            delete_btn,
            delete_all_btn,
            retranscribe_btn,
        ):
            btn.state(state)

    def open_recovery_folder() -> None:
        try:
            destinations.open_in_explorer(recovery.recovery_dir())
        except OSError as exc:
            messagebox.showerror(
                i18n.t("settings.title"),
                str(exc),
                parent=win,
            )

    def delete_selected() -> None:
        path = _selected_recovery_path()
        if path is None:
            messagebox.showinfo(
                i18n.t("settings.title"),
                i18n.t("recovery.select_first"),
                parent=win,
            )
            return
        if not messagebox.askyesno(
            i18n.t("settings.title"),
            i18n.t("recovery.confirm_delete", name=path.name),
            parent=win,
        ):
            return
        try:
            recovery.delete_recovery_file(path)
        except (OSError, ValueError) as exc:
            messagebox.showerror(i18n.t("settings.title"), str(exc), parent=win)
            return
        _refresh_recovery_list()

    def delete_all() -> None:
        if not recovery_paths:
            messagebox.showinfo(
                i18n.t("settings.title"),
                i18n.t("recovery.empty"),
                parent=win,
            )
            return
        if not messagebox.askyesno(
            i18n.t("settings.title"),
            i18n.t("recovery.confirm_delete_all", count=len(recovery_paths)),
            parent=win,
        ):
            return
        recovery.delete_all_recovery_files()
        _refresh_recovery_list()

    def _ask_delete_after_success(path: Path) -> None:
        if not path.exists():
            _refresh_recovery_list()
            return
        if messagebox.askyesno(
            i18n.t("settings.title"),
            i18n.t("recovery.ask_delete_after", name=path.name),
            parent=win,
        ):
            try:
                recovery.delete_recovery_file(path)
            except (OSError, ValueError) as exc:
                messagebox.showerror(i18n.t("settings.title"), str(exc), parent=win)
        _refresh_recovery_list()

    def retranscribe_selected() -> None:
        if recovery_busy["active"]:
            return
        path = _selected_recovery_path()
        if path is None:
            messagebox.showinfo(
                i18n.t("settings.title"),
                i18n.t("recovery.select_first"),
                parent=win,
            )
            return

        if on_parent_retranscribe is not None:
            on_parent_retranscribe(path)
            close()
            return

        if on_retranscribe is None:
            messagebox.showinfo(
                i18n.t("settings.title"),
                i18n.t("recovery.unavailable"),
                parent=win,
            )
            return

        recovery_busy["active"] = True
        status_var.set(i18n.t("recovery.busy_status"))
        _set_recovery_controls_enabled(False)

        def worker() -> None:
            error: str | None = None
            try:
                on_retranscribe(path)
            except Exception as exc:
                error = str(exc)

            def done() -> None:
                recovery_busy["active"] = False
                status_var.set("")
                _set_recovery_controls_enabled(True)
                if error is not None:
                    messagebox.showerror(
                        i18n.t("settings.title"),
                        error,
                        parent=win,
                    )
                    return
                _ask_delete_after_success(path)

            win.after(0, done)

        threading.Thread(target=worker, daemon=True).start()

    open_folder_btn = ttk.Button(
        recovery_btns,
        text=i18n.t("recovery.open_folder"),
        command=open_recovery_folder,
    )
    open_folder_btn.grid(row=0, column=0, padx=(0, 6))
    delete_btn = ttk.Button(
        recovery_btns,
        text=i18n.t("recovery.delete"),
        command=delete_selected,
    )
    delete_btn.grid(row=0, column=1, padx=(0, 6))
    delete_all_btn = ttk.Button(
        recovery_btns,
        text=i18n.t("recovery.delete_all"),
        command=delete_all,
    )
    delete_all_btn.grid(row=0, column=2, padx=(0, 6))
    retranscribe_btn = ttk.Button(
        recovery_btns,
        text=i18n.t("recovery.retranscribe"),
        command=retranscribe_selected,
    )
    retranscribe_btn.grid(row=0, column=3)

    _refresh_recovery_list()

    buttons = ttk.Frame(win)
    buttons.grid(row=1, column=0, sticky="e", pady=(12, 0))

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
            "indicator_position": pos_value_by_label.get(pos_var.get(), "boven-midden"),
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
    ttk.Button(buttons, text=i18n.t("settings.save"), command=save).grid(row=0, column=1)

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

    if wait:
        root.wait_window(win)
