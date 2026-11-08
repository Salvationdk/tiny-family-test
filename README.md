# Tiny Family — offentlig testversion 0.6.7

Tiny Family er en Home Assistant-integration til familiekort, GPS-ruter, opdagelse af steder, 30-dages turhistorik, beskeder, SOS og familieadvarsler.

**Testversion:** Integrationen er stadig under praktisk afprøvning. SOS er ikke en certificeret nødtjeneste, og Home Assistant-notifikationer garanterer ikke levering på en telefon.

## Nyt i 0.6.7
- Mobilvenlig navigation med store trykflader og de vigtigste GPS-, batteri- og statusoplysninger øverst på **Min dag**.
- Særskilt **Administration**-fane, som kun vises for Home Assistant-administratorer.
- Administrator vælger én Companion-telefon til hver person. GPS-trackerens Home Assistant-enheds-ID bruges til automatisk at knytte telefonens batteri-, opladnings- og aktivitetssensorer.
- Hvis en sensor ikke er registreret på telefonens enhed, kan administrator vælge den manuelt under **Avanceret**. Pushmodtagere vælges separat for at undgå fejlbeskeder til en anden telefon.
- Almindelige brugere har ikke en Ghost Mode- eller GPS-pauseknap. Nye forsøg på at aktivere sådanne fravalg gennem integrations-API'et afvises. Historiske private GPS-data fra tidligere opsætninger bevares efter de gamle adgangsregler.
- Kort, zoner, polygoner, fartalarmer, historik, beskeder og personlige datafunktioner er bevaret.

**Vigtigt:** Tiny Family kan ikke tilsidesætte Android/iOS' placeringstilladelser. Personer og enheder skal være korrekt tilknyttet i Home Assistant Companion.

## Installation med Home Assistant Marketplace (2026.11 eller nyere)

1. Lav først en fuld Home Assistant-backup.
2. Åbn **Indstillinger → Marketplace → Add from link**.
3. Indsæt `https://github.com/Salvationdk/tiny-family-test`, og vælg **Integration**, hvis du bliver spurgt.
4. Åbn **Tiny Family → Install** og tilføj integrationen via **Indstillinger → Enheder og tjenester**, hvis den ikke åbnes automatisk.
5. I fanen **Administration** vælger du familiemedlemmer, deres Home Assistant-brugere og den relevante Companion-telefon.
6. Vælg telefonens pushmodtager, kontrollér sensorerne og gem. Aktiver først automatiske alarmer, når modtagerne er verificeret.

Tidligere HACS: Tilføj samme URL via **HACS → Custom repositories** med typen **Integration**.

## Sikker test

Brug helst en separat testinstallation. Hvis du tidligere har brugt `person_timeline:` i YAML, må den gamle YAML-instans ikke være aktiv samtidig med den nye UI-konfiguration uden en gennemgået migration. Gem backup af både historik, scripts og `.storage`.

Ghost Mode fra tidligere installationer ændrer ikke Home Assistants `person`, `device_tracker` eller Recorder-data. Native widgets skal tilføjes gennem den officielle Companion-app. Intet officielt HACS-katalogbidrag er indsendt.

## Teknisk

Home Assistant-domæne: `person_timeline`. Version: `0.6.7`. Integrationens filer ligger i `custom_components/person_timeline/`.

Dette offentlige testrepository indeholder kun installationskode og dokumentation, ikke den private udviklingshistorik, personlige GPS-ruter, telefonnumre eller Home Assistant-konfigurationsdata.
