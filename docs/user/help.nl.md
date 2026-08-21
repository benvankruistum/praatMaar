# praatMaar — Help

## Aan de slag

1. Start praatMaar (tray-icoon verschijnt na het laden van het model).
2. Zet de cursor in een tekstveld.
3. Start/stop dicteren met de sneltoets (standaard
   `Ctrl+Shift+Alt+Spatie`; zie Instellingen).
4. Tekst wordt lokaal getranscribeerd en — afhankelijk van je instellingen —
   geplakt of alleen opgeslagen.

**Windows-installatie:** downloads zijn niet digitaal ondertekend. Bij
“Windows beschermde je pc”: **Meer info** → **Toch uitvoeren**.

**macOS (Apple Silicon):** uit GitHub Releases komt een unsigned
`praatMaar-*-macos-arm64.zip`. Bij Gatekeeper: rechtsklik → **Open**, of
`xattr -cr praatMaar.app`.

**Privacy (kort):** spraak-naar-tekst gebeurt lokaal. Gevoelige bestanden staan
onder `%APPDATA%\praatMaar\` (transcripts, recovery, inbox, logs). Zie ook
Privacy in de README.

**Status & fouten:** na het laden zie je kort een gereed-pill met je sneltoets.
Microfoonfouten openen geen blokkerende dialoog: de status-pill en het tray-icoon
tonen wat er misgaat; de checklist staat in Instellingen.

**Microfoon wisselen:** praatMaar kiest opnieuw het juiste apparaat bij de
**start van een dicteercyclus** en wanneer je in Instellingen een andere mic
opslaat (handig na Bluetooth-headset). Er is geen automatische wissel terwijl
de app idle is — start dicteren of sla Instellingen op.

**Whisper:** onder Instellingen → **Whisper** kun je kwaliteit (beam),
stiltefilter (VAD), prompt/hotwords en gerelateerde drempels bijstellen.
Onder **Geavanceerd** staan presets Snel / Gebalanceerd / Nauwkeurig (model +
basis-Whisper). Het Whisper-**model** (base/small/medium) vereist een herstart.

## Wat zijn bestemmingen?

Een **bestemming** is een naam gekoppeld aan een map op je computer. Als je dicteert,
wordt het transcript opgeslagen in de map van de actieve bestemming.

**Sticky:** de actieve bestemming blijft aan staan totdat je wisselt of terugzet naar
standaard. Je hoeft de naam niet elke keer opnieuw te zeggen.

**Automatisch plakken:** per bestemming kun je instellen of tekst naar klembord +
invoerveld mag. Standaard staat dat **uit** (alleen opslaan in de map). Zonder
actieve bestemming geldt de globale optie in Instellingen.

**Pill:** de kleine indicator op je scherm toont de naam van de actieve bestemming
(zichtbaar ook als je niet aan het opnemen bent). Geen label betekent: standaardmap.

## Wisselen met je stem

Neem één korte opname waarin je **alleen** de exacte bestemmingsnaam zegt — geen extra
woorden ervoor of erna. praatMaar vergelijkt de hele take met je opgeslagen namen
(exacte match na normalisatie).

- **Match:** de bestemming wordt actief, de pill wordt bijgewerkt. Er wordt niets
  geplakt en de naam zelf wordt niet als transcript opgeslagen.
- **Geen match:** normale dicteerflow — tekst plakken en opslaan in de huidige map.

**Terug naar standaard:** zeg alleen **standaard**, **default** of **standard**
(één take, exact). De actieve bestemming wordt gewist. Alle drie de woorden werken,
ongeacht de spraak- of interfacetaal.

## Waar landen je bestanden?

| Situatie | Map |
|----------|-----|
| Geen actieve bestemming (standaard) | `%APPDATA%\praatMaar\transcripts\` |
| Actieve bestemming | De map die je aan die naam hebt gekoppeld |

In de standaardmap houdt praatMaar automatisch alleen de nieuwste transcripts bij
(retentie). In bestemmingsmappen gebeurt dat niet.

Recovery-audiobestanden (bij mislukte opnames) blijven altijd in
`%APPDATA%\praatMaar\recovery\`, ongeacht de actieve bestemming. In **Instellingen**
→ **Herstel-audio** kun je die bestanden bekijken, wissen of opnieuw laten
transcriberen.

## Beheer via het systeemvak

Rechtsklik op het praatMaar-icoon in het systeemvak:

- **Instellingen** — microfoon, sneltoets, talen, herstel-audio
- **Bestemmingen** — dialoog om namen en mappen toe te voegen, te wijzigen of te
  verwijderen, en de actieve bestemming in te stellen of te wissen. In die dialoog
  vind je ook knoppen om de transcriptmap of de actieve map te openen.
- **Recente transcripts** — de laatste vijf geslaagde dicteer-transcripts
  (datum/tijd); klik om de tekst opnieuw op het klembord te zetten (niet plakken)
- **Modules** — uitbreidingen en incrementele transcriptie
- **Help** — deze gebruikershandleiding
- **Afsluiten**

## Modules en externe tools

Via **Modules** in het systeemvak kun je uitbreidingen aan- of uitzetten en
**incrementele transcriptie** inschakelen. Whisper draait dan tijdens de opname
over **nieuwe audiostukken** (vaste tijd, stilte/VAD, of hybride) en houdt de
laatste ~6 s achter tot de volgende knip of stop — zonder de hele opname
opnieuw te transcriberen. De live-tekst kan daardoor 4–8 s achterlopen.

Op de **naad** kunnen nog zelden woorden dubbel vallen; afgekapte woorden
(`brandende… torts`) worden tegengehouden door die onverwerkte audiostaart.
Werkpunt: knipmodus **vast**, chunk **20 s**, “voortbouwen op vorige tekst”
uit. Op de status-pill tonen twee LED’s of een knip door stilte of door het
tijdvenster kwam.

**Event-journal:** elke dicteercyclus wordt als JSON-regels weggeschreven in
`%APPDATA%\praatMaar\events\events.jsonl` (macOS: Application Support). Externe
programma's kunnen dat bestand volgen zonder praatMaar aan te passen. Elk event
heeft een `session_id`, `type` (bijv. `transcript.saved`) en metadata. De
**volledige transcripttekst staat niet** in het journal — wel o.a. de lengte
(`transcript_chars`). Transcriptbestanden zelf staan in `transcripts\` of je
bestemmingsmap.

**Inbox-spiegel** (standaard aan): kopieert elk opgeslagen transcript naar
`%APPDATA%\praatMaar\inbox\` — handig als vaste “drop zone” voor scripts.

Herstel-transcriptie (Instellingen → Herstel-audio) emitteert dezelfde soort
events met `source: "recovery"`.

## Risico's en tips

**Whisper hoort de naam verkeerd**
Als de transcriptie niet exact overeenkomt met een bestemmingsnaam, gebeurt er niets
extra: je blijft op de huidige bestemming en de tekst wordt normaal verwerkt. Veilig,
maar je wissel dan niet.

**Te korte of generieke namen**
Namen als "notities" of "werk" komen sneller per ongeluk voor in gewone dictatie.
Kies korte maar unieke namen, bijvoorbeeld "boodschappenlijst" of "project-alpha".

**Bestanden onversleuteld**
Transcripts worden als gewone tekstbestanden op schijf opgeslagen, zonder versleuteling.
Gebruik geen bestemmingen in gedeelde of onbeveiligde mappen als je gevoelige inhoud
dicteert.

## Meeting Buddy en Microsoft Teams (Windows)

**Meeting Buddy** schakel je in via systeemvak → **Modules**. Na **Opslaan** blijft
dat venster open en zie je meteen knoppen voor starten, snelle start, stoppen,
agenda en eigenschappen. In het traymenu staat ook **Meeting Buddy ▸** met dezelfde
acties.

- **Meeting starten…** opent de agenda (bibliotheek met Recent + alle `.md`-agenda’s).
- **Meeting starten (snel)** start met de huidige agenda zonder dialoog.
- **Agenda bewerken** om agenda’s op te slaan/laden zonder te starten.
- **Eigenschappen** voor meetinggeluid (Windows loopback), uitvoerapparaat en
  optioneel een andere transcriptmap.

Tijdens een meeting groeit het transcript als `.md` onder
`%APPDATA%\praatMaar\meeting-buddy\transcripts\` (alleen definitieve tekst;
aanpasbaar via Eigenschappen). Bij stoppen volgt een melding met het pad; de
laatste audiobuffer en openstaande transcriptie-chunks worden eerst nog
verwerkt.

### Local LLM, live samenvatting en agenda-review

Optioneel (standaard uit): schakel **Local LLM** in via **Modules**. Die module
gebruikt [Ollama](https://ollama.com/). Via **Eigenschappen** kies je:

- **Standaard (lokaal Ollama):** `http://127.0.0.1:11434` + model `qwen2.5:7b`
- **Eigen Ollama-server:** zelfde Ollama-API, andere basis-URL (host + poort) en
  modelnaam — handig voor een zwaarder model op deze machine of in het LAN

Via de Modules-acties kun je status controleren, installatiehulp openen en het
model downloaden (lokaal `ollama pull`). Zonder klaar Local LLM blijft Meeting
Buddy bij heuristische hints.

Met Local LLM klaar kun je in Meeting Buddy-**Eigenschappen** live samenvatting
en agenda-review aanzetten (standaard uit):

- **Live samenvatting** in de overlay (drempels voor tijd/nieuwe tekst).
- **Agenda-review**: statusladder per agendapunt en “vragen van anderen”
  (experimenteel; hangt af van speakerdetectie).

Zet de module **Speaker Detection** aan (Modules) voor groepsgesprekken met
**één microfoon**: praatMaar labelt dan lokaal anonieme sprekers (`spk_1`,
`spk_2`, …) zonder te bepalen wie jij bent. Handig dicht bij de microfoon in
een rustige ruimte; overlappende spraak blijft lastig.

Op Windows kan Meeting Buddy naast je microfoon ook **meetinggeluid** opnemen van
het gekozen Windows-uitvoerapparaat via **WASAPI-loopback** (niet Stereo Mix).
Kies in Eigenschappen hetzelfde apparaat als waarop Teams/Zoom afspeelt. Bluetooth
verschijnt vaak niet als loopback-bron — gebruik speakers of een HDMI/monitor-uitgang.

Voor Teams-gesprekken:

1. Zet Windows-**geluidsuitvoer** op het apparaat waar Teams doorheen speelt (vaak je headset).
2. Zet de Teams-**luidspreker** op hetzelfde apparaat.
3. Gebruik een **headset** om echo te beperken (je microfoon hoort de luidsprekers niet).

De Meeting Buddy-overlay toont of meetinggeluid actief is. Als loopback niet
beschikbaar is, neemt praatMaar alleen je microfoon op en zie je een waarschuwing.
