"""
Bestemmingen-dialoog voor praatMaar (tkinter `Toplevel`).

Geopend vanuit het systeemvak-menu. Beheer van sticky bestemmingen (naam + map).
Bij Opslaan: `on_apply(...)` met bijgewerkte `destinations` en `active_destination`.
"""

from __future__ import annotations

import copy
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Any, Callable

import destinations
import i18n
import recovery

_open_dialog: "tk.Toplevel | None" = None


def _revalidate_active(
    dest_list: list[dict[str, str]], active: str | None
) -> str | None:
    if active is None:
        return None
    if any(d["name"] == active for d in dest_list):
        return active
    return None


def _edit_destination(
    parent: tk.Misc,
    title: str,
    *,
    initial_name: str = "",
    initial_path: str = "",
) -> tuple[str, str] | None:
    """Kleine subdialoog voor naam + pad; retourneert None bij annuleren."""

    dlg = tk.Toplevel(parent)
    dlg.withdraw()
    dlg.title(title)
    dlg.resizable(False, False)
    dlg.transient(parent)
    dlg.grab_set()
    dlg.columnconfigure(1, weight=1)

    name_var = tk.StringVar(value=initial_name)
    path_var = tk.StringVar(value=initial_path)

    ttk.Label(dlg, text=i18n.t("destinations.name")).grid(
        row=0, column=0, sticky="w", padx=(12, 8), pady=(12, 6)
    )
    name_entry = ttk.Entry(dlg, textvariable=name_var, width=40)
    name_entry.grid(row=0, column=1, sticky="ew", padx=(0, 12), pady=(12, 6))

    ttk.Label(dlg, text=i18n.t("destinations.path")).grid(
        row=1, column=0, sticky="w", padx=(12, 8), pady=(0, 6)
    )
    path_entry = ttk.Entry(dlg, textvariable=path_var, width=40)
    path_entry.grid(row=1, column=1, sticky="ew", padx=(0, 8), pady=(0, 6))

    def browse() -> None:
        chosen = filedialog.askdirectory(parent=dlg, title=i18n.t("destinations.browse"))
        if chosen:
            path_var.set(chosen)

    ttk.Button(dlg, text=i18n.t("destinations.browse"), command=browse).grid(
        row=1, column=2, padx=(0, 12), pady=(0, 6)
    )

    result: dict[str, tuple[str, str] | None] = {"value": None}

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
        result["value"] = (name, path)
        dlg.destroy()

    def cancel() -> None:
        dlg.destroy()

    buttons = ttk.Frame(dlg)
    buttons.grid(row=2, column=0, columnspan=3, sticky="e", padx=12, pady=(6, 12))
    ttk.Button(buttons, text=i18n.t("destinations.cancel"), command=cancel).grid(
        row=0, column=0, padx=(0, 8)
    )
    ttk.Button(buttons, text=i18n.t("destinations.save"), command=confirm).grid(
        row=0, column=1
    )

    dlg.protocol("WM_DELETE_WINDOW", cancel)
    dlg.update_idletasks()
    dlg.deiconify()
    name_entry.focus_set()
    parent.wait_window(dlg)
    return result["value"]


def open_destinations_dialog(
    parent: tk.Misc,
    current: dict[str, Any],
    on_apply: Callable[[dict[str, Any]], None],
) -> None:
    global _open_dialog

    if _open_dialog is not None and _open_dialog.winfo_exists():
        _open_dialog.lift()
        _open_dialog.focus_force()
        return

    win = tk.Toplevel(parent)
    win.withdraw()
    _open_dialog = win
    win.title(i18n.t("destinations.title"))
    win.resizable(True, True)
    win.minsize(520, 360)
    win.configure(padx=18, pady=16)
    win.columnconfigure(0, weight=1)
    win.rowconfigure(1, weight=1)

    dest_list: list[dict[str, str]] = copy.deepcopy(
        destinations.sanitize_destinations(current.get("destinations"))
    )
    active_var = tk.StringVar(
        value=_revalidate_active(dest_list, current.get("active_destination")) or ""
    )

    active_label = ttk.Label(win, text="")
    active_label.grid(row=0, column=0, sticky="w", pady=(0, 8))

    list_frame = ttk.Frame(win)
    list_frame.grid(row=1, column=0, sticky="nsew", pady=(0, 8))
    list_frame.columnconfigure(0, weight=1)
    list_frame.rowconfigure(0, weight=1)

    columns = ("name", "path")
    tree = ttk.Treeview(
        list_frame, columns=columns, show="headings", selectmode="browse", height=8
    )
    tree.heading("name", text=i18n.t("destinations.column.name"))
    tree.heading("path", text=i18n.t("destinations.column.path"))
    tree.column("name", width=140, stretch=False)
    tree.column("path", width=320, stretch=True)
    tree.grid(row=0, column=0, sticky="nsew")

    scroll = ttk.Scrollbar(list_frame, orient="vertical", command=tree.yview)
    scroll.grid(row=0, column=1, sticky="ns")
    tree.configure(yscrollcommand=scroll.set)

    def _refresh_active_label() -> None:
        name = active_var.get().strip()
        if name:
            active_label.config(
                text=i18n.t("destinations.active.named", name=name)
            )
        else:
            active_label.config(text=i18n.t("destinations.active.default"))

    def _sync_tree() -> None:
        tree.delete(*tree.get_children())
        for index, item in enumerate(dest_list):
            tree.insert("", "end", iid=str(index), values=(item["name"], item["path"]))

    def _selected_index() -> int | None:
        selection = tree.selection()
        if not selection:
            return None
        try:
            return int(selection[0])
        except ValueError:
            return None

    def _revalidate_and_refresh() -> None:
        active_var.set(_revalidate_active(dest_list, active_var.get().strip() or None) or "")
        _sync_tree()
        _refresh_active_label()
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

    def add_item() -> None:
        result = _edit_destination(win, i18n.t("destinations.add"))
        if result is None:
            return
        name, path = result
        error = _validate_name(name)
        if error is not None:
            messagebox.showwarning(
                i18n.t("destinations.title"),
                error,
                parent=win,
            )
            return
        dest_list.append({"name": name, "path": path})
        _revalidate_and_refresh()

    def edit_item() -> None:
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
        )
        if result is None:
            return
        name, path = result
        error = _validate_name(name, skip_index=index)
        if error is not None:
            messagebox.showwarning(
                i18n.t("destinations.title"),
                error,
                parent=win,
            )
            return
        old_name = item["name"]
        dest_list[index] = {"name": name, "path": path}
        if active_var.get().strip() == old_name:
            active_var.set(name)
        _revalidate_and_refresh()

    def delete_item() -> None:
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

    def set_active() -> None:
        index = _selected_index()
        if index is None:
            messagebox.showinfo(
                i18n.t("destinations.title"),
                i18n.t("destinations.error.select_first"),
                parent=win,
            )
            return
        active_var.set(dest_list[index]["name"])
        _refresh_active_label()
        _update_open_active_btn()

    def clear_active() -> None:
        active_var.set("")
        _refresh_active_label()
        _update_open_active_btn()

    crud = ttk.Frame(win)
    crud.grid(row=2, column=0, sticky="w", pady=(0, 8))
    ttk.Button(crud, text=i18n.t("destinations.add"), command=add_item).grid(
        row=0, column=0, padx=(0, 6)
    )
    ttk.Button(crud, text=i18n.t("destinations.edit"), command=edit_item).grid(
        row=0, column=1, padx=(0, 6)
    )
    ttk.Button(crud, text=i18n.t("destinations.delete"), command=delete_item).grid(
        row=0, column=2, padx=(0, 6)
    )
    ttk.Button(crud, text=i18n.t("destinations.set_active"), command=set_active).grid(
        row=0, column=3, padx=(0, 6)
    )
    ttk.Button(
        crud, text=i18n.t("destinations.clear_active"), command=clear_active
    ).grid(row=0, column=4)

    folders = ttk.Frame(win)
    folders.grid(row=3, column=0, sticky="w", pady=(0, 12))

    def open_transcripts() -> None:
        destinations.open_in_explorer(recovery.transcripts_dir())

    open_active_btn = ttk.Button(folders, text=i18n.t("destinations.open_active"))

    def open_active_folder() -> None:
        name = active_var.get().strip() or None
        path = destinations.resolve_save_dir(
            name, dest_list, recovery.transcripts_dir()
        )
        destinations.open_in_explorer(path)

    def _update_open_active_btn() -> None:
        if active_var.get().strip():
            open_active_btn.state(["!disabled"])
        else:
            open_active_btn.state(["disabled"])

    open_active_btn.config(command=open_active_folder)
    ttk.Button(
        folders, text=i18n.t("destinations.open_transcripts"), command=open_transcripts
    ).grid(row=0, column=0, padx=(0, 8))
    open_active_btn.grid(row=0, column=1)

    buttons = ttk.Frame(win)
    buttons.grid(row=4, column=0, sticky="e")

    def close() -> None:
        global _open_dialog
        _open_dialog = None
        win.destroy()

    def save() -> None:
        active_name = _revalidate_active(
            dest_list, active_var.get().strip() or None
        )
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
    ttk.Button(buttons, text=i18n.t("destinations.save"), command=save).grid(
        row=0, column=1
    )

    win.protocol("WM_DELETE_WINDOW", close)

    _revalidate_and_refresh()

    win.update_idletasks()
    width = max(win.winfo_reqwidth(), 520)
    height = max(win.winfo_reqheight(), 360)
    x = (win.winfo_screenwidth() - width) // 2
    y = (win.winfo_screenheight() - height) // 3
    win.geometry(f"{width}x{height}+{x}+{y}")

    win.deiconify()
    win.lift()
    win.attributes("-topmost", True)
    win.after(300, lambda: win.attributes("-topmost", False))
    win.focus_force()
