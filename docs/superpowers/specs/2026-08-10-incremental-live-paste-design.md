# Design: live-plak bij incrementele transcriptie

Datum: 2026-08-10  
Status: approved (brainstorm)  
Bouwt voort op: [chunk-transcriptie-pipeline](2026-08-01-chunk-transcription-pipeline-design.md)  
Platform-advies: Windows / macOS / Linux agents — unaniem **klembord + plaktoets** voor v1.

## Probleem

De dicteercyclus levert tekst pas **aan het eind** (opslaan → klembord → één
`host.paste()`). Gebruikers willen tijdens het spreken al tekst in het **actieve
invoerveld** zien verschijnen. Echte word-streaming met Faster-Whisper is niet
realistisch; chunk-delta’s (seconden later) wel — de chunk-pipeline bestaat al,
maar plakt nog niet live.

## Doel

Optionele **live-plak** onder de module Incrementele transcriptie: bij elke
afgeronde chunk alleen de *nieuwe* tekst via klembord + Ctrl/Cmd+V in het
gefocuste veld; bij stop de staart-delta. Duidelijke UX dat dit via het klembord
loopt, met keuze om het klembord na afloop te herstellen.

## Non-goals (v1)

- Tekens typen (SendInput / CGEvent) of hybride injectie
- UI Automation / AX `insertText` als primair pad
- Partials tonen in de pill
- Wayland-parity of “werkt overal”-belofte op Linux
- Bestemmings-spraakcommando’s tijdens live-plak
- Cloud / ander STT-model voor echte streaming

## Beslissingen

| Onderwerp | Keuze |
|-----------|--------|
| Plaats | Optie in Modules → Incrementele transcriptie (vereist module aan) |
| Injectie | Klembord + bestaande `host.paste()` (platform-agents unaniem) |
| Relatie `auto_paste` | **Onafhankelijk** — live-plak en auto_paste zijn los |
| Bij stop (live aan) | Altijd **staart-delta** plakken; `auto_paste` negeren voor chunk- én staart-inserts |
| Bestemmingscommando’s | **Uit** zolang live-plak aan (wisselen via tray/UI) |
| Default live-plak | **Uit** |
| Klembord herstellen | Snapshot bij start, restore bij einde; **default aan**; gebruiker kan uitzetten |
| Productkeuze cross-platform | Eén toggle; implementatie mag per `host` verschillen |
| Linux | Best-effort X11; Wayland niet beloven; default uit |

## Config

| Key | Type | Default | Betekenis |
|-----|------|---------|-----------|
| `incremental_live_paste` | bool | `false` | Live chunk/staart-plak via klembord |
| `incremental_live_paste_restore_clipboard` | bool | `true` | Na sessie klembord best-effort terugzetten |

Alleen van toepassing als `incremental_transcription` aan staat. UI toont de
live-plak-opties genest / disabled als de module uit staat.

## Runtime

### Voorwaarden

- `incremental_transcription` én `incremental_live_paste` aan.
- Focus blijft in het doelveld (pill no-activate, ADR-0002).
- Inserts serialiseren (geen overlappende copy+paste).
- Modifier-clear vóór **elke** paste (chunk én staart), niet alleen bij stop.

### Tijdens opname

1. Chunk-pipeline commit een tekststuk (bestaand).
2. Bepaal **delta** = nieuw stuk t.o.v. wat al live geplakt is (lege delta → geen paste).
3. Zet alleen de delta op het klembord → wacht modifiers → `paste_delay` → `host.paste()`.
4. Geen bestemmings-match op chunk- of tussentekst.

### Bij start (eerste live-sessie insert of sessie-start)

- Als restore aan: snapshot van het algemene klembord (platform best-effort).

### Bij stop

1. Staart via bestaande chunk-stop-logica; plak **staart-delta** (ook als
   `auto_paste` uit).
2. Sla transcript op / emit events zoals nu (`transcript.saved`, enz.).
3. Geen tweede volle-buffer-Whisper (ongewijzigd t.o.v. chunk-pipeline).
4. Als restore aan: klembord terugzetten; waar mogelijk `changeCount` /
   equivalent respecteren (niet overschrijven als de gebruiker intussen iets
   anders kopieerde).
5. Geen klassieke “plak hele transcript”-stap wanneer live-plak aan stond
   (voorkomt dubbele tekst in het veld).

### Als live-plak uit

Ongewijzigd: chunk-pipeline voor snellere eindtijd/events; delivery via
`resolve_auto_paste` + één eind-plak zoals nu; bestemmingscommando’s actief.

## UI & copy

Modules-dialoog, in het incremental-blok (alleen zinvol als incremental aan):

- Checkbox **Live plakken** (of i18n-equivalent nl/en/de).
- Korte hint: tekst gaat **via het klembord** naar het actieve veld; tijdens
  dicteren wordt het klembord tijdelijk overschreven.
- Nested checkbox **Klembord na afloop herstellen** (default aan).
- Help nl/en/de: zelfde boodschap + bekende limieten (focus, UIPI/elevated,
  wachtwoordvelden, Linux X11 best-effort).

Geen aparte gebruikerskeuze “plak vs typ”.

## `host`-seam

- **v1 minimaal:** core blijft `copy_text(delta)` + modifier-wait + `host.paste()`.
- Optioneel (niet blocker): generieke `insert_text(delta)` achter de seam waarvan
  de v1-impl = clipboard set + paste (toekomstige backends zonder UI-keuze).
- Geen `type_text` in v1.
- Clipboard snapshot/restore: bij voorkeur achter host-helper of duidelijke
  platform-adapters; geen OS-API’s in `dictation.py`.

## Ownership

| Gebied | Owner | Consult |
|--------|-------|---------|
| Opnamesessie-wiring, delta-boekhouding, auto_paste-interactie | `core-python-architect` | `audio-speech` |
| Modules-UI + i18n/help | `core-python-architect` + `/update-documentation` | `ux-product-design` |
| `host` paste / clipboard restore Windows | `windows-platform` | `privacy-security` |
| idem macOS | `macos-platform` | `privacy-security` |
| idem Linux (best-effort) | `linux-platform` (advies) / implementatie dun | — |

## Privacy / security

- Zelfde klasse als huidige auto-paste: transcript-delta’s op het klembord.
- Geen omzeiling van wachtwoordvelden of UIPI.
- Documenteren in help/SECURITY waar relevant.
- Restore verkleint klembord-lek ná de sessie; tijdens de sessie blijft overschrijven.

## Tests / verificatie

**Automatisch**
- FakeHost: volgorde van copy+paste voor chunk-delta’s + staart; geen full-transcript-paste bij live aan.
- Live aan + `auto_paste` uit → toch chunk/staart-pastes.
- Live aan → geen `destination.command`-pad op transcript.
- Restore aan/uit: snapshot/restore hooks aangeroepen of overgeslagen.
- Lege delta → geen paste.

**Handmatig**
- Windows: Notepad, browser contenteditable, één Electron-app; elevated Notepad (verwacht falen); hotkey met modifiers.
- macOS: TextEdit + Accessibility aan; clipboard restore na sessie.
- Linux (optioneel): X11 met xdotool/xclip; Wayland niet als pass-criterium.

## Failure modes

| Failure | Mitigatie |
|---------|-----------|
| Focus niet in doelveld | Documenteren; geen focus stelen |
| Modifiers nog down | Modifier-clear per insert |
| Gebruiker kopieert tijdens sessie | Serialize; restore met changeCount-guard |
| Elevated / UIPI / geen paste-tools (Linux) | Fail visible waar mogelijk; transcript blijft opgeslagen |
| Dubbele tekst bij stop | Geen full re-paste als live aan was |

## Acceptance criteria

1. Met incremental + live-plak aan verschijnen chunk-delta’s in het actieve veld tijdens opname (klembord+plak).
2. Bij stop verschijnt de staart-delta; het veld bevat geen gedupliceerde volle transcript-plak.
3. `auto_paste` uit + live aan → toch live inserts; opslaan blijft werken.
4. Live aan → bestemmings-spraakcommando’s doen niets; UI-wisselen blijft werken.
5. Default: live uit; restore-optie default aan en uitzetbaar; copy vermeldt klembord-gebruik.
6. Restore aan → na sessie best-effort vorige klembordinhoud terug (waar platform het toelaat).
7. Incremental uit of live uit → gedrag gelijk aan huidige chunk-/eind-delivery.

## Open voor implementatieplan (niet blocker voor deze spec)

- Exacte i18n-strings en Modules-layout (checkbox nesting).
- Of snapshot bij `cycle.started` of vlak vóór eerste paste.
- Of `insert_text` op de Host-Protocol in dezelfde slice komt of later.
