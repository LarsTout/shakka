# Afwijkingen WP-17

Geen afwijking raakt een contract, schema, externe API, dependency of acceptatiecriterium.

## Uit review ronde 2 (meegenomen)
- **N-1 (`mailto:`-check na `strip()`).** `notifiers_from_settings` vergelijkt `vapid_subject.strip() == "mailto:"` (en leeg na `strip()`) voor "afwezig". Het subject gaat daarna ongewijzigd naar `WebPushNotifier`, dat zelf strip. Test: `test_notifiers_from_settings_disabled` (o.a. `" mailto: "`).
- **N-2 (`restore_logging` herstelt ook `urllib3`).** In `tests/test_cli_pipeline.py` en `tests/test_logsetup.py` herstelt de fixture nu alle `QUIET_LOGGERS`.
- **N-4 (VAPID-configuratie vóór de stale-check).** Kon zonder herstructurering: in `step_alerts` staat `notifiers = ctx.notifiers ... or notifiers_from_settings(...)` nu als eerste regel, vóór de stale-controle. Een configuratiefout laat de stap daardoor ook `failed` worden in een run waarin alerts anders `skipped` (stale_forecast) waren; de blueprint plaatste dit na de stale-regel. Het bouwen van de notifiers heeft geen bijwerkingen (geen netwerk, geen database). De push-disabled-warning en de log komen wel pas na de stale-check (alleen bij een echt draaiende stap). Test: `test_hourly_incomplete_vapid_fails_even_when_stale`.

## Kleine afwijkingen
- `PushTarget.from_row` roept de constructor met keyword-argumenten aan en leest ontbrekende sleutels als `None`; de `__post_init__` maakt daar `ValueError("push target fields must be non-empty strings")` van (zelfde gedrag als in de blueprint, alleen expliciet).
- `TestPushResult` heeft `__test__ = False`, zodat pytest de klasse niet als testklasse ziet.
- `RecordingWebpush` (tests) bewaart ook `claims_obj` (de doorgegeven dict) naast een kopie van de claims, omdat `id()` van een vrijgegeven dict hergebruikt kan worden; `test_fresh_claims_per_call` vergelijkt met `is not` in plaats van `claims_id`.
- Extra tests: `test_payload_validation` (push_text), `test_hourly_incomplete_vapid_fails_even_when_stale`, `test_update_subscriptions_naive_now`.
- `run_test_push_cli` en `run_vapid_keys_cli` staan al in de commit van stap 8 (zoals het stappenplan), niet in stap 5.
- `tests/test_notify_webpush.py::test_subject_invalid` controleert dat `"example"` niet in de foutmelding staat (de vaste tekst bevat zelf `mailto:`).

## Niet kunnen uitvoeren in deze omgeving
- `supabase db reset` en `supabase test db` (Docker niet bereikbaar): de migratie, `05_push_subscriptions.test.sql` (32 asserts, geteld) en de wijzigingen in `01_schema.test.sql` zijn niet lokaal gedraaid. Het bewijs komt van de CI-job `db`. Een fout daar is een fout in de SQL-tests of migratie van deze WP.
