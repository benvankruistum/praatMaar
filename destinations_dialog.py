"""
Bestemmingen-dialoog voor praatMaar (tkinter `Toplevel`).

Geopend vanuit het systeemvak-menu. Beheer van sticky bestemmingen (naam + map).
Bij Opslaan: `on_apply(...)` met bijgewerkte `destinations` en `active_destination`.
"""

from __future__ import annotations

import copy
import tkinter as tk
from collections.abc import Callable
from tkinter import filedialog, messagebox, ttk
from typing import Any

import destinations
import i18n
import recovery

_open_dialog: tk.Toplevel | None = None


def _revalidate_active(dest_list: list[dict[str, Any]], active: str | None) -> str | None:
    if active is None:
        return None
    if any(d["name"] == active for d in dest_list):
        return active
    return None


def _center_toplevel(dlg: tk.Toplevel, parent: tk.Misc) -> None:
    dlg.update_idletasks()
    pw = max(parent.winfo_width(), 1)
    ph = max(parent.winfo_height(), 1)
    px = parent.winfo_rootx()
    py = parent.winfo_rooty()
    dw = dlg.winfo_reqwidth()
    dh = dlg.winfo_reqheight()
    x = px + max(0, (pw - dw) // 2)
    y = py + max(0, (ph - dh) // 2)
    dlg.geometry(f"+{x}+{y}")


def _edit_destination(
    parent: tk.Misc,
    title: str,
    *,
    initial_name: str = "",
    initial_path: str = "",
    initial_auto_paste: bool = False,
    initial_file_mode: str = destinations.FILE_MODE_NEW,
    initial_append_file: str = "",
) -> dict[str, Any] | None:
    """Kleine subdialoog voor naam + pad + opties; retourneert None bij annuleren."""

    dlg = tk.Toplevel(parent)
    dlg.withdraw()
    dlg.title(title)
    dlg.resizable(False, False)
    dlg.transient(parent)
    dlg.grab_set()
    dlg.columnconfigure(1, weight=1)

    name_var = tk.StringVar(value=initial_name)
    path_var = tk.StringVar(value=initial_path)
    paste_var = tk.BooleanVar(value=initial_auto_paste)
    file_mode_var = tk.StringVar(
        value=initial_file_mode
        if initial_file_mode in (destinations.FILE_MODE_NEW, destinations.FILE_MODE_APPEND)
        else destinations.FILE_MODE_NEW
    )
    append_file_var = tk.StringVar(value=initial_append_file)

    row = 0

    ttk.Label(dlg, text=i18n.t("destinations.name")).grid(
        row=row, column=0, sticky="w", padx=(12, 8), pady=(12, 6)
    )
    name_entry = ttk.Entry(dlg, textvariable=name_var, width=40)
    name_entry.grid(row=row, column=1, sticky="ew", padx=(0, 12), pady=(12, 6))
    row += 1

    ttk.Label(dlg, text=i18n.t("destinations.path")).grid(
        row=row, column=0, sticky="w", padx=(12, 8), pady=(0, 6)
    )
    path_entry = ttk.Entry(dlg, textvariable=path_var, width=40)
    path_entry.grid(row=row, column=1, sticky="ew", padx=(0, 8), pady=(0, 6))

    def browse_folder() -> None:
        chosen = filedialog.askdirectory(parent=dlg, title=i18n.t("destinations.browse"))
        if chosen:
            path_var.set(chosen)

    ttk.Button(dlg, text=i18n.t("destinations.browse"), command=browse_folder).grid(
        row=row, column=2, padx=(0, 12), pady=(0, 6)
    )
    row += 1

    ttk.Checkbutton(
        dlg,
        text=i18n.t("destinations.auto_paste"),
        variable=paste_var,
    ).grid(row=row, column=0, columnspan=3, sticky="w", padx=12, pady=(4, 0))
    row += 1

    ttk.Label(dlg, text=i18n.t("destinations.file_mode")).grid(
        row=row, column=0, sticky="nw", padx=(12, 8), pady=(10, 6)
    )
    mode_frame = ttk.Frame(dlg)
    mode_frame.grid(row=row, column=1, columnspan=2, sticky="w", padx=(0, 12), pady=(10, 6))
    row += 1

    append_row = row
    append_file_entry = ttk.Entry(dlg, textvariable=append_file_var, width=40)

    def browse_append_file() -> None:
        initial_dir = path_var.get().strip() or None
        chosen = filedialog.askopenfilename(
            parent=dlg,
            title=i18n.t("destinations.browse_file"),
            initialdir=initial_dir,
            filetypes=[(i18n.t("destinations.file_filter"), "*.txt"), ("All files", "*.*")],
        )
        if chosen:
            append_file_var.set(chosen)

    def _sync_append_row() -> None:
        if file_mode_var.get() == destinations.FILE_MODE_APPEND:
            append_file_entry.grid(row=append_row, column=1, sticky="ew", padx=(0, 8), pady=(0, 6))
            append_browse_btn.grid(row=append_row, column=2, padx=(0, 12), pady=(0, 6))
            append_label.grid(row=append_row, column=0, sticky="w", padx=(12, 8), pady=(0, 6))
        else:
            append_label.grid_remove()
            append_file_entry.grid_remove()
            append_browse_btn.grid_remove()

    ttk.Radiobutton(
        mode_frame,
        text=i18n.t("destinations.file_mode.new"),
        variable=file_mode_var,
        value=destinations.FILE_MODE_NEW,
        command=_sync_append_row,
    ).grid(row=0, column=0, sticky="w")
    ttk.Radiobutton(
        mode_frame,
        text=i18n.t("destinations.file_mode.append"),
        variable=file_mode_var,
        value=destinations.FILE_MODE_APPEND,
        command=_sync_append_row,
    ).grid(row=1, column=0, sticky="w")

    append_label = ttk.Label(dlg, text=i18n.t("destinations.append_file"))
    append_browse_btn = ttk.Button(
        dlg, text=i18n.t("destinations.browse_file"), command=browse_append_file
    )
    row += 1

    result: dict[str, dict[str, Any] | None] = {"value": None}

    def confirm() -> None:
        name = name_var.get().strip()
        path = path_var.get().strip()
        if not name:
            messagebox.showwarning(
                i18n.t("destinations.title"),
                i18n.t("destinations.error.name_required"),
                parent=dlg,
            )
            return
        if not path:
            messagebox.showwarning(
                i18n.t("destinations.title"),
                i18n.t("destinations.error.path_required"),
                parent=dlg,
            )
            return
        file_mode = file_mode_var.get()
        append_file = append_file_var.get().strip()
        if file_mode == destinations.FILE_MODE_APPEND and not append_file:
            messagebox.showwarning(
                i18n.t("destinations.title"),
                i18n.t("destinations.error.append_file_required"),
                parent=dlg,
            )
            return
        result["value"] = {
            "name": name,
            "path": path,
            "auto_paste": bool(paste_var.get()),
            "file_mode": file_mode,
            "append_file": append_file if file_mode == destinations.FILE_MODE_APPEND else "",
        }
        dlg.destroy()

    def cancel() -> None:
        dlg.destroy()

    buttons = ttk.Frame(dlg)
    buttons.grid(row=row, column=0, columnspan=3, sticky="e", padx=12, pady=(6, 12))
    ttk.Button(buttons, text=i18n.t("destinations.cancel"), command=cancel).grid(
        row=0, column=0, padx=(0, 8)
    )
    ttk.Button(buttons, text=i18n.t("destinations.save"), command=confirm).grid(row=0, column=1)

    dlg.protocol("WM_DELETE_WINDOW", cancel)
    _sync_append_row()
    dlg.update_idletasks()
    dlg.deiconify()
    _center_toplevel(dlg, parent)
    name_entry.focus_set()
    parent.wait_window(dlg)
    return result["value"]


def open_destinations_dialog(
    parent: tk.Misc,
    current: dict[str, Any],
    on_apply: Callable[[dict[str, Any]], None],
    *,
    wait: bool = False,
) -> None:
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
    win.title(i18n.t("destinations.title"))
    win.resizable(True, True)
    win.minsize(560, 400)
    win.configure(padx=18, pady=16)
    win.columnconfigure(0, weight=1)
    win.rowconfigure(1, weight=1)

    dest_list: list[dict[str, Any]] = copy.deepcopy(
        destinations.sanitize_destinations(current.get("destinations"))
    )
    active_var = tk.StringVar(
        value=_revalidate_active(dest_list, current.get("active_destination")) or ""
    )

    intro = ttk.Label(
        win,
        text=i18n.t("destinations.intro"),
        wraplength=520,
        justify="left",
    )
    intro.grid(row=0, column=0, sticky="w", pady=(0, 10))

    list_frame = ttk.Frame(win)
    list_frame.grid(row=1, column=0, sticky="nsew", pady=(0, 8))
    list_frame.columnconfigure(0, weight=1)
    list_frame.rowconfigure(0, weight=1)

    columns = ("name", "path", "auto_paste", "active", "file_mode")
    tree = ttk.Treeview(list_frame, columns=columns, show="headings", selectmode="browse", height=8)
    tree.heading("name", text=i18n.t("destinations.column.name"))
    tree.heading("path", text=i18n.t("destinations.column.path"))
    tree.heading("auto_paste", text=i18n.t("destinations.column.auto_paste"))
    tree.heading("active", text=i18n.t("destinations.column.active"))
    tree.heading("file_mode", text=i18n.t("destinations.column.file_mode"))
    tree.column("name", width=120, stretch=False)
    tree.column("path", width=220, stretch=True)
    tree.column("auto_paste", width=70, stretch=False)
    tree.column("active", width=56, stretch=False, anchor="center")
    tree.column("file_mode", width=110, stretch=False)
    tree.grid(row=0, column=0, sticky="nsew")

    scroll = ttk.Scrollbar(list_frame, orient="vertical", command=tree.yview)
    scroll.grid(row=0, column=1, sticky="ns")
    tree.configure(yscrollcommand=scroll.set)

    empty_label = ttk.Label(
        win,
        text=i18n.t("destinations.empty"),
        foreground="#888888",
    )

    def _file_mode_label(item: dict[str, Any]) -> str:
        if item.get("file_mode") == destinations.FILE_MODE_APPEND:
            return i18n.t("destinations.file_mode.append.short")
        return i18n.t("destinations.file_mode.new.short")

    def _sync_tree() -> None:
        tree.delete(*tree.get_children())
        active_name = active_var.get().strip()
        tree.insert(
            "",
            "end",
            iid="default",
            values=(
                i18n.t("destinations.default.name"),
                i18n.t("destinations.default.path"),
                "—",
                i18n.t("destinations.active.yes") if not active_name else "",
                "—",
            ),
        )
        for index, item in enumerate(dest_list):
            paste_label = (
                i18n.t("destinations.auto_paste.yes")
                if item.get("auto_paste")
                else i18n.t("destinations.auto_paste.no")
            )
            active_label = i18n.t("destinations.active.yes") if item["name"] == active_name else ""
            tree.insert(
                "",
                "end",
                iid=str(index),
                values=(
                    item["name"],
                    item["path"],
                    paste_label,
                    active_label,
                    _file_mode_label(item),
                ),
            )
        if dest_list:
            empty_label.grid_remove()
        else:
            empty_label.grid(row=2, column=0, sticky="w", pady=(0, 8))

    def _selected_index() -> int | None:
        selection = tree.selection()
        if not selection:
            return None
        if selection[0] == "default":
            return None
        try:
            return int(selection[0])
        except ValueError:
            return None

    def _selected_is_default() -> bool:
        selection = tree.selection()
        return bool(selection) and selection[0] == "default"

    def _update_open_active_btn() -> None:
        if active_var.get().strip():
            open_active_btn.state(["!disabled"])
        else:
            open_active_btn.state(["disabled"])

    def _revalidate_and_refresh() -> None:
        active_var.set(_revalidate_active(dest_list, active_var.get().strip() or None) or "")
        _sync_tree()
        _update_open_active_btn()

    def _validate_name(name: str, skip_index: int | None = None) -> str | None:
        if destinations.is_reserved_name(name):
            return i18n.t("destinations.error.reserved_name")
        collision = destinations.find_normalized_collision(
            name, dest_list, exclude_index=skip_index
        )
        if collision is not None:
            return i18n.t("destinations.error.name_collision", existing=collision)
        return None

    def _set_active_default() -> None:
        active_var.set("")
        _revalidate_and_refresh()

    def _toggle_active_for_index(index: int) -> None:
        name = dest_list[index]["name"]
        if active_var.get().strip() == name:
            active_var.set("")
        else:
            active_var.set(name)
        _revalidate_and_refresh()

    def _on_tree_click(event: tk.Event) -> None:
        if tree.identify_region(event.x, event.y) != "cell":
            return
        if tree.identify_column(event.x) != "#4":
            return
        row_id = tree.identify_row(event.y)
        if not row_id:
            return
        if row_id == "default":
            _set_active_default()
            return
        try:
            index = int(row_id)
        except ValueError:
            return
        _toggle_active_for_index(index)

    tree.bind("<ButtonRelease-1>", _on_tree_click)

    def add_item() -> None:
        result = _edit_destination(win, i18n.t("destinations.add"))
        if result is None:
            return
        error = _validate_name(result["name"])
        if error is not None:
            messagebox.showwarning(
                i18n.t("destinations.title"),
                error,
                parent=win,
            )
            return
        dest_list.append(result)
        _revalidate_and_refresh()

    def edit_item() -> None:
        if _selected_is_default():
            messagebox.showinfo(
                i18n.t("destinations.title"),
                i18n.t("destinations.error.default_readonly"),
                parent=win,
            )
            return
        index = _selected_index()
        if index is None:
            messagebox.showinfo(
                i18n.t("destinations.title"),
                i18n.t("destinations.error.select_first"),
                parent=win,
            )
            return
        item = dest_list[index]
        result = _edit_destination(
            win,
            i18n.t("destinations.edit"),
            initial_name=item["name"],
            initial_path=item["path"],
            initial_auto_paste=bool(item.get("auto_paste", False)),
            initial_file_mode=str(item.get("file_mode", destinations.FILE_MODE_NEW)),
            initial_append_file=str(item.get("append_file", "")),
        )
        if result is None:
            return
        error = _validate_name(result["name"], skip_index=index)
        if error is not None:
            messagebox.showwarning(
                i18n.t("destinations.title"),
                error,
                parent=win,
            )
            return
        old_name = item["name"]
        dest_list[index] = result
        if active_var.get().strip() == old_name:
            active_var.set(result["name"])
        _revalidate_and_refresh()

    def delete_item() -> None:
        if _selected_is_default():
            messagebox.showinfo(
                i18n.t("destinations.title"),
                i18n.t("destinations.error.default_readonly"),
                parent=win,
            )
            return
        index = _selected_index()
        if index is None:
            messagebox.showinfo(
                i18n.t("destinations.title"),
                i18n.t("destinations.error.select_first"),
                parent=win,
            )
            return
        removed = dest_list.pop(index)
        if active_var.get().strip() == removed["name"]:
            active_var.set("")
        _revalidate_and_refresh()

    crud = ttk.Frame(win)
    crud.grid(row=3, column=0, sticky="w", pady=(0, 8))
    ttk.Button(crud, text=i18n.t("destinations.add"), command=add_item).grid(
        row=0, column=0, padx=(0, 6)
    )
    ttk.Button(crud, text=i18n.t("destinations.edit"), command=edit_item).grid(
        row=0, column=1, padx=(0, 6)
    )
    ttk.Button(crud, text=i18n.t("destinations.delete"), command=delete_item).grid(row=0, column=2)

    folders = ttk.Frame(win)
    folders.grid(row=4, column=0, sticky="w", pady=(0, 12))

    def open_transcripts() -> None:
        destinations.open_in_explorer(recovery.transcripts_dir())

    open_active_btn = ttk.Button(folders, text=i18n.t("destinations.open_active"))

    def open_active_folder() -> None:
        name = active_var.get().strip() or None
        path = destinations.resolve_save_dir(name, dest_list, recovery.transcripts_dir())
        destinations.open_in_explorer(path)

    open_active_btn.config(command=open_active_folder)
    ttk.Button(
        folders, text=i18n.t("destinations.open_transcripts"), command=open_transcripts
    ).grid(row=0, column=0, padx=(0, 8))
    open_active_btn.grid(row=0, column=1)

    buttons = ttk.Frame(win)
    buttons.grid(row=5, column=0, sticky="e")

    def close() -> None:
        global _open_dialog
        _open_dialog = None
        win.destroy()

    def save() -> None:
        active_name = _revalidate_active(dest_list, active_var.get().strip() or None)
        merged = dict(current)
        merged["destinations"] = copy.deepcopy(dest_list)
        merged["active_destination"] = active_name
        try:
            on_apply(merged)
        finally:
            close()

    ttk.Button(buttons, text=i18n.t("destinations.cancel"), command=close).grid(
        row=0, column=0, padx=(0, 8)
    )
    ttk.Button(buttons, text=i18n.t("destinations.save"), command=save).grid(row=0, column=1)

    win.protocol("WM_DELETE_WINDOW", close)

    _revalidate_and_refresh()

    win.update_idletasks()
    width = max(win.winfo_reqwidth(), 560)
    height = max(win.winfo_reqheight(), 400)
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
