## WP-03: Forecast-ingest wind (Open-Meteo multi-model) met call-budget

- `shakka.openmeteo`: client met retries, parameterbouwer, parser; modellen `knmi_harmonie_arome_netherlands`, `dwd_icon_seamless`, `ecmwf_ifs`, `ncep_gfs_seamless`, `cell_selection=sea`.
- `shakka.budget`: gewichtschatting en `BudgetGuard` (80% van de gratis limieten).
- `shakka.jobs.forecast` en `shakka forecast fetch [--dry-run]`; opruimen na 48 uur.
- Fixture van één echte respons (14 okt 2026) met CC BY 4.0-vermelding.
- 382 tests op de branch, 504 na rebase op develop; CI `ingest` + `db` groen.

**Verificatie:** AC-1..7 PASS, inclusief 10 mutatietests. AC-8 (twee echte runs tegen lokale stack) draait Lars na de merge op `develop`; stappen in RUNBOOK §9 en `docs/wp/WP-03/verification.md`.

**Beslispunten voor Lars:** vlagen een uur terugschuiven (A14, optie a; bevestigen vóór WP-05), `cell_selection=sea`, `forecast_days=7` (A10).

🤖 Generated with [Claude Code](https://claude.com/claude-code)
