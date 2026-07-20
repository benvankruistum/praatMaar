# RFC-MeetingBuddy-03

# Functionele specificatie (Uitgebreide versie)

**Status:** Concept\
**Versie:** 1.0\
**Project:** praatMaar -- Meeting Buddy

------------------------------------------------------------------------

# Inhoud

1.  Doel
2.  Voorbereiding
3.  Live Meeting
4.  Dashboard
5.  Samenvattingen
6.  Actiepunten
7.  Review
8.  Export
9.  Configuratie
10. UX-uitgangspunten
11. Foutscenario's
12. Acceptatiecriteria

------------------------------------------------------------------------

# 1. Doel

Meeting Buddy ondersteunt gebruikers gedurende de volledige levenscyclus
van een vergadering. De gebruiker hoeft zich niet bezig te houden met
transcriptie of notities; de focus ligt op deelnemen aan het gesprek.

------------------------------------------------------------------------

# 2. Voorbereiding

## Nieuwe sessie

De gebruiker kan:

-   een nieuwe vergadering starten;
-   een titel en doel opgeven;
-   een agenda importeren;
-   documenten koppelen;
-   eigen notities toevoegen.

## Contextanalyse

Meeting Buddy analyseert:

-   agenda;
-   documenten;
-   eerdere notities;
-   doel van de vergadering.

Resultaat:

-   verwachte onderwerpen;
-   aandachtspunten;
-   voorbereidende vragen.

``` mermaid
flowchart LR
A[Nieuwe sessie] --> B[Agenda]
A --> C[Documenten]
A --> D[Notities]
B --> E[Contextanalyse]
C --> E
D --> E
E --> F[Context Snapshot]
```

------------------------------------------------------------------------

# 3. Live Meeting

## Start

Bij het starten worden automatisch:

-   transcriptie;
-   Meeting State;
-   Hint Engine;
-   timer

geactiveerd.

## Tijdens de vergadering

De gebruiker ziet uitsluitend relevante informatie.

Voorbeelden:

-   open vragen;
-   nieuwe besluiten;
-   actiepunten;
-   waarschuwingen.

Transcriptie blijft op de achtergrond.

## Pauzeren

Tijdens een pauze stopt transcriptie terwijl de Meeting State behouden
blijft.

------------------------------------------------------------------------

# 4. Dashboard

## Overzicht

Het dashboard bevat:

-   sessiestatus;
-   verstreken tijd;
-   huidige onderwerpen;
-   besluiten;
-   actiepunten;
-   hints;
-   open vragen.

## Ontwerpprincipes

-   geen transcriptviewer;
-   minimale afleiding;
-   hoge leesbaarheid;
-   realtime updates.

``` mermaid
flowchart TD
State[Meeting State]
State --> Topics
State --> Decisions
State --> Actions
State --> Questions
State --> Hints
```

------------------------------------------------------------------------

# 5. Samenvattingen

Na afloop genereert Meeting Buddy meerdere samenvattingen.

## Varianten

-   Managementsamenvatting
-   Uitgebreide samenvatting
-   Chronologische samenvatting
-   Besluitenoverzicht

Iedere samenvatting is bewerkbaar.

------------------------------------------------------------------------

# 6. Actiepunten

Automatisch herkende velden:

-   omschrijving;
-   eigenaar;
-   deadline;
-   context;
-   prioriteit.

Statussen:

-   Open
-   In behandeling
-   Afgerond
-   Vervallen

Gebruikers kunnen actiepunten handmatig toevoegen of wijzigen.

------------------------------------------------------------------------

# 7. Review

Voor afsluiting controleert de gebruiker:

-   samenvatting;
-   besluiten;
-   actiepunten;
-   openstaande vragen.

Pas na goedkeuring wordt de sessie definitief afgesloten.

``` mermaid
flowchart LR
Meeting --> Review --> Goedkeuren --> Export
Review --> Wijzigen --> Review
```

------------------------------------------------------------------------

# 8. Export

Ondersteunde exportformaten:

-   Markdown
-   HTML
-   PDF
-   JSON

Selecteerbare onderdelen:

-   samenvatting;
-   besluiten;
-   actiepunten;
-   vragen;
-   metadata.

------------------------------------------------------------------------

# 9. Configuratie

## Transcriptie

-   taal;
-   model;
-   microfoon.

## AI

-   provider;
-   lokaal/cloud;
-   creativiteit;
-   samenvattingsniveau.

## Dashboard

-   compacte modus;
-   hints aan/uit;
-   meldingsniveau.

## Privacy

-   lokale opslag;
-   automatische verwijdering;
-   cloudgebruik toestaan.

------------------------------------------------------------------------

# 10. UX-uitgangspunten

-   De gebruiker staat centraal.
-   Geen overmatige notificaties.
-   Relevantie boven volledigheid.
-   AI ondersteunt maar beslist niet.
-   Belangrijkste informatie is binnen één oogopslag zichtbaar.

------------------------------------------------------------------------

# 11. Foutscenario's

  Situatie                Gedrag
  ----------------------- --------------------------------------------
  Transcriptie valt uit   Gebruiker informeren, sessie actief houden
  AI niet beschikbaar     Transcriptie blijft functioneren
  Export mislukt          Herhalen zonder gegevensverlies
  Context ontbreekt       Vergadering zonder context starten

------------------------------------------------------------------------

# 12. Acceptatiecriteria

-   Gebruiker kan een sessie voorbereiden.
-   Context wordt vóór de vergadering opgebouwd.
-   Live ondersteuning werkt zonder transcriptweergave.
-   Dashboard toont actuele Meeting State.
-   Samenvattingen zijn bewerkbaar.
-   Actiepunten worden automatisch herkend.
-   Review ondersteunt correcties.
-   Export ondersteunt meerdere formaten.
-   Configuratie is per gebruiker instelbaar.
-   De interface leidt niet af van de vergadering.