"""Meeting Buddy agenda dialog: library, recents, and start/edit flows."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import i18n

from .agenda_store import (
    default_new_path,
    display_title,
    list_agendas,
    list_recent,
    load_agenda,
    save_agenda,
    touch_recent,
)
from .prep import parse_agenda


@dataclass(frozen=True)
class AgendaDialogResult:
    agenda_text: str
    path: Path | None
    start: bool


def can_start_meeting(body: str) -> bool:
    """Return whether the agenda body has at least one topic."""

    return bool(parse_agenda(body))


def library_sections(
    *,
    recent: list[Path],
    all_agendas: list[Path],
) -> list[tuple[str, list[Path]]]:
    """Group library paths into Recent (optional) then All sections."""

    sections: list[tuple[str, list[Path]]] = []
    if recent:
        sections.append(("recent", recent))
    sections.append(("all", all_agendas))
    return sections


def show_agenda_dialog(
    *,
    agenda_text: str,
    path: Path | None,
    app_dir: Path,
    mode: Literal["start", "edit"],
    parent: Any = None,
) -> AgendaDialogResult | None:
    """Show agenda UI; return ``None`` on cancel (start mode only)."""

    import tkinter as tk
    from tkinter import messagebox, scrolledtext, ttk

    from ui_icon import apply_window_icon

    dlg = tk.Toplevel(parent)
    dlg.withdraw()
    dlg.title(i18n.t("modules.meeting_buddy.dialog.title"))
    apply_window_icon(dlg)
    dlg.resizable(True, True)
    dlg.columnconfigure(0, weight=1)
    dlg.rowconfigure(0, weight=1)

    frame = ttk.Frame(dlg, padding=12)
    frame.grid(row=0, column=0, sticky="nsew")
    frame.columnconfigure(1, weight=1)
    frame.rowconfigure(0, weight=1)

    current_path: Path | None = path

    library_frame = ttk.Frame(frame)
    library_frame.grid(row=0, column=0, sticky="ns", padx=(0, 8))
    library = tk.Listbox(library_frame, width=28, height=12, exportselection=False)
    library.pack(side="left", fill="y")
    library_scroll = ttk.Scrollbar(library_frame, orient="vertical", command=library.yview)
    library_scroll.pack(side="right", fill="y")
    library.configure(yscrollcommand=library_scroll.set)

    editor = ttk.Frame(frame)
    editor.grid(row=0, column=1, sticky="nsew")
    editor.columnconfigure(0, weight=1)
    editor.rowconfigure(1, weight=1)
    ttk.Label(editor, text=i18n.t("modules.meeting_buddy.dialog.agenda_prompt")).grid(
        row=0, column=0, sticky="w", pady=(0, 4)
    )
    agenda = scrolledtext.ScrolledText(editor, width=40, height=12, wrap="word")
    agenda.grid(row=1, column=0, sticky="nsew")
    if agenda_text:
        agenda.insert("1.0", agenda_text)

    topic_count = tk.StringVar()
    ttk.Label(frame, textvariable=topic_count).grid(
        row=1, column=0, columnspan=2, sticky="w", pady=(8, 0)
    )

    entry_paths: list[Path | None] = []

    def refresh_topic_count() -> None:
        count = len(parse_agenda(agenda.get("1.0", "end")))
        topic_count.set(i18n.t("modules.meeting_buddy.dialog.topic_count", count=count))

    def current_body() -> str:
        return agenda.get("1.0", "end").strip()

    def populate_library() -> None:
        nonlocal entry_paths
        library.delete(0, "end")
        entry_paths = []
        recent = list_recent(app_dir)
        all_items = list_agendas(app_dir)
        for section_id, paths in library_sections(recent=recent, all_agendas=all_items):
            section_label = i18n.t(f"modules.meeting_buddy.dialog.{section_id}")
            library.insert("end", section_label)
            entry_paths.append(None)
            for item_path in paths:
                library.insert("end", f"  {display_title(item_path)}")
                entry_paths.append(item_path)

    def load_path(item_path: Path) -> None:
        nonlocal current_path
        _title, body = load_agenda(item_path)
        agenda.delete("1.0", "end")
        agenda.insert("1.0", body)
        current_path = item_path
        refresh_topic_count()
        touch_recent(app_dir, item_path)

    def on_library_select(_event: object = None) -> None:
        selection = library.curselection()
        if not selection:
            return
        index = int(selection[0])
        if index < 0 or index >= len(entry_paths):
            return
        item_path = entry_paths[index]
        if item_path is not None:
            load_path(item_path)

    def require_topics() -> bool:
        if can_start_meeting(current_body()):
            return True
        messagebox.showwarning(
            i18n.t("modules.meeting_buddy.dialog.title"),
            i18n.t("modules.meeting_buddy.dialog.empty_agenda"),
            parent=dlg,
        )
        agenda.focus_set()
        return False

    def do_save(*, ask_path: bool) -> bool:
        from tkinter import filedialog

        nonlocal current_path
        if not require_topics():
            return False
        body = current_body()
        target = current_path
        if ask_path or target is None:
            initial = default_new_path(app_dir, body) if target is None else target
            chosen = filedialog.asksaveasfilename(
                parent=dlg,
                title=i18n.t("modules.meeting_buddy.dialog.save_as"),
                defaultextension=".md",
                filetypes=[
                    (i18n.t("modules.meeting_buddy.dialog.markdown_filter"), "*.md"),
                    ("All files", "*.*"),
                ],
                initialdir=str(initial.parent),
                initialfile=initial.name,
            )
            if not chosen:
                return False
            target = Path(chosen)
        save_agenda(target, body)
        current_path = target
        touch_recent(app_dir, target)
        populate_library()
        return True

    def open_file() -> None:
        from tkinter import filedialog

        chosen = filedialog.askopenfilename(
            parent=dlg,
            title=i18n.t("modules.meeting_buddy.dialog.open_file"),
            filetypes=[
                (i18n.t("modules.meeting_buddy.dialog.markdown_filter"), "*.md"),
                ("All files", "*.*"),
            ],
        )
        if not chosen:
            return
        load_path(Path(chosen))

    result: AgendaDialogResult | None = None

    def finish(*, start: bool) -> None:
        nonlocal result
        result = AgendaDialogResult(
            agenda_text=current_body(),
            path=current_path,
            start=start,
        )
        dlg.destroy()

    def save() -> None:
        nonlocal current_path
        if not require_topics():
            return
        body = current_body()
        if current_path is None:
            target = default_new_path(app_dir, body)
            save_agenda(target, body)
            current_path = target
            touch_recent(app_dir, target)
            populate_library()
            return
        save_agenda(current_path, body)
        touch_recent(app_dir, current_path)

    def save_as() -> None:
        do_save(ask_path=True)

    def start_meeting() -> None:
        if not require_topics():
            return
        if current_path is not None:
            touch_recent(app_dir, current_path)
        finish(start=True)

    def close_edit() -> None:
        finish(start=False)

    def cancel() -> None:
        dlg.destroy()

    agenda.bind("<KeyRelease>", lambda _event: refresh_topic_count())
    library.bind("<<ListboxSelect>>", on_library_select)
    library.bind("<Double-Button-1>", on_library_select)
    refresh_topic_count()
    populate_library()

    file_buttons = ttk.Frame(frame)
    file_buttons.grid(row=3, column=0, columnspan=2, sticky="w", pady=(10, 0))
    ttk.Button(
        file_buttons,
        text=i18n.t("modules.meeting_buddy.dialog.open_file"),
        command=open_file,
    ).grid(row=0, column=0, padx=(0, 8))
    ttk.Button(
        file_buttons,
        text=i18n.t("modules.meeting_buddy.dialog.save"),
        command=save,
    ).grid(row=0, column=1, padx=(0, 8))
    ttk.Button(
        file_buttons,
        text=i18n.t("modules.meeting_buddy.dialog.save_as"),
        command=save_as,
    ).grid(row=0, column=2)

    action_buttons = ttk.Frame(frame)
    action_buttons.grid(row=4, column=0, columnspan=2, sticky="e", pady=(10, 0))
    if mode == "start":
        ttk.Button(
            action_buttons,
            text=i18n.t("modules.meeting_buddy.dialog.cancel"),
            command=cancel,
        ).grid(row=0, column=0, padx=(0, 8))
        ttk.Button(
            action_buttons,
            text=i18n.t("modules.meeting_buddy.dialog.start"),
            command=start_meeting,
        ).grid(row=0, column=1)
        dlg.protocol("WM_DELETE_WINDOW", cancel)
        dlg.bind("<Escape>", lambda _event: cancel())
    else:
        ttk.Button(
            action_buttons,
            text=i18n.t("modules.meeting_buddy.dialog.close"),
            command=close_edit,
        ).grid(row=0, column=0)
        dlg.protocol("WM_DELETE_WINDOW", close_edit)
        dlg.bind("<Escape>", lambda _event: close_edit())

    dlg.update_idletasks()
    width = max(dlg.winfo_reqwidth(), 680)
    height = max(dlg.winfo_reqheight(), 420)
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
