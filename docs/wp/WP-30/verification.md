# Verificatie WP-30, ronde 1
Resultaat: PASS

| Criterium | Resultaat | Bewijs |
|---|---|---|
| AC-1 (migratie, CHECK, kolomrechten, A tegen B) | PASS | Migratie letterlijk volgens blueprint; `12_quiet_hours.test.sql` (plan 15, 15 asserts) en `01_schema.test.sql` bijgewerkt. pgTAP: bewijs uit CI (Docker draait niet). `schema-columns.test.ts` groen (grant is exact `QUIET_HOURS_COLUMNS`). |
| AC-2 (domein `quiet`, DST) | PASS | `uv run pytest tests/test_quiet.py tests/test_domain_purity.py` groen; DST-gevallen 32/40/0/8 kwartieren getoetst. |
| AC-3 (poort in job, dry_run, ongeldig, log) | PASS | `tests/test_job_alerts_quiet.py` groen; poort staat na `assert plan.diff is not None` en vóór `dry_run`/`assign_new_ids`/`deliver_plan`/`store_plan`. |
| AC-4 (geboren-en-verdwenen, geannuleerd-en-terug, pipeline `ok`) | PASS | `test_window_born_and_gone_in_quiet_gives_nothing`, `test_cancel_and_return_in_quiet_gives_nothing` (review N-1 verwerkt), `test_hourly_quiet_is_ok_not_partial`, `test_alert_counts_shape`, golden in `test_cli_jobs.py` groen. |
| AC-5 (web) | PASS | `quiet-hours-settings`, `forms`, `user-data`, `user-tables`, `schema-columns`, `alerts-page`, `a11y-alerts`: 146 tests groen. `quietHourOptions` voegt `''` niet toe (review N-2 verwerkt). |
| AC-6 (privacy) | PASS | `privacy-page.test.ts` groen; `/privacy` en `docs/PRIVACY.md` noemen stille uren / `quiet_from`, `quiet_until`. |

## Suites (zelf gedraaid)
- `cd ingest && uv run pytest`: 1821 passed, 24 skipped (lokale Supabase ontbreekt). `ruff check` en `ruff format --check` schoon.
- `cd web && npm run check`: 0 errors, 0 warnings. `npm test`: 1159 passed.
- `npm run build` met dummy `PUBLIC_SUPABASE_URL` en `PUBLIC_SUPABASE_PUBLISHABLE_KEY=sb_publishable_dummy`: ok. `npm run verify:build`: ok. Geen `.env` aangemaakt.

## Harde regels
- Geen secrets in de diff (grep op key/secret/token/password/JWT zonder treffers; geen `.env` in de diff).
- Geen client-side Open-Meteo; geen scraping; geen nieuwe betaalde dienst of package.
- Bronvermelding ongewijzigd. Offshore blijft `no_go` (planning en evaluatie niet aangeraakt; poort zit na `plan_favorite`).
- Log en foutregel bevatten geen user-id; `quiet` is alleen een telling en maakt de stap niet `partial`.
- Scope: alle gewijzigde bestanden staan in de bestandentabel van de blueprint (plus `docs/STATUS.md`, `review.md`). Geen `deviations.md`, geen ongedocumenteerde afwijkingen.
- A1 en A7: bevestigd door Lars (28 oktober 2026), vastgelegd in blueprint en `PROJECT_PLAN.md`.

## Problemen
Geen.

## Opmerkingen (niet blokkerend)
- Review N-5 (alter-guard slaat alleen `add column` op `profiles` over, andere tabellen blijven gecontroleerd) is verwerkt.
- Na de merge is `supabase db push` nodig (Lars).
