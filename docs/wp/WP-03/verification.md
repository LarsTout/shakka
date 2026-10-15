# Verificatie WP-03, ronde 1
Resultaat: NEEDS_LARS

Alle acceptatiecriteria behalve AC-8 zijn aantoonbaar gehaald. AC-8 vraagt twee echte runs tegen de lokale Supabase-stack en echte Open-Meteo-requests. Docker is vanuit de verificatiesandbox niet bereikbaar, dus AC-8 is niet uitvoerbaar. Dat is geen fail.

Uitgevoerd op `wp/WP-03` (HEAD `32625db`, gelijk aan `origin/wp/WP-03`).

- `cd ingest && uv run pytest`: 382 passed, 23 skipped. De skips zijn `tests/test_fake_parity.py` en vragen `SHAKKA_TEST_SUPABASE_URL` en `SHAKKA_TEST_SUPABASE_SECRET_KEY`. Dat is de bestaande WP-01-pariteitstest tegen de lokale stack.
- `uv run ruff check .`: All checks passed. `uv run ruff format --check .`: 36 files already formatted.
- CI-run 38633485021 van deze branch: `ingest` success, `db` success.

| Criterium | Resultaat | Bewijs |
|---|---|---|
| AC-1 | PASS | `tests/test_openmeteo_forecast.py`: `test_fixture_all_valid_at_utc`, `test_fixture_values_match_raw_json` (alle rijen tegen de ruwe JSON, met onafhankelijke opschoonhelper), `test_fixture_sample_per_model[knmi/icon/ecmwf/gfs]` (indexen 0, 12 en 24, dus minstens 3 waarden per model), `test_fixture_no_all_none_rows`, `test_parse_partial_null_is_none`. Mutatiecontrole in een tijdelijke kopie: `None` omzetten naar `0` laat een test falen, en het weglaten van de alle-drie-leeg-filter ook. |
| AC-2 | PASS | `test_build_params_exact` (`wind_speed_unit=kn`, de drie `hourly`-variabelen, vier model-id's uit `OPEN_METEO_MODELS`, `forecast_days=7`, `timezone=GMT`, `timeformat=unixtime`), `test_models_mapping`, `test_parse_rejects_non_knots` (3 varianten), `test_fixture_matches_current_params`. Mutatie: de eenhedencontrole uitzetten laat een test falen. Model-id's in code: `knmi_harmonie_arome_netherlands`, `dwd_icon_seamless`, `ecmwf_ifs`, `ncep_gfs_seamless`. Die komen overeen met de fixture. |
| AC-3 | PASS | `tests/test_budget.py`: `test_weight_single` (1,0), `test_weight_multi_model` (>= 1,2), `test_weight_scales_with_locations` (25x), `test_weight_long_range` (>= 1,5). Allemaal groen. |
| AC-4 | PASS | `test_can_spend_daily_exceeded`, `test_can_spend_monthly_exceeded`, `test_can_spend_boundary_inclusive`, `test_job_budget_exceeded_no_request` en `test_job_monthly_budget_exceeded_no_request` (MockTransport: 0 calls, `skipped_budget=True`), `test_job_budget_stops_mid_run`, `test_job_records_usage_after_success` (gewicht onder `open_meteo_forecast`). Mutaties: dag- of maandcontrole uitzetten laat een test falen. Boeken weglaten laat een test falen. De limieten zijn 8000 en 240000 (`test_limits_are_80_percent`). |
| AC-5 | PASS | `test_job_skips_spots_without_coordinates`, `test_job_upsert_on_conflict` (`spot_id,model,valid_at`), `test_delete_old_forecasts_only_older_than_48h`, `test_delete_old_forecasts_boundary`, `test_job_is_idempotent`. Mutaties: `on_conflict` wijzigen, de coördinatencontrole weghalen en de retentie naar 24 uur zetten laten elk een test falen. Het schema (`forecast_hours`, primary key `(spot_id, model, valid_at)`) uit WP-01 sluit aan bij de upsert. |
| AC-6 | PASS | `test_job_429_then_200_succeeds`, `test_job_three_500_reports_error` (geen exception, `errors` gevuld), `test_request_429_then_200`, `test_request_three_500_raises`. |
| AC-7 | PASS | `grep -rn "open-meteo.com" ingest/src` geeft alleen treffers in `ingest/src/shakka/openmeteo/` (`forecast.py:16` en `__init__.py:1`). Geborgd door `tests/test_openmeteo_isolation.py` (2 tests, groen). |
| AC-8 | NEEDS_LARS | Niet uitvoerbaar in de sandbox (geen Docker, geen echte Open-Meteo-requests voor de verifier). Nodig van Lars: de stappen uit `docs/RUNBOOK.md` sectie 9, "Lokale test met de stack". Zie hieronder. De logica is wel gedekt door `test_job_fixture_end_to_end` en `test_job_is_idempotent` met `FakeSupabase`. |

AC-8, exacte stappen (vanuit `ingest/`, na `supabase start` en `.env` tijdelijk op de lokale stack):
1. `psql "<DB URL uit supabase status>" -c "insert into public.spots (id, name, lat, lon) values ('test-strand', 'Teststrand', 52.47, 4.57) on conflict (id) do nothing;"`
2. `uv run shakka forecast fetch` (verwacht exit 0 en `forecast: ok`).
3. `select model, count(*) from public.forecast_hours group by model;` (verwacht alle vier: knmi, icon, ecmwf, gfs).
4. `uv run shakka forecast fetch` nogmaals. Het aantal rijen verdubbelt niet. Het is gelijk, of iets hoger doordat de KNMI-horizon opschuift.
5. `.env` terugzetten en de test-spot verwijderen.

## Harde regels
- Geen secrets: scan van de diff op sleutelpatronen en `eyJ`/`sb_secret`/`password`/`api_key` geeft geen treffers. Er is geen `.env` in de diff.
- Open-Meteo alleen server-side: de host staat alleen in `ingest/src/shakka/openmeteo/`. `web/` is niet gewijzigd en bevat geen Open-Meteo-verwijzing. `test_httpx_client_only_created_in_http_module` is groen.
- Bronvermelding: `ingest/tests/fixtures/openmeteo/README.md` en de docstring van `test_openmeteo_forecast.py` bevatten "Weather data by Open-Meteo.com ... CC BY 4.0". Er is geen UI in deze WP. De zichtbare vermelding in de app komt in een latere WP.
- Geen scraping: alleen de officiële Open-Meteo API.
- Geen nieuwe betaalde dienst of dependency: `pyproject.toml`, `uv.lock`, `.github`, `web`, `supabase` en `data` zijn niet gewijzigd.
- Offshore altijd `no_go`: niet geraakt door deze WP (evaluatie komt in WP-05).
- Geen verzonnen spotdata: de fixture is één echte, onaangepaste respons (opname 2026-10-14). De test-spot voor AC-8 wordt alleen door de verifier lokaal ingevoerd.
- Scope: de diff bevat alleen `ingest/` (src en tests), `docs/RUNBOOK.md` (nieuwe sectie 9), `docs/STATUS.md` (todo naar verifying) en `docs/wp/WP-03/`. Dat komt overeen met de Bestanden-lijst van de blueprint.
- Diff versus blueprint: de afwijkingen staan in `deviations.md` en raken geen contract of acceptatiecriterium. Daaronder de goedgekeurde vlaagverschuiving (A14, optie a): `gust_kn` op `valid_at` T is de ruwe vlaag van T+1h, en het laatste uur heeft `gust_kn=None`. Dit is gedocumenteerd in de docstrings van `ForecastHour` en de parser, en in RUNBOOK sectie 9. Review N-1 is verwerkt (testhelpers `expected_speed`, `expected_dir`).

## Problemen
Geen fails.

N-1 (informatief, geen fail): AC-8 blijft open voor Lars (zie hierboven). `wp/WP-03` is volgens `deviations.md` punt 7 door de builder niet gepusht, maar `origin/wp/WP-03` bestaat en staat op HEAD. Dit is daarmee achterhaald.

## Handmatige check op develop (15 oktober 2026, AC-8)
Uitgevoerd door de orchestrator tegen de lokale stack, met echte Open-Meteo-requests, na de merge op `develop` (`b794f7c`). Test-spot `test-strand` (52.47, 4.57).
- `shakka forecast fetch` (1e): `forecast: spots=1 rows=571 calls=1.20 deleted=0 skipped_budget=no errors=0`, `forecast: ok`, exit 0.
- `forecast_hours` per model: ecmwf 168, gfs 168, icon 168, knmi 67 (KNMI-horizon circa 2,5 dag).
- `shakka forecast fetch` (2e): zelfde regel, zelfde tellingen (geen verdubbeling).
- `api_usage`: `2026-10-15 | open_meteo_forecast | calls 2.40 | requests 2`.
- Test-spot daarna verwijderd.

**AC-8: PASS.** Resultaat WP-03: PASS.
