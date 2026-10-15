# Afwijkingen WP-11

Geen afwijkingen die een contract, schema, externe API, dependency of acceptatiecriterium raken.

- **N-1 (review ronde 2): importpad.** `short_error`, `db_error_summary` en `require_aware` komen uit `shakka.jobs.inputs` (niet uit `shakka.db`). Geen impact.
- **N-3: `TIDE_STEP_BUDGET_S`.** `step_tides` leest de module-global bij elke aanroep (`budget_s = TIDE_STEP_BUDGET_S`), nooit als default-argument; commentaar bij de constante. De test monkeypatcht hem.
- **N-4: activiteitsstap.** In `hourly.yml` heeft de stap `uv sync` nu `id: sync`, en de activiteitsstap heeft `if: ${{ !cancelled() && steps.sync.outcome == 'success' }}` in plaats van `!cancelled()`. Dit wijkt af van "letterlijk overnemen" in het blueprint; er is een extra test (`test_activity_step_skipped_when_sync_fails`). Impact: geen tweede fout als `uv sync` faalt.
- **Commentaarregels in `hourly.yml`** (toegestaan): bij cron, concurrency en de job-`if`.
- **Commitgranulariteit.** `pipeline.py` is in één keer geschreven (kern en stappen) en in stap 3 gecommit; de teststappen volgden in de commit erna. Geen inhoudelijke impact.
- **RUNBOOK §13 punt 2 (menupad meldingen).** De GitHub-documentatie bevestigt dat e-mail/web en "alleen bij gefaalde workflows" bestaan, maar geeft het exacte menupad niet. De tekst noemt het onderdeel voor Actions in Settings, Notifications en vraagt Lars de namen te controleren in de interface (niet het in het blueprint genoemde "System, Actions" als feit gesteld).
- **Tests.** Extra tests: `test_spots_sync_orphan_warning`, `test_forecast_ok_without_coordinates_runs_alerts`, `test_redacting_handler_output`, `test_injected_clients_not_closed`.
- **Skips.** De tests tegen de lokale Supabase-stack (24) zijn geskipt (Docker niet bereikbaar), zoals verwacht.
- **AC-6 is NEEDS_LARS** (echte workflow, secrets en `ingest_runs`-rij; zie blueprint "Nodig van Lars" en RUNBOOK §13).
