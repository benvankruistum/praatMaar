# Design — modules (hybride) + event-journal + incrementele transcriptie

- **Datum:** 2026-07-19
- **Status:** Goedgekeurd (chat); geïmplementeerd op branch `feat/modules`
- **Architectuur:** [ADR-0003](../../adr/0003-hybrid-module-system.md)

## Doel

praatMaar uitbreidbaar maken met **modules** — extra functionaliteit die je aan-
of uitzet, zonder de kern (opnemen → transcriberen → opslaan/plakken) te breken.

Tegelijk een **hybride brug** voor externe tools: dezelfde lifecycle-momenten als
JSON-regels op schijf, zodat andere programma's op opgeslagen transcripts kunnen
reageren zonder praatMaar te kennen.

Drie stappen in één traject (v1):

1. **Module-infrastructuur** — bus, registry, journal, UI aan/uit
2. **Eerste echte module** — inbox-spiegel
3. **Incrementele transcriptie** — partial events tijdens opname

## Architectuurkeuze: hybride vanaf dag één

| Kanaal | Wie | Hoe |
|--------|-----|-----|
| **In-process** | Ingewikkelde modules in de app | `PraatMaarModule`-Protocol + `ModuleBus` |
| **Out-of-process** | Scripts, andere apps | Append-only **event-journal** (JSONL) |

Beide kanalen krijgen **dezelfde** `CycleEvent`-payload. Externe tools lezen alleen
het journal; geen apart download-/plugin-mechanisme in v1.

```
Opnamesessie (dicteercyclus)
        │
        ▼
   ModuleBus ──► enabled in-process modules
        │
        ▼
   EventJournal ──► %APPDATA%\praatMaar\events\events.jsonl
                           │
                           ▼
                    externe tool / script
```

## Event-contract (`CycleEvent`)

Elke **dicteercyclus** (of herstel-transcriptie) krijgt een uniek `session_id`
(UUID). Timestamps in ISO 8601 UTC. `schema_version: 1` op elk event.

### Types (v1)

| Type | Wanneer |
|------|---------|
| `cycle.started` | Opname begint |
| `cycle.cancelled` | Geannuleerd (Shift+Esc) |
| `cycle.transcribing` | Whisper start (na stop) |
| `transcript.partial` | Tussentijdse tekst (incrementele modus) |
| `cycle.completed` | Transcriptie geslaagd (finaal transcript) |
| `transcript.saved` | Bestand weggeschreven |
| `cycle.error` | Transcriptie mislukt |
| `cycle.idle` | Terug naar idle |
| `destination.command` | Stemwissel/reset (geen normale cyclus) |
| `recovery.retranscribed` | Herstel-WAV opnieuw getranscribeerd |

### Regels

- `transcript.saved` komt **na** `cycle.completed` (externe tools kunnen op pad wachten).
- Bestemmings-commando's (`destination.command`) zijn **geen** `cycle.completed`.
- Herstel-pad gebruikt `source: "recovery"`; live dicteren `source: "live"`.
- Optionele velden: `transcript`, `path`, `destination`, `language`, `mode`, `error`,
  `recovery_path`, `destination_command`, `destination_name`.

Implementatie: `modules/_contract.py`. Emissie via `emit_event` in `Opnamesessie`
en herstel-pad in `dictation.retranscribe_recovery_wav`.

## In-process modules

### Interface (`PraatMaarModule`)

- `id` — stabiele sleutel (bijv. `inbox-mirror`)
- `display_name_key` / `description_key` — i18n
- `default_enabled()` — default bij ontbrekende config
- `on_app_start(ctx)` — eenmalig bij laden (read-only `ModuleContext`)
- `on_event(event)` — reactie op elk `CycleEvent`

### Registry & bus

- **Registry** (`modules/registry.py`): expliciete lijst ingebouwde modules (v1:
  geen dynamic loading, geen `entry_points`).
- **ModuleBus** (`modules/bus.py`): schrijft **altijd** naar journal; roept enabled
  modules aan in try/except — kapotte module mag dicteren nooit breken.
- **EventJournal** (`modules/journal.py`): `%APPDATA%\praatMaar\events\events.jsonl`.

### Eerste module: inbox-spiegel (`inbox-mirror`)

- Reageert op `transcript.saved`.
- Kopieert bestand naar `%APPDATA%\praatMaar\inbox\`.
- Default **ingeschakeld**; uitzetten via tray **Modules**.

## Aansluiting in de dicteercyclus

Events komen uit **strategische punten in `Opnamesessie`**, niet uit hotkey-routing:

- `start()` → `cycle.started`; start incrementele worker indien aan
- `cancel()` → `cycle.cancelled` → `cycle.idle`
- `stop_and_transcribe()` → `cycle.transcribing` → …
- `_transcribe_audio()` → `cycle.completed`, `transcript.saved`, `destination.command`,
  `cycle.error`, `cycle.idle`

Wiring in `dictation._build_session()`: `emit_event=module_bus.emit`.

Bestaande features (**bestemmingen**, **herstel-audio**) blijven in v1 **ongemigreerd**
naar modules; wel dezelfde events waar relevant.

## Incrementele transcriptie

Optie `incremental_transcription` (default uit).

- Tijdens opname: achtergrondthread transcribeert periodiek (~3 s) een kopie van
  geaccumuleerde audio (min. ~1,5 s).
- Emits `transcript.partial` met groeiende tekst.
- Bij stop: **finaal** transcript blijft autoritatief (`cycle.completed` + save).
- Model-toegang via lock (incrementeel + finaal delen één Whisper-model).

Zware feature — bedoeld voor modules/externe tools die tussentijdse tekst nodig
hebben; niet vereist voor basis journal-gebruik.

## Config

```json
{
  "incremental_transcription": false,
  "modules": {
    "inbox-mirror": { "enabled": true }
  }
}
```

- Ontbrekende `modules.<id>` → `default_enabled()` van die module.
- Geen module-specifieke settings in v1 (YAGNI).

## UI / tray

- **Tray-menu:** **Instellingen** | **Bestemmingen** | **Modules** | **Help** | Afsluiten.
- **Modules-dialoog** (`modules_dialog.py`), precedent Bestemmingen:
  - checkbox incrementele transcriptie;
  - lijst ingebouwde modules met aan/uit;
  - geen per-module settings in v1.
- macOS: subprocess via `settings_process.py` (`--praatmaar-modules-ui`), zelfde
  patroon als Bestemmingen/Instellingen.
- i18n nl/en/de; Help-sectie in `docs/user/help.*.md`.

## Datamappen (app-dir)

| Pad | Doel |
|-----|------|
| `events/events.jsonl` | Event-journal (altijd) |
| `inbox/` | Kopieën via inbox-spiegel module |
| `transcripts/` | Bestaand — ongewijzigd |
| `recovery/` | Bestaand — herstel emitteert events met `source: "recovery"` |

Journal bevat transcripttekst — behandel als gevoelige data (zie README privacy).

## Buiten scope (v1)

- Modules downloaden/installeren (`entry_points`, plugin-store)
- Bestemmingen/herstel migreren naar module-architectuur
- Modules die transcript **wijzigen** vóór opslaan (transform-hook)
- Webhook/HTTP-bridge (kan bovenop journal later)
- Async thread pool voor modules (alleen indien performance het vraagt)

## Teststrategie

- Contract: event-volgorde en payload (`tests/test_modules_contract.py`)
- Bus: enabled/disabled, fout in module blokkeert flow niet (`test_modules_bus.py`)
- Inbox-spiegel: kopie bij `transcript.saved`
- Opnamesessie: succesvolle cyclus emitteert verwachte event-keten

## Vervolg (niet v1)

- `entry_points` voor third-party Python-modules in registry
- Meer ingebouwde modules (webhook, formatter, …)
- Event-schema documentatie voor externe ontwikkelaars — zie [docs/modules-integration.md](../../modules-integration.md)
- ADR indien plugin-loading een architecturele beslissing wordt

Ingebouwde modules: [docs/modules-authoring.md](../../modules-authoring.md).

## Risico's

- **Incrementele modus:** extra CPU/GPU-last tijdens opname; lock kan finaal
  transcriptie kort vertragen.
- **Journal-grootte:** append-only zonder prune — externe tools of latere versie
  moeten rotatie overwegen.
- **Partial vs finaal:** consumers moeten finaal (`transcript.saved`) als waarheid
  zien; partial is indicatief.
