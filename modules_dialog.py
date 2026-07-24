"""
Modules-dialoog voor praatMaar (tkinter `Toplevel`).

Overzicht van ingebouwde modules (aan/uit), incrementele transcriptie en
optionele module-acties (knoppen per ingeschakelde module). Canvas-styling via
``ui_theme``.
"""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from tkinter import ttk
from typing import Any

import i18n
import ui_theme
from modules._contract import module_actions
from modules.registry import all_builtin_modules, modules_config_for_settings
from ui_icon import apply_window_icon

_open_dialog: tk.Toplevel | None = None


def module_shows_action_buttons(
    module_id: str,
    *,
    has_actions: bool,
    on_module_action: Callable[[str, str], None] | None,
    enabled_module_ids: set[str],
) -> bool:
    """Return whether action buttons should appear for ``module_id``."""

    return has_actions and on_module_action is not None and module_id in enabled_module_ids


def _enabled_module_ids_from_settings(settings: dict[str, Any]) -> set[str]:
    modules = settings.get("modules") or {}
    return {module_id for module_id, cfg in modules.items() if cfg.get("enabled")}


def _wrap_action_buttons(
    parent: tk.Misc,
    *,
    module_id: str,
    actions: list[Any],
    on_module_action: Callable[[str, str], None],
) -> ttk.Frame:
    """Place action buttons in wrapping rows (primary first)."""

    outer = ttk.Frame(parent)
    row_frame: ttk.Frame | None = None
    col = 0
    max_cols = 3
    for index, action in enumerate(actions):
        if row_frame is None or col >= max_cols:
            row_frame = ttk.Frame(outer)
            row_frame.pack(anchor="w", fill="x", pady=(0 if index == 0 else 6, 0))
            col = 0
        style = "Primary.TButton" if index == 0 else "TButton"
        ttk.Button(
            row_frame,
            text=i18n.t(action.label_key),
            style=style,
            command=lambda mid=module_id, aid=action.id: on_module_action(mid, aid),
        ).grid(row=0, column=col, padx=(0, 8))
        col += 1
    return outer


def _style_module_card(
    card: tk.Frame,
    *,
    enabled: bool,
    running: bool,
) -> None:
    if enabled and running:
        card.configure(
            background=ui_theme.COLOR_SURFACE,
            highlightbackground=ui_theme.COLOR_ACCENT,
            highlightthickness=1,
        )
    elif enabled:
        card.configure(
            background=ui_theme.COLOR_SURFACE,
            highlightbackground=ui_theme.COLOR_BORDER,
            highlightthickness=1,
        )
    else:
        card.configure(
            background=ui_theme.COLOR_CARD_OFF,
            highlightbackground=ui_theme.COLOR_CARD_OFF_BORDER,
            highlightthickness=1,
        )


def _rebuild_module_action_rows(
    *,
    module_cards: dict[str, dict[str, Any]],
    enabled_module_ids: set[str],
    on_module_action: Callable[[str, str], None] | None,
    toggled_enabled: dict[str, bool],
) -> None:
    for module in all_builtin_modules():
        meta = module_cards[module.id]
        actions_host: ttk.Frame = meta["actions_host"]
        for child in actions_host.winfo_children():
            child.destroy()

        running = module.id in enabled_module_ids
        enabled = bool(toggled_enabled.get(module.id, False))
        _style_module_card(meta["card"], enabled=enabled, running=running)
        meta["running_label"].configure(
            text=i18n.t("modules.running") if running else "",
            foreground=ui_theme.COLOR_OK if running else ui_theme.COLOR_TEXT_DIM,
        )

        actions = module_actions(module)
        if not module_shows_action_buttons(
            module.id,
            has_actions=bool(actions),
            on_module_action=on_module_action,
            enabled_module_ids=enabled_module_ids,
        ):
            continue
        assert on_module_action is not None
        row = _wrap_action_buttons(
            actions_host,
            module_id=module.id,
            actions=list(actions),
            on_module_action=on_module_action,
        )
        row.pack(anchor="w", fill="x", pady=(8, 0))


def open_modules_dialog(
    parent: tk.Misc,
    current: dict[str, Any],
    on_apply: Callable[[dict[str, Any]], None],
    *,
    wait: bool = False,
    on_module_action: Callable[[str, str], None] | None = None,
    enabled_module_ids: set[str] | None = None,
    get_enabled_module_ids: Callable[[], set[str]] | None = None,
) -> None:
    """Opent het modules-overzicht; bij Opslaan roept `on_apply` de bijgewerkte settings aan."""

    global _open_dialog

    if _open_dialog is not None and _open_dialog.winfo_exists():
        _open_dialog.deiconify()
        _open_dialog.lift()
        _open_dialog.attributes("-topmost", True)
        _open_dialog.after(300, lambda: _open_dialog.attributes("-topmost", False))
        _open_dialog.focus_force()
        if wait:
            parent.wait_window(_open_dialog)
        return

    settings = dict(current)
    modules_config = modules_config_for_settings(settings.get("modules") or {})
    incremental = bool(settings.get("incremental_transcription", False))
    running_ids = set(enabled_module_ids or ())

    dlg = tk.Toplevel(parent)
    _open_dialog = dlg
    dlg.withdraw()
    dlg.title(i18n.t("modules.title"))
    dlg.resizable(False, False)
    dlg.configure(background=ui_theme.COLOR_SURFACE)
    dlg.columnconfigure(0, weight=1)
    apply_window_icon(dlg)
    ui_theme.apply_dialog_style(dlg)

    outer = tk.Frame(dlg, background=ui_theme.COLOR_SURFACE)
    outer.grid(row=0, column=0, sticky="nsew")
    outer.columnconfigure(0, weight=1)

    header = tk.Frame(outer, background=ui_theme.COLOR_SURFACE_MUTED)
    header.grid(row=0, column=0, sticky="ew")
    header.columnconfigure(0, weight=1)
    ttk.Label(
        header,
        text=i18n.t("modules.intro_short"),
        wraplength=520,
        background=ui_theme.COLOR_SURFACE_MUTED,
        foreground=ui_theme.COLOR_TEXT_SECONDARY,
        font=ui_theme.FONT_UI_SMALL,
    ).grid(row=0, column=0, sticky="w", padx=18, pady=(14, 8))

    incremental_var = tk.BooleanVar(value=incremental)
    incr_box = tk.Frame(
        header,
        background=ui_theme.COLOR_SURFACE if not incremental else ui_theme.COLOR_ACCENT_SOFT,
        highlightbackground=ui_theme.COLOR_BORDER
        if not incremental
        else ui_theme.COLOR_ACCENT_BORDER,
        highlightthickness=1,
        padx=12,
        pady=10,
    )
    incr_box.grid(row=1, column=0, sticky="ew", padx=18, pady=(0, 14))
    incr_box.columnconfigure(1, weight=1)
    ttk.Checkbutton(incr_box, text="", variable=incremental_var, width=0).grid(
        row=0, column=0, sticky="nw", padx=(0, 8)
    )
    ttk.Label(
        incr_box,
        text=i18n.t("modules.incremental_title"),
        font=ui_theme.FONT_UI_BOLD,
        background=incr_box.cget("background"),
    ).grid(row=0, column=1, sticky="w")
    ttk.Label(
        incr_box,
        text=i18n.t("modules.incremental_hint"),
        wraplength=460,
        font=ui_theme.FONT_UI_TINY,
        foreground=ui_theme.COLOR_TEXT_DIM,
        background=incr_box.cget("background"),
    ).grid(row=1, column=1, sticky="w", pady=(2, 0))

    def _refresh_incr_style(*_args: object) -> None:
        on = bool(incremental_var.get())
        bg = ui_theme.COLOR_ACCENT_SOFT if on else ui_theme.COLOR_SURFACE
        border = ui_theme.COLOR_ACCENT_BORDER if on else ui_theme.COLOR_BORDER
        incr_box.configure(background=bg, highlightbackground=border)
        for child in incr_box.winfo_children():
            try:
                child.configure(background=bg)  # type: ignore[call-arg]
            except tk.TclError:
                pass

    incremental_var.trace_add("write", _refresh_incr_style)

    body = tk.Frame(outer, background=ui_theme.COLOR_SURFACE)
    body.grid(row=1, column=0, sticky="ew", padx=18, pady=(4, 8))
    body.columnconfigure(0, weight=1)

    ttk.Label(body, text=i18n.t("modules.list_heading").upper(), style="Section.TLabel").grid(
        row=0, column=0, sticky="w", pady=(0, 8)
    )

    module_vars: dict[str, tk.BooleanVar] = {}
    module_cards: dict[str, dict[str, Any]] = {}
    row = 1
    for module in all_builtin_modules():
        enabled = bool(modules_config.get(module.id, {}).get("enabled", module.default_enabled()))
        var = tk.BooleanVar(value=enabled)
        module_vars[module.id] = var
        running = module.id in running_ids

        card = tk.Frame(body, padx=14, pady=12)
        card.grid(row=row, column=0, sticky="ew", pady=(0, 10))
        card.columnconfigure(0, weight=1)
        _style_module_card(card, enabled=enabled, running=running)

        title_row = tk.Frame(card, background=card.cget("background"))
        title_row.grid(row=0, column=0, sticky="ew")
        title_row.columnconfigure(0, weight=1)

        title_left = tk.Frame(title_row, background=card.cget("background"))
        title_left.grid(row=0, column=0, sticky="w")
        ttk.Label(
            title_left,
            text=i18n.t(module.display_name_key()),
            font=ui_theme.FONT_NAME,
            background=card.cget("background"),
        ).pack(side="left")
        if module.id in ui_theme.EXPERIMENTAL_MODULE_IDS:
            badge = tk.Label(
                title_left,
                text=i18n.t("modules.badge.experimental"),
                font=ui_theme.FONT_UI_TINY_BOLD,
                foreground=ui_theme.COLOR_WARN,
                background=ui_theme.COLOR_WARN_BG,
                padx=5,
                pady=1,
            )
            badge.pack(side="left", padx=(8, 0))
        running_label = tk.Label(
            title_left,
            text=i18n.t("modules.running") if running else "",
            font=ui_theme.FONT_UI_TINY,
            foreground=ui_theme.COLOR_OK if running else ui_theme.COLOR_TEXT_DIM,
            background=card.cget("background"),
        )
        running_label.pack(side="left", padx=(8, 0))

        ttk.Checkbutton(title_row, text="", variable=var, width=0).grid(row=0, column=1, sticky="e")

        ttk.Label(
            card,
            text=i18n.t(module.description_key()),
            wraplength=500,
            font=ui_theme.FONT_UI_SMALL,
            foreground=ui_theme.COLOR_TEXT_MUTED if enabled else ui_theme.COLOR_TEXT_DIM,
            background=card.cget("background"),
        ).grid(row=1, column=0, sticky="w", pady=(4, 0))

        hint_key = ui_theme.MODULE_DEPENDENCY_HINT_KEYS.get(module.id)
        if hint_key:
            ttk.Label(
                card,
                text=i18n.t(hint_key),
                wraplength=500,
                font=ui_theme.FONT_UI_TINY,
                foreground=ui_theme.COLOR_TEXT_FAINT,
                background=card.cget("background"),
            ).grid(row=2, column=0, sticky="w", pady=(2, 0))

        actions_host = ttk.Frame(card)
        actions_host.grid(row=3, column=0, sticky="ew")

        module_cards[module.id] = {
            "card": card,
            "actions_host": actions_host,
            "running_label": running_label,
            "title_row": title_row,
        }

        def _on_toggle(
            *_args: object,
            mid: str = module.id,
            card_ref: tk.Frame = card,
        ) -> None:
            en = bool(module_vars[mid].get())
            run = mid in running_ids
            _style_module_card(card_ref, enabled=en, running=run)
            bg = card_ref.cget("background")
            for child in card_ref.winfo_children():
                try:
                    child.configure(background=bg)  # type: ignore[call-arg]
                except tk.TclError:
                    pass

        var.trace_add("write", _on_toggle)

        if module_shows_action_buttons(
            module.id,
            has_actions=bool(module_actions(module)),
            on_module_action=on_module_action,
            enabled_module_ids=running_ids,
        ):
            assert on_module_action is not None
            row_w = _wrap_action_buttons(
                actions_host,
                module_id=module.id,
                actions=list(module_actions(module)),
                on_module_action=on_module_action,
            )
            row_w.pack(anchor="w", fill="x", pady=(8, 0))

        row += 1

    status_var = tk.StringVar(value="")
    cancel_label = tk.StringVar(value=i18n.t("modules.cancel"))

    def _resolve_enabled_module_ids(updated_settings: dict[str, Any]) -> set[str]:
        if get_enabled_module_ids is not None:
            return get_enabled_module_ids()
        return _enabled_module_ids_from_settings(updated_settings)

    def save() -> None:
        nonlocal settings, running_ids
        updated_settings = {
            **settings,
            "incremental_transcription": bool(incremental_var.get()),
            "modules": {
                module_id: {"enabled": bool(var.get())} for module_id, var in module_vars.items()
            },
        }
        on_apply(updated_settings)
        settings = updated_settings
        running_ids = _resolve_enabled_module_ids(updated_settings)
        _rebuild_module_action_rows(
            module_cards=module_cards,
            enabled_module_ids=running_ids,
            on_module_action=on_module_action,
            toggled_enabled={mid: bool(v.get()) for mid, v in module_vars.items()},
        )
        status_var.set(i18n.t("modules.saved_actions_ready"))
        cancel_label.set(i18n.t("modules.close"))

    def cancel() -> None:
        dlg.destroy()

    footer = tk.Frame(outer, background=ui_theme.COLOR_SURFACE_FOOTER)
    footer.grid(row=2, column=0, sticky="ew")
    footer.columnconfigure(0, weight=1)
    tk.Label(
        footer,
        textvariable=status_var,
        foreground=ui_theme.COLOR_OK_TEXT,
        background=ui_theme.COLOR_SURFACE_FOOTER,
        font=ui_theme.FONT_UI_TINY,
        anchor="w",
    ).grid(row=0, column=0, sticky="w", padx=12, pady=10)
    btns = ttk.Frame(footer)
    btns.grid(row=0, column=1, sticky="e", padx=12, pady=8)
    ttk.Button(btns, textvariable=cancel_label, style="Ghost.TButton", command=cancel).grid(
        row=0, column=0, padx=(0, 8)
    )
    ttk.Button(btns, text=i18n.t("modules.save"), style="Primary.TButton", command=save).grid(
        row=0, column=1
    )

    dlg.protocol("WM_DELETE_WINDOW", cancel)

    def _on_destroy(_event: tk.Event) -> None:
        global _open_dialog
        if _open_dialog is dlg:
            _open_dialog = None

    dlg.bind("<Destroy>", _on_destroy)

    dlg.update_idletasks()
    width = max(dlg.winfo_reqwidth(), 560)
    height = max(dlg.winfo_reqheight(), 420)
    x = (dlg.winfo_screenwidth() - width) // 2
    y = (dlg.winfo_screenheight() - height) // 3
    dlg.geometry(f"{width}x{height}+{x}+{y}")

    dlg.deiconify()
    dlg.lift()
    dlg.attributes("-topmost", True)
    dlg.after(300, lambda: dlg.attributes("-topmost", False))
    dlg.focus_force()

    if wait:
        parent.wait_window(dlg)
