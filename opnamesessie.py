"""
Opnamesessie — de lifecycle van één dicteercyclus.

Beheert opname → transcriberen → idle/geannuleerd/fout. De UI-toestanden
(`RecordingState`) leven in `indicator.py`; deze module is de runtime die die
toestanden aandrijft. Toetsenbordrouting blijft in `dictation.py`.

Elke cyclus krijgt een `session_id` (UUID). Optioneel `emit_event` stuurt
`CycleEvent`-payloads naar de module-bus (zie `modules/`). Met
`incremental_transcription` draait een chunk-pipeline: Whisper alleen over
nieuwe audiostukken (fixed / VAD / hybrid). Bij stop worden chunk-teksten
geconcateneerd (+ eventuele staart); geen tweede volle-buffer-run.
Zie `docs/superpowers/specs/2026-08-01-chunk-transcription-pipeline-design.md`.

OS-plakken gaat via een geïnjecteerde `Host` (zie `docs/adr/0001-platform-seam.md`),
zodat tests een `FakeHost` kunnen steken.
"""

from __future__ import annotations

import os
import sys
import tempfile
import threading
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

import i18n
from chunk_transcription import (
    OVERLAP_SECONDS,
    decide_chunk_cut,
    dedupe_overlap_text,
    normalize_chunk_mode,
    trailing_silence_seconds,
)
from destinations import match_command, resolve_auto_paste
from indicator import (
    RecordingState,
    set_chunk_leds_enabled,
    set_transcription_progress,
    signal_chunk_trigger,
)
from indicator import (
    notify_state as default_notify_state,
)
from indicator import (
    push_level as default_push_level,
)
from indicator import (
    reset_levels as default_reset_levels,
)
from indicator._contract import transcription_percent
from mic_errors import (
    first_input_device_index,
    format_recording_start_error,
    refresh_portaudio,
)
from modules._contract import CycleEvent, CycleEventType
from modules.whisper import SharedWhisper

# RMS onder deze drempel telt als stilte voor chunk-VAD (v1, eenvoudig).
_CHUNK_SILENCE_RMS = 0.01
_CHUNK_FRAME_SECONDS = 0.05
_CHUNK_POLL_SECONDS = 0.25


class Host(Protocol):
    def paste(self) -> None: ...


NotifyFn = Callable[[RecordingState], None] | Callable[[RecordingState, str | None], None]


@dataclass
class CycleTiming:
    """Fase-tijden van één dicteercyclus (na stop), voor `praatMaar.log`."""

    session_id: str
    path: str  # "full" | "chunk" | "partial"
    record_s: float
    stop_at: float
    stop_join_s: float
    wav_s: float | None = None
    whisper_s: float | None = None
    deliver_s: float | None = None

    def log(self) -> None:
        print(format_cycle_timing(self))


def format_cycle_timing(timing: CycleTiming) -> str:
    """Machine-leesbare timingregel; zie `docs/profiling.md`."""

    sid = (timing.session_id or "?")[:8]

    def _fmt(value: float | None) -> str:
        return "—" if value is None else f"{value:.3f}s"

    total = max(0.0, time.perf_counter() - timing.stop_at)
    return (
        f"cycle.timing id={sid} path={timing.path} "
        f"record={timing.record_s:.3f}s stop_join={timing.stop_join_s:.3f}s "
        f"wav={_fmt(timing.wav_s)} whisper={_fmt(timing.whisper_s)} "
        f"deliver={_fmt(timing.deliver_s)} total_after_stop={total:.3f}s"
    )


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
        warm_microphone: bool = False,
        incremental_transcription: bool = False,
        incremental_interval_seconds: float = 3.0,
        incremental_min_seconds: float = 1.5,
        incremental_chunk_mode: str = "hybrid",
        incremental_vad_ms: int = 2000,
        incremental_chunk_seconds: float = 30.0,
        wait_until_modifiers_clear: Callable[[], None] | None = None,
        emit_event: Callable[[CycleEvent], None] | None = None,
        on_ready: Callable[[], None] | None = None,
        notify: Callable[..., None] | None = None,
        push_level: Callable[[float], None] | None = None,
        reset_levels: Callable[[], None] | None = None,
        copy_text: Callable[[str], None] | None = None,
        save_transcript: Callable[[str], Path] | None = None,
        preserve_audio: Callable[[Path], Path] | None = None,
        on_destination_command: Callable[[str, str | None], None] | None = None,
        get_destinations: Callable[[], list[dict[str, Any]]] | None = None,
        get_active_destination: Callable[[], str | None] | None = None,
        on_user_error: Callable[[str], None] | None = None,
        on_mic_ready: Callable[[], None] | None = None,
        has_external_streams: Callable[[], bool] | None = None,
        shared_whisper: SharedWhisper | None = None,
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
        self.warm_microphone = warm_microphone
        self.incremental_transcription = incremental_transcription
        self._incremental_interval_seconds = incremental_interval_seconds
        self._incremental_min_seconds = incremental_min_seconds
        self.incremental_chunk_mode = normalize_chunk_mode(incremental_chunk_mode)
        self.incremental_vad_ms = max(0, int(incremental_vad_ms))
        self._incremental_chunk_seconds = float(incremental_chunk_seconds)
        self._chunk_poll_seconds = _CHUNK_POLL_SECONDS

        self.wait_until_modifiers_clear = wait_until_modifiers_clear or (lambda: None)
        self._emit_event = emit_event
        self.on_ready = on_ready or (lambda: None)
        self._notify = notify or default_notify_state
        self._push_level = push_level or default_push_level
        self._reset_levels = reset_levels or default_reset_levels
        self._copy_text = copy_text
        self._save_transcript = save_transcript
        self._preserve_audio = preserve_audio
        self._on_destination_command = on_destination_command
        self._get_destinations = get_destinations
        self._get_active_destination = get_active_destination
        self._on_user_error = on_user_error
        self._on_mic_ready = on_mic_ready
        # Modules (Meeting Buddy-capture) openen eigen InputStreams op dezelfde
        # sounddevice-module; PortAudio herinitialiseren trekt die onder hen weg.
        self._has_external_streams = has_external_streams

        self._lock = threading.RLock()
        self._recording = False
        self._processing = False
        self._recording_started_at: float | None = None
        self._audio_stream: Any | None = None
        # Warm-stream gezondheid: Bluetooth-reconnect laat soms een "zombie"
        # InputStream achter (object bestaat, active=False of geen callbacks).
        self._stream_opened_at: float | None = None
        self._last_audio_callback_at: float | None = None
        # Geen callbacks langer dan dit → stream als dood beschouwen.
        self._stream_stale_after_seconds = 1.5
        self._audio_chunks: list[Any] = []
        self._session_id: str | None = None
        self._last_partial_transcript: str | None = None
        self._chunk_transcripts: list[str] = []
        self._transcribed_through_samples: int = 0
        self._incremental_thread: threading.Thread | None = None
        self._incremental_stop: threading.Event | None = None
        self._whisper = shared_whisper if shared_whisper is not None else SharedWhisper()

        self._np: Any | None = None
        self._sd: Any | None = None
        self._write_wav: Any | None = None

    @property
    def model(self) -> Any | None:
        return self._whisper.model

    @model.setter
    def model(self, value: Any | None) -> None:
        self._whisper.set_model(value)

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

    def warmup_microphone(self) -> bool:
        """
        Opent de microfoonstream alvast (na model-load).

        Alleen als `warm_microphone` aan staat (en niet op macOS). Zonder
        warmup kost de eerste InputStream.open op Windows vaak 0,5–2 s
        (zeker Bluetooth). Op macOS nooit warm: anders blijft de systeembrede
        mic-indicator permanent in de menubalk staan.

        Retourneert True als de microfoon bruikbaar is (of warm houden uit staat
        en een stille probe slaagt).
        """

        if not self._keep_stream_warm():
            return True

        try:
            self._ensure_stream()
            print(i18n.t("mic.warm"))
            if self._on_mic_ready is not None:
                self._on_mic_ready()
            return True
        except Exception as exc:
            # Warmup is best-effort: geen dialoog (GUI bestaat vaak nog niet).
            print(i18n.t("mic.warm_failed", error=exc))
            print(format_recording_start_error(exc))
            return False

    def probe_microphone(self) -> bool:
        """Controleert stilletjes of een inputstream geopend kan worden."""

        try:
            self._ensure_stream()
            if self._on_mic_ready is not None:
                self._on_mic_ready()
            return True
        except Exception:
            return False
        finally:
            if not self._keep_stream_warm():
                self.stop_audio_stream()

    def _keep_stream_warm(self) -> bool:
        """Effectief warm houden: user-optie, nooit op macOS (menubalk-indicator)."""

        return bool(self.warm_microphone) and sys.platform != "darwin"

    def _release_stream_if_cold(self) -> None:
        """Sluit de stream na een sessie tenzij warm houden aan staat."""

        if not self._keep_stream_warm():
            self.stop_audio_stream()

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

    def _error_status_hint(self, recovery_kept: Path | None) -> str:
        """Korte next-step-subline voor de ERROR-pill (FR-UX-04)."""

        if recovery_kept is not None:
            return i18n.t("state.error_recovery_hint")
        return i18n.t("state.error_retry_hint")

    def _notify_final(self, state: RecordingState, recovery_kept: Path | None = None) -> None:
        if state == RecordingState.ERROR:
            self._notify(state, self.mode, hint=self._error_status_hint(recovery_kept))
        else:
            self._notify(state)

    def _event(
        self,
        event_type: CycleEventType,
        *,
        transcript: str | None = None,
        path: str | None = None,
        destination: str | None = None,
        error: str | None = None,
        recovery_path: str | None = None,
        destination_command: str | None = None,
        destination_name: str | None = None,
        source: str = "live",
        session_id: str | None = None,
    ) -> None:
        # Expliciete session_id: afrondingspaden (transcribe-worker, early
        # returns) emitten met het id van hún cyclus, ook als er inmiddels
        # een nieuwe cyclus gestart is die self._session_id verving.
        sid = session_id if session_id is not None else self._session_id
        if self._emit_event is None or sid is None:
            return

        self._emit_event(
            CycleEvent(
                type=event_type,
                session_id=sid,
                transcript=transcript,
                path=path,
                destination=destination,
                language=self.language,
                mode=self.mode,
                error=error,
                recovery_path=recovery_path,
                destination_command=destination_command,
                destination_name=destination_name,
                source=source,
            )
        )

    def _clear_session_id(self, session_id: str | None) -> None:
        """Wist het sessie-id alleen als het nog bij déze cyclus hoort.

        Onvoorwaardelijk ``self._session_id = None`` clobberde het id van een
        cyclus die direct na de vorige gestart was; diens events vielen dan
        stil (guard in ``_event``).
        """

        with self._lock:
            if self._session_id == session_id:
                self._session_id = None

    def _stop_incremental_worker(self, *, wait: bool = True) -> None:
        stop = self._incremental_stop
        thread = self._incremental_thread
        if stop is not None:
            stop.set()
        if (
            wait
            and thread is not None
            and thread.is_alive()
            and thread is not threading.current_thread()
        ):
            thread.join(timeout=5.0)
        self._incremental_thread = None
        self._incremental_stop = None
        if wait:
            set_chunk_leds_enabled(False)

    def _start_incremental_worker(self) -> None:
        if not self.incremental_transcription:
            set_chunk_leds_enabled(False)
            return

        # Oude worker alleen seinen, niet joinen — anders blokkeert start de UI.
        self._stop_incremental_worker(wait=False)
        set_chunk_leds_enabled(True)
        self._incremental_stop = threading.Event()
        self._incremental_thread = threading.Thread(
            target=self._incremental_loop,
            daemon=True,
        )
        self._incremental_thread.start()

    def _concat_audio(self, chunks: list[Any]) -> Any:
        np, _, _ = self._require_audio()
        if not chunks:
            return np.zeros((0,), dtype=np.float32)
        return np.concatenate(chunks, axis=0).reshape(-1)

    def _sample_count_locked(self) -> int:
        return int(sum(int(chunk.shape[0]) for chunk in self._audio_chunks))

    def _rms_frames(self, audio: Any) -> list[float]:
        np, _, _ = self._require_audio()
        if audio.size == 0:
            return []
        frame = max(1, int(self.sample_rate * _CHUNK_FRAME_SECONDS))
        levels: list[float] = []
        for start in range(0, int(audio.shape[0]), frame):
            piece = audio[start : start + frame]
            levels.append(float(np.sqrt(np.mean(np.square(piece)))))
        return levels

    def _emit_partial(self, transcript: str, session_id: str) -> None:
        with self._lock:
            self._last_partial_transcript = transcript
        if self._emit_event is not None:
            self._emit_event(
                CycleEvent(
                    type=CycleEventType.TRANSCRIPT_PARTIAL,
                    session_id=session_id,
                    transcript=transcript,
                    language=self.language,
                    mode=self.mode,
                )
            )

    def _commit_audio_slice(
        self,
        *,
        audio: Any,
        start_sample: int,
        end_sample: int,
        previous_text: str,
    ) -> str | None:
        """Whisper over [start,end) + overlap-prefix; retourneert ontdubbelde tekst."""

        if end_sample <= start_sample:
            return None
        overlap = int(self.sample_rate * OVERLAP_SECONDS)
        slice_start = max(0, start_sample - overlap) if previous_text else start_sample
        piece = audio[slice_start:end_sample]
        if piece.size == 0:
            return None
        try:
            raw = self._transcribe_chunks_to_text([piece.reshape(-1, 1)])
        except Exception:
            return None
        if not raw:
            return None
        return dedupe_overlap_text(previous_text, raw) or None

    def _try_commit_chunk(self, reason: str) -> None:
        with self._lock:
            if not self._recording:
                return
            session_id = self._session_id
            chunks_copy = [chunk.copy() for chunk in self._audio_chunks]
            through = self._transcribed_through_samples
            previous = " ".join(self._chunk_transcripts).strip()
            total = self._sample_count_locked()

        if session_id is None or not chunks_copy or total <= through:
            return

        audio = self._concat_audio(chunks_copy)
        open_audio = audio[through:]
        silence_s = trailing_silence_seconds(
            self._rms_frames(open_audio),
            frame_seconds=_CHUNK_FRAME_SECONDS,
            silence_rms=_CHUNK_SILENCE_RMS,
        )
        silence_samples = int(silence_s * self.sample_rate)

        if reason == "vad":
            cut_end = total - silence_samples
            if cut_end <= through:
                # Open chunk is (bijna) alleen stilte — wacht op hard cap.
                return
        else:
            cut_end = min(
                total,
                through + int(self._incremental_chunk_seconds * self.sample_rate),
            )

        if cut_end <= through:
            return

        piece_text = self._commit_audio_slice(
            audio=audio,
            start_sample=through,
            end_sample=cut_end,
            previous_text=previous,
        )
        signal_chunk_trigger(reason)

        with self._lock:
            if self._session_id != session_id or not self._recording:
                return
            self._transcribed_through_samples = cut_end
            if piece_text:
                self._chunk_transcripts.append(piece_text)
                combined = " ".join(self._chunk_transcripts).strip()
            else:
                combined = previous

        if piece_text and combined:
            self._emit_partial(combined, session_id)

    def _incremental_loop(self) -> None:
        stop = self._incremental_stop
        if stop is None:
            return

        while not stop.wait(self._chunk_poll_seconds):
            with self._lock:
                if not self._recording:
                    return
                chunks_copy = [chunk.copy() for chunk in self._audio_chunks]
                through = self._transcribed_through_samples

            if not chunks_copy:
                continue

            audio = self._concat_audio(chunks_copy)
            total = int(audio.shape[0])
            open_seconds = (total - through) / float(self.sample_rate)
            silence_s = trailing_silence_seconds(
                self._rms_frames(audio[through:]),
                frame_seconds=_CHUNK_FRAME_SECONDS,
                silence_rms=_CHUNK_SILENCE_RMS,
            )
            reason = decide_chunk_cut(
                mode=self.incremental_chunk_mode,
                open_seconds=open_seconds,
                trailing_silence_seconds=silence_s,
                chunk_seconds=self._incremental_chunk_seconds,
                vad_ms=self.incremental_vad_ms,
                min_seconds=self._incremental_min_seconds,
            )
            if reason is None:
                continue
            try:
                self._try_commit_chunk(reason)
            except Exception:
                continue

    def _transcribe_chunks_to_text(self, chunks: list[Any]) -> str:
        """Transcribeert audioblokken naar tekst (incrementeel + finaal)."""

        temporary_path = self.create_temporary_wav(chunks)
        try:
            with self._whisper.locked_model() as model:
                segments, _info = model.transcribe(
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

            return " ".join(text_parts).strip()
        finally:
            if self.delete_temp_audio and temporary_path.exists():
                try:
                    os.remove(temporary_path)
                except OSError:
                    pass

    def _require_audio(self) -> tuple[Any, Any, Any]:
        if self._np is None or self._sd is None or self._write_wav is None:
            raise RuntimeError("Audio-libraries zijn nog niet gekoppeld (bind_audio).")
        return self._np, self._sd, self._write_wav

    def _stream_is_alive(self) -> bool:
        """True als de warme InputStream nog bruikbaar lijkt."""

        stream = self._audio_stream
        if stream is None:
            return False
        if not getattr(stream, "active", True):
            return False

        now = time.monotonic()
        opened_at = self._stream_opened_at
        if opened_at is not None and (now - opened_at) < self._stream_stale_after_seconds:
            # Net geopend: wacht op eerste callbacks.
            return True

        last = self._last_audio_callback_at
        if last is None:
            return False
        return (now - last) <= self._stream_stale_after_seconds

    def _ensure_stream(self) -> None:
        """Start één InputStream als die nog niet loopt. Heropent dode warme streams."""

        if self._audio_stream is not None and not self._stream_is_alive():
            self.stop_audio_stream()

        with self._lock:
            if self._audio_stream is not None:
                return

        _, sd, _ = self._require_audio()
        # Bluetooth/hotplug: herenumereren vóór open (geen eigen stream hier).
        self._refresh_portaudio_if_safe(sd)

        device = self._resolve_input_device(sd)
        try:
            self._open_input_stream(sd, device)
        except Exception as first_exc:
            # Stale default (-1) of oude index: opnieuw enumereren + concrete mic.
            self._refresh_portaudio_if_safe(sd)
            device = self._resolve_input_device(sd)
            if device is None:
                device = first_input_device_index(sd)
            if device is None:
                raise first_exc
            self._open_input_stream(sd, device)

    def _refresh_portaudio_if_safe(self, sd: Any) -> bool:
        """Herenumereer PortAudio alleen als er app-breed geen streams open zijn.

        ``refresh_portaudio`` doet ``_terminate()`` tot PortAudio uit is; met een
        actieve module-stream (Meeting Buddy-capture op dezelfde sounddevice-
        module) trekt dat die stream eronder weg — dode streams of een native
        crash. Overslaan kost alleen hotplug-detectie voor deze start.
        """

        if self._has_external_streams is not None:
            try:
                if self._has_external_streams():
                    return False
            except Exception:
                # Onbekende toestand: niet herinitialiseren (veilige kant).
                return False
        refresh_portaudio(sd)
        return True

    def _open_input_stream(self, sd: Any, device: int | None) -> None:
        """Opent en start een InputStream; koppelt die aan de sessie."""

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
            self._stream_opened_at = time.monotonic()
            self._last_audio_callback_at = None

    def audio_callback(
        self,
        indata: Any,
        frames: int,
        time_info: Any,
        status: Any,
    ) -> None:
        """sounddevice-callback: buffer + RMS voor de indicator (alleen tijdens opname)."""

        self._last_audio_callback_at = time.monotonic()

        np = self._np
        if status:
            print("\n" + i18n.t("rec.audio_warning", status=status))

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
            print(i18n.t("rec.device_invalid", device=chosen, error=exc))
            self.microphone_device = None
            return None

        if int(info.get("max_input_channels", 0) or 0) <= 0:
            print(
                i18n.t(
                    "rec.device_no_input",
                    device=chosen,
                    name=info.get("name", "?"),
                )
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
                print("\n" + i18n.t("rec.busy"))
                self._notify(RecordingState.TRANSCRIBING, self.mode)
                return

            self._audio_chunks = []
            self._recording = True
            self._recording_started_at = time.monotonic()
            self._session_id = str(uuid.uuid4())
            session_id = self._session_id
            self._last_partial_transcript = None
            self._chunk_transcripts = []
            self._transcribed_through_samples = 0

        self._event(CycleEventType.CYCLE_STARTED, session_id=session_id)

        # PREPARING tot de stream open is — geen false “Opname” (FR-UX-02).
        self._reset_levels()
        self._notify(RecordingState.PREPARING, self.mode)

        self._start_incremental_worker()

        try:
            self._ensure_stream()
            if self._on_mic_ready is not None:
                self._on_mic_ready()
        except Exception as exc:
            with self._lock:
                self._recording = False
                self._recording_started_at = None
                self._audio_chunks.clear()
            self._stop_incremental_worker(wait=False)
            message = format_recording_start_error(exc)
            print()
            print(i18n.t("rec.start_failed"))
            print(message)
            if self._on_user_error is not None:
                self._on_user_error(message)
            self._notify(
                RecordingState.ERROR,
                self.mode,
                hint=i18n.t("state.error_mic_hint"),
            )
            self._event(CycleEventType.CYCLE_ERROR, error=message, session_id=session_id)
            self._event(CycleEventType.CYCLE_IDLE, session_id=session_id)
            self._clear_session_id(session_id)
            return

        self._notify(RecordingState.RECORDING, self.mode)

        print()
        print(i18n.t("rec.started"))
        print(i18n.t("rec.speak"))
        print(i18n.t("rec.stop_hint"))

    def stop_audio_stream(self) -> None:
        """Stopt en sluit de warme microfoonstream (alleen bij afsluiten / mic-wissel)."""

        with self._lock:
            stream = self._audio_stream
            self._audio_stream = None
            self._stream_opened_at = None
            self._last_audio_callback_at = None

        if stream is None:
            return

        try:
            stream.stop()
        except Exception as exc:
            print(i18n.t("rec.mic_stop_warn", error=exc))

        try:
            stream.close()
        except Exception as exc:
            print(i18n.t("rec.mic_close_warn", error=exc))

    def stop_and_transcribe(self) -> None:
        """Stopt de opname en start de transcriptie."""

        stop_at = time.perf_counter()

        with self._lock:
            if not self._recording:
                return

            self._recording = False
            started_at = self._recording_started_at
            self._recording_started_at = None
            session_id = self._session_id

        duration = 0.0
        if started_at is not None:
            duration = time.monotonic() - started_at

        print()
        print(i18n.t("rec.stopped", seconds=f"{duration:.1f}"))

        if duration < self.minimum_recording_seconds:
            with self._lock:
                self._audio_chunks.clear()
                self._chunk_transcripts = []
                self._transcribed_through_samples = 0
            # Seinen zonder join: UI blijft snappy.
            self._stop_incremental_worker(wait=False)
            set_chunk_leds_enabled(False)
            self._notify(RecordingState.IDLE)
            print(i18n.t("rec.too_short"))
            self._release_stream_if_cold()
            self._event(CycleEventType.CYCLE_IDLE, session_id=session_id)
            self._clear_session_id(session_id)
            self.on_ready()
            return

        with self._lock:
            chunks_empty = not self._audio_chunks
            if not chunks_empty:
                self._processing = True
                chunks_to_process = [chunk.copy() for chunk in self._audio_chunks]
                self._audio_chunks.clear()

        if chunks_empty:
            self._stop_incremental_worker(wait=False)
            self._notify(RecordingState.IDLE)
            print(i18n.t("rec.no_audio"))
            # Vaak een dode warme stream na Bluetooth reconnect — heropen bij
            # de volgende start i.p.v. dezelfde zombie te hergebruiken.
            self.refresh_input_device()
            self._event(CycleEventType.CYCLE_IDLE, session_id=session_id)
            self._clear_session_id(session_id)
            self.on_ready()
            return

        # UI meteen naar Transcriberen — join van chunk-Whisper mag daarna.
        self._event(CycleEventType.CYCLE_TRANSCRIBING)
        self._release_stream_if_cold()
        self._notify(RecordingState.TRANSCRIBING, self.mode)

        # Join zodat een in-flight chunk nog kan landen (events).
        self._stop_incremental_worker(wait=True)
        stop_join_s = time.perf_counter() - stop_at

        with self._lock:
            chunk_texts = list(self._chunk_transcripts)
            through = self._transcribed_through_samples
            self._last_partial_transcript = None
            self._chunk_transcripts = []
            self._transcribed_through_samples = 0

        timing = CycleTiming(
            session_id=session_id or "",
            path="chunk" if chunk_texts else "full",
            record_s=duration,
            stop_at=stop_at,
            stop_join_s=stop_join_s,
        )

        if chunk_texts:
            thread = threading.Thread(
                target=self._finalize_chunk_transcript,
                args=(chunks_to_process, chunk_texts, through, timing),
                daemon=True,
            )
        else:
            thread = threading.Thread(
                target=self._transcribe_audio,
                args=(chunks_to_process, timing),
                daemon=True,
            )
        thread.start()

    def _finalize_chunk_transcript(
        self,
        chunks: list[Any],
        chunk_texts: list[str],
        through_samples: int,
        timing: CycleTiming,
    ) -> None:
        """Plakt chunk-teksten; Whisper alleen over de onaffe staart."""

        temporary_path: Path | None = None
        final_state = RecordingState.IDLE
        error_message: str | None = None
        recovery_kept: Path | None = None

        try:
            print(i18n.t("rec.transcribing"))
            set_transcription_progress(0)
            texts = list(chunk_texts)
            previous = " ".join(texts).strip()
            audio = self._concat_audio(chunks)
            total = int(audio.shape[0])
            tail_start = max(0, min(through_samples, total))
            tail = audio[tail_start:]
            tail_seconds = tail.shape[0] / float(self.sample_rate)

            if tail_seconds >= self._incremental_min_seconds and tail.shape[0] > 0:
                whisper_started = time.perf_counter()
                overlap = int(self.sample_rate * OVERLAP_SECONDS)
                slice_start = max(0, tail_start - overlap) if previous else tail_start
                piece_audio = audio[slice_start:total]
                try:
                    raw = self._transcribe_chunks_to_text([piece_audio.reshape(-1, 1)])
                    piece = dedupe_overlap_text(previous, raw) if raw else None
                    if piece:
                        texts.append(piece)
                except Exception as exc:
                    error_message = str(exc)
                    print()
                    print(i18n.t("rec.transcribe_error"))
                    print(i18n.t("rec.error", error=exc))
                    wav_started = time.perf_counter()
                    temporary_path = self.create_temporary_wav(chunks)
                    timing.wav_s = time.perf_counter() - wav_started
                    if self._preserve_audio is not None:
                        try:
                            recovery_kept = self._preserve_audio(temporary_path)
                            print(i18n.t("rec.recovery_saved", path=recovery_kept))
                        except OSError as preserve_exc:
                            print(i18n.t("rec.recovery_preserve_warn", error=preserve_exc))
                    final_state = RecordingState.ERROR
                timing.whisper_s = time.perf_counter() - whisper_started

            transcript = " ".join(t for t in texts if t).strip()
            set_transcription_progress(100)
            if transcript:
                deliver_started = time.perf_counter()
                self._apply_transcript(transcript)
                timing.deliver_s = time.perf_counter() - deliver_started
            elif final_state != RecordingState.ERROR:
                print()
                print(i18n.t("rec.no_speech"))

        except Exception as exc:
            final_state = RecordingState.ERROR
            error_message = str(exc)
            print()
            print(i18n.t("rec.transcribe_error"))
            print(i18n.t("rec.error", error=exc))
            if temporary_path is None:
                try:
                    temporary_path = self.create_temporary_wav(chunks)
                except Exception:
                    temporary_path = None
            if temporary_path is not None and self._preserve_audio is not None:
                try:
                    recovery_kept = self._preserve_audio(temporary_path)
                    print(i18n.t("rec.recovery_saved", path=recovery_kept))
                except OSError as preserve_exc:
                    print(i18n.t("rec.recovery_preserve_warn", error=preserve_exc))

        finally:
            if temporary_path is not None and temporary_path.exists():
                if final_state == RecordingState.ERROR and recovery_kept is None:
                    if self._preserve_audio is not None:
                        try:
                            recovery_kept = self._preserve_audio(temporary_path)
                        except OSError:
                            pass
                if self.delete_temp_audio and (
                    final_state != RecordingState.ERROR or recovery_kept is not None
                ):
                    try:
                        if temporary_path.exists():
                            os.remove(temporary_path)
                    except OSError as exc:
                        print(i18n.t("rec.temp_delete_warn", error=exc))

            timing.log()
            session_id = timing.session_id or None
            with self._lock:
                self._processing = False

            self._notify_final(final_state, recovery_kept)
            if error_message is not None:
                self._event(
                    CycleEventType.CYCLE_ERROR,
                    error=error_message,
                    recovery_path=str(recovery_kept) if recovery_kept is not None else None,
                    session_id=session_id,
                )
            self._event(CycleEventType.CYCLE_IDLE, session_id=session_id)
            self._clear_session_id(session_id)
            self.on_ready()

    def cancel(self) -> None:
        """Annuleert de opname zonder transcriptie of plakken."""

        with self._lock:
            if not self._recording:
                return

            self._recording = False
            self._recording_started_at = None
            self._audio_chunks.clear()
            self._last_partial_transcript = None
            self._chunk_transcripts = []
            self._transcribed_through_samples = 0
            session_id = self._session_id

        self._event(CycleEventType.CYCLE_CANCELLED, session_id=session_id)
        self._notify(RecordingState.CANCELLED)

        self._stop_incremental_worker(wait=False)
        set_chunk_leds_enabled(False)

        print()
        print(i18n.t("rec.cancelled"))
        print(i18n.t("rec.cancelled_detail"))
        self._release_stream_if_cold()
        self._event(CycleEventType.CYCLE_IDLE, session_id=session_id)
        self._clear_session_id(session_id)
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

    def _apply_transcript(self, transcript: str) -> None:
        """Bestemmingscommando, save, plakken en completion-events voor klaar tekst."""

        if not transcript:
            print()
            print(i18n.t("rec.no_speech"))
            return

        dests = self._get_destinations() if self._get_destinations else []
        kind, name = match_command(transcript, dests)
        if kind in ("set", "reset"):
            if self._on_destination_command:
                self._on_destination_command(kind, name)
            self._event(
                CycleEventType.DESTINATION_COMMAND,
                transcript=transcript,
                destination_command=kind,
                destination_name=name,
            )
            if kind == "set":
                print(i18n.t("destination.switched", name=name))
            else:
                print(i18n.t("destination.reset"))
            return

        print()
        print("-" * 60)
        print(i18n.t("rec.transcript_header"))
        print("-" * 60)
        print(transcript)
        print("-" * 60)

        active = self._get_active_destination() if self._get_active_destination else None
        self._event(
            CycleEventType.CYCLE_COMPLETED,
            transcript=transcript,
            destination=active,
        )

        saved_path: Path | None = None
        if self._save_transcript is not None:
            try:
                saved_path = self._save_transcript(transcript)
                print(i18n.t("rec.saved", path=saved_path))
                self._event(
                    CycleEventType.TRANSCRIPT_SAVED,
                    transcript=transcript,
                    path=str(saved_path),
                    destination=active,
                )
            except OSError as exc:
                print(i18n.t("rec.save_warn", error=exc))

        deliver = resolve_auto_paste(active, dests, self.auto_paste)

        if not deliver:
            if saved_path is not None:
                print(i18n.t("rec.saved_only"))
        else:
            if self._copy_text is not None:
                try:
                    self._copy_text(transcript)
                    print(i18n.t("rec.clipboard"))
                except Exception as exc:
                    print(i18n.t("rec.clipboard_warn", error=exc))
                    if saved_path is not None:
                        print(i18n.t("rec.saved_anyway", path=saved_path))

            self.wait_until_modifiers_clear()
            time.sleep(self.paste_delay_seconds)
            try:
                self.host.paste()
                print(i18n.t("rec.pasted"))
            except Exception as exc:
                print(i18n.t("rec.paste_failed"))
                print(i18n.t("rec.error", error=exc))
                print(i18n.t("rec.still_clipboard"))
                if saved_path is not None:
                    print(i18n.t("rec.and_saved", path=saved_path))

    def _transcribe_audio(self, chunks: list[Any], timing: CycleTiming) -> None:
        """Transcribeert de opgenomen audio lokaal met Faster-Whisper."""

        temporary_path: Path | None = None
        final_state = RecordingState.IDLE
        error_message: str | None = None
        recovery_kept: Path | None = None

        try:
            print(i18n.t("rec.transcribing"))
            set_transcription_progress(0)

            sample_count = sum(chunk.shape[0] for chunk in chunks)
            duration_seconds = sample_count / float(self.sample_rate)
            last_logged_bucket = -1

            wav_started = time.perf_counter()
            temporary_path = self.create_temporary_wav(chunks)
            timing.wav_s = time.perf_counter() - wav_started

            whisper_started = time.perf_counter()
            with self._whisper.locked_model() as model:
                segments, _info = model.transcribe(
                    str(temporary_path),
                    language=self.language,
                    beam_size=5,
                    vad_filter=True,
                    vad_parameters={"min_silence_duration_ms": 300},
                    condition_on_previous_text=False,
                )
                text_parts: list[str] = []
                for segment in segments:
                    end = float(getattr(segment, "end", 0.0) or 0.0)
                    percent = transcription_percent(end, duration_seconds)
                    set_transcription_progress(percent)
                    bucket = percent // 25
                    if bucket > last_logged_bucket and bucket >= 1:
                        print(i18n.t("rec.transcribing_progress", percent=percent))
                        last_logged_bucket = bucket
                    text = segment.text.strip()
                    if text:
                        text_parts.append(text)
            timing.whisper_s = time.perf_counter() - whisper_started

            set_transcription_progress(100)
            deliver_started = time.perf_counter()
            self._apply_transcript(" ".join(text_parts).strip())
            timing.deliver_s = time.perf_counter() - deliver_started

        except Exception as exc:
            final_state = RecordingState.ERROR
            error_message = str(exc)
            print()
            print(i18n.t("rec.transcribe_error"))
            print(i18n.t("rec.error", error=exc))

        finally:
            if temporary_path is not None and temporary_path.exists():
                if final_state == RecordingState.ERROR:
                    if self._preserve_audio is not None:
                        try:
                            recovery_kept = self._preserve_audio(temporary_path)
                            print(i18n.t("rec.recovery_saved", path=recovery_kept))
                        except OSError as exc:
                            print(i18n.t("rec.recovery_preserve_warn", error=exc))
                            # Recovery-map vol/onbeschrijfbaar: laat de
                            # opgenomen spraak niet in %TEMP% achter.
                            try:
                                os.remove(temporary_path)
                            except OSError:
                                pass
                elif self.delete_temp_audio:
                    try:
                        os.remove(temporary_path)
                    except OSError as exc:
                        print(i18n.t("rec.temp_delete_warn", error=exc))

            timing.log()
            # Vanaf _processing=False kan een nieuwe cyclus starten met een
            # nieuw session_id; alles hieronder werkt daarom expliciet met
            # het id van déze cyclus en wist het alleen als het nog klopt.
            session_id = timing.session_id or None
            with self._lock:
                self._processing = False

            self._notify_final(final_state, recovery_kept)
            if error_message is not None:
                self._event(
                    CycleEventType.CYCLE_ERROR,
                    error=error_message,
                    recovery_path=str(recovery_kept) if recovery_kept is not None else None,
                    session_id=session_id,
                )
            self._event(CycleEventType.CYCLE_IDLE, session_id=session_id)
            self._clear_session_id(session_id)
            self.on_ready()
