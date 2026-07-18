# Handoff — praatMaar opname-indicator

Geschreven 2026-07-15 om de sessie af te sluiten. Bedoeld om na een herstart naadloos
verder te gaan. Werktaal: **Nederlands**.

## Waar we staan

### 1. Wayfinder-effort "Opname-indicator" — AFGEROND ✅

Doel was: een klein statuslampje op het scherm dat de dicteercyclus toont (opname /
transcriberen / geannuleerd / fout), zonder focus te stelen, voorbereid op een latere
push-to-talk-modus. Plan-only.

- Kaart: [.scratch/opname-indicator/map.md](.scratch/opname-indicator/map.md)
- **Alle 5 tickets resolved** (01 techniek, 05 waveform, 02 architectuur, 03 ontwerp,
  04 spec).
- **Eindproduct = [.scratch/opname-indicator/spec.md](.scratch/opname-indicator/spec.md)** —
  overdraagbare implementatie-spec.
- Prototype-asset: [.scratch/opname-indicator/assets/03-prototype-indicator.html](.scratch/opname-indicator/assets/03-prototype-indicator.html)

### 2. Feasibility geverifieerd ✅ (bewijs, geen aanname)

Op verzoek van de gebruiker een proof-of-concept gedraaid (`.venv/Scripts/python.exe`,
Python 3.13, Tk 8.6, numpy 2.5.1). Bevestigd:

- **Puur Python, geen extra library.** tkinter + ctypes = stdlib; numpy is er al (voor
  RMS). Er is dus GEEN PySide/PyQt o.i.d. nodig.
- De pill rendert correct (gebruiker heeft 'm zien verschijnen; vond 'm er goed
  uitzien, "ongeveer zoals het prototype").
- **No-activate werkt** mits de shim vóór het eerste tonen staat. Eerste POC-poging
  stal wél even de focus (shim ná tonen); tweede poging niet. Geverifieerde volgorde
  staat nu in **spec.md §3 "Initialisatie-volgorde (GEVERIFIEERD)"**.
- De POC-scripts stonden in de scratchpad (session-temp) en zijn na herstart weg —
  niet nodig, de aanpak zit in de spec.

### 3. Gebruikersfeedback verwerkt ✅

- Pill mag **groter** voor zichtbaarheid (POC 260×46 voelde klein → richtwaarde
  ~340×60). Vastgelegd in **spec.md §5 "Maatvoering"**.
- Kleuren en animaties per toestand **goedgekeurd**.

## Openstaand — hier verder oppakken

### TAAK A: Matt Pocock's "handoff"-skill installeren — AFGEROND ✅ (2026-07-15)

Geïnstalleerd naar `%USERPROFILE%\.claude\skills\handoff\` (`SKILL.md` +
`agents/openai.yaml`), opgehaald uit `skills/productivity/handoff/` van
https://github.com/mattpocock/skills. Bestanden vóór installatie geïnspecteerd
(read-only via WebFetch/curl van de raw-URL's). `disable-model-invocation: true`,
dus alleen handmatig via `/handoff`. Dit document is mijn eigen ad-hoc versie;
gebruik voortaan de geïnstalleerde skill.

### TAAK B: de indicator daadwerkelijk bouwen — GEBOUWD ✅ (2026-07-15), acceptatietest openstaand

Gebouwd volgens [spec.md](.scratch/opname-indicator/spec.md), in een **aparte module**
(keuze gebruiker):

- Nieuw: [indicator.py](indicator.py) — `RecordingState`, `notify_state()`,
  `push_level()`/`reset_levels()`, en de `RecordingIndicator` (tkinter + ctypes
  no-activate-shim in de geverifieerde volgorde uit spec §3).
- Aangepast: [dictation.py](dictation.py) — import, `INDICATOR_POSITION`,
  RMS-feed in `audio_callback`, de zes `notify_state`-punten (spec §4), en `main()`
  omgedraaid naar listener-zonder-join + `indicator.run()` + SIGINT-afhandeling.
- **Visueel geverifieerd** op het echte bureaublad (schermafbeelding): RECORDING
  (afgeronde donkere capsule, rood puntje, "Opname", rode VU-balkjes, tag "↔ toggle")
  en TRANSCRIBING (amber puntje, "Transcriberen", drie lopende stippen) renderen goed.
  Win32 bevestigde de harde constraint: `visible=1`, en het voorgrondvenster verandert
  NIET bij tonen (`focus_ongewijzigd=True`, `pill_is_fg=False`) — geen focus-diefstal.
- Fixes t.o.v. eerste versie:
  - `_show/_hide` gebruiken Tk's `deiconify()/withdraw()` i.p.v. rauwe `ShowWindow`
    (die liet Tk het venster op 1×1 en verborgen; de shim vóór de eerste `deiconify`
    houdt no-activate intact).
  - stdout naar UTF-8 geforceerd in `dictation.py` (anders crasht `print("● ...")`
    op cp1252 zodra stdout omgeleid is).
  - Afgeronde capsule via `-transparentcolor` werkt (`USE_TRANSPARENT_KEY = True`).
  - Tag-glyphs `↔`/`●` i.p.v. `⇄`/`◉` (die renderen niet in Segoe UI).
- **Launch-context (belangrijk):** GUI-apps via de Bash-tool starten zet het venster op
  een niet-interactief bureaublad (onzichtbaar). Start `dictation.py` via een gewone
  terminal / PowerShell. Zie geheugen `gui-launch-via-powershell`.
- **Nog te doen door gebruiker (acceptatie):** `./.venv/Scripts/python.exe dictation.py`
  draaien, één keer dicteren, en bevestigen dat het plakken met Ctrl+V blijft werken.
  Positie/uiterlijk tunen via `INDICATOR_POSITION` (dictation.py) en de constanten boven
  in `indicator.py`.

## Handige feiten

- Geen git-repo (lokale map). Windows 11, PowerShell primair.
- Python: `.venv/Scripts/python.exe` (3.13). tkinter 8.6, numpy 2.5.1 aanwezig.
- Issue-tracker = lokale markdown onder `.scratch/` (zie `docs/agents/issue-tracker.md`).
