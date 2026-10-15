# Verificatie WP-19, ronde 1
Resultaat: FAIL

CI-run 38775836293 (commit c4e66f8), job `db`: `Files=8, Tests=425, Result: FAIL`. Alleen `07_sessions.test.sql` faalt, test 112 (1 van 112). `01`, `02`, `03`, `04`, `05`, `06` en `08` zijn ok. Jobs `web` en `ingest` groen.

| Criterium | Resultaat | Bewijs |
|---|---|---|
| AC-1 (`supabase test db` groen; anon/authenticated-rechten) | FAIL | CI `db`: `07_sessions.test.sql` test 112 faalt (zie F-1). De rechten-asserts 12-34 en 95-104 zijn groen in dezelfde run. |
| AC-2 (eigen sessie, slug-regex, geen vreemde `organizer_id`, geen update van andermans sessie) | PASS | `07` tests 74-92 groen in CI (43 `.`-asserts incl. 42501 bij vreemde `organizer_id`). |
| AC-3 (`get_public_session`: sleutels, onbekende slug `null`) | PASS | `08` tests 1-9 en extra's groen in CI (`08 ... ok`, 71 asserts). |
| AC-4 (token, update/delete, hash is niet token) | PASS | `08` tests 10-20, 45-53 groen in CI; statische controle: `extensions.gen_random_bytes(32)`, alleen `sha256` hex opgeslagen, lookup op hash. |
| AC-5 (30/10 min/geannuleerd/validatie/tikkie/11e sessie) | PASS | `08` tests 21-39 en `07` tests 45-61, 90-91 groen in CI. |
| AC-6 (purge: strikt `< p_now - 7 dagen`, cascade, alleen service_role) | PASS | `08` tests 54-62 plus extra's groen in CI; `07` test 42 (service_role mag exact `purge_expired_sessions`). |
| AC-7 (`STEPS` eindigt op `sessions_cleanup`, falen geeft `partial`) | PASS | `cd ingest && uv run pytest tests/test_pipeline.py tests/test_migrations.py tests/test_jobs_sessions.py tests/test_fakes.py`: 119 passed. |
| Suite lokaal | PASS | `uv run pytest`: 1569 passed, 24 skipped (parity/lokale Supabase, by design). `ruff check` en `ruff format --check` groen. |
| `supabase db push` door Lars | NEEDS_LARS | Remote push na merge (RUNBOOK §16.2); niet te verifieren hier. |

## Harde regels
- Geen secrets in de diff (grep op sleutelpatronen leeg). Geen wijzigingen buiten scope: alleen `docs/`, `ingest/`, `supabase/`; `web/`, `.github/`, `pyproject.toml` en `uv.lock` onaangeroerd. Geen nieuwe dependency.
- Geen client-side Open-Meteo, geen scraping, geen betaalde dienst. Bronvermelding niet geraakt. Offshore-regel niet geraakt (domeinlogica ongewijzigd).
- Migratie regel voor regel gelezen en met de blueprint-SQL gediffd: alleen de gedocumenteerde afwijkingen (pgcrypto-guard, tokennotitie in de kop, `if not found` in `rsvp_update`).
  1. `rsvps`: geen enkele grant aan anon/authenticated/service_role; geen policies. `sessions`: alleen select (tabel), insert op 9 en update op 9 kolommen; update zonder `slug`/`organizer_id`/`created_at`/`id`/`recent_rsvp_creates`. `organizer_id` staat wel in de INSERT-grant (nodig voor de `with check`; de blueprint wil dit zo, en RLS dwingt `= auth.uid()` af, test 77 toont 42501 bij vreemde id). Geen finding.
  2. Alle vier publieke RPC's en `purge_expired_sessions`: `security definer`, `set search_path = ''`, `public.`/`extensions.` gekwalificeerd (builtins via `pg_catalog`), `revoke all ... from public, anon, authenticated, service_role` vóór `grant execute`. Purge alleen `service_role`. pgTAP 07 legt per rol de uitvoerbare functies vast (groen in CI).
  3. Token: `extensions.gen_random_bytes(32)`, 43 tekens base64url, alleen sha256-hex opgeslagen, lookup op hash, token komt in geen `raise`. `get_public_session` geeft geen `organizer_id`, hashes, `cancelled_at` (alleen boolean `cancelled`) of `recent_rsvp_creates`.
  4. Sessielimiet 10/24 u in de trigger met advisory lock; RSVP-limiet via `recent_rsvp_creates`, alleen door de RPC geschreven (kolom niet in grant, test 85 groen).
  5. Alle RPC-fouten zijn `PT400` met de code als message.
  6. Python: `sessions_cleanup` is de laatste stap; `SESSION_RETENTION` = 7 dagen, gelijk aan `interval '7 days'` (`test_session_retention_matches_migration` groen); log bevat alleen `purged=<aantal>`.

## Problemen
F-1: `supabase/tests/07_sessions.test.sql` assert 112 (`a spot with sessions cannot be deleted (restrict)`) verwacht SQLSTATE `23001`, maar echte Postgres in CI geeft `23503` (`caught: 23503: update or delete on table "spots" violates foreign key constraint "sessions_spot_id_fkey"`). De "correctie" in `deviations.md` (blueprint-fout E36, `restrict_violation` 23001) is onjuist: een FK-`on delete restrict` rapporteert via de RI-trigger `23503`; de blueprint had gelijk en de eigen scratch-Postgres/mini-pgTAP gaf een vals bewijs. Fix: assert 112 terug naar `'23503'` en `deviations.md` ("Fout in de blueprint" E36/assert 107) en edge case E36 corrigeren. Reproduceren: `gh run view 38775836293 --log-failed` (job `db`, stap `supabase test db`).
