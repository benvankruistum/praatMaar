from __future__ import annotations

import signal
import sys
import threading
import time
import uuid
from pathlib import Path
from typing import Any

import app_logging
import config
import destinations
import host
import hotkeys
import i18n
import recovery
import win_identity
from indicator import (
    RecordingIndicator,
)
from modules import (
    CapabilityRegistry,
    CycleEvent,
    CycleEventType,
    ModuleBus,
    SharedWhisper,
    load_enabled_modules,
    modules_config_for_settings,
    noop_ui_dispatch,
    sanitize_modules_config,
    tray_action_entries,
    tray_root_action_entries,
)
from opnamesessie import Opnamesessie
from splash import Splash

# De zware libraries worden bewust NIET bij import geladen, maar pas in
# _load_dependencies() op de achtergrond-thread van het laadscherm. Zo verschijnt
# de splash direct (de module blijft licht) en zie je de onderdelen laden.
# Ze worden daar aan deze globals toegewezen zodat de rest van de code ze
# ongewijzigd als `np`, `sd`, ... kan blijven gebruiken. `settings` en `tray`
# worden lazy geïmporteerd (settings trekt zelf sounddevice binnen).
np = None  # numpy
sd = None  # sounddevice
pyperclip = None
keyboard = None  # pynput.keyboard
write_wav = None  # scipy.io.wavfile.write
WhisperModel = None  # faster_whisper.WhisperModel
TrayIcon = None  # tray.TrayIcon

# De console-meldingen gebruiken tekens als ●, ■ en ×. Op Windows valt stdout
# terug op cp1252 zodra de uitvoer naar een bestand of pipe gaat, en dan crasht
# een print op die tekens. Forceer UTF-8 zodat dat nooit gebeurt.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass


# =========================================================
# INSTELLINGEN
# =========================================================

# Whisper-model:
# - "base"   = sneller, iets minder nauwkeurig
# - "small"  = goede balans voor CPU
# - "medium" = nauwkeuriger, maar langzamer
MODEL_NAME = "small"

# CPU-instellingen.
# Voor een gewone Windows-computer is dit een veilige start.
DEVICE = "cpu"
COMPUTE_TYPE = "int8"

# Spraakherkenning (Whisper). UI-taal staat apart in i18n.
LANGUAGE = "nl"

# Audio-instellingen.
SAMPLE_RATE = 16000
CHANNELS = 1

# Laat op None staan om de standaardmicrofoon van Windows te gebruiken.
# Vul eventueel een apparaatnummer in, bijvoorbeeld:
# MICROPHONE_DEVICE = 2
MICROPHONE_DEVICE: int | None = None

# Automatisch plakken in het actieve invoerveld.
AUTO_PASTE = True

# Microfoonstream warm houden tussen opnames (sneller, mic blijft open).
# Default uit: privacyvriendelijker, vooral bij automatisch meestarten.
WARM_MICROPHONE = False

# Korte wachttijd voordat Ctrl+V wordt uitgevoerd.
PASTE_DELAY_SECONDS = 0.30

# Minimale opnameduur.
# Zeer korte, per ongeluk gestarte opnames worden genegeerd.
MINIMUM_RECORDING_SECONDS = 0.30

# Tijdelijke audiobestanden na verwerking verwijderen.
DELETE_TEMP_AUDIO = True

# Positie van de opname-indicator: "boven-midden", "onder-midden" of
# "laatst-geplaatst" (na slepen van de pill).
INDICATOR_POSITION = "boven-midden"
INDICATOR_XY: tuple[int, int] | None = None

# Bedieningsmodus:
# - "toggle" = indrukken start, nogmaals indrukken stopt en transcribeert
# - "ptt"    = push-to-talk: ingedrukt houden neemt op, loslaten stopt
MODE = "toggle"

# De sneltoets als set tokens (zie hotkeys.py). Standaard Ctrl+Shift+Alt+Spatie.
HOTKEY_TOKENS: set[str] = set(hotkeys.DEFAULT_HOTKEY)


# ---------------------------------------------------------
# Gebruikersinstellingen laden (overschrijven de defaults hierboven).
# Bron: %APPDATA%\praatMaar\config.json — bewerkbaar via het
# systeemvak-menu → Instellingen.
# ---------------------------------------------------------
_user_config = config.load_config()
if "model" in _user_config:
    MODEL_NAME = str(_user_config["model"])
if "microphone_device" in _user_config:
    MICROPHONE_DEVICE = _user_config["microphone_device"]
if "auto_paste" in _user_config:
    AUTO_PASTE = bool(_user_config["auto_paste"])
if "warm_microphone" in _user_config:
    WARM_MICROPHONE = bool(_user_config["warm_microphone"])
if "indicator_position" in _user_config:
    from indicator._contract import normalize_indicator_position, sanitize_indicator_xy

    INDICATOR_POSITION = normalize_indicator_position(_user_config["indicator_position"])
    INDICATOR_XY = sanitize_indicator_xy(_user_config.get("indicator_xy"))
    if INDICATOR_POSITION == "laatst-geplaatst" and INDICATOR_XY is None:
        INDICATOR_POSITION = "boven-midden"
if _user_config.get("mode") in ("toggle", "ptt"):
    MODE = str(_user_config["mode"])
if isinstance(_user_config.get("hotkey"), list) and _user_config["hotkey"]:
    HOTKEY_TOKENS = {str(token) for token in _user_config["hotkey"]}
if "speech_language" in _user_config:
    LANGUAGE = i18n.normalize_language(
        _user_config["speech_language"],
        allowed=i18n.SUPPORTED_SPEECH_LANGUAGES,
    )
_ui = i18n.normalize_language(
    _user_config.get("ui_language"),
    allowed=i18n.SUPPORTED_UI_LANGUAGES,
)
i18n.set_ui_language(_ui)

DESTINATIONS = destinations.sanitize_destinations(_user_config.get("destinations"))
_active_raw = _user_config.get("active_destination")
if _active_raw is None:
    ACTIVE_DESTINATION: str | None = None
else:
    _active_name = str(_active_raw).strip() or None
    if _active_name and any(d["name"] == _active_name for d in DESTINATIONS):
        ACTIVE_DESTINATION = _active_name
    else:
        ACTIVE_DESTINATION = None

MODULES_CONFIG = sanitize_modules_config(_user_config.get("modules"))
INCREMENTAL_TRANSCRIPTION = bool(_user_config.get("incremental_transcription", False))

shared_whisper = SharedWhisper()
capability_registry = CapabilityRegistry()
module_bus = ModuleBus(capabilities=capability_registry)
module_bus.set_modules(
    load_enabled_modules(
        MODULES_CONFIG,
        whisper=shared_whisper,
        capabilities=capability_registry,
    )
)

_ui_dispatch = noop_ui_dispatch


def _emit_cycle_event(event: CycleEvent) -> None:
    module_bus.emit(event)


def _reload_modules() -> None:
    """Herlaadt enabled modules na een instellingenwijziging."""

    module_bus.shutdown()
    module_bus.set_modules(
        load_enabled_modules(
            MODULES_CONFIG,
            ui_dispatch=_ui_dispatch,
            whisper=shared_whisper,
            capabilities=capability_registry,
        )
    )
    if _tray is not None:
        _tray.refresh_modules_menu()


# =========================================================
# GLOBALE STATUS (toetsenbord + wiring)
# =========================================================
#
# De dicteercyclus-lifecycle zit in `Opnamesessie` (`opnamesessie.py`).
# Hier blijven alleen de sneltoets-routing en capture-modus voor Instellingen.
# De tokenisatie staat in hotkeys.py.

state_lock = threading.RLock()

# Houdt bij welke onderdelen van de combinatie zijn ingedrukt.
pressed_tokens: set[str] = set()

# Voorkomt herhaald afgaan door keyboard-repeat.
toggle_latched = False

# Terwijl het instellingen-dialoog een nieuwe sneltoets opneemt, stuurt de globale
# listener elke toets door naar deze callback en voert géén normale actie uit
# (zodat het opnemen de dicteeropname niet start).
capturing = False
_capture_cb: Any | None = None

# Systeemvak (gezet in main); nodig voor live UI-taalwissel.
_tray = None

# Opname-indicator (gezet in main); nodig voor bestemmings-pill-updates.
_indicator: RecordingIndicator | None = None


# =========================================================
# MODEL LADEN
# =========================================================

# Het model wordt niet meer bij import geladen, maar in main() op een
# achtergrond-thread terwijl het laadscherm (splash.py) de voortgang toont.
# Zo ziet de gebruiker bij een eerste, minutenlange download een venster in
# plaats van een onzichtbare console-melding (de app draait onder pythonw).
model: WhisperModel | None = None


def _load_dependencies(reporter: Splash) -> None:
    """
    Importeert de zware libraries op de achtergrond-thread van het laadscherm en
    meldt elke stap. Zo verschijnt de splash direct — de module-import zelf blijft
    licht — en ziet de gebruiker welke onderdelen laden.

    De modules worden aan module-globals toegewezen zodat de rest van de code ze
    ongewijzigd als `np`, `sd`, `WhisperModel`, ... kan blijven gebruiken. Deze
    functie draait vóór het model geladen wordt en vóór de listener/tray starten,
    dus alle globals zijn op tijd gevuld.
    """

    global np, sd, pyperclip, keyboard, write_wav, WhisperModel, TrayIcon

    total_steps = 5

    def step(index: int, label: str) -> None:
        reporter.set_status(f"{label}…")
        # Onbepaalde ("bezig") animatie: een blokkerende import kan de balk niet
        # tussentijds laten oplopen, dus houdt de glijdende animatie de indruk van
        # voortgang vast. Het detail toont wél de stap-teller.
        reporter.set_progress(None, i18n.t("splash.part", index=index, total=total_steps))

    step(1, i18n.t("splash.dep.whisper"))
    from faster_whisper import WhisperModel as _WhisperModel

    WhisperModel = _WhisperModel

    step(2, i18n.t("splash.dep.audio"))
    import numpy as _np
    from scipy.io.wavfile import write as _write_wav

    np = _np
    write_wav = _write_wav

    step(3, i18n.t("splash.dep.mic"))
    import sounddevice as _sd

    sd = _sd

    step(4, i18n.t("splash.dep.keyboard"))
    import pyperclip as _pyperclip
    from pynput import keyboard as _keyboard

    keyboard = _keyboard
    pyperclip = _pyperclip

    # De sneltoets-tokenisatie in hotkeys.py koppelen aan pynput.
    hotkeys.init(keyboard)

    step(5, i18n.t("splash.dep.tray"))
    from tray import TrayIcon as _TrayIcon

    TrayIcon = _TrayIcon

    session.bind_audio(numpy_mod=np, sounddevice_mod=sd, write_wav=write_wav)


def _startup(reporter: Splash) -> WhisperModel:
    """
    De volledige opstarttaak op de achtergrond-thread van het laadscherm: eerst de
    zware libraries importeren (zichtbaar per stap), dan het model laden/downloaden.
    """

    _load_dependencies(reporter)
    return load_model(reporter)


def _format_mb(num_bytes: float) -> str:
    """Bytes als megabytes met een Nederlandse komma, bijv. '28,4'."""

    return f"{num_bytes / (1024 * 1024):.1f}".replace(".", ",")


class _DownloadTracker:
    """
    Verzamelt de downloadvoortgang over alle bestanden heen en meldt het
    totale percentage aan het laadscherm.

    huggingface_hub maakt per bestand een eigen tqdm-balk aan. We tellen de
    bytes op over alle byte-balken (unit == "B") en negeren niet-byte-balken
    (zoals de 'Fetching N files'-teller).
    """

    def __init__(self, reporter: Splash) -> None:
        self._reporter = reporter
        self._lock = threading.Lock()
        self._bars: dict[int, tuple[float, float]] = {}

    def update(self, bar_id: int, done: float, total: float) -> None:
        with self._lock:
            self._bars[bar_id] = (done, total)
            total_done = sum(d for d, _ in self._bars.values())
            total_all = sum(t for _, t in self._bars.values() if t)

        if total_all > 0:
            self._reporter.set_progress(
                total_done / total_all,
                f"{_format_mb(total_done)} / {_format_mb(total_all)} MB",
            )


def _download_model_with_progress(model_name: str, reporter: Splash) -> str:
    """
    Downloadt het model via huggingface_hub met een eigen tqdm-klasse die de
    voortgang doorgeeft aan het laadscherm. Retourneert het lokale pad.

    faster_whisper.download_model zet tqdm hard uit, dus we roepen
    snapshot_download zelf aan om wél voortgang te krijgen.
    """

    import huggingface_hub
    from tqdm.auto import tqdm

    # Publieke fallback: private `_MODELS` kan in nieuwere faster-whisper
    # verdwijnen. De repo-id's volgen de Systran faster-whisper-conventie.
    _KNOWN_REPO_IDS = {
        "tiny": "Systran/faster-whisper-tiny",
        "tiny.en": "Systran/faster-whisper-tiny.en",
        "base": "Systran/faster-whisper-base",
        "base.en": "Systran/faster-whisper-base.en",
        "small": "Systran/faster-whisper-small",
        "small.en": "Systran/faster-whisper-small.en",
        "medium": "Systran/faster-whisper-medium",
        "medium.en": "Systran/faster-whisper-medium.en",
        "large-v1": "Systran/faster-whisper-large-v1",
        "large-v2": "Systran/faster-whisper-large-v2",
        "large-v3": "Systran/faster-whisper-large-v3",
        "large": "Systran/faster-whisper-large-v3",
        "distil-large-v2": "Systran/faster-distil-whisper-large-v2",
        "distil-medium.en": "Systran/faster-distil-whisper-medium.en",
        "distil-small.en": "Systran/faster-distil-whisper-small.en",
        "distil-large-v3": "Systran/faster-distil-whisper-large-v3",
    }
    try:
        from faster_whisper.utils import _MODELS as _fw_models
    except ImportError:
        _fw_models = {}
    repo_id = _fw_models.get(model_name) or _KNOWN_REPO_IDS.get(model_name, model_name)

    # Dezelfde bestandenselectie als faster_whisper.download_model.
    allow_patterns = [
        "config.json",
        "preprocessor_config.json",
        "model.bin",
        "tokenizer.json",
        "vocabulary.*",
    ]

    tracker = _DownloadTracker(reporter)

    class _NullSink:
        """Slokt tqdm-uitvoer op: onder pythonw is sys.stderr None."""

        def write(self, *_args: Any) -> None:
            pass

        def flush(self) -> None:
            pass

    class _ProgressTqdm(tqdm):
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            # Alleen de byte-balken meetellen (de 'Fetching N files'-teller
            # niet). `unit` uit de kwargs lezen: self.unit bestaat niet
            # betrouwbaar. tqdm naar een sink sturen en niet uitzetten, zodat
            # n/total blijven bijwerken zonder ooit naar (afwezige) stderr te
            # schrijven.
            self._track = kwargs.get("unit") == "B"
            kwargs["file"] = _NullSink()
            kwargs["disable"] = False
            super().__init__(*args, **kwargs)

        def update(self, n: float | None = 1) -> bool | None:
            displayed = super().update(n)
            if self._track:
                tracker.update(id(self), self.n, self.total or 0)
            return displayed

    return huggingface_hub.snapshot_download(
        repo_id,
        allow_patterns=allow_patterns,
        tqdm_class=_ProgressTqdm,
    )


def load_model(reporter: Splash) -> WhisperModel:
    """
    Laadt het Whisper-model. Draait op de achtergrond-thread van het laadscherm
    en meldt zijn voortgang via `reporter`.

    Is het model nog niet in de cache aanwezig, dan wordt het eerst (eenmalig)
    gedownload met een echte voortgangsbalk; daarna volgt het laden vanaf schijf.
    """

    from faster_whisper.utils import download_model

    # Cache-check: al aanwezig? Dan geen download nodig.
    try:
        model_path = download_model(MODEL_NAME, local_files_only=True)
        need_download = False
    except Exception:
        model_path = None
        need_download = True

    if need_download:
        reporter.set_status(i18n.t("splash.download"))
        reporter.set_progress(0.0, "")
        model_path = _download_model_with_progress(MODEL_NAME, reporter)

    # Laden vanaf schijf: geen betrouwbaar percentage, dus onbepaald ("bezig").
    reporter.set_status(i18n.t("splash.loading"))
    reporter.set_progress(None)

    return WhisperModel(
        model_path,
        device=DEVICE,
        compute_type=COMPUTE_TYPE,
    )


# =========================================================
# HULPFUNCTIES VOOR TOETSEN
# =========================================================


def hotkey_is_pressed() -> bool:
    """Controleert of de volledige ingestelde sneltoets is ingedrukt."""

    with state_lock:
        return bool(HOTKEY_TOKENS) and HOTKEY_TOKENS.issubset(pressed_tokens)


def wait_until_modifier_keys_released(
    timeout: float = 3.0,
) -> None:
    """
    Wacht totdat de sneltoets én de modificatietoetsen zijn losgelaten.

    Dit voorkomt dat automatisch plakken per ongeluk als bijvoorbeeld
    Ctrl+Shift+V wordt uitgevoerd in plaats van Ctrl+V.
    """

    relevant = {"ctrl", "shift", "alt", "cmd"} | HOTKEY_TOKENS
    started = time.monotonic()

    while True:
        with state_lock:
            still_pressed = bool(pressed_tokens.intersection(relevant))

        if not still_pressed:
            return

        if time.monotonic() - started >= timeout:
            return

        time.sleep(0.05)


def print_ready_message() -> None:
    """Toont dat het programma weer beschikbaar is."""

    print()
    print(i18n.t("ready", hotkey=hotkeys.format_hotkey(HOTKEY_TOKENS)))


def _copy_to_clipboard(text: str) -> None:
    """Kopieert tekst via het lazy geladen pyperclip."""

    if pyperclip is None:
        raise RuntimeError("pyperclip is nog niet geladen.")
    pyperclip.copy(text)


def _user_config_dict() -> dict[str, Any]:
    """Snapshot van alle persistente gebruikersinstellingen."""

    return {
        "model": MODEL_NAME,
        "microphone_device": MICROPHONE_DEVICE,
        "auto_paste": AUTO_PASTE,
        "warm_microphone": WARM_MICROPHONE,
        "indicator_position": INDICATOR_POSITION,
        "indicator_xy": list(INDICATOR_XY) if INDICATOR_XY is not None else None,
        "mode": MODE,
        "hotkey": hotkeys.normalize(HOTKEY_TOKENS),
        "speech_language": LANGUAGE,
        "ui_language": i18n.ui_language(),
        "destinations": DESTINATIONS,
        "active_destination": ACTIVE_DESTINATION,
        "incremental_transcription": INCREMENTAL_TRANSCRIPTION,
        "modules": modules_config_for_settings(MODULES_CONFIG),
    }


def _save_transcript_routed(text: str) -> Path:
    """Slaat transcript op in de actieve bestemmingsmap of de defaultmap."""

    destination = destinations.find_destination(ACTIVE_DESTINATION, DESTINATIONS)
    append_path = destinations.resolve_append_file(destination)
    if append_path is not None:
        return recovery.append_transcript(text, append_path)

    directory = destinations.resolve_save_dir(
        ACTIVE_DESTINATION,
        DESTINATIONS,
        recovery.transcripts_dir(),
    )
    return recovery.save_transcript(text, directory=directory)


def retranscribe_recovery_wav(path: Path) -> str:
    """
    Transcribeert een recovery-WAV met het geladen model.

    Blokkerend — aanroepen vanaf een achtergrondthread. Geeft het transcript
    terug; gooit bij weigering (bezig) of lege/geen herkenning.
    Bestemmings-stemcommando's worden bewust overgeslagen (herstel-inhoud).
    """

    if session.is_recording or session.is_processing:
        raise RuntimeError(i18n.t("recovery.busy"))
    if not shared_whisper.is_ready:
        raise RuntimeError(i18n.t("model.load_failed"))

    resolved = path.resolve()
    if resolved.parent != recovery.recovery_dir().resolve():
        raise ValueError(i18n.t("recovery.invalid_file"))

    session_id = str(uuid.uuid4())
    module_bus.emit(
        CycleEvent(
            type=CycleEventType.CYCLE_TRANSCRIBING,
            session_id=session_id,
            language=LANGUAGE,
            mode=MODE,
            recovery_path=str(resolved),
            source="recovery",
        )
    )

    with shared_whisper.locked_model() as whisper_model:
        segments, _info = whisper_model.transcribe(
            str(resolved),
            language=LANGUAGE,
            beam_size=5,
            vad_filter=True,
            vad_parameters={"min_silence_duration_ms": 300},
            condition_on_previous_text=False,
        )
        text_parts: list[str] = []
        for segment in segments:
            text = segment.text.strip()
            if text:
                text_parts.append(text)
    transcript = " ".join(text_parts).strip()
    if not transcript:
        module_bus.emit(
            CycleEvent(
                type=CycleEventType.CYCLE_IDLE,
                session_id=session_id,
                source="recovery",
            )
        )
        raise RuntimeError(i18n.t("rec.no_speech"))

    module_bus.emit(
        CycleEvent(
            type=CycleEventType.CYCLE_COMPLETED,
            session_id=session_id,
            transcript=transcript,
            destination=ACTIVE_DESTINATION,
            language=LANGUAGE,
            mode=MODE,
            recovery_path=str(resolved),
            source="recovery",
        )
    )

    saved_path: Path | None = None
    try:
        saved_path = _save_transcript_routed(transcript)
    except OSError as exc:
        print(i18n.t("rec.save_warn", error=exc))

    if saved_path is not None:
        module_bus.emit(
            CycleEvent(
                type=CycleEventType.TRANSCRIPT_SAVED,
                session_id=session_id,
                transcript=transcript,
                path=str(saved_path),
                destination=ACTIVE_DESTINATION,
                language=LANGUAGE,
                mode=MODE,
                recovery_path=str(resolved),
                source="recovery",
            )
        )

    module_bus.emit(
        CycleEvent(
            type=CycleEventType.RECOVERY_RETRANSCRIBED,
            session_id=session_id,
            transcript=transcript,
            path=str(saved_path) if saved_path is not None else None,
            recovery_path=str(resolved),
            source="recovery",
        )
    )

    try:
        _copy_to_clipboard(transcript)
    except Exception as exc:
        print(i18n.t("rec.clipboard_warn", error=exc))

    if AUTO_PASTE:
        wait_until_modifier_keys_released()
        time.sleep(PASTE_DELAY_SECONDS)
        try:
            host.paste()
        except Exception as exc:
            print(i18n.t("rec.paste_failed"))
            print(i18n.t("rec.error", error=exc))

    module_bus.emit(
        CycleEvent(
            type=CycleEventType.CYCLE_IDLE,
            session_id=session_id,
            source="recovery",
        )
    )

    return transcript


def _start_recovery_retranscribe(path: Path, indicator: RecordingIndicator) -> None:
    """Start herstel-transcriptie op een achtergrondthread (macOS-parent-pad)."""

    from tkinter import messagebox

    def worker() -> None:
        error: str | None = None
        try:
            retranscribe_recovery_wav(path)
        except Exception as exc:
            error = str(exc)

        def done() -> None:
            if error is not None:
                messagebox.showerror(
                    i18n.t("settings.title"),
                    error,
                    parent=indicator.root,
                )
                return
            if not path.exists():
                return
            if messagebox.askyesno(
                i18n.t("settings.title"),
                i18n.t("recovery.ask_delete_after", name=path.name),
                parent=indicator.root,
            ):
                try:
                    recovery.delete_recovery_file(path)
                except (OSError, ValueError) as exc:
                    messagebox.showerror(
                        i18n.t("settings.title"),
                        str(exc),
                        parent=indicator.root,
                    )

        indicator.call_on_main(done)

    threading.Thread(target=worker, daemon=True).start()


def _handle_destination_command(kind: str, name: str | None) -> None:
    """Werkt sticky bestemming bij na een stem-commando."""

    global ACTIVE_DESTINATION

    if kind == "set":
        ACTIVE_DESTINATION = name
    elif kind == "reset":
        ACTIVE_DESTINATION = None

    config.save_config(_user_config_dict())

    indicator = _indicator
    if indicator is not None:
        active = ACTIVE_DESTINATION
        indicator.call_on_main(lambda: indicator.set_destination(active))


def _set_mic_attention(needed: bool) -> None:
    """Markeert het tray-icoon als er microfoonactie nodig is."""

    tray = _tray
    if tray is None:
        return
    tray.set_attention_needed(needed)


def _refresh_mic_attention() -> None:
    _set_mic_attention(not session.probe_microphone())


def _report_user_error(message: str) -> None:
    """Toont een gebruikersfout in een dialoog zodra de indicator-GUI bestaat."""

    _set_mic_attention(True)

    indicator = _indicator
    if indicator is None:
        # Te vroeg in de start (vóór pill/tray): alleen loggen, niet blokkeren.
        return

    def show() -> None:
        from tkinter import messagebox

        parent = getattr(indicator, "root", None)
        try:
            messagebox.showerror(
                i18n.t("rec.start_failed_title"),
                message,
                parent=parent,
            )
        except Exception:
            pass

    indicator.call_on_main(show)


def _build_session() -> Opnamesessie:
    """Bouwt de Opnamesessie met de huidige config en geïnjecteerde seams."""

    return Opnamesessie(
        host=host.default,
        sample_rate=SAMPLE_RATE,
        channels=CHANNELS,
        microphone_device=MICROPHONE_DEVICE,
        minimum_recording_seconds=MINIMUM_RECORDING_SECONDS,
        auto_paste=AUTO_PASTE,
        paste_delay_seconds=PASTE_DELAY_SECONDS,
        language=LANGUAGE,
        delete_temp_audio=DELETE_TEMP_AUDIO,
        mode=MODE,
        warm_microphone=WARM_MICROPHONE,
        incremental_transcription=INCREMENTAL_TRANSCRIPTION,
        emit_event=_emit_cycle_event,
        wait_until_modifiers_clear=wait_until_modifier_keys_released,
        on_ready=print_ready_message,
        copy_text=_copy_to_clipboard,
        save_transcript=_save_transcript_routed,
        preserve_audio=recovery.preserve_audio,
        on_destination_command=_handle_destination_command,
        get_destinations=lambda: DESTINATIONS,
        get_active_destination=lambda: ACTIVE_DESTINATION,
        on_user_error=_report_user_error,
        on_mic_ready=lambda: _set_mic_attention(False),
        shared_whisper=shared_whisper,
    )


# Sessiewording bij import (na config); audio-libs en model komen later.
session = _build_session()


# =========================================================
# TOETSENBORDLISTENER
# =========================================================


def set_capture(callback: Any | None) -> None:
    """
    Zet het opnemen van een nieuwe sneltoets aan (callback) of uit (None).

    Aangeroepen vanuit het instellingen-dialoog. Terwijl dit actief is, stuurt de
    listener elke toets naar `callback(event, key)` en voert hij geen dicteeractie
    uit. De ingedrukt-status wordt geleegd zodat er geen resten achterblijven.
    """

    global _capture_cb, capturing, toggle_latched

    with state_lock:
        _capture_cb = callback
        capturing = callback is not None
        pressed_tokens.clear()
        toggle_latched = False


def on_press(
    key: keyboard.Key | keyboard.KeyCode | None,
) -> None:
    """
    Verwerkt het indrukken van toetsen.

    De ingestelde sneltoets:
        - toggle: opname aan of uit
        - push-to-talk: opname start (loslaten stopt, zie on_release)
    """

    global toggle_latched

    # Sneltoets opnemen (instellingen): doorsturen, verder niets doen.
    capture_cb = _capture_cb
    if capture_cb is not None:
        capture_cb("press", key)
        return

    token = hotkeys.key_to_token(key)

    if token is not None:
        with state_lock:
            pressed_tokens.add(token)

    if not hotkey_is_pressed():
        return

    with state_lock:
        if toggle_latched:
            return

        toggle_latched = True
        is_recording = session.is_recording
        is_processing = session.is_processing

    if MODE == "ptt":
        # Push-to-talk: ingedrukt houden neemt op; loslaten stopt (on_release).
        if is_processing:
            print("\n" + i18n.t("dictation.busy"))
        elif not is_recording:
            print("\n" + i18n.t("dictation.ptt_started"))
            session.start()

    else:
        # Toggle: dezelfde sneltoets wisselt tussen starten en stoppen.
        if is_recording:
            print("\n" + i18n.t("dictation.stopped_hotkey"))
            session.stop_and_transcribe()
        elif is_processing:
            print("\n" + i18n.t("dictation.busy"))
        else:
            print("\n" + i18n.t("dictation.started_hotkey"))
            session.start()


def on_release(
    key: keyboard.Key | keyboard.KeyCode | None,
) -> None:
    """
    Verwerkt het loslaten van toetsen.

    In push-to-talk stopt het loslaten van de sneltoets de opname. In toggle-modus
    zorgt het loslaten ervoor dat dezelfde combinatie opnieuw kan afgaan.
    """

    global toggle_latched

    capture_cb = _capture_cb
    if capture_cb is not None:
        capture_cb("release", key)
        return

    token = hotkeys.key_to_token(key)

    if token is not None:
        with state_lock:
            pressed_tokens.discard(token)

    if not hotkey_is_pressed():
        with state_lock:
            was_latched = toggle_latched
            toggle_latched = False

        # Push-to-talk: zodra de sneltoets wordt losgelaten, stoppen.
        if MODE == "ptt" and was_latched:
            if session.is_recording:
                print("\n" + i18n.t("dictation.ptt_stopped"))
                session.stop_and_transcribe()


# =========================================================
# INSTELLINGEN TOEPASSEN (systeemvak → Instellingen)
# =========================================================


def current_settings() -> dict[str, Any]:
    """De huidige waarden, voor het vullen van het instellingen-dialoog."""

    return {
        "model": MODEL_NAME,
        "microphone_device": MICROPHONE_DEVICE,
        "auto_paste": AUTO_PASTE,
        "warm_microphone": WARM_MICROPHONE,
        "indicator_position": INDICATOR_POSITION,
        "indicator_xy": list(INDICATOR_XY) if INDICATOR_XY is not None else None,
        "mode": MODE,
        "hotkey": hotkeys.normalize(HOTKEY_TOKENS),
        "speech_language": LANGUAGE,
        "ui_language": i18n.ui_language(),
        "autostart": host.is_autostart_enabled(),
        "destinations": list(DESTINATIONS),
        "active_destination": ACTIVE_DESTINATION,
        "incremental_transcription": INCREMENTAL_TRANSCRIPTION,
        "modules": modules_config_for_settings(MODULES_CONFIG),
    }


def apply_settings(
    new_settings: dict[str, Any],
    indicator: RecordingIndicator,
) -> None:
    """
    Bewaart en past gewijzigde instellingen toe. Draait op de hoofdthread
    (het dialoog is daarheen gemarshald), dus GUI-calls zijn hier veilig.

    Live: pill-positie, auto-plakken, warm-mic, modus, sneltoets, talen,
    automatisch meestarten. Volgende opname: microfoon. Na herstart: model.
    """

    global MODEL_NAME, MICROPHONE_DEVICE, AUTO_PASTE, INDICATOR_POSITION, INDICATOR_XY
    global MODE, HOTKEY_TOKENS, LANGUAGE, WARM_MICROPHONE
    global DESTINATIONS, ACTIVE_DESTINATION, MODULES_CONFIG, INCREMENTAL_TRANSCRIPTION

    from indicator._contract import (
        POSITION_LAST,
        normalize_indicator_position,
        sanitize_indicator_xy,
    )

    new_model = str(new_settings.get("model", MODEL_NAME))
    model_changed = new_model != MODEL_NAME
    new_position = normalize_indicator_position(
        new_settings.get("indicator_position", INDICATOR_POSITION)
    )
    new_xy = sanitize_indicator_xy(new_settings.get("indicator_xy", INDICATOR_XY))
    if new_position == POSITION_LAST and new_xy is None:
        new_xy = INDICATOR_XY
    if new_position == POSITION_LAST and new_xy is None:
        new_position = "boven-midden"
    position_changed = new_position != INDICATOR_POSITION or new_xy != INDICATOR_XY

    MODEL_NAME = new_model
    MICROPHONE_DEVICE = new_settings.get("microphone_device", MICROPHONE_DEVICE)
    AUTO_PASTE = bool(new_settings.get("auto_paste", AUTO_PASTE))
    WARM_MICROPHONE = bool(new_settings.get("warm_microphone", WARM_MICROPHONE))
    INDICATOR_POSITION = new_position
    INDICATOR_XY = new_xy

    if new_settings.get("mode") in ("toggle", "ptt"):
        MODE = str(new_settings["mode"])

    new_hotkey = new_settings.get("hotkey")
    if isinstance(new_hotkey, list) and new_hotkey:
        HOTKEY_TOKENS = {str(token) for token in new_hotkey}

    LANGUAGE = i18n.normalize_language(
        new_settings.get("speech_language", LANGUAGE),
        allowed=i18n.SUPPORTED_SPEECH_LANGUAGES,
    )
    i18n.set_ui_language(
        i18n.normalize_language(
            new_settings.get("ui_language"),
            allowed=i18n.SUPPORTED_UI_LANGUAGES,
        )
    )

    if "destinations" in new_settings:
        DESTINATIONS = destinations.sanitize_destinations(new_settings["destinations"])
        if "active_destination" not in new_settings and ACTIVE_DESTINATION is not None:
            if not any(d["name"] == ACTIVE_DESTINATION for d in DESTINATIONS):
                ACTIVE_DESTINATION = None
    if "active_destination" in new_settings:
        raw_active = new_settings["active_destination"]
        if raw_active is None:
            ACTIVE_DESTINATION = None
        else:
            candidate = str(raw_active).strip() or None
            if candidate and any(d["name"] == candidate for d in DESTINATIONS):
                ACTIVE_DESTINATION = candidate
            else:
                ACTIVE_DESTINATION = None

    if "incremental_transcription" in new_settings:
        INCREMENTAL_TRANSCRIPTION = bool(new_settings["incremental_transcription"])
    if "modules" in new_settings:
        MODULES_CONFIG = sanitize_modules_config(new_settings["modules"])
        _reload_modules()

    # Houd de Opnamesessie synchroon met live-instellingen.
    old_mic = session.microphone_device
    old_warm = session.warm_microphone
    session.microphone_device = MICROPHONE_DEVICE
    session.auto_paste = AUTO_PASTE
    session.mode = MODE
    session.language = LANGUAGE
    session.warm_microphone = WARM_MICROPHONE
    session.incremental_transcription = INCREMENTAL_TRANSCRIPTION
    if old_mic != MICROPHONE_DEVICE:
        session.refresh_input_device()
    elif old_warm and not WARM_MICROPHONE:
        session.stop_audio_stream()
    elif (not old_warm) and WARM_MICROPHONE:
        session.warmup_microphone()

    _refresh_mic_attention()

    config.save_config(_user_config_dict())

    # Automatisch meestarten staat buiten config.json (register op Windows,
    # LaunchAgent op macOS) — geregeld via de platform-seam.
    if "autostart" in new_settings:
        host.set_autostart(bool(new_settings["autostart"]))

    # Live toepassen waar mogelijk.
    if position_changed:
        indicator.set_position(new_position, xy=INDICATOR_XY)

    indicator.set_destination(ACTIVE_DESTINATION)

    if _tray is not None:
        _tray.refresh_language()

    print()
    print(i18n.t("settings.saved"))
    if model_changed:
        print(i18n.t("settings.model_restart_note"))


def main() -> None:
    """
    Start de indicator, het systeemvak-/menubalk-icoon en de globale
    toetsenbordlistener.

    Threading per OS:
    - Windows: tkinter-mainloop op de hoofdthread; pystray detached; pynput
      op een eigen thread.
    - macOS: Cocoa-runloop op de hoofdthread via pystray (`TrayIcon.run`);
      de native NSPanel-indicator plant een NSTimer op dezelfde runloop.
    """

    global model, _tray, _indicator

    # Vóór splash/tray: Windows-app-id (taakbalk-groep / identiteit).
    win_identity.apply_windows_app_identity()

    # Bestandslog: onder pythonw / windowed exe is er geen console.
    log_file = app_logging.setup_logging()
    config.ensure_app_data_dirs()
    print(i18n.t("log.path", path=log_file))

    # Slechts één instantie tegelijk. Een tweede start (bijv. autostart én een
    # handmatige start, of twee keer klikken) stopt hier — vóór het laadscherm en
    # het model — zodat er nooit twee listeners, tray-iconen of indicators komen.
    if not host.acquire_single_instance():
        # MacHost print al een PID-hint; elders deze regel.
        if sys.platform != "darwin":
            print(i18n.t("already_running"))
        raise SystemExit(0)

    # Eerst het laadscherm: het model wordt op een achtergrond-thread geladen
    # (en zo nodig gedownload) terwijl de splash de voortgang toont. De splash
    # draait zijn eigen mainloop op de hoofdthread en wordt volledig afgebroken
    # voordat de indicator zijn venster opbouwt.
    try:
        model = Splash().run(_startup)
    except Exception as exc:
        # De fout is al in het laadscherm getoond; hier alleen netjes stoppen.
        print(i18n.t("model.load_failed"))
        print(i18n.t("model.error", error=exc))
        raise SystemExit(1) from exc

    session.model = model

    print(i18n.t("model.loaded"))
    # Optioneel: microfoon al openen (anders 0,5–2 s bij eerste/Bluetooth-opname).
    # Op macOS no-op: warme stream zou de systeembrede mic-indicator permanent tonen.
    if WARM_MICROPHONE:
        session.warmup_microphone()
    print(
        i18n.t(
            "controls",
            mode=MODE,
            hotkey=hotkeys.format_hotkey(HOTKEY_TOKENS),
        )
    )

    # Harde afhankelijkheid: kan de indicator niet initialiseren, dan stopt de
    # app (RecordingIndicator gooit SystemExit — net als een mislukte model-load).
    def _on_indicator_moved(position: str, x: int, y: int) -> None:
        global INDICATOR_POSITION, INDICATOR_XY
        INDICATOR_POSITION = position
        INDICATOR_XY = (x, y)
        config.save_config(_user_config_dict())

    def pill_control_press() -> None:
        """Start of stop via de pill-knop (zelfde regels als de sneltoets)."""

        if session.is_recording:
            print("\n" + i18n.t("dictation.stopped_hotkey"))
            session.stop_and_transcribe()
            return
        if session.is_processing:
            print("\n" + i18n.t("dictation.busy"))
            return
        if MODE == "ptt":
            print("\n" + i18n.t("dictation.ptt_started"))
        else:
            print("\n" + i18n.t("dictation.started_hotkey"))
        session.start()

    def pill_control_release() -> None:
        """Push-to-talk: loslaten van de pill-knop stopt de opname."""

        if MODE != "ptt":
            return
        if session.is_recording:
            print("\n" + i18n.t("dictation.ptt_stopped"))
            session.stop_and_transcribe()

    indicator = RecordingIndicator(
        position=INDICATOR_POSITION,
        xy=INDICATOR_XY,
        on_moved=_on_indicator_moved,
        on_control_press=pill_control_press,
        on_control_release=pill_control_release,
    )
    _indicator = indicator
    indicator.set_destination(ACTIVE_DESTINATION)

    global _ui_dispatch
    _ui_dispatch = indicator.call_on_main
    _reload_modules()

    def run_module_action(module_id: str, action_id: str) -> None:
        indicator.call_on_main(lambda: module_bus.run_action(module_id, action_id))

    # Systeemvak-/menubalk. "Afsluiten" en Ctrl+C funnelen naar request_stop +
    # tray.stop; "Instellingen" wordt naar de hoofdthread gemarshald.
    def open_settings() -> None:
        # Lazy import: settings.py trekt zelf sounddevice binnen; die is op dit
        # punt (na de splash) allang geladen, dus deze import is direct.
        if sys.platform == "darwin":
            # Apart Tk-proces: een Toplevel in pystray's NSApp-runloop crasht
            # bij sluiten (PyEval_RestoreThread → SIGABRT op macOS 26+).
            from settings_process import run_settings_subprocess

            def _mac_settings() -> None:
                # Onderdruk dicteer-hotkeys terwijl Instellingen open is.
                set_capture(lambda *_: None)
                try:
                    new = run_settings_subprocess(current_settings())
                finally:
                    set_capture(None)
                if new is None:
                    return
                path_str = new.get("_recovery_retranscribe")
                if path_str:
                    indicator.call_on_main(
                        lambda: _start_recovery_retranscribe(Path(str(path_str)), indicator)
                    )
                    return
                indicator.call_on_main(lambda: apply_settings(new, indicator))

            threading.Thread(target=_mac_settings, daemon=True).start()
            return

        from settings import open_settings_dialog

        indicator.call_on_main(
            lambda: open_settings_dialog(
                indicator.root,
                current_settings(),
                lambda new: apply_settings(new, indicator),
                set_capture,
                on_retranscribe=retranscribe_recovery_wav,
            )
        )

    def open_destinations() -> None:
        if sys.platform == "darwin":
            from settings_process import run_destinations_subprocess

            def _mac_destinations() -> None:
                set_capture(lambda *_: None)
                try:
                    new = run_destinations_subprocess(current_settings())
                finally:
                    set_capture(None)
                if new is not None:
                    indicator.call_on_main(lambda: apply_settings(new, indicator))

            threading.Thread(target=_mac_destinations, daemon=True).start()
            return

        from destinations_dialog import open_destinations_dialog

        indicator.call_on_main(
            lambda: open_destinations_dialog(
                indicator.root,
                current_settings(),
                lambda new: apply_settings(new, indicator),
            )
        )

    def open_modules() -> None:
        if sys.platform == "darwin":
            from settings_process import run_modules_subprocess

            def _mac_modules() -> None:
                set_capture(lambda *_: None)
                try:
                    new = run_modules_subprocess(current_settings())
                finally:
                    set_capture(None)
                if new is not None:
                    indicator.call_on_main(lambda: apply_settings(new, indicator))

            threading.Thread(target=_mac_modules, daemon=True).start()
            return

        from modules_dialog import open_modules_dialog

        indicator.call_on_main(
            lambda: open_modules_dialog(
                indicator.root,
                current_settings(),
                lambda new: apply_settings(new, indicator),
                on_module_action=run_module_action,
                enabled_module_ids={module.id for module in module_bus.modules},
            )
        )

    def open_help() -> None:
        if sys.platform == "darwin":
            from settings_process import run_help_subprocess

            def _mac_help() -> None:
                set_capture(lambda *_: None)
                try:
                    run_help_subprocess(current_settings())
                finally:
                    set_capture(None)

            threading.Thread(target=_mac_help, daemon=True).start()
            return

        from help_dialog import open_help as show_help

        indicator.call_on_main(lambda: show_help(indicator.root))

    def request_shutdown() -> None:
        indicator.request_stop()
        tray.stop()

    tray = TrayIcon(
        on_quit=request_shutdown,
        on_settings=open_settings,
        on_destinations=open_destinations,
        on_modules=open_modules,
        on_help=open_help,
        on_module_action=run_module_action,
        get_module_tray_actions=lambda: tray_action_entries(list(module_bus.modules)),
        get_module_tray_root_actions=lambda: tray_root_action_entries(list(module_bus.modules)),
    )
    _tray = tray

    # De pill is de enige toestandseigenaar; die stuurt het tray-icoon aan.
    indicator.state_listener = tray.set_state

    def show_pill_context_menu(x: int, y: int) -> None:
        parent = getattr(indicator, "root", None)
        tray.popup_menu(x, y, tk_parent=parent)

    indicator.on_context_menu = show_pill_context_menu
    tray.start()
    _refresh_mic_attention()

    # macOS 26+: géén pynput.Listener (TSM-crash op achtergrondthread).
    # NSEvent-monitor op de Cocoa-mainloop i.p.v. pynput.
    if tray.owns_main_thread:
        from mac_input import QuartzKeyListener

        listener = QuartzKeyListener(on_press=on_press, on_release=on_release)
    else:
        listener = keyboard.Listener(
            on_press=on_press,
            on_release=on_release,
        )
    listener.start()

    # Ctrl+C in de console laat de mainloop netjes eindigen.
    signal.signal(signal.SIGINT, lambda *_: request_shutdown())

    try:
        if tray.owns_main_thread:
            # macOS: NSTimer + NSEvent-monitor op de Cocoa-runloop; pystray
            # blokkeert met NSApp (menubalk-icoon rechtsboven).
            indicator.prepare_external_runloop()
            tray.run()
        else:
            indicator.run()

    except KeyboardInterrupt:
        pass

    finally:
        print()
        print(i18n.t("shutdown"))

        listener.stop()
        tray.stop()

        with state_lock:
            active_recording = session.is_recording

        if active_recording:
            session.cancel()

        session.stop_audio_stream()
        module_bus.shutdown()
        indicator.destroy()


if __name__ == "__main__":
    # Frozen macOS: dialogen als apart proces (zelfde binary).
    for _flag in (
        "--praatmaar-settings-ui",
        "--praatmaar-destinations-ui",
        "--praatmaar-modules-ui",
        "--praatmaar-help-ui",
    ):
        if _flag in sys.argv:
            from settings_process import main as settings_ui_main

            raise SystemExit(settings_ui_main(sys.argv[1:]))
    main()
