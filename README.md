# Tiny Family — offentlig testversion 0.6.6

Tiny Family er en Home Assistant-custom integration med familiekort, GPS- og turhistorik, geofences, administratorstyret Ghost Mode, fartalarmer og familiekommunikation.

**Status: testudgave.** Ikke optaget i HACS' officielle katalog. Ikke beregnet som et certificeret nød- eller alarmsystem.

## Installation direkte fra repository

### HACS
1. Åbn **HACS** i Home Assistant og vælg **Custom repositories**.
2. Indsæt `https://github.com/Salvationdk/tiny-family-test` og vælg typen **Integration**.
3. Download **Tiny Family** og genstart Home Assistant.
4. Vælg **Indstillinger → Enheder og tjenester → Tilføj integration → Tiny Family**.
5. Vælg dine `person.*`-entiteter, og konfigurer konti, sensorer og telefoner i Tiny Family-panelets editor.

### Home Assistant Marketplace
På Home Assistant-versioner med Marketplace: Brug **Add from link** med repository-adressen ovenfor, hvis den installerede Marketplace-version understøtter denne integrationsform.

## Før du tester

- Lav en **fuld Home Assistant-backup**. Test først på en separat testinstallation, især hvis du allerede bruger `person_timeline` i YAML.
- Tilføj ikke samtidig gammel YAML-konfiguration og ny UI-konfiguration uden at gennemgå migrationen.
- Automatiske notifikationer er fravalgt som standard. Kontrollér udvalgte modtagere før aktivering.
- GPS, rutehistorik, beskeder og personkoblinger er private driftsdata og hører **ikke** hjemme i dette repository.
- Ghost Mode styrer Tiny Familys egne delingsregler; det ændrer ikke Home Assistants almindelige `person`-/`device_tracker`-entiteter eller Recorder-data.
- SOS/Check-in er hjælpenotifikationer, ikke en erstatning for 112. Accept fra Home Assistant garanterer ikke levering til telefonen.

Pakkens HA-domæne er fortsat `person_timeline` af kompatibilitetshensyn. Kortfliser hentes normalt via Home Assistants korttjeneste. Flere funktioner kræver Home Assistant Companion og korrekte GPS-/notify-tilladelser.

Den offentlige pakke indeholder kun den installationsrelevante integration og tilhørende open source-kortbibliotekslicens; ingen privat Git-historik, familieoplysninger eller lokale HA-data.
