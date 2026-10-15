# Verificatie WP-19, ronde 2
Resultaat: NEEDS_LARS

CI-run 38776279899 (commit `9e92c83`, branch `wp/WP-19`): conclusie `success`; jobs `ingest`, `db` en `web` alle `success`. Job `db`, stap `supabase test db`: `Files=8, Tests=425, Result: PASS`. `01`, `03`, `05`, `06`, `07` en `08` zijn expliciet `ok` in de log (`02` en `04` ook, geen fail). Het enige openstaande punt is `supabase db push` door Lars (NEEDS_LARS by design).

Ronde 1 had één bevinding (F-1, assert 112 in `07_sessions.test.sql`). Die is hersteld.

| Criterium | Resultaat | Bewijs |
|---|---|---|
| AC-1 (`supabase test db` groen; anon/authenticated-rechten) | PASS | CI `db` op `9e92c83`: `Files=8, Tests=425, Result: PASS`; `07_sessions.test.sql ... ok`. |
| AC-2 (eigen sessie, slug-regex, geen vreemde `organizer_id`, geen update van andermans sessie) | PASS | `07` groen in CI (ronde 1: tests 74-92; ongewijzigd). |
| AC-3 (`get_public_session`: sleutels, onbekende slug `null`) | PASS | `08_session_rpcs.test.sql ... ok` in CI. |
| AC-4 (token, update/delete, hash is niet token) | PASS | `08` groen in CI; statische controle uit ronde 1 ongewijzigd (`extensions.gen_random_bytes(32)`, alleen sha256-hex opgeslagen, lookup op hash). |
| AC-5 (30/10 min/geannuleerd/validatie/tikkie/11e sessie) | PASS | `07` en `08` groen in CI. |
| AC-6 (purge: strikt `< p_now - 7 dagen`, cascade, alleen service_role) | PASS | `07` en `08` groen in CI. |
| AC-7 (`STEPS` eindigt op `sessions_cleanup`, falen geeft `partial`) | PASS | In `/ingest`: `uv run pytest` (inclusief `test_pipeline.py`, `test_migrations.py`, `test_jobs_sessions.py`, `test_fakes.py`) groen. |
| Suite lokaal | PASS | `cd ingest && uv run pytest`: 1569 passed, 24 skipped (parity/lokale Supabase, by design). `uv run ruff check .`: All checks passed. `uv run ruff format --check .`: 130 files already formatted. |
| `supabase db push` door Lars | NEEDS_LARS | Remote push na merge (RUNBOOK §16.2); niet te verifiëren hier. |

## Herstel F-1
- `git diff c4e66f8..9e92c83 --stat`: alleen `supabase/tests/07_sessions.test.sql` (1 regel), `docs/wp/WP-19/deviations.md` (1 regel) en `docs/wp/WP-19/verification.md` (ronde 1).
- Assert 112 verwacht weer `'23503'` (blueprint-conform). `deviations.md` zegt nu correct dat de blueprint gelijk had en dat het eerdere bewijs van de scratch-Postgres vals was. Geen ongedocumenteerde afwijking.

## Harde regels
Ongewijzigd t.o.v. ronde 1 (de diff sinds `c4e66f8` raakt geen code, migratie of config): geen secrets, geen wijzigingen buiten `docs/`, `ingest/`, `supabase/`, geen client-side Open-Meteo, geen scraping, geen nieuwe betaalde dienst, bronvermelding en offshore-regel niet geraakt. Migratie komt overeen met de blueprint op de gedocumenteerde afwijkingen na (pgcrypto-guard, tokennotitie, `if not found` in `rsvp_update`); alle RPC's `security definer` met `search_path = ''` en expliciete grants.

## Problemen
Geen. F-1 is opgelost.
