# Tiny Family — offentlig testversion 0.8.6

<!-- BEGIN: Salvationdk repository metrics -->
[![Release downloads](https://img.shields.io/github/downloads/Salvationdk/tiny-family-test/total?label=Release%20downloads&style=flat-square)](https://github.com/Salvationdk/tiny-family-test/releases)
[![Stars](https://img.shields.io/github/stars/Salvationdk/tiny-family-test?style=flat-square)](https://github.com/Salvationdk/tiny-family-test/stargazers)
[![Forks](https://img.shields.io/github/forks/Salvationdk/tiny-family-test?style=flat-square)](https://github.com/Salvationdk/tiny-family-test/forks)
[![Issues](https://img.shields.io/github/issues/Salvationdk/tiny-family-test?style=flat-square)](https://github.com/Salvationdk/tiny-family-test/issues)
[![Pull requests](https://img.shields.io/github/issues-pr/Salvationdk/tiny-family-test?style=flat-square)](https://github.com/Salvationdk/tiny-family-test/pulls)
[![Last commit](https://img.shields.io/github/last-commit/Salvationdk/tiny-family-test?style=flat-square)](https://github.com/Salvationdk/tiny-family-test/commits)

<sub>Release-downloads tæller kun filer vedhæftet GitHub Releases. HACS-installationer, kode-ZIP'er og Actions-artefakter indgår ikke. [Besøg og kloninger](https://github.com/Salvationdk/tiny-family-test/graphs/traffic) er kun synlige for brugere med de nødvendige rettigheder.</sub>

[![Registrerede visninger](https://raw.githubusercontent.com/Salvationdk/tiny-family-test/metrics-history/metrics/badges/visits.svg)](https://github.com/Salvationdk/tiny-family-test/blob/metrics-history/metrics/dashboard.md)
[![Registrerede kloninger](https://raw.githubusercontent.com/Salvationdk/tiny-family-test/metrics-history/metrics/badges/clones.svg)](https://github.com/Salvationdk/tiny-family-test/blob/metrics-history/metrics/dashboard.md)

**[Historisk statistik og downloads pr. version](https://github.com/Salvationdk/tiny-family-test/blob/metrics-history/metrics/dashboard.md)** · [Daglig dataindsamling](https://github.com/Salvationdk/tiny-family-test/actions/workflows/repository-metrics.yml)

<sub>Besøgs- og kloningstællerne starter først efter opsætning af det private METRICS_TRAFFIC_TOKEN; indtil da viser de "afventer token".</sub>
<!-- END: Salvationdk repository metrics -->


Tiny Family er en Home Assistant-integration til familiekort, GPS-ruter, opdagelse af steder, datobaserede tidslinjer, beskeder, SOS og familieadvarsler.

**Testversion:** Integrationen er stadig under praktisk afprøvning. SOS er ikke en certificeret nødtjeneste, og Home Assistant-notifikationer garanterer ikke levering på en telefon.

## Nyt i 0.8.6 – zonekort, selvstændige destinationer og kladder
- **Steder → Zoner:** Administrator kan tegne og redigere både Home Assistant-cirkelzoner (centrum og radius) og Tiny Family-polygonzoner (3–32 hjørner) direkte på mobilkortet. Andre familiemedlemmer kan se zonerne. Eksisterende Home Assistant-zoner vises; kun zoner, som Home Assistant tillader at redigere via lagring, kan ændres her.
- **Zoner og destinationer er forskellige:** Kortet viser også familiens fælles destinationer. En zone kan få et fælles destinationspunkt i centrum, men separate destinationer kan også ligge inden for en zone. Et indlært ophold inde i en HA-zone bliver ikke automatisk omdøbt til zonen. Polygonzoner er Tiny Family-områder og bliver ikke `zone.*`-entiteter i Home Assistant.
- **Oprydning i forslag:** Nærliggende registreringer inden for 35 m grupperes i visningen, mens de oprindelige opholdsdata og deres ejerskab bevares. Allerede oprettede, delte eller navngivne steder skjules fra forslaglisten. Et forsøg på at oprette et eksisterende fælles sted på næsten samme punkt – eller med samme navn inden for 75 m – returnerer det eksisterende sted frem for at oprette en dublet. Administrator kan fortsat rette og slette hvert ophold separat.
- **Kladder bevares:** Indtastede stednavne, koordinater, zonehjørner, åbne redigeringer, beskedudkast og administrationens endnu ikke gemte felter overlever panelnavigation eller genindlæsning i samme browserfane i op til 24 timer. Kladder gemmes kun i browserens session og er knyttet til den indloggede Home Assistant-konto. Farlige slettebekræftelser gemmes aldrig.
- **En mere ensartet mobilvisning:** Zoneeditoren og øvrige stedfaner bruger Tiny Neon-layoutet med indvendig rulning. Hvert familiemedlems indstillinger er nu sammenklappet under eget navn. Hvis dagens tidslinje har ture, men ingen arkiverede GPS-målinger, står det tydeligt, at ruten ikke kan rekonstrueres.

## Nyt i 0.8.5 – hurtig historik, forsigtige vejgæt og GPS-advarsler
- **Tidslinjedato åbnes uden vejventetid:** Den lokale SQLite-historik vises straks efter API-svaret. Bekræftet vejtilpasning og eventuelle vejgæt hentes i en **anden, asynkron forespørgsel**, så Overpass ikke holder datoens GPS-data tilbage. Ved fejl forbliver tidslinjen brugbar.
- **To slags vejstykker:** Faktiske, sammenhængende OSM-match tegnes med fuldt optrukket cyan. Forsigtige *anslåede* veje mellem sparsomme GPS-fix tegnes med **stiplet gul streg** og forklarende tekst. Motoren forsøger først at genbruge tidligere matchede vejforløb for **samme person og den samme seer**, derefter OSM-veje. Gæt er ikke målt kørsel; de bruges ikke som GPS-data til distance, hastighed, zonealarmer eller indlæring. Skjulte private GPS-afbrud forbindes aldrig af gæt.
- **Tidslinjefart og GPS-afbrud:** Hvis telefonen kun leverer 0 km/t trods registreret bevægelse, får dagsvisningen en diagnostisk advarsel. Under et anslået rutestykke kan afspilningsmarkøren følge en tydeligt markeret anslået position, og fart står som *ukendt*.
- **Advarsel om batterisparetilstand:** Administrator kan vælge automatisk push til telefonens **egen bruger**, hvis dens Companion-batterisparer er aktiv ved **over 30 %** strøm. Teksten advarer om upræcis/forsinket GPS og anbefaler at slå batterisparer fra, når opladning er mulig. Kræver både aktiv fælles notifikationsindstilling, kategorien og en fungerende Companion-pushmodtager; gentages ikke ved vedvarende batterisparetilstand og har seks timers køletid ved gentagne aktiveringer.

## Nyt i 0.8.4 – indbygget vejtilpasning er tændt som standard
- **Ny installation:** Indbygget OpenStreetMap/Snap-on-road er aktiveret fra første opsætning. Ingen OSRM-server eller API-nøgle kræves.
- **Eksisterende installation:** Hvis vejtilpasningen aldrig er gemt som et administratorvalg, opgraderes den tidligere deaktiverede standard automatisk til **til** ved næste opstart. Et udtrykkeligt administratorvalg om **fra** bevares. Fremover kan administrator stadig slå vejtilpasningen til eller fra i Administration → Vejtilpasning.
- **Databeskyttelse:** Når en tidslinjedato med egnede GPS-punkter vises, kan motoren hente vejgeometri fra OpenStreetMap Overpass. Den sender kun et afgrænset geografisk område, ikke person-id, rå GPS-punktliste eller tidsstempler. Historiske råmålinger ændres ikke.

## Nyt i 0.8.3 – tidslinje, vejtilpasning og registrerede steder
- **Tidslinjeafspilning:** Starter ved første GPS-måling, når man trykker Afspil. **1× er reel tid**, mens 5×, 20×, 60× og 300× kan vælges på kortet. Klokken viser sekunder; den målte fart vises undervejs. Ved pause og manuel spoling kan personen fortsat følges på kortet.
- **Personen i centrum:** Valgt person følges under afspilning og spoling. Ved personskift nulstilles datoen til **i dag**, og den tidligere persons rute fjernes straks. Hvis der endnu ikke er dagens historik, bruges den valgte persons sidste kendte position som kortcentrum.
- **Tættere vejtilpasning:** Den indbyggede motor accepterer nu sikre, sammenhængende Companion GPS-fix med op til fem minutter imellem. På matchede dele tegnes den faktiske OSM-vejgeometri frem for en ekstra rå GPS-streg; afspilningsmarkøren følger vejkurverne. Huller over fem minutter forbindes ikke kunstigt. Fra 0.8.4 er den indbyggede motor aktiv som standard. Hvis OSM-data ikke er tilgængelige, er råmålingerne fallback.
- **Stedforslag afsluttes:** Når et forslag bliver oprettet som fælles sted eller får et navn, forsvinder det fra listen over forslag. Det findes under fælles steder eller registrerede ophold i stedet. **Kun administrator kan senere rette eller slette** fælles og navngivne opholdssteder; administrator kan også markere dem private.

## Nyt i 0.8.2 – administratorstyring, stedforslag og GPS-drift
- **Telefonens sensorer:** Administrator vælger pr. tilknyttet telefon batteri, opladning, aktivitet og batterisparestatus. Alle fire er valgt som standard; GPS er altid påkrævet. Status viser aktiv, utilgængelig, deaktiveret i HA eller mangler fra Companion. Kun sensorer på **samme HA-enhed** bruges. App-tilladelser aktiverer ikke automatisk sensorens kontakt; hvis den mangler, skal telefonens ejer slå den til under **Companion-app → Administrer sensorer**. Tiny Family kan ikke fjernaktivere appens kontakter.
- **GPS-glitches:** Positionsspring mistænkt for drift, især under batterisparing, holdes tilbage, indtil næste GPS-fix bekræfter bevægelsen. Ubekræftede hop bruges ikke til zoner, fart, ture, ophold eller tidslinjer. Reelle store flytninger kan starte et nyt rutestykke uden en opfundet forbindelse. Status viser nylige frasorterede hop; beskyttelsen er heuristisk, ikke perfekt.
- **Kun administrator kan slette steder, GPS-tidslinjer og turarkiv.** Gælder også API og servicen `delete_place_suggestion`. Fra 0.8.3 kan kun administrator også rette etablerede stednavne. Brugere kan fortsat rydde egne indlærte afgangsobservationer uden at ændre administratorens indlæringsvalg.
- **Stedforslag vises på et indbygget kort** under Steder → Forslag hos alle tilknyttede medlemmer. Gentagne ophold er som standard fælles; administrator kan gøre hvert forslag privat (så vises det kun for administrator og personen selv). Historiske Ghost-markeringer respekteres. Et sted er et registreret ophold; en **HA-zone** er et administratoroprettet område med radius, der anvendes til ankomst, afgang og alarmer.
- **Lagring:** GPS-tidslinjer gemmes i 365 dage som standard. Administrator kan vælge 30–3650 dage; en kortere periode sletter ældre arkivdata efter genindlæsning. Den indbyggede vejtilpasning fungerer også for tidligere datoer, når de åbnes, og det beregnede resultat caches i lokal SQLite **pr. visning og person**. Originale GPS-fix ændres aldrig. Massebehandling af alle datoer på én gang udføres ikke, da det kan overbelaste OpenStreetMap Overpass.
- **Historisk destinationsforudsigelse:** Administrator vælger global rutineindlæring og hvilke familiemedlemmer den gælder. Når den er aktiveret, analyserer Tiny Family op til 30.000 reelle, lokale GPS-målinger pr. person fra arkivet, og genkender gentagne ankomsttidspunkter og konkrete rute-tilgange til kendte steder. Gentagen historik vægter tungt i destinationsgættet. Uden tilstrækkelig historik virker den eksisterende fallback med bevægelsesretning, afstand, besøgshyppighed og fart fortsat. Analyser opdateres højst én gang i timen pr. person. Ingen historik sendes til en ekstern AI-tjeneste, og beregningen kan ikke love korrekt destination eller ETA.

**Privatliv:** Familiemedlemmers gentagne ophold kan vise følsomme adresser, før en administrator har nået at gøre dem private. Gennemgå stedforslag med familien før ibrugtagning. En privat markering skjuler kun forslag i Tiny Family, ikke GPS fra Home Assistant selv eller allerede delte kopier. Administratorstyring af telefondata erstatter ikke telefonens OS-tilladelser.

## Nyt i 0.8.1 – indbygget Snap-on-road
- **Indbygget vejtilpasning** i Tiny Family: Ingen OSRM-server eller API-nøgle er påkrævet. Motoren bygger en lokal vejgraf af OpenStreetMap-geometri og finder sammenhængende vejruter under hensyn til ensretning.
- I **Administration → Vejtilpasning** vælges `Indbygget OpenStreetMap` som standard, eller eksisterende selvhostet OSRM som valgfrit alternativ. Fra version 0.8.4 er den indbyggede funktion som standard aktiveret, men administrator kan slå den fra.
- I 0.8.1 skulle den enkelte bruger aktivt vælge korttilpasning. Fra 0.8.2 styres dette af administrator, og en historisk dato tilpasses automatisk ved åbning, hvis funktionen er slået til. Den indbyggede motor henter da vejgeometri via HTTPS fra Overpass. Kun rutens geografiske afgrænsning sendes ud; ingen person-id, rå GPS-punktliste eller tidsstempler sendes til Overpass.
- Vejgeometri caches i hukommelsen i op til 24 timer. Forespørgsler er begrænsede; lange ture, manglende vejdata, serveroverbelastning eller usikre GPS-prøver kan give **delvis vejtilpasning**. Rå GPS-spor vises fortsat, hvor match ikke kan beregnes.
- Originale koordinater, historisk SQLite-database, afspilning og personcentreret kort ændres ikke. Det er et vejforslag baseret på de registrerede målepunkter, ikke et bevis for den kørte rute.
- Dette er **ikke fuldt offline**: Hvis Overpass er utilgængelig, vises originalsporet. For helt lokal vejmatching uden eksterne OSM-forespørgsler kræves en fremtidig import af lokale vejdata.

## Nyt i 0.8.1 – stabil Min dag og dansk højttalerbesked
- Retter en `insertBefore`-fejl, når brugerens personbinding eller privatlivsindstilling ikke er klar. Ingen personlige data slettes.
- Ved ny opsætning vælges hver persons Companion-GPS-telefon, Home Assistant-konto og eventuel smart speaker med TTS-stemme.
- Administration kan ændre samme bindinger senere.
- Beskeder kan eksplicit sendes som almindelig telefon-push eller **læses op på dansk** til én navngiven modtagers valgte højttaler.
- Højttalerbeskeder er fravalgte som standard, sendes aldrig automatisk eller som SOS og kræver en konfigureret TTS-stemme. Oplæsningen kan høres af andre i rummet.
- Den eksisterende OSRM-baserede vejtilpasning og 365-dages tidslinje er uændret.

## Nyt i 0.8.0 – navn, domæne og alarmstyring
- Tiny Family registrerer selv batteri-, fart-, zone-, tur- og GPS-hændelser og gemmer dem i systemhistorikken uden særskilte Home Assistant-automatiseringer.
- Under **Administration → Alarmer og fartgrænser** kan administrator se to kendte gamle `Tiny Family`-automatiseringer og deaktivere aktive eksemplarer med bekræftelse. Automatiseringerne slettes ikke.
- Kontrollér Companion-telefon, notifikationsmodtagere og aktiverede alarmkategorier før oprydning. Systemhistorik og eksisterende GPS-arkiver ændres ikke.
- Integrationsdomænet `tiny_family` bevares indtil en særskilt sikker migrering, så eksisterende enheder, historik og config entries ikke brydes.

## Mobilforbedringer i 0.7.1 – én skærm pr. hovedfane
- **Kort:** Under 24-timers afspilning og manuel tidslinjesøgning følger kortet den valgte person i fast gadeniveau-zoom; markeringsikonet viser personens initialer. Liveopdateringer afbryder ikke historisk afspilning.
- **Steder:** Kompakt trevejsvalg mellem Fælles, Mine ophold og administratorens Forslag. Oprettelse af steder og egne redigeringer bevares i den aktive visning.
- **Aktivitet:** Filtrér direkte mellem Alle, Ture og Ophold uden at forlade skærmen.
- **Beskeder:** Skift mellem Skriv besked og Indbakke på samme skærm. Svar åbner beskedfeltet med korrekt modtager; hurtigbeskeder ligger sammenklappet.
- **Administration:** Indstillinger er organiseret efter Familiemedlemmer, Alarmer, Rutiner, Vejtilpasning og øvrige værktøjer, mens Gem forbliver tilgængelig.
- Alle faner deler **Tiny Neon**, respekterer mobilens sikre skærmområder og holder bundnavigationen fast. Lange datalister ruller inde i en afgrænset sektion, så selve siden ikke bliver længere end telefonens skærm.

## Fra 0.7.1 – valgfri vejtilpasning (OSRM som alternativ)
- Administrator kan aktivere en **OSRM Match-server** under **Administration → Vejtilpasning / OSRM**. Funktionen er deaktiveret som standard.
- Sæt eksempelvis `http://192.168.1.50:5000` for en selvhostet OSRM-server på lokalnetværket. OSRM-serveren skal allerede være oprettet og indeholde vejkort for området; Tiny Family installerer ikke selv OSRM.
- Siden 0.8.2 starter **Følg vejene** automatisk ved visning af datoen, hvis administrator har slået det til. Ved ekstern OSRM sendes da udvalgte, synlige GPS-koordinater og tidsstempler til den konfigurerede server. Vælg den indbyggede motor, hvis du ikke vil sende rå ruter ud.
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
- Tidligere kalenderdage kan vælges én ad gangen; arkivet har automatisk lokal sletning efter administratorens periode (standard 365 dage). Fra 0.8.2 kan kun administrator slette tidslinjer og turarkiv manuelt.
- **Vigtigt:** Historik før denne opdatering kan kun genskabes fra de gamle, endnu eksisterende lokale data, ikke automatisk fra hele Home Assistant Recorder.

## Rettelser i 0.6.10 – stabilitet og automatiseringer
- Sensorer og binære sensorer opdateres nu på Home Assistants event loop, også hvis opdateringen oprindeligt kommer fra en worker-tråd.
- Companion-opdateringslyttere bruger Home Assistants `@callback`, så de ikke utilsigtet afvikles i executor-tråde.
- `tiny_family.log_notification` accepterer Home Assistants interne automationskontekst uden en indlogget bruger. Manuelle brugerbaserede kald er fortsat kun for administratorer. Andre services, der ændrer personer, zoner eller historik, bevarer deres adgangskontrol.
- Regressionstests for worker-tråde og automatisk systemlogging er tilføjet til GitHub Actions.

## Fra 0.6.9 – Tiny Neon på kortet
- Personmarkører viser aktuel hastighed (km/t), batteriprocent og registreret opholdstid på familiekortet.
- Hastighed og opholdstid skjules, når GPS-positionen er forældet; ukendte målinger mærkes som utilgængelige.
- Markørerne bruger den afdæmpede **Tiny Neon**-stil (cyan/lilla) i både lyst og mørkt Home Assistant-tema.
- Oprettelse af fælles steder ligger i et sammenklappeligt kortpanel, som først indlæser kortet, når det åbnes.
- Beskeder har kompakte handlinger og tekniske leveringsdetaljer under et udvideligt afsnit.

## Fra 0.6.8 – Zenly-inspireret mobilvisning
- Fire faner: **Kort**, **Steder**, **Aktivitet** og **Beskeder**. Kortet åbner først, og administration findes via skjoldikonet.
- Vælg én Companion-telefon pr. person. Sensorer tilknyttes fra **samme** Home Assistant-enhed; fra 0.8.2 kan administrator godkende eller fravælge hver sensorkategori.
- Et familiemedlem kan oprette fælles steder fra et kortpunkt, koordinater eller frisk telefon-GPS. Stederne bliver synlige for alle tilknyttede familiemedlemmer på kortet.
- Fælles steder kan oprettes af familiemedlemmer. Fra 0.8.3 kan kun administrator rette og slette dem. Gentagne opholdsforslag er synlige for familien, medmindre administrator gør dem private; oprettede forslag vises ikke igen i forslaglisten.
- Administrator kan bruge registrerede ophold til at oprette et fælles sted eller en Home Assistant-zone.
- Privat historik deles ikke automatisk, når et nyt fælles sted oprettes. Ingen Ghost Mode- eller sporingspauseknap i Tiny Family.

**Vigtigt:** Tiny Family kan ikke tilsidesætte Android/iOS' placeringstilladelser. Personer og enheder skal være korrekt tilknyttet i Home Assistant Companion.

## Éngangsovergang til Tiny Family 0.8.0

**Integrationsdomænet er nu `tiny_family`.** Det er en ny installation i
Home Assistant, ikke en almindelig opdatering af `person_timeline`.

1. Tag en **fuld Home Assistant-backup**, og notér dine person-/telefonbindinger.
2. Fjern den gamle Tiny Family-integration under **Indstillinger → Enheder og tjenester**.
3. Fjern den forældede mappe `custom_components/person_timeline/`, hvis
   Marketplace/HACS ikke selv har fjernet den.
4. Installér dette testrepository igen (nu version 0.8.0), genstart Home
   Assistant og tilføj **Tiny Family** som ny integration.
5. Vælg familiemedlemmer, Companion-telefoner, brugere og notifikationer
   igen. Kontrollér GPS-historik, zoner og alarmer før du rydder gamle entiteter.

Ved første opstart kopierer Tiny Family eventuelle eksisterende
`person_timeline_places.json` og `person_timeline_historik.json` til
`tiny_family_places.json` og `tiny_family_historik.json`, hvis nye filer
ikke findes. Gamle filer slettes ikke. SQLite-arkivet
`tiny_family_timeline.sqlite3` og eksisterende `tiny_family_*` data
fortsætter uændret. Der sker **ingen automatisk omskrivning** af den gamle
Home Assistant-konfigurationspost; denne engangsovergang kræver genopsætning.

## Installation med Home Assistant Marketplace (2026.11 eller nyere)

1. Lav først en fuld Home Assistant-backup.
2. Åbn **Indstillinger → Marketplace → Add from link**.
3. Indsæt `https://github.com/Salvationdk/tiny-family-test`, og vælg **Integration**, hvis du bliver spurgt.
4. Åbn **Tiny Family → Install** og tilføj integrationen via **Indstillinger → Enheder og tjenester**, hvis den ikke åbnes automatisk.
5. I fanen **Administration** vælger du familiemedlemmer, deres Home Assistant-brugere og den relevante Companion-telefon.
6. Vælg telefonens pushmodtager, kontrollér sensorerne og gem. Aktiver først automatiske alarmer, når modtagerne er verificeret.

Tidligere HACS: Tilføj samme URL via **HACS → Custom repositories** med typen **Integration**.

## Sikker test

Brug helst en separat testinstallation. Hvis du tidligere har brugt `tiny_family:` i YAML, må den gamle YAML-instans ikke være aktiv samtidig med den nye UI-konfiguration uden en gennemgået migration. Gem backup af både historik, scripts og `.storage`.

Ghost Mode fra tidligere installationer ændrer ikke Home Assistants `person`, `device_tracker` eller Recorder-data. Native widgets skal tilføjes gennem den officielle Companion-app. Intet officielt HACS-katalogbidrag er indsendt.

## Teknisk

Home Assistant-domæne: `tiny_family`. Version: `0.8.6`. Integrationens filer ligger i `custom_components/tiny_family/`.

Dette offentlige testrepository indeholder kun installationskode og dokumentation, ikke den private udviklingshistorik, personlige GPS-ruter, telefonnumre eller Home Assistant-konfigurationsdata.
