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

## 7. CI
De workflow `.github/workflows/ci.yml` draait op `push` en `pull_request`. Job `ingest` doet `uv sync`, `uv run ruff check .`, `uv run ruff format --check .` en `uv run pytest`. CI gebruikt geen secrets.

Laatste run bekijken: `gh run list --workflow ci.yml --limit 1`.
