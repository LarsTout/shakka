# Verificatie WP-22, ronde 1
Resultaat: NEEDS_LARS

Alles wat zonder account of secret te toetsen is, is PASS. Alleen AC-6 (Open-Meteo-mail, SMTP-dienst, magic link naar een niet-teamlid) en `supabase db push` hangen aan Lars of de orchestrator, zoals afgesproken.

Gedraaide suites (HEAD `f795227`, branch `wp/WP-22`):
- `cd ingest && uv run pytest`: 1735 passed, 24 skipped (alleen tests die een lokale Supabase vragen).
- `uv run ruff check .`: All checks passed. `uv run ruff format --check .`: 137 files already formatted.
- `cd web && npm ci && npm run check`: 0 errors, 0 warnings. `npm test`: 904 passed. `npm run build` met de CI-placeholders: geslaagd.
- `npm audit --omit=dev --audit-level=high`: `found 0 vulnerabilities`, exitcode 0.
- CI (run 38813178463 op `f795227`): jobs `web`, `ingest` en `db` alle drie success. De job `db` toont `01/02/04/07/10 ... ok`, `Files=9, Tests=449`, `Result: PASS`. Plan-aantallen in de bestanden: 01=70, 02=54, 04=40, 07=112, 10=28.

| Criterium | Resultaat | Bewijs |
|---|---|---|
| AC-1 | PASS | `grep -rn "httpx.Client(" ingest/src` geeft alleen `shakka/http.py:26`. `tests/test_http.py` (onderdeel van de groene suite) toetst de eindige timeout van `make_client`. |
| AC-2 | PASS | `tests/test_usage.py` groen (golden-tekst, 310 MB, 7.100 calls/dag, geen waarschuwing onder de drempels, limieten gelijk aan `budget`). |
| AC-3 | PASS | `tests/test_pipeline_usage.py` en `tests/test_job_usage.py` groen: alleen maandag, één keer per week, alleen naar de abonnementen van de operator, zonder operator/abonnement geen crash en rapport in `ingest_runs`, titel <= 50 en body <= 150. |
| AC-4 | PASS | CI `db`: `10_hardening.test.sql` ok (asserts: `anon` en `authenticated` kunnen `db_usage()` niet uitvoeren, `42501`; alleen `service_role`). De migratie doet `revoke all ... from public, anon, authenticated, service_role` en `grant execute ... to service_role`. |
| AC-5 | PASS | `npm audit --omit=dev --audit-level=high` exit 0 (zelf gedraaid). |
| AC-6 | NEEDS_LARS | RUNBOOK §17 bevat de SMTP-vergelijking, de Auth-rate-limits en het concept voor Open-Meteo; "Gekozen SMTP-dienst", datum en uitkomst van de Open-Meteo-bevestiging staan op "nog in te vullen door Lars". Nodig: SMTP-dienst kiezen en instellen, mail aan Open-Meteo, en een magic link naar een niet-teamlid testen. |
| AC-7 | PASS | CI `db` groen. `01_schema` noemt `telegram_chat_id` niet meer (alle `telegram_chat_id`-asserts uit 01/02/04 verwijderd, geen treffer in `supabase/tests`). `grep -rni telegram ingest/src web/src` is leeg. Oude migraties ongewijzigd (`git diff --name-status`: alleen twee nieuwe migratiebestanden). |

## Harde regels
- €0: geen nieuwe dienst, geen dependency-wijziging (`pyproject.toml`, `uv.lock`, `package*.json` niet in de diff). SMTP staat alleen in het RUNBOOK, met een expliciete "betaald, akkoord Lars" bij een eigen domein.
- Geen secrets in de diff (patroonscan op `sb_secret_`, JWT, private keys, API-sleutels leeg). `OPERATOR_USER_ID` staat alleen als lege regel in `.env.example` en als `secrets.OPERATOR_USER_ID` in `hourly.yml`. Geen `TELEGRAM_*` in `.github`.
- Persoonsgegevens in logs: `secret_values` neemt `OPERATOR_USER_ID` op in ruwe en canonieke (`str(uuid.UUID(..))`) vorm. Zelf getoetst met een end-to-end `run_hourly_cli` tegen een lokale nep-PostgREST, operator `ABCDEF12345678901234567890ABCDEF` (zonder streepjes, hoofdletters), report-run op een maandag, `push_subscriptions` gaf 503 met de pad-URL in de body. De canonieke UUID stond aantoonbaar in de requests (`UUID_IN_REQUEST True`), en kwam 0 keer voor in stdout, logs en annotaties. Het gebruiksrapport bevat alleen aantallen (rijen per tabel, runs, pushes sent/failed).
- Geen client-side Open-Meteo: `web/src` bevat alleen de bronvermelding-link. Bronvermelding intact (`Attribution.svelte` ongewijzigd). Geen scraping.
- Offshore ongemoeid: 0 treffers op "offshore" in de diff van `ingest/src`.
- Geen bestanden buiten scope: diff = ingest (http, db, jobs, notify, pipeline, openmeteo, rws, cli, config, logsetup), twee migraties, pgTAP-tests, `auth.ts` plus tests, workflows, `.env.example` en docs.

## Controlepunten uit de opdracht
- (2) Retries: `db.py` herhaalt alleen `select/upsert/update/delete` (`RETRYING_OPS`); insert niet. Alleen transportfouten en 429/502-504/520-524. Stroomonderbreker (`retries_disabled`) na een uitgeputte aanroep, getoetst in `test_db.py::test_circuit_breaker_after_exhaustion`. `git diff` op `jobs/alerts.py` raakt `store_plan` niet: de schrijfvolgorde van `alert_state` is ongewijzigd. Runbudget 600 s (`RUN_TIME_BUDGET_S`): resterende stappen `skipped` met reden `run_time_budget`, `::error::`-annotatie en exitcode 1 (`test_run_time_budget_skips_remaining_steps`).
- (3) Push: allowlist met `fcm.googleapis.com`, `jmt17.google.com` en de suffixen Mozilla/Apple/Windows; `android.googleapis.com`, poort, userinfo, `http` en lookalikes worden geweigerd (`test_push_allowlist.py`, ook in de notifier zelf als defence in depth). `push_non_retryable` loopt van `EventDelivery` naar `AlertJobResult`, geeft `::warning::`, stap `partial` en `alerts run` exit 1 (`test_non_retryable_push_is_partial_with_warning`, `test_alerts_run_non_retryable_exit_1`). 404/410 is `permanent_failure` en verwijdert; 401/403 is niet-permanent en niet-retryable en verwijdert niet. Abonnementsgrens 20 is een trigger (`push_subscriptions_limit`, `PT400 too_many_subscriptions`) met advisory lock en getoetst in `10_hardening`.
- (4) Veroudering: `MAX_FETCH_AGE` 3 uur per spot in `run_evaluation` (geen nieuwe evaluaties, bestaande rijen onaangeroerd, `test_stale_spot_gets_no_new_evaluations`) en in `load_alert_context` (spot wordt `ineligible`; `alert_state` ongewijzigd, geen writes, dus geen valse `cancelled`: `test_stale_forecast_makes_favorite_ineligible`).
- (5) Migraties: `telegram_chat_id` en `profiles_telegram_chat_id_format` weg; `db_usage()` security definer, `search_path` vastgezet, alleen `service_role`; sessie-horizon is trigger `sessions_starts_at_horizon` (geen CHECK; ongewijzigde `starts_at` blijft bewerkbaar); bestaande migraties ongewijzigd.
- (6) `auth.ts`: `shouldCreateUser: true`; `signup_disabled` (naast `otp_disabled`) geeft `notAuthorized`; tests bijgewerkt en groen.
- (7) Actions op SHA: `actions/checkout` `3d3c42e5...` (v7.0.1) en `actions/setup-node` `949feb24...` (v7.1.0) komen via `gh api repos/actions/<naam>/commits/<sha>` overeen. Geen `TELEGRAM_*` in workflows.
- (8) `07_sessions.test.sql`: alleen regels 68 en 69 gewijzigd (`db_usage` erbij; plan 112 ongewijzigd). `origin/develop` heeft inmiddels WP-23 met `delete_my_account` in regels 67 en 69. Een proefmerge (`git merge-tree`) geeft conflicten in `docs/RUNBOOK.md`, `docs/STATUS.md` en `supabase/tests/07_sessions.test.sql`; de rebase moet de regels 68/69 samenvoegen (eindvorm staat in de blueprint, Interfaces) en `RUNBOOK`-nummering (§17) hernummeren. De WP-23-migratie `20261016090000_delete_my_account.sql` heeft een latere timestamp dan de twee WP-22-migraties: `supabase db push --include-all` is nodig als WP-23 al gepusht is (staat in "Nodig van Lars").

## Problemen
Geen blokkerende problemen.

Niet-blokkerend:
- N-1: `jobs/usage.py::_delivery_notes` meldt bij een mislukte `load_targets` (DatabaseError) "usage push failed on all 0 device(s)"; het aantal "0" is misleidend. Cosmetisch, de status `partial` en de retry volgende run kloppen.
- N-2: de merge naar `develop` geeft de bovengenoemde conflicten in `RUNBOOK.md`, `STATUS.md` en `07_sessions.test.sql`. Los ze op bij de merge, daarna de CI-job `db` opnieuw laten draaien (07 moet dan `delete_my_account` en `db_usage` in de service_role- en definer-sets tonen op de juiste regels).
- N-3 (uit `deviations.md`, voor de orchestrator): `PROJECT_PLAN.md` sectie 2 (5.000 map sessions) tegenover RUNBOOK §18.8, en de Gmail-zin in `/privacy` en `docs/PRIVACY.md` na de SMTP-keuze.

## Nodig van Lars / orchestrator
1. AC-6: SMTP-dienst kiezen en instellen, mail aan Open-Meteo, magic link naar een niet-teamlid testen, daarna de twee velden in RUNBOOK §17 invullen.
2. "Allow new users to sign up" uit voor de merge (anders is `shouldCreateUser: true` open).
3. `supabase db push` (met `--include-all`) na de merge, en `OPERATOR_USER_ID` in `.env` en als GitHub Secret.
