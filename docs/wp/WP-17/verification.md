# Verificatie WP-17, ronde 1
Resultaat: NEEDS_LARS

Alles wat zonder echte push of `supabase db push` te controleren is, is PASS. Wat overblijft is by design voor Lars: een echte push naar een echt apparaat (`alerts test-push`) en `supabase db push` tegen het echte project.

| Criterium | Resultaat | Bewijs |
|---|---|---|
| AC-1 (`supabase test db`, eigen rijen, anon niets) | PASS | CI-run 38753472968 op HEAD 88fcd2f: job `db` groen, `05_push_subscriptions.test.sql .. ok`, `01_schema.test.sql .. ok`, `Files=5, Tests=222, Result: PASS`. De 32 asserts toetsen: authenticated ziet, maakt en verwijdert alleen eigen rijen; B's rijen blijven staan; `anon` select en insert geven 42501. |
| AC-2 (payload, claims) | PASS | `tests/test_notify_webpush.py::test_payload_contract` groen: sleutels exact `title, body, url, tag`, gelijk aan `to_push_text`, ≤ 3000 bytes, `vapid_claims["sub"]` = subject. Zelf nagelopen: payload met 2000-tekens go_url = 2328 bytes. |
| AC-3 (`test_push_text.py`, puurheid) | PASS | `tests/test_push_text.py` en `tests/test_domain_purity.py` groen, parametrisch over `GOLDEN_CASES`. Zelf gecontroleerd: 150 tekens op regelgrens blijft heel, 151 neemt alleen de regels die passen; te lange eerste regel eindigt op "…" en op woordgrens; titel 50 blijft, 51 wordt "…"; titel nooit leeg; multi-codepoint (emoji, é) binnen 50/150. |
| AC-4 (404/410 verwijderd, 5xx opnieuw) | PASS | `test_gone_subscription_removed`, `test_retryable_failure_keeps_state`, `test_status_permanent`/`test_status_not_permanent` groen. Zelf: 410 geeft `removed=2` en state schuift door; 503 geeft `deferred=1` en `alert_state` blijft leeg; 401/403 staan niet in de permanente set (alleen 404/410, `webpush.py`). |
| AC-5 (2 abonnementen, geen abonnement) | PASS | `test_two_subscriptions_one_fails` en `test_no_subscriptions` groen: 2 afleveringen, andere wordt toch bediend, `no_target` verhoogd, state schuift door. |
| AC-6 (zonder VAPID) | PASS | `test_hourly_without_vapid` groen: 0 afleveringen, `messages` gevuld, `alert_state` actief met `last_notified_at = None`, warning in log en annotatie. `test_hourly_incomplete_vapid` en `..._fails_even_when_stale` groen: half ingevulde VAPID geeft `ValueError` en `failed`, ook vóór de stale-check (`notifiers` is de eerste regel van `step_alerts`). Afwijking N-4 staat in `deviations.md`. |
| AC-7 (`hourly.yml`) | PASS | Diff: drie `${{ secrets.VAPID_* }}`; `test_hourly_workflow.py` groen. |
| AC-8 (geen secrets in `detail`/logs) | PASS | `test_failure_detail_has_no_secrets`, `test_no_endpoints_keys_or_user_ids_in_logs`, `test_hourly_push_failure_leaks_nothing` groen. Eigen run (zie Harde regels). |
| Echte push naar een apparaat; `supabase db push` | NEEDS_LARS | Vereist een VAPID-paar in `.env` en een echt abonnement (pas na WP-18), plus Lars' `supabase db push` (RUNBOOK §14, punt 2, 5 en 6). |

## Suite
- `cd ingest && uv run pytest`: 1442 passed, 24 skipped (de skips zijn de bestaande `SHAKKA_TEST_SUPABASE_*`-pariteitstests).
- `uv run ruff check .`: All checks passed. `uv run ruff format --check .`: 120 files already formatted.
- CI-run 38753472968 (HEAD 88fcd2f): `ingest`, `web` en `db` alle drie groen.

## Harde regels
- **Geen secrets in de diff.** Grep op sleutelachtige waarden vindt alleen testdummy's (`sb_secret_TESTVALUE`, `not-a-valid-key-value`). Het VAPID-paar in tests wordt per sessie gegenereerd. Geen `.env` in de diff.
- **Secrets alleen via env en `${{ secrets.* }}`.** `hourly.yml` heeft alleen `${{ secrets.VAPID_* }}` erbij. `.env.example` en `config.py` zijn niet gewijzigd; de VAPID-velden bestonden al in `Settings`.
- **Geen endpoints, sleutels, user-id's, subject of berichtteksten in logs.** Eigen test (`/tmp/v17/test_v17_leaks.py`, niet in de repo): `alerts run` en `alerts test-push` via CliRunner met echte `WebPushNotifier` en een gemockte `pywebpush.webpush`, in vier modi (ok, 503, 410, onverwachte exception die endpoint, private key, subject en payload in de tekst zet). Uitvoer, caplog (DEBUG), stdout en stderr bevatten geen endpoint, private key, subject, user-id, `p256dh` of `auth`. `detail` is alleen `HTTP <status>`, `WebPushException` of een exceptienaam. De `alerts run`-CLI toont berichtteksten lokaal; dat is ongewijzigd WP-10-gedrag (RUNBOOK §12 punt 9: nooit in een workflow) en `run_hourly` doet dat niet. `urllib3` staat nu ook op `WARNING`, `verbose` blijft uit, het subject zit in `secret_values` voor redactie.
- **Geen client-side Open-Meteo, geen scraping, geen nieuwe betaalde dienst.** `web/` is niet gewijzigd. Nieuwe dependencies `pywebpush`, `py-vapid` en `cryptography` zijn gratis en staan in blueprint A13.
- **Bronvermelding intact.** Geen UI- of bronteksten gewijzigd.
- **Offshore altijd `no_go`.** Geen domeinlogica van evaluatie of regels gewijzigd.

## Gerichte punten
1. **B-1 (subject).** Zelf gedraaid: `WebPushNotifier(key, "mailto:lars@example")`, `https://shakka.nl/contact`, `lars@example.org`, `mailto:`, lege string, `http://example.org` en `mailto:a b@example.org` geven `ValueError` met een vaste tekst zonder de invoer. `mailto:test@example.org`, `https://example.org` en `https://shakka.nl` werken. Een ongeldige private key geeft een aparte vaste `ValueError`.
2. **Autouse-fixture.** `conftest.py` vervangt `pywebpush.webpush` door `pytest.fail` (BaseException); `test_conftest_guard.py` bewijst dat `send_payload` en `deliver_event` er niet omheen komen. `webpush.py` zoekt `pywebpush.webpush` pas bij de aanroep op.
3. **Alles-of-niets en schrijfvolgorde.** `git diff` op `jobs/alerts.py`: `store_plan`, `plan_favorite` en de schrijfvolgorde zijn ongewijzigd. De aflevering zit tussen plannen en opslaan; bij `deferred` volgt `continue` zonder iets op te slaan. `assign_new_ids` kent de `uuid4` vooraf toe (alleen niet-`dry_run`); `test_ids_assigned_before_insert`, `test_all_or_nothing_on_split` en `test_stop_after_first_retryable_event` groen. `last_notified_at` = run-`now` alleen bij minstens één geslaagde aflevering.
4. **Kanaal uit.** Zonder VAPID geeft `notifiers_from_settings` `{}`, de state schuift door, warning aanwezig (zie AC-6). Een half ingevulde configuratie faalt vóór de stale-check.
5. **Migratie/RLS.** `authenticated`: `select`, `delete` en kolom-`insert` op `user_id, endpoint, p256dh, auth`, geen `update`; `anon` niets; `service_role` select/insert/update/delete; `revoke all` vooraf, expliciete grants, drie `own`-policies. Alle getoetst in pgTAP (job `db` groen).
6. **Scope.** Gewijzigd: `ingest/`, `supabase/` (migratie en tests), `hourly.yml`, `docs/RUNBOOK.md`, `docs/STATUS.md`, `docs/wp/WP-17/`. Niets in `web/`, `data/` of andere WP's.

## Problemen
Geen. Afwijkingen (N-1, N-2, N-4 en de kleine punten) staan in `deviations.md` en raken geen contract of acceptatiecriterium.

## Nodig van Lars
- VAPID-sleutelpaar maken (`uv run shakka alerts vapid-keys`), met `VAPID_SUBJECT=mailto:<adres met punt in domein>` in `.env` en de drie GitHub Secrets.
- `supabase db push` voor `20261015150000_push_subscriptions.sql`.
- Na WP-18: `uv run shakka alerts test-push --user-id <id>` voor een echte push op een apparaat.
