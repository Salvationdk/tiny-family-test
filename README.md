# Tiny Family — offentlig testversion 0.7.1

Tiny Family er en Home Assistant-integration til familiekort, GPS-ruter, opdagelse af steder, 30-dages turhistorik, beskeder, SOS og familieadvarsler.

**Testversion:** Integrationen er stadig under praktisk afprøvning. SOS er ikke en certificeret nødtjeneste, og Home Assistant-notifikationer garanterer ikke levering på en telefon.

## Nyt i 0.7.1 – valgfri vejtilpasning (map matching)
- Administrator kan aktivere en **OSRM Match-server** under **Administration → Vejtilpasning / OSRM**. Funktionen er deaktiveret som standard.
- Sæt eksempelvis `http://192.168.1.50:5000` for en selvhostet OSRM-server på lokalnetværket. OSRM-serveren skal allerede være oprettet og indeholde vejkort for området; Tiny Family installerer ikke selv OSRM.
- På **Kort → Tidslinje** kan en familiebruger aktivere **Følg vejene** for den valgte person og dato. Kun efter dette valg sendes udvalgte GPS-koordinater og tidsstempler til den konfigurerede OSRM-server.
- En ekstern server skal have HTTPS. En lokal OSRM-server er det mest private valg. Del ikke familiens positioner med offentlige routingtjenester uden at være klar over, hvor oplysningerne sendes hen.
- OSRM Matching accepteres kun ved tilstrækkelig sandsynlighed. Originale GPS-positioner bevares, mens vejruten vises som separat **cyanfarvet Tiny Neon-linje**. Ved usikkert match, GPS-huller eller serverfejl vises den oprindelige rute.
- Match beregnes ved forespørgsel, caches midlertidigt og gemmes **ikke** som erstatning for den rå GPS-historik.
- **Bemærk:** Kortjustering kræver nok faktisk indsamlede målepunkter. Et langt GPS-udfald kan ikke rekonstrueres sikkert.

## Fra 0.7.0 – datobaseret GPS-tidslinje på familiekortet
- Vælg en person og en dato, og træk gennem dagens GPS-spor, hastigheder, batteri og registrerede ophold i **samme kortvisning**.
- Mobilkortet har et kompakt **Tiny Neon**-betjeningspanel oven på kortet; persondetaljer og tekniske værktøjer fylder ikke længere skærmen og kræver ikke sidescroll på kortfanen.
- Faktiske GPS-fix arkiveres lokalt i `tiny_family_timeline.sqlite3` med op til **365 dages historik**, også efter Home Assistant-genstart. Eksisterende 24-timers spor og 30-dages aktivitetsdata importeres i det omfang, de stadig findes.
- Flyttede GPS-fix gemmes med mindst 5 sekunders interval i stedet for den gamle frasortering på 30 sekunder. Stillestående fix opsummeres typisk hvert minut. Det giver flere reelle rutepunkter, men kan **ikke genskabe vejforløb, som telefonen ikke sendte**.
- GPS-afbrydelser og gamle privatmarkerede punkter bliver ikke forbundet af en kunstig linje. Historiske GPS-punkter udstilles kun via en autoriseret API, ikke som almindelige HA-entitetsattributter.
- Tidligere kalenderdage kan vælges én ad gangen; arkivet har automatisk lokal sletning efter 365 dage for at begrænse lagrings- og privatlivsrisiko. Brugernes egen datasletning omfatter også SQLite-arkivet.
- **Vigtigt:** Historik før denne opdatering kan kun genskabes fra de gamle, endnu eksisterende lokale data, ikke automatisk fra hele Home Assistant Recorder.

## Rettelser i 0.6.10 – stabilitet og automatiseringer
- Sensorer og binære sensorer opdateres nu på Home Assistants event loop, også hvis opdateringen oprindeligt kommer fra en worker-tråd.
- Companion-opdateringslyttere bruger Home Assistants `@callback`, så de ikke utilsigtet afvikles i executor-tråde.
- `person_timeline.log_notification` accepterer Home Assistants interne automationskontekst uden en indlogget bruger. Manuelle brugerbaserede kald er fortsat kun for administratorer. Andre services, der ændrer personer, zoner eller historik, bevarer deres adgangskontrol.
- Regressionstests for worker-tråde og automatisk systemlogging er tilføjet til GitHub Actions.

## Fra 0.6.9 – Tiny Neon på kortet
- Personmarkører viser aktuel hastighed (km/t), batteriprocent og registreret opholdstid på familiekortet.
- Hastighed og opholdstid skjules, når GPS-positionen er forældet; ukendte målinger mærkes som utilgængelige.
- Markørerne bruger den afdæmpede **Tiny Neon**-stil (cyan/lilla) i både lyst og mørkt Home Assistant-tema.
- Oprettelse af fælles steder ligger i et sammenklappeligt kortpanel, som først indlæser kortet, når det åbnes.
- Beskeder har kompakte handlinger og tekniske leveringsdetaljer under et udvideligt afsnit.

## Fra 0.6.8 – Zenly-inspireret mobilvisning
- Fire faner: **Kort**, **Steder**, **Aktivitet** og **Beskeder**. Kortet åbner først, og administration findes via skjoldikonet.
- Vælg én Companion-telefon pr. person. GPS, batteri, opladning og aktivitet tilknyttes automatisk fra **samme** Home Assistant-enhed, uden særskilte sensorvalg.
- Et familiemedlem kan oprette fælles steder fra et kortpunkt, koordinater eller frisk telefon-GPS. Stederne bliver synlige for alle tilknyttede familiemedlemmer på kortet.
- Opretteren kan rette/slette egne fælles steder. Administrator kan altid rette/slette **alle** fælles steder og se indlærte destinationer og opholdsforslag fra samtlige tilknyttede personer.
- Administrator kan bruge registrerede ophold til at oprette et fælles sted eller en Home Assistant-zone.
- Privat historik deles ikke automatisk, når et nyt fælles sted oprettes. Ingen Ghost Mode- eller sporingspauseknap i Tiny Family.

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

Home Assistant-domæne: `person_timeline`. Version: `0.7.1`. Integrationens filer ligger i `custom_components/person_timeline/`.

Dette offentlige testrepository indeholder kun installationskode og dokumentation, ikke den private udviklingshistorik, personlige GPS-ruter, telefonnumre eller Home Assistant-konfigurationsdata.
