# Review WP-28, ronde 1
Oordeel: APPROVED

## Blokkerend
Geen.

## Niet-blokkerend
N-1: A1 staat in de blueprint als "staat nog niet in STATUS.md", maar STATUS.md (WP-28-rij) legt het besluit al vast; pas A1 en stap 1 aan zodat de builder niet onnodig stopt.
N-2: `test_dependabot_config` toetst `versioning-strategy` en `update-types` niet; een weggehaalde regel valt dan niet op (bewuste keuze, maar noem dat in het testplan).
N-3: `yaml` heeft in ingest mogelijk geen type stubs; draai `uv run ruff check` en eventuele typecheck vóór de commit (pyyaml staat wel al in pyproject).

## Zelf gecontroleerd
- GitHub options reference: `versioning-strategy` ondersteund door npm en uv; `increase-if-necessary` is een geldige waarde (niet per ecosysteem beperkt). R2 is daarmee grotendeels afgedekt.
- `groups`: `patterns` met `*` en `update-types` met `minor`/`patch`/`major` (zonder `version-update:`-prefix) kloppen; `ignore` gebruikt wel `version-update:semver-major`, zoals in de config.
- Bestaande `test_actions_pinned_to_commit_sha` blijft ongewijzigd. Alle 8 `uses:`-regels in `ci.yml` en `hourly.yml` matchen de nieuwe fullmatch-regex (40-hex SHA + `# vX.Y.Z` op dezelfde regel), dus de nieuwe tests breken CI niet.
- STATUS.md regel 37: "besluit Lars (draait WP-22 A17 terug)".
