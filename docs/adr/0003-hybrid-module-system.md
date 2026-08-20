# 0003 — Hybride module-systeem (in-process + event-journal)

- **Status:** Aanvaard
- **Datum:** 2026-07-19
- **Context-term:** module (praatMaar-module), dicteercyclus-event, event-journal —
  zie [CONTEXT.md](../../CONTEXT.md)
- **Feature-spec:** [2026-07-19-modules-design.md](../superpowers/specs/2026-07-19-modules-design.md)

## Context

praatMaar levert geslaagde dicteersessies af als transcriptbestanden. Er is
behoefte aan uitbreidbaarheid: ingebouwde extra’s (aan/uit) én externe tools
die op opgeslagen tekst kunnen reageren zonder de app te kennen.

Bestaande features (bestemmingen, herstel-audio) volgen al informeel het patroon
van geïnjecteerde callbacks in `Opnamesessie`, maar er is geen gedeeld contract,
geen lifecycle-identiteit per sessie, en geen externe API.

Drie richtingen lagen open:

- **A — Alleen in-process:** Python-modules via registry; geen stabiele externe
  interface.
- **B — Alleen out-of-process:** bestandswatcher op transcriptmap; geen
  first-class modules in de app.
- **C — Hybride:** in-process modules én hetzelfde event-contract op schijf
  (JSONL-journal).

## Beslissing

We kiezen **optie C — hybride vanaf dag één**:

- **`ModuleBus`** verdeelt **`CycleEvent`**-payloads naar enabled in-process
  modules (`PraatMaarModule`-Protocol in `modules/`).
- **`EventJournal`** schrijft **elk** event append-only naar
  `%APPDATA%\praatMaar\events\events.jsonl` (macOS: Application Support) —
  onafhankelijk van welke modules aan staan. Dat journal is de externe API.
- Elke dicteercyclus krijgt een **`session_id`** (UUID); events worden
  geëmit vanuit `Opnamesessie` via `emit_event`, plus herstel-transcriptie in
  `dictation.py` (`source: "recovery"`).
- **v1:** expliciete ingebouwde registry (geen plugin-download, geen
  `entry_points`). Eerste module: inbox-spiegel. UI: tray **Modules**.
- **Incrementele transcriptie** (optioneel): `transcript.partial` tijdens
  opname; finaal transcript blijft autoritatief.

Gedetailleerd gedrag, event-types, config en UI staan in de feature-spec
(hierboven gelinkt), niet in deze ADR.

### Bewust buiten deze ADR

- Migratie van bestemmingen/herstel naar modules — latere refactor.
- Third-party module-installatie — later bovenop hetzelfde contract.
Zie [docs/modules-integration.md](../modules-integration.md) (extern) en
[docs/modules-authoring.md](../modules-authoring.md) (ingebouwd via PR).
- Modules die transcript wijzigen vóór opslaan — geen hook in v1.

## Alternatieven overwogen

- **Alleen in-process (A).** Verworpen: externe tools zouden praatMaar-internals
  of ad-hoc mappen moeten reverse-engineeren; geen stabiel contract.
- **Alleen out-of-process (B).** Verworpen: geen module-overzicht in de app,
  geen gedeelde lifecycle-hooks voor ingebouwde uitbreidingen; slechtere
  testbaarheid.
- **Event-bus zonder journal.** Verworpen: breekt de hybride belofte; externe
  integratie vereist dan alsnog een apart kanaal.

## Gevolgen

- Nieuw package `modules/` (`_contract`, `bus`, `journal`, `registry`).
- `Opnamesessie` krijgt `emit_event` en optioneel `incremental_transcription`;
  dicteercyclus blijft leidend, hotkey-routing ongewijzigd in `dictation.py`.
- Journal bevat transcripttekst — behandel als gevoelige data (privacy).
- Fout in een module mag dicteren nooit breken (`ModuleBus`: try/except per
  module).
- ADR-0001 (`host`) en ADR-0002 (indicator) blijven ongewijzigd; modules zijn
  een feature-seam naast de platform-seam, niet erin.

## Aanvulling (2026-08-01) — journal zonder transcripttekst

Sinds 0.3.0 schrijft `EventJournal` **geen** volledige transcripttekst meer naar
`events.jsonl`. Velden als `transcript` worden omgezet naar
`transcript_chars` (lengte). Gevolgregel hierboven over “journal bevat
transcripttekst” is **verouderd**; behandel nog wel `transcripts/`, `inbox/`,
`recovery/` en meetingjournals als gevoelige data. Zie CHANGELOG 0.3.0 en
[v1.0-scope](../superpowers/specs/2026-08-01-v1-support-scope-product.md).

## Aanvulling (2026-08-18) — `source: "file"` en journal zonder bronpad

Bestandstranscriptie (module `file-transcription`) is een **derde emitter** van
het bestaande `CycleEvent`-contract, geen tweede bus en geen nieuwe ADR.

- **`source`:** `"live"` \| `"recovery"` \| `"file"`. `schema_version` blijft `1`.
- **Emitters:** `Opnamesessie` (live), herstel-pad (`source: "recovery"`),
  file-job worker via geïnjecteerde `emit` (`source: "file"`). `Opnamesessie`
  komt **niet** op `ModuleContext`.
- **`session_id`:** één UUID per file-job (niet per batch).
- **Velden:** `path` blijft het opgeslagen `.txt` (op `transcript.saved`).
  `recovery_path` blijft herstel-audio. File-jobs gebruiken optioneel
  in-memory `audio_path` (bron-WAV) voor UI/modules; ze zetten **geen**
  `recovery_path`. Geen nieuw `CycleEventType`.
- **Journal:** naast het strippen van `transcript` → `transcript_chars` stript
  `EventJournal` ook `audio_path`. Bronpad en bronnaam van user-files horen
  **niet** in `events.jsonl` (append-only, geen retentie). `error` in het
  journal is generiek/i18n, geen exception-tekst met paden.
- **Lock:** file-jobs gebruiken `try_locked_model`, nooit `dictation_priority`.

Feature-spec:
[2026-08-18-file-transcription-product.md](../superpowers/specs/2026-08-18-file-transcription-product.md).

## Implementatiestatus (2026-07-19)

Geïmplementeerd op branch `feat/modules`; merge via PR naar `main` volgt.
