# Verificatie WP-01, ronde 1
Resultaat: NEEDS_LARS

Alleen AC-7 (remote `supabase db push`) staat open en is bewust voor Lars. Alle andere criteria zijn gehaald.

Omgeving: de Docker-socket is voor deze sessie niet toegankelijk (`permission denied while trying to connect to the Docker daemon socket`). `supabase start`, `supabase db reset` en `supabase test db` zijn dus niet lokaal gedraaid. Het bewijs voor AC-1, AC-2 en AC-5 komt uit CI-run 38622163821. Die run staat op `headSha 8a982c79ffe156c2e97906e439e67fb94d16b654`, en dat is de huidige HEAD van `wp/WP-01`. Conclusie `success`, event `push`.

| Criterium | Resultaat | Bewijs |
|---|---|---|
| AC-1 (migraties foutloos toegepast) | PASS | Niet lokaal te draaien (zie boven). Job `db` log: `Applying migration 20261015090000_m1_schema.sql...`, `Applying migration 20261015090100_m1_security.sql...`, `Started supabase local development setup.` Geen `ERROR` in de log. `supabase start` past dezelfde migraties toe op een lege stack. |
| AC-2 (a) tabellen en kolommen | PASS | CI `supabase test db`: `01_schema.test.sql ok` (tables_are, columns_are, 86-kolommen-set_eq, col_is_pk, FK-set_eq, CHECK-tests). `Files=4, Tests=190, Result: PASS`. |
| AC-2 (b) anon leest 4 leestabellen, geen schrijfacties | PASS | `03_rls_anon.test.sql ok`: 4x `results_eq` count 1, 12x `throws_ok ... '42501'` voor insert/update/delete. Bronbestand gelezen: de asserts toetsen echt de genoemde acties. |
| AC-2 (c) anon leest 0 rijen uit privé-tabellen | PASS | `03_rls_anon.test.sql` asserts 17-22: `throws_ok('select * from public.<t>', '42501')` voor `profiles`, `favorites`, `alert_rules`, `alert_state`, `api_usage` en `ingest_runs`. Zo goedgekeurd in blueprint A3 en review ronde 1 (N-4): anon heeft geen grant, dus er komt geen rij terug. Migratie `m1_security.sql` bevestigt: geen enkele grant of policy voor `anon` op die tabellen. |
| AC-2 (d) A kan B's data niet lezen of wijzigen | PASS | `04_rls_users.test.sql ok` (42 asserts, secties d): `is_empty` voor B's rijen, `lives_ok` op wijzigingen die 0 rijen raken, `throws_ok 42501` op inserts voor B, en daarna controle als `postgres` dat B's data ongewijzigd is. |
| AC-2 (e) `telegram_chat_id` niet te wijzigen | PASS | `04`: assert 22 `throws_ok ... '42501'` op update van `telegram_chat_id` als A; asserts 24-25 tonen dat andere kolommen wel wijzigen en `telegram_chat_id` null blijft. `02_privileges` (`column_privs_are`) ok. Migratie: `grant update (weight_kg, level, quiver_m2, default_min_kn, default_max_kn)`. |
| AC-2 (f) insert in `auth.users` maakt profiel | PASS | `04`: asserts 1-2 (2 profielen na 2 inserts, `quiver_m2 = '{}'`). `01` toetst `has_trigger` op `auth.users`. |
| AC-2 (g) `dir_classes` met offshore geweigerd | PASS | `04`: asserts 27-32 (`23514` voor `side_offshore`, `offshore`, gemengd, leeg, NULL-element, ook als A), assert 33 `lives_ok` met geldige klassen. Migratie regel 134-138: CHECK `dir_classes <@ array['onshore','side_onshore','sideshore']`. |
| AC-2 (h) favoriet verwijderen verwijdert regel | PASS | `04`: assert 37-38 (als A favoriet verwijderen, `is_empty` op `alert_rules`), 39-42 cascade bij `auth.users`-delete. |
| AC-3 (`tests/test_db.py`) | PASS | `uv run pytest` in `ingest/`: 202 passed, 23 skipped. `tests/test_db.py` 64 tests groen. Gelezen: key-in-header-not-url, filterserialisatie, `on_conflict` en `Prefer: resolution=merge-duplicates`, paginering (2500 rijen, exact paginabeveel, korte pagina's), batches van 500 (1201 rijen -> 500/500/201), `ValueError` zonder filters, `DatabaseError` zonder secret in melding. Geen `authorization`-header, alleen `apikey`. |
| AC-4 (`tests/test_fakes.py`) | PASS | 47 tests groen (`test_filter_cases` over alle operatoren, `test_writes_recorded`, `test_signatures_match_client`, `test_order_tiebreak_matches_client`). `tests/test_fake_parity.py` is niet uitgevoerd (23 skipped: geen lokale stack, Docker niet toegankelijk). Zoals de blueprint voorschrijft steunt AC-4 dan op de handmatig afgeleide verwachtingen in `fake_cases.py`. |
| AC-5 (CI-job `db` groen) | PASS | `gh run view 38622163821`: jobs `db` (1m47s) en `ingest` (10s) groen. Workflow draait op `push` en `pull_request`. Job `db` voert `supabase start -x ...` en `supabase test db` uit (CLI 2.121.0, action op commit-SHA gepind). `tests/test_repo_hygiene.py::test_ci_workflow_contract` groen. |
| AC-6 (geen latere tabellen) | PASS | `grep -rniE "create table[^;]*(sessions\|rsvps\|push_subscriptions\|marine_hours)" supabase/migrations` geeft geen treffers (exit 1). `test_migrations.py::test_no_later_milestone_tables` groen. |
| AC-7 (remote toegepast) | NEEDS_LARS | Lars volgt `docs/RUNBOOK.md` sectie 8.3: `supabase link --project-ref <ref>`, `supabase db push --dry-run`, `supabase db push`, daarna `supabase migration list --linked` met beide migraties als toegepast. Niet door de verifier uit te voeren (geen toegangstoken/databasewachtwoord). |

## Harde regels
- Lint en tests: `uv run ruff check .` (All checks passed), `uv run ruff format --check .` (19 files already formatted), `uv run pytest` (202 passed, 23 skipped).
- Geen secrets in de diff of in de werkboom: grep op `sb_(secret|publishable)_...` en `eyJhbGciOi` in `ingest/` en `supabase/` geeft geen treffers. `.env` bestaat in de worktree maar is gitignored en niet getrackt. `test_no_keys_in_repo` groen. CI gebruikt geen secrets.
- Geen client-side Open-Meteo: de diff bevat geen `/web`. De enige verwijzing is de CHECK-waarde `open_meteo_forecast`/`open_meteo_marine` in `api_usage.source`. Geen HTTP-calls naar Open-Meteo.
- Geen scraping, geen nieuwe betaalde dienst (alleen Supabase gratis tier en GitHub Actions; geen nieuwe Python-packages).
- Bronvermelding: geen UI in deze WP; er is niets aangeraakt of verwijderd.
- Offshore altijd `no_go`: in de database afgedwongen door CHECK `evaluations_offshore_is_no_go` en CHECK op `alert_rules.dir_classes`; beide getoetst in pgTAP (`01` en `04`) en groen in CI.
- RLS aan op alle 10 tabellen, expliciete `revoke all` en grants per rol, `auto_expose_new_tables = false` in `config.toml`. Triggerfuncties zijn niet aanroepbaar via de API (`function_privs_are` ok).

## Diff tegenover blueprint en scope
- De gewijzigde bestanden komen overeen met de bestandstabel van de blueprint (migraties, pgTAP, `db.py`, `fakes.py`, `fake_cases.py`, tests, CI-job, `config.toml`, RUNBOOK, STATUS). Geen bestanden buiten de WP-scope.
- Afwijkingen zijn gedocumenteerd in `docs/wp/WP-01/deviations.md` (D1: geen lokale Docker voor de builder; D2: extra interne helpers in `shakka.db`). Geen ongedocumenteerde afwijkingen gevonden.
- `docs/STATUS.md` staat op `verifying`, correct voor dit moment.

## Problemen
Geen blokkerende problemen.

Opmerkingen (geen fail):
- O-1: AC-1 en `test_fake_parity.py` zijn niet lokaal gedraaid wegens ontbrekende Docker-toegang (D1 in `deviations.md`). Wil Lars de pariteit tegen echt PostgREST bevestigen: draai lokaal `supabase start`, daarna het commando uit RUNBOOK sectie 6 (`SHAKKA_TEST_SUPABASE_URL=http://127.0.0.1:54321 SHAKKA_TEST_SUPABASE_SECRET_KEY=<lokale key> uv run pytest tests/test_fake_parity.py`).
- O-2: Lokaal staat Supabase CLI 2.120.0; CI en blueprint gebruiken 2.121.0. Geen invloed op de uitkomst.
