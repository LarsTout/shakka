# Runbook

Praktische handleiding voor lokaal werken aan Shakka. Hier staan alleen namen van secrets, nooit waarden.

## 1. Vereisten
- uv: `brew install uv` of het installatiescript van astral.sh. uv haalt Python 3.12 zelf op als die ontbreekt.
- Supabase CLI: `brew install supabase/tap/supabase`.
- Docker Desktop of OrbStack: alleen nodig voor `supabase start`, vanaf WP-01.

## 2. Ingest lokaal
Alle commando's draaien vanuit `ingest/`:

```
cd ingest
uv sync
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run shakka doctor
```

Vanuit de repo-root kan ook: `uv run --project ingest shakka doctor`.

## 3. `.env` invullen
1. Kopieer in de repo-root: `cp .env.example .env`. `.env` staat in `.gitignore` en gaat nooit de repo in.
2. Vul `SUPABASE_URL` in. Je vindt die in het Supabase Dashboard onder Project Settings, API. De vorm is `https://<project-ref>.supabase.co`, zonder pad (dus niet `/rest/v1`).
3. Vul `SUPABASE_PUBLISHABLE_KEY` (begint met `sb_publishable_`) en `SUPABASE_SECRET_KEY` (begint met `sb_secret_`) in. Je vindt ze onder Project Settings, API Keys.

Let op: `SUPABASE_ANON_KEY` en `SUPABASE_SERVICE_ROLE_KEY` worden niet meer gelezen. Staat er nog een oude naam in je `.env`, dan wordt die genegeerd en meldt `doctor` de nieuwe naam als `missing`.

Wat `uv run shakka doctor` meldt:
- `missing NAAM`: de variabele ontbreekt of is leeg.
- `invalid SUPABASE_URL`: de URL is geen `https://<project-ref>.supabase.co` zonder pad (`http` mag alleen naar localhost).
- `warn ...`: de sleutel heeft een ander prefix dan verwacht. Legacy-sleutels werken tot eind 2026.
- `error ... rejected the key (HTTP 401/403)`: verkeerde sleutel. `SUPABASE_SECRET_KEY` moet een secret key zijn.
- `error ... returned HTTP 404`: verkeerde URL.
- `error ... redirected`: verkeerde URL. Redirects worden bewust niet gevolgd.
- `error ... timed out` of `unreachable`: netwerkprobleem.
- `doctor: ok`: alles werkt (exitcode 0). `doctor: failed`: exitcode 1.

`doctor` toont nooit waarden van variabelen.

## 4. Secrets, alleen namen

| Variabele | Waar | Gebruikt door | Vanaf |
|---|---|---|---|
| `SUPABASE_URL` | `.env`, GitHub Secret | ingest | WP-00 |
| `SUPABASE_PUBLISHABLE_KEY` | `.env` | ingest (`shakka doctor`) | WP-00 |
| `SUPABASE_SECRET_KEY` | `.env`, GitHub Secret | ingest | WP-00 |
| `TELEGRAM_BOT_TOKEN` | `.env`, GitHub Secret | ingest | WP-09 |
| `TELEGRAM_CHAT_ID` | `.env`, GitHub Secret | ingest: operatormeldingen en testberichten | WP-09 |
| `APP_BASE_URL` | `.env`, GitHub Actions variable | ingest: "ik ga"-links in berichten | WP-14 |
| `VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY`, `VAPID_SUBJECT` | `.env`, GitHub Secrets | ingest | WP-17 |

De Supabase access token en het database-wachtwoord blijven bij Lars en komen nergens in de repo. De `PUBLIC_*`-variabelen voor de web-app komen in `web/.env.example` (WP-13).

## 5. Supabase CLI koppelen
1. `supabase login`: opent de browser, de token blijft lokaal.
2. `supabase link --project-ref <ref>`: vraagt om het database-wachtwoord. Sla dat niet op in de repo.

`supabase/.temp/` bevat lokale koppelinfo en is gitignored, net als `supabase/.branches/`.

## 6. Lokale stack (vanaf WP-01)
- `supabase start` start de lokale stack, `supabase stop` stopt hem.
- `supabase status` toont de lokale URL (`http://127.0.0.1:54321`) en de lokale publishable en secret key.
- Om `.env` tijdelijk naar de lokale stack te laten wijzen: bewaar je echte waarden elders, zet `SUPABASE_URL` op de lokale URL en de sleutels op de lokale waarden uit `supabase status`. Zet de echte waarden daarna terug.
- `supabase start` past de migraties uit `supabase/migrations/` toe.
- `supabase db reset` bouwt de lokale database opnieuw op uit `supabase/migrations/`.
- `supabase test db` draait de pgTAP-tests in `supabase/tests/`.
- Optionele pariteitstest van `FakeSupabase` tegen echt PostgREST: neem de lokale secret key over uit `supabase status` en draai vanuit `ingest/`: `SHAKKA_TEST_SUPABASE_URL=http://127.0.0.1:54321 SHAKKA_TEST_SUPABASE_SECRET_KEY=<lokale secret key> uv run pytest tests/test_fake_parity.py`. Die test werkt alleen tegen localhost en wordt anders overgeslagen.

## 7. CI
De workflow `.github/workflows/ci.yml` draait op `push` en `pull_request`. Job `ingest` doet `uv sync`, `uv run ruff check .`, `uv run ruff format --check .` en `uv run pytest`. Job `db` draait `supabase start` (zonder de diensten die de tests niet nodig hebben) en `supabase test db`. CI gebruikt geen secrets.

Laatste run bekijken: `gh run list --workflow ci.yml --limit 1`.

## 8. Database en migraties
1. Migraties staan in `supabase/migrations/` en worden nooit achteraf gewijzigd. Een wijziging is altijd een nieuw bestand.
2. Elke nieuwe tabel krijgt in dezelfde migratie `enable row level security`, `revoke all ... from public, anon, authenticated, service_role`, expliciete grants (ook aan `service_role`, anders kan de ingest er niet bij) en policies. De tabel komt ook in `TABLE_KEYS` in `ingest/src/shakka/db.py`; `test_table_keys_match_migrations` bewaakt dat.
3. Naar het remote project, na de merge naar `develop` (Lars):
   - `supabase link --project-ref <ref>` (eenmalig);
   - `supabase db push --dry-run` om te zien welke migraties meegaan;
   - `supabase db push`;
   - `supabase migration list --linked`: alle migraties staan als toegepast.
4. Laat "Max rows" van de Data API op 1000. `SupabaseRest` vraagt pagina's van 1000; bij een lagere waarde blijft het resultaat compleet, maar kost het meer requests.
5. `auto_expose_new_tables = false` in `config.toml` spiegelt de instelling van het remote project. Weigert een nieuwere CLI die sleutel, haal de regel dan weg. De migraties werken ook zonder, omdat ze zelf revoken en granten.
