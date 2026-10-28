# Blueprint WP-27: Ingest-hygiëne: RWS-verbruik, stationvolgorde, `doctor`, puurheidscheck
Status: DRAFT
Revisie: 1

## Doel
Vier losse eindjes in `/ingest` dichten (WORK_PACKAGES_V2, WP-27):
1. het aantal RWS-requests komt in `api_usage` (bron `rws`) en als één regel in het gebruiksrapport van WP-22;
2. de getijjob ververst bij een krap tijdsbudget eerst de stations met de oudste data;
3. `shakka doctor` meldt welke optionele variabelen gezet zijn en crasht niet meer op een ongeldige URL of sleutel;
4. de puurheidscheck van `shakka.domain` vangt ook `datetime.now`, `date.today` en dergelijke zonder aanroep.

## Aannames
- **A1. Stand WP-22 en WP-23.** Beide zijn `done` en gemerged in `develop`. De punten die WORK_PACKAGES_V2 ("Uitgangspunten") eventueel naar WP-27 zou verplaatsen, zijn in WP-22 gebouwd: veroudering per spot (A11, `MAX_FETCH_AGE` in `jobs/inputs.py`), de bovengrens voor `starts_at` (A13) en open aanmelden (A14). Er komt dus niets extra in deze WP.
- **A2. Eén boeking per run.** De WP zegt "per request één boeking". Ik lees dat als "elke request telt mee". De job boekt na de stationslus één keer de som: `calls = requests = n`. Dat geeft dezelfde totalen als AC-1, met één database-roundtrip in plaats van n.
- **A3. Wat is één request.** Eén request is één aanroep van `fetch(station, start, end)`. De retries binnen `_post_json` (hoogstens 3, WP-22) tellen niet apart: de fetch-interface geeft het aantal pogingen niet door, en RWS publiceert geen limiet. Een mislukte fetch telt wel mee, zoals AC-1 vraagt.
- **A4. Budgetstop telt niet mee.** Als het tijdsbudget van de pipeline op is, gooit de begrensde fetch een exceptie voordat er een request is verstuurd. Die stations tellen niet mee. Dit wordt herkenbaar via een eigen exceptieklasse (zie Ontwerp).
- **A5. Venster "7 dagen".** Dat zijn de UTC-dagen `[vandaag − 6, vandaag]`, net als bij "hoogste dag" van Open-Meteo (WP-22).
- **A6. Wanneer RWS gelezen wordt.** Het RWS-verbruik wordt alleen gelezen als het rapport gebouwd wordt (maandagrapport en `shakka usage show`), niet elk uur. Er is geen drempel, dus elk uur lezen heeft geen zin.
- **A7. Uitvoertaal `doctor`. Lars bevestigt.** AC-4 noemt "gezet" en "niet gezet". De uitvoer van `doctor` is Engels, en de bestaande optionele regel heet al `unset   SUPABASE_PUBLISHABLE_KEY (optional)`. Ik gebruik daarom `set` en `unset` met de suffix `(optional)`. De tests toetsen die Engelse woorden.
- **A8. Strengere URL-validatie.** `SUPABASE_URL` met een niet-ASCII-teken, witruimte of een stuurteken wordt al in `Settings` geweigerd. Dat geldt voor alle commando's, maar het weigert alleen URL's die toch nooit werken. Een Supabase-URL is altijd ASCII.
- **A9. Mislukte boeking is niet fataal.** De getijdata zijn dan al opgeslagen. De fout komt in `errors` en in de log, en de stapstatus verandert niet.
- **A10. Variabelen van WP-24.** WP-24 is nog `todo`, dus WP-24 voegt zijn eigen variabelen zelf toe aan `OPTIONAL_ENV_VARS` (WP-27, "Buiten scope").

## Ontwerp
**RWS-verbruik.** `run_tide_ingest` telt de fetch-aanroepen. Een aanroep die `TideBudgetExhausted` gooit, telt niet mee (A4). Na de stationslus en vóór `delete_old_tides` volgt één boeking via de bestaande `BudgetGuard(db).record(SOURCE_RWS, float(n), now=now, requests=n)`, alleen als `n > 0`. `BudgetGuard` en de CHECK op `api_usage.source` kennen `rws` al (WP-01, WP-03). De Open-Meteo-guard en `read_open_meteo_usage` filteren op het prefix `open_meteo_`, dus RWS telt daar niet mee. Een `DatabaseError` bij het boeken wordt opgevangen (A9). Zowel de pipeline als `shakka tides fetch` boeken, omdat ze allebei `run_tide_ingest` gebruiken.

**Budgetstop herkenbaar.** De pipeline (`step_tides.bounded_fetch`) gooit nu `TideBudgetExhausted` in plaats van een kale `TimeoutError`. De klasse erft van `TimeoutError` en staat in `shakka.jobs.tides`. De melding blijft gelijk. De fouttekst in `counts.errors` wordt daardoor `"<station>: TideBudgetExhausted: tide step time budget of 240 s reached"`. Dat is de enige wijziging in `pipeline.py`.

**Stationvolgorde.** De select op verse stations (`fetched_at > now − 20 h`) wordt vervangen door één select van `station,fetched_at` voor alle geldige stations, zonder filter op `fetched_at`. Het pagineren gaat al via `SupabaseRest.select`; het gaat om ongeveer 40 rijen per station. Per station is `last` de hoogste `fetched_at`. Dat is equivalent aan de oude regel: vers betekent `last > now − TIDE_REFRESH_AFTER`, strikt. De volgorde van ophalen is `sorted(..., key=(heeft_rijen, last, code))`: nooit opgehaalde stations eerst, dan de oudste `last`, en bij gelijke stand alfabetisch. `force=True` slaat niets over, maar houdt dezelfde volgorde. PostgREST-aggregaten (`max()`) gebruik ik niet, want die staan bij Supabase standaard uit.

**Gebruiksrapport.** `UsageStats` krijgt `rws_requests_7d`. `build_usage_report` zet direct na de Open-Meteo-regel de regel `Rijkswaterstaat (7 dagen): <n> requests`, of `onbekend`. Het getal wordt geformatteerd met `_n` (1.234). Er is geen waarschuwing, en de pushtekst verandert niet. In `jobs/usage.py` leest `read_rws_requests` de som. Een nieuwe helper `_report_fields` bundelt de "alleen voor het rapport"-bronnen (run-historie en RWS), zodat `collect_usage_stats(with_history=True)` en de maandagtak van `run_usage_report` dezelfde code gebruiken.

**`doctor`.** Er komen drie wijzigingen:
1. Per naam in de nieuwe `config.OPTIONAL_ENV_VARS` een regel `set` of `unset`, zonder waarde. De exitcode verandert daardoor niet.
2. De geheime sleutel wordt vóór het request getoetst. Bevat hij een niet-ASCII-teken, witruimte of een stuurteken, dan volgt één `invalid`-regel, geen request, en exitcode 1.
3. Er komt een laatste vangnet `except Exception` rond het request en rond `get_settings()`. Dat toont alleen de exceptieklasse. Daarmee is WP-00 review N-4 opgelost: `httpx.InvalidURL` erft niet van `httpx.HTTPError` (geverifieerd, zie Externe afhankelijkheden).

Een URL met witruimte of een niet-ASCII-teken komt niet meer bij httpx, want `Settings` weigert hem al (A8).

**Puurheidscheck.** Er komt één extra AST-regel. Een `ast.Attribute` met `attr` in `{"now", "today"}` is een overtreding als de ontvanger de klasse `datetime` of `date` is:
- de namen `datetime` en `date`, plus hun aliassen uit `from datetime import datetime as X` of `date as Y`;
- de vorm `<module>.datetime` of `<module>.date`, waarbij `<module>` `datetime` is of een alias uit `import datetime as M`.

Een attribuut dat al de `func` van een `Call` is, wordt overgeslagen, want dat meldt de bestaande call-regel al. Daarnaast is `getattr(<x>, "now" | "today" | "utcnow")` met een stringconstante een overtreding. De bestaande regels voor `utcnow` en `time.time` blijven ongewijzigd. `stats.now` en `self.now` (in `domain/usage.py`) blijven toegestaan, omdat de ontvanger geen datetime-naam is.

## Bestanden
| Bestand | Actie | Inhoud |
|---|---|---|
| `ingest/src/shakka/jobs/tides.py` | wijzigen | `TideBudgetExhausted`, re-export `SOURCE_RWS`, `_parse_fetched_at`, stationvolgorde, telling en boeking. `TIDE_RETENTION` blijft letterlijk staan. |
| `ingest/src/shakka/pipeline.py` | wijzigen | `bounded_fetch` gooit `TideBudgetExhausted` (import uit `shakka.jobs.tides`). |
| `ingest/src/shakka/domain/usage.py` | wijzigen | Veld `rws_requests_7d`, validatie, rapportregel. |
| `ingest/src/shakka/jobs/usage.py` | wijzigen | `read_rws_requests`, `_report_fields`, gebruik in `collect_usage_stats` en `run_usage_report`, sleutel in `usage_stats_json`. |
| `ingest/src/shakka/config.py` | wijzigen | `OPTIONAL_ENV_VARS`; URL-validator weigert niet-ASCII, witruimte en stuurtekens. |
| `ingest/src/shakka/doctor.py` | wijzigen | Optionele regels, sleutelcheck, vangnetten. Docstring bijwerken. |
| `ingest/tests/test_job_tides.py` | wijzigen | Tests voor AC-1 en AC-2. |
| `ingest/tests/test_pipeline.py` | wijzigen | Fouttekst in `test_tide_budget_stops_fetching`, nieuwe volgordetest, en `test_marine_step_ok_counts` alleen als daar `rws` verschijnt. |
| `ingest/tests/test_usage.py` | wijzigen | Golden-teksten en validatie (AC-3). |
| `ingest/tests/test_job_usage.py` | wijzigen | Lezer en rapport-integratie (AC-3). |
| `ingest/tests/test_pipeline_usage.py` | wijzigen | Alleen als het de sleutels van `stats` exact toetst: `rws_requests_7d` erbij. |
| `ingest/tests/test_cli.py` | wijzigen | Tests voor `doctor` (AC-4). |
| `ingest/tests/test_config.py` | wijzigen | URL-gevallen en de koppeling `OPTIONAL_ENV_VARS` ↔ `Settings`. |
| `ingest/tests/test_domain_purity.py` | wijzigen | Nieuwe regel plus flag- en allow-gevallen (AC-5). |
| `docs/RUNBOOK.md` | wijzigen | §3 (doctor-regels), §10 (volgorde en `api_usage` `rws`), §18.1 (RWS-regel in het rapport). |

Niet gewijzigd: migraties, `web/`, `shakka.openmeteo`, `jobs/forecast.py` en `jobs/marine.py`. Die raakt WP-26.

## Interfaces en contracten

### `shakka.jobs.tides`
```python
from shakka.budget import SOURCE_RWS, BudgetGuard  # SOURCE_RWS == "rws"; re-export, no second definition
from shakka.db import DatabaseError, SupabaseRest, in_filter, iso_utc
from shakka.jobs.inputs import db_error_summary

class TideBudgetExhausted(TimeoutError):
    """Raised by a bounded fetch before any request is sent. Not counted in api_usage."""

def _parse_fetched_at(value: object) -> datetime | None:
    """Aware datetime -> UTC; ISO string with offset -> UTC; anything else (naive, unparsable) -> None."""

def run_tide_ingest(
    db: SupabaseRest,
    *,
    now: datetime,
    force: bool = False,
    fetch: TideFetcher = fetch_tide_extremes,
) -> TideIngestResult: ...   # signature and TideIngestResult unchanged
```
Gedrag van `run_tide_ingest`, in deze volgorde:
1. Spots lezen en ongeldige codes afhandelen: ongewijzigd.
2. Als er geldige stations zijn: `db.select("tide_extremes", columns="station,fetched_at", filters={"station": in_filter(stations)})`. Per station is `last[station]` de hoogste `_parse_fetched_at`. Rijen met `None` tellen niet mee. Zonder geldige stations is er geen select.
3. `fresh = set()` als `force`, anders `{s for s in stations if s in last and last[s] > now - TIDE_REFRESH_AFTER}`. `skipped = sorted(fresh)`.
4. Volgorde: `todo = sorted((s for s in stations if s not in fresh), key=lambda s: (s in last, last.get(s, now), s))`.
5. Per station in `todo`:
   - `TideBudgetExhausted` telt niet als request, maar het station komt wel in `failed`/`errors` met het bestaande formaat;
   - elke andere afloop van `fetch` (ok of exceptie) geeft `requests += 1`;
   - de rest van de stationsverwerking is ongewijzigd.
6. Als `requests > 0`: `BudgetGuard(db).record(SOURCE_RWS, float(requests), now=now, requests=requests)`. Bij een `DatabaseError`:
   - `errors.append(f"api_usage: {db_error_summary(exc)}")`;
   - `logger.warning("tides: api_usage booking failed (%s)", db_error_summary(exc))`;
   - `failed` verandert niet.
7. `delete_old_tides` en de logregel. In de logregel komt `requests %d` bij.

### `shakka.pipeline.step_tides`
`bounded_fetch` gooit `TideBudgetExhausted(f"tide step time budget of {budget_s:.0f} s reached")`. Verder ongewijzigd, ook `budget_skipped` en de warningtekst.

### `shakka.domain.usage`
```python
@dataclass(frozen=True, slots=True)
class UsageStats:
    ...                                # existing fields unchanged, in the same order
    rws_requests_7d: int | None = None  # sum of api_usage.requests, source rws, UTC days [today-6, today]
```
- `__post_init__`: `rws_requests_7d` gaat door `_check_number(..., integer=True)`.
- `build_usage_report`: direct na de regel `Open-Meteo: …` (of `Open-Meteo: onbekend`) komt:
  - `f"Rijkswaterstaat ({REPORT_DAYS} dagen): {_n(n)} requests"`, of
  - `f"Rijkswaterstaat ({REPORT_DAYS} dagen): {UNKNOWN}"` bij `None`.
- `usage_warnings`, `usage_push_text` en `warning_push_text`: ongewijzigd.

### `shakka.jobs.usage`
```python
from shakka.budget import OPEN_METEO_PREFIX, SOURCE_RWS

def read_rws_requests(db: SupabaseRest, *, now: datetime) -> int:
    """Sum of api_usage.requests for source rws over the UTC days [today - 6, today]."""
    # db.select("api_usage", columns="day,requests",
    #           filters={"source": f"eq.{SOURCE_RWS}",
    #                    "day": [f"gte.{week_first.isoformat()}", f"lte.{today.isoformat()}"]})

def _report_fields(db: SupabaseRest, *, now: datetime, errors: list[str]) -> dict[str, Any]:
    """Fields only needed for the full report: run history (runs_*, step_issues, push_*) and
    rws_requests_7d. A source that fails is left out and adds an error."""
```
- Volgorde en fouttekst:
  - eerst `read_run_history`; bij een `DatabaseError` `"ingest_runs: <summary>"`, zoals nu;
  - dan `read_rws_requests`; bij een `DatabaseError` `"api_usage (rws): <summary>"`.
- `collect_usage_stats(..., with_history=True)` gebruikt `fields.update(_report_fields(...))`.
- `run_usage_report` (maandagtak) gebruikt `stats = replace(stats, **_report_fields(...))`.
- `usage_stats_json` krijgt de sleutel `"rws_requests_7d": stats.rws_requests_7d`.
- `UsageReportResult` en de stapcounts verder ongewijzigd.

### `shakka.config`
```python
OPTIONAL_ENV_VARS: Final[tuple[str, ...]] = (
    "APP_BASE_URL", "VAPID_PUBLIC_KEY", "VAPID_PRIVATE_KEY", "VAPID_SUBJECT", "OPERATOR_USER_ID",
)
```
- Elke `name.lower()` is een veld van `Settings`.
- `_validate_supabase_url` doet als eerste stap: `if not value.isascii() or any(c.isspace() or not c.isprintable() for c in value): raise ValueError(URL_ERROR)`. `URL_ERROR` blijft gelijk.

### `shakka.doctor.run_doctor(*, echo) -> int` (signatuur ongewijzigd)
Uitvoer in deze volgorde. Kolombreedte 8, zoals nu. `<T>` is `type(exc).__name__`.

| Situatie | Regel(s) | Exit |
|---|---|---|
| `get_settings()` gooit `ValidationError` | ongewijzigd | 1 |
| `get_settings()` gooit iets anders | `error   could not read settings (<T>)`, `doctor: failed` | 1 |
| altijd daarna | `ok      SUPABASE_URL` | |
| sleutel geldig | `ok      SUPABASE_SECRET_KEY` | |
| sleutel bevat niet-ASCII, witruimte of een stuurteken | `invalid SUPABASE_SECRET_KEY: contains non-ASCII, whitespace or control characters` | 1 |
| publishable | ongewijzigd (`ok …` of `unset   SUPABASE_PUBLISHABLE_KEY (optional)`) | |
| per naam in `OPTIONAL_ENV_VARS` | `set     <NAME> (optional)` of `unset   <NAME> (optional)` | geen invloed |
| prefixwaarschuwingen | ongewijzigd; die voor de secret key alleen bij een geldige sleutel | |
| sleutel ongeldig | `skip    Supabase REST check (configuration invalid)` | 1 |
| request: bestaande uitkomsten | ongewijzigd (HTTP-status, timeout, `unreachable (<T>)`) | |
| request: elke andere `Exception` | `error   Supabase REST check failed (<T>)` | 1 |
| slot | `doctor: ok` of `doctor: failed` | |

"Gezet" betekent: de waarde is niet `None` en na `strip()` niet leeg (`SecretStr` via `get_secret_value()`). Er komt nooit een waarde, URL, exceptiemelding of traceback in de uitvoer.

### `tests/test_domain_purity.py`
- `CLOCK_ATTRS = frozenset({"now", "today"})`.
- `GETATTR_CLOCK = frozenset({"now", "today", "utcnow"})`.
- Een overtreding is `Violation(path, line, "forbidden_call", "<owner>.<attr>")`, met `owner` `datetime` of `date` (de oorspronkelijke klassenaam, niet de alias). Voor `getattr` is het detail `getattr <attr>`.
- `check_source` behoudt zijn signatuur.

## Edge cases
- **E1.** Alle stations vers (20-uursregel) → er is geen fetch, en `api_usage` krijgt geen upsert.
- **E2.** Er wordt alleen een ongeldige stationscode gevonden → er is geen fetch en geen boeking.
- **E3.** Het budget is op vóór het eerste station → `requests = 0` en geen boeking. `budget_skipped` en `failed` blijven zoals nu.
- **E4.** Er staat al een `rws`-rij voor vandaag (`requests = 2`) → na 3 requests is `requests = 5` en `calls = 5.00`.
- **E5.** De boeking geeft een `DatabaseError` → de data is opgeslagen, `errors` bevat `api_usage: DatabaseError (HTTP 500)`, en `failed` en de stapstatus zijn ongewijzigd.
- **E6.** Een station heeft rijen met `fetched_at` 50 h en 21 h geleden → `last` is 21 h, dus het komt na een station met `last` 22 h.
- **E7.** `fetched_at` komt als ISO-string (PostgREST) of als datetime (fake) → beide werken. Bij een naïeve of onleesbare waarde telt die rij niet mee.
- **E8.** `force=True` met een vers station → het verse station komt als laatste. `skipped` is leeg.
- **E9.** Twee stations hebben exact dezelfde `last` → ze worden alfabetisch opgehaald.
- **E10.** `rws_requests_7d = 1234` → de rapportregel is `Rijkswaterstaat (7 dagen): 1.234 requests`.
- **E11.** Rijen van `rws` op vandaag − 7 en van `open_meteo_forecast` → die tellen niet mee in `read_rws_requests`.
- **E12.** Een uur dat geen maandag is → RWS wordt niet gelezen (A6). `test_quiet_hour_reads_little_and_writes_nothing` blijft groen.
- **E13.** De `api_usage`-select met `source=eq.rws` faalt op maandag → `errors` bevat `api_usage (rws): …`, de regel is `onbekend`, en de status is `partial`.
- **E14.** `SUPABASE_URL="http://exa mple"`, `"https://exa mple"` of `"https://tëst.supabase.co"` → `invalid SUPABASE_URL: …`, exit 1, geen request.
- **E15.** De sleutel is `sb_secret_tëst` of heeft een spatie of een `\n` aan het eind → de `invalid`-regel, geen request, exit 1, en de sleutel staat niet in de uitvoer.
- **E16.** De client gooit `httpx.InvalidURL` of `UnicodeEncodeError` → `error   Supabase REST check failed (InvalidURL)` of `(UnicodeEncodeError)`, exit 1.
- **E17.** `.env` is geen geldige UTF-8 → `error   could not read settings (UnicodeDecodeError)`, exit 1.
- **E18.** `VAPID_SUBJECT="   "` → `unset`. `VAPID_SUBJECT="mailto:"` (placeholder) → `set`. Of de VAPID-instellingen geldig zijn, controleert `doctor` niet (Buiten scope).
- **E19.** In de domeincode `def f(stats): return stats.now` → geen overtreding.
- **E20.** `import datetime as dt` en daarna `dt.datetime.now` als verwijzing → overtreding met `datetime.now`.

## Testplan
Fixtures: `FakeSupabase` (`tests/fakes.py`) en de helpers `make_db`, `seed_row` en `FakeFetch` in `test_job_tides.py`. Voeg daar een `BudgetFetch` toe: de eerste aanroep geeft `default_extremes`, elke volgende gooit `TideBudgetExhausted`. Verder `STATS_OK` en `GOLDEN` in `test_usage.py`, `usage_row` en `run` in `test_job_usage.py`, en `rec` en `env` in `test_cli.py`.

**AC-1** (`tests/test_job_tides.py`)
- `test_rws_usage_booked_per_request`: 3 stations, `vlissingen` gooit `TideFetchError`. De `api_usage`-rij (`2026-10-14`, `rws`) heeft `requests == 3` en `calls == 3`.
- `test_rws_usage_nothing_when_all_fresh`: 3 verse stations. `db.rows("api_usage") == []` en `("api_usage", "day,source") not in db.upserts` (E1).
- `test_rws_usage_adds_to_existing_day`: E4.
- `test_rws_usage_excludes_budget_exhausted`: `BudgetFetch` met 3 stations geeft `requests == 1` (E3, A4).
- `test_rws_usage_booking_failure_is_not_fatal`: een fake die `upsert` op `api_usage` laat falen (E5).

**AC-2** (`tests/test_job_tides.py`, `tests/test_pipeline.py`)
- `test_stations_ordered_oldest_first`:
  - stations `a` (30 h), `b` (25 h), `c` (zonder rijen) en `d` (40 h);
  - `[c[0] for c in fetch.calls] == ["c", "d", "a", "b"]`.
- `test_budget_after_one_station_serves_oldest`: `BudgetFetch` haalt alleen `c` op. In `failed` staan de andere drie, met `TideBudgetExhausted` in `errors`.
- `test_last_fetch_uses_newest_row` (E6), `test_station_order_tie_alphabetical` (E9), `test_force_keeps_order_fresh_last` (E8).
- `test_fetched_at_iso_string`: `seed_row` met `iso_utc(...)` als `fetched_at` geeft dezelfde volgorde en dezelfde versheid (E7).
- Bestaande tests (`test_fresh_station_skipped` met grens 19/20/21 h, `test_unique_nonempty_stations`) blijven ongewijzigd groen.
- `test_pipeline.py::test_tide_budget_fetches_oldest_first`:
  - met de nep-klok van `_tide_ctx`, `station-b` met een rij van 30 h oud en `station-a` met een rij van 25 h;
  - `calls == ["station-b"]`.
- `test_tide_budget_stops_fetching`: de verwachte fouttekst wordt `"station-b: TideBudgetExhausted: tide step time budget"`.

**AC-3** (`tests/test_usage.py`, `tests/test_job_usage.py`)
- `test_build_usage_report_golden`: `STATS_OK` krijgt `rws_requests_7d=12`. `GOLDEN` krijgt `Rijkswaterstaat (7 dagen): 12 requests` direct na de Open-Meteo-regel. Ook `test_build_usage_report_with_warnings_golden` gaat mee.
- `test_build_usage_report_unknown`: de regel `Rijkswaterstaat (7 dagen): onbekend`.
- `test_rws_requests_thousands` (E10). `test_usage_stats_validation` krijgt `rws_requests_7d` = `-1`, `1.5` en `True`, die elk `ValueError` geven.
- `test_read_rws_requests_sums_last_7_days`: rijen op `2026-07-14` (dag − 6), `2026-07-20` en `2026-07-13` (dag − 7), plus een `open_meteo_forecast`-rij. Op `MONDAY` geeft dat alleen de eerste twee (E11).
- `test_read_rws_requests_empty` geeft `0`.
- `test_collect_with_history_fills_rws`: `stats.rws_requests_7d` komt uit de geseede `requests`.
- `test_report_contains_rws_line`: `run(db, MONDAY, …)` geeft `result.report` met `Rijkswaterstaat (7 dagen): 3 requests`.
- `test_rws_unreadable_on_monday` (E13).
- `test_quiet_hour_reads_little_and_writes_nothing`: daarbij `db.selected.count("api_usage") == 1` (E12).

**AC-4** (`tests/test_cli.py`, `tests/test_config.py`)
- `test_doctor_lists_optional_unset`: alleen de verplichte variabelen. Exit 0, en voor elk van de vijf namen de regel `unset   <NAME> (optional)`.
- `test_doctor_optional_set_without_values`:
  - alle vijf gezet, met herkenbare waarden (`TESTAPPURL`, `TESTVAPIDPUB`, …);
  - de regels `set     <NAME> (optional)`, geen waarde in de uitvoer, exit 0.
- `test_doctor_invalid_url_no_traceback`:
  - parametrisatie over E14;
  - exit 1, `invalid SUPABASE_URL`, en `isinstance(result.exception, SystemExit)`. CliRunner vangt exceptions zelf, dus de exitcode alleen bewijst niets;
  - `"Traceback" not in out`, `SECRET not in out`, `"exa mple" not in out`, `r.requests == []`.
- `test_doctor_secret_key_unusable_characters` (E15).
- `test_doctor_unexpected_client_error`:
  - `rec(error=httpx.InvalidURL("bad testref"))` en `rec(error=UnicodeEncodeError("ascii", "x", 0, 1, "bad"))`;
  - de regel van E16, exit 1, `SystemExit`, en `testref` niet in de uitvoer.
- `test_doctor_settings_read_error`: `monkeypatch.setattr(shakka.doctor, "get_settings", raiser)` (E17).
- `test_config.py::test_supabase_url_validation`: er komen drie gevallen bij met `None` (E14), plus `"https://testref.supabase.co "` (een spatie aan het eind).
- `test_config.py::test_optional_env_vars_are_settings_fields`: toetst de koppeling `OPTIONAL_ENV_VARS` ↔ `Settings`.

**AC-5** (`tests/test_domain_purity.py`)
- `test_checker_flags` krijgt erbij:
  - `"from datetime import datetime\nfrom pydantic import Field\nx = Field(default_factory=datetime.now)\n"`;
  - `"x = date.today\n"`;
  - `"f = datetime.today\n"`;
  - `"from datetime import datetime as dt\nf = dt.now\n"`;
  - `"from datetime import date as d\nf = d.today\n"`;
  - `"import datetime\nf = datetime.datetime.now\n"`;
  - `"import datetime as m\nf = m.date.today\n"`;
  - `"f = getattr(datetime, 'now')\n"`.
- `test_checker_allows` krijgt erbij:
  - `"from datetime import datetime\n"`;
  - `"def f(stats):\n    return stats.now\n"`;
  - `"def f(self):\n    return self.now.tzinfo\n"`;
  - `"def f(x, name):\n    return getattr(x, name)\n"`.
- `test_checker_reports_reference_once`: `"x = datetime.now()\n"` geeft precies één overtreding.
- `test_domain_package_is_pure` blijft groen.

**AC-6:** `cd ingest && uv run pytest` en `uv run ruff check . && uv run ruff format --check .` zijn volledig groen.

## Externe afhankelijkheden
Geen nieuwe packages, geen nieuwe endpoints. RWS DDAPI20 (`OphalenWaarnemingen`) is ongewijzigd en overgenomen uit WP-04 en WP-22.
- httpx 0.28.1 (`ingest/uv.lock`). Exceptiehiërarchie: `InvalidURL` staat naast `HTTPError`, niet eronder. **Zelf gecontroleerd:** https://www.python-httpx.org/exceptions/. Dat `UnicodeEncodeError` bij een niet-ASCII-headerwaarde ontstaat, staat daar niet. Ik neem het over uit WP-00 review N-4. De sleutelcheck voorkomt het vooraf, en het vangnet dekt het hoe dan ook.
- PostgREST-aggregaten staan standaard uit bij Supabase. Ik gebruik ze daarom niet; er is geen bron nodig.

## Risico's
- **R1.** `web/test/retention-consistency.test.ts` (WP-23) leest `TIDE_RETENTION: Final = timedelta(hours=48)` met een regex uit `jobs/tides.py`. Laat die regel letterlijk staan.
- **R2.** CliRunner vangt exceptions zelf, met exitcode 1 en zonder traceback in `output`. Een doctortest die alleen de exitcode toetst, mist dus een crash. Toets `SystemExit` en de verwachte foutregel.
- **R3.** `BudgetGuard.record` doet read-modify-write en is niet atomair. Dat is hetzelfde risico als bij Open-Meteo. De workflow draait als één run tegelijk (WP-11).
- **R4.** WP-26 loopt parallel. Gedeeld is alleen `docs/RUNBOOK.md`, in andere secties (§9 tegenover §3, §10 en §18). Als `test_budget.py` of `test_pipeline.py` bij beide wijzigen, is dat een tekstueel triviaal mergeconflict.
- **R5.** De select op `tide_extremes` zonder filter op `fetched_at` leest ongeveer 40 rijen per station in plaats van alleen de verse. Bij 25 stations zijn dat ongeveer 1.000 rijen, in één of twee pagina's. Dat is verwaarloosbaar.

## Buiten scope
- Een limiet, drempel of push voor RWS. Ook het tellen van retries per HTTP-poging (A3).
- Of de VAPID-instellingen geldig zijn, en een waarschuwing bij een half gezette VAPID-set. `doctor` meldt alleen `set` of `unset`.
- Variabelen van WP-24 (A10).
- RWS-retries (WP-22), Open-Meteo, en het alertformulier (WP-26).

## Gevolgen voor latere WP's
- **WP-24:**
  - voegt zijn variabelen toe aan `config.OPTIONAL_ENV_VARS`, als `Settings`-velden, zodat `test_optional_env_vars_are_settings_fields` groen blijft;
  - zet zijn rapportregel ná `Rijkswaterstaat (7 dagen): …` in `build_usage_report` en `GOLDEN`;
  - leest extra rapportbronnen via `_report_fields`.
- **Wie een nieuwe bron in `api_usage` boekt:** bron toevoegen aan de CHECK (migratie) en aan `budget.API_USAGE_SOURCES`. Telt de bron niet mee voor Open-Meteo, dan géén prefix `open_meteo_`.
- **Wie de tijdsbudgetlogica in `step_tides` wijzigt:** blijf `TideBudgetExhausted` gooien. Anders telt de budgetstop als RWS-request.

## Stappenplan voor de builder
1. **Puurheidscheck.**
   - Voeg de regels (`CLOCK_ATTRS`, aliasverzameling, `getattr`) en de flag- en allow-gevallen van AC-5 toe aan `test_domain_purity.py`.
   - Draai `uv run pytest tests/test_domain_purity.py`.
2. **Config.**
   - `OPTIONAL_ENV_VARS` en de strengere URL-validator.
   - Draai `test_config.py`.
3. **Doctor.**
   - Optionele regels, sleutelcheck, de twee vangnetten en de docstring.
   - Tests van AC-4 in `test_cli.py`. Draai `test_cli.py`.
4. **Budgetstop.**
   - `TideBudgetExhausted` in `jobs/tides.py`, gebruikt in `pipeline.step_tides`.
   - Pas de fouttekst aan in `test_tide_budget_stops_fetching`. Draai `test_pipeline.py` en `test_job_tides.py`.
5. **Stationvolgorde.**
   - `_parse_fetched_at`, de select op `last` en de sortering.
   - Tests van AC-2, waaronder `test_tide_budget_fetches_oldest_first`. Draai `test_job_tides.py` en `test_pipeline.py`.
6. **RWS-boeking.**
   - Telling en boeking in `run_tide_ingest`, plus de logregel.
   - Tests van AC-1.
   - Draai de volledige `uv run pytest`. Let op `test_cli_tides.py`, en op `test_marine_step_ok_counts`, als daar een `rws`-rij ontstaat.
7. **Gebruiksrapport.**
   - Veld en regel in `domain/usage.py`, en de golden-teksten.
   - `read_rws_requests`, `_report_fields` en `usage_stats_json` in `jobs/usage.py`.
   - Tests van AC-3, plus `test_pipeline_usage.py` als dat nodig is.
   - Draai `test_usage.py`, `test_job_usage.py` en `test_pipeline_usage.py`.
8. **RUNBOOK.**
   - §3: de regels `set`/`unset … (optional)`, `invalid SUPABASE_SECRET_KEY`, `REST check failed (<type>)` en `could not read settings`.
   - §10: de volgorde "oudste eerst", en de boeking onder `api_usage` `rws` (requests, geen limiet).
   - §18.1: de rapportregel "Rijkswaterstaat (7 dagen)".
9. **Afronding.** Draai `cd ingest && uv run pytest && uv run ruff check . && uv run ruff format --check .` (AC-6).
