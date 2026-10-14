# Afwijkingen WP-01

## D1. Geen lokale Supabase-stack, pgTAP lokaal op losse Postgres 18
- Wat: `supabase start`, `supabase db reset` en `supabase test db` zijn niet lokaal gedraaid. De Docker-socket (`/var/run/docker.sock`) is voor de builder-sessie niet toegankelijk (permission denied), dus A1 viel af.
- Alternatief: de twee migraties en alle vier pgTAP-bestanden zijn gedraaid op een tijdelijke Postgres 18.6 (Homebrew) met pgTAP 1.3.4 en een nagebouwde omgeving (rollen `anon`, `authenticated`, `service_role`, een `auth.users`-tabel en `auth.uid()`, default privileges zoals Supabase die uitdeelt). Alle asserts slaagden (71 + 55 + 22 + 42).
- Verschil met echt: `postgres` was daar superuser, en GoTrue-kolommen van `auth.users` zijn niet nagebouwd (R6 is dus nog niet getoetst). Het echte bewijs voor AC-1, AC-2 en AC-5 komt uit de CI-job `db` of een lokale run door de verifier.
- Impact: geen wijziging aan contract of ontwerp. De pariteitstest `test_fake_parity.py` is niet uitgevoerd (geen PostgREST beschikbaar); de verwachtingen in `fake_cases.py` zijn handmatig afgeleid.

## D2. Extra helpers in `shakka.db` en extra tests
- Toegevoegd: `split_filter`, `parse_in_list`, `check_rows` en `parse_on_conflict` (gedeeld door client en fake, zodat validatie gelijk is), plus kleine extra tests in `test_db.py` en `test_fakes.py`. Interne helpers, geen contractwijziging.
