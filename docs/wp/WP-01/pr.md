## WP-01: Datamodel M1, RLS en database-client

### Wat er nu werkt
- Twee migraties in `supabase/migrations/` met alle M1-tabellen: enum-CHECKs, indexen, `updated_at`-triggers, automatische `profiles`-rij per nieuwe gebruiker, RLS-policies en expliciete grants per rol. Offshore en side-offshore zijn in de database afgedwongen als `no_go`.
- pgTAP-tests in `supabase/tests/` (4 bestanden, 190 asserts) en een nieuwe CI-job `db` die ze draait op een lokale Supabase-stack.
- `shakka.db.SupabaseRest`: PostgREST-client op httpx met paginering per 1000 rijen (deterministisch, PK als tiebreaker), upserts in batches van 500 en een `DatabaseError` zonder key.
- `FakeSupabase` in `ingest/tests/fakes.py`: in-memory nep-database met PostgREST-semantiek, plus een optionele pariteitstest tegen de lokale stack.
- `docs/RUNBOOK.md` secties 6–8: lokale stack, CI en migraties naar het remote project.

### Zelf proberen (vanaf `develop`)
- `cd ingest && uv run pytest`
- `supabase start && supabase db reset && supabase test db`
- Optioneel pariteit: `cd ingest && SHAKKA_TEST_SUPABASE_URL=http://127.0.0.1:54321 SHAKKA_TEST_SUPABASE_SECRET_KEY=<key uit supabase status> uv run pytest tests/test_fake_parity.py`

### Nodig van Lars (AC-7)
Na de merge, volgens RUNBOOK 8.3: `supabase link --project-ref <ref>` (eenmalig), `supabase db push --dry-run`, `supabase db push`, `supabase migration list --linked`.

### Niet-blokkerende punten
- AC-2(c): `anon` heeft geen grant op privé-tabellen; lezen geeft `42501` in plaats van een lege lijst (strenger dan de letterlijke tekst, akkoord in review).
- Databasebereiken (kn 5–60, quiver 3–21 m² en max. 10 kites, `min_go_hours` 1–24, `days_ahead` 0–7) zijn nu de bron voor WP-07 en WP-16.
- Latere WP's: WP-03/WP-05 normaliseren richtingen naar 0–359; een nieuwe redencode in WP-05 vraagt een migratie; WP-16 werkt het profiel bij met `update`, niet met upsert.
- De Docker-socket was niet toegankelijk in de bouwsessie: het bewijs voor de pgTAP-tests komt uit CI, en de pariteitstest is nog niet tegen echt PostgREST gedraaid.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
