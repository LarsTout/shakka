# Verificatie WP-10, ronde 1
Resultaat: NEEDS_LARS

Alleen AC-11 staat open (echte `.env`, auth-user en geverifieerde spot nodig). Alle andere criteria zijn PASS.

| Criterium | Resultaat | Bewijs |
|---|---|---|
| AC-1 | PASS | `tests/test_job_evaluate.py` groen. `test_evaluates_only_spots_with_coords` (2 spots, 1 zonder coördinaten, 3 modellen, getij): `EvaluationJobResult(spots=1, rows=9, deleted=0)`, alleen `test-strand`, precies 9 uren. `test_old_rows_deleted` voor de 48-uursopruiming. |
| AC-2 | PASS | `test_job_alerts.py::test_end_to_end_new_repeat_cancel`. Run 1: 1 `RenderedAlert` met kind `new`, titel met "Teststrand", rij `active`/`new`, `state_id == rows[0]["id"]`. Run 2: 0 berichten, rijen ongewijzigd, alleen een `delete` als schrijfactie. Run 3: 1 `cancelled`-bericht, rij `cancelled`. |
| AC-3 | PASS | `grep -rniE telegram ingest/src .env.example` geeft niets. `grep -rn "shakka.notify" ingest/src/shakka/jobs` geeft niets. Ook bewaakt door `test_repo_hygiene.py::test_no_telegram_in_ingest_src_and_env_example`. |
| AC-4 | PASS | `test_logs_contain_no_user_ids_or_bodies` (caplog op DEBUG plus capsys, direct rond `run_alerts`): geen user-id's, geen bodyregels, stdout en stderr leeg. Eigen controle met `httpx.MockTransport` (`/tmp/verify_wp10.py`, 2 gebruikers, echte `SupabaseRest`, httpx-logger op INFO): geen user-id, geen secret, geen titel of body in de request-URL's of in de logtekst. `test_no_user_id_in_request_filters` toetst hetzelfde op de FakeSupabase-filters. Grep op `logger`/`echo` in `jobs/`: `alerts.py` logt alleen aantallen en exception-typen. |
| AC-5 | PASS | `test_users_get_different_windows`: A (min 12) krijgt 10:00-16:00 UTC, B (min 20) krijgt 12:00-15:00 UTC, met verschillende eerste bodyregels. |
| AC-6 | PASS | `test_offshore_never_alerts` (4 regelvarianten x dir 90 en 135, shore-normal 270): 0 events. |
| AC-7 | PASS | Gedrag: alleen `verified: true` geeft alerts. `test_unverified_spot_gives_no_alerts` (0 berichten, 0 staterijen, `ineligible == 1`, en dezelfde setup met `verified=True` geeft 1 bericht). `test_unverified_spot_is_evaluated` voor de evaluatiekant. |
| AC-8 | PASS | `test_cli_jobs.py::test_alerts_run_dry_run_writes_nothing` en `test_admin.py::test_alerts_preview_writes_nothing`: `db.writes == []`. `test_job_alerts.py::test_dry_run` idem, inclusief de opruiming. |
| AC-9 | PASS | `test_profile_set_weight_only` (alleen `weight_kg`, `db.writes == [("update","profiles")]`), `test_profile_set_unknown_option` (`--telegram-chat-id` geeft exit != 0 en "No such option"), `test_rule_set_offshore_rejected` (3 varianten, exit 1, melding "not allowed"/"never ridable", geen writes), `test_favorite_add_unknown_spot` (exit 1). |
| AC-10 | PASS | `.env.example` bevat exact de 7 sleutels, `VAPID_SUBJECT=mailto:`, de rest leeg (`test_env_example_exact` groen). `test_no_telegram_fields` en `test_old_telegram_env_is_ignored` in `test_config.py` groen. Volledige suite: 1254 passed, 24 skipped. |
| AC-11 | NEEDS_LARS | Niet uitvoerbaar zonder Lars' `.env`, auth-user en een `verified: true` favoriet. Commando's staan onder "Voor Lars". |

## Volledige suites
- `cd ingest && uv run pytest`: 1254 passed, 24 skipped. De 24 skips zijn `test_fake_parity` (23) en `test_spots_sync_local` (1), die de lokale Supabase-stack nodig hebben (Docker onbereikbaar, verwacht).
- `uv run ruff check .`: All checks passed. `uv run ruff format --check .`: 99 files already formatted.
- CI op `wp/WP-10` (laatste run, commit `docs(WP-10): verifying`): `db`, `ingest` en `web` success.

## Extra aandachtspunten
1. **Privacy.** Zie AC-4. Spot-id's van favorieten komen wel voor in request-URL's (`spots?id=in.(...)`, `forecast_hours?spot_id=eq.<id>`). Dat staat in de docstring van `shakka.jobs.alerts` (N-1) en wordt afgedekt door de WP-11-eis dat `httpx` en `httpcore` op `WARNING` staan. De eigen MockTransport-run bevestigt dat de `httpx`-logger deze URL's op INFO wel logt. Geen user-id's, geen berichtteksten en geen secret. Geen fail, maar WP-11 moet die eis echt inbouwen.
2. **Geen telegram.** Zie AC-3. `shakka doctor` noemt het ook niet (`test_doctor_never_mentions_telegram`).
3. **Alleen `verified: true`.** `plan_favorite` geeft `ineligible` voor niet-geverifieerde spots vóór enige regel- of evaluatiestap. `enabled=false` geeft `disabled` (`test_disabled_rule`: geen events, staterij ongewijzigd). Spot zonder forecast geeft `ineligible` "no forecast data" (`test_no_forecast_data_keeps_state`): geen events, geen crash, staat blijft staan.
4. **Isolatie.** `test_skipped_favorite_does_not_stop_job`: twee kapotte favorieten (regel-/profielrij) leiden tot `skipped == 2`, en gebruiker C krijgt nog gewoon zijn bericht. Verder `test_broken_state_row_is_skipped_and_unchanged`, `test_write_error_isolated` en `test_update_count_mismatch` (een DatabaseError bij schrijven stopt de job niet). `skipped` of `write_errors` geeft exit 1 in `alerts run`.
5. **Schrijfvolgorde `alert_state`.** In `store_plan`: eerst de updates, gesorteerd op `update_rank` (0 = expired/cancelled, 1 = actief en niet langer, 2 = rest), daarna de inserts. Tests: `test_update_rank` (rangen), `test_write_order_split` (volgorde update, insert, delete), `test_write_order_merge` (`update_calls`: eerst het opgeheven window `expired`, dan het verlengde window).
6. **Beheer-CLI.** Een domeinfout (`AdminError`) geeft exit 1 (`test_favorite_add_unknown_spot`, `test_profile_set_validation`, `test_rule_set_errors`, `test_favorite_add_unknown_user`). `test_parse_quiver` dekt `"7, 9, 12"` gelijk aan `[7.0, 9.0, 12.0]`, `" 10,5 ; 12 "` gelijk aan `[10.5, 12.0]`, `"7,9,12"`, `"10,5"` gelijk aan `[5.0, 10.0]` en ongeldige invoer. `test_quiver_comma_note` dekt de `note:`-regel bij onduidelijke komma's. Het commando `profile set` schrijft alleen de opgegeven velden.

## Harde regels
- Geen secrets in de diff. De enige hit is de nepwaarde `sb_secret_TESTVALUE` in een test.
- Geen client-side Open-Meteo calls. Er is geen web-wijziging. Open-Meteo blijft in `jobs/forecast.py`, dat in deze WP niet is gewijzigd.
- Geen scraping en geen nieuwe betaalde dienst of dependency.
- Bronvermelding is niet geraakt.
- Offshore en side-offshore zijn `no_go` (AC-6). Het commando `rule set` weigert ze (AC-9).
- Geen bestanden buiten de scope gewijzigd. Buiten `ingest/` en `docs/` is alleen `.env.example` gewijzigd, zoals de WP voorschrijft. `docs/RUNBOOK.md` heeft de `TELEGRAM_*`-rijen verloren en een nieuwe sectie 12.
- De diff komt overeen met blueprint revisie 2 (APPROVED). De afwijkingen in `deviations.md` (rood-fase, `updated_at`-controle, gedeelde helpers, extra tests) zijn klein en gedocumenteerd, en geen fail.

## Problemen
Geen.

## Voor Lars (AC-11, NEEDS_LARS)
Nodig: de `.env` met `SUPABASE_URL` en `SUPABASE_SECRET_KEY` (en optioneel `APP_BASE_URL`), een auth-user (Dashboard, Authentication, Add user, kopieer de UUID) en minstens één spot met `verified: true` die gesynct is.
```
cd ingest
uv run shakka spots sync          # na verified: true in data/spots.yaml
uv run shakka forecast fetch
uv run shakka tides fetch
uv run shakka admin profile set --user-id <id> --weight <kg> --level <beginner|intermediate|advanced> --quiver "7 9 12"
uv run shakka admin favorite add --user-id <id> --spot <spot-id>
uv run shakka evaluate
uv run shakka admin alerts preview --user-id <id>    # windows of "geen windows", zonder fouten
uv run shakka alerts run --dry-run                    # nog niets opgeslagen
uv run shakka alerts run                              # bij een window: alert_state-rij in het Dashboard
```
Controleer daarna in het Supabase Dashboard (Table Editor, `alert_state`) dat er een rij met `status = active` en `last_event = new` staat.
