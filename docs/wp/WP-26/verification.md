# Verificatie WP-26, ronde 1
Resultaat: PASS (AC-6 blijft open als NEEDS_LARS, na promotie naar `main`)

| Criterium | Resultaat | Bewijs |
|---|---|---|
| AC-1 | PASS | `uv run pytest tests/test_openmeteo_forecast.py` groen. `test_build_params_exact` eist `forecast_days=8`. `test_fixture_has_eight_days` en `test_fixture_matches_current_params` slagen. Zelf nagerekend op de JSON: 2 elementen, elk 192 uren, stap 3600, `time[0]` = 2026-10-28 00:00Z. ECMWF en GFS hebben 24/24 waarden op index 168-191, ICON 13/24, KNMI 0 (verwacht). |
| AC-2 | PASS | `tests/test_budget.py::test_weight_eight_days_equals_seven` groen (30.0 gelijk aan 30.0). |
| AC-3 | PASS | `tests/test_windows.py::test_days_ahead_seven_reaches_local_today_plus_seven` groen. Test toetst echt: 1 window met `days_ahead=7`, `[]` met `days_ahead=6`. |
| AC-4 | PASS | `npm run check` 0 fouten. `npm test` 1095 passed. `npm run build` groen met de CI-placeholders. Zonder `.env` faalt de build op `env_invalid`, wat een worktree-kwestie is. `alert-rule-form.test.ts` toetst opties `['', '0'..'7']`, label `7 (vandaag plus 7 dagen)` en dat "geen data" ontbreekt. `forms.test.ts` bevat de guard `DAYS_AHEAD_UI_MAX === ALERT_DEFAULTS.days_ahead.max`. |
| AC-5 | PASS | `uv run pytest`: 1739 passed, 24 skipped (alleen Supabase-lokaal-tests zonder env). `ruff check` en `ruff format --check` groen. |
| AC-6 | NEEDS_LARS | De query uit de WP draaien na promotie naar `main` en één uurlijkse run. Bij voorkeur tussen 06:00 en 22:00 UTC. Verwacht minstens 1 rij voor `icon`, `ecmwf` en `gfs`. |

## Harde regels
- Geen secrets in de diff. De grep op secret/key/token/password gaf geen treffers.
- Geen client-side Open-Meteo: alleen `ingest/src/shakka/openmeteo/forecast.py` (één regel) en tests/docs zijn gewijzigd. Er is geen web-productiecode met Open-Meteo.
- Geen scraping, geen nieuwe dienst, gewicht gelijk (€0).
- Bronvermelding intact: de CC BY 4.0-regel staat nog in de fixture-README. Alleen datum en URL zijn gewijzigd.
- Offshore blijft `no_go`: niet geraakt.

## Diff versus blueprint
De diff komt overeen met de bestandstabel van de blueprint (13 bestanden: 11 uit de tabel plus STATUS.md en review.md). Er is geen `deviations.md`. De RUNBOOK-regel **Horizon.** staat letterlijk in §9, met `forecast_days=8` in de curl-URL. Er zijn geen bestanden buiten de scope gewijzigd. `AlertRuleForm.svelte` is ongewijzigd, zoals bedoeld.

## Problemen
Geen blokkerende.
N-1 (niet-blokkerend): de fixture is niet opnieuw opgehaald door de verifier. Dat is niet nodig, want de inhoud is gecontroleerd op vorm en dekking.
