# Shakka

Gratis PWA voor Nederlandse kiters: per spot een oordeel of je kunt kiten, alerts die standaard goed staan, en "ik ga"-links die je in WhatsApp deelt. Het volledige plan staat in `docs/PROJECT_PLAN.md`; dat is de bron van waarheid.

## Werkwijze
- Werk per work package (WP) via `/ship WP-XX`. Status staat in `docs/STATUS.md`; lees die eerst in elke nieuwe sessie.
- Bouw alleen op basis van een blueprint met status `APPROVED` in `docs/wp/WP-XX/blueprint.md`.
- Eén WP per sessie. Na `done`: nieuwe sessie. Meerdere WP's parallel mag, elk in een eigen sessie.
- Branches: `main` is stabiel en wordt per mijlpaal door Lars bijgewerkt vanaf `develop`. Elke WP werkt op `wp/WP-XX` (afgetakt van `develop`, in een eigen worktree) en gaat via een PR met groene CI naar `develop`. Nooit direct op `main` of `develop` committen. (WP-00 is de uitzondering: die is onder de oude regels op `main` gestart.)
- Documentatie in het Nederlands. Code, comments, identifiers, commit messages in het Engels.

## Orchestratie: subagents, geen losse sessies
- De orchestrator voert elk werkpakket uit met subagents (Agent-tool, `run_in_background: true`): planner, reviewer, builder, verifier. Start geen aparte sessies per werkpakket, tenzij Lars daar expliciet om vraagt.
- Subagents krijgen het absolute pad van hun worktree, het WP-ID en de regel "schrijf niets buiten deze worktree". Lees alleen hun eindrapport en het oordeel bovenaan hun bestand, nooit hun transcript.
- Werk onafhankelijke stappen parallel af (bijv. de planner van WP-A terwijl de builder van WP-B bouwt). Twee schrijvende agents raken nooit dezelfde bestanden.
- Houd de takenlijst onder je bericht actueel met één stap per WP-fase. Meld na elk eindrapport in 1–2 zinnen wat de agent opleverde en wat er nu loopt.
- Ga na een gemergde WP direct door met de volgende WP die niet geblokkeerd is. Stop alleen voor wat echt bij Lars ligt (accounts, tokens, scopewijzigingen, een geblokkeerde WP) en vraag dat terwijl de rest doorloopt.
- Subagents hebben geen eigen rij in de zijbalk. Vraagt Lars wat er loopt, noem dan per actieve agent de rol en de WP.

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
