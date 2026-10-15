# Verificatie WP-06, ronde 1
Resultaat: NEEDS_LARS

| Criterium | Resultaat | Bewijs |
|---|---|---|
| AC-1 | PASS | `cd ingest && uv run pytest tests/test_kite.py`: 150 passed. `test_example` is geparametriseerd over alle 26 gevallen en toetst `size_m2`, `ideal_size_m2` en `fit`. De fixture is byte-identiek aan de YAML in de blueprint (programmatisch vergeleken). |
| AC-2 | NEEDS_LARS | `ingest/tests/fixtures/kite_examples.yaml` regel 9: `checked_by_lars: false`. Lars moet de 26 gevallen controleren en de waarde op `true` zetten. Verwacht, geen fout. |
| AC-3 | PASS | `test_size_always_from_quiver` (6 quivers x 3 niveaus x 13 gewichten x 65 winden), `test_empty_quiver_gives_none` (ook `recommend_for_window`) en `test_single_kite_always_chosen` zijn groen. De gewichten (50-110, stap 5), winden (8-40) en 6 quivers komen overeen met het criterium (minstens 4). |
| AC-4 | PASS | `test_more_wind_never_bigger` en `test_ideal_monotone_in_wind_fine_grid` toetsen `size_m2` en `ideal_size_m2` op niet-stijgend. Aanvullend door mij uitgevoerd met een eigen script: alle gewichten 30-200, 3 niveaus, wind 1,0-100,0 in stappen van 0,1, quiver (5, 7, 9, 12, 14, 17): 0 schendingen. |
| AC-5 | PASS | `test_heavier_never_smaller_ideal` (gewicht 30-200, stap 1, alle niveaus, 65 winden) en `test_heavier_never_smaller_size` zijn groen. Eigen script: alle niveaus x wind 1,0-100,0 (stap 0,1) x gewicht 30-200: 0 schendingen. |
| AC-6 | PASS | `test_window_uses_upper_median` ([12, 18, 25, 14] geeft 18 kn, ideaal 9,2, maat 9, en verschilt van gemiddelde, mediaan en maximum), `test_window_upper_median_changes_size_too`, `_odd_length`, `_order_invariant` (alle permutaties), `_single_hour`, `_empty` en `_invalid_value` zijn groen. Implementatie gebruikt `statistics.median_high` zoals A5. |

Volledige suites (in `/Users/larst/Dev/Shakka/.claude/worktrees/WP-06/ingest`):
- `uv run pytest`: 745 passed, 24 skipped (de skips zijn bestaande Supabase-lokaal-tests die env-variabelen vragen, niet van WP-06).
- `uv run ruff check .`: All checks passed.
- `uv run ruff format --check .`: 60 files already formatted.
- `uv run pytest tests/test_domain_purity.py`: 31 passed (dekt `kite.py` automatisch).
- CI `wp/WP-06` (run 38717590447, commit 8a900c8): jobs `ingest` en `web` success; job `db` liep nog op het moment van schrijven (raakt deze WP niet: geen wijzigingen in `supabase/` of `web/`).

## Harde regels
- Puurheid `shakka.domain.kite`: imports zijn uitsluitend `math`, `statistics`, `collections.abc`, `enum`, `types`, `typing`, `pydantic`, `shakka.domain.spot`; geen I/O, geen klok, geen random. Puurheidstest groen. PASS.
- Geen secrets in de diff (grep op secret/key/token/http: alleen bronlinks in blueprint/review). PASS.
- Geen Open-Meteo-calls, geen scraping, geen nieuwe dienst of dependency (`pyproject.toml` ongewijzigd). Bronnen voor de formule zijn alleen als documentatie geciteerd. PASS.
- Bronvermelding in de app: niet geraakt (geen web-wijzigingen). PASS.
- Offshore altijd `no_go`: niet geraakt; kite-advies raakt de evaluatie niet. PASS.

## Diff versus blueprint en scope
Gewijzigde bestanden: `docs/STATUS.md` (alleen WP-06 `verifying`), `docs/wp/WP-06/{blueprint,deviations,review}.md`, `ingest/src/shakka/domain/kite.py`, `ingest/tests/fixtures/kite_examples.yaml`, `ingest/tests/test_kite.py`. Dit is precies de bestandenlijst van de blueprint; niets buiten scope.
`kite.py` volgt de blueprint: constanten, A2 (half-up), A3 (kwadraatvergelijking, tie naar kleiner), A4 (1,25 inclusief), A5, A6, A8. De overgenomen N-2, N-4, N-5 en de kleine afwijkingen (stappenvolgorde, drie extra tests) staan in `deviations.md`; geen afwijking raakt een contract of criterium.

## Problemen
Geen.
