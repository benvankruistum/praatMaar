"""
Standalone instellingen-UI (eigen Tk-proces) + launcher voor de parent.

Op macOS crasht het sluiten van een Tk-`Toplevel` die in dezelfde Cocoa-
runloop als pystray/NSApp hangt (`PyEval_RestoreThread` → SIGABRT). Daarom
draait Instellingen daar in een apart proces met een echte `mainloop`.

Sneltoets-opname gebeurt via Tk KeyPress/KeyRelease (`use_tk_capture`) — dat
herkent Windows-/PC-toetsenborden (Win=Meta/Super, Alt, enz.) beter dan alleen
NSEvent-keycodes.

Parent: ``run_settings_subprocess(current)`` → dict of None.
Kind: ``python settings_process.py <in.json> <out.json>``
of frozen: ``praatMaar --praatmaar-settings-ui <in.json> <out.json>``.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


def run_settings_subprocess(current: dict[str, Any]) -> "dict[str, Any] | None":
    """
    Open Instellingen in een apart proces; return nieuwe settings of None.

    Alleen bedoeld voor macOS (eigen Tk-mainloop). Blokkeert tot het kind eindigt.
    """

    with tempfile.TemporaryDirectory(prefix="praatmaar-settings-") as tmp:
        tmp_path = Path(tmp)
        in_path = tmp_path / "in.json"
        out_path = tmp_path / "out.json"
        in_path.write_text(
            json.dumps(current, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        env = os.environ.copy()
        env["PRAATMAAR_SETTINGS_CHILD"] = "1"

        if getattr(sys, "frozen", False):
            cmd = [
                sys.executable,
                "--praatmaar-settings-ui",
                str(in_path),
                str(out_path),
            ]
        else:
            script = Path(__file__).resolve().parent / "settings_process.py"
            cmd = [sys.executable, str(script), str(in_path), str(out_path)]

        try:
            subprocess.run(cmd, env=env, check=False)
        except OSError as exc:
            print(f"Kon Instellingen niet openen: {exc}")
            return None

        if not out_path.is_file():
            return None
        try:
            data = json.loads(out_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            print(f"Instellingen-resultaat onleesbaar: {exc}")
            return None
        return data if isinstance(data, dict) else None


def main(argv: "list[str] | None" = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) >= 1 and args[0] == "--praatmaar-settings-ui":
        args = args[1:]
    if len(args) != 2:
        print(
            "Gebruik: settings_process.py <in.json> <out.json>",
            file=sys.stderr,
        )
        return 2

    in_path = Path(args[0])
    out_path = Path(args[1])
    current = json.loads(in_path.read_text(encoding="utf-8"))

    import tkinter as tk

    from settings import open_settings_dialog

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


if __name__ == "__main__":
    raise SystemExit(main())
