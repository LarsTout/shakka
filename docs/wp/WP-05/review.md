# Review WP-05, ronde 2
Oordeel: APPROVED

Ronde 2 (blueprint revisie 2). Getoetst: de afhandeling van B-1 en B-2 uit ronde 1, de verwerking van N-1 t/m N-8, en het latere besluit van de orchestrator om de klasse te bepalen op de onafgeronde consensusrichting (`Consensus.dir_mean_deg`, `DIR_MEAN_DECIMALS = 6`, A15, E41, `test_rounding_never_makes_offshore_ridable`).

## Blokkerend
Geen.

## Controle van de punten uit ronde 1

**B-1 is opgelost.** `SIDESHORE_MAX_DEG = 90.0` met inclusieve bovengrens staat overal consistent: A1 (uitzondering), A14, de klassentabel in Ontwerp/Richting, Drempelwaarden, Interfaces/defaults, E15, `test_class_boundaries` (90/91, 270/269 bij normaal 0, en 180/0 tegen 179/1 bij normaal 270), R3 en de tekst voor SPOT_DATA §4. Het rekenvoorbeeld voor 270 klopt: 180 en 0 hebben d = 90 en zijn sideshore, 135 en 45 hebben d = 135 en zijn side_offshore, 90 heeft d = 180 en is offshore. `test_sideshore_bound_is_hard_rule` legt de waarde en de equivalentie `d > 90` ⇔ offshore-klasse vast. In de blueprint komt geen 100°-grens meer voor (de enige resterende "100" staat in het O1-voorbeeld en is daar correct).

**B-2 is opgelost.** Zelf nagerekend:
- (270, 270, 270, 0): de vectorsom is (−3, 1), dus het gemiddelde is ca. 288,43°, `dir_deg` 288, de spreiding 71,6 en de uitkomst `low`.
- (270, 270, 270, 320): het gemiddelde is ca. 281,88°, `dir_deg` 282, de spreiding 38,1 en de uitkomst `medium`, want 20 < 38,1 ≤ 45 en `n_wind` = `n_dir` = 4.

**N-1 t/m N-8** zijn verwerkt zoals beschreven:
- N-1: `model_copy` is overschreven en valideert opnieuw. Het verbod op `model_construct` wordt getest.
- N-2: de klasse en de reden zijn nu in beide richtingen aan elkaar gekoppeld (invariant 3 en 4).
- N-3: staat onder "Gevolgen voor latere WP's".
- N-4: regel 4 eist nu ook `n_dir`.
- N-5 t/m N-7: vastgelegd als O1 t/m O3.
- N-8: de tekst is aangepast.

## Is de harde regel nu waterdicht?
- **Het pad in `evaluate_hour`.** Eerst wordt de klasse bepaald op `dir_mean_deg`. Pas daarna volgt de `ridable_dirs`-controle, en alleen voor rijdbare klassen. Geen enkele parameter beïnvloedt de klasse; dat wordt getest met `test_no_bypass_parameters`. `REASON_EFFECT` geeft `offshore` en `side_offshore` als `no_go`. Ook `ridable_dirs = {0, 359}` kan een offshore-uur niet vrijgeven (E13, `test_ridable_dirs_cannot_allow_offshore`).
- **Grensgevallen.** De invoer bestaat uit hele graden: `ForecastHour.dir_deg` en `SpotProfile.shore_normal_deg` zijn allebei `int`. Bij gelijke modellen is `dir_mean_deg` daardoor na afronding exact die gehele waarde, en `angular_distance` op gehele floats is exact. Precies 90 is dus sideshore en 91 side_offshore, zonder floatruis. Wijkt het gemiddelde af door spreiding, dan valt alles boven 90 naar side_offshore. Twee voorbeelden:
  - (90, 90, 90, 91) geeft ca. 90,2500° en dus side_offshore.
  - (88, 91, 91, 90) heeft als rekenkundig gemiddelde precies 90, maar circulair ca. 90,000076°. Ook dat wordt side_offshore, met `dir_deg` 90. Dat is de veilige kant, zoals A15 beschrijft.
- **4×180 en 4×0 bij normaal 270.** Het gemiddelde komt exact op 180,0 en 0,0 uit, dus d = 90 en sideshore. Dat klopt: de wind waait exact evenwijdig aan de kust. De afronding werkt hier zoals bedoeld. Afronden vóór de `% 360` voorkomt bovendien de Python-valkuil `-1e-20 % 360 == 360.0`: de kleinste negatieve waarde na afronding is −1e-6, en die geeft 359,999999.
- **`model_copy`.** De signature `model_copy(self, *, update: Mapping[str, Any] | None = None, deep: bool = False) -> Self` klopt met de pydantic-broncode (pydantic 2.14.1 in `uv.lock`). Het origineel kopieert via `__copy__`/`__deepcopy__` en zet `update` rechtstreeks in `__dict__`, zonder validatie. De override sluit dat gat. `__copy__` en `__deepcopy__` roepen `model_copy` niet aan en maken alleen identieke kopieën, dus daarmee is geen inconsistent object te maken. `model_dump()` houdt in Python-modus de enum-leden, tuples en aware datetimes intact. Overblijvende uitwegen zijn `model_construct` (getest verboden in `src`) en `object.__setattr__`/`__dict__`-manipulatie (niet realistisch). Daarmee is de validatie voldoende afgedekt.
- **DB-contract.** Er is geen CHECK die `dir_deg` aan `dir_class` koppelt (`evaluations_dir_range` en `evaluations_offshore_is_no_go` zijn de enige). `dir_deg = 90` met `dir_class = side_offshore` en `no_go` is dus in de database geldig.

## Niet-blokkerend
N-1: De zin in A15 "afronden mag een aflandig uur nooit rijdbaar maken" is wiskundig niet absoluut. Een echt gemiddelde in (90, 90 + 5e-7] wordt door `round(…, 6)` 90,0 en dus sideshore. Bij invoer in hele graden en weinig spreiding is de kleinste afwijking boven een geheel getal ca. 7,6e-5° (bijv. (88, 91, 91, 90)): ruim boven 5e-7, dus die blijft side_offshore. Alleen bij extreme spreiding is een toevallige bijna-opheffing onder 5e-7° denkbaar. Zo'n uur heeft dan `dir_spread_deg` > 45, dus `low_confidence` en hooguit `marginal`, en een aflandige component van orde 1e-8 van de wind. Er is dus geen praktisch risico. Voorstel: formuleer de zin als "de afronding verschuift de richting hooguit 5e-7°, ver onder de meetnauwkeurigheid".

N-2: `Consensus` koppelt `dir_deg` en `dir_mean_deg` niet aan elkaar, en `dir_mean_deg` heeft default `None`. Stap 5 controleert `c.dir_deg is None` en gebruikt daarna `c.dir_mean_deg`. Via `compute_consensus` zijn ze altijd samen gezet, en `evaluate_hour` krijgt nooit een kant-en-klare `Consensus` binnen, dus het pad is niet bereikbaar. Toch is een kleine `model_validator` op `Consensus` goedkoop en maakt die het contract expliciet. De validator eist:
- `(dir_deg is None) == (dir_mean_deg is None)`;
- `0 <= dir_mean_deg < 360`;
- `dir_deg == int(round(dir_mean_deg)) % 360`.

Laat stap 5 dan op `c.dir_mean_deg is None` controleren. De builder mag dit meenemen zonder dat het ontwerp verandert.

N-3: In `test_rounding_never_makes_offshore_ridable`, tweede bullet: `dir_mean_deg` is geen veld van `HourEvaluation`. De test moet `dir_mean_deg` daarom via `compute_consensus` op dezelfde uren controleren, en `dir_class`/`verdict`/`reasons` via `evaluate_hour`. Dat is duidelijk genoeg voor een builder, maar het mag expliciet. Neem (88, 91, 91, 90) bij normaal 0 eventueel op als extra geval: het rekenkundige gemiddelde is 90, het circulaire ca. 90,000076, dus side_offshore.

N-4: `dir_deg = int(round(dir_mean_deg))` gebruikt Pythons bankiersafronding (90,5 → 90, 91,5 → 92). Dat is alleen informatief en raakt de klasse niet. Een half-up-afronding kan ook, maar is niet nodig.

## Gecontroleerde bronnen
- https://raw.githubusercontent.com/pydantic/pydantic/main/pydantic/main.py (`BaseModel.model_copy`: signature en implementatie zonder validatie; `__copy__`/`__deepcopy__` roepen `model_copy` niet aan)
- Lokaal: `ingest/uv.lock` (pydantic 2.14.1), `ingest/src/shakka/domain/forecast.py` (`dir_deg: int | None`, 0..359), `ingest/src/shakka/domain/spot.py` (`shore_normal_deg: int | None`, 0..359), `supabase/migrations/20261015090000_m1_schema.sql` (geen CHECK die `dir_deg` aan `dir_class` koppelt; `evaluations_offshore_is_no_go`)
- Bronnen uit ronde 1 (astral 3.2: PyPI, `sun.py`, `__init__.py`) blijven geldig; de daglichtsectie is ongewijzigd.
