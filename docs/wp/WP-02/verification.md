# Verificatie WP-02, ronde 1
Resultaat: NEEDS_LARS

Alleen AC-6 (sync tegen echt Postgres) kan niet in deze omgeving worden aangetoond. Alle andere criteria zijn PASS.

| Criterium | Resultaat | Bewijs |
|---|---|---|
| AC-1 | PASS | `cd ingest && uv run shakka spots validate` geeft exit 0 met `ok      25 spots valid (0 verified)` en `spots validate: ok`. `test_spots_cli.py::test_validate_default_path` en `test_spots_data.py::test_data_file_is_valid` zijn groen. |
| AC-2 | PASS | De `yaml.safe_load`-controle uit het testplan toont precies de 25 contract-id's in de volgorde van het plan. De namen kloppen met het plan, elke spot heeft `verified False` en de sleutels `['id', 'name', 'verified']`. `git diff` van `data/spots.yaml` is een nieuw bestand met alleen die drie sleutels per spot. |
| AC-3 | PASS | `uv run pytest tests/test_spots_validation.py` is groen. Handmatige steekproef met een bestand met fouten: `spots[1] (zz-ok): lon: required when lat is set`, `spots[2] (zz-t): season[0].from_time: ... expected a quoted 'HH:MM' time`, `spots[3] (zz-t): id: duplicate of spots[2]`. Alle fouten staan in één run (6 fouten, exit 1). `shakka spots sync --path` op dat bestand geeft `nothing written`. |
| AC-4 | PASS | `tests/test_spot_model.py` groen, inclusief `test_to_row_columns_match_migration` en `test_roundtrip`. |
| AC-5 | PASS | `tests/test_spots_sync.py` (8 tests) groen. `sync.py` bevat geen `delete`-aanroep (grep). Een tweede sync schrijft niets, wezen worden alleen gemeld. |
| AC-6 | NEEDS_LARS | Docker is niet bereikbaar (`permission denied` op de socket), dus `supabase start`, `db reset` en de echte sync zijn niet gedraaid. CI-run 38632644683 is groen (job `ingest` en job `db`), maar de job `db` draait alleen `supabase start` en `supabase test db` (pgTAP van WP-01). Hij synct geen 25 spots. `test_spots_sync_local.py` wordt zonder env overgeslagen. Zie "Nodig van Lars". |
| AC-7 | PASS | `tests/test_spot_docs.py` groen (alle 17 kolomnamen, `270`, `verified: true`, `shakka tides stations`, `shakka spots validate`, `NKV`). |
| Regressie | PASS | `uv run pytest`: 324 passed, 24 skipped (alle skips zijn Supabase-env-afhankelijk: `test_fake_parity` en `test_spots_sync_local`). `uv run ruff check .` geeft `All checks passed!`. `uv run ruff format --check .` geeft `32 files already formatted`. `test_domain_purity.py` en `test_repo_hygiene.py` zijn groen. |
| CI | PASS | `gh run view 38632644683`: status completed, success, beide jobs groen. |

## Harde regels
- Geen secrets in de diff: `git grep --untracked -nE "sb_(secret|publishable)_[A-Za-z0-9_-]{20,}|eyJhbGciOi" -- . ':!docs'` geeft geen treffers.
- Geen client-side Open-Meteo, geen scraping en geen nieuwe dienst. Alleen `pyyaml` is toegevoegd, het is gratis en komt uit het blueprint.
- Bronvermelding: er is niets aan `/web` of de bronvermelding gewijzigd.
- Offshore blijft `no_go`: dit raakt WP-02 niet. `SPOT_DATA.md` en de blueprint zeggen dat `ridable_dirs` offshore nooit rijdbaar maakt.
- Geen feitelijke spotdata verzonnen: de startset heeft alleen `id`, `name` en `verified: false`.
- Scope: de gewijzigde bestanden komen overeen met de bestandentabel van de blueprint. Daarnaast zijn alleen `docs/STATUS.md` (de orchestrator zette de status op verifying) en de docs onder `docs/wp/WP-02/` aangepast. `pyproject.toml` heeft één regel extra en `uv.lock` is bijgewerkt.
- Afwijkingen: `deviations.md` documenteert D1 (geen Docker) en D2 (kleine punten). Ik vond geen ongedocumenteerde afwijking.

## Problemen
Geen FAIL-bevindingen.

## Nodig van Lars (AC-6)
Vanuit de repo-root `supabase start` en `supabase db reset`. Vanuit `ingest/`, met de lokale secret key uit `supabase status` alleen als env:
```
SUPABASE_URL=http://127.0.0.1:54321 SUPABASE_SECRET_KEY=<local> uv run shakka spots sync
SUPABASE_URL=http://127.0.0.1:54321 SUPABASE_SECRET_KEY=<local> uv run python -c "from shakka.config import get_settings; from shakka.db import SupabaseRest; print(len(SupabaseRest.from_settings(get_settings()).select('spots', columns='id')))"
SHAKKA_TEST_SUPABASE_URL=http://127.0.0.1:54321 SHAKKA_TEST_SUPABASE_SECRET_KEY=<local> uv run pytest tests/test_spots_sync_local.py
```
Verwacht: de eerste sync meldt `25 of 25 spots upserted`, de telling geeft 25, de tweede sync meldt `0 of 25 spots upserted (25 unchanged)` en de lokale test slaagt.
