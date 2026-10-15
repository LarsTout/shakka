## WP-11: Orkestratie: uurlijkse workflow, logging, foutmeldingen

- `shakka.pipeline.run_hourly`: spots_sync → forecast → tides → evaluate → alerts, foutisolatie per stap, elke run in `ingest_runs` (`running` → stappen → eindstatus), stale-regel 3 uur (`stale_forecast` → exit 1), getij-deadline 240 s zonder wijziging aan `shakka.jobs.tides`.
- `shakka.logsetup`: redactie van secrets, `httpx`/`httpcore` op WARNING, `::warning::`-annotaties; alleen tellingen in logs (openbare Actions-logs).
- `shakka.activity` / `check-activity`: 60-dagen-maatregel (warning vanaf 45, exit 1 vanaf 53 dagen).
- `.github/workflows/hourly.yml`: schedule met `ref: main`, `concurrency`, `workflow_dispatch`, `HOURLY_ENABLED`-schakelaar, `timeout-minutes: 15`, secrets alleen via `${{ secrets.* }}`.
- RUNBOOK §13; 1328 tests groen; CI groen.

**Verificatie:** AC-1..5 PASS (AC-3 zelf getest: dummy-secret komt niet in de uitvoer). AC-6 (echte run) na promotie van `develop` naar `main` en `HOURLY_ENABLED=true`.

**Hiermee is M1 compleet** (WP-09 vervallen). Open voor Lars: AC-11 van WP-10 (M1-check met eigen user en een geverifieerde spot) en AC-6 hier.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
