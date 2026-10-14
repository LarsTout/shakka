# Shakka

Gratis PWA voor Nederlandse kiters: per spot een oordeel of je kunt kiten, alerts die standaard goed staan, en "ik ga"-links die je in WhatsApp deelt. Het volledige plan staat in `docs/PROJECT_PLAN.md`; dat is de bron van waarheid.

## Werkwijze
- Werk per work package (WP) via `/ship WP-XX`. Status staat in `docs/STATUS.md`; lees die eerst in elke nieuwe sessie.
- Bouw alleen op basis van een blueprint met status `APPROVED` in `docs/wp/WP-XX/blueprint.md`.
- Eén WP per sessie. Na `done`: nieuwe sessie.
- Documentatie in het Nederlands. Code, comments, identifiers, commit messages in het Engels.

## Stack
- `/ingest`: Python 3.12 met `uv`. Tests: `uv run pytest`. Lint: `uv run ruff check . && uv run ruff format --check .`
- `/web`: SvelteKit (static adapter), TypeScript. `npm run check`, `npm test`, `npm run build`
- `/supabase`: Postgres-migraties en RLS
- `/data/spots.yaml`: handmatig samengestelde spotprofielen
- Scheduler: GitHub Actions cron (elk uur)

## Harde regels
- €0 per maand: alleen gratis tiers. Geen nieuwe betaalde dienst zonder akkoord van Lars.
- Open-Meteo alleen server-side vanuit `/ingest`, per spot gecachet. Nooit vanuit de browser.
- Bronvermelding (Open-Meteo, KNMI, Rijkswaterstaat, CC BY 4.0) blijft zichtbaar in de app.
- Geen scraping van Windguru, Windfinder, KiteGids, Hanglos, Marktplaats of andere sites.
- Geen feitelijke spotdata verzinnen. Onzeker = leeg laten, `verified: false`.
- Offshore en side-offshore zijn altijd `no_go`. Niet configureerbaar.
- Secrets alleen in `.env` (lokaal, gitignored) en GitHub Secrets. Nooit in code of docs.
- Minimale persoonsgegevens. Geen tracking, geen third-party analytics.
