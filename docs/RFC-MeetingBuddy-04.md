# RFC-MeetingBuddy-04

# Technische uitwerking (Uitgebreide versie)

**Status:** Concept\
**Versie:** 1.0\
**Project:** praatMaar -- Meeting Buddy

> Dit document beschrijft de technische uitwerking van Meeting Buddy.
> Het vormt de basis voor implementatie, testen en toekomstige
> uitbreidingen.

------------------------------------------------------------------------

# Inhoud

1.  Doel
2.  Technische uitgangspunten
3.  Datamodellen
4.  Interfaces
5.  Capability-contracten
6.  AI-integratie
7.  Performance
8.  Privacy
9.  Security
10. Logging & Observability
11. Foutafhandeling
12. Teststrategie
13. Acceptatiecriteria
14. Roadmap

------------------------------------------------------------------------

# 1. Doel

De technische architectuur moet:

-   modulair zijn;
-   uitbreidbaar zijn;
-   lokale AI ondersteunen;
-   cloud-AI ondersteunen;
-   privacy-by-design toepassen;
-   schaalbaar blijven.

------------------------------------------------------------------------

# 2. Technische uitgangspunten

## Modulair

Elke component heeft één verantwoordelijkheid.

## Dependency inversion

Alle afhankelijkheden verlopen via capability-contracten.

## Stateless componenten

Waar mogelijk zijn componenten stateless; sessiestatus bevindt zich in
de Meeting State.

## Incrementele verwerking

Alleen transcriptdelta's worden verwerkt.

------------------------------------------------------------------------

# 3. Datamodellen

## MeetingSession

``` text
id
title
status
created_at
started_at
ended_at
configuration
```

## MeetingState

``` text
topics[]
decisions[]
action_items[]
questions[]
risks[]
participants[]
context
confidence
```

## Topic

``` text
id
title
status
confidence
references[]
```

## ActionItem

``` text
id
description
owner
due_date
priority
status
origin
```

## Decision

``` text
id
description
confidence
timestamp
participants
```

``` mermaid
classDiagram
MeetingSession --> MeetingState
MeetingState --> Topic
MeetingState --> ActionItem
MeetingState --> Decision
```

------------------------------------------------------------------------

# 4. Interfaces

Alle interne services communiceren via expliciete interfaces.

  Interface             Verantwoordelijkheid
  --------------------- -----------------------
  SessionService        Sessiebeheer
  ContextService        Contextopbouw
  SemanticService       AI-analyse
  MeetingStateService   Mutaties en validatie
  HintService           Prioriteren hints
  DashboardService      Presentatie
  ReviewService         Samenvattingen
  ExportService         Exports

Belangrijke ontwerpregel:

> Componenten kennen alleen interfaces, nooit concrete implementaties.

------------------------------------------------------------------------

# 5. Capability-contracten

## Verplicht

-   transcription.speech_to_text

## Optioneel

-   audio.speaker_detection
-   calendar.provider
-   documents.search
-   semantic.search
-   vision.ocr
-   translation.provider

### Contracteigenschappen

Iedere capability beschrijft:

-   naam
-   versie
-   input
-   output
-   foutcodes
-   beschikbaarheid

Meeting Buddy detecteert capabilities tijdens initialisatie en
degradeert gecontroleerd wanneer een capability ontbreekt.

------------------------------------------------------------------------

# 6. AI-integratie

Ondersteunde providers:

-   Geen AI
-   Qwen
-   Gemma
-   OpenAI
-   Claude
-   toekomstige providers

``` mermaid
flowchart LR
Transcript --> Semantic
Semantic --> MeetingState
MeetingState --> HintEngine
HintEngine --> Dashboard
```

Ontwerpregels:

-   AI mag de Meeting State alleen verrijken.
-   AI verwijdert geen gebruikersinformatie.
-   AI is volledig vervangbaar.

------------------------------------------------------------------------

# 7. Performance

## Doelstellingen

-   Realtime transcriptverwerking
-   Lage latency voor hints
-   Geen volledige transcript-heranalyse
-   Lage CPU-belasting
-   Beperkt geheugenverbruik

## Optimalisaties

-   Delta-processing
-   Lazy loading
-   Immutable snapshots
-   Capability caching
-   Asynchrone AI-aanroepen

------------------------------------------------------------------------

# 8. Privacy

Uitgangspunten:

-   Privacy by Design
-   Lokale verwerking als standaard
-   Cloudgebruik optioneel
-   Configureerbare bewaartermijnen
-   Gebruiker bepaalt export

Gegevens worden uitsluitend verwerkt voor de actieve sessie.

------------------------------------------------------------------------

# 9. Security

## Maatregelen

-   Least Privilege
-   Inputvalidatie
-   Capability-isolatie
-   Veilige configuratieopslag
-   Veilige exports
-   Geen gevoelige data in logging

## Risico's

-   Prompt injection
-   Onbedoelde cloudverwerking
-   Ongeautoriseerde exports

Voor ieder risico moeten mitigerende maatregelen worden geïmplementeerd.

------------------------------------------------------------------------

# 10. Logging & Observability

Logcategorieën:

-   Session lifecycle
-   Capability discovery
-   AI-calls
-   Performance
-   Errors

Geen transcriptinhoud of persoonsgegevens in standaardlogs.

Metrics:

-   gemiddelde AI-latency
-   transcriptverwerkingssnelheid
-   actieve sessies
-   capability failures

------------------------------------------------------------------------

# 11. Foutafhandeling

  Situatie               Gedrag
  ---------------------- ---------------------------------------
  AI-timeout             Laatste Meeting State behouden
  Capability ontbreekt   Functionaliteit degraderen
  Export mislukt         Retry aanbieden
  Transcriptie stopt     Gebruiker informeren, sessie behouden

Het systeem mag niet crashen door het uitvallen van één component.

------------------------------------------------------------------------

# 12. Teststrategie

## Unit tests

Alle services afzonderlijk.

## Integratietests

Capability-koppelingen.

## Contracttests

Validatie van capability-interfaces.

## AI-tests

Deterministische regressiesets.

## Performance

Langdurige sessies.

## End-to-end

Volledige gebruikersworkflow.

``` mermaid
flowchart LR
Unit --> Integration --> Contract --> E2E --> Performance
```

------------------------------------------------------------------------

# 13. Acceptatiecriteria

-   Meeting State is de enige bron van waarheid.
-   Interfaces zijn stabiel en gedocumenteerd.
-   Capability-contracten worden gevolgd.
-   AI werkt incrementeel.
-   Componenten zijn onafhankelijk testbaar.
-   Privacy by Design is aantoonbaar toegepast.
-   Securitymaatregelen zijn geïmplementeerd.
-   Regressietests voorkomen functionele achteruitgang.
-   Nieuwe AI-providers vereisen geen architectuurwijziging.

------------------------------------------------------------------------

# 14. Roadmap

## Fase 1

-   Transcriptie
-   Meeting State
-   Dashboard

## Fase 2

-   Speaker Detection
-   Review
-   Export

## Fase 3

-   Kalenderintegratie
-   Documentanalyse
-   Geavanceerde Hint Engine

## Fase 4

-   Vision
-   OCR
-   Whiteboardanalyse
-   Knowledge Retrieval
-   Multi-meeting inzichten

------------------------------------------------------------------------

# Bijlage A -- Niet-functionele eisen

  Onderwerp           Doel
  ------------------- ------------------------------------------
  Beschikbaarheid     Sessie blijft actief bij componentuitval
  Schaalbaarheid      Nieuwe capabilities zonder herontwerp
  Onderhoudbaarheid   Componenten los gekoppeld
  Testbaarheid        Iedere service afzonderlijk testbaar
  Portabiliteit       Windows, macOS en Linux

# Bijlage B -- Architectuurregels

1.  Transcript is nooit de bron van waarheid.
2.  Meeting State is leidend.
3.  Capabilities abstraheren externe afhankelijkheden.
4.  AI ondersteunt, beslist niet.
5.  Alle communicatie verloopt via goed gedefinieerde interfaces.
6.  Nieuwe functionaliteit wordt als capability of interne service
    toegevoegd.