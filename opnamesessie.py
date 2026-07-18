"""
Opnamesessie — de lifecycle van één dicteercyclus.

Beheert opname → transcriberen → idle/geannuleerd/fout. De UI-toestanden
(`RecordingState`) leven in `indicator.py`; deze module is de runtime die die
toestanden aandrijft. Toetsenbordrouting blijft in `dictation.py`.

OS-plakken gaat via een geïnjecteerde `Host` (zie `docs/adr/0001-platform-seam.md`),
zodat tests een `FakeHost` kunnen steken.
"""

from __future__ import annotations

import os
import tempfile
import threading
import time
from pathlib import Path
from typing import Any, Callable, Protocol

from indicator import (
    RecordingState,
    notify_state as default_notify_state,
    push_level as default_push_level,
    reset_levels as default_reset_levels,
)


class Host(Protocol):
    def paste(self) -> None: ...


NotifyFn = Callable[[RecordingState], None] | Callable[[RecordingState, str | None], None]


class Opnamesessie:
    """
    Eén dicteersessie: microfoonbuffer, transcriptie-thread en plak-pad.

    Audio-libraries (`numpy`, `sounddevice`, `write_wav`) worden na het
    laadscherm gekoppeld via `bind_audio`, omdat die imports zwaar zijn.
    """

    def __init__(
        self,
        *,
        host: Host,
        sample_rate: int = 16000,
        channels: int = 1,
        microphone_device: int | None = None,
        minimum_recording_seconds: float = 0.30,
        auto_paste: bool = True,
        paste_delay_seconds: float = 0.30,
        language: str = "nl",
        delete_temp_audio: bool = True,
        mode: str = "toggle",
        wait_until_modifiers_clear: Callable[[], None] | None = None,
        on_ready: Callable[[], None] | None = None,
        notify: Callable[..., None] | None = None,
        push_level: Callable[[float], None] | None = None,
        reset_levels: Callable[[], None] | None = None,
        copy_text: Callable[[str], None] | None = None,
        save_transcript: Callable[[str], Path] | None = None,
        preserve_audio: Callable[[Path], Path] | None = None,
    ) -> None:
        self.host = host
        self.sample_rate = sample_rate
        self.channels = channels
        self.microphone_device = microphone_device
        self.minimum_recording_seconds = minimum_recording_seconds
        self.auto_paste = auto_paste
        self.paste_delay_seconds = paste_delay_seconds
        self.language = language
        self.delete_temp_audio = delete_temp_audio
        self.mode = mode

        self.wait_until_modifiers_clear = wait_until_modifiers_clear or (lambda: None)
        self.on_ready = on_ready or (lambda: None)
        self._notify = notify or default_notify_state
        self._push_level = push_level or default_push_level
        self._reset_levels = reset_levels or default_reset_levels
        self._copy_text = copy_text
        self._save_transcript = save_transcript
        self._preserve_audio = preserve_audio

        self._lock = threading.RLock()
        self._recording = False
        self._processing = False
        self._recording_started_at: float | None = None
        self._audio_stream: Any | None = None
        self._audio_chunks: list[Any] = []

        self.model: Any | None = None
        self._np: Any | None = None
        self._sd: Any | None = None
        self._write_wav: Any | None = None

    def bind_audio(
        self,
        *,
        numpy_mod: Any,
        sounddevice_mod: Any,
        write_wav: Callable[..., None],
    ) -> None:
        """Koppelt de zware audio-libraries na het laadscherm."""

        self._np = numpy_mod
        self._sd = sounddevice_mod
        self._write_wav = write_wav

    def warmup_microphone(self) -> None:
        """
        Opent de microfoonstream alvast (na model-load).

        Zonder dit kost de eerste InputStream.open op Windows vaak 0,5–2 s
        (zeker Bluetooth), terwijl je al praat. Warm houden = opname start meteen.
        """

        try:
            self._ensure_stream()
            print("Microfoon warm — opname start zonder wachttijd.")
        except Exception as exc:
            print(f"Microfoon-warmup mislukt (opname probeert het later opnieuw): {exc}")

    def refresh_input_device(self) -> None:
        """Sluit de warme stream zodat een gewijzigde microfoon opnieuw opent."""

        self.stop_audio_stream()

    @property
    def is_recording(self) -> bool:
        with self._lock:
            return self._recording

    @property
    def is_processing(self) -> bool:
        with self._lock:
            return self._processing

    def _require_audio(self) -> tuple[Any, Any, Any]:
        if self._np is None or self._sd is None or self._write_wav is None:
            raise RuntimeError("Audio-libraries zijn nog niet gekoppeld (bind_audio).")
        return self._np, self._sd, self._write_wav

    def _ensure_stream(self) -> None:
        """Start één InputStream als die nog niet loopt. Open gebeurt buiten de lock."""

        with self._lock:
            if self._audio_stream is not None:
                return

        _, sd, _ = self._require_audio()
        device = self._resolve_input_device(sd)

        # latency='low': kleinere buffers, snellere eerste callback na start.
        stream = sd.InputStream(
            samplerate=self.sample_rate,
            channels=self.channels,
            dtype="float32",
            callback=self.audio_callback,
            device=device,
            latency="low",
        )
        stream.start()

        with self._lock:
            if self._audio_stream is not None:
                # Parallel geopend — onze stream is overbodig.
                try:
                    stream.stop()
                    stream.close()
                except Exception:
                    pass
                return
            self._audio_stream = stream

    def audio_callback(
        self,
        indata: Any,
        frames: int,
        time_info: Any,
        status: Any,
    ) -> None:
        """sounddevice-callback: buffer + RMS voor de indicator (alleen tijdens opname)."""

        np = self._np
        if status:
            print(f"\nAudio-waarschuwing: {status}")

        with self._lock:
            is_recording = self._recording
            if is_recording:
                self._audio_chunks.append(indata.copy())

        if is_recording and frames > 0 and np is not None:
            self._push_level(float(np.sqrt(np.mean(np.square(indata)))))

    def _resolve_input_device(self, sd: Any) -> int | None:
        """
        Geeft een bruikbaar input-device terug, of None (= Windows-standaard).

        Device-indexen op Windows schuiven (Bluetooth, docks). Een oude index
        kan later een pure output zijn → PortAudio -9996 Invalid device.
        """

        chosen = self.microphone_device
        if chosen is None:
            return None

        try:
            info = sd.query_devices(chosen)
        except Exception as exc:
            print(
                f"Microfoon-apparaat {chosen} is ongeldig ({exc}); "
                "val terug op Windows-standaard."
            )
            self.microphone_device = None
            return None

        if int(info.get("max_input_channels", 0) or 0) <= 0:
            print(
                f"Apparaat {chosen} ({info.get('name', '?')}) heeft geen "
                "microfooningang; val terug op Windows-standaard."
            )
            self.microphone_device = None
            return None

        return chosen

    def start(self) -> None:
        """Start een nieuwe microfoonopname (stream blijft warm tussen sessies)."""

        with self._lock:
            if self._recording:
                return

            if self._processing:
                print("\nEr wordt nog een vorige opname verwerkt.")
                return

            self._audio_chunks = []
            self._recording = True
            self._recording_started_at = time.monotonic()

        # UI meteen rood — vóór eventuele (her)open van de stream.
        self._reset_levels()
        self._notify(RecordingState.RECORDING, self.mode)

        try:
            self._ensure_stream()
        except Exception as exc:
            with self._lock:
                self._recording = False
                self._recording_started_at = None
                self._audio_chunks.clear()
            print()
            print("De microfoonopname kon niet worden gestart.")
            print(f"Foutmelding: {exc}")
            print()
            print("Controleer:")
            print("- of Windows microfoontoegang toestaat;")
            print("- of de juiste standaardmicrofoon is geselecteerd;")
            print("- of de microfoon in Instellingen correct is ingesteld.")
            self._notify(RecordingState.ERROR)
            return

        print()
        print("● OPNAME GESTART")
        print("  Spreek nu.")
        print("  Stop met de sneltoets of met Esc.")

    def stop_audio_stream(self) -> None:
        """Stopt en sluit de warme microfoonstream (alleen bij afsluiten / mic-wissel)."""

        with self._lock:
            stream = self._audio_stream
            self._audio_stream = None

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

    def stop_and_transcribe(self) -> None:
        """Stopt de opname en start de transcriptie; microfoonstream blijft open."""

        with self._lock:
            if not self._recording:
                return

            self._recording = False
            started_at = self._recording_started_at
            self._recording_started_at = None

        duration = 0.0
        if started_at is not None:
            duration = time.monotonic() - started_at

        print()
        print(f"■ OPNAME GESTOPT ({duration:.1f} seconden)")

        if duration < self.minimum_recording_seconds:
            with self._lock:
                self._audio_chunks.clear()
            self._notify(RecordingState.IDLE)
            print("De opname was te kort en wordt niet verwerkt.")
            self.on_ready()
            return

        with self._lock:
            if not self._audio_chunks:
                self._notify(RecordingState.IDLE)
                print("Er is geen audio opgenomen.")
                self.on_ready()
                return

            self._processing = True
            chunks_to_process = [chunk.copy() for chunk in self._audio_chunks]
            self._audio_chunks.clear()

        self._notify(RecordingState.TRANSCRIBING, self.mode)

        thread = threading.Thread(
            target=self._transcribe_audio,
            args=(chunks_to_process,),
            daemon=True,
        )
        thread.start()

    def cancel(self) -> None:
        """Annuleert de opname zonder transcriptie of plakken; stream blijft warm."""

        with self._lock:
            if not self._recording:
                return

            self._recording = False
            self._recording_started_at = None
            self._audio_chunks.clear()

        self._notify(RecordingState.CANCELLED)

        print()
        print("× OPNAME GEANNULEERD")
        print("Er wordt niets getranscribeerd of geplakt.")
        self.on_ready()

    def create_temporary_wav(self, chunks: list[Any]) -> Path:
        """Maakt van de opgenomen audioblokken een tijdelijk WAV-bestand."""

        np, _, write_wav = self._require_audio()

        if not chunks:
            raise ValueError("Er zijn geen audioblokken ontvangen.")

        audio = np.concatenate(chunks, axis=0).reshape(-1)
        audio_int16 = np.int16(np.clip(audio, -1.0, 1.0) * 32767)

        temporary_file = tempfile.NamedTemporaryFile(
            prefix="whisper_dictation_",
            suffix=".wav",
            delete=False,
        )
        temporary_file.close()
        temporary_path = Path(temporary_file.name)
        write_wav(temporary_path, self.sample_rate, audio_int16)
        return temporary_path

    def _transcribe_audio(self, chunks: list[Any]) -> None:
        """Transcribeert de opgenomen audio lokaal met Faster-Whisper."""

        temporary_path: Path | None = None
        final_state = RecordingState.IDLE

        try:
            print("Transcriptie wordt lokaal uitgevoerd...")

            if self.model is None:
                raise RuntimeError("Whisper-model is niet geladen.")

            temporary_path = self.create_temporary_wav(chunks)
            segments, _info = self.model.transcribe(
                str(temporary_path),
                language=self.language,
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
                print()
                print("Er is geen gesproken tekst herkend.")
                return

            print()
            print("-" * 60)
            print("TRANSCRIPTIE")
            print("-" * 60)
            print(transcript)
            print("-" * 60)

            saved_path: Path | None = None
            if self._save_transcript is not None:
                try:
                    saved_path = self._save_transcript(transcript)
                    print(f"Transcript opgeslagen: {saved_path}")
                except OSError as exc:
                    print(
                        f"Waarschuwing: transcript kon niet worden opgeslagen: {exc}"
                    )

            if self._copy_text is not None:
                try:
                    self._copy_text(transcript)
                    print("De tekst staat op het klembord.")
                except Exception as exc:
                    print(
                        f"Waarschuwing: kopiëren naar klembord is mislukt: {exc}"
                    )
                    if saved_path is not None:
                        print(f"De tekst is wel bewaard: {saved_path}")

            if self.auto_paste:
                self.wait_until_modifiers_clear()
                time.sleep(self.paste_delay_seconds)
                try:
                    self.host.paste()
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
                    if self._preserve_audio is not None:
                        try:
                            kept = self._preserve_audio(temporary_path)
                            print(f"De opname is bewaard voor herstel: {kept}")
                        except OSError as exc:
                            print(
                                "Waarschuwing: audio kon niet worden bewaard "
                                f"voor herstel: {exc}"
                            )
                elif self.delete_temp_audio:
                    try:
                        os.remove(temporary_path)
                    except OSError as exc:
                        print(
                            "Waarschuwing: tijdelijk audiobestand "
                            f"kon niet worden verwijderd: {exc}"
                        )

            with self._lock:
                self._processing = False

            self._notify(final_state)
            self.on_ready()
