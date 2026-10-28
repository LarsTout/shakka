# Verificatie WP-28, ronde 1
Resultaat: PASS (AC-1 en AC-2 gehaald; AC-3 is NEEDS_LARS en staat open, het blokkeert de uitslag niet)

| Criterium | Resultaat | Bewijs |
|---|---|---|
| AC-1 | PASS | `cd ingest && uv run pytest tests/test_repo_hygiene.py -v`: 10 passed, inclusief `test_dependabot_config` en `test_actions_pins_have_version_comment`. De test toetst version 2, precies de drie paren, `monthly`, `target-branch: develop`, limiet 3 en niet-lege `groups`. Mutatie: `target-branch` uit één update gehaald, dan faalt de test met `KeyError: 'target-branch'`. Daarna teruggezet. |
| AC-1 (A8) | PASS | Versiecommentaar uit `ci.yml` gehaald, dan faalt `test_actions_pins_have_version_comment`. Daarna teruggezet. `test_actions_pinned_to_commit_sha` is ongewijzigd en groen. |
| AC-2 | PASS | `docs/RUNBOOK.md` §18.8: rij "Dependabot-PR's" en een alinea "Dependabot en Cloudflare" (preview-build per push, ruwweg 15 per maand, drempel 350 van 500). §18.10: Dependabot, geen secrets, review en handmatige terugval. De tekst is letterlijk gelijk aan Interfaces in de blueprint. De WP zegt "§17", de blueprint legt dat vast als §18.8 en §18.10 (A2). |
| AC-3 | NEEDS_LARS | Pas na de merge naar `develop` te controleren. Zie "Open punt voor Lars". |

## Volledige suites
- `uv run ruff check .`: All checks passed.
- `uv run ruff format --check .`: 137 files already formatted.
- `uv run pytest`: 1737 passed, 24 skipped. De skips komen van de lokale-Supabase-tests zonder `SHAKKA_TEST_SUPABASE_*`, en zijn niet WP-gerelateerd.
- `/web` is niet gewijzigd, dus `npm`-checks zijn niet gedraaid.

## Harde regels
- Diff vergeleken met de blueprint: `.github/dependabot.yml`, de twee tests, RUNBOOK §18.8 en §18.10, en STATUS.md komen overeen met de Interfaces. Er is geen `deviations.md` en ik heb geen afwijking gevonden.
- Geen secrets in de diff. De grep vond alleen de bestaande RUNBOOK-verwijzingen naar sleutelprefixen.
- Geen Open-Meteo-calls, geen scraping, geen nieuwe betaalde dienst, geen wijziging aan bronvermelding of offshore-logica.
- Alleen bestanden binnen de WP-scope zijn gewijzigd: `.github/dependabot.yml`, `ingest/tests/test_repo_hygiene.py`, `docs/RUNBOOK.md`, `docs/STATUS.md` en `docs/wp/WP-28/*`.

## Open punt voor Lars (AC-3)
1. Na de merge naar `develop`: Settings, Advanced Security, "Dependabot alerts" en "Dependabot security updates" op Enable.
2. Insights, Dependency graph, Dependabot: per ecosysteem (`github-actions`, `npm`, `uv`) een geslaagde controle ("Check for updates"). Een schemafout zoals een afgewezen `versioning-strategy: increase-if-necessary` bij `uv` (R2) of een lockfile-fout (R3) zie je daar. Haal in dat geval de regel weg bij `uv` en noteer het in `deviations.md`.
3. Bij de eerste `github-actions`-PR: blijft de SHA-pin staan en wordt `# vX.Y.Z` op dezelfde regel bijgewerkt (E1, E2)? Zo niet, dan beslist Lars of de pin-test of de Dependabot-config wordt aangepast.

## Problemen
Geen.
