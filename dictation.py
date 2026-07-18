from __future__ import annotations

import os
import signal
import sys
import tempfile
import threading
import time
from pathlib import Path
from typing import Any

from indicator import (
    RecordingIndicator,
    RecordingState,
    notify_state,
    push_level,
    reset_levels,
)

import config
import hotkeys
import host
import recovery
from splash import Splash

# De zware libraries worden bewust NIET bij import geladen, maar pas in
# _load_dependencies() op de achtergrond-thread van het laadscherm. Zo verschijnt
# de splash direct (de module blijft licht) en zie je de onderdelen laden.
# Ze worden daar aan deze globals toegewezen zodat de rest van de code ze
# ongewijzigd als `np`, `sd`, ... kan blijven gebruiken. `settings` en `tray`
# worden lazy geïmporteerd (settings trekt zelf sounddevice binnen).
np = None            # numpy
sd = None            # sounddevice
pyperclip = None
keyboard = None      # pynput.keyboard
write_wav = None     # scipy.io.wavfile.write
WhisperModel = None  # faster_whisper.WhisperModel
TrayIcon = None      # tray.TrayIcon

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

# Nederlands afdwingen.
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

# Korte wachttijd voordat Ctrl+V wordt uitgevoerd.
PASTE_DELAY_SECONDS = 0.30

# Minimale opnameduur.
# Zeer korte, per ongeluk gestarte opnames worden genegeerd.
MINIMUM_RECORDING_SECONDS = 0.30

# Tijdelijke audiobestanden na verwerking verwijderen.
DELETE_TEMP_AUDIO = True

# Positie van de opname-indicator: "boven-midden" (standaard) of "onder-midden".
INDICATOR_POSITION = "boven-midden"

# Bedieningsmodus:
# - "toggle" = indrukken start, nogmaals indrukken (of Esc) stopt en transcribeert
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
if "indicator_position" in _user_config:
    INDICATOR_POSITION = str(_user_config["indicator_position"])
if _user_config.get("mode") in ("toggle", "ptt"):
    MODE = str(_user_config["mode"])
if isinstance(_user_config.get("hotkey"), list) and _user_config["hotkey"]:
    HOTKEY_TOKENS = {str(token) for token in _user_config["hotkey"]}


# =========================================================
# GLOBALE STATUS
# =========================================================
#
# De tokenisatie van toetsen (Ctrl/Shift/Alt samenvouwen, letters via vk, enz.)
# staat in hotkeys.py, gedeeld met het instellingen-dialoog dat een nieuwe
# sneltoets opneemt.

state_lock = threading.RLock()

recording = False
processing = False
cancel_requested = False

recording_started_at: float | None = None

audio_stream: sd.InputStream | None = None
audio_chunks: list[np.ndarray] = []

# Houdt bij welke onderdelen van de combinatie zijn ingedrukt.
pressed_tokens: set[str] = set()

# Voorkomt herhaald afgaan door keyboard-repeat.
toggle_latched = False

# Terwijl het instellingen-dialoog een nieuwe sneltoets opneemt, stuurt de globale
# listener elke toets door naar deze callback en voert géén normale actie uit
# (zodat het opnemen de dicteeropname niet start).
capturing = False
_capture_cb: "Any | None" = None


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
        reporter.set_progress(None, f"onderdeel {index} van {total_steps}")

    step(1, "Spraakherkenning laden")
    from faster_whisper import WhisperModel as _WhisperModel
    WhisperModel = _WhisperModel

    step(2, "Audioverwerking laden")
    import numpy as _np
    from scipy.io.wavfile import write as _write_wav
    np = _np
    write_wav = _write_wav

    step(3, "Microfoon laden")
    import sounddevice as _sd
    sd = _sd

    step(4, "Toetsenbord en plakken laden")
    from pynput import keyboard as _keyboard
    import pyperclip as _pyperclip
    keyboard = _keyboard
    pyperclip = _pyperclip

    # De sneltoets-tokenisatie in hotkeys.py koppelen aan pynput.
    hotkeys.init(keyboard)

    step(5, "Systeemvak laden")
    from tray import TrayIcon as _TrayIcon
    TrayIcon = _TrayIcon


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


def _download_model_with_progress(
    model_name: str, reporter: Splash
) -> str:
    """
    Downloadt het model via huggingface_hub met een eigen tqdm-klasse die de
    voortgang doorgeeft aan het laadscherm. Retourneert het lokale pad.

    faster_whisper.download_model zet tqdm hard uit, dus we roepen
    snapshot_download zelf aan om wél voortgang te krijgen.
    """

    import huggingface_hub
    from tqdm.auto import tqdm

    from faster_whisper.utils import _MODELS

    repo_id = _MODELS.get(model_name, model_name)

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
        reporter.set_status("Model wordt gedownload (eenmalig)…")
        reporter.set_progress(0.0, "")
        model_path = _download_model_with_progress(MODEL_NAME, reporter)

    # Laden vanaf schijf: geen betrouwbaar percentage, dus onbepaald ("bezig").
    reporter.set_status("Model wordt geladen…")
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


def shift_is_pressed() -> bool:
    """Controleert of Shift momenteel is ingedrukt."""

    with state_lock:
        return "shift" in pressed_tokens


def wait_until_modifier_keys_released(
    timeout: float = 3.0,
) -> None:
    """
    Wacht totdat de sneltoets én de modificatietoetsen zijn losgelaten.

    Dit voorkomt dat automatisch plakken per ongeluk als bijvoorbeeld
    Ctrl+Shift+V wordt uitgevoerd in plaats van Ctrl+V.
    """

    relevant = {"ctrl", "shift", "alt"} | HOTKEY_TOKENS
    started = time.monotonic()

    while True:
        with state_lock:
            still_pressed = bool(pressed_tokens.intersection(relevant))

        if not still_pressed:
            return

        if time.monotonic() - started >= timeout:
            return

        time.sleep(0.05)


# =========================================================
# AUDIO
# =========================================================

def audio_callback(
    indata: np.ndarray,
    frames: int,
    time_info: Any,
    status: sd.CallbackFlags,
) -> None:
    """
    Ontvangt audioblokken van de microfoon.

    De callback moet zo weinig mogelijk werk uitvoeren,
    zodat de audio-opname niet wordt onderbroken.
    """

    if status:
        print(f"\nAudio-waarschuwing: {status}")

    with state_lock:
        is_recording = recording
        if is_recording:
            audio_chunks.append(indata.copy())

    # Buiten de lock: goedkoop niveau (RMS) voor de waveform in de indicator.
    # De audio-callback doet hier alleen rekenwerk + schrijven, geen I/O of Tk.
    if is_recording and frames > 0:
        push_level(float(np.sqrt(np.mean(np.square(indata)))))


def start_recording() -> None:
    """Start een nieuwe microfoonopname."""

    global recording
    global processing
    global cancel_requested
    global recording_started_at
    global audio_stream
    global audio_chunks

    with state_lock:
        if recording:
            return

        if processing:
            print("\nEr wordt nog een vorige opname verwerkt.")
            return

        audio_chunks = []
        cancel_requested = False
        recording_started_at = time.monotonic()

        try:
            stream = sd.InputStream(
                samplerate=SAMPLE_RATE,
                channels=CHANNELS,
                dtype="float32",
                callback=audio_callback,
                device=MICROPHONE_DEVICE,
            )

            audio_stream = stream
            recording = True
            stream.start()

        except Exception as exc:
            recording = False
            recording_started_at = None
            audio_stream = None

            print()
            print("De microfoonopname kon niet worden gestart.")
            print(f"Foutmelding: {exc}")
            print()
            print("Controleer:")
            print("- of Windows microfoontoegang toestaat;")
            print("- of de juiste standaardmicrofoon is geselecteerd;")
            print("- of MICROPHONE_DEVICE correct is ingesteld.")
            return

    reset_levels()
    notify_state(RecordingState.RECORDING, MODE)

    print()
    print("● OPNAME GESTART")
    print("  Spreek nu.")
    print(
        "  Stop met Ctrl + Shift + Alt + Spatie "
        "of met Esc."
    )


def stop_audio_stream() -> None:
    """Stopt en sluit de actieve microfoonstream."""

    global audio_stream

    stream: sd.InputStream | None

    with state_lock:
        stream = audio_stream
        audio_stream = None

    if stream is None:
        return

    try:
        stream.stop()
    except Exception as exc:
        print(f"Waarschuwing bij stoppen microfoon: {exc}")

    try:
        stream.close()
    except Exception as exc:
        print(f"Waarschuwing bij sluiten microfoon: {exc}")


def stop_recording_and_transcribe() -> None:
    """
    Stopt de opname en start de transcriptie in een aparte thread.
    """

    global recording
    global processing
    global recording_started_at

    with state_lock:
        if not recording:
            return

        recording = False

        started_at = recording_started_at
        recording_started_at = None

    stop_audio_stream()

    duration = 0.0

    if started_at is not None:
        duration = time.monotonic() - started_at

    print()
    print(f"■ OPNAME GESTOPT ({duration:.1f} seconden)")

    if duration < MINIMUM_RECORDING_SECONDS:
        with state_lock:
            audio_chunks.clear()

        notify_state(RecordingState.IDLE)
        print("De opname was te kort en wordt niet verwerkt.")
        print_ready_message()
        return

    with state_lock:
        if not audio_chunks:
            notify_state(RecordingState.IDLE)
            print("Er is geen audio opgenomen.")
            print_ready_message()
            return

        processing = True

        # Maak een kopie zodat een latere opname deze data
        # niet kan wijzigen.
        chunks_to_process = [
            chunk.copy()
            for chunk in audio_chunks
        ]

        audio_chunks.clear()

    notify_state(RecordingState.TRANSCRIBING, MODE)

    thread = threading.Thread(
        target=transcribe_audio,
        args=(chunks_to_process,),
        daemon=True,
    )
    thread.start()


def cancel_recording() -> None:
    """
    Annuleert de opname.

    Er wordt niets getranscribeerd en niets geplakt.
    """

    global recording
    global cancel_requested
    global recording_started_at

    with state_lock:
        if not recording:
            return

        cancel_requested = True
        recording = False
        recording_started_at = None
        audio_chunks.clear()

    stop_audio_stream()

    notify_state(RecordingState.CANCELLED)

    print()
    print("× OPNAME GEANNULEERD")
    print("Er wordt niets getranscribeerd of geplakt.")
    print_ready_message()


# =========================================================
# TRANSCRIPTIE
# =========================================================

def create_temporary_wav(
    chunks: list[np.ndarray],
) -> Path:
    """Maakt van de opgenomen audioblokken een tijdelijk WAV-bestand."""

    if not chunks:
        raise ValueError("Er zijn geen audioblokken ontvangen.")

    audio = np.concatenate(chunks, axis=0)

    # Maak een mono-array.
    audio = audio.reshape(-1)

    # sounddevice levert float32-waarden van ongeveer -1 tot 1.
    # WAV wordt hier opgeslagen als 16-bit PCM.
    audio_int16 = np.int16(
        np.clip(audio, -1.0, 1.0) * 32767
    )

    temporary_file = tempfile.NamedTemporaryFile(
        prefix="whisper_dictation_",
        suffix=".wav",
        delete=False,
    )
    temporary_file.close()

    temporary_path = Path(temporary_file.name)

    write_wav(
        temporary_path,
        SAMPLE_RATE,
        audio_int16,
    )

    return temporary_path


def transcribe_audio(
    chunks: list[np.ndarray],
) -> None:
    """Transcribeert de opgenomen audio lokaal met Faster-Whisper."""

    global processing

    temporary_path: Path | None = None
    final_state = RecordingState.IDLE

    try:
        print("Transcriptie wordt lokaal uitgevoerd...")

        temporary_path = create_temporary_wav(chunks)

        segments, info = model.transcribe(
            str(temporary_path),
            language=LANGUAGE,
            beam_size=5,
            vad_filter=True,
            vad_parameters={
                "min_silence_duration_ms": 300,
            },
            condition_on_previous_text=False,
        )

        # Faster-Whisper geeft segments als generator terug.
        # De transcriptie wordt daadwerkelijk uitgevoerd
        # wanneer we door de generator itereren.
        text_parts: list[str] = []

        for segment in segments:
            text = segment.text.strip()

            if text:
                text_parts.append(text)

        transcript = " ".join(text_parts).strip()

        if not transcript:
            print()
            print("Er is geen gesproken tekst herkend.")
            return

        print()
        print("-" * 60)
        print("TRANSCRIPTIE")
        print("-" * 60)
        print(transcript)
        print("-" * 60)

        # Fallback laag 1: transcript direct naar schijf, vóór klembord en
        # plakken. Zo overleeft de tekst een mislukte plakactie, een defect
        # klembord én een crash daarna.
        saved_path: Path | None = None
        try:
            saved_path = recovery.save_transcript(transcript)
            print(f"Transcript opgeslagen: {saved_path}")
        except OSError as exc:
            print(f"Waarschuwing: transcript kon niet worden opgeslagen: {exc}")

        # Klembord apart afvangen: een defect klembord mag niet als
        # "transcriptiefout" worden gemeld en mag de audio niet onnodig
        # als herstelbestand bewaren.
        try:
            pyperclip.copy(transcript)
            print("De tekst staat op het klembord.")
        except Exception as exc:
            print(f"Waarschuwing: kopiëren naar klembord is mislukt: {exc}")
            if saved_path is not None:
                print(f"De tekst is wel bewaard: {saved_path}")

        if AUTO_PASTE:
            wait_until_modifier_keys_released()
            time.sleep(PASTE_DELAY_SECONDS)

            try:
                host.paste()
                print("De tekst is in het actieve invoerveld geplakt.")

            except Exception as exc:
                print("Automatisch plakken is mislukt.")
                print(f"Foutmelding: {exc}")
                print("De tekst staat nog wel op het klembord.")
                if saved_path is not None:
                    print(f"En is bewaard als: {saved_path}")

    except Exception as exc:
        final_state = RecordingState.ERROR
        print()
        print("Er is een fout opgetreden tijdens de transcriptie.")
        print(f"Foutmelding: {exc}")

    finally:
        if temporary_path is not None and temporary_path.exists():
            if final_state == RecordingState.ERROR:
                # Fallback laag 2: bij een transcriptiefout de audio niet
                # weggooien maar bewaren, zodat later opnieuw getranscribeerd
                # kan worden.
                try:
                    kept = recovery.preserve_audio(temporary_path)
                    print(f"De opname is bewaard voor herstel: {kept}")
                except OSError as exc:
                    print(
                        "Waarschuwing: audio kon niet worden bewaard "
                        f"voor herstel: {exc}"
                    )
            elif DELETE_TEMP_AUDIO:
                try:
                    os.remove(temporary_path)
                except OSError as exc:
                    print(
                        "Waarschuwing: tijdelijk audiobestand "
                        f"kon niet worden verwijderd: {exc}"
                    )

        with state_lock:
            processing = False

        notify_state(final_state)
        print_ready_message()


# =========================================================
# MELDINGEN
# =========================================================

def print_ready_message() -> None:
    """Toont dat het programma weer beschikbaar is."""

    print()
    print(
        f"Gereed. Druk {hotkeys.format_hotkey(HOTKEY_TOKENS)} "
        "om een opname te starten."
    )


# =========================================================
# TOETSENBORDLISTENER
# =========================================================

def set_capture(callback: "Any | None") -> None:
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
    Esc:        stoppen en transcriberen (tijdens opname)
    Shift+Esc:  opname annuleren
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

    # Escape afhandelen voordat de sneltoets wordt gecontroleerd.
    if key == keyboard.Key.esc:
        with state_lock:
            is_recording = recording

        if not is_recording:
            return

        if shift_is_pressed():
            cancel_recording()
        else:
            stop_recording_and_transcribe()

        return

    if not hotkey_is_pressed():
        return

    with state_lock:
        if toggle_latched:
            return

        toggle_latched = True
        is_recording = recording
        is_processing = processing

    if MODE == "ptt":
        # Push-to-talk: ingedrukt houden neemt op; loslaten stopt (on_release).
        if is_processing:
            print("\nDe vorige opname wordt nog verwerkt.")
        elif not is_recording:
            print("\nDicteren (push-to-talk) gestart.")
            start_recording()

    else:
        # Toggle: dezelfde sneltoets wisselt tussen starten en stoppen.
        if is_recording:
            print("\nDicteren wordt gestopt via de sneltoets.")
            stop_recording_and_transcribe()
        elif is_processing:
            print("\nDe vorige opname wordt nog verwerkt.")
        else:
            print("\nDicteren wordt gestart via de sneltoets.")
            start_recording()


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
            with state_lock:
                is_recording = recording

            if is_recording:
                print("\nDicteren (push-to-talk) gestopt.")
                stop_recording_and_transcribe()


# =========================================================
# INSTELLINGEN TOEPASSEN (systeemvak → Instellingen)
# =========================================================

def current_settings() -> dict[str, Any]:
    """De huidige waarden, voor het vullen van het instellingen-dialoog."""

    return {
        "model": MODEL_NAME,
        "microphone_device": MICROPHONE_DEVICE,
        "auto_paste": AUTO_PASTE,
        "indicator_position": INDICATOR_POSITION,
        "mode": MODE,
        "hotkey": hotkeys.normalize(HOTKEY_TOKENS),
        "autostart": host.is_autostart_enabled(),
    }


def apply_settings(
    new_settings: dict[str, Any],
    indicator: RecordingIndicator,
) -> None:
    """
    Bewaart en past gewijzigde instellingen toe. Draait op de hoofdthread
    (het dialoog is daarheen gemarshald), dus GUI-calls zijn hier veilig.

    Live: pill-positie, auto-plakken, modus, sneltoets en automatisch meestarten.
    Volgende opname: microfoon. Na herstart: model.
    """

    global MODEL_NAME, MICROPHONE_DEVICE, AUTO_PASTE, INDICATOR_POSITION
    global MODE, HOTKEY_TOKENS

    new_model = str(new_settings.get("model", MODEL_NAME))
    model_changed = new_model != MODEL_NAME
    new_position = str(new_settings.get("indicator_position", INDICATOR_POSITION))
    position_changed = new_position != INDICATOR_POSITION

    MODEL_NAME = new_model
    MICROPHONE_DEVICE = new_settings.get("microphone_device", MICROPHONE_DEVICE)
    AUTO_PASTE = bool(new_settings.get("auto_paste", AUTO_PASTE))
    INDICATOR_POSITION = new_position

    if new_settings.get("mode") in ("toggle", "ptt"):
        MODE = str(new_settings["mode"])

    new_hotkey = new_settings.get("hotkey")
    if isinstance(new_hotkey, list) and new_hotkey:
        HOTKEY_TOKENS = {str(token) for token in new_hotkey}

    config.save_config(
        {
            "model": MODEL_NAME,
            "microphone_device": MICROPHONE_DEVICE,
            "auto_paste": AUTO_PASTE,
            "indicator_position": INDICATOR_POSITION,
            "mode": MODE,
            "hotkey": hotkeys.normalize(HOTKEY_TOKENS),
        }
    )

    # Automatisch meestarten staat buiten config.json (register op Windows,
    # LaunchAgent op macOS) — geregeld via de platform-seam.
    if "autostart" in new_settings:
        host.set_autostart(bool(new_settings["autostart"]))

    # Live toepassen waar mogelijk.
    if position_changed:
        indicator.set_position(new_position)

    print()
    print("Instellingen opgeslagen.")
    if model_changed:
        print("Let op: het gewijzigde model werkt pas na herstart.")


def main() -> None:
    """
    Start de indicator (hoofdthread), het systeemvak-icoon (eigen thread) en de
    globale toetsenbordlistener.

    De tkinter-mainloop moet op de hoofdthread draaien (Tk-eis), dus die
    blokkeert i.p.v. `listener.join()`. De pynput-listener en de pystray-tray
    draaien op eigen threads.
    """

    global model

    # Slechts één instantie tegelijk. Een tweede start (bijv. autostart én een
    # handmatige start, of twee keer klikken) stopt hier — vóór het laadscherm en
    # het model — zodat er nooit twee listeners, tray-iconen of indicators komen.
    if not host.acquire_single_instance():
        print("praatMaar draait al; deze tweede start wordt gestopt.")
        raise SystemExit(0)

    # Eerst het laadscherm: het model wordt op een achtergrond-thread geladen
    # (en zo nodig gedownload) terwijl de splash de voortgang toont. De splash
    # draait zijn eigen mainloop op de hoofdthread en wordt volledig afgebroken
    # voordat de indicator zijn eigen Tk-root opbouwt.
    try:
        model = Splash().run(_startup)
    except Exception as exc:
        # De fout is al in het laadscherm getoond; hier alleen netjes stoppen.
        print("Het Whisper-model kon niet worden geladen.")
        print(f"Foutmelding: {exc}")
        raise SystemExit(1) from exc

    print("Model geladen. Klaar voor gebruik.")
    print(
        f"Bediening ({MODE}): {hotkeys.format_hotkey(HOTKEY_TOKENS)} "
        "(of Esc) om te starten/stoppen."
    )

    # Harde afhankelijkheid: kan de indicator niet initialiseren, dan stopt de
    # app (RecordingIndicator gooit SystemExit — net als een mislukte model-load).
    indicator = RecordingIndicator(position=INDICATOR_POSITION)

    # Systeemvak-icoon. "Afsluiten" en Ctrl+C funnelen beide naar request_stop();
    # "Instellingen" wordt naar de hoofdthread gemarshald (tkinter-eis).
    def open_settings() -> None:
        # Lazy import: settings.py trekt zelf sounddevice binnen; die is op dit
        # punt (na de splash) allang geladen, dus deze import is direct.
        from settings import open_settings_dialog

        indicator.call_on_main(
            lambda: open_settings_dialog(
                indicator.root,
                current_settings(),
                lambda new: apply_settings(new, indicator),
                set_capture,
            )
        )

    tray = TrayIcon(
        on_quit=indicator.request_stop,
        on_settings=open_settings,
    )

    # De pill is de enige toestandseigenaar; die stuurt het tray-icoon aan.
    indicator.state_listener = tray.set_state
    tray.start()

    listener = keyboard.Listener(
        on_press=on_press,
        on_release=on_release,
    )
    listener.start()

    # Ctrl+C in de console laat de mainloop netjes eindigen. De handler draait
    # op de hoofdthread; de poll-tick (elke ~50 ms) pikt de stop-vlag op.
    signal.signal(signal.SIGINT, lambda *_: indicator.request_stop())

    try:
        indicator.run()

    except KeyboardInterrupt:
        pass

    finally:
        print()
        print("Programma wordt afgesloten.")

        listener.stop()
        tray.stop()

        with state_lock:
            active_recording = recording

        if active_recording:
            cancel_recording()

        stop_audio_stream()
        indicator.destroy()


if __name__ == "__main__":
    main()