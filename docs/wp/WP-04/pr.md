## WP-04: Getij-ingest (Rijkswaterstaat)

- `shakka.domain.tide`: `TideExtreme` en `estimate_tide_level` (cosinus-interpolatie, `None` bij gat > 9 uur).
- `shakka.rws.tides`: DDAPI20 via `httpx` (geen `ddlpy`: geen timeout, trekt pandas binnen), parsers, `list_tide_stations`.
- `shakka.jobs.tides` en `shakka tides fetch [--force]` / `shakka tides stations [--search]`; 20-uursregel, opruimen na 48 uur.
- Fixture van één echte DDAPI20-respons (Hoek van Holland, 35 extremen); RUNBOOK §10.
- 293 tests op de branch; CI `ingest` + `db` groen.

**Verificatie:** AC-1..4 PASS (AC-4 met echt netwerk). AC-5 (fetch tegen lokale stack) draait Lars na de merge op `develop`; stappen in `docs/wp/WP-04/verification.md`.

**Beslispunten voor Lars:** `httpx` i.p.v. `ddlpy` (daarna stackregel in PROJECT_PLAN/WORK_PACKAGES aanpassen); agger-uitzondering op "kind wisselt af" (gevolg voor WP-05: getijvoorkeur op geschat niveau).

🤖 Generated with [Claude Code](https://claude.com/claude-code)
