# Product specification — Microfoon lazy rebind (dicteercyclus)

## Status

**Accepted** — 2026-08-08 (grill + platform overleg 2026-08-03; go voor implementatie)

### Open questions (resolved for v1)

- **Identity-tuple:** PortAudio `(name, hostapi)` — geen WASAPI endpoint-id in core
  (ADR 0006).
- **Settings-dropdown herenumereren bij openen:** out of scope (niet blokkerend).

## Context

praatMaar houdt op Windows optioneel een **warme** microfoonstream open
(`warm_microphone`). PortAudio/WASAPI bindt een endpoint bij open. Als de
gebruiker later een Bluetooth-headset verbindt terwijl de app al draait, blijft
die stream vaak op het oude apparaat (of stilte) hangen. De volgende
**dicteercyclus** lijkt te werken, maar Whisper/VAD ziet geen spraak.

Platformadvies (product-owner + windows-/macos-/linux-platform): geen OS
device-watcher in deze slice; lazy rebind volstaat voor het happy path.

Gerelateerd:

- [2026-07-18-warm-microphone-design.md](2026-07-18-warm-microphone-design.md)
- ADR (voorstel): [0006 — Microfoon lazy rebind](../../adr/0006-mic-lazy-rebind.md)
- `opnamesessie.py` (`_ensure_stream`, `_resolve_input_device`, `refresh_input_device`)

## Problem

**User:** Windows-dicteergebruiker met headset/Bluetooth.  
**Situation:** praatMaar draait al; gebruiker verbindt of activeert een headset.  
**Problem:** De volgende opname (Shift+Esc) levert stilte of het verkeerde
apparaat; app-herstart is nu de betrouwbare workaround.  
**Impact:** Mislukte cyclus, wantrouwen in de tool, vooral met warme mic.  
**Desired outcome:** Eerste dicteercyclus na headset-connect pakt de juiste
OS-standaard (of handmatig gekozen) mic zonder herstart.

## Goal

Bij **start van de dicteercyclus** en bij **Instellingen opslaan** de microfoon
opnieuw resolven; warme stream alleen heropenen als de device-**identiteit**
sinds de vorige open is gewijzigd. Happy path = OS-standaardmicrofoon.
Handmatige switch in Instellingen blijft werken zonder app-herstart.

## Non-goals

- OS/WASAPI/Core Audio device-change watcher (later epic, Windows-first, achter
  `host`-seam)
- Meeting Buddy mid-meeting reconnect / loopback-starvation
- Stream bij élke start altijd forceren-heropenen (warm mic zinloos maken)
- Linux-parity als v1-gate
- Nieuwe instellingen naast bestaande mic-keuze / warme mic
- Mid-opname hot-swap van het inputapparaat

## Users and scenarios

1. **Headset na start:** App idle → BT-headset verbindt → Windows-standaard wordt
   headset (of blijft standaard) → Shift+Esc → audio van de juiste mic.
2. **Handmatig switchen:** App draait → Instellingen → kies BT-opnameapparaat →
   Opslaan → volgende dicteercyclus gebruikt dat apparaat.
3. **Vast apparaat weg:** Gekozen mic verdwijnt → preference cleared →
   OS-standaard; volgende start werkt op default.

## Functional requirements

- **FR-01** Met `microphone_device` = OS-standaard (`None`): bij start van de
  dicteercyclus resolvet `Opnamesessie` de PortAudio-default **op dat moment**
  (na veilige herenumeratie), niet “wat default was bij warm-open”.
- **FR-02** Als een warme stream open is, heropent `Opnamesessie` die alleen als
  de device-identiteit (duurzame id / friendly name + rol; niet alleen raw index)
  sinds vorige open **verschilt**.
- **FR-03** Bij Opslaan in Instellingen met gewijzigde mic-keuze: stream sluiten
  en preference toepassen zodat de volgende (of meteen volgende) open de nieuwe
  keuze gebruikt — zonder app-herstart.
- **FR-04** Als een vastgezette mic-index/naam niet meer geldig is: preference
  clearen naar OS-standaard en daarop openen (bestaand clear-gedrag versterken /
  consistent maken).
- **FR-05** `refresh_portaudio` blijft achterwege terwijl externe streams open
  zijn (o.a. Meeting Buddy) — zelfde veiligheidsregel als nu.
- **FR-06** macOS: geen warm-stream-pad; cold open bij start blijft voldoende;
  FR-03/FR-04 gelden wel voor preference clear / Settings.

## Quality requirements

- **QR-01** Geen focus-steal; herbinden gebeurt in bestaande start-/save-paden.
- **QR-02** Privacy: geen nieuwe netwerk- of cloud-API; alleen lokale device-lijst.
- **QR-03** Warm-mic start mag niet systematisch 0,5–2 s trager worden wanneer
  de identity **niet** wijzigde.
- **QR-04** Windows is primaire acceptatie; macOS regressie-smoke; Linux
  best-effort / geen gate.

## Supported platforms

| Platform | Scope |
|----------|--------|
| Windows 10/11 | Primair (warme mic + BT) |
| macOS | Preference clear + Settings; geen warm-rebind-logica nodig |
| Linux | Experimenteel; geen aparte AC |

## Edge cases

- Zelfde index+naam maar stille/verkeerde endpoint → kan nog een mislukte cyclus
  kosten; geen watcher in deze slice (bekend risico).
- BT Hands-Free vs Stereo: niet automatisch HFP pinnen als “default”.
- Meeting Buddy actief: PortAudio global refresh overslaan; dicteer-belofte geldt
  voor dicteercyclus, niet alle capture-paden tegelijk.

## Privacy considerations

Ongewijzigd local-first. Geen device-notification-API in v1 → geen extra
privacy-review voor watchers.

## Dependencies

- Bestaande Instellingen mic-dropdown + `warm_microphone`
- `mic_errors.refresh_portaudio` / `_refresh_portaudio_if_safe`
- ADR 0006 (rebind-beleid)

## Risks

| Risico | Mitigatie |
|--------|-----------|
| Identity-check mist stille zombie | Documenteren; later watcher-epic bij bewijs |
| MB + dicteren tegelijk | FR-05; geen claim op alle streams |
| Gebruiker verwacht idle auto-switch | Copy/help: herbindt bij start/opslaan |

## Acceptance criteria

1. **Given** praatMaar draait (warm mic aan of uit), **When** gebruiker verbindt
   een headset die Windows-default wordt en start dicteren, **Then** de opname
   bevat bruikbare mic-audio (geen volledig VAD-lege stilte door stale stream).
2. **Given** warme stream op oud apparaat, **When** default-identity ongewijzigd,
   **Then** start heropent de stream niet onnodig (warm blijft warm).
3. **Given** warme stream, **When** default-identity wel wijzigde, **Then**
   stream wordt gesloten en opnieuw geopend op de nieuwe default vóór opname.
4. **Given** gebruiker kiest een andere mic in Instellingen en slaat op,
   **When** volgende dicteercyclus start, **Then** die mic wordt gebruikt zonder
   app-herstart.
5. **Given** vastgezette mic is verdwenen, **When** start of resolve faalt op
   die preference, **Then** preference = OS-standaard en open slaagt op default
   (of toont bestaand mic-foutpad als er géén input is).

## Required evidence

- Unit tests: identity unchanged → geen reopen; identity changed → reopen;
  pinned gone → clear to default
- Handmatige Windows-smoke: BT connect terwijl app draait → Shift+Esc
- macOS smoke (optioneel): Settings mic change + cold start

## Agent ownership

| Rol | Agent |
|-----|--------|
| Responsible implementatie | `core-python-architect` |
| Consult | `audio-speech`, `windows-platform`; `macos-platform` (FR-06) |
| Spec / acceptatie | `product-owner` |
| Review vóór merge | `/code-review`; privacy alleen als watcher later landt |
