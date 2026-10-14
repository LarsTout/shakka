# Verificatie WP-04, ronde 1
Resultaat: NEEDS_LARS

| Criterium | Resultaat | Bewijs |
|---|---|---|
| AC-1 | PASS | `test_rws_tides.py`: `test_fixture_count` (35), `test_fixture_levels_are_int`, `test_fixture_times_utc`, `test_offset_plus_one_converted` (12:00+01:00 wordt 11:00Z) groen. `test_fixture_kinds_alternate` staat low→low alleen toe voor `laagwater 1` gevolgd door `laagwater 2` (agger; goedgekeurd in review N-2, blueprint A3). In de huidige fixture is er geen agger, dus feitelijk wisselt het strikt af. |
| AC-2 | PASS | `test_domain_tide.py`: `test_exact_extremes`, `test_halfway` (+100/-80, 6 u: 10), `test_outside_and_empty` (None vóór eerste en na laatste), `test_gap_limit` (9:00:01 geeft None, 9:00:00 geeft waarde) groen. |
| AC-3 | PASS | `test_job_tides.py`: `test_unique_nonempty_stations`, `test_fresh_station_skipped[19-False]` (19 u overgeslagen; 20 en 21 u niet), `test_force_ignores_freshness`, `test_failure_isolated`, `test_cleanup_48h` (filter `at=lt.<now-48h>`, 49 u weg, 48 u blijft) groen. |
| AC-4 | PASS | `uv run shakka tides stations --search "hoek van holland"` (echt netwerk) gaf `hoekvanholland	Hoek van Holland	51.97690	4.11983` plus `hoekvanholland.maeslantkering.beneden.noord`. Zonder filter: 103 regels (101 stations), exit 0. |
| AC-5 | NEEDS_LARS | Docker-daemon niet bereikbaar (`permission denied` op `/var/run/docker.sock`), dus geen lokale stack. De CI-job `db` draait alleen `supabase test db` (pgTAP) en voert `shakka tides fetch` niet uit, dus CI dekt AC-5 niet. Wel zelf gedraaid (echt netwerk): `fetch_tide_extremes("hoekvanholland", now-1d, now+8d)` geeft 35 extremen (≥ 25), kind begint `low, high, low, high...`. Het schrijfpad naar Postgres (upsert + venster-delete met dubbele `at`-filter) is alleen gedekt door FakeSupabase; de parity-tests (`test_fake_parity.py`) zijn hier geskipt. Zie "Nodig van Lars". |

## Suites
- `cd ingest && uv run pytest`: 293 passed, 23 skipped (alle 23 zijn `test_fake_parity.py`, vereisen lokale stack).
- `uv run ruff check .`: All checks passed. `uv run ruff format --check .`: 29 files already formatted.
- CI-run 38632716134 (branch `wp/WP-04`, commit `docs(WP-04): verifying`): job `ingest` success; job `db` liep nog bij afronding.

## Diff vs blueprint
- Bestanden komen overeen met de blueprint-lijst (domain/tide, rws/tides, jobs/tides, cli, capture-script, fixtures, vier testbestanden, RUNBOOK sectie 9, STATUS). Geen bestanden buiten `ingest/` en `docs/` gewijzigd; geen wijzigingen aan bestaande code behalve `cli.py` (additief).
- Afwijking `ddlpy` naar httpx rechtstreeks: bewust, door reviewer goedgekeurd (review N-1), vastgelegd in blueprint (A1/R2). Geen fail. Lars moet er nog akkoord op geven en de stackregel in `PROJECT_PLAN.md` kan later worden aangepast.
- Review-punten N-3 t/m N-6 zijn doorgevoerd en gedocumenteerd in `deviations.md` D1, elk met een test (`test_empty_fetch_keeps_existing_window`, `test_invalid_station_code_fails_only_that_station`, `test_structural_errors`, `test_quality_99_type_skipped`).
- Gedocumenteerde kleinigheden in D2/D3 geverifieerd: RUNBOOK-sectie 9 kan conflicteren met WP-02/WP-03 bij merge (hernummeren, alles behouden).

## Harde regels
- Geen secrets in de diff. De enige treffer is `SECRET = "sb_secret_TESTVALUE"` in `test_cli_tides.py` (nepwaarde).
- Geen Open-Meteo-calls; Rijkswaterstaat wordt alleen server-side in `/ingest` aangeroepen (`test_rws_hosts_only_in_rws_package`). Niets in `/web`.
- Geen scraping: officiële RWS WaterWebservices API (DDAPI20).
- Geen nieuwe betaalde dienst; geen nieuwe dependency (httpx via `make_client`, bestaand).
- Bronvermelding: RUNBOOK noemt Rijkswaterstaat (DDAPI20, CC0). Er is in dit WP geen UI.
- Offshore altijd `no_go`: niet van toepassing op dit WP, niet geraakt.

## Problemen
Geen fails.

## Nodig van Lars (AC-5)
Met Docker en de lokale stack (`supabase start`, migraties toegepast, `SHAKKA_SUPABASE_URL` en secret key in `.env` naar localhost):
1. Voeg een test-spot toe met `rws_station = 'hoekvanholland'` (bijv. via `shakka spots sync` uit WP-02 of een insert in `spots`).
2. `cd ingest && uv run shakka tides fetch --force` moet exit 0 geven en `fetched 1 station(s), 35 row(s)` (of ≥ 25) tonen.
3. Controle: `select count(*) from tide_extremes where station='hoekvanholland' and at > now();` is ≥ 25.
4. Tweede `--force`-run mag het aantal niet laten groeien (idempotent).
Optioneel daarna: `SHAKKA_TEST_SUPABASE_URL=... SHAKKA_TEST_SUPABASE_SECRET_KEY=... uv run pytest tests/test_fake_parity.py`.
