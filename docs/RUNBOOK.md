# Runbook

Praktische handleiding voor lokaal werken aan Shakka. Hier staan alleen namen van secrets, nooit waarden.

## 1. Vereisten
- uv: `brew install uv` of het installatiescript van astral.sh. uv haalt Python 3.12 zelf op als die ontbreekt.
- Supabase CLI: `brew install supabase/tap/supabase`.
- Docker Desktop of OrbStack: alleen nodig voor `supabase start`, vanaf WP-01.
- Node 24 LTS (bijv. via nvm: `nvm install 24`); `web/.nvmrc` bevat de versie. Vanaf WP-13.

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
| `PUBLIC_SUPABASE_URL`, `PUBLIC_SUPABASE_PUBLISHABLE_KEY` | `web/.env`, Cloudflare Pages | web | WP-13 |
| `NODE_VERSION` | Cloudflare Pages | build | WP-13 |

De Supabase access token en het database-wachtwoord blijven bij Lars en komen nergens in de repo. De `PUBLIC_*`-variabelen voor de web-app staan in `web/.env.example`. Gebruik daar nooit de secret key; de build weigert een sleutel die met `sb_secret_` begint.

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
De workflow `.github/workflows/ci.yml` draait op `push` en `pull_request`. Job `ingest` doet `uv sync`, `uv run ruff check .`, `uv run ruff format --check .` en `uv run pytest`. Job `db` draait `supabase start` (zonder de diensten die de tests niet nodig hebben) en `supabase test db`. Job `web` draait in `web/`: `npm ci`, `npm run check`, `npm test`, `npm run build`, `npm run verify:build` en de Open-Meteo-guard `scripts/check-no-client-openmeteo.sh`. Voor de publieke variabelen gebruikt de job placeholders (geen secrets). CI gebruikt geen secrets.

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

## 9. Forecast-ingest (vanaf WP-03)
Elk uur haalt de ingest per spot met coördinaten de windverwachting op bij Open-Meteo (server-side, nooit vanuit de browser) en bewaart die in `forecast_hours`. Rijen ouder dan 48 uur worden opgeruimd. Ontwerp: `docs/wp/WP-03/blueprint.md`.

**Commando's** (vanuit `ingest/`)
- `uv run shakka forecast fetch --dry-run`: toont het plan (aantal spots, requests, geschat gewicht, huidig verbruik, `budget: ok` of `budget: exceeded`). Doet geen request naar Open-Meteo en schrijft niets. Exit 0.
- `uv run shakka forecast fetch`: haalt op en slaat op. Eerste regel: `forecast: spots=<n> rows=<n> calls=<x.xx> deleted=<n> skipped_budget=<yes|no> errors=<n>`, daarna per fout een regel `error   chunk <n>/<totaal>: <melding>`, en tot slot `forecast: ok` of `forecast: failed`.
- Exitcodes: 0 bij succes; 1 bij fouten per chunk, een budgetstop, een onvolledige config (`forecast: configuration incomplete; run shakka doctor`) of een databasefout (`forecast: database error: ...`).

**Budget.** De guard stopt bij 8.000 calls per dag en 240.000 per maand (80% van de gratis limiet van 10.000 en 300.000). Het verbruik staat in `api_usage` (bronnen `open_meteo_forecast`, `open_meteo_marine`, `rws`; alleen `open_meteo_*` telt mee). Het gewicht wordt per request geboekt, ook bij een mislukte request.

**Modellen en cel.** KNMI HARMONIE, DWD ICON, ECMWF IFS en GFS, met `cell_selection=sea` (zie blueprint WP-03, A1 en A2).

**Tijdsemantiek.** `gust_kn` op `valid_at` T is de maximale vlaag in [T, T+1h) (de ruwe Open-Meteo-waarde van T+1h); het laatste uur van een respons heeft geen vlaag (A14).

**Lokale test met de stack**
1. `supabase start`, en zet `.env` tijdelijk op de lokale stack (sectie 6).
2. Voeg een test-spot toe: `psql "<DB URL uit supabase status>" -c "insert into public.spots (id, name, lat, lon) values ('test-strand', 'Teststrand', 52.47, 4.57) on conflict (id) do nothing;"`
3. `uv run shakka forecast fetch` (exit 0), en controleer met `select model, count(*) from public.forecast_hours group by model;` dat er 4 modellen staan.
4. Draai het commando nogmaals: het aantal rijen verdubbelt niet (gelijk, of iets hoger doordat de KNMI-horizon opschuift).
5. Zet `.env` terug en verwijder de test-spot.

**Fixture opnieuw vastleggen.** Alleen nodig als een request-parameter verandert (`test_fixture_matches_current_params` faalt). Vanuit de repo-root:

```
curl -sS --fail -o ingest/tests/fixtures/openmeteo/forecast_2loc_4models.json \
 "https://api.open-meteo.com/v1/forecast?latitude=52.4700,52.1000&longitude=4.5700,4.2700&hourly=wind_speed_10m,wind_direction_10m,wind_gusts_10m&models=knmi_harmonie_arome_netherlands,dwd_icon_seamless,ecmwf_ifs,ncep_gfs_seamless&wind_speed_unit=kn&timezone=GMT&timeformat=unixtime&forecast_days=7&cell_selection=sea"
```

Pas daarna `CAPTURE_URL` en `CAPTURE_DATE` in `ingest/tests/test_openmeteo_forecast.py` aan. `ingest/tests/fixtures/openmeteo/README.md` bevat de CC BY 4.0-vermelding van Open-Meteo; werk de opnamedatum (en URL) daar ook bij.

## 10. Getij (Rijkswaterstaat, vanaf WP-04)
1. `cd ingest && uv run shakka tides stations --search hoek` toont stations met astronomische hoog- en laagwaters (code, naam, lat, lon). Zet de `code` als `rws_station` in `data/spots.yaml`. Neem het dichtstbijzijnde station aan dezelfde kust of hetzelfde zeegat. Dit commando heeft geen `.env` nodig.
2. `uv run shakka tides fetch` haalt per station eens per 20 uur op; `--force` negeert die regel. Exitcode 1 betekent dat minstens één station faalde (zie de regels onder `failed`).
3. Hoek van Holland kent een dubbel laagwater. Dat wordt opgeslagen als twee laagwaters; de topagger ertussen wordt niet opgeslagen.
4. Een onbekend extreemtype (bijv. bij dubbel hoogwater) laat het station falen in plaats van iets te raden. Meld het dan als issue.
5. Bron: Rijkswaterstaat WaterWebservices (DDAPI20), CC0. Geen uptimegarantie. Een storing van een paar dagen is geen probleem, want er staat 8 dagen vooruit in de database.
6. Fixtures opnieuw vastleggen: `uv run python scripts/capture_rws_fixtures.py`. Daarna de tests bijwerken: `EXPECTED_EXTREMES` in `tests/test_rws_tides.py`.

## 11. Web-app (PWA, vanaf WP-13)
1. **Lokaal.** `cd web && cp .env.example .env` en vul je waarden in: remote (Dashboard, Project Settings, API) of de lokale stack (`http://127.0.0.1:54321` en de publishable key uit `supabase status`). Daarna `npm ci`, `npm run dev` (http://localhost:5173), `npm run check`, `npm test`, `npm run build`, `npm run verify:build` en vanuit de repo-root `bash scripts/check-no-client-openmeteo.sh`.
2. **Lokaal inloggen.** Met de lokale stack komt de magic link in Mailpit (`http://127.0.0.1:54324`). `config.toml` staat `http://localhost:5173` als redirect toe. Inloggen werkt alleen voor bestaande gebruikers (`shouldCreateUser: false`, tot WP-22): maak jezelf eenmalig aan via het Supabase Dashboard (Authentication, Users, Add user) of lokaal via Studio.
3. **Cloudflare Pages (eenmalig, Lars).**
   - Workers & Pages, Create, Pages, Connect to Git, repo `LarsTout/shakka`;
   - production branch `main`;
   - framework preset "None", build command `npm run build`, build output directory `build`, root directory `web`;
   - Preview branches: alle niet-productiebranches (dus `develop` en `wp/*`);
   - environment variables voor **Production en Preview**: `PUBLIC_SUPABASE_URL`, `PUBLIC_SUPABASE_PUBLISHABLE_KEY` en `NODE_VERSION=24.22.0` (het standaardimage heeft Node 22.16, en dat is te oud voor SvelteKit 3). Installeert 24.22.0 niet, gebruik dan een eerdere 24.x vanaf 24.15.
4. **Supabase Auth (Lars).** Authentication, URL Configuration:
   - Site URL: `https://<project>.pages.dev`;
   - Redirect URLs: `https://<project>.pages.dev`, `https://<project>.pages.dev/**`, `https://*.<project>.pages.dev`, `https://*.<project>.pages.dev/**`, `http://localhost:5173` en `http://localhost:5173/**`.
5. **Beperkingen.** De standaard-SMTP mailt alleen naar teamleden van het project, max. 2 per uur. Een inloglink is één keer bruikbaar en verloopt na 1 uur. Op iOS heeft een app op het beginscherm eigen opslag, los van Safari. Een magic link uit de mail logt je in Safari in, niet in de geïnstalleerde app (zie WP-18).
6. **App-icoon vervangen.** Vervang de PNG's in `web/static/icons/` door bestanden met dezelfde naam en afmeting. `npm run icons` maakt de placeholders opnieuw.
