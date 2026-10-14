# Blueprint WP-03: Forecast-ingest wind (Open-Meteo multi-model) met call-budget
Status: DRAFT
Revisie: 1

## Doel
Elk uur per spot met coördinaten de windverwachting (snelheid, vlagen, richting) van vier modellen server-side ophalen bij Open-Meteo. De waarden worden in knopen opgeslagen in `forecast_hours`, rijen ouder dan 48 uur worden opgeruimd, en het verbruik wordt bewaakt in `api_usage` met een harde grens op 80% van de gratis limiet.

Deze WP levert:
- het pure type `ForecastHour` (input voor WP-05);
- een gedeelde Open-Meteo-requesthelper met retries (hergebruikt door WP-12);
- `BudgetGuard` (hergebruikt door WP-11 en WP-12);
- de job `run_forecast_ingest` (aangeroepen door WP-11);
- de CLI `shakka forecast fetch [--dry-run]`.

## Aannames
Voorstellen voor Lars staan gemarkeerd met **[keuze Lars]**. De builder bouwt het voorstel. Een andere keuze is een wijziging van één constante, plus de bijbehorende fixture en test.

- **A1. Model-id's (gecontroleerd op 14-10-2026, zie Externe afhankelijkheden).** **[keuze Lars]**

  | `ModelKey` | Open-Meteo-id | Waarom deze variant |
  |---|---|---|
  | `knmi` | `knmi_harmonie_arome_netherlands` | 2 km, elk uur ververst, horizon ca. 2,5 dag. Bewust niet `knmi_seamless`: die vult na 2,5 dag aan met ECMWF, en dan telt ECMWF in de consensus van WP-05 dubbel mee. |
  | `icon` | `dwd_icon_seamless` | Combineert ICON-D2 (2 km), ICON-EU en ICON global. Dekt de volle 7 dagen. |
  | `ecmwf` | `ecmwf_ifs` | IFS HRES 9 km, sinds 1-10-2025 open data. Heeft vlagen (`wind_gusts_10m`) en dekt 15 dagen. `ecmwf_ifs025` (0,25°) is grover. |
  | `gfs` | `ncep_gfs_seamless` | GFS seamless. Dekt 16 dagen. |

  De oudere namen `icon_seamless` en `gfs_seamless` werken ook, maar de huidige documentatie gebruikt de namen met prefix (`dwd_`, `ncep_`). In een multi-model-respons krijgt elke variabele het aangevraagde id als achtervoegsel, bijvoorbeeld `wind_speed_10m_dwd_icon_seamless`. Dat is gecontroleerd voor beide naamvormen.
- **A2. `cell_selection=sea`.** **[keuze Lars]** Open-Meteo kiest standaard (`land`) een landcel met een vergelijkbare hoogte. Een meting op 14-10-2026 voor testcoördinaat 52,47 N / 4,57 O met `ecmwf_ifs` gaf het volgende:
  - met `land`: cel 52,478 / 4,684, ruim 7 km landinwaarts, eerste uur 11,4 kn;
  - met `sea`: cel 52,478 / 4,517, op zee, eerste uur 18,4 kn.

  Kiters varen op het water, dus de zeecel is representatiever. Met `land` zou de app systematisch te weinig wind voorspellen. Voor meren kiest `sea` een watercel als het model het meer als water kent; anders valt Open-Meteo terug op de dichtstbijzijnde cel ("prefers"). De constante is `CELL_SELECTION` in `shakka.openmeteo.forecast`. Alternatieven zijn `nearest` (neutraal) en `land` (de standaard van Open-Meteo).
- **A3. Tijdformaat.** De parameters zijn `timezone=GMT` (de documentatiestandaard; UTC-offset 0) en `timeformat=unixtime`. Tijden komen dan als Unix-seconden en zijn per definitie UTC; er hoeft geen naïeve ISO-string te worden geïnterpreteerd. De parser eist `hourly_units.time == "unixtime"` en `utc_offset_seconds == 0`.
- **A4. Gewichtsformule.** De broncode van Open-Meteo (`ForecastApiResult.swift`, `calculateQueryWeight`) rekent per locatie `max(1, max(v/10, d/14 · v/10))`, met `v` = variabelen × modellen en `d` = dagen. AC-3 eist voor (1, 3, 1, 21) minstens 1,5, terwijl de bron daar 1,0 geeft. Daarom gebruikt `estimate_call_weight` een conservatieve bovengrens: `n_locations · max(1, v/10) · max(1, d/14)`. Bij `d ≤ 14` (dus ook bij onze 7 dagen) is die exact gelijk aan de bron, en daarboven is hij nooit lager. Met 25 spots kost een run 25 × 1,2 = 30 calls. Per dag is dat 720 (9% van de guard), per maand ongeveer 22.300.
- **A5. Boekhouding per request.** Per chunk (één HTTP-request plus retries) wordt het budget één keer gecontroleerd en het gewicht één keer geboekt. Dat geldt ook als de fetch faalt, want een deel van de pogingen kan door Open-Meteo zijn meegeteld. Retries worden niet apart geteld. In het slechtste geval tellen we per uur 2 × 30 calls te weinig. De marge tussen guard en limiet (2.000 per dag) dekt dat ruim.
- **A6. Chunks van 50 locaties per request.** De URL blijft dan kort (ongeveer 1 kB), en het gewicht per request (60) blijft ver onder de minuutlimiet van 600. De startset van 25 spots past in één request.
- **A7. `--dry-run` doet geen enkele request naar Open-Meteo en geen schrijfacties.** **[keuze Lars]** De dry-run leest alleen `spots` en `api_usage` en toont het plan: aantal spots, aantal requests, het geschatte gewicht, het huidige verbruik en of het budget toereikend is. Alternatief: wel ophalen en alleen niet opslaan. Dat kost echter calls en hoort niet bij "dry".
- **A8. Vervangsemantiek.** Er is alleen een upsert plus het opruimen na 48 uur; verouderde voorspellingen worden niet actief vervangen. Een model dat een uur eerder wel en nu niet meer levert, laat dus de oude rij staan, met een oudere `fetched_at`. In de praktijk schuift de horizon alleen vooruit, dus dit komt zelden voor. Consumenten (WP-10) kunnen op `fetched_at` filteren (zie "Gevolgen voor latere WP's"). Een extra delete op `fetched_at` zou botsen met AC-5 ("verwijdert alleen rijen met `valid_at < now - 48h`").
- **A9. Read-modify-write op `api_usage` zonder lock.** Er is geen atomaire increment-RPC; WP-01 liet die keuze bij WP-03. Een RPC kost een migratie, en er draait maar één job tegelijk: WP-11 zet `concurrency: hourly`. Twee gelijktijdige handmatige runs kunnen één boeking verliezen; dat valt binnen de marge.
- **A10. `forecast_days=7`.** Dat staat in het contract en in AC-2. Opgemerkt: 8 dagen kost hetzelfde gewicht (de factor `d/14` blijft onder 1). Een wijziging is een besluit voor WP-10 of WP-16 (`days_ahead` tot 7) en valt buiten deze WP.
- **A11. Testcoördinaten in de fixture zijn testdata, geen spotdata.** Het gaat om 52,47 / 4,57 (dezelfde als in WP-05 AC-5) en 52,10 / 4,27. Ze komen niet in `data/spots.yaml`.
- **A12. Additieve uitbreidingen van het contract.** Bestaande signatures blijven geldig. De uitbreidingen zijn:
  - `ForecastHour.to_row()` en `ForecastHour.from_row()`;
  - `ForecastParseError` (subklasse van `ForecastFetchError`);
  - een keyword `sleep=` op `fetch_forecast`, en een keyword `fetch=` op `run_forecast_ingest`, naar het patroon van WP-04;
  - het veld `deleted` (met default) op `ForecastIngestResult`;
  - `BudgetGuard.usage()`, `daily_limit` en `monthly_limit`;
  - `plan_forecast_ingest`, `load_spot_locations` en `run_forecast_cli`;
  - de module `shakka.openmeteo.client` met `request_json`.

  Waarom: testbaarheid zonder echte sleeps, en hergebruik door WP-11 en WP-12.
- **A13. Geen nieuwe dependencies.** Alles werkt met httpx, pydantic en de standaardbibliotheek.

## Ontwerp

**Lagen.** De lagen volgen de afspraak "puur en I/O gescheiden":
1. `shakka.domain.forecast` (puur): `ModelKey`, `SpotLocation`, `ForecastHour`. Bevroren pydantic-modellen met `extra="forbid"`, zoals WP-02. De validatie legt de DB-CHECKs vooraf vast:
   - `wind_kn` en `gust_kn` zijn eindig en `>= 0`;
   - `dir_deg` ligt tussen 0 en 359;
   - `valid_at` is tz-aware, wordt naar UTC genormaliseerd en valt op een heel uur.
2. `shakka.openmeteo` (I/O; de enige plek waar `open-meteo.com` voorkomt):
   - `models.py`: de mapping `ModelKey` → id;
   - `client.py`: `request_json` met retries;
   - `forecast.py`: een pure parameterbouwer, een pure parser en `fetch_forecast`.
3. `shakka.budget`: de pure `estimate_call_weight` en `BudgetGuard` op `api_usage`.
4. `shakka.jobs.forecast`: spots laden, chunken, budget, fetch, upsert, opruimen, plus de CLI-glue.

**Parser.** De parser is streng op structuur en mild op waarden. Een structuurfout geeft `ForecastParseError` en de hele chunk faalt, omdat dat op een API-wijziging wijst. Structuurfouten zijn:
- een ontbrekende sleutel;
- een andere eenheid dan `kn` of `°`;
- een andere arraylengte dan `time`;
- een ander aantal locaties dan gevraagd;
- een `location_id` die niet klopt;
- een niet-numerieke waarde.

Losse waarden worden zo behandeld:
- `null`, NaN of ±inf wordt `None`, nooit `0`;
- een negatieve snelheid of vlaag wordt `None`;
- een richting wordt `round(x) % 360`;
- uren waarin alle drie de waarden `None` zijn, leveren geen rij op. Dat is bijvoorbeeld KNMI na ca. 2,5 dag.

Bij één locatie geeft Open-Meteo een object in plaats van een lijst; de parser normaliseert dat naar een lijst. `location_id` ontbreekt bij het eerste element en is `1, 2, …` bij de volgende (waargenomen op 14-10-2026). Daarom geldt: ontbreekt `location_id`, dan telt de positie; is hij er wel, dan moet hij gelijk zijn aan de positie.

**Retries.** `request_json` doet maximaal 3 pogingen. Opnieuw proberen gebeurt bij:
- HTTP 429;
- HTTP 5xx;
- elke `httpx.HTTPError` (verbindingsfout of timeout).

De wachttijd vóór poging 2 is 1 s en vóór poging 3 is 2 s. Bij een 429 met een integer `Retry-After` geldt `min(max(Retry-After, 1), 30)` seconden. Andere statuscodes (400 met `{"error": true, "reason": …}`, en 3xx omdat `make_client` geen redirects volgt) en een 200 met ongeldige JSON geven direct een fout, zonder retry. De melding bevat de status of de klassenaam van de exception en maximaal 200 tekens van `reason`, maar nooit de URL. `sleep` is injecteerbaar, zodat tests niet echt wachten. WP-22 kan dit later vervangen door `shakka.http.with_retries`.

**Job.** `run_forecast_ingest(db, http, budget, *, now, fetch=fetch_forecast)` werkt zo:
1. Laad `spots` (`id,lat,lon`). Spots zonder `lat` of `lon` worden overgeslagen.
2. Verdeel de locaties op volgorde van `id` in chunks van 50.
3. Per chunk:
   - schat het gewicht;
   - als `can_spend` faalt, wordt `skipped_budget=True` en stopt de lus (er gaan dan ook geen latere chunks meer uit);
   - anders volgt de fetch;
   - `ForecastFetchError` → een regel in `errors` en door naar de volgende chunk;
   - boek het gewicht (ook na een fout, zie A5);
   - dedupliceer op de PK en upsert met `on_conflict=spot_id,model,valid_at`. `fetched_at` is `now`.
4. Tot slot draait altijd `delete_old_forecasts` (`valid_at < now - 48h`).

`DatabaseError` wordt niet afgevangen. Een database die niet werkt, is een stapfout voor WP-11. Zo gaat er ook nooit een request uit als het budget niet te lezen is (fail-safe).

**Budget.** `BudgetGuard` leest met één select de `api_usage`-rijen van de lopende UTC-maand (`day gte <1e van de maand>` en `day lt <1e van de volgende maand>`). In Python telt hij de bronnen op die met `open_meteo_` beginnen. PostgREST kent in onze client geen `like`, en de tabel heeft per maand hooguit ongeveer 90 rijen.

`can_spend` geeft `True` als zowel `dag + gewicht <= daily_limit` als `maand + gewicht <= monthly_limit`. Precies op de grens mag dus nog; het contract zegt "meer dan". `record` leest de rij (`day`, `source`) en doet een upsert met `calls = round(oud + gewicht, 2)` en `requests = oud + requests`.

**CLI.** `shakka forecast fetch [--dry-run]` maakt `SupabaseRest.from_settings`, `make_client(timeout=30.0)` en `BudgetGuard(db)`, met `now = datetime.now(UTC)`. Dat mag in de CLI, want die valt buiten het domein. Met `--dry-run` roept de CLI `plan_forecast_ingest` aan. De uitvoer is vast (zie Interfaces). De exitcode is 0 bij succes en 1 bij fouten, bij een budgetstop of bij een onvolledige config.

## Bestanden

| Pad | Actie | Inhoud |
|---|---|---|
| `ingest/src/shakka/domain/forecast.py` | aanmaken | `ModelKey`, `SpotLocation`, `ForecastHour` (met `to_row` en `from_row`). Puur. |
| `ingest/src/shakka/openmeteo/__init__.py` | aanmaken | Alleen een docstring: `"""Open-Meteo clients. The only package that talks to open-meteo.com."""` |
| `ingest/src/shakka/openmeteo/models.py` | aanmaken | `OPEN_METEO_MODELS`. |
| `ingest/src/shakka/openmeteo/client.py` | aanmaken | `OpenMeteoRequestError`, `request_json`, retryconstanten. |
| `ingest/src/shakka/openmeteo/forecast.py` | aanmaken | Constanten, `ForecastFetchError`, `ForecastParseError`, `build_forecast_params`, `parse_forecast_response`, `fetch_forecast`. |
| `ingest/src/shakka/budget.py` | aanmaken | Constanten, `estimate_call_weight`, `BudgetUsage`, `BudgetGuard`. |
| `ingest/src/shakka/jobs/__init__.py` | aanmaken | Alleen een docstring: `"""Jobs that connect domain logic to the database and external sources."""` |
| `ingest/src/shakka/jobs/forecast.py` | aanmaken | `ForecastIngestResult`, `ForecastIngestPlan`, `load_spot_locations`, `plan_forecast_ingest`, `run_forecast_ingest`, `delete_old_forecasts`, `run_forecast_cli`, de seams `_open_resources` en `_utcnow`. |
| `ingest/src/shakka/cli.py` | wijzigen | Groep `forecast` met het commando `fetch --dry-run`. `doctor` blijft ongewijzigd. |
| `ingest/tests/fixtures/openmeteo/forecast_2loc_4models.json` | aanmaken | Echte respons, onbewerkt vastgelegd met de exacte capture-URL (zie Testplan). |
| `ingest/tests/openmeteo_payloads.py` | aanmaken | Helper `make_forecast_payload(...)` voor synthetische responses. |
| `ingest/tests/test_domain_forecast.py` | aanmaken | Validatie van de domeintypes, `to_row` en `from_row`. |
| `ingest/tests/test_openmeteo_forecast.py` | aanmaken | AC-1 en AC-2: parameterbouwer en parser (fixture plus synthetisch). |
| `ingest/tests/test_openmeteo_client.py` | aanmaken | Retries (AC-6, eenheidsniveau). |
| `ingest/tests/test_budget.py` | aanmaken | AC-3 en het guard-deel van AC-4. |
| `ingest/tests/test_job_forecast.py` | aanmaken | AC-4 (job), AC-5 en AC-6 (job). |
| `ingest/tests/test_cli_forecast.py` | aanmaken | CLI met fakes. |
| `ingest/tests/test_openmeteo_isolation.py` | aanmaken | AC-7 als permanente test. |
| `docs/RUNBOOK.md` | wijzigen | Nieuwe sectie `## 9. Forecast-ingest (vanaf WP-03)`. |

Geen migraties, geen wijziging in `shakka.db` of `FakeSupabase`, geen nieuwe dependencies. `docs/STATUS.md` werkt de orchestrator bij.

## Interfaces en contracten

### `shakka.domain.forecast`
```python
"""Forecast value types shared by the ingest (WP-03) and the evaluation (WP-05). Pure."""

class ModelKey(StrEnum):
    KNMI = "knmi"
    ICON = "icon"
    ECMWF = "ecmwf"
    GFS = "gfs"

class SpotLocation(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    spot_id: str = Field(min_length=1)
    lat: float = Field(ge=-90, le=90, allow_inf_nan=False)
    lon: float = Field(ge=-180, le=180, allow_inf_nan=False)

class ForecastHour(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    spot_id: str = Field(min_length=1)
    model: ModelKey
    valid_at: datetime            # validator: aware, else ValueError; astimezone(UTC);
                                  # minute == second == microsecond == 0, else ValueError
    wind_kn: float | None = Field(ge=0, allow_inf_nan=False)   # knots
    gust_kn: float | None = Field(ge=0, allow_inf_nan=False)   # knots
    dir_deg: int | None = Field(ge=0, le=359)                  # meteorological "from"

    def to_row(self, *, fetched_at: datetime) -> dict[str, Any]:
        """Row for public.forecast_hours. Keys exactly: spot_id, model (str value), valid_at,
        wind_kn, gust_kn, dir_deg, fetched_at. fetched_at must be aware (ValueError otherwise)."""

    @classmethod
    def from_row(cls, row: Mapping[str, Any]) -> "ForecastHour":
        """Inverse of to_row; valid_at may be a str (datetime.fromisoformat) or a datetime.
        fetched_at and unknown keys are ignored."""
```
Alle velden zijn verplicht (geen defaults), ook als de waarde `None` is. Er zijn geen imports buiten de standaardbibliotheek en pydantic.

### `shakka.openmeteo.models`
```python
OPEN_METEO_MODELS: Final[dict[ModelKey, str]] = {
    ModelKey.KNMI: "knmi_harmonie_arome_netherlands",
    ModelKey.ICON: "dwd_icon_seamless",
    ModelKey.ECMWF: "ecmwf_ifs",
    ModelKey.GFS: "ncep_gfs_seamless",
}
```
De volgorde ligt vast en bepaalt de volgorde in `models=`. Met maar één model zou Open-Meteo variabelen zonder achtervoegsel teruggeven; de parser veronderstelt er minstens twee (getest).

### `shakka.openmeteo.client`
```python
RETRY_ATTEMPTS: Final = 3
RETRY_BASE_DELAY_S: Final = 1.0      # delay before attempt n (n >= 2): base * 2 ** (n - 2)
RETRY_MAX_DELAY_S: Final = 30.0      # cap for Retry-After
MAX_REASON_CHARS: Final = 200

class OpenMeteoRequestError(Exception):
    def __init__(self, message: str, *, status: int | None = None) -> None: ...
    status: int | None

def request_json(
    http: httpx.Client,
    url: str,
    params: Mapping[str, str],
    *,
    attempts: int = RETRY_ATTEMPTS,
    base_delay: float = RETRY_BASE_DELAY_S,
    sleep: Callable[[float], None] = time.sleep,
) -> Any:
    """GET url with params and return the parsed JSON.
    Retries on 429, 5xx and httpx.HTTPError; other statuses and invalid JSON fail at once.
    Raises OpenMeteoRequestError. Messages never contain the URL."""
```
Vorm van de meldingen (exact):
- na de laatste poging: `"failed after 3 attempts: HTTP 500"` of `"failed after 3 attempts: ConnectError"`;
- bij een andere status dan 2xx, 429 of 5xx: `"HTTP 400: <reason, max 200 tekens>"`, of `"HTTP 400"` zonder reason;
- bij een 2xx met ongeldige JSON: `"invalid JSON response"`.

Per mislukte poging met retry volgt een log-warning: `logger.warning("open-meteo request attempt %d/%d failed: %s; retrying in %.1fs", ...)`. De logger is `logging.getLogger("shakka.openmeteo")`.

### `shakka.openmeteo.forecast`
```python
FORECAST_URL: Final = "https://api.open-meteo.com/v1/forecast"
HOURLY_VARIABLES: Final = ("wind_speed_10m", "wind_direction_10m", "wind_gusts_10m")
DEFAULT_FORECAST_DAYS: Final = 7
MAX_LOCATIONS_PER_REQUEST: Final = 50
CELL_SELECTION: Final = "sea"         # A2, choice for Lars
SPEED_UNIT: Final = "kn"
DIRECTION_UNIT: Final = "°"

class ForecastFetchError(Exception): ...
class ForecastParseError(ForecastFetchError): ...

def build_forecast_params(
    locations: Sequence[SpotLocation], *, forecast_days: int = DEFAULT_FORECAST_DAYS
) -> dict[str, str]:
    """ValueError if locations is empty or longer than MAX_LOCATIONS_PER_REQUEST,
    or forecast_days is not in 1..16."""

def parse_forecast_response(payload: Any, locations: Sequence[SpotLocation]) -> list[ForecastHour]:
    """Pure. Order: per location (input order), per model (OPEN_METEO_MODELS order), per time.
    Raises ForecastParseError on any structural problem (see Ontwerp)."""

def fetch_forecast(
    http: httpx.Client,
    locations: Sequence[SpotLocation],
    *,
    forecast_days: int = DEFAULT_FORECAST_DAYS,
    sleep: Callable[[float], None] = time.sleep,
) -> list[ForecastHour]:
    """[] without a request for empty locations. OpenMeteoRequestError -> ForecastFetchError
    (same message, prefixed "open-meteo forecast: "). ForecastParseError propagates."""
```
`build_forecast_params` geeft exact deze dict, in deze volgorde:
```python
{
    "latitude": ",".join(f"{loc.lat:.4f}" for loc in locations),
    "longitude": ",".join(f"{loc.lon:.4f}" for loc in locations),
    "hourly": "wind_speed_10m,wind_direction_10m,wind_gusts_10m",
    "models": "knmi_harmonie_arome_netherlands,dwd_icon_seamless,ecmwf_ifs,ncep_gfs_seamless",
    "wind_speed_unit": "kn",
    "timezone": "GMT",
    "timeformat": "unixtime",
    "forecast_days": str(forecast_days),
    "cell_selection": CELL_SELECTION,
}
```
`hourly` en `models` worden opgebouwd uit `HOURLY_VARIABLES` en `OPEN_METEO_MODELS`, niet als losse strings.

**Responsvorm** (gecontroleerd op 14-10-2026; de fixture legt die vast). Bij meer dan één locatie is de respons een lijst van objecten, bij één locatie een object. Per object:
```json
{
  "latitude": 52.456, "longitude": 4.582, "generationtime_ms": 1.08,
  "utc_offset_seconds": 0, "timezone": "GMT", "timezone_abbreviation": "GMT", "elevation": 7.0,
  "location_id": 1,
  "hourly_units": {"time": "unixtime",
                   "wind_speed_10m_knmi_harmonie_arome_netherlands": "kn",
                   "wind_direction_10m_knmi_harmonie_arome_netherlands": "°",
                   "wind_gusts_10m_knmi_harmonie_arome_netherlands": "kn", "...": "..."},
  "hourly": {"time": [1791936000, 1791939600, "..."],
             "wind_speed_10m_knmi_harmonie_arome_netherlands": [16.1, 13.6, "...", null], "...": []}
}
```
`location_id` ontbreekt bij het eerste object.

**Parserregels** (elke overtreding geeft `ForecastParseError` met de locatie-index en de sleutel in de melding):
1. Een object met `"error": true` → fout met `reason`.
2. Een object wordt `[object]`. Wat dan geen lijst is, is een fout. De lengte moet gelijk zijn aan `len(locations)`.
3. Per element `i`:
   - het element is een dict;
   - `location_id` ontbreekt of is gelijk aan `i`;
   - `utc_offset_seconds == 0`;
   - `hourly_units` en `hourly` zijn dicts;
   - `hourly_units["time"] == "unixtime"`;
   - `hourly["time"]` is een lijst van ints (geen bool).
4. Per model en variabele staat de sleutel `f"{var}_{model_id}"` in zowel `hourly_units` als `hourly`. De lijst heeft dezelfde lengte als `time`. De eenheid is `kn` voor `wind_speed_10m` en `wind_gusts_10m` en `°` voor `wind_direction_10m`. Is de windsnelheid niet in `kn`, dan volgt de melding `"... unit for wind_speed_10m_<id> is 'km/h', expected 'kn'"` (AC-2).
5. Waarden:
   - `None` blijft `None`;
   - een bool of een niet-getal (bijv. een string) is een fout;
   - een getal dat niet eindig is wordt `None`;
   - een snelheid of vlaag `< 0` wordt `None`;
   - een richting wordt `int(round(x)) % 360`.
6. `valid_at = datetime.fromtimestamp(t, tz=UTC)`. Zijn alle drie de waarden `None`, dan volgt er geen rij.
7. Een pydantic-`ValidationError` bij het maken van een `ForecastHour` (bijv. `t` niet op een heel uur) wordt een `ForecastParseError`.

### `shakka.budget`
```python
OPEN_METEO_DAILY_LIMIT: Final = 10_000
OPEN_METEO_MONTHLY_LIMIT: Final = 300_000
GUARD_FRACTION: Final = 0.8
DEFAULT_DAILY_LIMIT: Final = 8000.0       # == GUARD_FRACTION * OPEN_METEO_DAILY_LIMIT
DEFAULT_MONTHLY_LIMIT: Final = 240000.0   # == GUARD_FRACTION * OPEN_METEO_MONTHLY_LIMIT
REFERENCE_VARIABLES: Final = 10
REFERENCE_DAYS: Final = 14
OPEN_METEO_PREFIX: Final = "open_meteo_"
SOURCE_OPEN_METEO_FORECAST: Final = "open_meteo_forecast"
SOURCE_OPEN_METEO_MARINE: Final = "open_meteo_marine"
SOURCE_RWS: Final = "rws"
API_USAGE_SOURCES: Final = frozenset({SOURCE_OPEN_METEO_FORECAST, SOURCE_OPEN_METEO_MARINE, SOURCE_RWS})

def estimate_call_weight(n_locations: int, n_hourly_vars: int, n_models: int, forecast_days: int) -> float:
    """n_locations * max(1, vars*models/10) * max(1, days/14), rounded to 4 decimals.
    Upper bound of Open-Meteo's calculateQueryWeight; equal for days <= 14.
    ValueError if any argument < 1."""

@dataclass(frozen=True)
class BudgetUsage:
    daily: float     # sum of open_meteo_* calls on the UTC day of `now`
    monthly: float   # sum of open_meteo_* calls in the UTC month of `now`

class BudgetGuard:
    def __init__(self, db: SupabaseRest, *, daily_limit: float = DEFAULT_DAILY_LIMIT,
                 monthly_limit: float = DEFAULT_MONTHLY_LIMIT) -> None: ...  # limits > 0, else ValueError
    @property
    def daily_limit(self) -> float: ...
    @property
    def monthly_limit(self) -> float: ...
    def usage(self, *, now: datetime) -> BudgetUsage: ...
    def can_spend(self, weight: float, *, now: datetime) -> bool: ...
    def record(self, source: str, weight: float, *, now: datetime, requests: int = 1) -> None: ...
```
- `now` naïef → `ValueError` (in alle drie de methoden). De dag is `now.astimezone(UTC).date()`.
- `usage` doet één select: `db.select("api_usage", columns="day,source,calls", filters={"day": [f"gte.{first_of_month}", f"lt.{first_of_next_month}"]})`. Het telt `float(row["calls"])` op voor bronnen die met `OPEN_METEO_PREFIX` beginnen, en houdt de dagsom apart bij (`row["day"] == day.isoformat()`).
- `can_spend`: `weight` moet eindig zijn en `>= 0` (anders `ValueError`). Het resultaat is `usage.daily + weight <= daily_limit and usage.monthly + weight <= monthly_limit`.
- `record`:
  - `source` moet in `API_USAGE_SOURCES` zitten, `weight` moet eindig en `>= 0` zijn en `requests >= 0`; anders `ValueError`;
  - select `api_usage` met `day=eq.<dag>` en `source=eq.<source>`;
  - daarna `db.upsert("api_usage", [{"day": day, "source": source, "calls": round(old_calls + weight, 2), "requests": old_requests + requests}], on_conflict="day,source")`.

### `shakka.jobs.forecast`
```python
RETENTION: Final = timedelta(hours=48)
CHUNK_SIZE: Final = MAX_LOCATIONS_PER_REQUEST
FORECAST_TABLE: Final = "forecast_hours"
FORECAST_ON_CONFLICT: Final = "spot_id,model,valid_at"

class FetchForecast(Protocol):
    def __call__(self, http: httpx.Client, locations: Sequence[SpotLocation], *,
                 forecast_days: int = ...) -> list[ForecastHour]: ...

@dataclass(frozen=True)
class ForecastIngestResult:
    spots: int            # spots with coordinates considered
    rows: int             # rows upserted (after de-duplication)
    calls: float          # Open-Meteo weight recorded this run, rounded to 2 decimals
    skipped_budget: bool  # True if a chunk was not fetched because of the budget
    errors: list[str]     # one line per failed chunk: "chunk <n>/<total>: <message>"
    deleted: int = 0      # rows removed by delete_old_forecasts

@dataclass(frozen=True)
class ForecastIngestPlan:
    spots: int
    without_coords: list[str]   # spot ids without lat or lon, sorted
    requests: int
    weight: float
    usage: BudgetUsage
    within_budget: bool         # budget.can_spend(weight, now=now)

def load_spot_locations(db: SupabaseRest) -> tuple[list[SpotLocation], list[str]]:
    """select spots(id,lat,lon) in id order; returns (locations, ids without coordinates)."""

def plan_forecast_ingest(db: SupabaseRest, budget: BudgetGuard, *, now: datetime) -> ForecastIngestPlan:
    """No HTTP, no writes."""

def run_forecast_ingest(db: SupabaseRest, http: httpx.Client, budget: BudgetGuard, *,
                        now: datetime, fetch: FetchForecast = fetch_forecast) -> ForecastIngestResult: ...

def delete_old_forecasts(db: SupabaseRest, *, now: datetime) -> int:
    """db.delete("forecast_hours", filters={"valid_at": f"lt.{iso_utc(now - RETENTION)}"})."""

def run_forecast_cli(*, dry_run: bool, echo: Callable[[str], None]) -> int: ...
def _open_resources(settings: Settings) -> tuple[SupabaseRest, httpx.Client]: ...  # test seam
def _utcnow() -> datetime: ...                                                     # test seam
```
- `now` naïef → `ValueError` in `plan_forecast_ingest`, `run_forecast_ingest` en `delete_old_forecasts`.
- De logger is `logging.getLogger("shakka.jobs.forecast")`. Er wordt een info-regel gelogd per chunk en een warning bij een budgetstop.

**Rijvorm van de upsert:** `ForecastHour.to_row(fetched_at=now)` met precies de sleutels `spot_id`, `model`, `valid_at`, `wind_kn`, `gust_kn`, `dir_deg` en `fetched_at`.

**CLI-uitvoer** (exact; `{x:.2f}` voor gewichten en limieten via `{:.0f}`):

Normale run:
```
forecast: spots=<n> rows=<n> calls=<x.xx> deleted=<n> skipped_budget=<yes|no> errors=<n>
error   <errorregel>                      (één per fout)
forecast: ok | forecast: failed
```
Exit 0 als `errors` leeg is en `skipped_budget` False is; anders exit 1 en `forecast: failed`.

Dry-run:
```
forecast: dry run, no requests to Open-Meteo and no database writes
spots with coordinates: <n>, without coordinates: <m>
requests: <r>, estimated weight: <w.xx>
usage today: <d.xx> / 8000, this month: <m.xx> / 240000
budget: ok | budget: exceeded
```
Altijd exit 0, behalve bij een fout in de config of de database.

Foutgevallen in beide modi:
- een pydantic-`ValidationError` uit `get_settings()` → `forecast: configuration incomplete; run shakka doctor` en exit 1;
- `DatabaseError` → `forecast: database error: <str(exc)>` en exit 1. De melding is al geredigeerd door `shakka.db`.

Er gaan nooit waarden van environment-variabelen naar de uitvoer.

### `shakka.cli` (toevoeging)
```python
@cli.group()
def forecast() -> None:
    """Wind forecast ingest (Open-Meteo, server-side)."""

@forecast.command("fetch")
@click.option("--dry-run", is_flag=True, help="Show the plan; no Open-Meteo requests, no writes.")
def forecast_fetch(dry_run: bool) -> None:
    """Fetch wind forecasts for all spots with coordinates."""
    from shakka.jobs.forecast import run_forecast_cli

    raise SystemExit(run_forecast_cli(dry_run=dry_run, echo=click.echo))
```

### Gevolgen voor latere WP's
- **WP-05** importeert `ModelKey` en `ForecastHour` uit `shakka.domain.forecast`. `wind_kn` en `gust_kn` kunnen per uur en per model `None` zijn; ook met alle drie `None` is het type geldig, maar de ingest slaat zo'n rij nooit op.
- **WP-10** (`load_inputs`) maakt `ForecastHour` met `ForecastHour.from_row(row)` en filtert `valid_at` op `now - 1h` tot `now + 8d`. Aanbeveling: negeer per spot en model rijen waarvan `fetched_at` ouder is dan de nieuwste `fetched_at` van die spot min 3 uur (zie A8). Dit beslist WP-10.
- **WP-11** roept `run_forecast_ingest(db, http, BudgetGuard(db), now=now)` aan. Voor de operatormelding gebruikt WP-11 `BudgetGuard.usage(now=now).daily > 0.8 * guard.daily_limit`. `ForecastIngestResult` past in de `counts` van de step (`dataclasses.asdict`).
- **WP-12** hergebruikt `request_json`, `load_spot_locations`, `BudgetGuard` (source `SOURCE_OPEN_METEO_MARINE`) en `estimate_call_weight`. De constante voor de marine-URL hoort in `shakka/openmeteo/marine.py` (AC-7 blijft gelden).
- **WP-22** kan `request_json` intern laten overstappen op `shakka.http.with_retries`, zonder de signature te wijzigen.

## Edge cases
| # | Geval | Gedrag | Test |
|---|---|---|---|
| E1 | Spot zonder `lat` of `lon` | overgeslagen; telt in `without_coords` van het plan, niet in `spots` | `test_job_skips_spots_without_coordinates` |
| E2 | Geen enkele spot met coördinaten | 0 requests, `spots=0`, opruimen draait wel | `test_job_no_spots_no_requests` |
| E3 | Respons bij één locatie is een object | genormaliseerd naar een lijst | `test_parse_single_location_object` |
| E4 | Aantal elementen ≠ aantal locaties | `ForecastParseError` | `test_parse_location_count_mismatch` |
| E5 | `location_id` ontbreekt bij element 0 en is `1` bij element 1 | geaccepteerd | fixture |
| E6 | `location_id` klopt niet met de positie | `ForecastParseError` | `test_parse_location_id_mismatch` |
| E7 | KNMI levert `null` na ca. 2,5 dag | geen rijen voor die uren | `test_fixture_knmi_horizon` |
| E8 | Eén van de drie waarden `null` | rij met `None` op die plek, nooit `0` | `test_parse_partial_null_is_none` |
| E9 | NaN of inf in de JSON | `None` | `test_parse_non_finite_is_none` |
| E10 | Negatieve snelheid of vlaag | `None` | `test_parse_negative_speed_is_none` |
| E11 | Richting 360, 359,6 of -1 | 0, 0 en 359 | `test_parse_direction_normalized` |
| E12 | Waarde is een string of bool | `ForecastParseError` | `test_parse_non_numeric_value` |
| E13 | Eenheid `km/h` of `m/s` voor snelheid of vlaag, of geen `°` voor richting | `ForecastParseError` | `test_parse_rejects_non_knots` (AC-2) |
| E14 | Ontbrekende sleutel voor een model | `ForecastParseError` met de sleutelnaam | `test_parse_missing_model_key` |
| E15 | Arraylengte ≠ lengte van `time` | `ForecastParseError` | `test_parse_length_mismatch` |
| E16 | `hourly_units.time` niet `unixtime`, of `utc_offset_seconds != 0` | `ForecastParseError` | `test_parse_requires_unixtime_utc` |
| E17 | Tijdstip niet op een heel uur | `ForecastParseError` | `test_parse_rejects_non_hour_time` |
| E18 | Object met `"error": true` | `ForecastParseError` met de reason | `test_parse_error_object` |
| E19 | Dubbele PK binnen een chunk (bijv. dubbel tijdstip) | gededupliceerd vóór de upsert, laatste wint (WP-01: 21000) | `test_job_deduplicates_before_upsert` |
| E20 | Budget raakt op halverwege de chunks | eerste chunk opgeslagen, daarna stop, `skipped_budget=True` | `test_job_budget_stops_mid_run` |
| E21 | Budget precies op de grens (`dag + gewicht == 8000`) | toegestaan | `test_can_spend_boundary_inclusive` |
| E22 | `open_meteo_marine` telt mee, `rws` niet; vorige maand telt niet | volgens de prefix- en maandfilter | `test_usage_sums_open_meteo_sources_only`, `test_usage_ignores_previous_month` |
| E23 | 400 van Open-Meteo | geen retry, fout met reason | `test_request_400_no_retry` |
| E24 | 429 met `Retry-After: 5` | wacht 5 s (cap 30) | `test_request_429_honours_retry_after` |
| E25 | Verbindingsfout en daarna 200 | slaagt na 1 retry | `test_request_transport_error_then_ok` |
| E26 | 200 met ongeldige JSON | geen retry, fout | `test_request_invalid_json` |
| E27 | `now` naïef | `ValueError` | `test_job_rejects_naive_now`, `test_budget_rejects_naive_now` |
| E28 | Grens van de 48 uur (`valid_at == now - 48h`) | blijft staan (alleen `<`) | `test_delete_old_forecasts_boundary` |
| E29 | Meer dan 50 spots | meerdere requests van max. 50, op volgorde van `id` | `test_job_chunks_by_50` |
| E30 | Fout in de database bij het budget of de upsert | `DatabaseError` wordt doorgegeven; zonder leesbaar budget gaat er geen request uit | `test_job_database_error_propagates` |
| E31 | Twee spots met identieke coördinaten | twee locaties in de request, elk eigen rijen | `test_job_identical_coordinates` |
| E32 | Maandovergang (31-10 23:30Z ten opzichte van 01-11 00:30Z) | maandsom alleen van de lopende UTC-maand | `test_usage_month_boundary` |

## Testplan
Alle tests draaien zonder netwerk: `httpx.MockTransport` en `FakeSupabase`. Domeinlogica en pure functies worden eerst getest (stappen 1 tot en met 4).

**Fixture.** Bestand: `ingest/tests/fixtures/openmeteo/forecast_2loc_4models.json`, onbewerkt vastgelegd met:
```
curl -sS --fail -o ingest/tests/fixtures/openmeteo/forecast_2loc_4models.json \
 "https://api.open-meteo.com/v1/forecast?latitude=52.4700,52.1000&longitude=4.5700,4.2700&hourly=wind_speed_10m,wind_direction_10m,wind_gusts_10m&models=knmi_harmonie_arome_netherlands,dwd_icon_seamless,ecmwf_ifs,ncep_gfs_seamless&wind_speed_unit=kn&timezone=GMT&timeformat=unixtime&forecast_days=7&cell_selection=sea"
```
- `FIXTURE_LOCATIONS = [SpotLocation(spot_id="fixture-a", lat=52.47, lon=4.57), SpotLocation(spot_id="fixture-b", lat=52.10, lon=4.27)]`.
- De capture-URL en -datum staan als constanten in de docstring en code van `test_openmeteo_forecast.py`.
- `test_fixture_matches_current_params` borgt dat `build_forecast_params(FIXTURE_LOCATIONS)` exact de query van die URL geeft (vergelijking per parameter via `httpx.URL(CAPTURE_URL).params`). Verandert er een parameter, dan moet de fixture opnieuw worden vastgelegd (RUNBOOK 9).

**Synthetische responses.** `tests/openmeteo_payloads.py`:
```python
def make_forecast_payload(n_locations: int, *, start: datetime, hours: int = 3,
                          speed: float | None = 12.0, gust: float | None = 18.0,
                          direction: float | None = 270.0,
                          units: Mapping[str, str] | None = None) -> Any
```
De helper levert alle modellen uit `OPEN_METEO_MODELS`, `time` als Unix-seconden, en `location_id` vanaf element 1. Bij `n_locations == 1` is het een object, anders een lijst. Met `units` kun je een eenheid per sleutel overschrijven.

| AC | Tests (bestand::test) | Fixtures en opzet |
|---|---|---|
| AC-1 | `test_openmeteo_forecast.py::test_fixture_all_valid_at_utc`: elke `valid_at` heeft `utcoffset() == timedelta(0)` en `tzinfo is UTC`. `::test_fixture_values_match_raw_json`: volledige vergelijking. Voor elke locatie, elk model en elke index: als niet alle drie de waarden `null` zijn, bestaat precies één `ForecastHour` met `wind_kn`, `gust_kn` en `dir_deg` gelijk aan de ruwe waarde (richting `int(round(x)) % 360`), en anders géén rij. `::test_fixture_sample_per_model`: per model 3 expliciete steekproeven (index 0, 12 en 24 van locatie 0), met de verwachte waarden uit de ruwe JSON gelezen via de sleutel `f"wind_speed_10m_{id}"` (niet via de parser). `::test_parse_partial_null_is_none`: synthetisch met `gust=None` → `gust_kn is None`, nooit 0. `::test_fixture_no_all_none_rows`: geen enkele rij met alle drie `None`. `::test_fixture_knmi_horizon`: de fixture heeft voor KNMI zowel uren met data als uren met alleen `null`. Het aantal KNMI-rijen is groter dan 0 en kleiner dan 168. Voor ICON, ECMWF en GFS zijn het er 168 per locatie. | fixture, `FIXTURE_LOCATIONS` |
| AC-2 | `::test_build_params_exact`: exacte dict-gelijkheid met het contract, inclusief `wind_speed_unit=kn`, `hourly=…`, de vier id's, `forecast_days=7`, `timezone=GMT` en `timeformat=unixtime`. `::test_build_params_validation`: 0 locaties, 51 locaties, `forecast_days` 0 en 17 → `ValueError`. `::test_parse_rejects_non_knots`: geparametriseerd over `km/h` op `wind_speed_10m_<knmi-id>`, `m/s` op `wind_gusts_10m_<icon-id>` en `"deg"` op de richting → `ForecastParseError`, met de sleutel in de melding. `::test_fixture_matches_current_params`. `::test_models_mapping`: de mapping is exact zoals in het contract, met minstens 2 modellen. | synthetisch, fixture |
| AC-3 | `test_budget.py::test_weight_single`: (1, 3, 1, 7) == 1,0. `::test_weight_multi_model`: (1, 3, 4, 7) == approx(1,2) en ≥ 1,2. `::test_weight_scales_with_locations`: (25, 3, 4, 7) == approx(25 × (1, 3, 4, 7)). `::test_weight_long_range`: (1, 3, 1, 21) ≥ 1,5 (== approx(1,5)). `::test_weight_matches_open_meteo_up_to_14_days`: voor v ∈ {1, 3, 12, 30} en d ∈ {1, 7, 14} is het gelijk aan `max(1, max(v/10, d/14*v/10))`; voor d ∈ {15, 16} is het ≥. `::test_weight_rejects_zero`. | geen |
| AC-4 | `test_budget.py`: `::test_can_spend_daily_exceeded`: seed `api_usage` (vandaag, `open_meteo_forecast`, 7999,5) → `can_spend(1,2)` is False. `::test_can_spend_monthly_exceeded`: rijen eerder in de maand met samen 239.999,5 → False. `::test_can_spend_boundary_inclusive`. `::test_usage_sums_open_meteo_sources_only`. `::test_usage_ignores_previous_month`. `::test_usage_month_boundary`. `::test_record_creates_and_increments`: twee keer `record(1,2)` → `calls == 2,4` en `requests == 2`, met de upsert op `day,source`. `::test_record_rejects_unknown_source`. `test_job_forecast.py::test_job_budget_exceeded_no_request`: seed dagverbruik 7999 en 1 spot → `MockTransport` registreert 0 requests, `skipped_budget is True`, `rows == 0`, en `api_usage` is ongewijzigd. Hetzelfde voor het maandverbruik: `::test_job_monthly_budget_exceeded_no_request`. `::test_job_records_usage_after_success`: na een geslaagde run staat in `api_usage` voor (vandaag, `open_meteo_forecast`) `calls == 1,2`, `requests == 1` en `result.calls == 1,2`. `::test_job_budget_stops_mid_run`. | `FakeSupabase`, `make_forecast_payload` |
| AC-5 | `test_job_forecast.py::test_job_skips_spots_without_coordinates`: 3 spots, waarvan 1 zonder coördinaten → de request bevat 2 latitudes en `result.spots == 2`. `::test_job_upsert_on_conflict`: `fake.upserts` bevat `("forecast_hours", "spot_id,model,valid_at")`. De opgeslagen rijen hebben exact de 7 kolommen, met `fetched_at == now`. `::test_job_fixture_end_to_end`: een `MockTransport` geeft de fixture terug; `forecast_hours` bevat precies `len(parse_forecast_response(fixture))` rijen voor `fixture-a` en `fixture-b`. `::test_delete_old_forecasts_only_older_than_48h`: seed rijen op `now-72h`, `now-49h`, `now-48h`, `now-47h` en `now+1h` → alleen de eerste twee verdwijnen, de returnwaarde is 2, en `fake.writes` bevat `("delete", "forecast_hours")`. `::test_delete_old_forecasts_boundary`. `::test_job_runs_cleanup` (`result.deleted`). | `FakeSupabase` (seed `spots` met `id`, `name`, `lat`, `lon`), fixture |
| AC-6 | `test_openmeteo_client.py::test_request_429_then_200` (1 sleep van 1,0). `::test_request_three_500_raises` (3 calls, sleeps [1,0, 2,0], `OpenMeteoRequestError` met `"failed after 3 attempts: HTTP 500"`). `::test_request_transport_error_then_ok`. `::test_request_400_no_retry`. `::test_request_429_honours_retry_after`. `::test_request_invalid_json`. `::test_error_message_has_no_url`. `test_job_forecast.py::test_job_429_then_200_succeeds`: rijen opgeslagen, `errors == []`. `::test_job_three_500_reports_error`: geen exception, `errors` heeft 1 regel met `HTTP 500`, `rows == 0`, `skipped_budget is False`, 3 requests. De sleep wordt geïnjecteerd via `fetch=functools.partial(fetch_forecast, sleep=fake_sleep)`. | `MockTransport` met een reeks responses |
| AC-7 | `test_openmeteo_isolation.py::test_open_meteo_host_only_in_openmeteo_package`: doorzoekt alle bestanden onder `ingest/src` op `open-meteo.com`. Treffers mogen alleen onder `ingest/src/shakka/openmeteo/` staan, en daar moet er minstens één zijn. De verifier draait ook letterlijk `grep -rn "open-meteo.com" ingest/src`. | geen |
| AC-8 | Handmatig door de verifier tegen de lokale stack (RUNBOOK 9): test-spot invoegen, `uv run shakka forecast fetch` (exit 0), `select model, count(*) from forecast_hours group by model` geeft 4 modellen, en na een tweede run is `count(*)` niet verdubbeld (gelijk, of iets hoger door een verder vooruitgeschoven KNMI-horizon). Zonder Docker wordt dit `NEEDS_LARS` of komt het bij de verifier. | lokale stack |

Overige tests:
- `test_domain_forecast.py`:
  - `test_forecast_hour_requires_aware` (naïef → `ValidationError`);
  - `test_forecast_hour_normalizes_to_utc` (+02:00 → UTC);
  - `test_forecast_hour_rejects_non_hour`;
  - `test_forecast_hour_ranges` (`wind_kn=-1`, `dir_deg=360`, `nan` → `ValidationError`);
  - `test_forecast_hour_frozen`;
  - `test_to_row_keys_exact`;
  - `test_from_row_roundtrip` (via `to_row` → JSON-codering met `shakka.db.to_json` → `from_row` geeft hetzelfde object; `valid_at` als string met `+00:00` en met `Z`);
  - `test_spot_location_ranges`.
- De bestaande `test_domain_purity.py` dekt `shakka/domain/forecast.py` automatisch.
- `test_cli_forecast.py`:
  - `test_help_lists_forecast_fetch`;
  - `test_fetch_success_output` (monkeypatch `_open_resources` → `FakeSupabase` en een client met `MockTransport`; monkeypatch `_utcnow`; exacte eerste regel en `forecast: ok`, exit 0);
  - `test_fetch_errors_exit_1`;
  - `test_dry_run_makes_no_requests_and_no_writes` (`MockTransport` 0 requests, `fake.writes == []`, exacte regels, exit 0);
  - `test_missing_config_exit_1` (lege env → de configregel, geen request);
  - `test_database_error_exit_1`.

## Externe afhankelijkheden

**Packages:** geen nieuwe. Gebruikt worden `httpx` (0.28, al aanwezig; `MockTransport`, `HTTPError`), `pydantic` (2.x, al aanwezig) en de standaardbibliotheek (`time.sleep`, `datetime`, `math`, `logging`).

**API** (gecontroleerd op 14-10-2026):

| Wat | Bevinding | Bron |
|---|---|---|
| Endpoint | `GET https://api.open-meteo.com/v1/forecast` | https://open-meteo.com/en/docs |
| Parameters | `latitude` en `longitude` kommagescheiden voor meerdere locaties; `hourly`; `models` (kommagescheiden); `wind_speed_unit=kn`; `timezone` (standaard GMT); `timeformat=unixtime`; `forecast_days` 0–16 (standaard 7); `cell_selection` `land` (standaard), `sea` of `nearest` | https://open-meteo.com/en/docs |
| Meerdere locaties | "the JSON output changes to a list of structures". Waargenomen: `location_id` ontbreekt bij element 0 en is `1` bij element 1. Bij één locatie volgt een object | https://open-meteo.com/en/docs, plus live-call |
| Foutformaat | HTTP 400 met `{"error": true, "reason": "..."}` | https://open-meteo.com/en/docs |
| Model-id's | `knmi_harmonie_arome_netherlands` (2 km, 2,5 dag, elk uur); `dwd_icon_seamless`; `ecmwf_ifs` (label "ECMWF IFS HRES 9km"), naast `ecmwf_ifs025`; `ncep_gfs_seamless` | https://open-meteo.com/en/docs/knmi-api, https://open-meteo.com/en/docs/ecmwf-api, broncode van de website `src/routes/en/docs/{knmi,dwd,ecmwf,gfs}-api/options.ts` in https://github.com/open-meteo/open-meteo-website |
| Naamgeving bij multi-model | `<variabele>_<model-id>` in `hourly` en `hourly_units`; eenheden `kn` en `°`; `time` als Unix-seconden bij `timeformat=unixtime` | live-call `latitude=52.47,52.10…models=knmi_harmonie_arome_netherlands,dwd_icon_seamless,ecmwf_ifs,ncep_gfs_seamless…` op 14-10-2026 |
| Limieten | 600/min, 5.000/uur, 10.000/dag, 300.000/maand; "more than 10 weather variables or … more than 2 weeks … are considered multiple API calls"; fractioneel | https://open-meteo.com/en/pricing |
| Gewicht | `calculateQueryWeight`: `max(1, max(v/10, d/14·v/10))` per locatie, met `v` = variabelen × domeinen | https://github.com/open-meteo/open-meteo/blob/main/Sources/App/Helper/Writer/ForecastApiResult.swift, https://github.com/open-meteo/open-meteo/issues/464 |
| `cell_selection` | "land finds a suitable grid-cell on land with similar elevation … sea prefers grid-cells on sea. nearest selects the nearest possible grid-cell." | https://open-meteo.com/en/docs |
| Licentie | CC BY 4.0. De bronvermelding in de app valt onder WP-13 en WP-14 | https://open-meteo.com/en/licence |

Geen API-sleutel, geen secrets, geen betaalde dienst.

## Risico's
- **R1. Gedeeld IP van GitHub Actions.** Open-Meteo telt de limieten per IP, en runners delen IP-adressen met andere gebruikers. Daardoor kan een 429 of een bereikte daglimiet optreden die niet van ons komt. Mitigatie: retries, een fout per chunk in `errors` (WP-11 meldt dat), en de stale-regel van WP-11 (alerts overslaan bij forecasts ouder dan 3 uur). Er is geen gratis alternatief; een API-sleutel kost geld en valt buiten de randvoorwaarden.
- **R2. Model-id's of de naamgeving veranderen.** De website gebruikt nu de namen met prefix; de oude namen werken (nog) ook. Gaat er een id weg, dan geeft Open-Meteo een 400 met reason. Die komt in `errors`, en de verifier ziet het in AC-8. De mapping staat op één plek.
- **R3. `cell_selection=sea` kiest bij meren de verkeerde cel**, bijvoorbeeld bij grove modellen zoals GFS 0,25°. Dat is een keuze voor Lars (A2). Na de M1-testweek kan Lars dit per regio heroverwegen; een per-spot-instelling valt buiten scope.
- **R4. Verouderde rijen (A8)** kunnen even een oude voorspelling tonen als een model data voor een uur niet meer levert. WP-10 kan op `fetched_at` filteren.
- **R5. Het gewicht wordt onderschat bij retries (A5).** Begrensd door de marge van 20%.
- **R6. Race op `api_usage` (A9)** bij gelijktijdige handmatige runs. Beperkt tot één verloren boeking.
- **R7. De fixture veroudert.** Tests hangen niet af van de huidige datum, en `test_fixture_matches_current_params` dwingt een nieuwe capture af als de parameters veranderen.
- **R8. Een structuurfout in de respons laat de hele chunk falen**, dus met 25 spots in één chunk alle spots. Dat is bewust: liever geen data dan verkeerd toegewezen data. Het wordt zichtbaar via `errors` en de operatormelding van WP-11.
- **R9. Niet-commercieel gebruik.** Het open punt uit het plan (mail aan Open-Meteo) loopt via WP-22 en verandert niets aan deze WP.

## Buiten scope
- Golven en de Marine API (WP-12).
- Evaluatie, consensus en betrouwbaarheid (WP-05).
- Scheduling, `ingest_runs`, operatormeldingen en de stale-regel (WP-11).
- Een atomaire increment-RPC voor `api_usage` (A9).
- Instellingen per spot voor `cell_selection` of het model.
- Het generieke `with_retries` (WP-22).
- Spotdata in `data/spots.yaml` (WP-02 en Lars).
- Vervangsemantiek voor verouderde rijen (A8).
- Wijzigingen in `shakka.db`, `FakeSupabase` of het schema.
- Bronvermelding in de UI (WP-13 en WP-14).

## Stappenplan voor de builder
Werk op branch `wp/WP-03` in de worktree `/Users/larst/Dev/Shakka/.claude/worktrees/WP-03`. Lees of print `.env` nooit. Na elke stap: `cd ingest && uv run pytest && uv run ruff check . && uv run ruff format --check .` (groen). Eén commit per stap, commitberichten in het Engels.

1. **Domeintypes, eerst de tests.**
   - Schrijf `tests/test_domain_forecast.py`. Rood.
   - Maak `src/shakka/domain/forecast.py` volgens het contract. Groen, ook `test_domain_purity.py`.

   Commit: `feat(domain): add forecast value types`.
2. **Fixture vastleggen.** Maak `tests/fixtures/openmeteo/` aan en draai het `curl`-commando uit het Testplan vanuit de repo-root. Laat het bestand onbewerkt. Controleer handmatig dat het een lijst van 2 objecten is en dat de KNMI-arrays `null` bevatten.

   Commit: `test(ingest): add recorded Open-Meteo multi-model fixture`.
3. **Parameters en parser, eerst de tests.**
   - Schrijf `tests/openmeteo_payloads.py` en `tests/test_openmeteo_forecast.py` (AC-1, AC-2 en E3 tot en met E18). Rood.
   - Maak `src/shakka/openmeteo/__init__.py`, `models.py` en `forecast.py` (constanten, fouttypes, `build_forecast_params`, `parse_forecast_response`; `fetch_forecast` nog niet). Groen.

   Commit: `feat(openmeteo): add forecast params builder and parser`.
4. **Request met retries en de fetch, eerst de tests.**
   - Schrijf `tests/test_openmeteo_client.py`, plus een test `test_fetch_forecast_parses_mocked_response` en `test_fetch_forecast_empty_locations_no_request` in `test_openmeteo_forecast.py`. Rood.
   - Maak `src/shakka/openmeteo/client.py` en voeg `fetch_forecast` toe. Groen.

   Commit: `feat(openmeteo): add request helper with retries and fetch_forecast`.
5. **Budget, eerst de tests.**
   - Schrijf `tests/test_budget.py` (AC-3 en het guard-deel van AC-4). Rood.
   - Maak `src/shakka/budget.py`. Groen.

   Commit: `feat(ingest): add Open-Meteo call weight estimate and budget guard`.
6. **Job, eerst de tests.**
   - Schrijf `tests/test_job_forecast.py` (job-deel van AC-4, AC-5, job-deel van AC-6, E1, E2 en E19 tot en met E31). Rood.
   - Maak `src/shakka/jobs/__init__.py` en `src/shakka/jobs/forecast.py`, zonder CLI-glue. Groen.

   Commit: `feat(jobs): add forecast ingest job with cleanup`.
7. **CLI, eerst de tests.**
   - Schrijf `tests/test_cli_forecast.py`. Rood.
   - Voeg `run_forecast_cli`, `_open_resources` en `_utcnow` toe aan `jobs/forecast.py`, en de groep `forecast` aan `cli.py`. Groen. Controleer dat `uv run shakka forecast --help` en `uv run shakka forecast fetch --help` exit 0 geven.

   Commit: `feat(cli): add shakka forecast fetch`.
8. **Isolatie.**
   - Schrijf `tests/test_openmeteo_isolation.py`.
   - Draai letterlijk `grep -rn "open-meteo.com" ingest/src`: alleen treffers onder `ingest/src/shakka/openmeteo/`.
   - Draai `grep -rn "httpx.Client(" ingest/src`: alleen `shakka/http.py`.

   Commit: `test(ingest): guard that Open-Meteo hosts stay in shakka.openmeteo`.
9. **RUNBOOK.** Voeg sectie `## 9. Forecast-ingest (vanaf WP-03)` toe, in het Nederlands, met:
   - `uv run shakka forecast fetch --dry-run` en `uv run shakka forecast fetch`, wat de uitvoer betekent en de exitcodes;
   - de budgetgrenzen (8.000 per dag en 240.000 per maand, 80% van de gratis limiet) en waar het verbruik staat (`api_usage`);
   - een lokale test met de stack: `supabase start`, `.env` tijdelijk naar de lokale stack (sectie 6), en de test-spot invoegen met `psql "<DB URL uit supabase status>" -c "insert into public.spots (id, name, lat, lon) values ('test-strand', 'Teststrand', 52.47, 4.57) on conflict (id) do nothing;"`. Controleer daarna met `select model, count(*) from public.forecast_hours group by model;`;
   - de fixture opnieuw vastleggen: het `curl`-commando, en dat de capture-URL in `test_openmeteo_forecast.py` mee moet;
   - de gekozen modellen en `cell_selection=sea` in één zin, met een verwijzing naar deze blueprint.

   Commit: `docs: document forecast ingest and fixture refresh`.
10. **Eindcontrole.**
    - `cd ingest && uv sync && uv run pytest && uv run ruff check . && uv run ruff format --check .`
    - De greps uit stap 8, en `git grep --untracked -nE "sb_(secret|publishable)_[A-Za-z0-9_-]{20,}|eyJhbGciOi" -- . ':!docs'`: geen treffers.
    - Als Docker beschikbaar is: AC-8 volgens RUNBOOK 9 tegen de lokale stack (twee runs). Zonder Docker noteert de builder dat in `deviations.md` als niet-ontwerpraakbaar; de verifier doet AC-8 dan.
    - Push `wp/WP-03` alleen met uitdrukkelijke toestemming van de orchestrator.
