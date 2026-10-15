# Afwijkingen WP-12

Geen afwijkingen die een contract, schema, externe API, dependency of acceptatiecriterium raken. Alles hieronder is klein en genoteerd.

## Uit de review (niet-blokkerend) verwerkt
- **N-1:** de pgTAP-asserts 14, 18 en 20 in `supabase/tests/06_marine_hours.test.sql` filteren op `spot_id = 'pgtap-spot'` (count = 2, `is_empty` na cascade), zodat ze niet van een lege tabel afhangen. Aantal asserts blijft 20. De RUNBOOK-sectie noemt dit.
- **N-2:** `formatMeters` is `(Math.floor(x * 10 + 0.5) / 10).toFixed(1).replace('.', ',')`. Geen `toLocaleString`. De testvoorbeelden (1.24, 1.25, 0, 0.84, 2) staan niet op binaire randwaarden zoals 1.15.
- **N-3:** de golfnotitie op de spotpagina verschijnt alleen als minstens één golfregel zichtbaar is (afgeleide `anyWaveVisible` op basis van `visibleHours(g.hours, showDark)`), niet bij `waves.size > 0`. Extra test: golfrij alleen voor een donker uur geeft geen notitie.
- **N-4:** laten zoals de blueprint (twee fallbackplekken, spiegelt `forecast_fetch`). Extra test `test_marine_fallback_looks_up_module_function` dekt de route zonder `marine_fetch`.
- **N-5:** E27 wordt gedekt door `test_job_database_error_propagates` plus de generieke `run_step`-tests van WP-11; `test_marine_exception_is_partial_run` gebruikt een `RuntimeError`.
- **N-6:** `test_cli_marine.py` gebruikt een kleine subklasse `ClosingFake` met een sluitteller; `fakes.py` is hiervoor niet aangepast (alleen de cascade van `marine_hours` bij `spots`).
- **N-7:** EWAM levert live ca. 80 uur (79 niet-null waarden van 168 in de fixture, kust en IJsselmeer), niet de 8 dagen uit de Open-Meteo-docs. Vastgelegd in fixture en RUNBOOK §15; A1 blijft nodig.
- **N-8:** `formatKn` hergebruikt voor seconden, naam ongewijzigd.

## Kleine afwijkingen
- Tests en implementatie voor stappen 4 tot en met 6 zijn in dezelfde commit geschreven (tests eerst opgezet, geen aparte rode commit).
- `test_job_fixture_end_to_end` gebruikt een `now` vlak na het eerste fixtureuur, zodat de opruiming de gefixeerde rijen niet verwijdert.
- `run-hourly`-docstring is over drie regels verdeeld (E501, 100 tekens); inhoud gelijk aan de blueprint.
- RUNBOOK-sectienummer is 15 (eerstvolgende vrije op deze branch); bij een merge met WP-15/WP-16 kan het verschuiven.
- `web/.env` (gitignored) is lokaal aangemaakt uit URL en publishable key; niets gecommit.

## Niet uitgevoerd
- **AC-5 (live `shakka marine fetch` tegen de lokale stack):** niet gedraaid, omdat de draaiende Docker-stack (`supabase_db_shakka`) die van de hoofdrepo is en de migratie daar niet is toegepast (`supabase db push`/`db reset` op de gedeelde stack valt buiten mijn worktree). Verifier draait dit volgens RUNBOOK §15.6.
- **pgTAP:** wel gedraaid, zonder `supabase` CLI (niet geinstalleerd): in een tijdelijke scratch-database (schema-dump van de lokale stack plus de migraties `20261015150000` en `20261015180000`) alle bestanden `01` t/m `06` met psql; alle asserts `ok` (01: 71, 06: 20). Scratch-database daarna verwijderd. CI-job `db` draait de officiele run.
