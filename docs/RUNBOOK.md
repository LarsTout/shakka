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
| `APP_BASE_URL` | `.env`, GitHub Actions variable | ingest: "ik ga"-links in berichten | WP-14 |
| `HOURLY_ENABLED` | GitHub Actions variable | workflow hourly.yml: schedule aan (true) of uit | WP-11 |
| `VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY`, `VAPID_SUBJECT` | `.env`, GitHub Secrets | ingest | WP-17 |
| `PUBLIC_SUPABASE_URL`, `PUBLIC_SUPABASE_PUBLISHABLE_KEY` | `web/.env`, Cloudflare Pages | web | WP-13 |
| `PUBLIC_MAPTILER_KEY` | `web/.env` (lokale key), Cloudflare Pages (productiekey) | web: kaart (optioneel, publiek) | WP-15 |
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
   - framework preset "None", root directory leeg (repo-root), build command `cd web && npm ci && npm run build`, build output directory `web/build`. De app importeert `data/contracts/*.json` buiten `web/`; daarom bouwt Pages vanaf de repo-root (WP-14). Optioneel: build watch paths `web/*` en `data/contracts/*`, zodat een push die alleen `ingest/` raakt geen Pages-build start (gratis tier: 500 builds per maand);
   - Preview branches: alle niet-productiebranches (dus `develop` en `wp/*`);
   - environment variables voor **Production en Preview**: `PUBLIC_SUPABASE_URL`, `PUBLIC_SUPABASE_PUBLISHABLE_KEY` en `NODE_VERSION=24.22.0` (het standaardimage heeft Node 22.16, en dat is te oud voor SvelteKit 3; `web/.nvmrc` wordt vanaf de repo-root niet gelezen). Installeert 24.22.0 niet, gebruik dan een eerdere 24.x vanaf 24.15.
4. **Supabase Auth (Lars).** Authentication, URL Configuration:
   - Site URL: `https://<project>.pages.dev`;
   - Redirect URLs: `https://<project>.pages.dev`, `https://<project>.pages.dev/**`, `https://*.<project>.pages.dev`, `https://*.<project>.pages.dev/**`, `http://localhost:5173` en `http://localhost:5173/**`.
5. **Beperkingen.** De standaard-SMTP mailt alleen naar teamleden van het project, max. 2 per uur. Een inloglink is één keer bruikbaar en verloopt na 1 uur. Op iOS heeft een app op het beginscherm eigen opslag, los van Safari. Een magic link uit de mail logt je in Safari in, niet in de geïnstalleerde app (zie WP-18).
6. **App-icoon vervangen.** Vervang de PNG's in `web/static/icons/` door bestanden met dezelfde naam en afmeting. `npm run icons` maakt de placeholders opnieuw.
7. **Spotlijst, spotpagina en `/go` (vanaf WP-14).** De app leest alleen `spots`, `evaluations`, `tide_extremes` en (vanaf WP-12) `marine_hours`. Het oordeel gebruikt de standaardgrenzen van de spot, niet de persoonlijke instellingen. "Ouder dan 3 uur" kijkt naar `evaluated_at`; die is ook vers als alleen de forecast-ingest faalt, dus controleer bij twijfel `ingest_runs` (§13.5). Donkere uren (reden `dark`) zijn op de spotpagina standaard verborgen. `/go?spot=...&start=...&end=...` stuurt in M2 door naar `/spot/<spot>`; ongeldige parameters gaan naar `/`. De app pagineert per 1000 rijen; zet de Supabase-instelling "Max rows" (API settings) niet lager dan 1000.
8. **Profiel, favorieten en alerts in de app (vanaf WP-16).** Ingelogd zie je een ster bij elke spot (favoriet) en de pagina's Profiel en Alerts. Ze schrijven naar dezelfde tabellen als `shakka admin` (§12). Een favoriet zonder eigen instellingen gebruikt de standaard; "Standaardinstellingen" verwijdert de eigen regel. Een spot uit de favorieten halen verwijdert ook de regel. Ontbreekt een profiel ("Je profiel is niet gevonden"), voer dan in de SQL Editor de backfill uit de migratie uit: `insert into public.profiles (user_id) select id from auth.users on conflict (user_id) do nothing;`. Controle (WP-16 AC-7): zie §12 punt 6 (`admin alerts preview`).
9. **Kaart (vanaf WP-15).**
   - Maak een gratis MapTiler Cloud-account. Maak onder Account, API keys **twee** keys: één voor productie en één voor lokaal.
   - **Productiekey:** onder "Allowed HTTP origins" alleen `<project>.pages.dev` en `*.<project>.pages.dev` (previews), één per regel. **Nooit `localhost` of `127.0.0.1` op deze key.** De key staat publiek in de app, en volgens MapTiler matcht localhost elke machine, dus iedereen zou dan je quotum kunnen opmaken.
   - **Lokale key (optioneel):** onder "Allowed HTTP origins" `localhost` en `127.0.0.1` (zonder poort en protocol). Zet hem alleen in `web/.env`, nooit in Cloudflare Pages en nooit in de repo. Zonder lokale key werkt de lijst gewoon.
   - Alle keys delen het quotum van het account.
   - Zet `PUBLIC_MAPTILER_KEY` = de productiekey in Cloudflare Pages (Production en Preview). Het is een publieke key, geen secret. De waarde komt bij de build in de app, dus na een wijziging is een nieuwe deploy nodig.
   - Zonder key werkt de app gewoon, en geeft "Kaart" een melding. De kaart laadt alleen na een klik op "Kaart".
   - MapTiler rekent bij MapLibre in API-requests: 100.000 per maand gratis, en alleen tiles tellen. Bij overschrijding is het gepauzeerd tot de volgende maand (geen kosten; de app valt terug op de lijst). Het verbruik staat in MapTiler Cloud, Analytics.
   - **Key vervangen** (bijvoorbeeld bij misbruik): maak een nieuwe productiekey met dezelfde origins, zet hem in Cloudflare Pages, deploy opnieuw en verwijder daarna de oude key in MapTiler Cloud.

## 12. Alerts in M1 (vanaf WP-10)
Vanaf WP-16 kan dit ook in de app (Profiel, Alerts, ster bij een spot); de CLI blijft werken.
In M1 worden er nog geen meldingen verstuurd. De alertjob berekent per favoriet of er een go-window is en legt dat vast in `alert_state`. Zo controleer je lokaal of de alerts kloppen; versturen komt in WP-17.

1. **Auth-user maken.** Supabase Dashboard, Authentication, Users, Add user. Kopieer de user-id (UUID). Het profiel wordt automatisch aangemaakt.
2. **Profiel invullen.** `cd ingest && uv run shakka admin profile set --user-id <id> --weight <kg> --level <beginner|intermediate|advanced> --quiver "7 9 12"`, controleer met `uv run shakka admin profile show --user-id <id>`.
   - `--quiver`: scheid maten met spaties, `;` of komma's. **Alleen komma's** betekent dat elke komma een scheidingsteken is, dus `--quiver 7,5` wordt 5 en 7 m² en niet 7,5 m². Typ een decimale maat met een punt (`10.5`), of met een komma als je de maten met spaties of `;` scheidt (`--quiver "10,5; 12"`). Bij twijfel toont de CLI een `note:`-regel met hoe de invoer gelezen is. Controleer altijd met `profile show`.
   - `--quiver ""` maakt de quiver leeg. Een veld terugzetten op de standaard (`NULL`) kan alleen in het Supabase Dashboard (Table Editor).
3. **Favoriet toevoegen.** `uv run shakka admin favorite add --user-id <id> --spot <spot-id>` en `uv run shakka admin favorite list --user-id <id>`.
4. **Regel aanpassen (optioneel).** `uv run shakka admin rule set --user-id <id> --spot <spot-id> ...` met `--min-kn`, `--max-kn`, `--dir-classes`, `--weekdays` (1 = maandag), `--after HH:MM`, `--before HH:MM`, `--min-go-hours`, `--days-ahead` en `--enable/--disable`. Alleen de opgegeven velden veranderen. Offshore en side-offshore kunnen nooit in een regel; dat is geen instelling.
5. **Alleen geverifieerde spots.** Alerts gaan alleen af voor spots met `verified: true`. Vul het profiel in `data/spots.yaml` volgens `docs/SPOT_DATA.md`, zet `verified: true` en draai `uv run shakka spots sync`. Een niet-geverifieerde spot wordt wel geëvalueerd, maar geeft geen alerts.
6. **Volgorde.** `uv run shakka forecast fetch`, `uv run shakka tides fetch`, `uv run shakka evaluate`, `uv run shakka admin alerts preview --user-id <id>`, eventueel `uv run shakka alerts run --dry-run` en dan `uv run shakka alerts run`.
7. **`alert_state` bekijken.** Dashboard, Table Editor, `alert_state`: `status`, `last_event` en `snapshot` (de laatst gemelde stand, niet de nieuwste verwachting). `last_notified_at` is in M1 altijd leeg; vanaf WP-17 het tijdstip van de run waarin de melding voor het eerst is afgeleverd. Rijen verdwijnen 48 uur na `window_end`.
8. **Exitcodes.** `alerts run` geeft exitcode 1 bij `skipped` (een kapotte regel-, profiel- of staterij), `write_errors`, een databasefout, een onvolledige config of een ongeldige `APP_BASE_URL`. `ineligible` (spot niet geverifieerd, niet geladen of nog geen forecastdata: "no forecast data") en `disabled` (regel uitgezet) zijn geen fout: exitcode 0. `shakka evaluate` geeft exitcode 1 als een spot niet geladen of geëvalueerd kan worden; een spot zonder forecastrijen is geen fout.
9. **Waarschuwing.** `alerts run` en `admin alerts preview` tonen berichtteksten. `alerts run` levert vanaf WP-17 ook echt af (Web Push, §14), tenzij je `--dry-run` gebruikt; `admin alerts preview` levert nooit af. Gebruik ze lokaal en nooit in een GitHub-workflow: de logs van een publieke repo zijn openbaar. De uurlijkse workflow (WP-11) roept de functies aan, niet deze commando's.
10. **Oude `TELEGRAM_*`-variabelen.** Die mag je uit je lokale `.env` halen. Ze worden genegeerd en zijn niet meer nodig.

## 13. Uurlijkse run (vanaf WP-11)
1. **Wat draait er.** Elk uur om :17 UTC (geen garantie: GitHub kan vertragen of een run overslaan) draait `shakka run-hourly`: `spots_sync`, `forecast`, `marine`, `tides`, `evaluate`, `alerts`, met foutisolatie per stap. De schedule draait de code van `main`, met het workflowbestand van `develop` (de default branch). Alleen als de variable `HOURLY_ENABLED` op `true` staat. Er draait één run tegelijk.
2. **Eenmalige setup.**
   - Repo Settings, Secrets and variables, Actions: secrets `SUPABASE_URL` en `SUPABASE_SECRET_KEY`; vanaf WP-17 ook `VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY` en `VAPID_SUBJECT` (zonder deze secrets geen pushmeldingen, zie §14); de variable `APP_BASE_URL` op de productie-URL zonder pad of slash aan het eind (bijv. `https://<project>.pages.dev`), vanaf WP-14. Daarmee bevat elk alertbericht een werkende "ik ga"-link (`/go`).
   - Settings, Actions, General: Actions aan.
   - E-mailmeldingen: github.com, Settings, Notifications, onderdeel voor Actions ("workflow runs updates on repositories set up with GitHub Actions"). Zet e-mail aan, desgewenst alleen bij gefaalde workflows. De GitHub-documentatie noemt deze opties maar geeft het exacte menupad niet; controleer de namen in de actuele interface.
   - Wie de mail krijgt: wie `hourly.yml` heeft aangemaakt, of als laatste de cron wijzigde, of de workflow opnieuw aanzette. Controleer dat jij dat bent.
3. **Handmatig starten.** Actions, hourly, Run workflow (kies `ref`), of `gh workflow run hourly.yml -f ref=main`. `ref = develop` schrijft naar dezelfde database; bedoeld als test vóór een promotie.
4. **Runs bekijken.** `gh run list --workflow hourly.yml --limit 5` en `gh run view <run-id> --log`. Annotaties (`::warning::`, `::error::`) staan bovenaan de samenvatting van een run. Een run met status "cancelled" in de lijst is geen storing: duurt een run lang en komen er intussen twee nieuwe starts (schedule en/of dispatch), dan vervangt de nieuwste de wachtende, en die wachtende krijgt "cancelled" (`concurrency`). Een getijstap met de warning "time budget of 240 s reached" betekent dat RWS traag of onbereikbaar is; de overgeslagen stations volgen in een latere run.
5. **`ingest_runs` lezen** (Dashboard, SQL Editor):
   - `select id, started_at, finished_at, status, error_summary from public.ingest_runs order by started_at desc limit 24;`
   - `select jsonb_pretty(steps) from public.ingest_runs where id = <id>;`
   - Per stap: `status`, `duration_ms`, `counts`, `error` (alleen hier leesbaar, secrets geredigeerd), `error_type`, `reason` (bij `skipped`) en `warnings`. Stapstatussen: `ok`, `partial` (de job draaide, maar meldde fouten per onderdeel), `failed` (exception), `skipped` (voorwaarde ontbrak, bijvoorbeeld `stale_forecast`). Runstatussen: `running`, `ok`, `partial`, `failed`.
6. **Wat een gefaalde run betekent** (mail van GitHub):
   - exitcode 1 bij `failed`: de alertstap faalde, niets werkte, of de run kon niet worden vastgelegd;
   - bij `stale_forecast`: de forecast faalt en de nieuwste is ouder dan 3 uur, dus geen alerts;
   - bij een onvolledige configuratie (secrets);
   - bij de activiteitscheck vanaf 53 dagen (punt 8).

   De oorzaak vind je in de annotaties en in `ingest_runs`. `partial` geeft geen mail. Tijdens een storing komt er elk uur een mail (GitHub dedupliceert niet; bewust geaccepteerd). Pauzeren: zet `HOURLY_ENABLED` op `false`. **Let op:** de uurlijkse run houdt het gratis Supabase-project actief (PROJECT_PLAN §2). Staat `HOURLY_ENABLED` langer dan ongeveer een week op `false` (Supabase pauzeert na 7 dagen zonder activiteit), dan pauzeert het project. Zet de run dus binnen een week weer aan, of start tussendoor handmatig een run (punt 3). Is het project toch gepauzeerd: herstel het via het Supabase-dashboard.
7. **Budgetwaarschuwing.** Boven 80% van de guard (6.400 calls per dag, of 192.000 per maand) volgt een `::warning::`-annotatie en een warning in de stap `forecast`; geen mail.
8. **60-dagenregel.** GitHub schakelt geplande workflows in een publieke repo uit na 60 dagen zonder activiteit. De activiteitscheck (`shakka check-activity`) kijkt naar de laatste commit op de default branch: vanaf 45 dagen een warning, vanaf 53 dagen een fout (elk uur een mail). Oplossing: merge een kleine wijziging naar `develop` via een PR, bijvoorbeeld de regel "Laatste activiteitscommit" onderaan deze sectie bijwerken. Is de schedule toch uitgeschakeld: `gh workflow enable hourly.yml` (de meldingen gaan daarna naar jou als je hem aanzet) en daarna een commit.
9. **Wijzigingen aan `hourly.yml`** moeten werken met de code op `main`: de schedule gebruikt het workflowbestand van `develop` maar de code van `main`. Is er nieuwe code voor nodig, promoveer dan eerst of zet `HOURLY_ENABLED` tijdelijk uit.
10. **Lokaal.** `cd ingest && uv run shakka run-hourly` doet een echte run tegen de database uit `.env` en legt die vast in `ingest_runs`. De uitvoer bevat geen berichtteksten.

Laatste activiteitscommit: 2026-10-15

## 14. Pushmeldingen (vanaf WP-17)
1. **Wat er gebeurt.** Alerts gaan als Web Push naar alle apparaten van een gebruiker (hoogstens de 10 nieuwste abonnementen). Abonneren in de app komt met WP-18. Een abonnement dat de push-service afwijst met 404 of 410 wordt automatisch verwijderd.
2. **Sleutels maken.** `cd ingest && uv run shakka alerts vapid-keys`. Zet de twee regels plus `VAPID_SUBJECT=mailto:<jouw adres>` in `.env`. Deel de uitvoer niet en draai het commando nooit in een workflow. Het subject is `mailto:<adres>` met een domein met een punt, of `https://<host>` zonder pad (dus niet `https://…/contact`); een ander subject laat de stap `alerts` falen.
3. **GitHub Secrets.** `gh secret set VAPID_PUBLIC_KEY`, `gh secret set VAPID_PRIVATE_KEY` en `gh secret set VAPID_SUBJECT`; plak de waarde bij de prompt (niet met `--body`: dan staat hij in je shell-history).
4. **Cloudflare Pages (WP-18).** `PUBLIC_VAPID_PUBLIC_KEY` is dezelfde publieke sleutel als `VAPID_PUBLIC_KEY`.
5. **Database.** `supabase db push` na de merge (§8): de migratie maakt `push_subscriptions`.
6. **Controleren (na WP-18).** `cd ingest && uv run shakka alerts test-push --user-id <id>` stuurt een testmelding naar elk apparaat. Per apparaat `ok`, `failed (<reden>)` (tijdelijk, het abonnement blijft) of `gone (...); subscription removed` (dood, verwijderd). Daarna `sent`, `failed` en `removed`, en `test-push: ok` (minstens één geslaagd) of `test-push: failed` (exitcode 1).
7. **Tellers in `ingest_runs`** (stap `alerts`): `sent`, `failed`, `no_target`, `deferred`, `removed`, `push_enabled` en `push_failures` (per reden, bijvoorbeeld `{"HTTP 503": 2}`). `deferred` betekent: voor een favoriet slaagde geen aflevering en minstens één fout was tijdelijk; de state is niet opgeslagen en de volgende run probeert het opnieuw. Dat is zichtbaar als `::warning::alerts: <n> favorite(s) deferred ...` in de Actions-log. Staat die warning in elke run en toont `push_failures` `HTTP 403`, controleer dan of `PUBLIC_VAPID_PUBLIC_KEY` in Cloudflare gelijk is aan `VAPID_PUBLIC_KEY` en volg punt 10.
8. **Zonder VAPID-secrets** is het kanaal uit: een `::warning::` per run en de state schuift door zonder melding. Een onvolledige of ongeldige configuratie laat de stap `alerts` falen (mail van GitHub).
9. **Overgang naar push (optioneel).** Wie push aanzet nadat hij al favorieten had (Lars bij de overgang uit M1, maar ook elke latere gebruiker), krijgt de lopende windows niet als melding. Wil je dat voor één gebruiker toch: na het aanzetten van push in de app de SQL `delete from public.alert_state where user_id = '<id>' and status = 'active';` in de SQL Editor; de volgende run pusht de lopende windows als nieuw.
10. **Sleutels vervangen.** Zet de nieuwe sleutels overal, draai daarna `delete from public.push_subscriptions;` (oude abonnementen werken niet met een nieuwe sleutel) en zet push in de app opnieuw aan.
11. **Privacy.** Endpoints, sleutels en het subject komen nooit in logs of uitvoer. `shakka alerts run` levert lokaal ook echt af; gebruik `--dry-run` om niets te sturen.

## 15. Golven (Open-Meteo Marine, vanaf WP-12)
1. **Wat er gebeurt.** Elk uur, direct na de forecast, haalt de ingest per spot met coördinaten golfhoogte, golfperiode en golfrichting op bij de Open-Meteo Marine API (server-side) en bewaart die in `marine_hours`. Rijen ouder dan 48 uur worden opgeruimd. Golven zijn alleen informatie: ze tellen niet mee in het oordeel of in alerts. Ontwerp: `docs/wp/WP-12/blueprint.md`.
2. **Commando** (vanuit `ingest/`). `uv run shakka marine fetch`. Eerste regel: `marine: spots=<n> rows=<n> calls=<x.xx> deleted=<n> skipped_budget=<yes|no> errors=<n>`, daarna per fout `error   chunk <n>/<totaal>: <melding>`, en tot slot `marine: ok` of `marine: failed`. Exit 0 bij succes; exit 1 bij fouten per chunk, een budgetstop, een onvolledige config of een databasefout. Er is geen `--dry-run`; `shakka forecast fetch --dry-run` toont het gedeelde verbruik al.
3. **Modellen.** Eerst DWD EWAM (ca. 80 uur vooruit, ook op het IJsselmeer), daarna per uur ECMWF WAM (7 dagen, alleen kust), met `cell_selection=sea` (blueprint A1). Waarden van twee modellen komen nooit in één rij. Een spot zonder golfdata in beide modellen (binnenland) krijgt geen rijen.
4. **Budget.** Gedeeld met de wind: bron `open_meteo_marine` in `api_usage`, ca. 1 call per spot per run (de guard telt alle bronnen met prefix `open_meteo_`).
5. **Fouten.** Een mislukte marinestap geeft geen mail: de stap wordt `partial` of `failed` in `ingest_runs` (stap `marine`, zie §13.5) en de run `partial` met exitcode 0. De app verbergt golfdata met een `fetched_at` ouder dan 3 uur zonder melding.
6. **Lokale test (AC-5).**
   1. `supabase start`, en zet `.env` tijdelijk op de lokale stack (sectie 6).
   2. Voeg een test-spot toe zoals in §9 (id `test-strand`, 52.47 / 4.57).
   3. `uv run shakka marine fetch` (exit 0, `rows` > 0) en controleer met `select count(*), min(valid_at), max(valid_at) from public.marine_hours where spot_id = 'test-strand';` dat er rijen tot ca. dag 7 staan.
   4. Draai het commando nogmaals: het aantal rijen verdubbelt niet.
   5. Zet `.env` terug en verwijder de test-spot (de rijen verdwijnen mee). Draai `supabase test db` bij voorkeur na `supabase db reset`; de pgTAP-test filtert wel op `pgtap-spot`, dus losse rijen van andere spots storen niet.
7. **Fixture opnieuw vastleggen.** Alleen nodig als een request-parameter verandert (`test_fixture_matches_current_params` faalt) of de dekking verandert. Vanuit de repo-root:

   ```
   curl -sS --fail -o ingest/tests/fixtures/openmeteo/marine_3loc_2models.json \
    "https://marine-api.open-meteo.com/v1/marine?latitude=52.4700,52.7500,52.0900&longitude=4.5700,5.3000,5.1200&hourly=wave_height,wave_period,wave_direction&models=ewam,ecmwf_wam&timezone=GMT&timeformat=unixtime&forecast_days=7&cell_selection=sea"
   ```

   Pas daarna `CAPTURE_URL` en `CAPTURE_DATE` in `ingest/tests/test_openmeteo_marine.py` en de opnamedatum in `ingest/tests/fixtures/openmeteo/README.md` aan. Verandert de dekking (bijvoorbeeld ECMWF krijgt IJsselmeer-data), dan faalt `test_fixture_lake_uses_ewam_only`; pas die test dan aan.
8. **Na de merge.** `supabase db push` (§8): de migratie `20261015180000_marine_hours.sql` maakt `marine_hours`.
