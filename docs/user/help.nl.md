# praatMaar — Help

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

**Terug naar standaard:** zeg alleen het woord **standaard** (één take, exact). De
actieve bestemming wordt gewist. (Het resetwoord is altijd *standaard*, ongeacht de
taal van de interface.)

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
- **Modules** — uitbreidingen en incrementele transcriptie
- **Help** — deze gebruikershandleiding
- **Afsluiten**

## Modules en externe tools

Via **Modules** in het systeemvak kun je uitbreidingen aan- of uitzetten en
**incrementele transcriptie** inschakelen. Met incrementele transcriptie draait
Whisper al tijdens je opname op de achtergrond; modules en externe tools kunnen
tussentijdse tekst ontvangen vóór je stopt.

**Event-journal:** elke dicteercyclus wordt als JSON-regels weggeschreven in
`%APPDATA%\praatMaar\events\events.jsonl` (macOS: Application Support). Externe
programma's kunnen dat bestand volgen zonder praatMaar aan te passen. Elk event
heeft een `session_id`, `type` (bijv. `transcript.saved`) en metadata.

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
