# RFC-AudioCapture-01

# Audio Capture Architectuur

**Status:** Concept\
**Versie:** 0.1\
**Project:** praatMaar -- Meeting Buddy

## Doel

Deze RFC beschrijft de architectuur voor het vastleggen van audio voor
Meeting Buddy. Het doel is betrouwbare, realtime audio-opname van één of
meerdere bronnen als input voor transcriptie en semantische analyse.

## Ontwerpdoelen

-   Lage latency
-   Hoge betrouwbaarheid
-   Platformonafhankelijk ontwerp
-   Privacy by Design
-   Ondersteuning voor meerdere gelijktijdige audiobronnen
-   Fail-soft gedrag

## Architectuuroverzicht

``` mermaid
flowchart LR
    Mic[Microfoon]
    Loopback[System Audio]
    Virtual[Virtual Device]
    Capture[Audio Capture Engine]
    Mixer[Audio Mixer]
    Buffer[Ring Buffer]
    STT[Speech-to-Text Capability]

    Mic --> Capture
    Loopback --> Capture
    Virtual --> Capture
    Capture --> Mixer
    Mixer --> Buffer
    Buffer --> STT
```

## Audiobronnen

### Verplicht

-   Microfoon

### Optioneel

-   System Audio (loopback)
-   Virtuele audiodevices
-   Toekomstige netwerkbron

## Platformondersteuning

  Platform   Status     Implementatie
  ---------- ---------- ---------------------
  Windows    MVP        WASAPI + Loopback
  macOS      Toekomst   CoreAudio
  Linux      Toekomst   PipeWire/PulseAudio

## Sessiemodel

Een sessie bevat één of meer actieve audiokanalen.

``` text
CaptureSession
- id
- started_at
- devices[]
- sample_rate
- channels
- state
```

## Device Discovery

De Audio Capture Engine detecteert:

-   beschikbare microfoons
-   loopback-devices
-   sample rates
-   kanaalconfiguraties

Wijzigingen tijdens een sessie worden als events verwerkt.

## Buffering

Gebruik een ringbuffer om:

-   jitter op te vangen
-   AI-verwerking te ontkoppelen
-   realtime transcriptie mogelijk te maken

Doelen:

-   Buffergrootte: 100--500 ms
-   Geen dataverlies bij korte pieken

## Synchronisatie

Bij meerdere bronnen:

-   uniforme sample rate
-   timestamp-normalisatie
-   synchronisatie vóór transcriptie

## Foutafhandeling

  Situatie                    Gedrag
  --------------------------- ------------------------------------
  Microfoon verdwijnt         Waarschuwen, herverbinden proberen
  Loopback niet beschikbaar   Alleen microfoon gebruiken
  Device wisselt              Capture opnieuw initialiseren
  Buffer overflow             Oudste audio verwerpen en loggen

## Capability-koppeling

Audio Capture levert audio aan:

-   `transcription.speech_to_text`

Audio Capture is een interne infrastructuurcomponent en geen
transcriptie-engine.

## Security & Privacy

-   Audio blijft standaard lokaal.
-   Geen opslag tenzij gebruiker dit inschakelt.
-   Geen verzending naar cloud zonder expliciete AI-configuratie.
-   Device-informatie bevat geen persoonsgegevens.

## Performance-eisen

-   End-to-end latency \< 500 ms
-   CPU-overhead laag genoeg voor lokale AI
-   Continue verwerking gedurende vergaderingen \> 4 uur
-   Herstel van device-uitval zonder applicatiecrash

## Teststrategie

-   Unit tests voor buffering
-   Integratietests met meerdere devices
-   Hot-plug tests
-   Langdurige stresstests
-   Latencymetingen
-   Handmatige validatie met Teams/Zoom

## Acceptatiecriteria

-   Microfooncapture werkt stabiel.
-   Loopback wordt gebruikt indien beschikbaar.
-   Meerdere bronnen kunnen worden samengevoegd.
-   Transcriptie ontvangt een continue audiostream.
-   Device-uitval veroorzaakt geen sessieverlies.
-   Architectuur ondersteunt toekomstige platformuitbreidingen.