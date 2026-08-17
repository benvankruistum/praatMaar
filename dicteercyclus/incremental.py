"""Chunk-worker en incrementele transcriptie-pad."""

from __future__ import annotations

import os
import queue
import threading
from dataclasses import dataclass
from typing import Any

from chunk_transcription import (
    OVERLAP_SECONDS,
    decide_chunk_cut,
    dedupe_overlap_text,
    trailing_silence_seconds,
)
from indicator import set_chunk_leds_enabled, signal_chunk_trigger
from modules._contract import CycleEvent, CycleEventType

# RMS onder deze drempel telt als stilte voor chunk-VAD (v1, eenvoudig).
_CHUNK_SILENCE_RMS = 0.01
_CHUNK_FRAME_SECONDS = 0.05
_CHUNK_POLL_SECONDS = 0.25


@dataclass(frozen=True)
class _ChunkWhisperJob:
    """Audio-knip klaar voor Whisper; knip/LED gebeuren vóór deze job."""

    session_id: str
    audio_1d: Any
    previous_text: str
    reason: str
    live_generation: int


class IncrementalMixin:
    def _stop_incremental_worker(self, *, wait: bool = True) -> None:
        stop = self._incremental_stop
        decision = self._incremental_thread
        whisper_thread = self._chunk_whisper_thread
        if stop is not None:
            stop.set()
        if (
            wait
            and decision is not None
            and decision.is_alive()
            and decision is not threading.current_thread()
        ):
            decision.join(timeout=5.0)
        # Sentinel zodat de Whisper-worker leegloopt i.p.v. forever te blocken.
        try:
            self._chunk_jobs.put_nowait(None)
        except Exception:
            pass
        if (
            whisper_thread is not None
            and whisper_thread.is_alive()
            and whisper_thread is not threading.current_thread()
        ):
            # wait=True: medium-model chunks kunnen lang duren.
            # wait=False (restart): korte join zodat we geen zombie achterlaten
            # die later de volgende sentinel steelt.
            whisper_thread.join(timeout=180.0 if wait else 0.5)
        self._incremental_thread = None
        self._chunk_whisper_thread = None
        self._incremental_stop = None
        if wait:
            set_chunk_leds_enabled(False)
            while True:
                try:
                    self._chunk_jobs.get_nowait()
                except queue.Empty:
                    break

    def _start_incremental_worker(self) -> None:
        if not self.incremental_transcription:
            set_chunk_leds_enabled(False)
            return

        # Oude worker alleen seinen, niet joinen — anders blokkeert start de UI.
        self._stop_incremental_worker(wait=False)
        while True:
            try:
                self._chunk_jobs.get_nowait()
            except queue.Empty:
                break
        set_chunk_leds_enabled(True)
        self._incremental_stop = threading.Event()
        self._incremental_thread = threading.Thread(
            target=self._incremental_loop,
            daemon=True,
            name="praatmaar-chunk-decide",
        )
        self._chunk_whisper_thread = threading.Thread(
            target=self._chunk_whisper_loop,
            daemon=True,
            name="praatmaar-chunk-whisper",
        )
        self._incremental_thread.start()
        self._chunk_whisper_thread.start()

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
            live_generation = self._live_paste_generation

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
                # Open chunk is (bijna) alleen stilte. Hard cap forceert alsnog
                # een fixed-knip zodat de cursor niet vastloopt (LED + live-plak).
                open_seconds = (total - through) / float(self.sample_rate)
                if open_seconds < float(self._incremental_chunk_seconds):
                    return
                reason = "fixed"
                cut_end = min(
                    total,
                    through + int(self._incremental_chunk_seconds * self.sample_rate),
                )
        else:
            cut_end = min(
                total,
                through + int(self._incremental_chunk_seconds * self.sample_rate),
            )

        if cut_end <= through:
            return

        # LED meteen bij knipbesluit — niet pas ná trage Whisper.
        signal_chunk_trigger(reason)

        overlap = int(self.sample_rate * OVERLAP_SECONDS)
        slice_start = max(0, through - overlap) if previous else through
        piece = audio[slice_start:cut_end]
        if piece.size == 0:
            return

        with self._lock:
            if self._session_id != session_id or not self._recording:
                return
            # Cursor opschuiven vóór Whisper, zodat de decide-loop doorgaat terwijl
            # medium-model inferentie seconden/tientallen seconden kost.
            self._transcribed_through_samples = cut_end

        self._chunk_jobs.put(
            _ChunkWhisperJob(
                session_id=session_id,
                audio_1d=piece.copy(),
                previous_text=previous,
                reason=reason,
                live_generation=live_generation,
            )
        )

    def _chunk_whisper_loop(self) -> None:
        """Verwerkt knip-jobs in volgorde: Whisper → partial → live-plak.

        Stop normaal alleen op de ``None``-sentinel — niet op een lege queue
        terwijl ``stop`` al gezet is. Anders kan decide ná ``stop.set()``
        (vóór de sentinel) nog een job enqueue’en die bij drain verloren gaat;
        finalize ziet dan lege ``_chunk_transcripts`` en Whisper’t de hele
        buffer opnieuw.

        Uitzondering: een *vervangen* worker (``wait=False`` restart) moet wél
        op Empty+stop stoppen, anders blijft die daemon de volgende sentinel
        stelen en hangt de nieuwe join.
        """

        stop = self._incremental_stop
        while True:
            try:
                job = self._chunk_jobs.get(timeout=0.25)
            except queue.Empty:
                if (
                    stop is not None
                    and stop.is_set()
                    and self._chunk_whisper_thread is not threading.current_thread()
                ):
                    return
                continue
            if job is None:
                return
            try:
                self._process_chunk_job(job)
            except Exception:
                continue

    def _process_chunk_job(self, job: _ChunkWhisperJob) -> None:
        try:
            raw = self._transcribe_chunks_to_text([job.audio_1d.reshape(-1, 1)])
        except Exception:
            return
        if not raw:
            return
        piece_text = dedupe_overlap_text(job.previous_text, raw) or None
        if not piece_text:
            return

        with self._lock:
            if self._session_id != job.session_id:
                return
            self._chunk_transcripts.append(piece_text)
            combined = " ".join(self._chunk_transcripts).strip()

        if combined:
            self._emit_partial(combined, job.session_id)
        if self._live_paste_enabled():
            self._paste_delta(piece_text, generation=job.live_generation)

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
                    **self.transcribe_kwargs(),
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
