# RFC-MeetingBuddy-02

# Architectuur (Uitgebreide versie)

**Status:** Concept\
**Versie:** 1.0\
**Project:** praatMaar -- Meeting Buddy

> Dit document beschrijft de architectuur van Meeting Buddy. De nadruk
> ligt op schaalbaarheid, modulariteit, uitbreidbaarheid en
> privacy-by-design.

------------------------------------------------------------------------

# Inhoud

1.  Doelstellingen
2.  Architectuurprincipes
3.  Overzichtsarchitectuur
4.  Componentarchitectuur
5.  Capability-model
6.  Meeting State
7.  Context Engine
8.  Hint Engine
9.  AI-pipeline
10. Interne services
11. Componentinteractie
12. Foutafhandeling
13. Uitbreidbaarheid
14. Acceptatiecriteria

------------------------------------------------------------------------

# 1. Doelstellingen

Meeting Buddy is ontworpen als een **Second Brain**. Transcriptie is
slechts een middel; de architectuur is gericht op het realtime
ondersteunen van de gebruiker.

Belangrijkste doelen:

-   Realtime ondersteuning
-   Lage latency
-   Lokale verwerking waar mogelijk
-   Uitwisselbare AI-providers
-   Modulair ontwerp
-   Privacy by Design

------------------------------------------------------------------------

# 2. Architectuurprincipes

## Single Responsibility

Iedere component heeft één verantwoordelijkheid.

## Capability First

Externe functionaliteit wordt uitsluitend benaderd via capabilities.

## Incremental Processing

Alleen nieuwe transcriptdelen worden verwerkt.

## Fail Soft

Uitval van een capability leidt tot beperkte functionaliteit, niet tot
het stoppen van de sessie.

## Session Centric

Alle data behoort tot één actieve sessie.

------------------------------------------------------------------------

# 3. Overzichtsarchitectuur

``` mermaid
flowchart TD
    PM[praatMaar]
    CAP[Capability Registry]
    MB[Meeting Buddy]

    PM --> CAP
    CAP --> MB

    MB --> PREP[Preparation]
    MB --> SESSION[Session]
    MB --> REVIEW[Review]
    MB --> EXPORT[Export]
```

------------------------------------------------------------------------

# 4. Componentarchitectuur

``` mermaid
flowchart LR
    PREP[Preparation]
    CONTEXT[Context Engine]
    PIPE[AI Pipeline]
    STATE[Meeting State]
    HINT[Hint Engine]
    DASH[Dashboard]

    PREP --> CONTEXT
    CONTEXT --> PIPE
    PIPE --> STATE
    STATE --> HINT
    HINT --> DASH
```

## Componenten

### Session Manager

Verantwoordelijk voor lifecycle en statusovergangen.

### Preparation Engine

Verzamelt agenda, documenten, notities en doelen.

### Context Engine

Combineert context uit alle bronnen tot één contextsnapshot.

### AI Pipeline

Voert semantische analyse uit op transcriptdelta's.

### Meeting State

De centrale bron van waarheid.

### Hint Engine

Bepaalt welke informatie relevant is voor de gebruiker.

### Review Engine

Genereert samenvattingen en actiepunten.

### Export Engine

Maakt Markdown-, HTML-, PDF- en JSON-export.

------------------------------------------------------------------------

# 5. Capability-model

## Verplichte capability

-   transcription.speech_to_text

## Optionele capabilities

-   audio.speaker_detection
-   calendar.provider
-   documents.search
-   semantic.search
-   vision.ocr
-   ai.semantic_analysis

Nieuwe providers kunnen worden geregistreerd zonder wijzigingen aan
Meeting Buddy.

------------------------------------------------------------------------

# 6. Meeting State

Meeting State is geen transcript.

Meeting State bevat:

-   besproken onderwerpen
-   open onderwerpen
-   besluiten
-   actiepunten
-   open vragen
-   risico's
-   context
-   confidence scores

``` mermaid
flowchart TD
    Transcript --> Semantic
    Semantic --> MeetingState
    MeetingState --> Dashboard
    MeetingState --> Review
    MeetingState --> Export
```

------------------------------------------------------------------------

# 7. Context Engine

Bronnen:

-   Agenda
-   Documenten
-   Eigen notities
-   Transcript
-   Speaker Detection
-   Handmatige input

Output:

-   Context Snapshot

Eigenschappen:

-   Immutable snapshots
-   Sessiegebonden
-   Incrementeel bijgewerkt

------------------------------------------------------------------------

# 8. Hint Engine

De Hint Engine bepaalt welke meldingen zichtbaar zijn.

Voorbeelden:

-   onderwerp vergeten
-   actiepunt zonder eigenaar
-   onbeantwoorde vraag
-   ontbrekend besluit

Iedere hint bevat:

-   prioriteit
-   confidence
-   cooldown
-   timestamp

------------------------------------------------------------------------

# 9. AI-pipeline

``` mermaid
flowchart LR
    TD[Transcript Delta]
    SA[Semantic Analysis]
    SD[Semantic Delta]
    MS[Meeting State Update]
    HE[Hint Evaluation]

    TD --> SA --> SD --> MS --> HE
```

Belangrijk:

-   geen volledige heranalyse
-   alleen wijzigingen verwerken
-   AI is vervangbaar

Ondersteunde modellen:

-   Geen AI
-   Qwen
-   Gemma
-   OpenAI
-   Claude
-   toekomstige providers

------------------------------------------------------------------------

# 10. Interne services

  Service               Verantwoordelijkheid
  --------------------- ----------------------
  SessionService        Sessiebeheer
  ContextService        Context verzamelen
  SemanticService       AI-aanroepen
  MeetingStateService   Bron van waarheid
  HintService           Prioriteren hints
  DashboardService      Presentatie
  ReviewService         Samenvattingen
  ExportService         Exportformaten

------------------------------------------------------------------------

# 11. Componentinteractie

``` mermaid
sequenceDiagram
    participant STT as Speech-to-Text
    participant AI
    participant MS as Meeting State
    participant H as Hint Engine
    participant UI

    STT->>AI: Transcript Delta
    AI->>MS: Semantic Delta
    MS->>H: Updated State
    H->>UI: Relevante hints
```

------------------------------------------------------------------------

# 12. Foutafhandeling

  Situatie                 Gedrag
  ------------------------ ----------------------------------------
  Geen Speaker Detection   UNKNOWN gebruiken
  Geen AI                  Alleen transcriptie
  Geen documenten          Lege context
  AI-timeout               Laatste geldige Meeting State behouden

------------------------------------------------------------------------

# 13. Uitbreidbaarheid

Toekomstige componenten:

-   Vision Engine
-   OCR
-   Whiteboard Analysis
-   Task Synchronisation
-   Calendar Sync
-   Knowledge Retrieval

Door het capability-model zijn deze zonder grote architectuurwijzigingen
toe te voegen.

------------------------------------------------------------------------

# 14. Acceptatiecriteria

-   Meeting Buddy is één praatMaar-module.
-   Componenten zijn los gekoppeld.
-   Capabilities abstraheren externe functionaliteit.
-   Meeting State is leidend.
-   AI verwerkt alleen transcriptdelta's.
-   Hint Engine toont uitsluitend relevante informatie.
-   Nieuwe AI-providers zijn plugbaar.
-   De architectuur ondersteunt toekomstige uitbreidingen zonder
    herontwerp.