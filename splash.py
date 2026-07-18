"""
Laadscherm (splash) voor praatMaar.

Toont bij het opstarten een klein venster met een statusregel en een
voortgangsbalk terwijl het Whisper-model op een achtergrond-thread wordt
gedownload en geladen. Zonder dit scherm zou de gebruiker bij een eerste,
minutenlange download alleen een onzichtbare console-melding krijgen
(de app draait onder `pythonw.exe`, dus zonder console).

Techniek: tkinter (stdlib), consistent met `indicator.py`. Geen extra
dependencies. Het venster draait zijn eigen mainloop op de hoofdthread; de
eigenlijke laad-taak draait op een aparte thread en meldt voortgang via een
thread-veilige queue.

Gebruik::

    splash = Splash()
    model = splash.run(worker)   # worker(reporter) draait op een bg-thread

`worker` krijgt een `reporter` (dit Splash-object) en gebruikt:
  - reporter.set_status("Model wordt geladen…")
  - reporter.set_progress(0.62, "28,4 / 46,1 MB")   # bepaald percentage
  - reporter.set_progress(None)                       # onbepaald ("bezig")

`run()` retourneert wat `worker` teruggeeft, of gooit de exception door die
`worker` opwierp (nadat de gebruiker de foutmelding heeft weggeklikt).
"""

from __future__ import annotations

import queue
import sys
import threading
from collections.abc import Callable
from typing import Any

# =========================================================
# UITERLIJK (constanten — bedoeld om te tunen)
# =========================================================

SPLASH_WIDTH = 400
SPLASH_HEIGHT = 170

# Poll-tempo van de GUI (ms). ~30 ms ≈ 33 fps voor een vloeiende animatie.
POLL_INTERVAL_MS = 30

# Kleuren (consistent met de opname-pill in indicator.py).
BG_COLOR = "#202124"
TEXT_COLOR = "#f1f3f4"
MUTED_COLOR = "#9aa0a6"
ACCENT_COLOR = "#ffb020"
ERROR_COLOR = "#ff5252"
TRACK_COLOR = "#3c4043"

# Voortgangsbalk.
BAR_X1 = 30
BAR_X2 = SPLASH_WIDTH - 30
BAR_Y = 108
BAR_HEIGHT = 10


def _ui_fonts() -> tuple[tuple, tuple, tuple]:
    """Platform-conforme UI-fonts voor het laadscherm."""

    if sys.platform == "darwin":
        return (
            ("Helvetica Neue", 15, "bold"),
            ("Helvetica Neue", 10),
            ("Helvetica Neue", 9),
        )
    return (
        ("Segoe UI Semibold", 15),
        ("Segoe UI", 10),
        ("Segoe UI", 9),
    )


TITLE_FONT, STATUS_FONT, DETAIL_FONT = _ui_fonts()


class Splash:
    """
    Het laadscherm. Bezit zijn eigen tkinter-root en mainloop.

    Alle `set_*`-methoden zijn veilig vanaf elke thread: ze leggen een bericht
    in een queue die de GUI op zijn poll-tick verwerkt.
    """

    def __init__(self, app_name: str = "praatMaar") -> None:
        import tkinter as tk

        self._tk = tk
        self._queue: queue.Queue[tuple[Any, ...]] = queue.Queue()

        self._result: Any = None
        self._error: BaseException | None = None
        self._worker_done = False

        # Voortgangsstaat.
        self._fraction: float | None = 0.0  # None = onbepaald ("bezig")
        self._indeterminate_phase = 0.0
        self._frame = 0
        self._error_shown = False

        self._build_window(app_name)

    # ----- opbouw -----

    def _build_window(self, app_name: str) -> None:
        tk = self._tk

        self.root = tk.Tk()
        self.root.withdraw()
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.configure(bg=BG_COLOR)

        self._center()

        self.canvas = tk.Canvas(
            self.root,
            width=SPLASH_WIDTH,
            height=SPLASH_HEIGHT,
            highlightthickness=0,
            bd=0,
            bg=BG_COLOR,
        )
        self.canvas.pack()

        c = self.canvas

        # Titel.
        c.create_text(
            SPLASH_WIDTH / 2,
            40,
            text=app_name,
            fill=TEXT_COLOR,
            font=TITLE_FONT,
        )

        # Statusregel.
        self._status_item = c.create_text(
            SPLASH_WIDTH / 2,
            74,
            text="Bezig met opstarten…",
            fill=MUTED_COLOR,
            font=STATUS_FONT,
        )

        # Voortgangsbalk: track + vulling.
        c.create_rectangle(
            BAR_X1,
            BAR_Y,
            BAR_X2,
            BAR_Y + BAR_HEIGHT,
            fill=TRACK_COLOR,
            outline="",
        )
        self._bar_fill = c.create_rectangle(
            BAR_X1,
            BAR_Y,
            BAR_X1,
            BAR_Y + BAR_HEIGHT,
            fill=ACCENT_COLOR,
            outline="",
        )

        # Detailregel (percentage / MB) onder de balk.
        self._detail_item = c.create_text(
            SPLASH_WIDTH / 2,
            BAR_Y + BAR_HEIGHT + 20,
            text="",
            fill=MUTED_COLOR,
            font=DETAIL_FONT,
        )

        # Verborgen "Sluiten"-knop, alleen zichtbaar in de foutstaat
        # (een overrideredirect-venster heeft geen eigen sluitknop).
        self._close_button = tk.Button(
            self.root,
            text="Sluiten",
            command=self.root.quit,
            relief="flat",
            bg=TRACK_COLOR,
            fg=TEXT_COLOR,
            activebackground=ERROR_COLOR,
            activeforeground=TEXT_COLOR,
            font=STATUS_FONT,
            bd=0,
            padx=14,
            pady=4,
            cursor="hand2",
        )

    def _center(self) -> None:
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        x = (screen_w - SPLASH_WIDTH) // 2
        y = (screen_h - SPLASH_HEIGHT) // 2
        self.root.geometry(f"{SPLASH_WIDTH}x{SPLASH_HEIGHT}+{x}+{y}")

    # ----- reporter-API (thread-veilig) -----

    def set_status(self, text: str) -> None:
        """Zet de statusregel (bijv. 'Model wordt geladen…')."""

        self._queue.put(("status", text))

    def set_progress(self, fraction: float | None, detail: str = "") -> None:
        """
        Werkt de voortgang bij.

        fraction: 0.0–1.0 voor een bepaald percentage, of None voor een
        onbepaalde 'bezig'-animatie.
        detail: optionele regel onder de balk (bijv. '28,4 / 46,1 MB').
        """

        self._queue.put(("progress", fraction, detail))

    # ----- levenscyclus -----

    def run(self, worker: Callable[[Splash], Any]) -> Any:
        """
        Toont het laadscherm en voert `worker(self)` uit op een achtergrond-thread.

        Blokkeert tot de taak klaar is (of tot de gebruiker een foutmelding
        wegklikt). Retourneert het resultaat van `worker`, of gooit de
        exception door die `worker` opwierp.
        """

        thread = threading.Thread(target=self._run_worker, args=(worker,), daemon=True)
        thread.start()

        self.root.deiconify()
        self.root.after(POLL_INTERVAL_MS, self._tick)
        self.root.mainloop()

        try:
            self.root.destroy()
        except Exception:
            pass

        if self._error is not None:
            raise self._error

        return self._result

    def _run_worker(self, worker: Callable[[Splash], Any]) -> None:
        try:
            self._result = worker(self)
            self._queue.put(("done",))
        except BaseException as exc:  # noqa: BLE001 — melden i.p.v. verzwelgen
            self._error = exc
            self._queue.put(("error", str(exc)))

    # ----- poll-tick (GUI-thread) -----

    def _tick(self) -> None:
        try:
            while True:
                message = self._queue.get_nowait()
                self._handle_message(message)
        except queue.Empty:
            pass

        self._frame += 1

        if self._worker_done and self._error is None:
            # Taak klaar zonder fout: mainloop netjes verlaten.
            self.root.quit()
            return

        self._render()
        self.root.after(POLL_INTERVAL_MS, self._tick)

    def _handle_message(self, message: tuple[Any, ...]) -> None:
        kind = message[0]

        if kind == "status":
            self.canvas.itemconfigure(self._status_item, text=message[1])

        elif kind == "progress":
            self._fraction = message[1]
            detail = message[2]
            self.canvas.itemconfigure(self._detail_item, text=detail)

        elif kind == "done":
            self._worker_done = True

        elif kind == "error":
            self._show_error(message[1])

    def _show_error(self, text: str) -> None:
        if self._error_shown:
            return

        self._error_shown = True
        c = self.canvas

        c.itemconfigure(
            self._status_item,
            text="Het model kon niet worden geladen.",
            fill=ERROR_COLOR,
        )
        c.itemconfigure(self._detail_item, text=_shorten(text), fill=MUTED_COLOR)

        # Balk verbergen, knop tonen.
        c.itemconfigure(self._bar_fill, state="hidden")
        self._close_button.place(relx=0.5, y=BAR_Y + BAR_HEIGHT + 18, anchor="center")

    # ----- tekenen -----

    def _render(self) -> None:
        if self._error_shown:
            return

        c = self.canvas
        span = BAR_X2 - BAR_X1

        if self._fraction is None:
            # Onbepaald: een lichtje dat heen en weer over de balk glijdt.
            chunk = span * 0.28
            travel = span - chunk
            # Driehoeksgolf 0..1..0 zodat het lichtje terugkaatst.
            t = (self._frame % 80) / 80.0
            phase = 1.0 - abs(2.0 * t - 1.0)
            x1 = BAR_X1 + travel * phase
            c.coords(self._bar_fill, x1, BAR_Y, x1 + chunk, BAR_Y + BAR_HEIGHT)
        else:
            fraction = max(0.0, min(1.0, self._fraction))
            x2 = BAR_X1 + span * fraction
            c.coords(self._bar_fill, BAR_X1, BAR_Y, x2, BAR_Y + BAR_HEIGHT)


def _shorten(text: str, limit: int = 70) -> str:
    """Kort een lange foutmelding in tot één leesbare regel."""

    text = " ".join(text.split())
    if len(text) > limit:
        return text[: limit - 1] + "…"
    return text
