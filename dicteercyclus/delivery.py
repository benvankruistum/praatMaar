"""Clipboard / paste / live-paste / destinations gate."""

from __future__ import annotations

import time
from pathlib import Path

import i18n
from destinations import match_command, resolve_auto_paste
from modules._contract import CycleEventType


def transcript_chars_message(transcript: str) -> str:
    """Privacy-safe console line: karaktertelling, geen volledige tekst."""

    count = len(transcript or "")
    message = i18n.t("rec.transcript_chars", count=count)
    if message == "rec.transcript_chars":
        return f"{count} chars"
    return message


class DeliveryMixin:
    def _live_paste_enabled(self) -> bool:
        """Live-plak alleen als incrementele transcriptie én live-plak aan staan."""

        return bool(self.incremental_transcription and self.incremental_live_paste)

    def _reset_live_paste_state(self) -> None:
        self._live_paste_generation += 1
        self._live_pasted_text = ""

    def _unpasted_suffix(self, transcript: str) -> str:
        """Nog niet live geplakte staart t.o.v. `" ".join`-boekhouding."""

        full = (transcript or "").strip()
        pasted = self._live_pasted_text.strip()
        if not full:
            return ""
        if not pasted:
            return full
        if full == pasted:
            return ""
        prefix = pasted + " "
        if full.startswith(prefix):
            return full[len(prefix) :].strip()
        return ""

    def _paste_delta(self, text: str, *, generation: int | None = None) -> None:
        """Plakt één chunk-/staart-delta via klembord + host.paste() (geserialiseerd).

        `generation` moet de `_live_paste_generation` van vóór de paste-poging zijn.
        Na cancel/too-short/start-reset wijkt die af → geen clipboard/paste/boekhouding.
        """

        delta = (text or "").strip()
        if not delta:
            return

        expected = self._live_paste_generation if generation is None else int(generation)

        with self._live_paste_lock:
            if expected != self._live_paste_generation:
                return

            if self._copy_text is not None:
                try:
                    self._copy_text(delta)
                except Exception as exc:
                    print(i18n.t("rec.clipboard_warn", error=exc))

            self.wait_until_modifiers_clear()
            time.sleep(self.paste_delay_seconds)

            # Cancel/too-short mogen generation bumpen zonder deze lock te nemen,
            # zodat we na delay nog kunnen afbreken vóór host.paste().
            if expected != self._live_paste_generation:
                return

            try:
                self.host.paste()
            except Exception as exc:
                print(i18n.t("rec.paste_failed"))
                print(i18n.t("rec.error", error=exc))
                return

            if expected != self._live_paste_generation:
                return

            if self._live_pasted_text:
                self._live_pasted_text = f"{self._live_pasted_text} {delta}"
            else:
                self._live_pasted_text = delta

    def _apply_transcript(self, transcript: str) -> None:
        """Bestemmingscommando, save, plakken en completion-events voor klaar tekst."""

        if not transcript:
            print()
            print(i18n.t("rec.no_speech"))
            return

        live = self._live_paste_enabled()
        dests = self._get_destinations() if self._get_destinations else []

        if not live:
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

        # Privacy: geen volledige transcripttekst naar stdout/log (tee → praatMaar.log).
        # Journal bewaart al alleen transcript_chars; console volgt die lijn.
        print()
        print("-" * 60)
        print(i18n.t("rec.transcript_header"))
        print("-" * 60)
        print(transcript_chars_message(transcript))
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

        if live:
            remaining = self._unpasted_suffix(transcript)
            if remaining:
                self._paste_delta(remaining)
            return

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
