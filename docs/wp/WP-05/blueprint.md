# Blueprint WP-05: Evaluatie-engine (puur)
Status: DRAFT
Revisie: 1

## Doel
Een deterministische, pure engine die per spot per uur een oordeel geeft (`go`, `marginal` of `no_go`) met alle redenen, volgens sectie 4 van het plan. Offshore en side-offshore zijn altijd `no_go`; geen enkele parameter kan dat uitzetten.

Deze WP levert:
- `shakka.domain.defaults`: alle drempels als benoemde constanten (zie "Drempelwaarden");
- `shakka.domain.direction`: richtingsklassen, `ridable_dirs`-controle en de Nederlandse windroos;
- `shakka.domain.consensus`: consensus over de modellen en de betrouwbaarheid;
- `shakka.domain.daylight`: daglicht via `astral`;
- `shakka.domain.season`: seizoenssluitingen in lokale tijd;
- `shakka.domain.tide`: uitbreiding met `relative_tide_position` (positie tussen laag- en hoogwater);
- `shakka.domain.evaluation`: `Verdict`, `ReasonCode`, `RiderLimits`, `HourEvaluation`, `evaluate_hour`, `evaluate_spot`;
- `shakka.contracts` plus de CLI `shakka contracts export [--check]` en drie gegenereerde bestanden in `data/contracts/`.

Er gaat niets naar de database (WP-10) en er zijn geen alertregels (WP-07).

## Aannames
- **A1. Drempelwaarden zijn een voorstel.** Alle waarden staan in de sectie "Drempelwaarden" met onderbouwing en zijn constanten in `shakka.domain.defaults`. Lars toetst ze in de M1-testweek. Een andere waarde is één regel in `defaults.py` plus de tests die precies op de grens liggen. Geen andere code verandert.
- **A2. Vlaag ontbreekt = onbekend (bevestigd door Lars, 15-10-2026).** Een `gust_kn = None` wordt nooit als 0 gebruikt. De consensusvlaag is de mediaan van de modellen die wél een vlaag hebben. Hebben alle modellen `None`, dan is `Consensus.gust_kn = None`. Dan wordt de vlagerigheid niet beoordeeld (geen `gusty` of `too_gusty`), en de betrouwbaarheid kan dan hooguit `medium` zijn (zie Ontwerp). `HourEvaluation.gust_kn` blijft `None`.
- **A3. Tijdsemantiek van WP-03 is bindend.** Een `ForecastHour` met `valid_at = T` beschrijft het uur [T, T+1h). `wind_kn` en `dir_deg` gelden op T, `gust_kn` is het maximum binnen [T, T+1h). De evaluatie vergelijkt `gust_kn` en `wind_kn` zonder iets te verschuiven.
- **A4. Getijvoorkeur op het geschatte niveau (bevestigd door Lars, 15-10-2026).** De voorkeur wordt bepaald met `estimate_tide_level` en een relatieve positie tussen het dichtstbijzijnde laagwater en het dichtstbijzijnde hoogwater. Er is geen aanname dat hoog en laag strikt afwisselen; een dubbel laagwater (agger, twee keer `low` achter elkaar) werkt correct (zie Ontwerp, Getij).
- **A5. Getijmoment = midden van het uur.** De waterstand voor uur [T, T+1h) is `estimate_tide_level(extremen, T + 30 min)` (`TIDE_SAMPLE_OFFSET`). Dat is representatiever voor het hele uur dan het begin. `HourEvaluation.tide_level_cm` is precies die waarde.
- **A6. `no_data` ook als de windsnelheid ontbreekt.** De redentabel zegt "geen enkel model heeft data". Zonder windsnelheid is geen oordeel mogelijk, dus `no_data` geldt als `compute_consensus` `None` geeft **of** als `Consensus.wind_kn` `None` is (alleen vlaag of richting bekend). Er komt geen nieuwe redencode; dat zou een migratie vragen (WP-01, R5).
- **A7. Spot zonder coördinaten.** `evaluate_hour` geeft dan een `ValueError` (daglicht is niet te bepalen). WP-03 haalt voor zulke spots geen forecasts op en WP-10 evalueert alleen spots met coördinaten, dus `evaluate_spot` geeft voor zo'n spot in de praktijk `[]` zonder fout.
- **A8. Getijniveau ook bij `tide_sensitive: none`.** Heeft de spot een `rws_station` en zijn er extremen, dan vult de evaluatie `tide_level_cm` altijd in (informatief, voor WP-14). Redenen over getij komen alleen bij een getijgevoelige spot.
- **A9. `tide_min_level_cm` geldt bij elke getijgevoeligheid.** WP-02 staat het veld toe bij `prefer_low`, `prefer_high` en `avoid_low`. Een geschatte stand onder het minimum geeft dus altijd `tide_too_low`, ongeacht de variant.
- **A10. Additieve uitbreidingen van het contract.** Bestaande signatures uit WORK_PACKAGES blijven exact zo. Erbij komen:
  - `Consensus.speed_spread_kn` en `Consensus.dir_spread_deg` (met default `None`), zodat de betrouwbaarheid uitlegbaar en testbaar is;
  - `circular_mean_deg`, `angular_distance`, `sun_times`, de module `shakka.domain.season`, `relative_tide_position`, `worst_verdict`, `VERDICT_SEVERITY`, `REASON_LABEL_NL`, `DIR_CLASS_LABEL_NL`, `CONFIDENCE_LABEL_NL`, `COMPASS_POINTS_NL`;
  - `HourEvaluation.to_row(*, evaluated_at)` (pure mapping naar de kolommen van `evaluations`, voor WP-10).
- **A11. Eén nieuwe dependency: `astral>=3.2,<4`.** Het plan noemt astral al in de stack, en de puurheidstest staat het al toe.
- **A12. Geen extra testdependencies.** Eigenschapstests zijn deterministische rasters in pytest, geen `hypothesis`.
- **A13. Testcoördinaten 52,47 N / 4,57 O zijn testdata**, geen spotdata (zelfde punt als WP-03 A11). Ze komen niet in `data/spots.yaml`.

## Ontwerp

### Lagen en afhankelijkheden
Alle nieuwe domeinmodules importeren alleen de standaardbibliotheek, `pydantic`, `astral`, `zoneinfo` en andere `shakka.domain`-modules. De importvolgorde voorkomt cycli:

```
defaults  (geen domeinimports)
  ├─ direction  (spot.DirRange)
  ├─ consensus  (forecast, direction)
  ├─ daylight   (astral)
  ├─ season     (spot.SeasonClosure)
  ├─ tide       (bestaand; + relative_tide_position)
  └─ evaluation (alles hierboven)
```

`shakka.contracts` is een I/O-module (buiten `shakka.domain`). Die schrijft JSON-bestanden en mag dus `pathlib` en `json` gebruiken.

### Richting
`angular_distance(a, b)` geeft de kleinste hoek tussen twee richtingen, in [0, 180]. De klasse volgt uit `d = angular_distance(wind_from, shore_normal)`, met bovengrenzen die bij de klasse horen (inclusief):

| `d` (graden) | Klasse |
|---|---|
| 0 t/m 22,5 | `onshore` |
| > 22,5 t/m 67,5 | `side_onshore` |
| > 67,5 t/m 100 | `sideshore` |
| > 100 t/m 157,5 | `side_offshore` |
| > 157,5 t/m 180 | `offshore` |

Omdat de klasse alleen van `d` afhangt, is ze per constructie symmetrisch (+x en -x geven dezelfde `d`) en monotoon in `d`. Rond 0/360 gaat het goed: `angular_distance(350, 10) = 20`.

`ridable_dirs` beperkt alleen. De controle `in_ranges` gebeurt pas als de klasse rijdbaar is. Een offshore- of side-offshore-uur krijgt dus altijd de reden `offshore` of `side_offshore`, ook als de richting in `ridable_dirs` valt. De klasse wordt eerst bepaald en daar is geen uitzondering op.

`in_ranges(deg, ranges)`: `x = deg % 360`. Per bereik geldt: bij `from <= to` moet `from <= x <= to`; bij `from > to` (over het noorden) moet `x >= from or x <= to`. Een lege reeks geeft `False`.

`compass_label(deg)`: `COMPASS_POINTS_NL[int(((deg % 360) + 11.25) // 22.5) % 16]`. Een grens (bijv. 11,25) valt in de volgende streek met de klok mee.

### Consensus
`compute_consensus(hours)` krijgt de `ForecastHour`s van één spot en één `valid_at` (hooguit één per model):
- Ongeldige invoer geeft `ValueError`: meerdere `spot_id`'s, meerdere `valid_at`'s of een dubbel model.
- `None` als `hours` leeg is, of als geen enkel model een `wind_kn`, `gust_kn` of `dir_deg` heeft.
- `wind_kn` = `round(statistics.median(winds), 1)` over de modellen met `wind_kn is not None`. Bij 4 modellen is dat het gemiddelde van de middelste twee: robuust tegen één uitschieter (vaak GFS).
- `gust_kn` = `round(median(gusts), 1)` over de modellen met een vlaag (A2).
- `dir_deg` = circulair gemiddelde (eenheidsvectoren, ongewogen) van de beschikbare richtingen, `int(round(mean)) % 360`. Is de lengte van de gemiddelde vector kleiner dan `DIR_MIN_RESULTANT` (bijv. 0 en 180), dan is de richting niet te bepalen en wordt `dir_deg = None`.
- `speed_spread_kn` = `round(max(winds) - min(winds), 1)`, of `None` zonder windsnelheid. Afronden vóór de vergelijking voorkomt floatfouten (12,3 − 8,3 = 4,000000000000002).
- `dir_spread_deg` = `round(max(angular_distance(d, mean)), 1)` over de beschikbare richtingen, met het onafgeronde gemiddelde. `None` als `dir_deg` `None` is.
- `models_used`: de modellen met minstens één waarde die niet `None` is, in de volgorde van `ModelKey` (`knmi`, `icon`, `ecmwf`, `gfs`).

**Betrouwbaarheid** (eerste regel die past):
1. `n_wind` (aantal modellen met `wind_kn`) ≤ 1 → `low`. **Eén model is dus altijd `low`**: zonder tweede model is er geen spreiding te meten. In de praktijk komt dit alleen bij een datafout voor; ICON, ECMWF en GFS dekken alle 7 dagen.
2. `dir_deg is None` → `low`.
3. `speed_spread_kn > CONFIDENCE_LOW_SPEED_SPREAD_KN` of `dir_spread_deg > CONFIDENCE_LOW_DIR_SPREAD_DEG` → `low`.
4. `n_wind >= CONFIDENCE_HIGH_MIN_MODELS` en `speed_spread_kn <= CONFIDENCE_HIGH_SPEED_SPREAD_KN` en `dir_spread_deg <= CONFIDENCE_HIGH_DIR_SPREAD_DEG` en `gust_kn is not None` → `high`.
5. Anders → `medium`. Twee modellen of een onbekende vlaag geven dus hooguit `medium`.

### Daglicht
`sun_times(lat, lon, day)` geeft `(sunrise, sunset)` in UTC via `astral.sun.sunrise` en `astral.sun.sunset` met `Observer(latitude=lat, longitude=lon)`, `date=day` en `tzinfo=UTC`. `date` wordt **altijd** meegegeven, want zonder `date` leest astral de klok ("today"). De functie heeft een `functools.lru_cache(maxsize=4096)`; ze is puur, dus cachen is veilig. `dawn` en `dusk` worden niet gebruikt.

`is_daylight(lat, lon, valid_at)` beschouwt het uur [T, T+1h). Met `sr, ss = sun_times(lat, lon, T.astimezone(UTC).date())` geeft de functie `True` als:

`T >= sr - DAYLIGHT_MARGIN_BEFORE_SUNRISE` **en** `T + 1h <= ss + DAYLIGHT_MARGIN_AFTER_SUNSET`

Het hele uur moet dus binnen de daglichtperiode met marge vallen. In Nederland liggen zonsopkomst (03:15–07:50Z) en zonsondergang (15:25–20:10Z) altijd op dezelfde UTC-datum als het daglicht. Nachturen rond middernacht UTC vallen buiten beide grenzen, dus de keuze voor de UTC-datum van T is veilig. Een `ValueError` van astral (pooldag of poolnacht) wordt doorgegeven; voor Nederlandse coördinaten komt die niet voor.

### Seizoen
De semantiek volgt WP-02 A4. Per sluiting en uur [T, T+1h):
1. `local = T.astimezone(LOCAL_TZ)` en `day = local.date()`.
2. `in_period(start, end, day)` vergelijkt `(maand, dag)`-tuples. Bij `start <= end` moet `start <= md <= end`; anders (over de jaargrens) `md >= start or md <= end`. `02-29` werkt zo zonder uitzondering.
3. Zonder tijdvenster is het uur gesloten als de dag in de periode valt.
4. Met tijdvenster: `ws = datetime.combine(day, from_time, tzinfo=LOCAL_TZ).astimezone(UTC)` en `we` net zo met `to_time`. Het uur is gesloten als het overlapt: `T < we and ws < T + 1h`. Alle vergelijkingen gebeuren in UTC, zodat zomer- en wintertijd vanzelf kloppen.

Een uur dat het venster maar gedeeltelijk raakt (bijv. venster vanaf 10:30), is dus gesloten. Dat is conservatief. Omdat Amsterdam altijd hele uren van UTC afwijkt, beginnen lokale uren op hele uren. Een uur kan daarom alleen met een venster op zijn eigen startdatum overlappen (vensters gaan niet over middernacht, WP-02 A2.4). Een lokaal tijdstip dat niet bestaat (02:30 op de dag van de zomertijd) volgt `fold=0` van `zoneinfo`; dat is deterministisch en in de praktijk niet relevant.

### Getij
Per spot: `station = spot.rws_station.strip()` als die gezet is, en `ext = [t for t in tides if t.station == station]`. Extremen van andere stations worden genegeerd. `estimate_tide_level` geeft een `ValueError` bij meerdere stations, dus dit filter is nodig. Het meetmoment is `sample = T + TIDE_SAMPLE_OFFSET`, en `level = estimate_tide_level(ext, sample)` (of `None` zonder station of extremen).

`relative_tide_position(extremes, at) -> float | None` (nieuw in `shakka.domain.tide`):
- `level = estimate_tide_level(extremes, at)`; bij `None` volgt `None`.
- Kandidaten zijn de extremen met `|e.at - at| <= TIDE_NEIGHBOUR_WINDOW` (9 uur, gelijk aan `MAX_EXTREME_GAP`).
- `low` is het dichtstbijzijnde (in tijd) laagwater en `high` het dichtstbijzijnde hoogwater. Bij gelijke afstand wint het vroegste.
- Ontbreekt één van beide, of geldt `high.level_cm <= low.level_cm`, dan volgt `None`.
- Anders `min(1.0, max(0.0, (level - low.level_cm) / (high.level_cm - low.level_cm)))`. Daarbij betekent 0,0 "op laagwater" en 1,0 "op hoogwater".

Bij een agger (laagwater 1, topagger, laagwater 2) ligt het geschatte niveau tussen de twee laagwaters dicht bij het laagwaterniveau. Het dichtstbijzijnde laagwater is één van beide, dus de positie is klein ("rond laagwater"). Dat klopt. Strikte afwisseling is nergens nodig.

Regels als `spot.tide_sensitive != none` (`pos = relative_tide_position(ext, sample)`):
1. `level is None` → `tide_unknown`. Er wordt verder niets beoordeeld.
2. `spot.tide_min_level_cm is not None` en `level < tide_min_level_cm` → `tide_too_low` (A9; precies gelijk is niet te laag).
3. Per variant:
   - `prefer_low`: `pos is None` → `tide_unknown`; `pos > TIDE_LOW_BAND` → `tide_unfavorable`.
   - `prefer_high`: `pos is None` → `tide_unknown`; `pos < TIDE_HIGH_BAND` → `tide_unfavorable`.
   - `avoid_low` zonder `tide_min_level_cm`: `pos is None` → `tide_unknown`; `pos <= TIDE_LOW_BAND` → `tide_unfavorable`.
   - `avoid_low` met `tide_min_level_cm`: alleen regel 2 (volgens de redentabel).

### Evaluatie van één uur
`evaluate_hour(spot, valid_at, hours, tides, limits)`:
0. Controles (`ValueError`):
   - `valid_at` is naïef of geen heel uur;
   - een `ForecastHour` met een andere `spot_id` of `valid_at`;
   - `spot.lat` of `spot.lon` is `None` (A7).

   `valid_at` wordt naar UTC genormaliseerd.
1. `c = compute_consensus(hours)`.
2. **Data:** `c is None or c.wind_kn is None` → `no_data`.
3. **Wind** (alleen als `c.wind_kn` bekend is, `w = c.wind_kn`):
   - `w < limits.min_kn` → `wind_too_light`;
   - `w > limits.max_kn` → `wind_too_strong`;
   - anders: `w < limits.min_kn + WIND_BORDERLINE_KN` of `w > limits.max_kn - WIND_BORDERLINE_KN` → `wind_borderline`.
4. **Vlagen** (alleen als `w` en `g = c.gust_kn` bekend zijn en `w > 0`), met `delta = g - w`:
   - `delta >= GUST_MIN_DELTA_KN` en `g >= TOO_GUSTY_RATIO * w` → `too_gusty`;
   - anders: `delta >= GUST_MIN_DELTA_KN` en `g >= GUSTY_RATIO * w` → `gusty`.
5. **Richting:**
   - Is `spot.shore_normal_deg` `None`, of `c` `None`, of `c.dir_deg` `None`, dan volgt `direction_unknown` en `dir_class = None`.
   - Anders `dir_class = classify_direction(c.dir_deg, spot.shore_normal_deg)`. Bij `offshore` volgt `offshore`, bij `side_offshore` volgt `side_offshore`.
   - Is de klasse rijdbaar, `spot.ridable_dirs` gezet en `not in_ranges(c.dir_deg, spot.ridable_dirs)`, dan volgt `direction_not_ridable`.
6. **Daglicht:** `not is_daylight(spot.lat, spot.lon, valid_at)` → `dark`.
7. **Seizoen:** `is_season_closed(spot.season, valid_at)` → `season_closed`.
8. **Status:** `forbidden` geeft `spot_forbidden`, `limited` geeft `spot_limited`, `None` geeft `status_unknown`. `allowed` geeft niets.
9. **Getij:** zie hierboven.
10. **Betrouwbaarheid:** `c is not None and c.confidence == low` → `low_confidence`.

De redenen worden ontdubbeld en gesorteerd in de volgorde van `ReasonCode` (de volgorde van de redentabel). Het oordeel is `worst_verdict(reasons)`: het zwaarste `REASON_EFFECT` (`no_go` > `marginal` > `go`), en `go` als er geen redenen zijn. Alle controles zijn onafhankelijk; er is geen vroege return. Daardoor ziet de gebruiker alle redenen (bijv. `dark` én `side_offshore`).

`HourEvaluation` vult `wind_kn`, `gust_kn`, `dir_deg` en `confidence` uit `c` (of `None`), `dir_class` uit stap 5 en `tide_level_cm = level`.

**Invarianten in het model.** Een `model_validator` van `HourEvaluation` eist:
- `reasons` is uniek en gesorteerd volgens `ReasonCode`;
- `verdict == worst_verdict(reasons)`;
- `dir_class` in {`offshore`, `side_offshore`} impliceert `verdict == no_go` (spiegel van de DB-CHECK `evaluations_offshore_is_no_go`).

Een inconsistente evaluatie is dus niet te maken, ook niet in tests van WP-07 en WP-08.

### Evaluatie van een spot
`evaluate_spot(spot, forecasts, tides, limits)`:
- groepeert `forecasts` op `valid_at` (een andere `spot_id` geeft `ValueError`);
- filtert de getijden één keer op het station;
- roept per unieke `valid_at`, oplopend gesorteerd, `evaluate_hour` aan.

Zonder forecasts volgt `[]`.

### `default_limits`
`min_kn = float(spot.default_min_kn)` als die gezet is, anders `DEFAULT_MIN_KN`. Daarnaast `max_kn = max(DEFAULT_MAX_KN, min_kn + MIN_LIMIT_SPAN_KN)`, zodat een spot met `default_min_kn: 35` (toegestaan tot 40) nog geldige grenzen geeft.

### Contractbestanden
`shakka.contracts.build_contracts()` bouwt in het geheugen drie JSON-teksten uit de domeinconstanten. `export` schrijft alleen bestanden waarvan de inhoud verschilt; `--check` schrijft niets en meldt ontbrekende of verouderde bestanden. Andere bestanden in `data/contracts/` (later `alert_defaults.json` uit WP-07 en `rule_resolution_cases.json` uit WP-16) worden niet aangeraakt en niet gecontroleerd door deze functie. Het formaat is `json.dumps(obj, ensure_ascii=False, indent=2) + "\n"`, in UTF-8, zodat de bestanden diff-baar zijn en de Nederlandse tekens leesbaar blijven.

## Drempelwaarden
Voorstel van de planner. Lars toetst dit in de M1-testweek (WORK_PACKAGES, "Beslissingen voor Lars"). Alle waarden staan in `shakka.domain.defaults`.

| Constante | Waarde | Betekenis | Onderbouwing |
|---|---|---|---|
| `LOCAL_TZ` | `ZoneInfo("Europe/Amsterdam")` | Lokale tijd | Projectafspraak. |
| `DEFAULT_MIN_KN` | `12.0` | Ondergrens zonder spot-default | Met een 12 m kite (rider van ca. 75 kg, twintip) is 12 kn de gangbare ondergrens. Daaronder kan het alleen met grote kites of een foil. De spot-default (`default_min_kn`) gaat voor. |
| `DEFAULT_MAX_KN` | `30.0` | Bovengrens | Boven 30 kn wordt het voor een gemiddelde rider (niveau intermediate) met een kleine kite (7–8 m) zwaar en onveilig. Gevorderden verhogen dit via hun profiel of regel (WP-07). |
| `MIN_LIMIT_SPAN_KN` | `5.0` | Minimaal verschil tussen min en max in `default_limits` | Voorkomt `min >= max` bij een hoge `default_min_kn`. |
| `WIND_BORDERLINE_KN` | `2.0` | Marge voor `wind_borderline` | 2 kn is ongeveer de nauwkeurigheid van een modelverwachting op 1–2 dagen. Binnen die marge kan het uur net wel of net niet lukken. |
| `GUSTY_RATIO` | `1.6` | Vlaag/wind vanaf "vlagerig" (`marginal`) | Zie de toelichting hieronder. |
| `TOO_GUSTY_RATIO` | `1.9` | Vlaag/wind vanaf "te vlagerig" (`no_go`) | Kitekracht schaalt met v². Bij 1,9 is de kracht in een vlaag ongeveer 3,6 keer die bij de gemiddelde wind; dat is niet meer te hanteren met één kitemaat. |
| `GUST_MIN_DELTA_KN` | `8.0` | Vlaag moet ook minstens zoveel kn boven de wind liggen | Bij weinig wind is de ratio snel hoog zonder praktisch effect (10 → 16 kn). Beide voorwaarden moeten gelden. |
| `ONSHORE_MAX_DEG` | `22.5` | Hoekafwijking t.o.v. `shore_normal_deg` voor `onshore` (inclusief) | Halve sector van 45°, centraal rond recht aanlandig (twee streken van de windroos). |
| `SIDE_ONSHORE_MAX_DEG` | `67.5` | Grens `side_onshore` | Sector van 45° rond 45°. |
| `SIDESHORE_MAX_DEG` | `100.0` | Grens `sideshore`, **veiligheidskritisch** | Symmetrische sectoren zouden 112,5 geven. Daarmee zou wind met 22,5° van het land af nog "sideshore" en rijdbaar zijn. 100 laat maximaal 10° aflandige component toe. Dat is ongeveer de onnauwkeurigheid van de modelrichting en van een handmatig bepaalde kustrichting. Daarboven is het `side_offshore` en dus altijd `no_go`. Strenger alternatief: 90 (elke aflandige component is `no_go`); dat kost veel uren bij wind evenwijdig aan de kust. |
| `SIDE_OFFSHORE_MAX_DEG` | `157.5` | Grens `side_offshore`, daarboven `offshore` | Sector van 45° rond 135° (met de verruimde ondergrens). Voor de veiligheid maakt deze grens niets uit: beide klassen zijn `no_go`. Hij bepaalt alleen het label. |
| `DAYLIGHT_MARGIN_BEFORE_SUNRISE` | `15 min` | Uur mag 15 min vóór zonsopkomst beginnen | Civiele schemering duurt in Nederland 35–50 min; 15 min vóór zonsopkomst is er ruim zicht. Bewust krap: AC-5 eist dat 21 juni 03:00Z donker is (zonsopkomst bij de testcoördinaten is ca. 03:19Z), dus de marge moet kleiner zijn dan 19 min. |
| `DAYLIGHT_MARGIN_AFTER_SUNSET` | `15 min` | Uur mag tot 15 min na zonsondergang lopen | Symmetrisch. Aparte constante, zodat Lars de avond ruimer kan zetten zonder de ochtend te raken. |
| `CONFIDENCE_HIGH_SPEED_SPREAD_KN` | `4.0` | Max. spreiding (max − min) in wind voor `high` | 4 kn is het verschil tussen twee opeenvolgende kitematen. In de fixture van WP-03 (14-10-2026) lag de spreiding op dag 1 tussen 1,5 en 5 kn. |
| `CONFIDENCE_LOW_SPEED_SPREAD_KN` | `8.0` | Spreiding **boven** deze waarde geeft `low` | Een bereik van meer dan 8 kn (bijv. 9–17,1 kn) loopt van "te weinig" tot "goed". Het oordeel is dan niet te vertrouwen. |
| `CONFIDENCE_HIGH_DIR_SPREAD_DEG` | `20.0` | Max. richtingsafwijking voor `high` | Kleiner dan een halve klassesector (45°). |
| `CONFIDENCE_LOW_DIR_SPREAD_DEG` | `45.0` | Afwijking **boven** deze waarde geeft `low` | Een afwijking van meer dan 45° kan een andere richtingsklasse betekenen, ook richting aflandig. |
| `CONFIDENCE_HIGH_MIN_MODELS` | `3` | Minimaal aantal modellen met wind voor `high` | Met twee modellen is "eens zijn" zwak bewijs. |
| `DIR_MIN_RESULTANT` | `0.1` | Minimale lengte van de gemiddelde eenheidsvector | Daaronder heffen de richtingen elkaar op (bijv. 0 en 180) en is er geen zinvolle richting. |
| `TIDE_SAMPLE_OFFSET` | `30 min` | Meetmoment van het getij binnen het uur | A5. |
| `TIDE_NEIGHBOUR_WINDOW` | `9 h` | Zoekvenster voor het dichtstbijzijnde hoog- en laagwater | Gelijk aan `MAX_EXTREME_GAP` uit WP-04. Binnen 9 uur van elk moment ligt bij een halfdaags getij altijd een hoog- en een laagwater, ook met een agger. |
| `TIDE_LOW_BAND` | `0.3` | Positie ≤ 0,3 = "rond laagwater" | Met de cosinusinterpolatie komt 0,3 overeen met ca. 37% van een halve getijperiode aan weerszijden van laagwater, dus ongeveer ±2,3 uur. Dat sluit aan bij de vuistregel "2 uur voor tot 2 uur na laagwater". |
| `TIDE_HIGH_BAND` | `0.7` | Positie ≥ 0,7 = "rond hoogwater" | Symmetrisch: ±2,3 uur rond hoogwater. |

**Toelichting vlagerigheid.** De ratio (vlaag gedeeld door wind) is de meteorologische vlaagfactor. Hij past bij de krachtschommeling in de kite (∝ v²), en die bepaalt voor een kiter of het vlagerig voelt. De drempels liggen hoger dan je voor zee zou verwachten (ca. 1,3). De reden staat in de vastgelegde respons uit WP-03 (`forecast_2loc_4models.json`, 14-10-2026, rond 12–15 kn): ECMWF en ICON gaven een vlaagfactor van ca. 1,3, KNMI Harmonie en GFS van ca. 1,8–2,0. De mediaan over de modellen komt op een gewone dag dus rond 1,5–1,6 uit. Met `GUSTY_RATIO = 1,4` zou bijna elk uur `marginal` worden. Bij 1,6 en 1,9 slaat de regel pas aan als ook ECMWF en ICON duidelijk meer vlagen geven (buien, onstabiele lucht). Dit is de drempel met de grootste onzekerheid; zie R2.

## Bestanden

| Pad | Actie | Inhoud |
|---|---|---|
| `ingest/pyproject.toml` | wijzigen | `"astral>=3.2,<4"` in `dependencies` (via `uv add`). |
| `ingest/uv.lock` | wijzigen | Door `uv add`. |
| `ingest/src/shakka/domain/defaults.py` | aanmaken | Alle constanten uit "Drempelwaarden", met per constante een commentaar van één regel. Imports: `datetime.timedelta`, `typing.Final`, `zoneinfo.ZoneInfo`. Geen domeinimports. |
| `ingest/src/shakka/domain/direction.py` | aanmaken | `DirClass`, `RIDABLE_DIR_CLASSES`, `DIR_CLASS_LABEL_NL`, `COMPASS_POINTS_NL`, `angular_distance`, `classify_direction`, `in_ranges`, `compass_label`. |
| `ingest/src/shakka/domain/consensus.py` | aanmaken | `Confidence`, `CONFIDENCE_LABEL_NL`, `Consensus`, `circular_mean_deg`, `compute_consensus`. |
| `ingest/src/shakka/domain/daylight.py` | aanmaken | `sun_times` (met `lru_cache`), `is_daylight`. |
| `ingest/src/shakka/domain/season.py` | aanmaken | `in_period`, `closure_applies`, `is_season_closed`. |
| `ingest/src/shakka/domain/tide.py` | wijzigen | Functie `relative_tide_position` erbij. Bestaande code blijft ongewijzigd. Import van `TIDE_NEIGHBOUR_WINDOW` uit `defaults`. |
| `ingest/src/shakka/domain/evaluation.py` | aanmaken | `Verdict`, `VERDICT_SEVERITY`, `ReasonCode`, `REASON_EFFECT`, `REASON_LABEL_NL`, `worst_verdict`, `RiderLimits`, `HourEvaluation`, `default_limits`, `evaluate_hour`, `evaluate_spot`. |
| `ingest/src/shakka/contracts.py` | aanmaken | `CONTRACTS_DIR`, `CONTRACT_FILES`, `GENERATED_NOTE`, `build_contracts`, `check_contracts`, `export_contracts`, `run_contracts_export`. |
| `ingest/src/shakka/cli.py` | wijzigen | Groep `contracts` met het commando `export [--check]`, na de groep `tides`. Lazy import in de commandfunctie, net als bij de andere groepen. |
| `data/contracts/reason_codes.json` | aanmaken | Gegenereerd met `uv run shakka contracts export`. |
| `data/contracts/dir_classes.json` | aanmaken | Idem. |
| `data/contracts/confidence.json` | aanmaken | Idem. |
| `ingest/tests/evaluation_fixtures.py` | aanmaken | Helpers voor de evaluatietests (zie Testplan). |
| `ingest/tests/test_direction.py` | aanmaken | AC-1, `in_ranges`, `compass_label`. |
| `ingest/tests/test_consensus.py` | aanmaken | AC-8 (eenheid). |
| `ingest/tests/test_daylight.py` | aanmaken | AC-5. |
| `ingest/tests/test_season.py` | aanmaken | AC-6 (eenheid). |
| `ingest/tests/test_tide_position.py` | aanmaken | `relative_tide_position`, inclusief agger. |
| `ingest/tests/test_evaluation.py` | aanmaken | AC-3, AC-4, AC-6 (status en seizoen via `evaluate_hour`), AC-7, AC-8 (integratie). |
| `ingest/tests/test_evaluation_safety.py` | aanmaken | AC-2, plus de signaturecontrole. |
| `ingest/tests/test_evaluation_properties.py` | aanmaken | AC-9. |
| `ingest/tests/test_contracts.py` | aanmaken | AC-10, plus de controle tegen de CHECK-lijsten in de migratie. |
| `docs/SPOT_DATA.md` | wijzigen | §4: de indicatieve zin vervangen door de exacte grenstabel uit "Ontwerp/Richting" (tekst in het Nederlands, getallen gelijk aan `defaults.py`). §7: per variant één zin over de betekenis (bijv. "`prefer_low`: ongunstig buiten ongeveer 2 uur vóór tot 2 uur na laagwater") en dat `tide_min_level_cm` bij elke variant geldt. De bestaande strings die `test_spot_docs.py` zoekt blijven staan. |

Geen migraties, geen wijziging aan `shakka.db`, `FakeSupabase`, `ForecastHour`, `TideExtreme` of `SpotProfile`. `docs/STATUS.md` werkt de orchestrator bij.

## Interfaces en contracten

### `shakka.domain.defaults`
```python
LOCAL_TZ: Final = ZoneInfo("Europe/Amsterdam")
DEFAULT_MIN_KN: Final = 12.0
DEFAULT_MAX_KN: Final = 30.0
MIN_LIMIT_SPAN_KN: Final = 5.0
WIND_BORDERLINE_KN: Final = 2.0
GUSTY_RATIO: Final = 1.6
TOO_GUSTY_RATIO: Final = 1.9
GUST_MIN_DELTA_KN: Final = 8.0
ONSHORE_MAX_DEG: Final = 22.5
SIDE_ONSHORE_MAX_DEG: Final = 67.5
SIDESHORE_MAX_DEG: Final = 100.0
SIDE_OFFSHORE_MAX_DEG: Final = 157.5
DAYLIGHT_MARGIN_BEFORE_SUNRISE: Final = timedelta(minutes=15)
DAYLIGHT_MARGIN_AFTER_SUNSET: Final = timedelta(minutes=15)
CONFIDENCE_HIGH_SPEED_SPREAD_KN: Final = 4.0
CONFIDENCE_LOW_SPEED_SPREAD_KN: Final = 8.0
CONFIDENCE_HIGH_DIR_SPREAD_DEG: Final = 20.0
CONFIDENCE_LOW_DIR_SPREAD_DEG: Final = 45.0
CONFIDENCE_HIGH_MIN_MODELS: Final = 3
DIR_MIN_RESULTANT: Final = 0.1
TIDE_SAMPLE_OFFSET: Final = timedelta(minutes=30)
TIDE_NEIGHBOUR_WINDOW: Final = timedelta(hours=9)
TIDE_LOW_BAND: Final = 0.3
TIDE_HIGH_BAND: Final = 0.7
```
Een test (`test_direction.py::test_thresholds_ordered`) eist `0 < ONSHORE < SIDE_ONSHORE < SIDESHORE < SIDE_OFFSHORE < 180`, `1 < GUSTY_RATIO < TOO_GUSTY_RATIO`, `HIGH < LOW` voor beide spreidingen en `0 < TIDE_LOW_BAND < TIDE_HIGH_BAND < 1`.

### `shakka.domain.direction`
```python
class DirClass(StrEnum):
    ONSHORE = "onshore"
    SIDE_ONSHORE = "side_onshore"
    SIDESHORE = "sideshore"
    SIDE_OFFSHORE = "side_offshore"
    OFFSHORE = "offshore"

RIDABLE_DIR_CLASSES: Final[frozenset[DirClass]] = frozenset(
    {DirClass.ONSHORE, DirClass.SIDE_ONSHORE, DirClass.SIDESHORE})
DIR_CLASS_LABEL_NL: Final[dict[DirClass, str]] = {
    DirClass.ONSHORE: "Aanlandig",
    DirClass.SIDE_ONSHORE: "Schuin aanlandig",
    DirClass.SIDESHORE: "Sideshore (langs de kust)",
    DirClass.SIDE_OFFSHORE: "Schuin aflandig",
    DirClass.OFFSHORE: "Aflandig",
}
COMPASS_POINTS_NL: Final[tuple[str, ...]] = (
    "N", "NNO", "NO", "ONO", "O", "OZO", "ZO", "ZZO",
    "Z", "ZZW", "ZW", "WZW", "W", "WNW", "NW", "NNW")

def angular_distance(a: float, b: float) -> float:
    """Smallest angle between two directions, in [0, 180]. ValueError if not finite."""
def classify_direction(wind_from_deg: float, shore_normal_deg: float) -> DirClass:
    """Class from angular_distance(wind_from_deg, shore_normal_deg) and the *_MAX_DEG bounds
    (upper bound inclusive). Both arguments are taken modulo 360. ValueError if not finite."""
def in_ranges(deg: float, ranges: Sequence[DirRange]) -> bool:
    """True if deg (mod 360) lies in any clockwise, inclusive range; from > to wraps north."""
def compass_label(deg: float) -> str:
    """Dutch 16-point compass label; a boundary (e.g. 11.25) belongs to the next point clockwise."""
```

### `shakka.domain.consensus`
```python
class Confidence(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

CONFIDENCE_LABEL_NL: Final[dict[Confidence, str]] = {
    Confidence.HIGH: "Hoog", Confidence.MEDIUM: "Gemiddeld", Confidence.LOW: "Laag"}

class Consensus(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    wind_kn: float | None
    gust_kn: float | None
    dir_deg: int | None            # 0..359
    confidence: Confidence
    models_used: tuple[ModelKey, ...]
    speed_spread_kn: float | None = None
    dir_spread_deg: float | None = None

def circular_mean_deg(degrees: Sequence[float]) -> float | None:
    """Unweighted circular mean in [0, 360); None if empty or the mean resultant length
    is below DIR_MIN_RESULTANT."""
def compute_consensus(hours: Sequence[ForecastHour]) -> Consensus | None:
    """Consensus over the models of one spot and one valid_at (see Ontwerp).
    None if no model has any value. ValueError on mixed spot_id/valid_at or a duplicate model."""
```

### `shakka.domain.daylight`
```python
@functools.lru_cache(maxsize=4096)
def sun_times(lat: float, lon: float, day: date) -> tuple[datetime, datetime]:
    """(sunrise, sunset) on UTC date `day`, tz-aware UTC, via astral with date=day, tzinfo=UTC.
    Propagates astral's ValueError when the sun does not rise or set."""
def is_daylight(lat: float, lon: float, valid_at: datetime) -> bool:
    """True if the hour [valid_at, valid_at + 1h) lies within
    [sunrise - DAYLIGHT_MARGIN_BEFORE_SUNRISE, sunset + DAYLIGHT_MARGIN_AFTER_SUNSET]
    of the UTC date of valid_at. ValueError if valid_at is naive."""
```
`valid_at` hoeft hier geen heel uur te zijn (de grenstests gebruiken minuten en seconden).

### `shakka.domain.season`
```python
def in_period(start: str, end: str, day: date) -> bool:
    """Inclusive MM-DD period, compared as (month, day) tuples; start > end wraps the year."""
def closure_applies(closure: SeasonClosure, valid_at: datetime) -> bool:
    """True if the hour [valid_at, valid_at + 1h) falls in the closure (see Ontwerp/Seizoen).
    ValueError if valid_at is naive."""
def is_season_closed(closures: Sequence[SeasonClosure], valid_at: datetime) -> bool:
    """any(closure_applies(c, valid_at) for c in closures)."""
```

### `shakka.domain.tide` (toevoeging)
```python
def relative_tide_position(extremes: Sequence[TideExtreme], at: datetime) -> float | None:
    """Position of the estimated level at `at` between the nearest low (0.0) and the nearest
    high (1.0) water within TIDE_NEIGHBOUR_WINDOW, clamped to [0, 1]. Ties: earliest wins.
    None if estimate_tide_level is None, a kind is missing in the window, or high <= low.
    Does not assume that high and low alternate (double low water is fine)."""
```

### `shakka.domain.evaluation`
```python
class Verdict(StrEnum):
    GO = "go"
    MARGINAL = "marginal"
    NO_GO = "no_go"

VERDICT_SEVERITY: Final[dict[Verdict, int]] = {Verdict.GO: 0, Verdict.MARGINAL: 1, Verdict.NO_GO: 2}

class ReasonCode(StrEnum):            # declaration order = canonical reason order
    NO_DATA = "no_data"
    WIND_TOO_LIGHT = "wind_too_light"
    WIND_TOO_STRONG = "wind_too_strong"
    WIND_BORDERLINE = "wind_borderline"
    TOO_GUSTY = "too_gusty"
    GUSTY = "gusty"
    OFFSHORE = "offshore"
    SIDE_OFFSHORE = "side_offshore"
    DIRECTION_UNKNOWN = "direction_unknown"
    DIRECTION_NOT_RIDABLE = "direction_not_ridable"
    DARK = "dark"
    SEASON_CLOSED = "season_closed"
    SPOT_FORBIDDEN = "spot_forbidden"
    SPOT_LIMITED = "spot_limited"
    STATUS_UNKNOWN = "status_unknown"
    TIDE_TOO_LOW = "tide_too_low"
    TIDE_UNFAVORABLE = "tide_unfavorable"
    TIDE_UNKNOWN = "tide_unknown"
    LOW_CONFIDENCE = "low_confidence"

REASON_EFFECT: Final[dict[ReasonCode, Verdict]]   # exactly the table in WORK_PACKAGES WP-05
REASON_LABEL_NL: Final[dict[ReasonCode, str]] = {
    ReasonCode.NO_DATA: "Geen voorspelling beschikbaar",
    ReasonCode.WIND_TOO_LIGHT: "Te weinig wind",
    ReasonCode.WIND_TOO_STRONG: "Te veel wind",
    ReasonCode.WIND_BORDERLINE: "Wind op het randje",
    ReasonCode.TOO_GUSTY: "Te vlagerig",
    ReasonCode.GUSTY: "Vlagerig",
    ReasonCode.OFFSHORE: "Aflandige wind: niet kiten",
    ReasonCode.SIDE_OFFSHORE: "Schuin aflandige wind: niet kiten",
    ReasonCode.DIRECTION_UNKNOWN: "Windrichting of kustrichting onbekend",
    ReasonCode.DIRECTION_NOT_RIDABLE: "Windrichting niet geschikt voor deze spot",
    ReasonCode.DARK: "Donker",
    ReasonCode.SEASON_CLOSED: "Seizoenssluiting",
    ReasonCode.SPOT_FORBIDDEN: "Kiten verboden op deze spot",
    ReasonCode.SPOT_LIMITED: "Kiten beperkt toegestaan",
    ReasonCode.STATUS_UNKNOWN: "Status van de spot onbekend",
    ReasonCode.TIDE_TOO_LOW: "Waterstand te laag",
    ReasonCode.TIDE_UNFAVORABLE: "Ongunstig getij",
    ReasonCode.TIDE_UNKNOWN: "Getij onbekend",
    ReasonCode.LOW_CONFIDENCE: "Weermodellen zijn het oneens",
}

def worst_verdict(reasons: Iterable[ReasonCode]) -> Verdict:
    """Most severe REASON_EFFECT; Verdict.GO for no reasons."""

class RiderLimits(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    min_kn: float     # finite, >= 0
    max_kn: float     # finite, > min_kn   (model_validator; ValueError otherwise)

class HourEvaluation(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    spot_id: str                      # min_length=1
    valid_at: datetime                # aware -> UTC, whole hour (ValueError otherwise)
    verdict: Verdict
    reasons: tuple[ReasonCode, ...]
    wind_kn: float | None             # >= 0, finite
    gust_kn: float | None             # >= 0, finite
    dir_deg: int | None               # 0..359
    dir_class: DirClass | None
    confidence: Confidence | None
    tide_level_cm: int | None
    # model_validator: reasons unique and in ReasonCode order; verdict == worst_verdict(reasons);
    # dir_class in {offshore, side_offshore} -> verdict == no_go.

    def to_row(self, *, evaluated_at: datetime) -> dict[str, Any]:
        """Row for public.evaluations. Keys exactly: spot_id, valid_at, verdict, reasons
        (list[str]), wind_kn, gust_kn, dir_deg, dir_class (str | None), confidence (str | None),
        tide_level_cm, evaluated_at. Naive evaluated_at -> ValueError."""

def default_limits(spot: SpotProfile) -> RiderLimits: ...
def evaluate_hour(spot: SpotProfile, valid_at: datetime, hours: Sequence[ForecastHour],
                  tides: Sequence[TideExtreme], limits: RiderLimits) -> HourEvaluation: ...
def evaluate_spot(spot: SpotProfile, forecasts: Sequence[ForecastHour],
                  tides: Sequence[TideExtreme], limits: RiderLimits) -> list[HourEvaluation]: ...
```
Geen enkele functie in `direction`, `consensus`, `daylight`, `season` en `evaluation` heeft een parameter (positioneel of keyword) waarmee de offshore-regel of de richtingsklasse te beïnvloeden is. De drempels zijn moduleconstanten, geen parameters.

### `shakka.contracts`
```python
CONTRACTS_DIR: Final[Path] = REPO_ROOT / "data" / "contracts"   # REPO_ROOT from shakka.config
CONTRACT_FILES: Final = ("reason_codes.json", "dir_classes.json", "confidence.json")
GENERATED_NOTE: Final = "Generated by `shakka contracts export` from shakka.domain. Do not edit."

def build_contracts() -> dict[str, str]:
    """{file name: file text} for CONTRACT_FILES, in that order. Text is
    json.dumps(obj, ensure_ascii=False, indent=2) + "\n"."""
def check_contracts(directory: Path | None = None) -> list[str]:
    """Names in CONTRACT_FILES that are missing or differ from build_contracts(); writes nothing.
    directory None -> CONTRACTS_DIR (looked up at call time)."""
def export_contracts(directory: Path | None = None) -> list[str]:
    """Create the directory if needed; write (UTF-8 bytes) only files whose text differs.
    Returns the names written. Other files in the directory are left alone."""
def run_contracts_export(*, check: bool, echo: Callable[[str], None],
                         directory: Path | None = None) -> int: ...
```

**Bestandsinhoud** (volgorde van de items = declaratievolgorde van de enum):
```json
// reason_codes.json
{
  "_generated": "Generated by `shakka contracts export` from shakka.domain. Do not edit.",
  "items": [
    {"code": "no_data", "effect": "no_go", "label_nl": "Geen voorspelling beschikbaar"},
    ...
  ]
}
// dir_classes.json: items {"code": "onshore", "ridable": true, "label_nl": "Aanlandig"}, ...
// confidence.json:  items {"code": "high", "label_nl": "Hoog"}, ...
```
(Commentaarregels staan alleen hier ter uitleg; de bestanden zijn gewone JSON. `indent=2` zet elk item over meerdere regels.)

**CLI** (`shakka contracts export [--check]`), exacte uitvoer:
- export: per bestand `wrote   data/contracts/<naam>` of `ok      data/contracts/<naam> (unchanged)`, daarna `contracts export: ok`. Exit 0.
- `--check`, alles actueel: `ok      data/contracts/<naam>` per bestand, daarna `contracts export: check ok`. Exit 0.
- `--check`, iets mis: `stale   data/contracts/<naam>` (bestaat maar verschilt) of `missing data/contracts/<naam>`, daarna `contracts export: check failed; run 'shakka contracts export'`. Exit 1. Er wordt niets geschreven.

Het pad in de uitvoer is altijd `data/contracts/<naam>`, ook als `directory` in tests anders is. Zo blijft de uitvoer stabiel.

### Consistentie met afhankelijke WP's
- `ForecastHour`, `ModelKey` (WP-03), `TideExtreme`, `estimate_tide_level` (WP-04) en `SpotProfile`, `DirRange`, `SeasonClosure`, `TideSensitivity`, `SpotStatus` (WP-02) worden ongewijzigd gebruikt.
- De waarden van `ReasonCode`, `DirClass`, `Confidence` en `Verdict` zijn exact gelijk aan de CHECK-lijsten in `supabase/migrations/20261015090000_m1_schema.sql` (getest in `test_contracts.py`).
- `HourEvaluation.to_row` geeft exact de kolommen van `evaluations` uit WP-01 en respecteert `evaluations_offshore_is_no_go`.

### Gevolgen voor latere WP's
- **WP-07:** gebruikt `RiderLimits` (min < max is gevalideerd), `RIDABLE_DIR_CLASSES` en `HourEvaluation`. `dir_class` kan `None` zijn (richting onbekend); zo'n uur is altijd `no_go` en telt nooit mee. `HourEvaluation` is alleen consistent te construeren (invarianten); testfixtures van WP-07 moeten `verdict` en `reasons` dus kloppend invullen (bijv. `go` met `()`).
- **WP-08:** labels uit `REASON_LABEL_NL`, `DIR_CLASS_LABEL_NL`, `CONFIDENCE_LABEL_NL`; windroos via `compass_label`.
- **WP-10:**
  - `evaluate_spot(spot, forecasts, tides, default_limits(spot))` alleen voor spots met coördinaten (A7);
  - `HourEvaluation.to_row(evaluated_at=now)` en upsert met `on_conflict=spot_id,valid_at`;
  - laad de getij-extremen van het station voor ten minste [eerste `valid_at` − 10 uur, laatste `valid_at` + 11 uur]. Dat is de interpolatie plus `TIDE_SAMPLE_OFFSET` plus `TIDE_NEIGHBOUR_WINDOW`;
  - het oordeel is `marginal` of slechter zolang `status` leeg is (`status_unknown`), dus pas na het invullen door Lars kunnen er `go`-uren en alerts zijn.
- **WP-14:** `data/contracts/*.json` heeft de vorm `{"_generated": str, "items": [...]}`.

## Edge cases

| # | Geval | Gedrag |
|---|---|---|
| E1 | `hours` leeg of alle waarden `None` | `compute_consensus` geeft `None`, met de redenen `no_data` en `direction_unknown`; `confidence = None`; `no_go`. |
| E2 | Alleen vlaag en/of richting, geen windsnelheid | `no_data` (A6). Consensus bestaat, met `confidence = low`, dus ook `low_confidence`. |
| E3 | Vlaag `None` bij alle modellen | Geen vlaagreden; `gust_kn = None`; betrouwbaarheid hooguit `medium` (A2). |
| E4 | Vlaag bij sommige modellen `None` (laatste uur van de horizon) | Mediaan over de modellen met een vlaag. |
| E5 | `wind_kn = 0` | `wind_too_light`; vlaagcontrole overgeslagen (`w > 0` vereist). |
| E6 | Vlaag lager dan wind (wind neemt af in het uur) | `delta < 0`, dus geen vlaagreden. |
| E7 | Richtingen 350 en 10 | Consensus 0; spreiding 10°. |
| E8 | Richtingen 0 en 180 (twee modellen) | Gemiddelde vector < `DIR_MIN_RESULTANT`, dus `dir_deg = None`, `direction_unknown` en `low`. |
| E9 | Consensusrichting precies 360 na afronding | `% 360` geeft 0. |
| E10 | Eén model beschikbaar | `low` en dus `low_confidence`; een anders `go` uur wordt `marginal`. |
| E11 | Twee modellen, eens | Hooguit `medium`. |
| E12 | `shore_normal_deg` `None` | `direction_unknown`, `dir_class = None`, `no_go`. |
| E13 | Offshore-richting binnen `ridable_dirs` | `offshore` of `side_offshore`; geen `direction_not_ridable` (de klasse gaat voor). |
| E14 | `ridable_dirs` over het noorden (`{from: 300, to: 20}`) | Wind uit 350 en 10 erbinnen, 21 en 299 erbuiten. |
| E15 | `d` precies op een klassegrens (bijv. 100 bij hele graden) | Hoort bij de lagere klasse (bovengrens inclusief): 100 is `sideshore`, 101 is `side_offshore`. |
| E16 | Wind precies `min_kn` of `max_kn` | Niet te licht of te sterk, wel `wind_borderline`. |
| E17 | `min_kn + 2 > max_kn - 2` (smalle limieten) | Beide borderline-voorwaarden kunnen gelden; de code komt één keer voor. |
| E18 | Uur gedeeltelijk binnen een seizoensvenster (venster 10:30–18:00, uur 10:00) | Gesloten (overlap). |
| E19 | Seizoen tot en met `03-28`, uur 2026-03-28 23:00Z (lokaal 29-03 00:00 CET) | Open: de lokale datum telt. |
| E20 | Uur rond de wintertijdovergang (25-10-2026 00:00Z en 01:00Z zijn beide lokaal 02:00) | Beide worden apart en correct beoordeeld in UTC; geen fout. |
| E21 | `02-29` als einde in een niet-schrikkeljaar | Tot en met 28-02. |
| E22 | Getijgevoelig, `rws_station` `None` | `tide_unknown`; `tide_level_cm = None`. |
| E23 | Extremen van een ander station in `tides` | Genegeerd. |
| E24 | `rws_station` met spaties eromheen | `strip()` vóór de vergelijking (zoals WP-04). |
| E25 | Meetmoment buiten het bereik van de extremen of bij een gat van meer dan 9 uur | `estimate_tide_level` geeft `None`, dus `tide_unknown`. |
| E26 | Agger: twee laagwaters, topagger niet opgeslagen | Positie dicht bij 0, dus "rond laagwater" (getest). |
| E27 | Alleen laagwaters binnen 9 uur (onvolledige reeks) | `relative_tide_position` geeft `None`; bij `prefer_*` en bij `avoid_low` zonder minimum volgt `tide_unknown`; een `tide_too_low`-controle met het niveau gebeurt wel. |
| E28 | `tide_sensitive: none` met station en extremen | `tide_level_cm` gevuld, geen getij-reden. |
| E29 | Geschatte stand precies gelijk aan `tide_min_level_cm` | Niet te laag (strikt `<`). |
| E30 | Spot zonder `lat`/`lon` in `evaluate_hour` | `ValueError` (A7). |
| E31 | `valid_at` naïef of geen heel uur | `ValueError`. |
| E32 | `ForecastHour` van een andere spot of ander uur | `ValueError`. |
| E33 | Dubbel model in één uur | `ValueError` uit `compute_consensus`. |
| E34 | Forecasts in willekeurige volgorde | `evaluate_spot` sorteert op `valid_at`; elke `valid_at` één keer. |
| E35 | `status` `None` (alle huidige spots) | `status_unknown`, hooguit `marginal`. |
| E36 | `HourEvaluation` handmatig gemaakt met `go` en redenen, of offshore met `go` | `ValidationError` (subklasse van `ValueError`). |
| E37 | `data/contracts/` bestaat niet | `export` maakt de map aan; `--check` meldt drie keer `missing`. |
| E38 | Extra bestand in `data/contracts/` | Genegeerd door export en check. |
| E39 | Astral zonder `date` | Komt niet voor: `date` wordt altijd meegegeven (code review en de puurheidsregel; astral leest anders de klok). |

## Testplan
Tests eerst voor alle domeinlogica. Er wordt geen netwerk gebruikt en er zijn geen tijdafhankelijke tests (`now` komt niet voor).

### Fixtures (`ingest/tests/evaluation_fixtures.py`)
```python
LAT, LON = 52.47, 4.57                                 # test coordinates (WP-05 AC-5), not spot data
NOON = datetime(2026, 7, 15, 10, tzinfo=UTC)           # 12:00 local, daylight, no season in base spot
LIMITS = RiderLimits(min_kn=12, max_kn=30)
STATION = "teststation"

def make_spot(**overrides) -> SpotProfile:
    """Base: id='test-strand', name='Teststrand', lat=LAT, lon=LON, shore_normal_deg=270,
    status='allowed', level='intermediate', verified=False; overrides via model_validate."""

def model_hours(valid_at, *, wind=20.0, gust=24.0, dir_deg=270,
                models=tuple(ModelKey), spot_id="test-strand") -> list[ForecastHour]:
    """Same values for each model."""

def per_model(valid_at, values: Mapping[ModelKey, tuple[float | None, float | None, int | None]],
              spot_id="test-strand") -> list[ForecastHour]:
    """(wind, gust, dir) per model."""

def extremes(*points: tuple[datetime, str, int], station=STATION) -> list[TideExtreme]: ...
```
De basis (`make_spot()`, `model_hours(NOON)`, geen getij, `LIMITS`) geeft `go` met `reasons == ()`. Dat is de eerste test in `test_evaluation.py` (`test_baseline_is_go`). Elke andere test verandert één ding ten opzichte van die basis.

### Per acceptatiecriterium

**AC-1 (richting), `test_direction.py`:**
- `test_examples_270`: geparametriseerd over (270 → onshore), (225, 315 → side_onshore), (180, 0 → sideshore), (135, 45 → side_offshore), (90 → offshore).
- `test_wraparound`: normaal 10 en wind 350 → onshore; normaal 350 en wind 10 → onshore.
- `test_exhaustive_symmetry_and_monotonic`: voor normaal ∈ {0, 45, 270, 359} en elke gehele wind 0..359:
  - `classify(normal + d) == classify(normal - d)` voor d = 0..180;
  - de rang (onshore = 0 … offshore = 4) is niet-dalend in `angular_distance` (sorteer op afstand en controleer).
- `test_class_boundaries`: d = 22 en 23, 67 en 68, 100 en 101, 157 en 158 (normaal 0) geven de verwachte klassen.
- `test_thresholds_ordered` (zie Interfaces).
- `test_in_ranges`: `{200, 340}` met 200, 340 (in), 199, 341 (uit); wrap `{300, 20}` met 350, 0, 20 (in), 21, 299 (uit); `from == to`; lege lijst geeft `False`; meerdere bereiken.
- `test_compass_label`: 0 → N, 11.24 → N, 11.25 → NNO, 90 → O, 180 → Z, 225 → ZW, 270 → W, 348.75 → N, 359.9 → N, -10 → N; alle 16 labels komen voor bij 0, 22.5, …, 337.5.
- `test_angular_distance_invalid`: NaN geeft `ValueError`.

**AC-2 (veiligheid), `test_evaluation_safety.py`:**
- `test_offshore_always_no_go`: voor normaal in `range(0, 360, 15)` en elke gehele wind met `classify_direction` in {offshore, side_offshore}:
  - spot met `ridable_dirs=[{from: 0, to: 359}]`, `status: allowed`;
  - `model_hours(NOON, wind=20, gust=24, dir_deg=wind_from)`;
  - `RiderLimits(min_kn=0, max_kn=100)`.

  Verwacht: `verdict == no_go` en `offshore` of `side_offshore` (passend bij de klasse) in `reasons`, en `dir_class` gelijk aan die klasse.
- `test_offshore_no_go_under_variants`: voor elke 5e gehele wind uit de offshore-set van normaal 270, elk van deze varianten:
  - limieten `(0, 100)`, `(12, 30)`, `(25, 26)`;
  - een getijgevoelige spot (`prefer_low`) op laagwater;
  - een spot zonder getij;
  - modellen die het oneens zijn (`low`);
  - modellen die het eens zijn (`high`).

  Altijd `no_go` met de offshore-reden.
- `test_no_bypass_parameters`: `inspect.signature` van de publieke functies moet exact deze parameternamen hebben:
  - `evaluate_hour`: (`spot`, `valid_at`, `hours`, `tides`, `limits`);
  - `evaluate_spot`: (`spot`, `forecasts`, `tides`, `limits`);
  - `classify_direction`: (`wind_from_deg`, `shore_normal_deg`);
  - `compute_consensus`: (`hours`);
  - `default_limits`: (`spot`).

  Daarnaast: geen enkele publieke functie in `shakka.domain.evaluation` en `shakka.domain.direction` heeft een parameter waarvan de naam `offshore`, `allow`, `override`, `force` of `unsafe` bevat.
- `test_model_rejects_offshore_go`: `HourEvaluation(..., dir_class=offshore, verdict=go, reasons=())` geeft `ValidationError`.

**AC-3 (onbekende richting en `ridable_dirs`), `test_evaluation.py`:**
- `test_no_shore_normal_every_hour`: `make_spot(shore_normal_deg=None)` en `evaluate_spot` over 24 uur → elk uur `no_go` met `direction_unknown` en `dir_class is None`.
- `test_ridable_dirs_restricts`: `ridable_dirs=[{from: 200, to: 340}]`, wind 190 → `sideshore` en `direction_not_ridable`; wind 270 → geen richtingsreden.
- `test_ridable_dirs_cannot_allow_offshore` (wind 90 binnen `{0, 359}`) → `offshore`, niet `direction_not_ridable`.

**AC-4 (wind en vlagen), `test_evaluation.py`**, met `LIMITS (12, 30)`, gelijke modellen en gust = wind + 2 (tenzij anders):

| Wind | Verwacht |
|---|---|
| 11.9 | `wind_too_light` |
| 12.0, 13.9 | `wind_borderline` |
| 14.0, 28.0 | geen windreden |
| 28.1, 30.0 | `wind_borderline` |
| 30.1 | `wind_too_strong` |

Vlagen:

| Wind / vlaag | Ratio, delta | Verwacht |
|---|---|---|
| 20 / 31.9 | 1.595, 11.9 | geen |
| 20 / 32.0 | 1.6, 12 | `gusty` |
| 20 / 37.9 | 1.895, 17.9 | `gusty` |
| 20 / 38.0 | 1.9, 18 | `too_gusty` (zonder `gusty`) |
| 12 / 19.9 | 1.66, 7.9 | geen (delta te klein) |
| 12 / 20.0 | 1.67, 8.0 | `gusty` |
| 20 / `None` (alle modellen) | onbekend | geen vlaagreden, `gust_kn is None`, betrouwbaarheid `medium` |
| 20 / 18 | delta < 0 | geen |

Verder `test_default_limits`: spot zonder default geeft (12, 30); `default_min_kn: 14` geeft (14, 30); `default_min_kn: 35` geeft (35, 40). En `test_rider_limits_invalid`: min ≥ max, negatief of NaN geven `ValidationError`.

**AC-5 (daglicht), `test_daylight.py`:**
- `is_daylight(52.47, 4.57, 2026-06-21 03:00Z) is False`.
- `is_daylight(52.47, 4.57, 2026-06-21 12:00Z) is True`.
- `is_daylight(52.47, 4.57, 2026-12-21 17:00Z) is False`.
- `test_sun_times_plausible`: zonsopkomst op 21-06-2026 tussen 03:10 en 03:30Z, zonsondergang tussen 19:55 en 20:15Z. Op 21-12-2026 tussen 07:35 en 08:00Z en tussen 15:20 en 15:45Z. Ter controle: IJmuiden 21-06-2026 zonsopkomst 05:19 en zonsondergang 22:04 lokale tijd, zie Externe afhankelijkheden.
- `test_margin_boundaries`: met `sr, ss = sun_times(LAT, LON, date(2026, 6, 21))`:
  - `is_daylight(sr - 15 min)` is `True`, `is_daylight(sr - 15 min - 1 s)` is `False`;
  - `is_daylight(ss + 15 min - 1 h)` is `True`, `is_daylight(ss + 15 min - 1 h + 1 s)` is `False`.
- `test_naive_raises`; `test_winter_daylight_hours`: op 21-12-2026 zijn de daglichturen (UTC) precies 08:00 t/m 14:00.

  De builder controleert dat laatste met de echte astral-uitkomst. Wijkt het af, dan past hij alleen de verwachting aan en meldt dat in `deviations.md`, want het is een gevolg van de marge en geen ontwerpkeuze.
- Via `evaluate_hour`: `make_spot()` op 2026-06-21 03:00Z heeft `dark` in de redenen.

**AC-6 (seizoen en status), `test_season.py` en `test_evaluation.py`.** Sluiting S = `{start: "05-01", end: "09-30", from_time: "10:00", to_time: "18:00"}`.
- 15-07-2026 12:00 lokaal (10:00Z) is gesloten; 19:00 lokaal (17:00Z) open; 15-10-2026 12:00 lokaal (10:00Z) open.
- Grenzen: 15-07 09:00 lokaal (07:00Z) open, 17:00 lokaal (15:00Z) gesloten, 18:00 lokaal (16:00Z) open.
- Over de jaargrens: `{start: "11-15", end: "02-15"}` geldt op 10-01-2027 12:00Z en niet op 16-02-2027 12:00Z.
- Zomer- en wintertijd, met `{start: "03-01", end: "11-30", from_time: "10:00", to_time: "18:00"}`:
  - 28-03-2026 (CET): 09:00Z gesloten, 08:00Z open;
  - 29-03-2026 (CEST): 08:00Z gesloten, 07:00Z open, 16:00Z open, 15:00Z gesloten;
  - 24-10-2026 (CEST): 08:00Z gesloten, 07:00Z open;
  - 25-10-2026 (CET): 09:00Z gesloten, 08:00Z open, 17:00Z open, 16:00Z gesloten.
- Lokale datum: `{start: "03-01", end: "03-28"}` (hele dag) is gesloten op 28-03-2026 22:00Z (lokaal 23:00) en open op 28-03-2026 23:00Z (lokaal 29-03 00:00 CET; de zomertijd begint pas om 01:00Z).
- Gedeeltelijke overlap: venster 10:30–18:00, uur 08:00Z op 15-07 (lokaal 10:00–11:00) is gesloten.
- `02-29`: `in_period("12-01", "02-29", date(2027, 2, 28))` is `True`, `date(2027, 3, 1)` is `False`; `in_period("02-29", "03-31", date(2027, 3, 1))` is `True`.
- Status via `evaluate_spot` over 6 daguren: `forbidden` geeft elk uur `spot_forbidden` (`no_go`); `limited` geeft elk uur `spot_limited` (`marginal`); `None` geeft elk uur `status_unknown` (`marginal`); `allowed` geeft geen statusreden.

**AC-7 (getij), `test_evaluation.py` en `test_tide_position.py`.** Synthetische reeks (station `teststation`): hoogwater +100 om 00:30Z, 12:30Z en 00:30Z van de volgende dag, laagwater -80 om 06:30Z en 18:30Z, op 15-07-2026. Het meetmoment van uur 12:00Z is 12:30Z, precies op hoogwater.
- `none` met dezelfde extremen: geen getij-reden op 06:00Z, 09:00Z en 12:00Z; `tide_level_cm` is gevuld (A8).
- `avoid_low`, `tide_min_level_cm: 0`, extremen met laagwater -50 om 06:30Z: uur 06:00Z geeft `tide_too_low`.
- `prefer_low` op hoogwater (12:00Z) geeft `tide_unfavorable`; op laagwater (06:00Z) geen getij-reden.
- `prefer_high` op laagwater geeft `tide_unfavorable`; op hoogwater niets.
- `avoid_low` zonder minimum: op laagwater `tide_unfavorable`, op hoogwater niets.
- Getijgevoelige spot zonder extremen geeft `tide_unknown`; met `rws_station: None` ook; met alleen extremen van `anderstation` ook (E23).
- `ev.tide_level_cm == estimate_tide_level(ext, valid_at + TIDE_SAMPLE_OFFSET)` voor 06:00Z, 09:00Z en 12:00Z.
- `test_tide_position.py`:
  - op hoogwater 1.0, op laagwater 0.0, halverwege 0.5 ± 0.01;
  - agger: laag -60 om 10:00Z, laag -55 om 14:00Z, hoog +120 om 19:00Z en een hoog +110 om 03:00Z. Op 12:00Z is de positie ≤ 0.05, op 16:30Z 0.5 ± 0.05;
  - alleen laagwaters binnen 9 uur geeft `None`;
  - een gelijke afstand tot twee laagwaters kiest het vroegste;
  - `high.level <= low.level` geeft `None`.

**AC-8 (consensus), `test_consensus.py` en `test_evaluation.py`:**
- Vier modellen (20.0, 20.5, 19.8, 20.2 kn; richtingen 268–272; vlagen gezet) geven `high`, met `wind_kn == 20.1` (mediaan) en `dir_deg == 270`.
- Snelheidsspreiding: (10, 12, 18.1, 14) heeft spreiding 8.1 en geeft `low`; (10, 12, 18, 14) heeft spreiding 8.0 en is niet `low` (grens). Richtingsspreiding: (270, 270, 270, 320) heeft een afwijking > 45 en geeft `low`.
- Integratie: hetzelfde uur dat met gelijke modellen `go` is, wordt met de `low`-modellen `marginal` met `low_confidence`. Een uur dat `no_go` is (wind 5) blijft `no_go` en bevat ook `low_confidence`.
- Eén model geeft `low`, gedocumenteerd in de docstring. Twee gelijke modellen geven `medium`.
- Alle modellen `None` (rijen met drie keer `None`) geeft `compute_consensus is None`; `evaluate_hour` geeft `no_data` en `no_go`. `hours == []` doet hetzelfde.
- Richtingen 350 en 10 geven `dir_deg == 0` (± 1, rekening houdend met de wrap: `angular_distance(dir_deg, 0) <= 1`), niet 180.
- 0 en 180 geven `dir_deg is None` en `low` (E8).
- `models_used` volgt de `ModelKey`-volgorde, ook bij invoer in omgekeerde volgorde. Een model met alleen een vlaag telt mee.
- Fouten: dubbel model, gemengde `valid_at`, gemengde `spot_id` geven `ValueError`.
- Afronding: 12.3 en 8.3 plus twee modellen met 10.0 geven `speed_spread_kn == 4.0` en dus `high` (geen floatfout).

**AC-9 (eigenschappen), `test_evaluation_properties.py`:**
- Raster:
  - spots: basis; `shore_normal_deg None`; `forbidden`; `limited`; `status None`; `prefer_low` met getijreeks; seizoen S; `ridable_dirs {200, 340}`;
  - uren: 2026-07-15 00:00Z t/m 23:00Z;
  - modelsets: eens, oneens, één model, `None`;
  - richtingen 0, 90, 180, 270.

  Per evaluatie gelden `verdict == worst_verdict(reasons)`, `(verdict == go) == (reasons == ())`, `reasons` zonder dubbelen en in `ReasonCode`-volgorde, en offshore-klassen zijn `no_go`.
- `evaluate_spot` met dezelfde invoer twee keer geeft gelijke lijsten (`==`). De invoer wordt gehusseld met een vaste permutatie (omgekeerd plus om-en-om), zonder `random`. Het resultaat is gesorteerd op `valid_at` en elke `valid_at` komt één keer voor.
- `REASON_EFFECT` en `REASON_LABEL_NL` dekken elke `ReasonCode`; `REASON_EFFECT` is exact de tabel uit WORK_PACKAGES (expliciete dict in de test).
- `HourEvaluation.to_row` heeft exact de kolommen van `evaluations`, en `reasons` is een `list[str]`.

**AC-10 (contracten), `test_contracts.py`:**
- `test_repo_files_up_to_date`: `check_contracts() == []`. De melding noemt `uv run shakka contracts export`.
- `test_files_cover_all_codes`: de JSON-bestanden van schijf bevatten elke `ReasonCode`, `DirClass` en `Confidence` exact één keer, met een niet-lege `label_nl`. `effect` is gelijk aan `REASON_EFFECT` en `ridable` aan `RIDABLE_DIR_CLASSES`.
- `test_codes_match_migration`: de lijsten in de CHECK-constraints `evaluations_reasons_enum`, `evaluations_dir_class_enum`, `evaluations_confidence_enum` en `evaluations_verdict_enum` (met een regex uit de SQL van `supabase/migrations/*.sql`) zijn gelijk aan de enumwaarden.
- `test_export_and_check_tmp` (`tmp_path`):
  - op een lege map geeft check drie namen;
  - export schrijft er drie;
  - daarna geeft check `[]` en schrijft een tweede export niets;
  - een gewijzigd bestand geeft `stale`;
  - een extra bestand `other.json` blijft onaangeroerd.
- CLI (CliRunner):
  - `contracts export --check` op de repo geeft exit 0 en `contracts export: check ok`;
  - met `shakka.contracts.CONTRACTS_DIR` gemonkeypatcht naar een lege `tmp_path`: `--check` geeft exit 1 met `missing data/contracts/reason_codes.json` en schrijft niets;
  - `export` geeft exit 0 met drie keer `wrote`.
- `--help` van `shakka` toont `contracts`.

**AC-11:** `tests/test_domain_purity.py` vindt de nieuwe modules automatisch (`rglob`) en is groen. Extra controle in `test_daylight.py`: de bron van `daylight.py` bevat bij elke aanroep van `sunrise(` en `sunset(` het keyword `date=`. Dat gaat met een AST-check op de keywords van die calls.

## Externe afhankelijkheden
- **astral 3.2** (PyPI, laatste release 5-11-2022, Apache-2.0, geen runtime-dependencies op Python ≥ 3.9). Gecontroleerd op 15-10-2026:
  - https://pypi.org/project/astral/
  - API: https://astral.readthedocs.io/en/latest/package.html. `astral.Observer(latitude, longitude, elevation=0.0)`, `astral.sun.sunrise(observer, date=None, tzinfo=timezone.utc)` en `astral.sun.sunset(...)` geven aware datetimes in `tzinfo`. Ze geven een `ValueError` als de zon niet opkomt of ondergaat. Zonder `date` gebruiken ze "today" in `tzinfo`. Daarom geven wij `date` altijd mee.
  - Broncode: https://github.com/sffjunkie/astral/blob/master/src/astral/sun.py. Als de berekende tijd op een andere datum valt dan gevraagd, rekent astral opnieuw voor de buurdag. Voor UTC en Nederlandse lengtegraden speelt dat niet.

  Installatie: `cd ingest && uv add "astral>=3.2,<4"`.
- **Referentie voor de daglichttest:** zonsopkomst in IJmuiden op 21-06-2026 om 05:19 en zonsondergang om 22:04 lokale tijd (zoekresultaat op weeronline.nl, https://www.weeronline.nl/Europa/Nederland/IJmuiden/4058361/zonsopkomst-en-zonsondergang, en KNMI-tabel 2026: https://cdn.knmi.nl/system/downloads/files/000/000/075/original/tijden_van_zonopkomst_en_-ondergang_2026.pdf). De tests gebruiken ruime vensters, geen exacte minuten.
- **Tijdzonedata:** `zoneinfo` gebruikt de tz-database van het systeem (macOS en Ubuntu-runners hebben die; `tests/test_db.py` gebruikt `ZoneInfo("Europe/Amsterdam")` al in CI). Geen `tzdata`-package nodig.
- Geen API-endpoints, geen netwerk, geen kosten.

## Risico's
- **R1. Drempels zijn niet gekalibreerd op echte sessies.** Mitigatie: alles in `defaults.py`, onderbouwd in "Drempelwaarden". Lars toetst in de M1-testweek; een wijziging is één constante plus de grenstests.
- **R2. Vlaagbias verschilt per model.** KNMI Harmonie en GFS geven veel hogere vlagen dan ECMWF en ICON (zie de toelichting bij de vlagerigheid). De mediaan dempt dit, maar een dag met alleen GFS-vlagen (bijv. als andere vlagen `None` zijn) kan vals `gusty` geven. Mitigatie: drempels hoog gezet; per-modelnormalisatie is een mogelijke vervolgstap na de testweek (scopebesluit van Lars).
- **R3. `SIDESHORE_MAX_DEG = 100` laat 10° aflandige component toe als "sideshore".** Dit is de veiligheidskritische grens. Mitigatie: expliciet benoemd voor Lars, met het strengere alternatief 90; de kustrichting per spot verifieert Lars zelf.
- **R4. Alle 25 startspots hebben nog geen `status` of `shore_normal_deg`.** Elk uur is daardoor `no_go` (`direction_unknown`) of hooguit `marginal`, en alerts komen pas als Lars de profielen invult. Dat is bewust (geen verzonnen data) en staat onder "Gevolgen voor latere WP's".
- **R5. Daglichtgrens van AC-5 ligt 4 minuten van de marge** (03:00Z tegen 03:19Z − 15 min). De uitkomst van astral is deterministisch, dus de test is stabiel. Maar een marge van 20 min of meer zou AC-5 breken. Dat staat in de onderbouwing.
- **R6. Winterse middag.** Door de regel "het hele uur binnen daglicht met marge" valt in december het laatste deeluur (lokaal 16:00–16:30) weg. Dat is conservatief en verstelbaar via `DAYLIGHT_MARGIN_AFTER_SUNSET`.
- **R7. Nieuwe redencodes vragen een migratie** (WP-01 R5). Deze WP voegt geen codes toe; `test_codes_match_migration` bewaakt dat.
- **R8. Prestaties.** 25 spots × 168 uur geeft ca. 4.200 evaluaties per run, met pydantic en een gecachete astral. Ruim onder een seconde tot enkele seconden; niet kritiek.

## Buiten scope
- Evaluaties opslaan, opruimen en de job (WP-10). Alleen de pure mapping `to_row` hoort hier.
- Persoonlijke alertregels, profiel-limieten en windows (WP-07).
- Kite-advies (WP-06), berichten (WP-08).
- Golven (niet in de evaluatie volgens het plan).
- Wijzigingen aan de database, `ForecastHour`, de forecast- of getij-ingest.
- Per-model vlaagcorrectie of -weging (zie R2), en weging van modellen in de consensus.
- UI en weergave van de labels (WP-14).

## Stappenplan voor de builder
Werk op branch `wp/WP-05` in de worktree `/Users/larst/Dev/Shakka/.claude/worktrees/WP-05`. Lees of print `.env` nooit. Na elke stap vanuit `ingest/`: `uv run pytest && uv run ruff check . && uv run ruff format --check .`. Eén commit per stap, commitberichten in het Engels. Tests gebruiken altijd aware datetimes (`tzinfo=UTC`), want ruff `DTZ` staat aan.

1. **Dependency.** `cd ingest && uv add "astral>=3.2,<4"`. Alleen `pyproject.toml` (één regel) en `uv.lock` wijzigen. De suite is groen.
   Commit: `build(ingest): add astral`.
2. **Defaults en richting, eerst de tests.**
   - Schrijf `tests/test_direction.py` (AC-1, `in_ranges`, `compass_label`, `test_thresholds_ordered`). Rood.
   - Implementeer `domain/defaults.py` (alle constanten uit Interfaces) en `domain/direction.py`. Groen, inclusief de puurheidstest.

   Commit: `feat(domain): add evaluation thresholds and direction classes`.
3. **Consensus, eerst de tests.**
   - Schrijf `tests/evaluation_fixtures.py` (alleen de helpers die nu al kunnen: `model_hours`, `per_model`) en `tests/test_consensus.py`. Rood.
   - Implementeer `domain/consensus.py`. Groen.

   Commit: `feat(domain): add multi-model consensus and confidence`.
4. **Daglicht, eerst de tests.**
   - Schrijf `tests/test_daylight.py`. Rood.
   - Implementeer `domain/daylight.py`. Groen. Klopt `test_winter_daylight_hours` niet met de echte astral-uitkomst, pas dan alleen de verwachte uren aan en noteer het in `deviations.md` (zie Testplan AC-5).

   Commit: `feat(domain): add daylight check with astral`.
5. **Seizoen, eerst de tests.**
   - Schrijf `tests/test_season.py`. Rood.
   - Implementeer `domain/season.py`. Groen.

   Commit: `feat(domain): add season closures in local time`.
6. **Getijpositie, eerst de tests.**
   - Schrijf `tests/test_tide_position.py`. Rood.
   - Voeg `relative_tide_position` toe aan `domain/tide.py`. Groen; de bestaande `test_domain_tide.py` blijft groen.

   Commit: `feat(domain): add relative tide position between low and high water`.
7. **Evaluatie, eerst de tests.**
   - Maak `tests/evaluation_fixtures.py` af (`make_spot`, `extremes`, `NOON`, `LIMITS`).
   - Schrijf `tests/test_evaluation.py`, `tests/test_evaluation_safety.py` en `tests/test_evaluation_properties.py`. Rood.
   - Implementeer `domain/evaluation.py` volgens Ontwerp (stappen 0–10, invarianten in `HourEvaluation`). Groen.

   Commit: `feat(domain): add hourly spot evaluation with reasons`.
8. **Contracten en CLI, eerst de tests.**
   - Schrijf `tests/test_contracts.py`. Rood.
   - Implementeer `src/shakka/contracts.py` en de groep `contracts` in `cli.py`.
   - Draai `uv run shakka contracts export` en controleer de drie bestanden in `data/contracts/` op leesbare Nederlandse labels. Groen, inclusief `uv run shakka contracts export --check` met exit 0.

   Commit: `feat(contracts): export reason codes, direction classes and confidence labels`.
9. **Documentatie.** Werk `docs/SPOT_DATA.md` §4 en §7 bij (zie Bestanden). `test_spot_docs.py` blijft groen.
   Commit: `docs: document direction class bounds and tide preference`.
10. **Eindcontrole.** Volledige suite, ruff, `uv run shakka contracts export --check` en `uv run shakka --help` (toont `contracts`). Controleer met `git status` dat er geen bestanden buiten de lijst in "Bestanden" zijn gewijzigd.
