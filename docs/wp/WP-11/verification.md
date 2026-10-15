# Verificatie WP-11, ronde 1
Resultaat: NEEDS_LARS

Alle automatisch toetsbare criteria zijn gehaald (AC-1 t/m AC-5). AC-6 (echte workflow-run, secrets, e-mailmeldingen) is NEEDS_LARS by design.

Suite: `cd ingest && uv run pytest -q` geeft 1328 passed, 24 skipped (tests tegen lokale Supabase-stack: `SHAKKA_TEST_SUPABASE_URL` niet gezet, zoals verwacht). `uv run ruff check .` en `uv run ruff format --check .` groen (108 files formatted). CI op `wp/WP-11` (commit "docs(WP-11): verifying"): success.

| Criterium | Resultaat | Bewijs |
|---|---|---|
| AC-1 | PASS | `tests/test_pipeline.py::test_all_steps_ok_records_run` (echte stappen, fakes): `ingest_runs`-rij `ok`, stappen exact `spots_sync, forecast, tides, evaluate, alerts`, `exit_code` 0, `finished_at` gezet, `error_summary` None; `test_steps_contract_order`. Groen. |
| AC-2 | PASS | `test_forecast_exception_with_stale_data_skips_alerts` (4 u oud: `tides`/`evaluate` ok, `alerts` skipped `stale_forecast`, run `partial`, exit 1, geen `alert_state`-writes, `forecast.error` in steps); `..._with_fresh_data_runs_alerts` (2 u: alerts ok, partial, exit 0); `test_stale_boundary_exactly_three_hours_is_fresh`; `test_forecast_failed_without_rows_is_stale`; `test_forecast_partial_triggers_stale_check`; `test_failed_run_exit_code_1` (failed -> 1); `tests/test_cli_pipeline.py::test_cli_exit_code_follows_report[0,1]` (CLI geeft `RunReport.exit_code`). Code: `step_alerts` leest `newest < now - 3h` strikt, alleen als forecast niet `ok`; `exit_code_for` geeft 1 bij `failed` of `stale_forecast`. |
| AC-3 | PASS | `test_cli_pipeline.py::test_secret_not_in_log_output` (falende forecaststap met secret in exceptietekst): `SUPABASE_SECRET_KEY` niet in caplog, stdout, stderr; in `ingest_runs.steps[forecast].error` geredigeerd (`***`). Zelf gedraaid: `env -i SUPABASE_URL=http://127.0.0.1:9 (en https://nonexistent.invalid) SUPABASE_SECRET_KEY=sb_secret_TESTVALUE uv run shakka run-hourly`: exit 1, uitvoer = 2 logregels met alleen `DatabaseError`, een `::error::`-regel en de eindregel; `grep -c TESTVALUE` = 0 in beide runs. |
| AC-4 | PASS | `tests/test_hourly_workflow.py` groen. Handmatig: `grep -nE "sb_secret_" .github/workflows/*.yml` en `grep -niE "telegram" ...` geven niets. YAML geldig (`yaml.safe_load`): cron `17 * * * *`, `workflow_dispatch` met input `ref` (main/develop), `concurrency {group: hourly, cancel-in-progress: false}`, `timeout-minutes: 15`, `working-directory: ingest`, `uv run shakka run-hourly`, `permissions: contents: read`. |
| AC-5 | PASS | `test_pipeline.py::test_budget_warning_recorded` (6500 calls: warning in `steps[forecast].warnings`, annotatie `::warning::forecast: ...`, status ok, exit 0), `test_budget_below_threshold_no_warning`; `test_cli_pipeline.py::test_budget_warning_on_stdout` (regel begint met `::warning::`, exit 0). |
| AC-6 | NEEDS_LARS | Vereist GitHub Secrets `SUPABASE_URL` en `SUPABASE_SECRET_KEY`, Actions aan, variable `HOURLY_ENABLED=true`, een `workflow_dispatch`-run met `ingest_runs`-rij `status = ok` in het remote project, een geplande run binnen 2 uur, en bevestiging dat e-mailmeldingen voor Actions aan staan (RUNBOOK §13 punt 2). `main` bevat `shakka run-hourly` pas na promotie; tot die tijd `ref: develop` bij dispatch. |

## Extra gerichte controles
- hourly.yml: secrets alleen als `${{ secrets.SUPABASE_URL }}` en `${{ secrets.SUPABASE_SECRET_KEY }}`, alleen in de `env` van de pipelinestap (niet job-breed); `APP_BASE_URL` via `vars`. `checkout` met `ref: ${{ github.event_name == 'workflow_dispatch' && inputs.ref || 'main' }}` (schedule altijd `main`), `persist-credentials: false`. Job-`if` `github_event_name == 'workflow_dispatch' || vars.HOURLY_ENABLED == 'true'`. Activiteitsstap heeft `if: !cancelled() && steps.sync.outcome == 'success'` (id `sync` op `uv sync`; afwijking N-4, gedocumenteerd, met test `test_activity_step_skipped_when_sync_fails`).
- Geen user-id's of berichtteksten in log/stdout: `_step_log_line` neemt alleen bool/int/float-tellingen; lijsten (`errors`) en `error` blijven in `ingest_runs`; `alert_counts` bevat nooit `messages`. `test_no_user_ids_or_message_texts_in_output` en `test_alerts_errors_only_in_ingest_runs` groen. `configure_logging` zet `httpx` en `httpcore` op WARNING (`test_httpx_and_httpcore_quiet`), redactie op elke geformatteerde regel.
- Levenscyclus `ingest_runs`: wezen-rijen sluiten (`test_abandoned_runs_marked_failed`), insert `running` bij start, voortgangsupdate per stap, slotupdate met `finished_at >= started_at`; mislukte insert -> fail-fast, geen stap, exit 1 (zelf bevestigd met onbereikbare URL, `test_cannot_start_run`); mislukte slotupdate -> exit 1.
- Foutisolatie: `run_step` vangt `Exception` per stap (`test_spots_sync_failure_continues`, `test_all_steps_failed`); `KeyboardInterrupt`/`SystemExit` gaan door.
- Getijdeadline: `TIDE_STEP_BUDGET_S = 240.0`, gelezen bij elke aanroep, via `bounded_fetch` in `pipeline.py`; `ingest/src/shakka/jobs/tides.py` is niet gewijzigd (diff). `test_tide_budget_stops_fetching` en `test_tide_budget_zero_still_runs_alerts` groen.
- `check-activity`: zelf gedraaid met 44/45/52/53 dagen: ok exit 0 / `::warning::` exit 0 / `::warning::` exit 0 / `::error::` exit 1; lege datum geeft warning, exit 0.

## Harde regels
- Geen secrets in de diff: grep op `sb_secret_<waarde>`, JWT-prefix en private-key headers in de diff: niets. Testwaarde `sb_secret_TESTVALUE` staat alleen in tests (bestaande conventie).
- Geen client-side Open-Meteo: diff raakt alleen `/ingest` en docs, geen `/web`.
- Geen scraping, geen nieuwe dependency (`pyproject.toml` en `uv.lock` niet gewijzigd), geen nieuwe betaalde dienst.
- Bronvermelding: niet geraakt (geen `/web`-wijziging).
- Offshore `no_go`: niet geraakt; `shakka.domain` ongewijzigd.
- Scope: gewijzigd zijn alleen `.github/workflows/hourly.yml`, `ingest/src/shakka/{pipeline,logsetup,activity,cli}.py`, `jobs/runtime.py` (toegestaan), tests, `docs/RUNBOOK.md`, `docs/STATUS.md`, `docs/wp/WP-11/*`. Niet gewijzigd: `shakka.db`, `shakka.domain`, `jobs/tides.py`, `tests/fakes.py`, `pyproject.toml`, `ci.yml`, migraties.
- Diff versus blueprint: afwijkingen N-1, N-3, N-4 en het RUNBOOK-menupad staan in `deviations.md`; geen ongedocumenteerde afwijkingen gevonden. `hourly.yml` wijkt alleen af via N-4 en toegestane commentaarregels.

## Problemen
Geen. Open voor Lars: AC-6 (zie tabel).
