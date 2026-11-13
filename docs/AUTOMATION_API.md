# Tiny Family som byggesten i Home Assistant — 0.8.12

Tiny Family er ikke kun et kort. Integrationen offentliggør sensorer,
hændelser og handlinger (*actions/services*), så andre dashboards,
automationer og custom integrationer kan genbruge resultaterne.

## Hvilken adgang skal jeg vælge?

| Vil du… | Brug | Hvorfor |
|---|---|---|
| Vise en gemt polygon i et specialkort | `sensor.tiny_family_polygon_<id>` → attributten `geojson` | Indeholder selve områdets hjørner som standard GeoJSON. |
| Reagere på, at en bestemt person går ind/ud | `binary_sensor.tiny_family_<person>_polygon_<id>` | Registreret HA-entitet; almindelig `state`-trigger, også i andre dashboards. |
| Reagere på ind-/udgang og få områdets navn med | `tiny_family_polygon_entered` / `tiny_family_polygon_left` | Hændelsen har `polygon_id`, `polygon_name`, `person`, `timestamp`. |
| Teste vilkårlige koordinater mod **alle** polygoner | Handlingen `tiny_family.evaluate_location` | Genbruger Tiny Familys point-in-polygon-motor fra YAML, også til andre GPS-enheder. |
| Teste koordinater mod Home Assistants cirkelzoner | `tiny_family.evaluate_location` → `circles` | Kombinerer almindelige `zone.*`-cirkler og Tiny Family-polygoner uden at ændre dem. |
| Beregne luftlinjeafstand og et forsigtigt ETA-skøn | `tiny_family.evaluate_location` med målkoordinater | Genbruger Tiny Familys afstands- og ETA-udregninger; viser `null`, når data ikke kan give et forsvarligt estimat. |
| Udregne fart/bevægelse mellem to selvvalgte GPS-fix | `tiny_family.analyze_motion` | Samme hastighedsvurdering som under live tur; viser om hastigheden kommer fra telefonen eller er beregnet fra GPS. |
| Opsummere en indsendt GPS-rute | `tiny_family.analyze_route` | 2–200 GPS-fix; aggregerer distance, varighed, topfart, afbrud og antal fartkilder uden at gemme koordinaterne. |
| Bruge personens aktuelle hastighed i en anden automation | `sensor.tiny_family_<person>_current_speed` og `_speed_source` | Ingen opdigtet 0 ved ukendt fart; kilden er `phone`, `gps_estimate` eller `unavailable`. |
| Hente en persons dagsoversigt | `tiny_family.get_day_summary` | Eksisterende svarservice; kræver et identificerbart, autoriseret HA-brugerkontekst. |
| Bruge en normal Home Assistant-cirkelzone | `zone.<navn>` | Stadig Home Assistants egen cirkelzone med centrum og radius. |

`<id>` er polygonens permanente 32-tegns ID, ikke selve navnet. Find det
konkrete entitets-ID under **Indstillinger → Enheder og tjenester → Entiteter**.
Et ændret polygonnavn påvirker ikke ID'et. Ved sletning fjernes de tilhørende
entiteter; et nyoprettet område får et nyt ID.

## 1. Opret eller ændr polygon på telefonen

Åbn **Tiny Family → Steder → Zoner → Tegn eller rediger zone**.

- Tegn en polygon med 3–32 hjørner på kortet.
- Du kan vælge en eksisterende cirkel og trykke **Lav polygon ud fra cirkel**.
  Det giver en polygon med 16 hjørner, som kan trækkes til den ønskede form.
- Den oprindelige `zone.*`-cirkel bevares. Du kan have både cirkel og polygon
  samme sted, og destinationer kan ligge inde i dem.
- Gem. Sensorer oprettes/opdateres uden en Home Assistant-genstart.

Home Assistants indbyggede zonetrigger forstår **ikke** polygoner. Derfor skal
en polygon bruges via Tiny Family-entiteter, hændelser eller den geografiske
service nedenfor. Andre integrationer behøver ikke at kende Tiny Familys panel.

## 2. Brug polygonen som normal HA-sensor

For hver polygon oprettes:

1. `sensor.tiny_family_polygon_<id>` — tilstand `active` og attributterne:
   - `polygon_id` og `polygon_name`
   - `points`: `[[breddegrad, længdegrad], …]`
   - `geojson`: `{"type":"Polygon","coordinates":[[[længdegrad,breddegrad],…]]}`;
     første hjørne gentages til sidst for at lukke polygonringen.
2. `binary_sensor.tiny_family_<person>_polygon_<id>` for hver konfigureret
   person — `on` når personen er inde, `off` udenfor, `unknown` hvis
   GPS-status ikke er frisk eller personen er beskyttet af Ghost Mode.

En anden custom integration kan bruge HA's almindelige state API:

```python
polygon = hass.states.get("sensor.tiny_family_polygon_<id>")
if polygon is not None:
    geometry = polygon.attributes.get("geojson")
```

En YAML-skabelon kan læse samme data:

```jinja2
{{ state_attr('sensor.tiny_family_polygon_<id>', 'geojson') }}
```

Dette er en læsbar polygondefinition, **ikke** en automatisk `zone.*`-entitet.
En brugerdefineret kortkomponent skal selv tegne GeoJSON-geometrien.

## 3. Automation: person går ind i en polygon

Skift det markerede entitets-ID til det, du ser i din egen installation:

```yaml
alias: Person kom ind i Tiny Family-polygon
triggers:
  - trigger: state
    entity_id: binary_sensor.tiny_family_nicolaj_rusbjerg_polygon_<id>
    to: "on"
actions:
  - action: persistent_notification.create
    data:
      title: "Område registreret"
      message: "Personen er inde i den valgte polygon."
```

Du kan også bruge hændelserne i stedet for binærsensoren:

```yaml
alias: Polygon ankomst - alle Tiny Family-områder
triggers:
  - trigger: event
    event_type: tiny_family_polygon_entered
actions:
  - action: persistent_notification.create
    data:
      title: "Ankomst til {{ trigger.event.data.polygon_name }}"
      message: "{{ trigger.event.data.person }} gik ind i området."
```

Hændelser dannes ved registreret ændring mellem inde/ude på to accepterede
GPS-målinger. Første måling efter genstart fastlægger blot udgangspunktet;
den genererer ikke en falsk ankomst. Forskellige overlappende polygoner
registreres separat. Ingen rå GPS-koordinater sendes i disse hændelser.

## 4. Brug selve polygonmotoren fra YAML — også til andre enheder

Handlingen `tiny_family.evaluate_location` er en **skrivebeskyttet
beregningsservice**. Den modtager selvvalgte koordinater og svarer med
alle polygoner, der indeholder punktet. Den er ikke bundet til en Tiny
Family-person og kan bruges med f.eks. en anden `device_tracker`.

Eksempel i en automation, hvor `device_tracker.firmabil` har koordinater:

```yaml
alias: Firmabil i Tiny Family-område
triggers:
  - trigger: state
    entity_id: device_tracker.firmabil
conditions:
  - condition: template
    value_template: >-
      {{ state_attr('device_tracker.firmabil', 'latitude') is number
         and state_attr('device_tracker.firmabil', 'longitude') is number }}
actions:
  - action: tiny_family.evaluate_location
    data:
      latitude: "{{ state_attr('device_tracker.firmabil', 'latitude') | float }}"
      longitude: "{{ state_attr('device_tracker.firmabil', 'longitude') | float }}"
    response_variable: geometri
  - if:
      - condition: template
        value_template: "{{ geometri.inside_any_polygon }}"
    then:
      - action: persistent_notification.create
        data:
          title: Firmabil inde i område
          message: >-
            Match: {{ geometri.polygons | map(attribute='name') | join(', ') }}
```

Svarformat (når punktet er inde i én polygon):

```yaml
inside_any_polygon: true
polygon_count: 1
polygons:
  - id: "<32-tegns-id>"
    name: Arbejde
    entity_id: "sensor.tiny_family_polygon_<32-tegns-id>"
```

Vil du også have luftlinjeafstand og en ETA-vurdering, kan du sende:

```yaml
- action: tiny_family.evaluate_location
  data:
    latitude: 55.68
    longitude: 11.08
    target_latitude: 55.70
    target_longitude: 11.10
    speed_kmh: 30
  response_variable: beregning
```

Så tilføjes `distance_m`, `distance_km`, `eta_minutes`,
`eta_is_estimate` til svaret. Et ETA-resultat kan være `null`, hvis
hastighed, afstand eller måledata falder uden for motorens forsigtige
beregningsgrænser. Afstand er **luftlinje**, ikke faktisk ruteafstand.

Fra 0.8.12 er der også `inside_any_circle`, `circle_count`, `circles`
og `inside_any_area` i hvert svar. `circles` er de normale Home Assistant-zoner
med `entity_id` som f.eks. `zone.home`, `name` og `shape: circle`.
De eksisterende `polygons` / `polygon_count` ændres ikke, så gamle scripts
fortsætter med at virke. Ingen cirkel ændres til en polygon eller omvendt.

## 5. Nye fart- og ruteberegninger til YAML og scripts

`tiny_family.analyze_motion` beregner forskydning mellem to koordinater i
meter og returnerer en fart i km/t, `moving` / `stationary` / `uncertain` /
`unknown`, samt `speed_source`. `reported_speed_mps` er valgfri **m/s**,
samme enhed som Home Assistant Companion angiver i sin GPS-tracker.
Inputtid er **sekunder mellem fix**, ikke en dato. Et GPS-skøn vises kun,
når målingerne ligger tæt nok på hinanden og GPS-nøjagtigheden er tilstrækkelig.

```yaml
alias: Beregn fart med Tiny Family-motoren
sequence:
  - action: tiny_family.analyze_motion
    data:
      start_latitude: 55.6700
      start_longitude: 12.0800
      end_latitude: 55.6730
      end_longitude: 12.0800
      elapsed_seconds: 60
      accuracy_m: 8
      previous_accuracy_m: 8
      reported_speed_mps: 0
    response_variable: beregning
  - action: persistent_notification.create
    data:
      title: "GPS-beregning"
      message: >-
        {{ beregning.speed_kmh }} km/t
        (kilde: {{ beregning.speed_source }},
        bevægelse: {{ beregning.movement }})
```

Svaret indeholder bl.a. `displacement_m`, `displacement_km`,
`elapsed_seconds`, `continuous`, `speed_kmh`, `speed_source`,
`movement`, `is_estimate` og `distance_is_airline`. `continuous=false`
betyder, at punkterne er for langt fra hinanden tidsligt eller geografisk
til en sammenhængende GPS-tur. En GPS-afstand mellem to punkter er ikke en
bekræftet vejstrækning.

`tiny_family.analyze_route` kan bruges med en liste af 2–200 fix, som
kommer fra dit eget script, en anden integration eller et andet køretøj.
Du skal selv hente og levere GPS-punkterne; Tiny Family læser ikke
personers historik for denne handling.

```yaml
sequence:
  - action: tiny_family.analyze_route
    data:
      fixes:
        - {latitude: 55.6700, longitude: 12.0800, timestamp: 1794580000, accuracy_m: 8}
        - {latitude: 55.6750, longitude: 12.0800, timestamp: 1794580060, accuracy_m: 8, speed_mps: 0}
        - {latitude: 55.6800, longitude: 12.0800, timestamp: 1794580120, accuracy_m: 8, speed_mps: 0}
    response_variable: tur
  - action: persistent_notification.create
    data:
      message: >-
        Tur: {{ tur.distance_km }} km, {{ tur.duration_minutes }} min,
        topfart {{ tur.max_speed_kmh }} km/t,
        GPS-afbrud {{ tur.gps_gaps }}.
```

Alle tidsstempler er Unix-sekunder, og hvert nyt tidspunkt skal være
større end det forrige. Svaret indeholder kun samlede tal:
`fix_count`, `valid_intervals`, `gps_gaps`, `distance_km`,
`duration_minutes`, `moving_minutes`, `max_speed_kmh`,
`speed_sources` og `distance_is_gps_estimate`. Det returnerer **ikke**
rå koordinater. Et GPS-afbrud over 15 minutter eller et usandsynligt
positionsspring tæller som hul; der lægges ikke fiktiv distance ind.
Disse motorer er beregninger, ikke dokumentation for en bestemt persons
faktiske transportform eller en garanti for bilens instrumenthastighed.

## 6. Live-position og genbrugelige hændelser

| Entitet/hændelse | Indhold | Sikker anvendelse |
|---|---|---|
| `sensor.tiny_family_<person>_current_speed` | Hastighed i km/t eller `unknown` ved manglende frisk GPS | Brug i grafer og alarmer, hvis målekilden er acceptabel. |
| `sensor.tiny_family_<person>_speed_source` | `phone`, `gps_estimate`, `unavailable` | Skeln mellem målt og estimeret fart. |
| `sensor.tiny_family_<person>_gps_health` | `fresh`, `stale`, `unknown` | Styr visninger og automationer ved manglende opdateringer. |
| `sensor.tiny_family_<person>_gps_age_minutes` | Minutter siden accepteret GPS-fix | Advar om manglende GPS på telefonen. |
| `tiny_family_position_updated` | `person`, `timestamp` uden koordinater | Opdatér et andet panel straks efter et nyt accepteret fix. |

Den sidste hændelse udsendes ikke for tidligere Ghost-markerede personer.
**Vigtigt:** Et 6-sekunders statusopslag får ikke telefonen til at sende nye
GPS-positioner: Android/iOS og Companion bestemmer GPS-opdateringsrytmen.
Hvis der står `GPS forældet`, skal du kontrollere tilladelsen til *præcis
position*, baggrundsplacering, Companion-sensorer og batterisparer på den
konkrete telefon. Under tidslinjeafspilning stoppes live opdateringer,
så rute og kortcentrum ikke flytter sig uventet.

## 7. Hvilke andre Tiny Family-motorer kan genbruges?

| Motor | Tilgængelig udenfor panelet nu | Begrænsning |
|---|---|---|
| Polygongeometri | Ja, sensorattributter (`geojson`, `points`) | En tredjeparts kortvisning skal tegne polygonen selv. |
| Polygon-test for vilkårlig GPS-position | Ja, `evaluate_location` | Kræver bredde-/længdegrad. |
| Cirkelzone-test for vilkårlig GPS-position | Ja, `evaluate_location` | Medtager de eksisterende `zone.*`-entiteter. |
| Luftlinjeafstand og grundlæggende ETA | Ja, `evaluate_location` | Er en beregning, ikke navigation. |
| Hastighed og bevægelse mellem to GPS-fix | Ja, `analyze_motion` | Meget usikre eller lange spring giver intet falsk GPS-skøn. |
| Statistik over selvvalgte GPS-punkter | Ja, `analyze_route` | Højst 200 fix pr. kald; ingen lokationshistorik åbnes på tværs af personer. |
| Personers position i polygoner | Ja, dynamiske `binary_sensor` og bus-hændelser | Kun personer i Tiny Family; GPS-status og privatliv respekteres. |
| Bevægelse, fart, afstand, batteri mv. | Ja, eksisterende Tiny Family-sensorer og udvalgte hændelser | Afhænger af telefonens reelle GPS-/sensordata. |
| Daglig personsammenfatning | Ja, `get_day_summary` | Eksisterende adgangskontrol; system-YAML uden brugerkontekst kan afvises. |
| Vejtilpasning med indbygget OSM/OSRM | Kun via Tiny Familys kort- og tidslinje-API i denne version | Ikke en generel `match_route`-YAML-service endnu. |
| Læring af ophold, destination og rutiner | Resultater som eksisterende entiteter/hændelser | De interne læringsfunktioner er endnu ikke et åbent beregnings-API. |
| 365 dages GPS- og aktivitetshistorik | Via Tiny Familys adgangskontrollerede tidslinje-API | Offentliggøres bevidst ikke som fuldt positionsarkiv i HA-attributter. |

### Hvorfor ikke bare kalde Python-funktionerne direkte i YAML?

Home Assistants YAML-automatiseringer kalder **services**, læser **entiteter**
og lytter til **hændelser**. De importerer ikke Python-funktioner fra en
custom integration. De interne moduler kan ændre signatur ved opdateringer;
de dokumenterede HA-grænseflader ovenfor er beregnet til genbrug. Fremtidige
motorer kan åbnes som selvstændige, versionerede services med validerede
input og sikre svar, når de er klar.

### Privatliv og fejlhåndtering

- Gemte polygoners geometri ligger i HA-sensorers attributter og er dermed
  synlig for andre HA-integrationskomponenter og relevante brugere.
- Personernes rå GPS-fixes, arkiver og Ghost-data ligger **ikke** i disse
  geometri-sensorer eller polygonhændelser.
- `evaluate_location` læser kun de koordinater, du selv sender i kaldet;
  den henter ikke andre personers aktuelle eller historiske position.
- `analyze_motion` og `analyze_route` bruger udelukkende koordinater leveret
  i kaldet og opbevarer dem ikke efter beregningen. En anden integration
  er selv ansvarlig for adgang til sine GPS-data.
- Manglende/ugyldige koordinater giver en fejl i stedet for et opdigtet svar.
- Det er fortsat administratoren, der kan oprette, rette og slette polygoner.

**Versionsstatus:** Disse grænseflader er udviklet og testet i Tiny Family
0.8.12. Kontroller entitets-ID'erne i din egen installation, når versionen
er installeret, og test en automation med kendte koordinater, før den bruges
til sikkerhedskritiske formål.
