# Blueprint WP-12: Marine-ingest (golven) en golven op de spotpagina
Status: DRAFT
Revisie: 1

## Doel
Elk uur per spot met coördinaten golfhoogte, golfperiode en golfrichting server-side ophalen bij de Open-Meteo Marine API, binnen hetzelfde call-budget als de wind (`api_usage`, bron `open_meteo_marine`). De waarden komen in de nieuwe tabel `marine_hours` (RLS: `anon` en `authenticated` lezen), rijen ouder dan 48 uur worden opgeruimd, en de spotpagina toont per uur een golfregel als er verse data is.

Golven zijn alleen informatie. Ze tellen **niet** mee in het oordeel (`evaluations`) of in de alerts (bevestigd, A-4). Deze WP raakt `shakka.domain.evaluation`, `shakka.jobs.evaluate`, `shakka.jobs.alerts` en de stale-regel van de pipeline dus niet.

Deze WP levert:
- de tabel `marine_hours` met grants, policy en pgTAP-test;
- het pure type `MarineHour` (`shakka.domain.marine`);
- `shakka.openmeteo.marine` (parameters, pure parser, fetch);
- de job `run_marine_ingest` en de CLI `shakka marine fetch`;
- de pipelinestap `marine` direct na `forecast`;
- `getMarineHours`, het type `MarineHour` en de golfregel op `/spot/[id]`.

## Aannames
Voorstellen voor Lars staan gemarkeerd met **[keuze Lars]**. De builder bouwt het voorstel.

- **A1. Twee golfmodellen, samengevoegd per uur: eerst DWD EWAM, daarna ECMWF WAM.** **[keuze Lars]** Live gecontroleerd op 15-10-2026 (zie Externe afhankelijkheden):
  - zonder `models` (`best_match`) levert de API voor 52,47 N / 4,57 O exact de waarden van `ewam` (DWD EWAM, Europa, ca. 5 km, elk uur), maar alleen de eerste ca. 79 uur; daarna is alles `null`. `best_match` vult niet aan met een ander model;
  - `ecmwf_wam` (ECMWF WAM, wereldwijd, 9 km, elk uur) dekt de volle 7 dagen aan de kust, maar heeft op het IJsselmeer (52,75 / 5,30) geen data;
  - `ewam` heeft op het IJsselmeer wel data (ca. 79 uur);
  - een punt in het binnenland (52,09 / 5,12) is in beide modellen helemaal `null`.

  Daarom vraagt de ingest `models=ewam,ecmwf_wam` en kiest de parser per uur het eerste model in die volgorde dat voor dat uur minstens één waarde heeft (A7). Resultaat: aan de kust ca. 3 dagen EWAM en daarna ECMWF WAM tot dag 7; op binnenwater dat EWAM kent ca. 3 dagen; elders niets. Het gewicht blijft gelijk aan één model (A4). Alternatieven (één constante plus fixture en tests): alleen `best_match`/`ewam` (ca. 3 dagen), of alleen `ecmwf_wam` (7 dagen, geen IJsselmeer).
- **A2. `cell_selection=sea`**, zoals bij de wind (bevestigde beslissing WP-03). Bij de Marine API is `sea` ook de standaard; de parameter gaat toch expliciet mee, zodat de request niet van een standaard afhangt.
- **A3. Tijdformaat** zoals WP-03 A3: `timezone=GMT`, `timeformat=unixtime`. De parser eist `hourly_units.time == "unixtime"`, `utc_offset_seconds == 0` en een `time`-reeks in stappen van precies 3600 s.
- **A4. Gewicht.** Variabelen × modellen = 3 × 2 = 6, dus `estimate_call_weight(n, 3, 2, 7) = n × max(1; 0,6) × max(1; 7/14) = n`. Met 25 spots: 25 per run, 600 per dag, ca. 18.600 per maand. Samen met de wind (720 per dag) ca. 1.320 per dag: 17% van de guard van 8.000. De guard is gedeeld: `BudgetGuard` telt alle bronnen met prefix `open_meteo_`.
- **A5. Boekhouding per request** zoals WP-03 A5: per chunk één budgetcontrole en één boeking onder `open_meteo_marine`, ook als de fetch faalt; daarna pas upsert bij succes.
- **A6. Geen tijdverschuiving.** Alle drie de golfvariabelen zijn "Instant" (Open-Meteo-documentatie). Een rij met `valid_at = T` bevat de momentane waarden op T, net als `wind_kn` en `dir_deg` bij de wind. Ze horen bij het uur [T, T+1h) volgens de projectafspraak.
- **A7. Samenvoegen per uur, nooit per variabele.** Per locatie en per index `i`: neem het eerste model uit `MARINE_MODELS` waarvan het drietal (hoogte, periode, richting) op `i` na het opschonen niet helemaal `None` is, en neem dat hele drietal over (ook als er daarbinnen een `None` staat). Waarden van verschillende modellen komen dus nooit in één rij. Zijn beide drietallen helemaal `None`, dan volgt er geen rij.
- **A8. Waarderegels.** `null`, NaN en ±inf worden `None`; een negatieve hoogte of periode wordt `None`; een richting wordt `int(round(x)) % 360`; een bool of niet-getal is een parsefout. Hoogte en periode 0 blijven 0. De richting is meteorologisch ("0° = From north"), net als bij de wind.
- **A9. Vervangsemantiek en versheid.** Net als WP-03 A8: alleen upsert plus opruimen na 48 uur. Een uur dat eerder wel en nu geen golfdata heeft, houdt zijn oude rij met een oudere `fetched_at`. Faalt de marinestap een tijd, dan blijven oude rijen staan. Daarom toont de web-app alleen rijen met `now - fetched_at <= 3 uur` (dezelfde grens als de versheidswaarschuwing van WP-14). Oudere golfdata verdwijnt van de pagina zonder melding; het oordeel hangt er niet van af.
- **A10. Weergave.** Per zichtbaar uur een regel `Golven 1,2 m, periode 5 s, uit WZW (250°)` onder het `HourVerdict`, binnen dezelfde `<li>`; `HourVerdict` blijft ongewijzigd (WP-14 "Gevolgen", WP-21). Hoogte met één decimaal en een komma, periode afgerond op hele seconden, richting met de windroos uit `labels.ts`. Als er minstens één golfregel is, staat boven de dagen één notitie dat golven een modelverwachting zijn, minder nauwkeurig aan de kust en op binnenwater, en niet meetellen in het oordeel (de Marine-documentatie waarschuwt expliciet voor kustnauwkeurigheid).
- **A11. Een mislukte golfquery breekt de pagina niet.** `loadSpotPage` vangt een fout van `getMarineHours` af, logt `console.warn('wave data load failed')` (zonder melding of id) en gaat verder met `marine: []`. Een fout in `getSpot`, `getEvaluations` of `getTideExtremes` geeft net als in WP-14 `kind: 'error'`. Voor een spot zonder `lat` of `lon` gaat er geen golfquery uit.
- **A12. Testcoördinaten zijn testdata, geen spotdata:** 52,47 / 4,57 (kust, dezelfde als WP-03 en WP-05), 52,75 / 5,30 (IJsselmeer, binnenwater) en 52,09 / 5,12 (binnenland). Ze komen niet in `data/spots.yaml`.
- **A13. Additieve uitbreidingen van het contract.** Bestaande en voorgeschreven signatures blijven geldig:
  - `MarineHour.to_row()` en `MarineHour.from_row()`; `MarineHour` weigert een rij met drie keer `None`;
  - `MarineFetchError` en `MarineParseError`, `build_marine_params`, een keyword `sleep=` op `fetch_marine`;
  - een keyword `fetch=` op `run_marine_ingest` en het veld `deleted: int = 0` op `MarineIngestResult`;
  - `delete_old_marine`, `run_marine_cli`;
  - `run_hourly(..., marine_fetch=None)` en het veld `PipelineContext.marine_fetch` (default `None`, achteraan, zodat de bestaande positionele aanroep in `test_pipeline.py` blijft werken);
  - web: `MARINE_HOUR_COLUMNS`, de module `#lib/marine.ts`, het veld `marine` in `SpotPageData` (`ok`).
- **A14. Geen `--dry-run` op `shakka marine fetch`.** De WP vraagt alleen `shakka marine fetch`; het plan van de forecast-dry-run toont het gedeelde verbruik al.
- **A15. Een mislukte marinestap mailt niet.** De stap wordt `failed` of `partial`, de run `partial`, exitcode 0 (regels van WP-11). De stale-regel kijkt alleen naar `forecast`. Details staan in `ingest_runs`.
- **A16. Geen nieuwe bronvermelding nodig.** `Attribution.svelte` noemt al Open-Meteo (CC BY 4.0), DWD en ECMWF, de bronnen van EWAM en ECMWF WAM. De Marine-documentatie eist "a clear attribution to DWD as well as a reference to Open-Meteo"; beide staan op elke pagina en op de spotpagina in de sectie Bronnen.
- **A17. Geen nieuwe dependencies**, in `ingest/` noch in `web/`.
- **A18. Migratiebestand** `supabase/migrations/20261015180000_marine_hours.sql`, na de laatste bestaande (`20261015150000_push_subscriptions.sql`).

## Ontwerp

**Lagen.** Zelfde opbouw als WP-03:
1. `shakka.domain.marine` (puur): `MarineHour`, bevroren pydantic-model met `extra="forbid"`. Validatie: `valid_at` tz-aware, naar UTC, op een heel uur; hoogte en periode eindig en `>= 0`; richting 0–359; niet alle drie `None`.
2. `shakka.openmeteo.marine` (I/O; de enige plek met `marine-api.open-meteo.com`): constanten, een pure parameterbouwer, een pure parser en `fetch_marine` via de bestaande `request_json` (retries, foutmeldingen zonder URL).
3. `shakka.jobs.marine`: spots laden (`load_spot_locations` uit `shakka.jobs.forecast`), chunks van 50, budget, fetch, boeken, upsert, opruimen, plus de CLI-glue.
4. `shakka.pipeline`: stap `step_marine` tussen `forecast` en `tides`.

**Parser.** Streng op structuur, mild op waarden (zelfde regels als WP-03, zonder vlaagverschuiving). Een structuurfout geeft `MarineParseError` en laat de hele chunk falen. De structuurcontrole is bewust gedupliceerd uit `shakka.openmeteo.forecast` in plaats van gedeeld: zo blijft de goedgekeurde code van WP-03 onaangeroerd. Samenvoegen gebeurt volgens A7.

**Job.** `run_marine_ingest(db, http, budget, *, now, fetch=fetch_marine)`, letterlijk naar het patroon van `run_forecast_ingest`:
1. `locations, _ = load_spot_locations(db)` (spots zonder coördinaten vallen af).
2. Chunks van `CHUNK_SIZE = 50` in volgorde van `id`.
3. Per chunk `n` van `total`:
   1. `weight = _chunk_weight(len(chunk))`;
   2. `budget.can_spend(weight, now=now)` False → `skipped_budget=True`, warning loggen, `break`;
   3. `try: hours = fetch(http, chunk)` (zonder `forecast_days`);
   4. `except MarineFetchError as exc:` `errors.append(f"chunk {n}/{total}: {exc}")`, `hours = None`;
   5. altijd `budget.record(SOURCE_OPEN_METEO_MARINE, weight, now=now, requests=1)` en `calls += weight`;
   6. alleen bij `hours is not None`: dedupliceren op `(spot_id, valid_at)` (laatste wint), upsert met `on_conflict="spot_id,valid_at"` en `fetched_at = now`; een lege lijst geeft geen upsert.
4. Altijd `delete_old_marine(db, now=now)`.

`DatabaseError` wordt niet afgevangen (fail-safe: zonder leesbaar budget gaat er geen request uit; de pipeline maakt er een `failed`-stap van).

**Pipeline.** `step_marine` roept de job aan met `ctx.marine_fetch or om_marine.fetch_marine` (opzoeken via de module op het moment van aanroepen, zodat een monkeypatch op `shakka.openmeteo.marine.fetch_marine` werkt). Status `partial` bij fouten per chunk of een budgetstop, met bij een budgetstop een warning (annotatie). Geen extra gebruikswaarschuwing: die zit al bij `forecast` (WP-11).

**Web.** `getMarineHours` leest alleen `marine_hours` (één spot, halfopen `[from, to)`, op `valid_at`, gepagineerd via `fetchAllPages`). `loadSpotPage` doet de query als derde element in de `Promise.all`, met dezelfde `from`/`to` als de evaluaties en met de foutafvang uit A11. De pure module `#lib/marine.ts` filtert op versheid (A9), maakt een `Map` van uur naar rij en formatteert de tekst; de pagina koppelt per `<li>` op `Date.parse(valid_at)`, dus onafhankelijk van de notatie van de tijdstempel.

**Waarom zo.** Hergebruik van `request_json`, `BudgetGuard`, `load_spot_locations` en het jobpatroon houdt de nieuwe code klein en voorspelbaar. Twee modellen kosten niets extra en geven aan de kust 7 dagen en op het IJsselmeer 3 dagen golfdata (A1). Golven blijven volledig buiten de evaluatie, dus een storing in de marine-ingest kan geen alert beïnvloeden. De wijzigingen in `web/` zijn additief (nieuwe module, nieuwe velden, één extra regel per uur) vanwege de parallelle WP-15 en WP-16.

## Bestanden

### Database
| Pad | Actie | Inhoud |
|---|---|---|
| `supabase/migrations/20261015180000_marine_hours.sql` | aanmaken | Tabel, index, RLS, revoke, grants, policy (zie Interfaces). |
| `supabase/tests/06_marine_hours.test.sql` | aanmaken | pgTAP, `plan(20)` (zie Testplan). |
| `supabase/tests/01_schema.test.sql` | wijzigen | `tables_are` krijgt `marine_hours`; de `set_eq` met kolomtypen krijgt 6 rijen voor `marine_hours`; de `set_eq` met foreign keys krijgt `('marine_hours', 'spots', 'c')`. `plan(71)` blijft gelijk (geen nieuwe asserts). |

### Ingest
| Pad | Actie | Inhoud |
|---|---|---|
| `ingest/src/shakka/domain/marine.py` | aanmaken | `MarineHour` met `to_row`/`from_row`. Puur. |
| `ingest/src/shakka/openmeteo/marine.py` | aanmaken | Constanten, `MarineFetchError`, `MarineParseError`, `build_marine_params`, `parse_marine_response`, `fetch_marine`. |
| `ingest/src/shakka/jobs/marine.py` | aanmaken | `FetchMarine`, `MarineIngestResult`, `_chunk_weight`, `run_marine_ingest`, `delete_old_marine`, `run_marine_cli`. |
| `ingest/src/shakka/db.py` | wijzigen | `TABLE_KEYS` krijgt `"marine_hours": ("spot_id", "valid_at")` (na `forecast_hours`). Verder niets. |
| `ingest/src/shakka/pipeline.py` | wijzigen | Import `shakka.openmeteo.marine as om_marine` en `run_marine_ingest, FetchMarine`; constante `MARINE_BUDGET_WARNING`; `STEP_NAMES` en `STEPS` met `marine`; `step_marine`; veld `marine_fetch` in `PipelineContext`; keyword `marine_fetch` in `run_hourly` en `_run`. |
| `ingest/src/shakka/cli.py` | wijzigen | Groep `marine` met commando `fetch`, direct na de groep `forecast`; docstring van `run-hourly` noemt `marine`. Verder niets. |
| `ingest/tests/fixtures/openmeteo/marine_3loc_2models.json` | aanmaken | Echte respons, onbewerkt (capture-URL in Testplan). |
| `ingest/tests/fixtures/openmeteo/README.md` | wijzigen | Twee regels toevoegen (zie Testplan). |
| `ingest/tests/openmeteo_payloads.py` | wijzigen | Helper `make_marine_payload` toevoegen; bestaande helper ongewijzigd. |
| `ingest/tests/test_domain_marine.py` | aanmaken | Domeintype. |
| `ingest/tests/test_openmeteo_marine.py` | aanmaken | Parameters, parser (fixture en synthetisch), fetch. AC-1. |
| `ingest/tests/test_job_marine.py` | aanmaken | Job, budget (AC-2), opruimen. |
| `ingest/tests/test_cli_marine.py` | aanmaken | CLI. |
| `ingest/tests/pipeline_fixtures.py` | wijzigen | `fake_marine_fetch`, `failing_marine_fetch` toevoegen. |
| `ingest/tests/test_pipeline.py` | wijzigen | `run_real` zet `marine_fetch`; contractvolgorde; `["ok"] * 5` in `test_spots_sync_failure_continues`; nieuwe marinetests (AC-3). |
| `ingest/tests/test_cli_pipeline.py` | wijzigen | `patch_runtime` patcht ook `om_marine.fetch_marine`. |
| `ingest/tests/test_migrations.py` | wijzigen | Patroon in `test_no_later_milestone_tables` wordt `(sessions|rsvps)`. |
| `ingest/tests/fakes.py` | wijzigen | In `delete` bij `spots`: `"marine_hours"` in de lijst van child-tabellen (cascade). |
| `ingest/tests/test_fakes.py` | wijzigen | `test_cascades`: per spot ook een `marine_hours`-rij seeden en `"marine_hours"` in de controlelus opnemen. |

### Web
| Pad | Actie | Inhoud |
|---|---|---|
| `web/src/lib/types.ts` | wijzigen | Onderaan: `MarineHour` en `MARINE_HOUR_COLUMNS`. |
| `web/src/lib/data.ts` | wijzigen | Import `MARINE_HOUR_COLUMNS`, `type MarineHour`; functie `getMarineHours` onderaan. |
| `web/src/lib/marine.ts` | aanmaken | `MARINE_STALE_AFTER_MS`, `WAVES_NOTE_NL`, `formatMeters`, `waveText`, `marineByHour`. |
| `web/src/lib/page-data.ts` | wijzigen | `marine` in `SpotPageData` (`ok`), derde query in `loadSpotPage`, interne `loadMarine`. |
| `web/src/routes/spot/[id]/+page.svelte` | wijzigen | Imports, `waves`, notitie na `<Freshness>`, golfregel in de `<li>` (zie Interfaces). |
| `web/src/app.css` | wijzigen | Onderaan twee regels onder het commentaar `/* WP-12: waves */`. |
| `web/test/fixtures/spot-data.ts` | wijzigen | `MARINE_FRESH`, `MARINE_STALE`; `pageData` krijgt default `marine: []`. |
| `web/test/marine.test.ts` | aanmaken | Pure functies uit `marine.ts`. |
| `web/test/marine-schema.test.ts` | aanmaken | `MARINE_HOUR_COLUMNS` gelijk aan de kolommen in de migratie. |
| `web/test/data.test.ts` | wijzigen | Test voor `getMarineHours` toevoegen. |
| `web/test/data-tables.test.ts` | wijzigen | `marine_hours` toegestaan en verplicht (AC-7). |
| `web/test/page-data.test.ts` | wijzigen | Mock `getMarineHours`; nieuwe tests. |
| `web/test/spot-page.test.ts` | wijzigen | Nieuw `describe('waves (WP-12, AC-6)')` onderaan. |

### Docs
| Pad | Actie | Inhoud |
|---|---|---|
| `docs/RUNBOOK.md` | wijzigen | Nieuwe sectie "Golven (Open-Meteo Marine, vanaf WP-12)" met het eerstvolgende vrije sectienummer; §11.7 noemt `marine_hours`; §13.1 noemt de stap `marine`. |

`docs/STATUS.md` werkt de orchestrator bij. Geen wijzigingen in `.github/`, `data/`, `scripts/` (de guard kent `marine-api.open-meteo.com` al), `Attribution.svelte`, `HourVerdict.svelte` of `package.json`/`pyproject.toml`.

## Interfaces en contracten

### Migratie `20261015180000_marine_hours.sql` (exact)
```sql
-- Wave forecasts per spot and hour (WP-12). Display only: never used in evaluations or alerts.
-- Written by the ingest (secret key -> service_role), read by the app (anon, authenticated).

create table public.marine_hours (
  spot_id text not null references public.spots (id) on delete cascade,
  valid_at timestamptz not null,
  wave_height_m real null constraint marine_hours_wave_height_nonneg check (wave_height_m >= 0),
  wave_period_s real null constraint marine_hours_wave_period_nonneg check (wave_period_s >= 0),
  wave_dir_deg smallint null
    constraint marine_hours_wave_dir_range check (wave_dir_deg between 0 and 359),
  fetched_at timestamptz not null,
  primary key (spot_id, valid_at),
  constraint marine_hours_has_value
    check (wave_height_m is not null or wave_period_s is not null or wave_dir_deg is not null)
);
create index marine_hours_valid_at_idx on public.marine_hours (valid_at);

alter table public.marine_hours enable row level security;

revoke all on table public.marine_hours from public, anon, authenticated, service_role;

-- Public read data.
grant select on table public.marine_hours to anon, authenticated;

-- Ingest.
grant select, insert, update, delete on table public.marine_hours to service_role;

create policy marine_hours_read on public.marine_hours for select to anon, authenticated using (true);
```

### `shakka.domain.marine`
```python
"""Wave forecast value type (WP-12). Display only: never used in evaluations or alerts. Pure."""

class MarineHour(BaseModel):
    """Wave forecast for the hour [valid_at, valid_at + 1h), UTC.

    All values are instantaneous at valid_at (Open-Meteo Marine "Instant"). wave_dir_deg is the
    direction the waves come from (0 = north), like wind direction. At least one value is set.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")
    spot_id: str = Field(min_length=1)
    valid_at: datetime                 # validator as ForecastHour: aware, astimezone(UTC), whole hour
    wave_height_m: float | None = Field(ge=0, allow_inf_nan=False)   # metres
    wave_period_s: float | None = Field(ge=0, allow_inf_nan=False)   # seconds
    wave_dir_deg: int | None = Field(ge=0, le=359)

    # model_validator(mode="after"): all three None -> ValueError("at least one wave value is required")

    def to_row(self, *, fetched_at: datetime) -> dict[str, Any]:
        """Row for public.marine_hours. Keys exactly: spot_id, valid_at, wave_height_m,
        wave_period_s, wave_dir_deg, fetched_at. fetched_at must be aware (ValueError otherwise)."""

    @classmethod
    def from_row(cls, row: Mapping[str, Any]) -> Self:
        """Inverse of to_row; valid_at may be a str (datetime.fromisoformat) or a datetime.
        fetched_at and unknown keys are ignored."""
```
Alle velden verplicht (geen defaults). Imports alleen standaardbibliotheek en pydantic.

### `shakka.openmeteo.marine`
```python
MARINE_URL: Final = "https://marine-api.open-meteo.com/v1/marine"
MARINE_VARIABLES: Final = ("wave_height", "wave_period", "wave_direction")
MARINE_MODELS: Final = ("ewam", "ecmwf_wam")   # priority order per hour (A1, A7), choice for Lars
DEFAULT_MARINE_DAYS: Final = 7
MAX_MARINE_DAYS: Final = 8
MAX_LOCATIONS_PER_REQUEST: Final = 50
CELL_SELECTION: Final = "sea"
HEIGHT_UNIT: Final = "m"
PERIOD_UNIT: Final = "s"
DIRECTION_UNIT: Final = "°"

class MarineFetchError(Exception): ...
class MarineParseError(MarineFetchError): ...

def build_marine_params(
    locations: Sequence[SpotLocation], *, forecast_days: int = DEFAULT_MARINE_DAYS
) -> dict[str, str]:
    """ValueError if locations is empty or longer than MAX_LOCATIONS_PER_REQUEST,
    or forecast_days is not in 1..MAX_MARINE_DAYS."""

def parse_marine_response(payload: Any, locations: Sequence[SpotLocation]) -> list[MarineHour]:
    """Pure. Order: per location (input order), per time. Per hour the first model in
    MARINE_MODELS whose (height, period, direction) is not all None supplies the whole row;
    values of different models are never mixed. Hours without any value give no row.
    Raises MarineParseError on any structural problem."""

def fetch_marine(
    http: httpx.Client,
    locations: Sequence[SpotLocation],
    *,
    forecast_days: int = DEFAULT_MARINE_DAYS,
    sleep: Callable[[float], None] = time.sleep,
) -> list[MarineHour]:
    """[] without a request for empty locations. OpenMeteoRequestError -> MarineFetchError
    (same message, prefixed "open-meteo marine: "). MarineParseError propagates."""
```
`build_marine_params` geeft exact deze dict, in deze volgorde (`hourly` en `models` opgebouwd uit de tuples):
```python
{
    "latitude": ",".join(f"{loc.lat:.4f}" for loc in locations),
    "longitude": ",".join(f"{loc.lon:.4f}" for loc in locations),
    "hourly": "wave_height,wave_period,wave_direction",
    "models": "ewam,ecmwf_wam",
    "timezone": "GMT",
    "timeformat": "unixtime",
    "forecast_days": str(forecast_days),
    "cell_selection": CELL_SELECTION,
}
```

**Responsvorm** (live gecontroleerd op 15-10-2026; de fixture legt die vast). Meer dan één locatie: lijst van objecten; één locatie: object. `location_id` ontbreekt bij element 0 en is `1, 2, …` daarna. Per object:
```json
{"latitude": 52.45, "longitude": 4.5, "generationtime_ms": 0.18, "utc_offset_seconds": 0,
 "timezone": "GMT", "timezone_abbreviation": "GMT", "elevation": 7.0,
 "hourly_units": {"time": "unixtime", "wave_height_ewam": "m", "wave_period_ewam": "s",
                  "wave_direction_ewam": "°", "wave_height_ecmwf_wam": "m",
                  "wave_period_ecmwf_wam": "s", "wave_direction_ecmwf_wam": "°"},
 "hourly": {"time": [1792022400, 1792026000, "..."],
            "wave_height_ewam": [0.8, 0.84, "...", null], "...": []}}
```

**Parserregels** (elke overtreding geeft `MarineParseError` met de locatie-index en, waar van toepassing, de sleutel):
1. Een object met `"error": true` → `f"open-meteo returned an error: {reason[:200]}"`.
2. Een object wordt `[object]`; wat dan geen lijst is, is een fout; lengte moet `len(locations)` zijn.
3. Per element `i`: een dict; geen `"error": true`; `location_id` ontbreekt of is `i`; `utc_offset_seconds == 0`; `hourly_units` en `hourly` zijn dicts; `hourly_units["time"] == "unixtime"`; `hourly["time"]` is een lijst van ints (geen bool); `time[k] - time[k-1] == 3600` voor elke `k >= 1`, anders `"... time is not hourly at index <k>"`. Een lege `time` is geldig.
4. Per model in `MARINE_MODELS` en variabele in `MARINE_VARIABLES`: sleutel `f"{var}_{model}"` in `hourly_units` en `hourly` (anders `"... missing key <key>"`); eenheid `m`, `s` of `°` (anders `"... unit for <key> is 'ft', expected 'm'"`); lijst met lengte `len(time)`.
5. Waarden (voor elke ruwe waarde): `None` blijft `None`; bool of niet-getal → fout `"... non-numeric value in <key>"`; niet-eindig → `None`; hoogte of periode `< 0` → `None`; richting → `int(round(x)) % 360`.
6. Per index `i`: voor elk model in volgorde: `(h, p, d)` = opgeschoonde waarden op `i`; is er minstens één niet `None`, dan `MarineHour(spot_id=location.spot_id, valid_at=datetime.fromtimestamp(time[i], tz=UTC), wave_height_m=h, wave_period_s=p, wave_dir_deg=d)` en stop met de modellen. Anders geen rij.
7. `ValidationError`, `OverflowError`, `OSError` of `ValueError` bij het maken van een `MarineHour` → `MarineParseError(f"{where}: invalid hour at index {i}")`.

`MARINE_MODELS` moet minstens 2 modellen bevatten: met één model geeft Open-Meteo sleutels zonder achtervoegsel (test `test_models_tuple`).

### `shakka.jobs.marine`
```python
RETENTION: Final = timedelta(hours=48)
CHUNK_SIZE: Final = MAX_LOCATIONS_PER_REQUEST
MARINE_TABLE: Final = "marine_hours"
MARINE_ON_CONFLICT: Final = "spot_id,valid_at"

class FetchMarine(Protocol):
    def __call__(self, http: httpx.Client, locations: Sequence[SpotLocation], *,
                 forecast_days: int = ...) -> list[MarineHour]: ...

@dataclass(frozen=True)
class MarineIngestResult:
    spots: int            # spots with coordinates considered
    rows: int             # rows upserted (after de-duplication)
    calls: float          # Open-Meteo weight recorded this run, rounded to 2 decimals
    skipped_budget: bool  # True if a chunk was not fetched because of the budget
    errors: list[str]     # "chunk <n>/<total>: <message>"
    deleted: int = 0      # rows removed by delete_old_marine

def _chunk_weight(n_locations: int) -> float:
    """estimate_call_weight(n_locations, len(MARINE_VARIABLES), len(MARINE_MODELS), DEFAULT_MARINE_DAYS)."""

def run_marine_ingest(db: SupabaseRest, http: httpx.Client, budget: BudgetGuard, *,
                      now: datetime, fetch: FetchMarine = fetch_marine) -> MarineIngestResult: ...

def delete_old_marine(db: SupabaseRest, *, now: datetime) -> int:
    """db.delete("marine_hours", filters={"valid_at": f"lt.{iso_utc(now - RETENTION)}"})."""

def run_marine_cli(*, echo: Callable[[str], None]) -> int: ...
```
- `now` naïef → `ValueError` in `run_marine_ingest` en `delete_old_marine` (via `shakka.jobs.inputs.require_aware`).
- Logger `logging.getLogger("shakka.jobs.marine")`: info per chunk (`"chunk %d/%d: %d locations, weight %.2f"`), warning bij een budgetstop (`"chunk %d/%d skipped: Open-Meteo budget exhausted"`).
- Rijvorm van de upsert: `MarineHour.to_row(fetched_at=now)`.
- `run_marine_cli`: `get_settings()` (pydantic-`ValidationError` → `marine: configuration incomplete; run shakka doctor`, exit 1); `db = runtime.open_db(settings)`, `http = runtime.open_http()`; in `try`: `run_marine_ingest(db, http, BudgetGuard(db), now=runtime.utcnow())`; `except DatabaseError as exc` → `marine: database error: {exc}`, exit 1; `finally`: `http.close()` en `db.close()`. Import `from shakka.jobs import runtime` en aanroepen via de module.

**CLI-uitvoer** (exact):
```
marine: spots=<n> rows=<n> calls=<x.xx> deleted=<n> skipped_budget=<yes|no> errors=<n>
error   <errorregel>                    (één per fout)
marine: ok | marine: failed
```
Exit 0 als `errors` leeg is en `skipped_budget` False; anders `marine: failed` en exit 1. Nooit waarden van environment-variabelen in de uitvoer.

### `shakka.cli` (toevoeging, direct na de groep `forecast`)
```python
@cli.group()
def marine() -> None:
    """Wave forecast ingest (Open-Meteo Marine, server-side). Display only."""


@marine.command("fetch")
def marine_fetch() -> None:
    """Fetch wave forecasts for all spots with coordinates."""
    from shakka.jobs.marine import run_marine_cli

    raise SystemExit(run_marine_cli(echo=click.echo))
```
De docstring van `run-hourly` wordt `"""Run all hourly steps (spots sync, forecast, marine, tides, evaluate, alerts) and record the run."""`.

### `shakka.pipeline` (wijzigingen)
```python
import shakka.openmeteo.marine as om_marine
from shakka.jobs.marine import FetchMarine, run_marine_ingest

MARINE_BUDGET_WARNING: Final = "Open-Meteo budget guard reached: marine request skipped"
STEP_NAMES: Final = ("spots_sync", "forecast", "marine", "tides", "evaluate", "alerts")

@dataclass(slots=True)
class PipelineContext:
    ...                                   # existing fields unchanged, in the same order
    notifiers: Mapping[str, Notifier] | None = None
    marine_fetch: FetchMarine | None = None   # None: om_marine.fetch_marine at call time

def step_marine(ctx: PipelineContext) -> StepOutcome:
    fetch = ctx.marine_fetch or om_marine.fetch_marine
    result = run_marine_ingest(ctx.db, ctx.http, ctx.budget, now=ctx.now, fetch=fetch)
    warnings = (MARINE_BUDGET_WARNING,) if result.skipped_budget else ()
    partial = bool(result.errors) or result.skipped_budget
    return StepOutcome("partial" if partial else "ok", dataclasses.asdict(result), warnings)

STEPS: Final[tuple[Step, ...]] = (
    ("spots_sync", step_spots_sync),
    ("forecast", step_forecast),
    ("marine", step_marine),
    ("tides", step_tides),
    ("evaluate", step_evaluate),
    ("alerts", step_alerts),
)

def run_hourly(settings, *, now, db=None, http=None, steps=STEPS, forecast_fetch=None,
               tide_fetch=None, clock=None, notifiers=None,
               marine_fetch: FetchMarine | None = None) -> RunReport: ...
```
`_run` krijgt de parameter `marine_fetch` (na `notifiers`) en geeft `marine_fetch=marine_fetch or om_marine.fetch_marine` als keyword aan `PipelineContext`. `step_alerts`, `run_status`, `exit_code_for` en de stale-regel blijven ongewijzigd.

### Web: `web/src/lib/types.ts` (onderaan toevoegen)
```ts
/** Row of public.marine_hours (all columns). Display only (WP-12). */
export interface MarineHour {
	spot_id: string;
	valid_at: string;
	wave_height_m: number | null;
	wave_period_s: number | null;
	wave_dir_deg: number | null;
	fetched_at: string;
}

export const MARINE_HOUR_COLUMNS = [
	'spot_id',
	'valid_at',
	'wave_height_m',
	'wave_period_s',
	'wave_dir_deg',
	'fetched_at'
] as const;
```

### Web: `web/src/lib/data.ts` (onderaan toevoegen)
```ts
export function getMarineHours(spotId: string, from: Date, to: Date): Promise<MarineHour[]> {
	return fetchAllPages<MarineHour>('getMarineHours', () =>
		supabase
			.from('marine_hours')
			.select(MARINE_HOUR_COLUMNS.join(','))
			.eq('spot_id', spotId)
			.gte('valid_at', from.toISOString())
			.lt('valid_at', to.toISOString())
			.order('valid_at', { ascending: true })
	);
}
```
Daarna bevat `data.ts` precies vijf `.from(`-aanroepen, alle met een letterlijke tabelnaam uit `spots`, `evaluations`, `tide_extremes`, `marine_hours`.

### Web: `web/src/lib/marine.ts` (nieuw)
```ts
import { compassLabel, formatKn } from './labels.js';
import type { MarineHour } from './types.js';
import { STALE_AFTER_MS } from './view.js';

/** Wave rows older than this (fetched_at) are not shown (A9). */
export const MARINE_STALE_AFTER_MS = STALE_AFTER_MS;

export const WAVES_NOTE_NL =
	'Golven zijn een modelverwachting (Open-Meteo Marine, DWD en ECMWF), minder nauwkeurig vlak bij de kust en op binnenwater. Ze tellen niet mee in het oordeel.';

/** One decimal with a comma: Math.floor(x * 10 + 0.5) / 10, e.g. 1.24 -> '1,2', 1.25 -> '1,3', 0 -> '0,0'. */
export function formatMeters(x: number): string;

/** 'Golven 1,2 m, periode 5 s, uit WZW (250°)'. Unknown parts: 'hoogte onbekend',
 *  'periode onbekend', 'richting onbekend'. Period via formatKn (whole seconds). */
export function waveText(m: Pick<MarineHour, 'wave_height_m' | 'wave_period_s' | 'wave_dir_deg'>): string;

/** Map from Date.parse(valid_at) to the row. Skips rows with an unparseable valid_at or fetched_at,
 *  rows with now - fetched_at > MARINE_STALE_AFTER_MS (strict; exactly 3 h is still shown),
 *  and rows with all three values null. Later rows with the same hour overwrite earlier ones. */
export function marineByHour(rows: readonly MarineHour[], now: Date): Map<number, MarineHour>;
```
`waveText` exact: `` `Golven ${h}, ${p}, ${d}` `` met `h = wave_height_m === null ? 'hoogte onbekend' : `${formatMeters(wave_height_m)} m``, `p = wave_period_s === null ? 'periode onbekend' : `periode ${formatKn(wave_period_s)} s``, `d = wave_dir_deg === null ? 'richting onbekend' : `uit ${compassLabel(wave_dir_deg)} (${Math.round(wave_dir_deg)}°)``. Geen `Date`-getters in lokale tijd (test `no-local-date-getters`).

### Web: `web/src/lib/page-data.ts` (wijzigingen)
```ts
import { getEvaluations, getMarineHours, getSpot, getSpotSummaries, getTideExtremes, listSpots } from '#lib/data.js';
import type { Evaluation, MarineHour, Spot, SpotSummary, TideExtreme } from './types.js';

export type SpotPageData =
	| { kind: 'ok'; now: string; spot: Spot; evaluations: Evaluation[]; tides: TideExtreme[]; marine: MarineHour[] }
	| { kind: 'not_found'; now: string; id: string }
	| { kind: 'error'; now: string; id: string };

/** Waves are optional: a failing query gives [] and one console.warn without details (A11). */
async function loadMarine(spotId: string, from: Date, to: Date): Promise<MarineHour[]> {
	try {
		return await getMarineHours(spotId, from, to);
	} catch {
		console.warn('wave data load failed');
		return [];
	}
}
```
In `loadSpotPage`, na `station`:
```ts
const hasCoords = spot.lat !== null && spot.lon !== null;
const [evaluations, tides, marine] = await Promise.all([
	getEvaluations(spot.id, floorHour(now), end),
	station ? getTideExtremes(station, startOfLocalDay(todayKey), end) : Promise.resolve([]),
	hasCoords ? loadMarine(spot.id, floorHour(now), end) : Promise.resolve([])
]);
return { kind: 'ok', now: now.toISOString(), spot, evaluations, tides, marine };
```

### Web: `web/src/routes/spot/[id]/+page.svelte` (wijzigingen)
- Script: `import { WAVES_NOTE_NL, marineByHour, waveText } from '#lib/marine.js';` en `import type { MarineHour } from '#lib/types.js';`, plus na `station`:
  ```ts
  const waves = $derived(
  	data.kind === 'ok' ? marineByHour(data.marine, now) : new Map<number, MarineHour>()
  );
  ```
- Direct na `<Freshness {latest} {now} showUpdated />`:
  ```svelte
  {#if groups.length > 0 && waves.size > 0}<p class="muted waves-note">{WAVES_NOTE_NL}</p>{/if}
  ```
- De `<ol class="hours">` wordt:
  ```svelte
  <ol class="hours">
  	{#each hours as e (e.valid_at)}
  		{@const wave = waves.get(Date.parse(e.valid_at))}
  		<li>
  			<HourVerdict evaluation={e} />
  			{#if wave}<p class="waves">{waveText(wave)}</p>{/if}
  		</li>
  	{/each}
  </ol>
  ```
Verder niets aan de pagina.

### Web: `web/src/app.css` (onderaan)
```css
/* WP-12: waves */
.waves { margin: 0.25rem 0 0.5rem; font-size: 0.875rem; }
.waves-note { font-size: 0.875rem; }
```

### Gevolgen voor latere WP's
- **WP-15 en WP-16** (parallel): raken mogelijk dezelfde bestanden (`spot/[id]/+page.svelte`, `page-data.ts`, `test/fixtures/spot-data.ts`, `app.css`, `docs/RUNBOOK.md`). De wijzigingen van deze WP zijn additief; bij een mergeconflict blijven beide kanten staan. `SpotPageData` (`ok`) heeft na deze WP het veld `marine`; fixtures van andere WP's die `pageData()` gebruiken krijgen het via de default.
- **WP-21:** `HourVerdict` is ongewijzigd; de publieke sessiepagina kan golven later tonen met `getMarineHours`, `marineByHour` en `waveText`.
- **WP-22:**
  - het uniforme tijdsbudget per netwerkstap (WP-11 N-5) geldt ook voor `marine` (max. 3 pogingen met 30 s timeout per chunk);
  - de maandelijkse Open-Meteo-schatting wordt ca. 41.000 (wind ca. 22.300, golven ca. 18.600) bij 25 spots;
  - een marinestap die elke run `partial` of `failed` is, mailt niet (A15); een drempel daarvoor hoort bij de bestaande WP-22-punten over blijvende `partial`;
  - per-spot keuze van golfmodel of `cell_selection` valt buiten scope.
- **WP-23:** geen nieuwe origins; `connect-src` hoeft alleen Supabase te bevatten.
- **Lars:** na de merge `supabase db push` (nieuwe migratie). Een parallelle WP met een migratie die een eerdere tijdstempel heeft maar later gemerged wordt, vergt `supabase db push --include-all`; zie Risico's.

## Edge cases
| # | Geval | Gedrag | Test |
|---|---|---|---|
| E1 | Spot zonder `lat`/`lon` | Niet in de request; telt niet in `spots`. Web: geen golfquery | `test_job_skips_spots_without_coordinates`, `page-data.test.ts` "no coordinates" |
| E2 | Geen enkele spot met coördinaten | 0 requests, geen boeking, opruimen draait | `test_job_no_spots_no_requests` |
| E3 | Locatie met alleen `null` (binnenland) | Geen rijen voor die spot (AC-1) | `test_fixture_inland_has_no_rows` |
| E4 | Binnenwater met alleen EWAM (IJsselmeer) | Rijen alleen voor uren met EWAM-data, uit EWAM | `test_fixture_lake_uses_ewam_only` |
| E5 | Kust: EWAM stopt na ca. 79 uur | Daarna rijen uit ECMWF WAM | `test_fixture_coast_switches_to_ecmwf` |
| E6 | EWAM-drietal deels `null` (alleen hoogte) | Rij met alleen de hoogte uit EWAM; niet aangevuld uit ECMWF (A7) | `test_parse_partial_triple_not_mixed` |
| E7 | EWAM-drietal helemaal `null`, ECMWF gevuld | Rij uit ECMWF | `test_parse_falls_back_to_second_model` |
| E8 | Beide drietallen `null` | Geen rij | `test_parse_all_none_no_row` |
| E9 | Negatieve hoogte of periode, NaN, inf | `None` | `test_parse_negative_and_non_finite_are_none` |
| E10 | Hoogte 0 of periode 0 | Blijft 0.0 | `test_parse_zero_kept` |
| E11 | Richting 360, 359,6, -1 | 0, 0, 359 | `test_parse_direction_normalized` |
| E12 | Waarde is een string of bool | `MarineParseError` | `test_parse_non_numeric_value` |
| E13 | Eenheid `ft` voor hoogte, of `deg` voor richting | `MarineParseError` met de sleutel | `test_parse_rejects_wrong_units` |
| E14 | Ontbrekende sleutel voor een model | `MarineParseError` met de sleutel | `test_parse_missing_model_key` |
| E15 | Arraylengte ≠ lengte van `time` | `MarineParseError` | `test_parse_length_mismatch` |
| E16 | `time` niet in stappen van 3600 s (gat, dubbel, aflopend) | `MarineParseError` met de index | `test_parse_rejects_non_hourly_time` |
| E17 | `hourly_units.time` niet `unixtime` of `utc_offset_seconds != 0` | `MarineParseError` | `test_parse_requires_unixtime_utc` |
| E18 | Object met `"error": true` | `MarineParseError` met reason | `test_parse_error_object` |
| E19 | Eén locatie: respons is een object | Genormaliseerd | `test_parse_single_location_object` |
| E20 | Aantal elementen of `location_id` klopt niet | `MarineParseError` | `test_parse_location_count_mismatch`, `test_parse_location_id_mismatch` |
| E21 | Dubbele PK in een chunk | Gededupliceerd, laatste wint | `test_job_deduplicates_before_upsert` |
| E22 | Forecast heeft het dagbudget bijna op (dag + 1,0 > 8.000) | Geen marine-request, `skipped_budget`, geen boeking (AC-2) | `test_job_budget_exceeded_no_request`, `test_marine_budget_skipped_after_forecast` |
| E23 | Precies op de grens (dag + 1,0 == 8.000) | Request gaat uit | `test_job_budget_boundary_inclusive` |
| E24 | Fetch faalt (400, of 3× 500) | Fout in `errors`, gewicht toch geboekt, geen upsert | `test_job_fetch_error_books_weight` |
| E25 | `valid_at == now - 48h` | Blijft staan (alleen `<`) | `test_delete_old_marine_boundary` |
| E26 | Meer dan 50 spots | Requests van max. 50 | `test_job_chunks_by_50` |
| E27 | `DatabaseError` bij budget of upsert | Doorgegeven; pipelinestap `failed` | `test_job_database_error_propagates`, `test_marine_exception_is_partial_run` |
| E28 | Marinestap faalt in de pipeline | Run `partial`, exit 0, `tides`/`evaluate`/`alerts` draaien (AC-3) | `test_marine_exception_is_partial_run` |
| E29 | `now` naïef | `ValueError` | `test_job_rejects_naive_now` |
| E30 | Web: spot zonder golfdata | Geen `.waves`, geen notitie, geen fout (AC-6) | `spot-page.test.ts` |
| E31 | Web: golfrij met `fetched_at` ouder dan 3 uur | Niet getoond (A9) | `marine.test.ts`, `spot-page.test.ts` |
| E32 | Web: golfquery faalt | Pagina `ok` met `marine: []`, één `console.warn` zonder details | `page-data.test.ts` |
| E33 | Web: tijdstempelnotatie verschilt (`Z` vs `+00:00`) | Koppeling op `Date.parse` | `marine.test.ts` |
| E34 | Web: golfrij voor een donker uur | Alleen zichtbaar als het uur zelf zichtbaar is | (gevolg van de opbouw; geen aparte test) |

## Testplan
Alle ingest-tests draaien zonder netwerk (`httpx.MockTransport`, `FakeSupabase`). Tests voor domein, parser en job komen vóór de implementatie. Gebruik in tests nooit een 5xx-antwoord met de echte `time.sleep`: injecteer `sleep` via `functools.partial(fetch_marine, sleep=fake_sleep)` of gebruik 400 (geen retry).

**Fixture.** `ingest/tests/fixtures/openmeteo/marine_3loc_2models.json`, onbewerkt vastgelegd vanuit de repo-root met:
```
curl -sS --fail -o ingest/tests/fixtures/openmeteo/marine_3loc_2models.json \
 "https://marine-api.open-meteo.com/v1/marine?latitude=52.4700,52.7500,52.0900&longitude=4.5700,5.3000,5.1200&hourly=wave_height,wave_period,wave_direction&models=ewam,ecmwf_wam&timezone=GMT&timeformat=unixtime&forecast_days=7&cell_selection=sea"
```
- `FIXTURE_LOCATIONS = [SpotLocation(spot_id="fixture-a", lat=52.47, lon=4.57), SpotLocation(spot_id="fixture-b", lat=52.75, lon=5.30), SpotLocation(spot_id="fixture-c", lat=52.09, lon=5.12)]` (kust, IJsselmeer, binnenland; de ids sorteren in fixturevolgorde, zodat ook de job-test met `load_spot_locations` klopt).
- `CAPTURE_URL` en `CAPTURE_DATE` als constanten in `test_openmeteo_marine.py`; `test_fixture_matches_current_params` vergelijkt `build_marine_params(FIXTURE_LOCATIONS)` per parameter met `httpx.URL(CAPTURE_URL).params`.
- Bronvermelding: de module-docstring van `test_openmeteo_marine.py` begint met `Weather data by Open-Meteo.com (https://open-meteo.com/), licensed under CC BY 4.0 (https://creativecommons.org/licenses/by/4.0/). Wave models: DWD EWAM and ECMWF WAM.` In `README.md` komen er twee regels bij: `Wave data in marine_3loc_2models.json: DWD (EWAM) and ECMWF (WAM) via Open-Meteo.` en `marine_3loc_2models.json: recorded on <YYYY-MM-DD> from <capture-URL>.`

**Synthetisch.** In `tests/openmeteo_payloads.py`:
```python
Triple = tuple[Value | Sequence[Value], Value | Sequence[Value], Value | Sequence[Value]]  # height, period, direction

def make_marine_payload(n_locations: int, *, start: datetime, hours: int = 3,
                        ewam: Triple = (1.2, 5.0, 250.0),
                        ecmwf: Triple = (1.4, 6.0, 260.0),
                        units: Mapping[str, str] | None = None) -> Any
```
Zelfde regels als `make_forecast_payload`: alle sleutels `f"{var}_{model}"` voor `MARINE_MODELS`, eenheden `m`/`s`/`°` (overschrijfbaar met `units`), `time` = `start + k·3600` in Unix-seconden, `location_id` vanaf element 1, één locatie → object. Scalars worden herhaald, sequences (geen `str`) moeten lengte `hours` hebben.

### Per acceptatiecriterium
| AC | Tests | Opzet |
|---|---|---|
| AC-1 | `test_openmeteo_marine.py`: `::test_fixture_all_valid_at_utc` (elke `valid_at` heeft `tzinfo is UTC`). `::test_fixture_values_match_raw_json`: voor elke locatie `l` en index `i` wordt de verwachting uit de ruwe JSON afgeleid met de regel van A7 (eerst `ewam`, dan `ecmwf_wam`; richting `int(round(x)) % 360`); bestaat er een verwacht drietal, dan is er precies één `MarineHour` met `spot_id == FIXTURE_LOCATIONS[l].spot_id`, `valid_at == fromtimestamp(time[i], UTC)` en exact die waarden, anders geen rij. `::test_fixture_inland_has_no_rows` (E3): geen rij met `spot_id == "fixture-c"`, en de test assert eerst dat alle zes ruwe reeksen van locatie 2 alleen `null` bevatten. `::test_fixture_lake_uses_ewam_only` (E4): voor `fixture-b` komt elke rij uit `ewam` (waarden gelijk aan de `ewam`-reeksen), het aantal rijen ligt strikt tussen 0 en `len(time)`. `::test_fixture_coast_switches_to_ecmwf` (E5): voor `fixture-a` zijn er rijen gelijk aan `ewam` én rijen (op indexen waar `ewam` helemaal `null` is) gelijk aan `ecmwf_wam`; beide aantallen > 0. `::test_fixture_values_belong_to_spot`: de rij van `fixture-a` en die van `fixture-b` op `time[0]` hebben de ruwe waarden van hun eigen element (locatie 0 resp. 1) en verschillen van elkaar. | fixture |
| AC-2 | `test_job_marine.py`: `::test_job_records_usage_under_marine_source`: 1 spot, geslaagde run → `api_usage` (vandaag, `open_meteo_marine`) `calls == 1.0`, `requests == 1`, geen rij voor `open_meteo_forecast`, `result.calls == 1.0`. `::test_job_budget_exceeded_no_request` (E22): seed (vandaag, `open_meteo_forecast`, 7999.5) → `MockTransport` registreert 0 requests, `skipped_budget is True`, `rows == 0`, `api_usage` ongewijzigd, `marine_hours` leeg. `::test_job_budget_boundary_inclusive` (E23): seed 7999.0 → 1 request. `::test_job_monthly_budget_exceeded_no_request`: rijen eerder in de maand met samen 239.999,5 → 0 requests. `test_pipeline.py::test_marine_budget_skipped_after_forecast`: seed (dag, `open_meteo_forecast`, 7998.5) → stap `forecast` `ok` (gewicht 1,2 → 7999,7), stap `marine` `partial` met `counts["skipped_budget"] is True` en `warnings == (MARINE_BUDGET_WARNING,)`, annotatie `::warning::marine: Open-Meteo budget guard reached: marine request skipped`, run `partial`, exit 0. | `FakeSupabase`, `make_marine_payload` |
| AC-3 | `test_pipeline.py::test_steps_contract_order`: `["spots_sync", "forecast", "marine", "tides", "evaluate", "alerts"]` en gelijk aan `STEP_NAMES`. `::test_marine_exception_is_partial_run` (E28): met `seed_user(db)` en `marine_fetch=failing_marine_fetch(RuntimeError("boom"))` → stap `marine` `failed` met `error_type == "RuntimeError"`; `tides`, `evaluate` en `alerts` `ok`; `report.status == "partial"`, `exit_code == 0`; `alerts.counts["events"] == 1`. `::test_marine_fetch_error_is_partial_step`: `failing_marine_fetch(MarineFetchError("down"))` → stap `marine` `partial` met `counts["errors"] == ["chunk 1/1: down"]`, run `partial`, exit 0. `::test_marine_step_ok_counts`: `run_real` → stap `marine` `ok`, `counts["rows"] == len(WINDS)`, `counts["calls"] == 1.0`; `marine_hours` bevat die rijen. `::test_all_steps_ok_records_run` blijft groen met de nieuwe `STEP_NAMES`. | `run_real` met `fake_marine_fetch` |
| AC-4 | `supabase test db`: `06_marine_hours.test.sql` (zie hieronder) en het bijgewerkte `01_schema.test.sql`. | lokale stack |
| AC-5 | Handmatig (verifier) tegen de lokale stack volgens de nieuwe RUNBOOK-sectie: test-spot 52,47 / 4,57 invoegen, `uv run shakka marine fetch` (exit 0, `rows` > 0), `select count(*), min(valid_at), max(valid_at) from public.marine_hours where spot_id = 'test-strand';` geeft rijen tot ca. dag 7; een tweede run verdubbelt het aantal niet. Zonder Docker: `NEEDS_LARS` of de verifier. | lokale stack |
| AC-6 | `cd web && npm run check && npm test && npm run build && npm run verify:build` en `bash scripts/check-no-client-openmeteo.sh` (exit 0). `spot-page.test.ts`, nieuw `describe('waves (WP-12, AC-6)')`: (a) `pageData({ marine: [MARINE_FRESH] })` → `hourOf('14:00').closest('li')` bevat een `.waves` met tekst `Golven 1,2 m, periode 5 s, uit WZW (250°)`; er is precies één `.waves`; de notitie `WAVES_NOTE_NL` staat er. (b) `pageData()` (zonder golfdata) → `document.querySelectorAll('.waves').length === 0`, geen `.waves-note`, geen `role="alert"`. (c) `pageData({ marine: [MARINE_STALE] })` → geen `.waves`. | fixtures hieronder |
| AC-7 | `data-tables.test.ts`: alle treffers van `/\.from\(/g` zijn ook treffers van `/\.from\('(spots|evaluations|tide_extremes|marine_hours)'\)/g`; elk van de vier tabellen komt minstens één keer voor. De verifier draait letterlijk `grep -n "\.from(" web/src/lib/data.ts`. | broncode |

### pgTAP `supabase/tests/06_marine_hours.test.sql`, `plan(20)`
Fixture (postgres): `insert into public.spots (id, name) values ('pgtap-spot', 'Pgtap Spot');` en één rij `('pgtap-spot', '2026-10-14T12:00:00Z', 1.2, 5.0, 250, '2026-10-14T11:00:00Z')`.
1. `columns_are` (6 kolommen in volgorde van de migratie);
2. `col_is_pk` (`spot_id`, `valid_at`);
3. `has_index` `marine_hours_valid_at_idx`;
4. `table_privs_are` `anon` = `{SELECT}`;
5. `table_privs_are` `authenticated` = `{SELECT}`;
6. `table_privs_are` `service_role` = `{DELETE, INSERT, SELECT, UPDATE}`;
7. `policies_are` = `{marine_hours_read}`;
8. `throws_ok` hoogte `-0.1` → `23514`;
9. `throws_ok` periode `-1` → `23514`;
10. `throws_ok` richting `360` → `23514`;
11. `throws_ok` drie keer `null` → `23514` (`marine_hours_has_value`);
12. `throws_ok` onbekende spot → `23503`;
13. `lives_ok` rij met alleen `wave_height_m` (ander uur);
14. als `anon`: `results_eq('select count(*)::int from public.marine_hours', array[2])`;
15. als `anon`: `throws_ok` insert → `42501`;
16. als `anon`: `throws_ok` `update public.marine_hours set wave_height_m = 1` → `42501`;
17. als `anon`: `throws_ok` `delete from public.marine_hours` → `42501`;
18. als `authenticated` (met `request.jwt.claims` van een willekeurige uuid, zoals in `05_push_subscriptions.test.sql`): `results_eq` count `2`;
19. als `authenticated`: `throws_ok` insert → `42501`;
20. na `reset role`: `delete from public.spots where id = 'pgtap-spot'` en `is_empty($$select 1 from public.marine_hours$$)` (cascade).

Gebruik `begin; ... select * from finish(); rollback;` zoals de bestaande bestanden.

### Overige ingest-tests
- `test_domain_marine.py`: `test_marine_hour_requires_aware`, `test_normalizes_to_utc` (+02:00 → UTC), `test_rejects_non_hour`, `test_ranges` (hoogte -1, periode -1, richting 360, `nan` → `ValidationError`), `test_all_none_rejected`, `test_single_value_allowed`, `test_frozen`, `test_to_row_keys_exact`, `test_from_row_roundtrip` (via `shakka.db.to_json`; `valid_at` met `+00:00` en met `Z`). De bestaande `test_domain_purity.py` dekt het nieuwe bestand automatisch.
- `test_openmeteo_marine.py` (synthetisch, met `make_marine_payload`): `test_build_params_exact`, `test_build_params_validation` (0 en 51 locaties, `forecast_days` 0 en 9 → `ValueError`), `test_models_tuple` (exact `("ewam", "ecmwf_wam")`, minstens 2), `test_fixture_matches_current_params`, en E6–E20 met de testnamen uit de tabel. `test_fetch_marine_parses_mocked_response` (één request naar host `marine-api.open-meteo.com`, pad `/v1/marine`, params gelijk aan `build_marine_params`), `test_fetch_marine_empty_locations_no_request`, `test_fetch_marine_wraps_request_error` (400 met reason → `MarineFetchError` met melding die begint met `open-meteo marine: HTTP 400`, zonder URL).
- `test_job_marine.py` (naast AC-2): `test_job_skips_spots_without_coordinates` (3 spots, 1 zonder → request met 2 latitudes, `spots == 2`), `test_job_no_spots_no_requests`, `test_job_upsert_on_conflict` (`fake.upserts` bevat `("marine_hours", "spot_id,valid_at")`, rijen met exact de 6 sleutels en `fetched_at == now`), `test_job_fixture_end_to_end` (seed `fixture-a/b/c` met de fixturecoördinaten, `MockTransport` geeft de fixture → `marine_hours` bevat precies `len(parse_marine_response(fixture, FIXTURE_LOCATIONS))` rijen, geen voor `fixture-c`), `test_job_deduplicates_before_upsert` (via `fetch=` twee rijen met dezelfde PK), `test_job_fetch_error_books_weight` (400 met body `{"error": true, "reason": "bad request"}` → `errors == ["chunk 1/1: open-meteo marine: HTTP 400: bad request"]`, `rows == 0`, `api_usage` marine `calls == 1.0`, `requests == 1`, geen upsert), `test_job_three_500_reports_error` (met `fetch=functools.partial(fetch_marine, sleep=fake_sleep)`, 3 requests, sleeps `[1.0, 2.0]`), `test_job_chunks_by_50` (51 spots → 2 requests met 50 en 1 latitudes), `test_delete_old_marine_only_older_than_48h` (rijen op `now-72h`, `-49h`, `-48h`, `-47h`, `+1h` → eerste twee weg, returnwaarde 2), `test_delete_old_marine_boundary`, `test_job_runs_cleanup` (`result.deleted`), `test_job_database_error_propagates`, `test_job_rejects_naive_now`.
- `test_cli_marine.py` (env met nepwaarden zoals `test_cli_forecast.py`; `runtime.open_db`, `runtime.open_http` en `runtime.utcnow` gemonkeypatcht; de HTTP-client gebruikt een `MockTransport` met `make_marine_payload`): `test_help_lists_marine_fetch`, `test_fetch_success_output` (exacte eerste regel en `marine: ok`, exit 0; de secret-waarde staat niet in de uitvoer), `test_fetch_errors_exit_1` (400), `test_missing_config_exit_1` (geen `open_db`-aanroep), `test_database_error_exit_1`, `test_resources_closed` (na een `DatabaseError` is `http.is_closed` True en `close()` van de fake één keer aangeroepen).
- `test_openmeteo_isolation.py` blijft ongewijzigd en dekt de nieuwe host (alleen onder `shakka/openmeteo/`).
- `pipeline_fixtures.py`:
  ```python
  def fake_marine_fetch(http, locations, *, forecast_days: int = 7) -> list[MarineHour]:
      return [MarineHour(spot_id=loc.spot_id, valid_at=at(h), wave_height_m=1.0,
                         wave_period_s=5.0, wave_dir_deg=270)
              for loc in locations for h in WINDS]

  def failing_marine_fetch(exc: Exception) -> Callable[..., list[MarineHour]]: ...
  ```
  `run_real` krijgt `kw.setdefault("marine_fetch", fake_marine_fetch)`; `patch_runtime` in `test_cli_pipeline.py` krijgt `monkeypatch.setattr(om_marine, "fetch_marine", fake_marine_fetch)` (met `import shakka.openmeteo.marine as om_marine`).

### Web-fixtures (`web/test/fixtures/spot-data.ts`, toevoegen)
```ts
export const MARINE_FRESH: MarineHour = {
	spot_id: 'test-strand', valid_at: '2026-07-15T12:00:00+00:00',
	wave_height_m: 1.24, wave_period_s: 5.4, wave_dir_deg: 250, fetched_at: '2026-07-15T12:05:00+00:00'
};
export const MARINE_STALE: MarineHour = {
	...MARINE_FRESH, valid_at: '2026-07-15T12:00:00+00:00', fetched_at: '2026-07-15T09:29:00+00:00'
};
```
(`NOW_FRESH` = 12:30Z: `MARINE_STALE` is 3 uur en 1 minuut oud.) `pageData` krijgt `marine: [] as MarineHour[]` vóór `...overrides`.

### Overige web-tests
- `marine.test.ts`: `formatMeters` (1.24 → `'1,2'`, 1.25 → `'1,3'`, 0 → `'0,0'`, 0.84 → `'0,8'`); `waveText(MARINE_FRESH) === 'Golven 1,2 m, periode 5 s, uit WZW (250°)'`; met `wave_height_m: null` → `'Golven hoogte onbekend, periode 5 s, uit WZW (250°)'`; met alleen hoogte → `'Golven 1,2 m, periode onbekend, richting onbekend'`. `marineByHour`: verse rij → sleutel `Date.parse('2026-07-15T12:00:00Z')` (dus ook gevonden met de `Z`-notatie, E33); `MARINE_STALE` → leeg; `fetched_at` precies 3 uur oud → aanwezig; rij met drie keer `null` → leeg; lege lijst → lege `Map`.
- `marine-schema.test.ts` (node): leest `../../supabase/migrations/20261015180000_marine_hours.sql`, pakt het blok `create table public.marine_hours (` tot `);` met dezelfde regel als `schema-columns.test.ts`, en eist `[...MARINE_HOUR_COLUMNS]` gelijk aan die kolommen (zelfde volgorde). Daarnaast: geen migratie bevat `alter table … public.marine_hours … add|drop|rename column`.
- `data.test.ts`: `getMarineHours('test-strand', 2026-07-15T12:00Z, 2026-07-22T22:00Z)` → één `Call` op `marine_hours` met ops `select(MARINE_HOUR_COLUMNS.join(','))`, `eq('spot_id', 'test-strand')`, `gte('valid_at', '2026-07-15T12:00:00.000Z')`, `lt('valid_at', '2026-07-22T22:00:00.000Z')`, `order('valid_at', asc)`, `range(0, 999)`; een antwoord met `error: { code: '42501', message: 'secret detail' }` → `DataError` met `operation 'getMarineHours'` en zonder `'secret detail'`.
- `page-data.test.ts`: `getMarineHours: vi.fn()` in het gehoiste object; in `beforeEach` na `vi.clearAllMocks()`: `data.getMarineHours.mockResolvedValue([])`. Nieuwe tests: (1) `SPOT_UNVERIFIED` → `getMarineHours('test-strand', 2026-07-15T12:00Z, 2026-07-22T22:00Z)` en `res.marine` gelijk aan het gemockte resultaat; (2) spot met `lat: null, lon: null` → `getMarineHours` niet aangeroepen, `marine: []`; (3) `getMarineHours` rejectet met `new Error('secret detail')` → `kind 'ok'`, `marine: []`, `console.warn` precies één keer, geen `'secret detail'` en geen `'test-strand'` in de warn-argumenten. De bestaande tests blijven ongewijzigd groen.

## Externe afhankelijkheden
**Packages:** geen nieuwe (A17). Ingest: `httpx` (`MockTransport`), `pydantic` 2, standaardbibliotheek. Web: bestaande versies uit WP-13/WP-14.

**Open-Meteo Marine API** (gecontroleerd op 15-10-2026):

| Wat | Bevinding | Bron |
|---|---|---|
| Endpoint | `GET https://marine-api.open-meteo.com/v1/marine` | https://open-meteo.com/en/docs/marine-weather-api |
| Parameters | `latitude`/`longitude` kommagescheiden; `hourly`; `models`; `timezone` (standaard `GMT`); `timeformat` (`iso8601` of `unixtime`); `forecast_days` (documentatie: 0–8; de website-opties gaan verder, wij gebruiken 7 en valideren 1–8); `cell_selection` `land`/`sea`/`nearest`, standaard `sea`; `length_unit` standaard `metric` | https://open-meteo.com/en/docs/marine-weather-api, https://github.com/open-meteo/open-meteo-website/blob/main/src/routes/en/docs/marine-weather-api/options.ts |
| Variabelen | `wave_height` (m), `wave_period` (s), `wave_direction` (°, "0° = From north towards south; 90° = From east"); alle drie "Instant" | https://open-meteo.com/en/docs/marine-weather-api |
| Model-id's | `best_match`, `meteofrance_wave`, `meteofrance_currents`, `ewam` (DWD EWAM, Europa, 0,05°, elk uur), `gwam`, `ecmwf_wam` (ECMWF WAM, 9 km, elk uur), `ecmwf_wam025`, `ncep_gfswave025`, `ncep_gfswave016`, `era5_ocean` | `options.ts` (zie hierboven) en de modeltabel op de docs-pagina |
| Multi-model-naamgeving | `<variabele>_<model-id>` in `hourly` en `hourly_units`, eenheden `m`, `s`, `°`; `time` in Unix-seconden bij `unixtime`; stappen van 3600 s | live-call met de capture-URL op 15-10-2026 |
| Meerdere locaties | "the JSON output changes to a list of structures"; waargenomen: `location_id` ontbreekt bij element 0, daarna `1`, `2` | docs plus live-call |
| Dekking (live, 15-10-2026) | 52,47/4,57: `best_match` = `ewam`, data tot ca. index 78, daarna `null`; `ecmwf_wam` alle uren. 52,75/5,30 (IJsselmeer): `ewam` ca. 79 uur, `ecmwf_wam` geen data. 52,09/5,12: alles `null` | live-calls op 15-10-2026 |
| Foutformaat | HTTP 400 met `{"error": true, "reason": "..."}` | docs |
| Nauwkeurigheid | "Accuracy is limited in coastal areas ... may be completely unreliable further inland. This is not suitable for coastal navigation" (basis voor de notitie op de pagina, A10) | docs |
| Bronvermelding | "All users of Open-Meteo data must provide a clear attribution to DWD as well as a reference to Open-Meteo"; CC BY 4.0 | https://open-meteo.com/en/docs/marine-weather-api, https://open-meteo.com/en/licence |
| Limieten en gewicht | 10.000/dag, 300.000/maand, per IP over alle API's; gewicht volgens `calculateQueryWeight` (variabelen × modellen ≤ 10 en ≤ 14 dagen → 1 per locatie) | https://open-meteo.com/en/pricing, WP-03 blueprint (A4) |

**Supabase/supabase-js:** dezelfde methoden als WP-14 (`select`, `eq`, `gte`, `lt`, `order`, `range`); bronnen staan in de WP-14-blueprint. pgTAP-functies (`columns_are`, `col_is_pk`, `has_index`, `table_privs_are`, `policies_are`, `throws_ok`, `lives_ok`, `results_eq`, `is_empty`) zoals al gebruikt in `supabase/tests/`.

Geen API-sleutel, geen secrets, geen betaalde dienst.

## Risico's
- **R1. Modelhorizon of -dekking verandert.** Als EWAM langer of korter loopt, verschuift alleen het omslagpunt; de parser hangt niet af van een vaste index. Verdwijnt een model-id, dan geeft Open-Meteo een 400 met reason; die komt in `errors` en in `ingest_runs` (geen mail, A15). De mapping staat op één plek (`MARINE_MODELS`).
- **R2. Sprong op het omslagpunt.** EWAM en ECMWF WAM verschillen iets (in de live-call 0,80 vs 0,90 m). Op het uur van de overgang kan de golfhoogte een kleine sprong maken. Alleen weergave; geaccepteerd.
- **R3. Gedeeld IP van GitHub Actions** (WP-03 R1): een 429 of bereikte daglimiet die niet van ons komt. Mitigatie: retries, fout per chunk, oude golfrijen verdwijnen na 3 uur van de pagina (A9).
- **R4. Een structuurfout laat de hele chunk falen** (alle spots tegelijk). Bewust: liever geen golven dan verkeerd toegewezen golven.
- **R5. Mergeconflicten met WP-15/WP-16** in `spot/[id]/+page.svelte`, `page-data.ts`, `spot-data.ts`, `app.css` en `RUNBOOK.md`. De wijzigingen zijn klein en additief; de orchestrator lost ze op door beide kanten te behouden. Ook het RUNBOOK-sectienummer kan bij de merge verschuiven.
- **R6. Migratievolgorde.** Krijgt een parallelle WP een migratie met een eerdere tijdstempel die pas na deze WP gemerged wordt, dan weigert `supabase db push` die zonder `--include-all`. Mitigatie: melden in "Nodig van Lars" van die WP; deze WP gebruikt de eerstvolgende vrije tijdstempel.
- **R7. Kustnauwkeurigheid.** De golfdata is een modelwaarde op een rastercel op open water; een strand achter een zandbank kan anders zijn. Mitigatie: notitie op de pagina (A10); golven tellen niet mee in het oordeel.
- **R8. Fixture veroudert.** Tests hangen niet af van de datum; `test_fixture_matches_current_params` dwingt een nieuwe capture af bij een parameterwijziging. Verandert de dekking (bijv. ECMWF krijgt IJsselmeer-data), dan faalt `test_fixture_lake_uses_ewam_only` pas na een nieuwe capture; dan die test aanpassen en noteren.

## Buiten scope
- Golven in de evaluatie, in `evaluations`, in alerts of in pushteksten.
- Swell, windgolven, stroming, watertemperatuur en andere marinevariabelen.
- Een golfkolom op de spotlijst (`/`) of op de kaart (WP-15).
- Golfmodel of `cell_selection` per spot; `--dry-run` op `shakka marine fetch` (A14).
- Een eigen versheidsbanner voor golven (A9: oude golfdata wordt verborgen).
- Wijzigingen in `Attribution.svelte`, `HourVerdict.svelte`, `.github/`, `scripts/`, `data/` of de WP-03-code in `shakka.openmeteo.forecast`/`client`.
- Een atomaire increment-RPC voor `api_usage` (WP-03 A9).

## Stappenplan voor de builder
Werk in de worktree `/Users/larst/Dev/Shakka/.claude/worktrees/WP-12` op branch `wp/WP-12`. Lees of print `.env` en `web/.env` nooit. Na elke ingest-stap: `cd ingest && uv run pytest && uv run ruff check . && uv run ruff format --check .`; na elke web-stap: `cd web && npm run check && npm test`. Eén commit per stap, in het Engels.

1. **Migratie en database-tests.**
   - Maak `supabase/migrations/20261015180000_marine_hours.sql` exact zoals in Interfaces.
   - Werk `supabase/tests/01_schema.test.sql` bij (tables_are, kolomtypen, foreign keys) en maak `06_marine_hours.test.sql` (`plan(20)`).
   - Ingest: `TABLE_KEYS` in `shakka/db.py`, het patroon in `tests/test_migrations.py`, de cascade in `tests/fakes.py` en `test_cascades` in `tests/test_fakes.py`.
   - Als Docker beschikbaar is: `supabase db reset && supabase test db` (groen). Anders noteren in `deviations.md`; de verifier draait het.

   Commit: `feat(db): add marine_hours table with read-only public access`.
2. **Domeintype, tests eerst.** Schrijf `tests/test_domain_marine.py` (rood), maak `src/shakka/domain/marine.py` (groen, ook `test_domain_purity.py`). Commit: `feat(domain): add MarineHour value type`.
3. **Fixture vastleggen.** Draai het `curl`-commando vanuit de repo-root; laat het bestand onbewerkt. Controleer (bijv. met `python -c` of `jq`):
   - een lijst van 3 objecten; `time` met 168 elementen in stappen van 3600 s;
   - element 0: `wave_height_ewam` bevat getallen én `null`, en op minstens één index waar het `ewam`-drietal helemaal `null` is, heeft `ecmwf_wam` een waarde;
   - element 1: `ewam` bevat getallen; `ecmwf_wam` mag leeg zijn;
   - element 2: alle zes reeksen alleen `null`;
   - eenheden `m`, `s`, `°` met achtervoegsel per model.

   Klopt element 0 of 2 niet, leg dan opnieuw vast of kies voor element 2 een ander binnenlandpunt; noteer elke afwijking in `deviations.md` en pas `FIXTURE_LOCATIONS`, de capture-URL en de README mee aan. Werk `tests/fixtures/openmeteo/README.md` bij. Commit: `test(ingest): add recorded Open-Meteo marine fixture`.
4. **Parameters, parser en fetch, tests eerst.** Voeg `make_marine_payload` toe aan `tests/openmeteo_payloads.py`; schrijf `tests/test_openmeteo_marine.py` (AC-1, E3–E20, fetch-tests, CC BY-regel in de docstring). Rood. Maak `src/shakka/openmeteo/marine.py`. Groen. Commit: `feat(openmeteo): add marine params, parser and fetch`.
5. **Job, tests eerst.** Schrijf `tests/test_job_marine.py` (AC-2 en overige jobtests). Rood. Maak `src/shakka/jobs/marine.py` zonder CLI-glue, met de volgorde uit Ontwerp/Job letterlijk. Groen. Commit: `feat(jobs): add marine ingest job with budget and cleanup`.
6. **CLI, tests eerst.** Schrijf `tests/test_cli_marine.py`. Rood. Voeg `run_marine_cli` toe en de groep `marine` in `cli.py` (alleen die toevoeging plus de `run-hourly`-docstring). Groen. Controleer `uv run shakka marine --help` en `uv run shakka marine fetch --help` (exit 0). Commit: `feat(cli): add shakka marine fetch`.
7. **Pipeline, tests eerst.** Voeg `fake_marine_fetch` en `failing_marine_fetch` toe aan `tests/pipeline_fixtures.py`; pas `run_real`, `test_steps_contract_order` en `test_spots_sync_failure_continues` (`["ok"] * 5`) aan en schrijf de nieuwe marinetests (AC-2-pipeline, AC-3); pas `patch_runtime` in `tests/test_cli_pipeline.py` aan. Rood. Wijzig `src/shakka/pipeline.py` zoals in Interfaces. Groen. Controleer dat de hele suite geen echte sleeps doet (`uv run pytest --durations=10`: geen test boven 1 s door marine). Commit: `feat(pipeline): add marine step after forecast`.
8. **Isolatie en hygiëne.** `grep -rn "open-meteo.com" ingest/src` (alleen onder `shakka/openmeteo/`), `grep -rn "httpx.Client(" ingest/src` (alleen `shakka/http.py`). Geen commit nodig als er niets verandert.
9. **Web: types, data en pure module, tests eerst.** Schrijf `web/test/marine.test.ts`, `web/test/marine-schema.test.ts`, de toevoeging in `data.test.ts` en de wijziging in `data-tables.test.ts`; voeg `MARINE_FRESH`, `MARINE_STALE` en de default `marine: []` toe aan de fixtures. Rood. Voeg `MarineHour`/`MARINE_HOUR_COLUMNS` toe aan `types.ts`, `getMarineHours` aan `data.ts` en maak `src/lib/marine.ts`. Groen. Draai `grep -n "\.from(" src/lib/data.ts` (vijf regels, vier tabellen). Commit: `feat(web): add marine_hours query and wave formatting`.
10. **Web: paginadata en spotpagina, tests eerst.** Pas `page-data.test.ts` aan en schrijf het nieuwe `describe` in `spot-page.test.ts`. Rood. Wijzig `page-data.ts`, `spot/[id]/+page.svelte` en `app.css` zoals in Interfaces. Groen, plus `npm run build`, `npm run verify:build` en vanuit de root `bash scripts/check-no-client-openmeteo.sh`. Commit: `feat(web): show waves per hour on the spot page`.
11. **RUNBOOK.** Nieuwe sectie "Golven (Open-Meteo Marine, vanaf WP-12)" met het eerstvolgende vrije nummer, in het Nederlands, met:
    - wat er gebeurt (elk uur na de forecast, alleen weergave, telt niet mee in oordeel of alerts);
    - `uv run shakka marine fetch`, de uitvoer en de exitcodes;
    - de modellen (EWAM, daarna ECMWF WAM) en `cell_selection=sea` in één zin, met verwijzing naar deze blueprint (A1);
    - het gedeelde budget (bron `open_meteo_marine` in `api_usage`, ca. 1 call per spot per run);
    - dat een mislukte marinestap geen mail geeft maar in `ingest_runs` staat (stap `marine`), en dat de app golfdata ouder dan 3 uur verbergt;
    - de lokale test (AC-5): `supabase start`, `.env` op de lokale stack, test-spot invoegen zoals §9, `uv run shakka marine fetch`, de controlequery uit AC-5, tweede run, opruimen;
    - fixture opnieuw vastleggen (het `curl`-commando; `CAPTURE_URL`/`CAPTURE_DATE` in `test_openmeteo_marine.py` en de README bijwerken);
    - `supabase db push` na de merge (§8).

    Werk daarnaast §11.7 bij (de app leest ook `marine_hours`) en §13.1 (stappen `spots_sync`, `forecast`, `marine`, `tides`, `evaluate`, `alerts`). Commit: `docs: document marine ingest and waves on the spot page`.
12. **Eindcontrole.**
    - `cd ingest && uv sync && uv run pytest && uv run ruff check . && uv run ruff format --check .`;
    - `cd web && npm ci && npm run check && npm test && npm run build && npm run verify:build`; vanuit de root `bash scripts/check-no-client-openmeteo.sh` (exit 0);
    - de greps uit stap 8 en 9, en `git grep --untracked -nE "sb_(secret|publishable)_[A-Za-z0-9_-]{20,}|eyJhbGciOi" -- . ':!docs'` (geen treffers);
    - met Docker: `supabase db reset && supabase test db` en AC-5 volgens de RUNBOOK; zonder Docker noteren in `deviations.md` (verifier of `NEEDS_LARS`);
    - `git status`: geen `.env`, `web/.env`, `web/build` of `node_modules` gestaged;
    - push `wp/WP-12` alleen met toestemming van de orchestrator.

**Nodig van Lars:** na de merge `supabase db push`; een reactie op A1 (modelkeuze).
