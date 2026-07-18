"""
Standalone Tk-UI in een apart proces + launcher voor de parent.

Op macOS crasht het sluiten van een Tk-`Toplevel` die in dezelfde Cocoa-
runloop als pystray/NSApp hangt (`PyEval_RestoreThread` → SIGABRT). Daarom
draaien Instellingen, Bestemmingen en Help daar in een apart proces met een
echte `mainloop`.

Sneltoets-opname (Instellingen) gebeurt via Tk KeyPress/KeyRelease
(`use_tk_capture`) — dat herkent Windows-/PC-toetsenborden beter dan alleen
NSEvent-keycodes.

Parent:
  ``run_settings_subprocess(current)`` → dict of None
  ``run_destinations_subprocess(current)`` → dict of None
  ``run_help_subprocess(current)`` → None (geen resultaat)

Kind: ``python settings_process.py --praatmaar-<kind>-ui <in.json> [out.json]``
of frozen: ``praatMaar --praatmaar-<kind>-ui ...``.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Literal

DialogKind = Literal["settings", "destinations", "help"]

_FLAG = {
    "settings": "--praatmaar-settings-ui",
    "destinations": "--praatmaar-destinations-ui",
    "help": "--praatmaar-help-ui",
}


def _run_dialog_subprocess(
    kind: DialogKind,
    current: dict[str, Any],
    *,
    expect_result: bool,
) -> dict[str, Any] | None:
    """Open een Tk-dialoog in een apart proces. Blokkeert tot het kind eindigt."""

    with tempfile.TemporaryDirectory(prefix=f"praatmaar-{kind}-") as tmp:
        tmp_path = Path(tmp)
        in_path = tmp_path / "in.json"
        out_path = tmp_path / "out.json"
        in_path.write_text(
            json.dumps(current, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        env = os.environ.copy()
        env["PRAATMAAR_SETTINGS_CHILD"] = "1"

        flag = _FLAG[kind]
        if getattr(sys, "frozen", False):
            cmd = [sys.executable, flag, str(in_path)]
        else:
            script = Path(__file__).resolve().parent / "settings_process.py"
            cmd = [sys.executable, str(script), flag, str(in_path)]
        if expect_result:
            cmd.append(str(out_path))

        try:
            subprocess.run(cmd, env=env, check=False)
        except OSError as exc:
            print(f"Kon {kind} niet openen: {exc}")
            return None

        if not expect_result:
            return None
        if not out_path.is_file():
            return None
        try:
            data = json.loads(out_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            print(f"{kind}-resultaat onleesbaar: {exc}")
            return None
        return data if isinstance(data, dict) else None


def run_settings_subprocess(current: dict[str, Any]) -> dict[str, Any] | None:
    """Open Instellingen in een apart proces; return nieuwe settings of None."""

    return _run_dialog_subprocess("settings", current, expect_result=True)


def run_destinations_subprocess(
    current: dict[str, Any],
) -> dict[str, Any] | None:
    """Open Bestemmingen in een apart proces; return nieuwe settings of None."""

    return _run_dialog_subprocess("destinations", current, expect_result=True)


def run_help_subprocess(current: dict[str, Any] | None = None) -> None:
    """Open Help in een apart proces (geen resultaat)."""

    _run_dialog_subprocess("help", current or {}, expect_result=False)


def _apply_ui_language(current: dict[str, Any]) -> None:
    import i18n

    if "ui_language" in current:
        i18n.set_ui_language(str(current["ui_language"]))


def _run_settings_child(in_path: Path, out_path: Path) -> int:
    import tkinter as tk

    from settings import open_settings_dialog

    current = json.loads(in_path.read_text(encoding="utf-8"))
    _apply_ui_language(current)

    root = tk.Tk()
    root.withdraw()
    root.title("praatMaar — Instellingen")

    def on_apply(new_settings: dict[str, Any]) -> None:
        out_path.write_text(
            json.dumps(new_settings, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    try:
        open_settings_dialog(
            root,
            current,
            on_apply,
            set_capture=None,
            wait=True,
            use_tk_capture=True,
        )
    finally:
        try:
            root.destroy()
        except Exception:
            pass
    return 0


def _run_destinations_child(in_path: Path, out_path: Path) -> int:
    import tkinter as tk

    from destinations_dialog import open_destinations_dialog

    current = json.loads(in_path.read_text(encoding="utf-8"))
    _apply_ui_language(current)

    root = tk.Tk()
    root.withdraw()
    root.title("praatMaar")

    def on_apply(new_settings: dict[str, Any]) -> None:
        out_path.write_text(
            json.dumps(new_settings, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    try:
        open_destinations_dialog(root, current, on_apply, wait=True)
    finally:
        try:
            root.destroy()
        except Exception:
            pass
    return 0


def _run_help_child(in_path: Path) -> int:
    import tkinter as tk

    from help_dialog import open_help

    current = json.loads(in_path.read_text(encoding="utf-8"))
    _apply_ui_language(current)

    root = tk.Tk()
    root.withdraw()
    root.title("praatMaar")

    try:
        open_help(root, wait=True)
    finally:
        try:
            root.destroy()
        except Exception:
            pass
    return 0


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args:
        print(
            "Gebruik: settings_process.py --praatmaar-<kind>-ui <in.json> [out.json]",
            file=sys.stderr,
        )
        return 2

    flag = args[0]
    rest = args[1:]

    if flag == "--praatmaar-settings-ui":
        if len(rest) != 2:
            print(
                "Gebruik: settings_process.py --praatmaar-settings-ui <in.json> <out.json>",
                file=sys.stderr,
            )
            return 2
        return _run_settings_child(Path(rest[0]), Path(rest[1]))

    if flag == "--praatmaar-destinations-ui":
        if len(rest) != 2:
            print(
                "Gebruik: settings_process.py --praatmaar-destinations-ui <in.json> <out.json>",
                file=sys.stderr,
            )
            return 2
        return _run_destinations_child(Path(rest[0]), Path(rest[1]))

    if flag == "--praatmaar-help-ui":
        if len(rest) != 1:
            print(
                "Gebruik: settings_process.py --praatmaar-help-ui <in.json>",
                file=sys.stderr,
            )
            return 2
        return _run_help_child(Path(rest[0]))

    # Backward-compat: oud formaat zonder flag (alleen settings).
    if len(args) == 2 and not args[0].startswith("--"):
        return _run_settings_child(Path(args[0]), Path(args[1]))

    print(
        "Gebruik: settings_process.py --praatmaar-<kind>-ui <in.json> [out.json]",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
