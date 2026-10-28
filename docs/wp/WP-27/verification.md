# Verificatie WP-27, ronde 1
Resultaat: PASS

Volledige suite: `cd ingest && uv run pytest` geeft 1789 passed, 24 skipped (alle skips zijn de lokale Supabase-pariteitstests die `SHAKKA_TEST_SUPABASE_URL` vereisen). `uv run ruff check .` geeft "All checks passed", `uv run ruff format --check .` geeft "137 files already formatted". De test-subset voor deze WP (job_tides, usage, job_usage, cli, domain_purity, pipeline, config) geeft 276 passed.

| Criterium | Resultaat | Bewijs |
|---|---|---|
| AC-1 | PASS | `test_rws_usage_booked_per_request` (3 stations, 1 faalt: `requests == 3`, `calls == 3`, dag 2026-10-14, bron `rws`). `test_rws_usage_nothing_when_all_fresh` (alles overgeslagen: geen `api_usage`-rij, geen upsert). Extra: bestaande dagrij (2+3=5), budgetstop telt niet mee, ongeldige code boekt niets, mislukte boeking is niet fataal. De broncode boekt na de lus `BudgetGuard.record(SOURCE_RWS, n, requests=n)` alleen bij `n > 0`. |
| AC-2 | PASS | `test_budget_after_one_station_serves_oldest` (nep-fetch die na één station `TideBudgetExhausted` gooit: station `c` zonder rijen wordt opgehaald, `a`, `b`, `d` falen). `test_stations_ordered_oldest_first` (volgorde c, d, a, b). `test_station_order_tie_alphabetical`. `test_tide_budget_fetches_oldest_first` in `test_pipeline.py` toetst het via `step_tides` met een nep-klok. |
| AC-3 | PASS | `tests/test_usage.py`: GOLDEN bevat `Rijkswaterstaat (7 dagen): 12 requests` en bij `None` `Rijkswaterstaat (7 dagen): onbekend`. `test_rws_requests_thousands` (1.234). Validatietests voor -1, 1.5 en `True`. `tests/test_job_usage.py`: `test_read_rws_requests_sums_last_7_days` (som uit `api_usage`; buiten het venster en andere bron tellen niet mee), `test_report_contains_rws_line`, `test_rws_unreadable_on_monday`. De test op het stille uur bevestigt dat RWS dan niet gelezen wordt. |
| AC-4 | PASS | `tests/test_cli.py`: `test_doctor_lists_optional_unset` (alleen verplichte variabelen: exit 0, vijf namen met `unset`). `test_doctor_optional_set_without_values` (geen waarden in de uitvoer). `test_doctor_invalid_url_no_traceback[http://exa mple]` (exit 1, geen `Traceback`, geen secret, geen request). Ook groen: URL's met witruimte of niet-ASCII, sleutel met niet-ASCII of witruimte, `httpx.InvalidURL`, `UnicodeEncodeError`, en het lezen van settings. |
| AC-5 | PASS | `tests/test_domain_purity.py::test_checker_flags` bevat `Field(default_factory=datetime.now)` en `x = date.today`. `test_checker_allows` bevat `from datetime import datetime`, `stats.now` en `self.now`. `test_domain_package_is_pure` blijft groen op de echte `shakka.domain`. |
| AC-6 | PASS | Zie boven: pytest en ruff volledig groen. |

## Diff versus blueprint
De diff komt overeen met de bestandentabel van de blueprint (`tides.py`, `pipeline.py`, `domain/usage.py`, `jobs/usage.py`, `config.py`, `doctor.py`, de zeven testbestanden, `RUNBOOK.md`). Niet aangeraakt: migraties, `web/`, `openmeteo`, `forecast.py`, `marine.py`. Het enige buiten de tabel is de statuswijziging in `docs/STATUS.md` (`todo` naar `verifying`), en de WP-documenten zelf. `pipeline.py` heeft alleen de importregel en één `raise`. De twee afwijkingen (A2: één boeking per run, A7: `set`/`unset` in plaats van "gezet"/"niet gezet") staan in `deviations.md`. De test-toevoegingen die daar genoemd worden bestaan en zijn groen.

## Harde regels
- Geen secrets in de diff: gecontroleerd op sleutelpatronen, geen treffers. De tests gebruiken placeholders zoals `TESTAPPURL`.
- Geen client-side Open-Meteo: er zijn geen wijzigingen in `web/`.
- Geen scraping: geen nieuwe externe URL's of bronnen in de diff.
- Geen nieuwe betaalde dienst: er is geen nieuwe afhankelijkheid en er zijn geen `.github`- of migratiewijzigingen.
- Bronvermelding intact: de wijziging raakt geen web- of attributietekst. Het RWS-regelitem in het rapport en de RUNBOOK-tekst voegen niets weg.
- Offshore blijft `no_go`: de evaluatielogica is niet gewijzigd.
- `doctor` toont geen waarden, URL's of exceptieberichten, alleen de namen en `type(exc).__name__`.

## Problemen
Geen blokkerende problemen.

N-1 (niet-blokkerend): `deviations.md` en blueprint A7 beroepen zich op een bevestiging van Lars voor `set`/`unset`. Die is niet in de repo na te lezen. Lars kan dit bij de PR bevestigen. De tests toetsen de Engelse woorden exact.
