# Afwijkingen WP-10

Geen afwijking raakt een contract, schema, externe API, dependency of acceptatiecriterium.

## Meegenomen uit review ronde 2 (opdracht orchestrator)
- **N-1**: één zin over spot-id's in request-URL's (`spots?id=in.(...)`, `forecast_hours?spot_id=eq.<id>`) in de module-docstring van `shakka.jobs.alerts`; het restlek wordt afgedekt door de WP-11-eis (`httpx`/`httpcore` op `WARNING`).
- **N-2**: het gedrag "kapotte regel-/profiel-/staterij plus geen forecast = `skipped` (exit 1), niet `ineligible`" staat in de module-docstring en in de docstring van `plan_favorite`. Test: `test_broken_rule_without_forecast_is_skipped_not_ineligible`.
- **N-3**: `"7, 9, 12"` -> `[7.0, 9.0, 12.0]` toegevoegd aan `test_parse_quiver`.

## Klein, genoteerd en doorgegaan
- **Rood-fase.** Per stap zijn tests en implementatie in dezelfde stap geschreven en niet apart als rood gecommit; alle tests draaien groen per commit.
- **`test_profile_set_weight_only`**: de controle "`updated_at` na" is weggelaten, omdat `FakeSupabase` een vaste klok heeft (2026-01-01). Gecontroleerd zijn: `weight_kg` 80, alle andere kolommen gelijk, `db.writes == [("update", "profiles")]`.
- **`require_aware`** is een gedeelde helper in `shakka.jobs.inputs` (naïeve `now` -> `ValueError`), hergebruikt door evaluate, alerts en `delete_old_alert_state`. Idem `format_profile` en `format_preview` in `shakka.jobs.admin` voor de uitvoerregels (de CLI-closures roepen ze aan).
- **`run_admin`** meldt een onvolledige config met het vaste label `admin:` zoals in de blueprint (niet met het commandolabel).
- **Extra tests**: `test_floor_hour`, `test_invalid_user_id_rejected_by_click`, `test_broken_rule_without_forecast_is_skipped_not_ineligible`, `test_alerts_preview_not_eligible`.
- **Stale-test volgorde**: `load_inputs` sorteert op `(valid_at, model.value)`, dus binnen één uur staat `ecmwf` vóór `icon`; de test verwacht dat.
- **Niet uitgevoerd (Docker onbereikbaar)**: tests tegen de lokale stack (`test_fake_parity`, `test_spots_sync_local`) worden overgeslagen (24 skipped, zoals vóór deze WP).
- **AC-11** blijft `NEEDS_LARS` (echte `.env`, auth-user, geverifieerde spot).
