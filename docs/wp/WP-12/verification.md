# Verificatie WP-12, ronde 1
Resultaat: NEEDS_LARS

Alleen AC-5 (live `shakka marine fetch` tegen de lokale stack) is niet gedraaid: Docker/de lokale stack is hier niet bereikbaar, en de migratie moet na de merge met `supabase db push` worden toegepast. Alle andere criteria zijn aantoonbaar gehaald.

Gedraaid op HEAD `ec2ddeb` (branch `wp/WP-12`, diff t.o.v. merge-base met `origin/develop`):
- `cd ingest && uv run pytest`: 1529 passed, 24 skipped (live-parity, geen lokale stack).
- `uv run ruff check . && uv run ruff format --check .`: groen (127 files formatted).
- `cd web && npm ci && npm run check`: 0 errors, 0 warnings.
- `npm test`: 29 files, 221 tests groen.
- `npm run build`, `npm run verify:build`: ok.
- `bash scripts/check-no-client-openmeteo.sh`: ok.
- CI run 38761096329 (HEAD): jobs `ingest`, `db` en `web` alle success. `db` draait de officiele pgTAP-run, inclusief `06_marine_hours.test.sql` en de bijgewerkte `01_schema.test.sql`.

| Criterium | Resultaat | Bewijs |
|---|---|---|
| AC-1 | PASS | `test_openmeteo_marine.py::test_fixture_all_valid_at_utc`, `test_fixture_values_match_raw_json`, `test_fixture_values_belong_to_spot`, `test_fixture_inland_has_no_rows` groen. Fixture gecontroleerd: 3 locaties, locatie 2 (52,09/5,10) heeft 0 niet-null waarden in beide modellen en geeft geen rijen. Tests vergelijken met de ruwe JSON, ze toetsen het criterium. |
| AC-2 | PASS | `test_job_records_usage_under_marine_source`, `test_job_budget_exceeded_no_request` (forecastverbruik 7999,5 + 1,0 > 8000: geen request, `skipped_budget`, usage ongewijzigd), `test_job_budget_boundary_inclusive`, `test_job_monthly_budget_exceeded_no_request`. `test_pipeline.py::test_marine_budget_skipped_after_forecast`: forecastverbruik 7998,5 stopt marine (partial, geen rijen), usage staat onder `open_meteo_forecast` en `open_meteo_marine` (`test_marine_step_ok_counts`). Bron `SOURCE_OPEN_METEO_MARINE = "open_meteo_marine"` valt onder prefix `open_meteo_` van de gedeelde `BudgetGuard`. |
| AC-3 | PASS | `STEPS` = spots_sync, forecast, marine, tides, evaluate, alerts (`test_steps_contract_order`). `test_marine_exception_is_partial_run`: marine `failed`, tides/evaluate/alerts `ok`, run `partial`, exit 0, alert-event nog aangemaakt. `test_marine_fetch_error_is_partial_step`: step `partial`, run `partial`, exit 0. Code: `step_alerts`, `run_status`, `exit_code_for` en stale-regel niet in de diff. |
| AC-4 | PASS | CI-job `db` success (officiele pgTAP). `06_marine_hours.test.sql` (20 asserts) toetst: anon leest 2 rijen, anon insert/update/delete geeft 42501, authenticated leest en kan niet schrijven, exacte privileges per rol, policy `marine_hours_read`, constraints, cascade. |
| AC-5 | NEEDS_LARS | Niet gedraaid (geen Docker/lokale stack in deze sessie; migratie nog niet toegepast). Nodig: lokale stack met migratie `20261015180000_marine_hours.sql` (`supabase db reset` of `db push`), een test-spot op de Noordzeekust met coordinaten, daarna `uv run shakka marine fetch` en controle dat `marine_hours` gevuld is (RUNBOOK §15.6). De logica is wel gedekt door `test_job_fixture_end_to_end` en `test_cli_marine.py` met fakes. |
| AC-6 | PASS | `npm run check`, `npm test`, `npm run build`, `verify:build` en de guard (`check-no-client-openmeteo.sh`, `guard.test.ts` inclusief marine-host) groen. `spot-page.test.ts` "waves": golfregel `Golven 1,2 m, periode 5 s, uit WZW (250°)` onder het uur van 14:00; zonder marinedata geen `.waves`, geen notitie en geen `alert`; verouderde data verborgen; geen notitie bij alleen een donker uur. |
| AC-7 | PASS | `data-tables.test.ts` is aangepast: toegestane tabellen uitgebreid met `marine_hours` en "reads each table at least once" uitgebreid. De test is niet verzwakt: de `.from(`-telling moet nog steeds gelijk zijn aan het aantal toegestane aanroepen. `data.ts` heeft 6 `.from(`-aanroepen (2x `spots`, 2x `evaluations`, 1x `tide_extremes`, 1x `marine_hours`), alle op toegestane tabellen. |

## Harde regels
- Marine-URL alleen in `ingest/src/shakka/openmeteo/marine.py`. `grep marine-api` buiten tests/docs vindt alleen dat bestand en `scripts/check-no-client-openmeteo.sh` (guard). `test_openmeteo_isolation.py` groen. PASS.
- Open-Meteo niet client-side: geen aanroepen in `web/src`; alleen de attributielink `https://open-meteo.com/` in `Attribution.svelte` (ongewijzigd). Guard ok. PASS.
- Golven raken oordeel en alerts niet: `grep -i marine` in `domain/evaluation.py`, `domain/alerts.py`, `jobs/alerts.py`, `jobs/inputs.py` en `jobs/evaluate.py` levert niets. Er wordt niets gewijzigd aan die modules. PASS.
- Fixture `marine_3loc_2models.json` is een enkele, ongewijzigde echte respons (3 locaties; kust, IJsselmeer en landlocatie met alleen null). `README.md` noemt CC BY 4.0, Open-Meteo, DWD en ECMWF en de opnamedatum plus URL. PASS.
- Migratie: RLS aan, `revoke all ... from public, anon, authenticated, service_role`, expliciete `grant select` aan `anon` en `authenticated`, CRUD aan `service_role`, policy `marine_hours_read`. PASS.
- Geen secrets in de diff (`git grep` op `sb_secret|sb_publishable|eyJhbGciOi` buiten docs: geen treffers). `web/.env` is gitignored en niet gecommit. PASS.
- Geen scraping, geen nieuwe betaalde dienst (Open-Meteo gratis tier, geen sleutel), bronvermelding ongewijzigd intact; spotpagina krijgt extra notitie met DWD/ECMWF. PASS.
- Offshore altijd `no_go`: code van de evaluatie niet geraakt. PASS.
- Pipeline: `marine` direct na `forecast`; falen of budgetstop geeft `partial` of `failed` voor de stap, run `partial`, exit 0. PASS.
- Web: `getMarineHours` leest alleen `marine_hours`; mislukte golfquery geeft `marine: []` met een anonieme `console.warn` (test controleert dat er geen details of spot-id gelogd worden); rijen met `fetched_at` ouder dan 3 uur verborgen (`marineByHour`, strikt; precies 3 uur nog zichtbaar, getest); Nederlandse opmaak met komma (`formatMeters`, `1,2`, `0,0`). PASS.
- Scope: alle gewijzigde bestanden liggen in `ingest/`, `web/`, `supabase/` en `docs/` en zijn voor WP-12 te verwachten. Bestaande tests zijn alleen aangepast voor de nieuwe stap/tabel (`test_migrations.py` haalt `marine_hours` uit de verboden-lijst voor latere mijlpalen, `test_pipeline.py` verwacht 6 stappen, `01_schema.test.sql` en `test_fakes.py` krijgen de nieuwe tabel). PASS.
- Afwijkingen: `deviations.md` beschrijft de kleine afwijkingen (o.a. tests en implementatie in dezelfde commit, RUNBOOK-sectienummer 15, AC-5 niet gedraaid). Geen ongedocumenteerde afwijking gevonden.

## Problemen
Geen blokkerende problemen.
N-1 (NEEDS_LARS, AC-5): live `uv run shakka marine fetch` tegen de lokale stack nog te draaien, na `supabase db push`/`db reset` (zie boven).
