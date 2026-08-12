"""
Opnamesessie — de lifecycle van één dicteercyclus.

Beheert opname → transcriberen → idle/geannuleerd/fout. De UI-toestanden
(`RecordingState`) leven in `indicator.py`; deze module is de runtime die die
toestanden aandrijft. Toetsenbordrouting blijft in de composition root (`app`).

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
import tempfile
import threading
import time
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Any

import i18n
from chunk_transcription import OVERLAP_SECONDS, dedupe_overlap_text, normalize_chunk_mode
from dicteercyclus.delivery import DeliveryMixin
from dicteercyclus.incremental import _CHUNK_POLL_SECONDS, IncrementalMixin
from dicteercyclus.mic_stream import MicStreamMixin
from dicteercyclus.timing import CycleTiming, Host, NotifyFn, format_cycle_timing
from indicator import (
    RecordingState,
    set_chunk_leds_enabled,
    set_transcription_progress,
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
from mic_errors import format_recording_start_error
from modules._contract import CycleEvent, CycleEventType
from modules.whisper import SharedWhisper

__all__ = ["CycleTiming", "Host", "NotifyFn", "Opnamesessie", "format_cycle_timing"]


class Opnamesessie(MicStreamMixin, IncrementalMixin, DeliveryMixin):
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
        whisper_beam_size: int = 5,
        whisper_vad_filter: bool = True,
        whisper_vad_min_silence_ms: int = 300,
        whisper_condition_on_previous_text: bool = False,
        whisper_no_speech_threshold: float = 0.6,
        whisper_initial_prompt: str = "",
        whisper_hotwords: str = "",
        incremental_transcription: bool = False,
        incremental_live_paste: bool = False,
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
        self.whisper_beam_size = int(whisper_beam_size)
        self.whisper_vad_filter = bool(whisper_vad_filter)
        self.whisper_vad_min_silence_ms = int(whisper_vad_min_silence_ms)
        self.whisper_condition_on_previous_text = bool(whisper_condition_on_previous_text)
        self.whisper_no_speech_threshold = float(whisper_no_speech_threshold)
        self.whisper_initial_prompt = str(whisper_initial_prompt or "")
        self.whisper_hotwords = str(whisper_hotwords or "")
        self.incremental_transcription = incremental_transcription
        self.incremental_live_paste = bool(incremental_live_paste)
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
        self._live_paste_lock = threading.Lock()
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
        # Device-identiteit bij laatste succesvolle open (lazy rebind).
        self._bound_device_identity: tuple[str, int] | None = None
        self._audio_chunks: list[Any] = []
        self._session_id: str | None = None
        self._last_partial_transcript: str | None = None
        self._chunk_transcripts: list[str] = []
        self._live_pasted_text = ""
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

    def transcribe_kwargs(self) -> dict[str, Any]:
        """Faster-Whisper ``transcribe``-kwargs uit sessie-instellingen."""

        kwargs: dict[str, Any] = {
            "language": self.language,
            "beam_size": max(1, int(self.whisper_beam_size)),
            "vad_filter": bool(self.whisper_vad_filter),
            "condition_on_previous_text": bool(self.whisper_condition_on_previous_text),
            "no_speech_threshold": float(self.whisper_no_speech_threshold),
        }
        if self.whisper_vad_filter:
            kwargs["vad_parameters"] = {
                "min_silence_duration_ms": max(0, int(self.whisper_vad_min_silence_ms)),
            }
        prompt = str(self.whisper_initial_prompt or "").strip()
        if prompt:
            kwargs["initial_prompt"] = prompt
        hotwords = str(self.whisper_hotwords or "").strip()
        if hotwords:
            kwargs["hotwords"] = hotwords
        return kwargs

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
            self._reset_live_paste_state()

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
                self._reset_live_paste_state()
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
                        if self._live_paste_enabled():
                            self._paste_delta(piece)
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
            self._reset_live_paste_state()
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
                    **self.transcribe_kwargs(),
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

