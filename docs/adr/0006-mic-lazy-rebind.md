# 0006 — Microfoon lazy rebind (geen OS device-watcher in v1)

- **Status:** Aanvaard
- **Datum:** 2026-08-03
- **Aanvaard:** 2026-08-08
- **Context-term:** Opnamesessie / dicteercyclus — zie [CONTEXT.md](../../CONTEXT.md)
- **Feature-spec:**
  [2026-08-03-mic-lazy-rebind-product.md](../superpowers/specs/2026-08-03-mic-lazy-rebind-product.md)
- **Gerelateerd:**
  [2026-07-18-warm-microphone-design.md](../superpowers/specs/2026-07-18-warm-microphone-design.md),
  [0001 — platform-seam](0001-platform-seam.md)

## Context

Op Windows houdt `Opnamesessie` optioneel een warme `sounddevice.InputStream`
open. PortAudio (WASAPI) pinnt het capture-endpoint bij `open`. Verbindt de
gebruiker daarna een Bluetooth-headset terwijl praatMaar al draait, dan kan de
warme stream “alive” blijven op het oude (of stille) endpoint. De volgende
dicteercyclus start wel, maar levert stilte.

Er is al zombie-detectie (`active` / ontbrekende callbacks) en preference-clear
bij ongeldige index. Dat vangt **niet** het pad “callbacks lopen, verkeerd
endpoint” noch “Windows-default is gewisseld terwijl `device=None`-stream open
blijft”.

Platformoverleg (windows / macos / linux + product-owner): een live
OS-watcher (`IMMNotificationClient`, Core Audio listeners, PipeWire subscribe)
is haalbaar later, maar niet nodig om het happy path te sluiten; en hoort niet
in `Opnamesessie` zonder `host`-Protocol.

## Beslissing

1. **Geen OS device-change watcher** in deze slice (en geen nieuwe `Host`-API
   voor device-events). Eventuele watcher is een **later epic**, Windows-first,
   alleen signalen via `host/_win.py`; stream open/close en
   `refresh_portaudio` blijven in `Opnamesessie` / `mic_errors`.
2. **Herbindmomenten:** start van de dicteercyclus én toepassen van Instellingen
   (mic-wijziging / opslaan dat de stream moet vernieuwen).
3. **Warme stream:** heropenen alleen als de **device-identiteit** sinds vorige
   succesvolle open is gewijzigd. Identiteit = PortAudio
   `(friendly name, hostapi)` — **niet** alleen de ruwe PortAudio-index; geen
   WASAPI endpoint-id in core (houdt de `host`-seam schoon).
4. **Happy path:** `microphone_device is None` betekent “open de OS-/PortAudio-
   default **op herbindtijd**”, niet “blijf het endpoint volgen zonder reopen”.
5. **Vastgezette mic weg:** preference clearen naar OS-standaard en opnieuw
   resolven (bestaand clear-gedrag consistent afdwingen).
6. **`refresh_portaudio`:** blijft achterwege terwijl externe streams open zijn
   (`has_external_streams` / Meeting Buddy) — ongewijzigde veiligheidsregel.
7. **macOS / Linux:** geen warm-rebind-pad op Darwin; Linux experimenteel, geen
   parity-gate. Geen watcher-investering.

### Bewust buiten scope

- Mid-meeting Meeting Buddy capture/loopback-reconnect
- Mid-opname device hot-swap
- Altijd heropenen bij elke start
- Idle auto-switch zonder gebruikersactie (start/opslaan)

## Alternatieven overwogen

- **OS-watcher in v1 (WASAPI `IMMNotificationClient`).** Uitgesteld: lost het
  sticky-warm-probleem niet alleen op (nog steeds stop → refresh → open); race
  met BT-profielonderhandeling en met MB-streams; event-storms; trekt COM in
  core of forceert vroege `host`-audio-API’s.
- **Altijd stream heropenen bij elke dicteerstart.** Verworpen: maakt
  `warm_microphone` zinloos (0,5–2 s BT-open elke keer).
- **Watcher in `Opnamesessie` zonder host-seam.** Verworpen (linux-/macos-
  platform): bak Windows-semantiek in het domeinobject; Linux/macOS betalen
  later met stubs.

## Gevolgen

**Positief**

- Lost het primaire Windows-scenario (headset terwijl app al draait → volgende
  Shift+Esc) met beperkte wijziging in bestaande start-/save-paden.
- macOS blijft cold-open; geen menubalk-risico.
- Laat ruimte voor een latere watcher-epic zonder API-schuld in core.

**Negatief / acceptatie**

- Geen auto-switch mid-idle: herbindt pas bij start of Instellingen-opslaan.
- Edge case: identity ongewijzigd maar endpoint stil/verkeerd → kan nog een
  mislukte cyclus kosten (bestaand empty-audio → `refresh_input_device` als
  vangnet).

## Verificatie

- Unit tests voor identity unchanged / changed / pinned-gone → default.
- Windows handmatige smoke: BT connect → Shift+Esc met warm mic aan.
- Geen nieuwe netwerk- of cloud-afhankelijkheden.
