# RFC-MeetingBuddy-01

# Visie, uitgangspunten en gebruikersscenario's

**Status:** Concept
**Versie:** 0.1
**Auteur:** Ben van Kruistum
**Project:** praatMaar
**Gerelateerde RFC's:**

* RFC-MeetingBuddy-02 – Architectuur
* RFC-MeetingBuddy-03 – Functionele specificatie
* RFC-MeetingBuddy-04 – Technische uitwerking
* RFC-SpeakerDetection-01

---

# 1. Inleiding

Meeting Buddy is een nieuwe functionaliteit binnen praatMaar die gebruikers ondersteunt tijdens vergaderingen.

Het primaire doel is **niet** het maken van een transcript of notulen, maar het ondersteunen van de gebruiker tijdens de vergadering zodat belangrijke informatie niet verloren gaat.

Meeting Buddy fungeert als een digitale assistent die realtime meedenkt, context bewaakt en helpt herinneren aan onderwerpen die aandacht vragen.

Deze RFC beschrijft de visie, uitgangspunten en gebruikersscenario's waarop alle volgende ontwerpbeslissingen zijn gebaseerd.

---

# 2. Probleemstelling

Tijdens een vergadering moet een deelnemer voortdurend schakelen tussen verschillende cognitieve taken.

De gebruiker probeert tegelijkertijd:

* actief te luisteren;
* na te denken over antwoorden;
* verbanden te leggen;
* besluiten te onthouden;
* actiepunten te herkennen;
* notities te maken;
* niets belangrijks te vergeten.

Hierdoor ontstaat cognitieve belasting.

In de praktijk leidt dit vaak tot:

* vergeten actiepunten;
* gemiste afspraken;
* onvoldoende voorbereiding;
* onvolledige notities;
* verlies van context;
* achteraf veel tijd besteden aan reconstructie.

Bestaande transcriptiesoftware lost dit probleem slechts gedeeltelijk op.

Een transcript vertelt **wat** er gezegd is, maar helpt de gebruiker nauwelijks tijdens het gesprek.

Meeting Buddy richt zich daarom niet op transcriptie als einddoel, maar op realtime ondersteuning.

---

# 3. Visie

## 3.1 Second Brain

Meeting Buddy is ontworpen als een **Second Brain**.

De software moet functioneren als een tweede geheugen dat de gebruiker ondersteunt zonder de vergadering over te nemen.

Het systeem onthoudt wat belangrijk is zodat de gebruiker zich volledig kan richten op het gesprek.

De gebruiker hoeft niet voortdurend bezig te zijn met:

* onthouden;
* noteren;
* controleren;
* terugzoeken.

De aandacht blijft bij de deelnemers.

---

## 3.2 Geen transcriptviewer

Meeting Buddy is nadrukkelijk **geen transcriptviewer**.

Een volledig transcript tijdens een vergadering leidt af.

In plaats daarvan toont Meeting Buddy uitsluitend informatie die op dat moment relevant is.

Voorbeelden:

* "Onderwerp X is nog niet besproken."
* "Er is nog geen eigenaar benoemd."
* "Je wilde nog terugkomen op punt Y."
* "Deze vraag staat nog open."

---

## 3.3 Proactieve ondersteuning

Meeting Buddy wacht niet tot de gebruiker een vraag stelt.

De software observeert de vergadering en helpt alleen wanneer dat daadwerkelijk waarde toevoegt.

Het uitgangspunt is:

> Zo weinig mogelijk onderbreken, zo veel mogelijk ondersteunen.

---

# 4. Ontwerpprincipes

## 4.1 De vergadering staat centraal

Niet het transcript.

Niet de AI.

Niet de techniek.

Maar de vergadering.

Alle technische keuzes moeten bijdragen aan betere vergaderondersteuning.

---

## 4.2 Lokale verwerking

Waar mogelijk wordt verwerking lokaal uitgevoerd.

Voordelen:

* privacy;
* snelheid;
* offline gebruik;
* voorspelbare kosten.

Cloudmodellen blijven optioneel.

---

## 4.3 Modulair

Meeting Buddy is opgebouwd uit losse componenten.

Voorbeelden:

* transcriptie
* speaker detection
* semantic analysis
* dashboard
* context engine

Componenten kunnen onafhankelijk worden vervangen.

---

## 4.4 AI is ondersteunend

AI neemt geen besluiten.

AI doet suggesties.

De gebruiker blijft verantwoordelijk.

---

## 4.5 Geen vendor lock-in

Er wordt geen afhankelijkheid opgebouwd van één AI-provider.

De architectuur ondersteunt meerdere AI-backends.

---

## 4.6 Privacy by Design

Persoonlijke gegevens worden alleen verwerkt wanneer noodzakelijk.

De gebruiker houdt controle over:

* opslag;
* export;
* verwijdering;
* AI-provider.

---

# 5. Scope

Meeting Buddy ondersteunt de gebruiker tijdens een vergadering.

De eerste versie richt zich op:

* voorbereiding;
* realtime ondersteuning;
* samenvatting;
* actiepunten;
* besluiten;
* review.

---

# 6. Buiten scope

De eerste versie bevat nadrukkelijk niet:

* automatische vergaderplanning;
* agenda-uitnodigingen versturen;
* deelnemersbeheer;
* stemidentificatie;
* gezichtsherkenning;
* automatische besluitvorming;
* permanente gebruikersprofielen;
* leren over meerdere vergaderingen heen;
* organisatiebrede kennisopbouw.

Deze functionaliteit kan later worden toegevoegd.

---

# 7. Persona's

## 7.1 De Projectleider

Leidt regelmatig vergaderingen.

Belangrijk:

* actiepunten
* besluiten
* planning
* openstaande onderwerpen

---

## 7.2 De Consultant

Voert veel klantgesprekken.

Belangrijk:

* context
* gemaakte afspraken
* vervolgstappen

---

## 7.3 De Product Owner

Heeft behoefte aan:

* requirements
* besluiten
* risico's
* follow-up

---

## 7.4 De Manager

Wil:

* overzicht
* samenvatting
* besluiten
* eigenaarschap

---

## 7.5 De Individuele gebruiker

Gebruikt Meeting Buddy om niets te vergeten.

Heeft vaak geen behoefte aan uitgebreide notulen.

---

# 8. Gebruikersscenario's

## Scenario 1 – Voorbereiden

De gebruiker opent Meeting Buddy.

Hij selecteert:

* agenda;
* documenten;
* eigen notities.

Meeting Buddy analyseert deze informatie.

Resultaat:

* aandachtspunten;
* mogelijke vragen;
* onderwerpen die waarschijnlijk aan bod komen.

---

## Scenario 2 – Meeting starten

De gebruiker start de vergadering.

Meeting Buddy:

* initialiseert de sessie;
* start transcriptie;
* laadt context;
* activeert ondersteuning.

Vanaf dit moment wordt de Meeting State opgebouwd.

---

## Scenario 3 – Tijdens de vergadering

Tijdens het gesprek:

* wordt transcriptie verwerkt;
* wordt context bijgehouden;
* worden onderwerpen gevolgd;
* worden actiepunten herkend.

Meeting Buddy toont alleen relevante hints.

Bijvoorbeeld:

> "Punt 4 staat nog open."

---

## Scenario 4 – Actiepunt

Tijdens de vergadering wordt gezegd:

> "Jan pakt dit volgende week op."

Meeting Buddy herkent:

* actiepunt;
* eigenaar;
* tijdsindicatie.

Na afloop verschijnt dit automatisch in de review.

---

## Scenario 5 – Open vraag

Er wordt een vraag gesteld.

Tien minuten later is deze nog niet beantwoord.

Meeting Buddy toont:

> "Open vraag nog onbeantwoord."

---

## Scenario 6 – Einde vergadering

De gebruiker beëindigt de sessie.

Meeting Buddy maakt:

* samenvatting;
* besluiten;
* actiepunten;
* openstaande vragen.

---

## Scenario 7 – Review

De gebruiker controleert:

* klopt de samenvatting?
* ontbreken actiepunten?
* zijn besluiten juist?

Daarna kan worden geëxporteerd.

---

# 9. Gebruikersreis

```
Voorbereiden
      │
      ▼
Context verzamelen
      │
      ▼
Meeting starten
      │
      ▼
Transcriptie
      │
      ▼
Realtime ondersteuning
      │
      ▼
Review
      │
      ▼
Export
```

---

# 10. Sessielevenscyclus

Iedere vergadering doorloopt dezelfde levenscyclus.

```
Created
    │
    ▼
Prepared
    │
    ▼
Running
    │
    ▼
Paused
    │
    ▼
Running
    │
    ▼
Finishing
    │
    ▼
Review
    │
    ▼
Completed
    │
    ▼
Archived
```

## Created

Nieuwe sessie aangemaakt.

Nog geen context geladen.

---

## Prepared

Agenda en context zijn beschikbaar.

De gebruiker kan nog wijzigingen aanbrengen.

---

## Running

Transcriptie actief.

Meeting State wordt opgebouwd.

Hints worden gegenereerd.

---

## Paused

Transcriptie tijdelijk gepauzeerd.

Geen analyse.

Meeting State blijft behouden.

---

## Finishing

Transcriptie stopt.

Laatste analyse wordt uitgevoerd.

Meeting State wordt afgerond.

---

## Review

Gebruiker controleert:

* samenvatting;
* besluiten;
* actiepunten.

Correcties zijn mogelijk.

---

## Completed

Vergadering is afgerond.

Resultaten zijn definitief.

---

## Archived

Sessie wordt opgeslagen of verwijderd volgens gebruikersinstellingen.

---

# 11. Ontwerpbeslissingen

## Meeting Buddy is geen transcriptieprogramma

Transcriptie is een hulpmiddel.

Niet het eindproduct.

---

## Meeting Buddy is sessiegericht

Iedere vergadering staat op zichzelf.

Er wordt geen impliciete kennis meegenomen uit eerdere vergaderingen.

---

## AI ondersteunt

AI doet voorstellen.

De gebruiker beslist.

---

## Privacy heeft prioriteit

Lokale verwerking heeft de voorkeur.

Cloudgebruik blijft optioneel.

---

## Relevantie boven volledigheid

Liever één waardevolle hint dan twintig irrelevante meldingen.

---

# 12. Succescriteria

De Meeting Buddy is succesvol wanneer gebruikers:

* minder notities hoeven te maken;
* minder zaken vergeten;
* beter voorbereid zijn;
* minder tijd kwijt zijn aan uitwerken;
* meer aandacht hebben voor de deelnemers;
* vertrouwen krijgen dat belangrijke informatie niet verloren gaat.

Wanneer gebruikers na een vergadering zeggen:

> "Ik hoefde niet bang te zijn dat ik iets zou vergeten."

dan heeft Meeting Buddy zijn primaire doel bereikt.

---

# 13. Relatie met volgende RFC's

Deze RFC beschrijft uitsluitend de visie en functionele uitgangspunten.

De verdere uitwerking volgt in:

* **RFC-MeetingBuddy-02** – Architectuur
* **RFC-MeetingBuddy-03** – Functionele specificatie
* **RFC-MeetingBuddy-04** – Technische uitwerking

Deze documenten bouwen voort op de ontwerpprincipes die in deze RFC zijn vastgelegd.
