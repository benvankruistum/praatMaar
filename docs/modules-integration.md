# Module-integratie (extern)

Handleiding voor **externe tools** die praatMaar willen volgen zonder code in de
app te wijzigen. Architectuur: [ADR-0003](adr/0003-hybrid-module-system.md).
Volledige feature-spec: [2026-07-19-modules-design.md](superpowers/specs/2026-07-19-modules-design.md).

## Overzicht

praatMaar schrijft elke dicteercyclus weg als **JSON Lines** (één JSON-object per
regel). In-process modules krijgen dezelfde payload; jouw script leest alleen het
bestand.

```
Opname → transcriptie → opslaan
              │
              ▼
   events/events.jsonl   ← jij leest dit
              │
              ▼
   optioneel: inbox/     ← kopie via inbox-spiegel module (indien aan)
```

**v1:** geen plugin-installatie, geen HTTP-webhook. Alleen het journal (+ optioneel
de inbox-map).

## Datamappen

| Platform | App-datamap |
|----------|-------------|
| Windows | `%APPDATA%\praatMaar\` |
| macOS | `~/Library/Application Support/praatMaar/` |

| Pad (onder app-datamap) | Inhoud |
|-------------------------|--------|
| `events/events.jsonl` | Append-only event-log (altijd) |
| `inbox/` | Kopieën van opgeslagen transcripts (module aan) |
| `transcripts/` | Default transcriptmap (retentie) |
| `config.json` | User settings (modules aan/uit) |

Het journal kan **transcripttekst** bevatten — behandel als gevoelige data.

## Schema

Elke regel is één JSON-object:

| Veld | Type | Altijd | Betekenis |
|------|------|--------|-----------|
| `schema_version` | int | ja | Nu `1`; bij breaking changes omhoog |
| `type` | string | ja | Event-type (zie hieronder) |
| `session_id` | string | ja | UUID van één dicteercyclus |
| `timestamp` | string | ja | ISO 8601 UTC |
| `source` | string | ja | `"live"` of `"recovery"` |
| `transcript` | string | soms | Tekst (partial of finaal) |
| `path` | string | soms | Absoluut pad naar `.txt` op schijf |
| `destination` | string \| null | soms | Actieve bestemmingsnaam |
| `language` | string | soms | Whisper-taal (`nl`, `en`, …) |
| `mode` | string | soms | `toggle` of `ptt` |
| `error` | string | soms | Foutmelding |
| `recovery_path` | string | soms | Recovery-WAV bij herstel-flow |
| `destination_command` | string | soms | `set` of `reset` |
| `destination_name` | string | soms | Bestemmingsnaam bij `set` |

Canonical types staan in `modules/_contract.py` (`CycleEventType`).

## Event-types

| `type` | Wanneer |
|--------|---------|
| `cycle.started` | Opname begint |
| `cycle.cancelled` | Geannuleerd (bijv. bij afsluiten tijdens opname) |
| `cycle.transcribing` | Whisper start na stop |
| `transcript.partial` | Tussentijdse tekst (incrementele modus aan) |
| `cycle.completed` | Finaal transcript klaar |
| `transcript.saved` | Bestand weggeschreven |
| `cycle.error` | Transcriptie mislukt |
| `cycle.idle` | Cyclus afgerond, app weer idle |
| `destination.command` | Stemwissel bestemming (geen normale save) |
| `recovery.retranscribed` | Herstel-WAV opnieuw getranscribeerd |

## Typische volgorde (live dicteren)

Succesvolle cyclus:

```
cycle.started
cycle.transcribing
cycle.completed
transcript.saved
cycle.idle
```

Met incrementele transcriptie (optioneel, instelling **Modules**):

```
cycle.started
transcript.partial      ← kan meerdere keren
transcript.partial
cycle.transcribing
cycle.completed
transcript.saved
cycle.idle
```

Geannuleerd:

```
cycle.started
cycle.cancelled
cycle.idle
```

Bestemmingscommando (geen `cycle.completed` / `transcript.saved`):

```
cycle.started
cycle.transcribing
destination.command
cycle.idle
```

**Regel:** behandel `transcript.saved` als autoritatief eindpunt voor “bestand
staat klaar”. Met incrementele transcriptie is dat vaak de laatste
`transcript.partial` (zonder extra Whisper bij stop); tussentijdse partials
vóór stop blijven indicatief.

## JSON-voorbeelden

### `transcript.saved` (meest gebruikt voor integraties)

```json
{
  "schema_version": 1,
  "type": "transcript.saved",
  "session_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "timestamp": "2026-07-19T14:30:05.123456+00:00",
  "source": "live",
  "transcript": "Dit is de getranscribeerde tekst.",
  "path": "C:\\Users\\jan\\AppData\\Roaming\\praatMaar\\transcripts\\2026-07-19_143005.txt",
  "destination": null,
  "language": "nl",
  "mode": "toggle"
}
```

### `transcript.partial`

```json
{
  "schema_version": 1,
  "type": "transcript.partial",
  "session_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "timestamp": "2026-07-19T14:30:02.000000+00:00",
  "source": "live",
  "transcript": "Dit is de getrans",
  "language": "nl",
  "mode": "toggle"
}
```

### `cycle.error`

```json
{
  "schema_version": 1,
  "type": "cycle.error",
  "session_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "timestamp": "2026-07-19T14:30:08.000000+00:00",
  "source": "live",
  "error": "RuntimeError: …",
  "recovery_path": "C:\\Users\\jan\\AppData\\Roaming\\praatMaar\\recovery\\2026-07-19_143008.wav",
  "language": "nl",
  "mode": "toggle"
}
```

## Minimale integratie (Python)

Tail het journal en reageer op opgeslagen transcripts:

```python
import json
from pathlib import Path

journal = Path.home() / "AppData/Roaming/praatMaar/events/events.jsonl"
# macOS: Path.home() / "Library/Application Support/praatMaar/events/events.jsonl"

with journal.open(encoding="utf-8") as f:
    f.seek(0, 2)  # einde — productie: gebruik watchdog of periodieke poll
    while True:
        line = f.readline()
        if not line:
            continue
        event = json.loads(line)
        if event.get("type") != "transcript.saved":
            continue
        path = event.get("path")
        if path:
            text = Path(path).read_text(encoding="utf-8")
            # … jouw verwerking …
```

Alternatief zonder journal: volg `%APPDATA%\praatMaar\inbox\` als de
inbox-spiegel-module aan staat (vaste drop zone).

## Compatibiliteit

- **`schema_version`:** check op `1`. Bij hogere versies: lees release notes /
  ADR voordat je parsed.
- **Append-only:** praatMaar roteert het journal niet automatisch in v1; plan
  zelf rotatie/archief als het bestand groot wordt.
- **Geen garantie op partials:** alleen als de gebruiker incrementele
  transcriptie heeft ingeschakeld.

## Niet ondersteund in v1

- Modules installeren zonder praatMaar-build aan te passen
- Events muteren of acknowledgements terug naar de app
- Webhooks / HTTP

Zie [docs/modules-authoring.md](../modules-authoring.md) als je een **ingebouwde**
Python-module via PR wilt toevoegen.
