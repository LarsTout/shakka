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
| `OPERATOR_USER_ID` | `.env`, GitHub Secret | ingest: push-abonnementen van Lars voor het gebruiksrapport | WP-22 |
| `PUBLIC_SUPABASE_URL`, `PUBLIC_SUPABASE_PUBLISHABLE_KEY` | `web/.env`, Cloudflare Pages | web | WP-13 |
| `PUBLIC_MAPTILER_KEY` | `web/.env` (lokale key), Cloudflare Pages (productiekey) | web: kaart (optioneel, publiek) | WP-15 |
| `PUBLIC_VAPID_PUBLIC_KEY` | `web/.env`, Cloudflare Pages | web: Web Push aanzetten (optioneel, publiek; zelfde waarde als `VAPID_PUBLIC_KEY`) | WP-18 |
| `NODE_VERSION` | Cloudflare Pages | build | WP-13 |

De Supabase access token en het database-wachtwoord blijven bij Lars en komen nergens in de repo. De `PUBLIC_*`-variabelen voor de web-app staan in `web/.env.example`. Gebruik daar nooit de secret key; de build weigert een sleutel die met `sb_secret_` begint. Ook `PUBLIC_VAPID_PUBLIC_KEY` is publiek; de build weigert een waarde die op de private key lijkt.

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
2. Elke nieuwe tabel krijgt in dezelfde migratie `enable row level security`, `revoke all ... from public, anon, authenticated, service_role`, expliciete grants (ook aan `service_role`, anders kan de ingest er niet bij) en policies. Uitzondering: heeft de ingest de tabel niet nodig, dan krijgt `service_role` geen grants. Voorbeeld: `sessions` en `rsvps` (WP-19), waar de ingest alleen de RPC `purge_expired_sessions` uitvoert; zie §16. De tabel komt ook in `TABLE_KEYS` in `ingest/src/shakka/db.py`; `test_table_keys_match_migrations` bewaakt dat.
3. Naar het remote project, na de merge naar `develop` (Lars):
   - `supabase link --project-ref <ref>` (eenmalig);
   - `supabase db push --dry-run` om te zien welke migraties meegaan;
   - `supabase db push`;
   - `supabase migration list --linked`: alle migraties staan als toegepast.
4. Laat "Max rows" van de Data API op 1000. `SupabaseRest` vraagt pagina's van 1000; bij een lagere waarde blijft het resultaat compleet, maar kost het meer requests.
5. `auto_expose_new_tables = false` in `config.toml` spiegelt de instelling van het remote project. Weigert een nieuwere CLI die sleutel, haal de regel dan weg. De migraties werken ook zonder, omdat ze zelf revoken en granten.
6. Elke nieuwe functie in `public` krijgt `revoke all on function … from public, anon, authenticated, service_role` en daarna een expliciete `grant execute` aan precies de rollen die hem nodig hebben. `security definer` alleen met `set search_path = ''` en volledig gekwalificeerde namen. `supabase/tests/07_sessions.test.sql` legt per rol vast welke functies uitvoerbaar zijn; pas die test aan bij een nieuwe RPC.

## 9. Forecast-ingest (vanaf WP-03)
Elk uur haalt de ingest per spot met coördinaten de windverwachting op bij Open-Meteo (server-side, nooit vanuit de browser) en bewaart die in `forecast_hours`. Rijen ouder dan 48 uur worden opgeruimd. Ontwerp: `docs/wp/WP-03/blueprint.md`.

**Commando's** (vanuit `ingest/`)
- `uv run shakka forecast fetch --dry-run`: toont het plan (aantal spots, requests, geschat gewicht, huidig verbruik, `budget: ok` of `budget: exceeded`). Doet geen request naar Open-Meteo en schrijft niets. Exit 0.
- `uv run shakka forecast fetch`: haalt op en slaat op. Eerste regel: `forecast: spots=<n> rows=<n> calls=<x.xx> deleted=<n> skipped_budget=<yes|no> errors=<n>`, daarna per fout een regel `error   chunk <n>/<totaal>: <melding>`, en tot slot `forecast: ok` of `forecast: failed`.
- Exitcodes: 0 bij succes; 1 bij fouten per chunk, een budgetstop, een onvolledige config (`forecast: configuration incomplete; run shakka doctor`) of een databasefout (`forecast: database error: ...`).

**Budget.** De guard stopt bij 8.000 calls per dag en 240.000 per maand (80% van de gratis limiet van 10.000 en 300.000). Het verbruik staat in `api_usage` (bronnen `open_meteo_forecast`, `open_meteo_marine`, `rws`; alleen `open_meteo_*` telt mee). Het gewicht wordt per request geboekt, ook bij een mislukte request.

**Modellen en cel.** KNMI HARMONIE, DWD ICON, ECMWF IFS en GFS, met `cell_selection=sea` (zie blueprint WP-03, A1 en A2).

**Horizon.** 8 dagen (`forecast_days=8`, 192 uur vanaf vandaag 00:00 UTC), zodat een alertregel met `days_ahead` 7 de hele lokale dag vandaag+7 heeft. Het gewicht is gelijk aan dat van 7 dagen. KNMI dekt ca. 2,5 dag en ICON 7,5 dag, dus aan het eind van dag 7 rekenen soms alleen ECMWF en GFS (lagere zekerheid).

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
 "https://api.open-meteo.com/v1/forecast?latitude=52.4700,52.1000&longitude=4.5700,4.2700&hourly=wind_speed_10m,wind_direction_10m,wind_gusts_10m&models=knmi_harmonie_arome_netherlands,dwd_icon_seamless,ecmwf_ifs,ncep_gfs_seamless&wind_speed_unit=kn&timezone=GMT&timeformat=unixtime&forecast_days=8&cell_selection=sea"
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
1. **Lokaal.** `cd web && cp .env.example .env` en vul je waarden in: remote (Dashboard, Project Settings, API) of de lokale stack (`http://127.0.0.1:54321` en de publishable key uit `supabase status`). Daarna `npm ci`, `npm run dev` (http://localhost:5173), `npm run check`, `npm test`, `npm run build`, `npm run verify:build` en vanuit de repo-root `bash scripts/check-no-client-openmeteo.sh`. Voor pushmeldingen lokaal: verwijder eerst de lege regel `PUBLIC_VAPID_PUBLIC_KEY=` uit `web/.env` (die komt mee uit `.env.example`). Zet dan de publieke VAPID-sleutel erin zonder hem te tonen, vanuit de repo-root: `grep '^VAPID_PUBLIC_KEY=' .env | sed 's/^/PUBLIC_/' >> web/.env`. In `npm run dev` werken meldingen niet (geen service worker); gebruik `npm run build && npm run preview`.
2. **Lokaal inloggen.** Met de lokale stack komt de magic link in Mailpit (`http://127.0.0.1:54324`). `config.toml` staat `http://localhost:5173` als redirect toe. Inloggen werkt voor bestaande gebruikers. Of een nieuw adres zich kan aanmelden hangt af van de Supabase-instelling "Allow new users to sign up" (vanaf WP-22, zie §17.6). Lokaal staat aanmelden aan; maak jezelf anders eenmalig aan via het Supabase Dashboard (Authentication, Users, Add user) of lokaal via Studio.
3. **Cloudflare Pages (eenmalig, Lars).**
   - Workers & Pages, Create, Pages, Connect to Git, repo `LarsTout/shakka`;
   - production branch `main`;
   - framework preset "None", root directory leeg (repo-root), build command `cd web && npm ci && npm run build`, build output directory `web/build`. De app importeert `data/contracts/*.json` buiten `web/`; daarom bouwt Pages vanaf de repo-root (WP-14). Optioneel: build watch paths `web/*` en `data/contracts/*`, zodat een push die alleen `ingest/` raakt geen Pages-build start (gratis tier: 500 builds per maand);
   - Preview branches: alle niet-productiebranches (dus `develop` en `wp/*`);
   - environment variables voor **Production en Preview**: `PUBLIC_SUPABASE_URL`, `PUBLIC_SUPABASE_PUBLISHABLE_KEY`, `PUBLIC_VAPID_PUBLIC_KEY` (zie §14 punt 4) en `NODE_VERSION=24.22.0` (het standaardimage heeft Node 22.16, en dat is te oud voor SvelteKit 3; `web/.nvmrc` wordt vanaf de repo-root niet gelezen). Installeert 24.22.0 niet, gebruik dan een eerdere 24.x vanaf 24.15.
4. **Supabase Auth (Lars).** Authentication, URL Configuration:
   - Site URL: `https://<project>.pages.dev`;
   - Redirect URLs: `https://<project>.pages.dev`, `https://<project>.pages.dev/**`, `https://*.<project>.pages.dev`, `https://*.<project>.pages.dev/**`, `http://localhost:5173` en `http://localhost:5173/**`.
5. **Beperkingen.** De standaard-SMTP mailt alleen naar teamleden van het project, max. 2 per uur. Die beperking geldt tot je eigen SMTP instelt (§17.6). Een inloglink is één keer bruikbaar en verloopt na 1 uur. Op iOS heeft een app op het beginscherm eigen opslag, los van Safari. Een magic link uit de mail logt je in Safari in, niet in de geïnstalleerde app. In de beginschermapp log je daarom in met 'Inloglink plakken' op de inlogpagina. De link werkt één keer, en een linkvoorvertoning (ingedrukt houden in Mail) laadt de link en gebruikt hem op. Zet daarom eerst de voorvertoningen uit: houd in Mail een link in een ándere mail ingedrukt en kies 'Verberg linkvoorvertoningen' (iOS onthoudt die keuze). Houd daarna de inloglink ingedrukt, kies 'Kopieer link' en plak hem in de app. Alternatief: kopieer de link op je Mac (rechtermuisknop, 'Kopieer link') en plak hem via het gedeelde klembord; niet via WhatsApp of Berichten, want die laden ook een voorvertoning. Met de standaard-SMTP kun je hoogstens 2 links per uur aanvragen, dus wees zuinig met pogingen.
6. **App-icoon vervangen.** Vervang de PNG's in `web/static/icons/` door bestanden met dezelfde naam en afmeting. `npm run icons` maakt de placeholders opnieuw.
7. **Spotlijst, spotpagina en `/go` (vanaf WP-14).** De app leest alleen `spots`, `evaluations`, `tide_extremes` en (vanaf WP-12) `marine_hours`. Het oordeel gebruikt de standaardgrenzen van de spot, niet de persoonlijke instellingen. "Ouder dan 3 uur" kijkt naar `evaluated_at`; die is ook vers als alleen de forecast-ingest faalt, dus controleer bij twijfel `ingest_runs` (§13.5). Donkere uren (reden `dark`) zijn op de spotpagina standaard verborgen. `/go?spot=...&start=...&end=...` (de "ik ga"-link in een melding) opent vanaf WP-20 "Sessie aanmaken", vooraf ingevuld. Uitgelogd vraagt de app eerst om in te loggen, en binnen een uur na het inloggen gaat hij terug naar dezelfde link. Ongeldige parameters gaan naar `/`. De app pagineert per 1000 rijen; zet de Supabase-instelling "Max rows" (API settings) niet lager dan 1000.
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
10. **Sessies aanmaken en delen (vanaf WP-20).**
   - Organiseren kan alleen met een account; in M3 is dat alleen Lars (§11.2). De crew meldt zich aan via de link, zonder account (WP-21).
   - Aanmaken kan via een melding ("ik ga"-link), via "Ik ga" op de spotpagina (alleen zichtbaar als je bent ingelogd), of via Mijn sessies, Nieuwe sessie. Daarna deel je de link `https://<project>.pages.dev/s/<code>` via WhatsApp, het deelmenu of kopiëren.
   - Hoogstens 10 nieuwe sessies per 24 uur (§16.4). Een sessie duurt hoogstens 16 uur, op één dag, van vandaag tot hoogstens een jaar vooruit.
   - De Tikkie-link moet beginnen met `https://tikkie.me/` (de app weigert andere links).
   - Bewerken en annuleren doe je in Mijn sessies. Deelnemers krijgen daar geen bericht van. Verwijderen kan niet; een sessie verdwijnt 7 dagen na het einde (§16.1).
   - Op dit apparaat bewaart de app de voornaam (`shakka:organizer_name`) en, bij inloggen vanuit een link, hoogstens een uur lang die link (`shakka:return_to`).
   - Controle (WP-20 AC-6): zie de procedure in `docs/wp/WP-20/blueprint.md`, Testplan.

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
1. **Wat draait er.** Elk uur om :17 UTC (geen garantie: GitHub kan vertragen of een run overslaan) draait `shakka run-hourly`: `spots_sync`, `forecast`, `marine`, `tides`, `evaluate`, `alerts`, `sessions_cleanup` en `usage_report` (§17.1), met foutisolatie per stap en een tijdsbudget voor de hele run (§17.3). De schedule draait de code van `main`, met het workflowbestand van `develop` (de default branch). Alleen als de variable `HOURLY_ENABLED` op `true` staat. Er draait één run tegelijk.
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
   - bij `run_time_budget`: de run had na 600 s nog stappen te gaan; die zijn `skipped` en staan als `::error::` in de annotaties (§17.3);
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
4. **Cloudflare Pages (WP-18).** Zet `PUBLIC_VAPID_PUBLIC_KEY` (Production en Preview) op exact dezelfde waarde als `VAPID_PUBLIC_KEY` en deploy opnieuw. Zonder deze variabele toont de app 'Meldingen zijn in deze versie van Shakka nog niet beschikbaar.' Een andere sleutel dan die van de ingest geeft bij elke aflevering 403 (punt 7 en 10).
5. **Database.** `supabase db push` na de merge (§8): de migratie maakt `push_subscriptions`.
6. **Controleren (na WP-18).** `cd ingest && uv run shakka alerts test-push --user-id <id>` stuurt een testmelding naar elk apparaat. Per apparaat `ok`, `failed (<reden>)` (tijdelijk, het abonnement blijft) of `gone (...); subscription removed` (dood, verwijderd). Daarna `sent`, `failed` en `removed`, en `test-push: ok` (minstens één geslaagd) of `test-push: failed` (exitcode 1).
7. **Tellers in `ingest_runs`** (stap `alerts`): `sent`, `failed`, `no_target`, `deferred`, `push_non_retryable`, `blocked_targets`, `removed`, `push_enabled` en `push_failures` (per reden, bijvoorbeeld `{"HTTP 503": 2}`).
   - `deferred` komt alleen bij 429, 5xx en netwerkfouten: voor een favoriet slaagde geen aflevering en minstens één fout was tijdelijk. De state is niet opgeslagen en de volgende run probeert het opnieuw. Zichtbaar als `::warning::alerts: <n> favorite(s) deferred ...` in de Actions-log.
   - `push_non_retryable`: HTTP 400, 401, 403, 413 en andere 4xx (behalve 404, 410 en 429) worden niet herhaald. Het event is voor dat apparaat verloren, de state wordt wel opgeslagen en het abonnement blijft staan. Dan staat er `::warning::alerts: <n> push delivery(ies) failed without retry ...` in de Actions-log en is de stap `partial` (exitcode 0, geen mail).
   - Staat die warning in elke run en toont `push_failures` `HTTP 403`, controleer dan of `PUBLIC_VAPID_PUBLIC_KEY` in Cloudflare gelijk is aan `VAPID_PUBLIC_KEY` en volg punt 10.
   - `blocked_targets`: abonnementen op een host buiten de lijst van toegestane push-diensten; zie §17.4.
8. **Zonder VAPID-secrets** is het kanaal uit: een `::warning::` per run en de state schuift door zonder melding. Een onvolledige of ongeldige configuratie laat de stap `alerts` falen (mail van GitHub).
9. **Overgang naar push (optioneel).** Wie push aanzet nadat hij al favorieten had (Lars bij de overgang uit M1, maar ook elke latere gebruiker), krijgt de lopende windows niet als melding. Wil je dat voor één gebruiker toch: na het aanzetten van push in de app de SQL `delete from public.alert_state where user_id = '<id>' and status = 'active';` in de SQL Editor; de volgende run pusht de lopende windows als nieuw.
10. **Sleutels vervangen.** Zet de nieuwe sleutels overal, draai daarna `delete from public.push_subscriptions;` (oude abonnementen werken niet met een nieuwe sleutel) en zet push in de app opnieuw aan.
11. **Privacy.** Endpoints, sleutels en het subject komen nooit in logs of uitvoer. `shakka alerts run` levert lokaal ook echt af; gebruik `--dry-run` om niets te sturen.
12. **Meldingen aanzetten (vanaf WP-18).** Android en computer: open Shakka, log in, ga naar Alerts en tik "Meldingen aanzetten". iPhone en iPad (iOS 16.4 of nieuwer): eerst in Safari "Zet op beginscherm", dan Shakka vanaf het beginscherm openen, daar inloggen (inloglink plakken, §11 punt 5) en op Alerts aanzetten. Installeer de productie-URL, want de "ik ga"-links in meldingen wijzen daarheen (`APP_BASE_URL`).
13. **Na een deploy.** Een nieuwe versie van de service worker wordt pas actief als alle vensters van Shakka dicht zijn. Sluit de app na een deploy helemaal (op iOS: wegvegen in de appkiezer; op Android: uit de recente apps vegen; op een computer: alle tabbladen van Shakka sluiten) en open hem opnieuw. Herhaal dat tot "Meldingen aanzetten" werkt; soms is het twee keer nodig (de eerste keer haalt de browser de nieuwe versie op, de tweede keer wordt die actief). Zegt de app "Er staat een nieuwe versie van Shakka klaar", sluit en open dan nog een keer.
14. **Uitloggen en gedeelde apparaten.** Uitloggen verwijdert het abonnement van dit apparaat (dat kan tot 5 seconden duren; de knop toont dan "Uitloggen…"); daarna krijgt het apparaat geen meldingen meer. Zet iemand anders op hetzelfde apparaat meldingen aan, dan krijgt het apparaat een nieuw abonnement en gaan de meldingen van het vorige account er niet meer heen. Per account gelden hoogstens 10 apparaten; bij een elfde verdwijnt het oudste. De database staat er hoogstens 20 per account toe (migratie van WP-22). Bij precies 20 geeft het opnieuw aanmelden van een bestaand apparaat een algemene foutmelding in plaats van "staat al aan"; verwijder dan oude abonnementen in de SQL-editor (`delete from public.push_subscriptions where user_id = '<id>' and last_success_at is null;`, of de oudste).
15. **Controle (WP-18 AC-5).** Zie punt 6 voor `test-push`. Een tik op de testmelding opent de startpagina. Voor een echte alert: punt 9 (actieve rijen verwijderen) en `uv run shakka alerts run`; tik op de melding, die opent de "ik ga"-link of de spotpagina. Noteer hoeveel van de titel (max. 50 tekens) en de body (max. 150 tekens) zichtbaar is op het vergrendelscherm en in de uitgeklapte melding.

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

## 16. Sessies en RSVP (vanaf WP-19)
1. De bewaartermijn is 7 dagen na het einde van een sessie (`ends_at`). De uurlijkse stap `sessions_cleanup` verwijdert oudere sessies met hun RSVP's. In `ingest_runs.steps` staat `counts.deleted`. De termijn staat op twee plekken: `interval '7 days'` in `purge_expired_sessions` en `SESSION_RETENTION` in `shakka.jobs.sessions`; `test_session_retention_matches_migration` bewaakt dat ze gelijk blijven.
2. Na de merge: `supabase db push` (§8.3), en wel vóór de promotie naar `main`, want de schedule draait de code van `main` (§13.1) en de stap `sessions_cleanup` faalt zolang de RPC ontbreekt (`PGRST202`, elk uur een `::error::`-annotatie, geen mail). Controleer eerst in de SQL-editor dat pgcrypto in het schema `extensions` staat: `select extnamespace::regnamespace from pg_extension where extname = 'pgcrypto';` moet `extensions` geven. De migratie zelf stopt met een fout als dat niet zo is; push dan niet verder en meld het, want `rsvp_create` gebruikt `extensions.gen_random_bytes`.
3. Geeft een RPC direct na de push `PGRST202` (functie niet gevonden), voer dan in de SQL-editor `notify pgrst, 'reload schema';` uit.
4. Limieten: hoogstens 30 RSVP's per sessie, hoogstens 10 nieuwe RSVP's per sessie per 10 minuten, hoogstens 10 nieuwe sessies per organisator per 24 uur. Er wordt geen IP-adres opgeslagen.
5. Een aanmelding verwijderen doet de organisator zelf op `/sessie/<slug>/beheer` (vanaf WP-25). Terugvaloptie, of bij misbruik over meerdere sessies: de SQL-editor, met `delete from public.sessions where slug = '<slug>';` (de RSVP's gaan mee) of `delete from public.rsvps where id = '<id>';`.
6. Geen enkele API-rol mag `rsvps` direct lezen, ook de ingest niet. Ook `sessions` is niet leesbaar voor `service_role` (bewust, zie §8.2). Kijken kan alleen via de SQL-editor (rol `postgres`).
7. De edit-token van een RSVP gaat alleen in de body van een POST-verzoek (de standaard van supabase-js voor `rpc()`), nooit in een URL, querystring of link: URL's komen in logs van de gateway terecht. In de database staat alleen de sha256-hash. Log de token ook nergens anders.
8. **Publieke sessiepagina (vanaf WP-21).**
   - `/s/<slug>` werkt zonder account. Je ziet de sessie, de deelnemers, de carpool en het oordeel per uur, en je meldt je aan met alleen een voornaam.
   - De edit-token staat alleen in de browser van de bezoeker (`localStorage`, sleutel `shakka:rsvp:<slug>`). Wie een andere browser of de in-app-browser van WhatsApp gebruikt, of de websitedata wist, kan zich daar niet meer afmelden.
   - Een RSVP voor iemand verwijderen: de organisator via 'Mijn sessies' → 'Aanmeldingen beheren'. Anders punt 5.
   - De pagina heeft `noindex`. Zoekmachines nemen hem niet op, maar iedereen met de link kan de voornamen zien.
9. **Controle (WP-21 AC-7).**
   - Zonder WP-20 maak je een testsessie in de SQL-editor:
     ```sql
     insert into public.sessions (slug, spot_id, organizer_id, organizer_name, starts_at, ends_at, seats_free, departure_point)
     values ('<eigen slug, 10-64 tekens A-Z a-z 0-9 _ ->', '<spot-id>', '<jouw user-id>', 'Lars',
             date_trunc('hour', now()) + interval '1 day', date_trunc('hour', now()) + interval '1 day 4 hours', 3, 'Utrecht CS');
     ```
   - Open `https://<project>.pages.dev/s/<slug>` op een telefoon zonder in te loggen, bijvoorbeeld via een link in WhatsApp. Meld je aan, wijzig je aanmelding (bijvoorbeeld naar "Ik kan mensen meenemen") en meld je af.
   - Controleer in de SQL-editor dat de RSVP weg is.
   - Ruim de testsessie op met `delete from public.sessions where slug = '<slug>';`.
10. **Moderatie (vanaf WP-25).**
   - De organisator kan op `/sessie/<slug>/beheer` (via 'Mijn sessies' → 'Aanmeldingen beheren') een aanmelding verwijderen en het aanmelden sluiten of weer openen. Sluiten blokkeert alleen nieuwe aanmeldingen; wie al aangemeld is, kan nog wijzigen en afmelden.
   - Na de merge: `supabase db push` voor `20261028090000_organizer_moderation.sql`, vóór de promotie naar `main`. Tot die tijd geeft 'Verwijderen' een foutmelding en lukt sluiten niet; `/s/<slug>` blijft gewoon werken, want de pagina leest een ontbrekende `rsvps_closed` als open.
   - Geeft een RPC direct na de push `PGRST202`: punt 3.
   - Controle (AC-7, door Lars): maak een testsessie en meld je er op `/s/<slug>` twee keer aan, met verschillende voornamen. Open `/sessie/<slug>/beheer` ingelogd als organisator. Verwijder één aanmelding en controleer dat die ook op `/s/<slug>` weg is. Sluit het aanmelden en controleer dat `/s/<slug>` de melding toont en geen formulier, en dat een bestaande aanmelding nog kan wijzigen en afmelden. Open het aanmelden weer en controleer dat het formulier terugkomt. Een tweede account kan de beheerpagina van deze sessie niet gebruiken (toont 'Sessie niet gevonden'). Ruim de testsessie op (punt 5).


## 17. Privacy, CSP en performance (vanaf WP-23)
1. `npm run build` schrijft `build/_headers` uit het sjabloon `web/static/_headers` (`scripts/write-headers.mjs`: Supabase-origin uit `PUBLIC_SUPABASE_URL`, hashes van de inline scripts in `index.html`). Een nieuwe externe origin (fetch, img, worker) vraagt een aanpassing van het sjabloon, van `checkHeaders` en van `docs/PRIVACY.md`.
2. `node scripts/check-bundle-size.mjs` (vanuit `web/`, na een build; ook `npm run size`). Gemeten bij WP-23 (gzip, niveau 9): initiële JS 102,4 kB (budget 150 kB), precache 595,2 kB (budget 900 kB), MapLibre-chunk 279,5 kB.
3. Supabase: Authentication → Audit Logs → "Write audit logs to the database" uit. Regio van het project controleren (EU).
4. Cloudflare Pages: Web Analytics uit. Laat Rocket Loader, Email Address Obfuscation en vergelijkbare functies uit als er ooit een eigen domein komt: die voegen scripts in die de CSP blokkeert.
5. Controle na deploy (AC-6), op een preview van `develop`:
   - `curl -sI https://<preview>/ | grep -iE 'content-security-policy|referrer-policy'`;
   - `curl -sI https://<preview>/s/AAAAAAAAAA | grep -i x-robots-tag`;
   - `curl -sI https://<preview>/spot/x | grep -i content-security-policy` (SPA-fallback);
   - in Chrome DevTools geen CSP-meldingen in de console bij: `/` laden, "Kaart", inloggen via de magic link, `/alerts` met meldingen aan/uit, `/s/<slug>` met aanmelden en afmelden, en `/profiel`;
   - Lighthouse (DevTools, Mobile, Navigation) op `/` en een spotpagina: toegankelijkheid ≥ 90, performance ≥ 80;
   - Application → Manifest → Installability zonder fouten;
   - account verwijderen met een testaccount (in het dashboard aangemaakt): daarna geen rij meer in `auth.users`, en de pagina toont de melding.
6. Terugdraaien bij een CSP-probleem in productie: verwijder de regel `Content-Security-Policy` uit `web/static/_headers` (en de check in `checkHeaders` tijdelijk), push en deploy. Andere headers blijven staan.
7. Na de merge: `supabase db push` voor de migratie `20261016090000_delete_my_account.sql`.

## 18. Hardening en kostenbewaking (vanaf WP-22)

Veldjes die Lars invult staan onderaan §18.6 en §18.9.

1. **Gebruiksrapport en waarschuwingen.**
   - De laatste stap van de uurlijkse run, `usage_report`, leest elk uur het Open-Meteo-verbruik (`api_usage`) en de databasegrootte (RPC `db_usage`). Het volledige rapport staat in `ingest_runs`, stap `usage_report`, `counts.report`.
   - Elke maandag tussen 08:00 en 22:00 (Europe/Amsterdam) gaat een korte samenvatting als pushmelding naar de apparaten van Lars (`OPERATOR_USER_ID`), tot het één keer gelukt is. Valt de maandag weg, dan komt het rapport pas de volgende maandag.
   - Drempels: database boven 300 MB (1 MB = 1024 × 1024 bytes, zoals het dashboard), Open-Meteo boven 7.000 calls op de UTC-dag of boven 210.000 in de UTC-maand (70% van de echte limieten). Een waarschuwing staat elk uur als `::warning::usage_report: usage threshold: ...` in de Actions-log zolang de drempel overschreden is. De pushmelding gaat hoogstens één keer per lokale dag en alleen tussen 08:00 en 22:00. Op maandag bevat het weekrapport de waarschuwingen zelf.
   - De stap ruimt in de weekrapport-run ook `ingest_runs` op die ouder zijn dan 90 dagen.
   - Lokaal lezen zonder iets te versturen: `cd ingest && uv run shakka usage show`. Een regel `error   ...` betekent dat een bron niet leesbaar was (exitcode 1).
   - Ontbreekt `OPERATOR_USER_ID`, of heeft Lars geen abonnement, dan wordt het rapport wel opgeslagen en staat er een note-annotatie. Een ongeldige waarde (geen UUID) maakt de stap `partial`, zonder de waarde te tonen.
2. **`OPERATOR_USER_ID` instellen.**
   - Dashboard, Authentication, Users, kopieer de UID van je eigen account.
   - `gh secret set OPERATOR_USER_ID` (plak de waarde bij de prompt, niet met `--body`) en zet dezelfde waarde in `.env`.
   - Zet pushmeldingen aan op je telefoon (§14.12). De waarde wordt in logs en in `ingest_runs` geredigeerd.
3. **Retries en budgetten.**
   - Alle externe HTTP-aanroepen lopen via één retry-helper (`shakka.http.with_retries`):

     | Bron | Opnieuw bij | Pogingen | Wachttijd (s) |
     |---|---|---|---|
     | Open-Meteo | transportfout, 429, 5xx | 3 | 1, 2; `Retry-After` bij 429 (1 tot 30) |
     | Rijkswaterstaat | transportfout, 429, 5xx | 3 | 1, 2 |
     | Supabase REST | transportfout, 429, 502, 503, 504, 520 tot 524; alleen select, upsert, update en delete | 3 | 0,5 en 1 |
     | Web Push | geen retry in de run; de deferral (§14.7) is de retry | - | - |

   - `insert` en `rpc` worden bewust niet herhaald (een insert kan dubbel staan). Is een update of delete wel doorgevoerd maar ging het antwoord verloren, dan geeft de herhaling 0 rijen terug; tellers als `removed` en `deleted` zijn dus indicatief.
   - Stroomonderbreker: maakt één Supabase-aanroep al zijn pogingen op met een herhaalbare fout, dan doet de rest van die run nog maar één poging per aanroep (log: `db: retries disabled for the rest of this run`).
   - Tijdsbudget voor de hele run: 600 s, gecontroleerd vóór elke stap. Daarna zijn alle resterende stappen `skipped` met reden `run_time_budget`, met een `::error::` per stap en exitcode 1 (mail van GitHub). Omdat `alerts` na de ingeststappen komt, is dat bij een trage ingest juist de stap die wordt overgeslagen; de volgende run doet hem opnieuw met de dan aanwezige data. De job-timeout is 900 s; het getijbudget van 240 s blijft bestaan.
   - Veroudering per spot: de evaluatie- en de alertjob laten forecastrijen weg met `fetched_at` ouder dan 3 uur. Een spot met alleen oude rijen krijgt geen nieuwe evaluaties (de app toont dan zelf "verouderd") en een favoriet daarop wordt `ineligible`. Begrensd, niet eerlijk tot op het uur: de forecast achter een oordeel kan tot ongeveer 6 uur oud zijn voordat de app "verouderd" toont (3 uur tot de laatste evaluatie, daarna 3 uur voor de banner).
4. **Push.**
   - Alleen deze endpoints krijgen een push: `https://` zonder poort en zonder gebruikersnaam, met host `fcm.googleapis.com` of `jmt17.google.com` (het FCM-stagingendpoint van Chrome Beta, Dev en Canary), of een subdomein van `push.services.mozilla.com`, `push.apple.com` of `notify.windows.com`. `android.googleapis.com` (oude GCM) staat bewust niet in de lijst.
   - Een abonnement op een andere host wordt overgeslagen en telt in `blocked_targets`, met een `::warning::alerts: <n> push subscription(s) skipped: push service host not allowed`. Herstel: controleer de host van het endpoint (SQL-editor, alleen de host bekijken), voeg hem toe aan `PUSH_SERVICE_HOSTS` of de suffixen in `ingest/src/shakka/notify/base.py` en maak een release.
   - De database staat hoogstens 20 abonnementen per gebruiker toe (de app houdt er 10).
5. **Migraties van WP-22.**
   - `supabase db push` na de merge en vóór de promotie naar `main`. Zonder de migratie is `usage_report` elk uur `partial` (`PGRST202`). Staat de migratie van WP-23 (`20261016090000_...`) al op het remote project, gebruik dan `supabase db push --include-all`, omdat de migraties van WP-22 een eerdere tijdstempel hebben.
   - Bij `PGRST202` na het pushen: `notify pgrst, 'reload schema';` in de SQL-editor.
   - De migraties verwijderen de ongebruikte kolom `profiles.telegram_chat_id`, voegen `db_usage()` toe (alleen `service_role`) en twee triggers: de grens van 20 abonnementen en de bovengrens voor `sessions.starts_at` (hoogstens 370 dagen vooruit; de app staat 365 toe). De sessiegrens controleert bestaande rijen niet.
6. **Eigen SMTP en aanmelden.**
   - **Eerst, los van deze WP:** controleer in het Supabase Dashboard (Authentication, de algemene instellingen) dat "Allow new users to sign up" **uit** staat. De app stuurt vanaf WP-22 `shouldCreateUser: true`; of een nieuw adres een account krijgt, bepaalt alleen deze serverinstelling. Staat ze uit, dan geeft GoTrue `signup_disabled` en toont de app "nog niet inloggen"; bestaande gebruikers loggen gewoon in.
   - Eisen aan de maildienst: een gratis tier, open- en kliktracking aantoonbaar uit, een geverifieerde afzender.

     | Dienst | Gratis | Tracking | Eigen domein nodig | Oordeel |
     |---|---|---|---|---|
     | Resend | 3.000 per maand, 100 per dag | standaard uit voor alle domeinen | Ja | Voorkeur als er een domein is |
     | Postmark | 100 per maand | opens en links standaard uit | Ja, plus handmatige goedkeuring | Voldoet, maar 100 per maand is te weinig zodra aanmelden open is |
     | Gmail (apart Google-account voor Shakka) | 500 per dag | geen tracking-functie; bevestig met de test hieronder | Nee | Voorkeur zonder domein, met kanttekeningen |
     | Brevo | 300 per dag | bij transactionele mail niet uit te zetten op de gratis tier | Nee | Afgewezen |
     | SMTP2GO | 1.000 per maand | standaard niet te verifiëren | Onduidelijk | Niet voorgesteld |

   - **Met een eigen domein: Resend.** Host `smtp.resend.com`, poort 465 (SMTPS) of 587 (STARTTLS), gebruiker `resend`, wachtwoord = een Resend-API-sleutel met permission `sending_access`. Zet tracking niet aan. Let op: een domein kost geld (registratie per jaar). Dat is een betaalde dienst en vergt het akkoord van Lars.
   - **Zonder domein: een apart Gmail-account voor Shakka** (niet je persoonlijke adres), met tweestapsverificatie en een app-wachtwoord. Host `smtp.gmail.com`, poort 465 (SSL) of 587 (TLS), gebruiker = het volledige Gmail-adres, wachtwoord = het app-wachtwoord. Kanttekeningen: Google raadt app-wachtwoorden af en kan ze intrekken (dan stoppen de inloglinks tot er een andere dienst is), de afzender is een `@gmail.com`-adres en Google verwerkt de adressen van de ontvangers.
   - De keuze is aan Lars. Instellen: Authentication, SMTP Settings: host, poort, gebruiker, wachtwoord of sleutel, afzenderadres, afzendernaam "Shakka".
   - **Test (AC-6):**
     1. eigen SMTP is ingesteld, "Allow new users to sign up" staat nog uit;
     2. maak een testgebruiker aan via Authentication, Add user, mét "Auto Confirm User" (een onbevestigde gebruiker krijgt `signup_disabled` zolang aanmelden uit staat);
     3. vraag in de app een inloglink aan: de mail komt aan;
     4. de link in de mail wijst direct naar `https://<project-ref>.supabase.co/auth/v1/verify?...` en niet naar een redirect- of trackingdomein van de maildienst. Controleer dat door de link te kopiëren in plaats van erop te klikken;
     5. inloggen met die link lukt;
     6. pas daarna "Allow new users to sign up" aanzetten.
   - Daarna moet "De maildienst" op `/privacy` en in `docs/PRIVACY.md` de gekozen dienst noemen (bij Gmail ook dat Google de adressen van de ontvangers verwerkt): een kleine vervolgwijziging.
   - Gekozen SMTP-dienst: nog in te vullen door Lars.
7. **Rate limits van Supabase Auth.** Instellen onder Authentication, Rate Limits (niet in `config.toml`; lokaal gebruikt de stack Mailpit). Een overschrijding geeft 429; de app toont dan "Te veel inlogpogingen".

   | Limiet | Default | Voorstel |
   |---|---|---|
   | E-mails per uur | 30 na het instellen van eigen SMTP | daglimiet van de dienst gedeeld door 24, naar beneden afgerond: 4 bij Resend (100 per dag), 20 bij Gmail (500 per dag) |
   | Aanmeldingen en inlogpogingen | 30 per 5 minuten per IP | de default |
   | OTP-aanvragen per gebruiker | 60 s ertussen | de default |
   | Verificaties | 30 per 5 minuten | de default |
   | Token refreshes | 150 per 5 minuten | de default |

   Een hogere limiet voor e-mails per uur kan, als je accepteert dat bij misbruik de daglimiet van de dienst bereikt wordt (dan werken inloglinks tot de volgende dag niet). Postmark (100 per maand) valt af zodra aanmelden open is.
8. **Maandcheck (handmatig, eerste werkdag van de maand).**

   | Dienst | Waar | Gratis grens | Actie bij |
   |---|---|---|---|
   | Supabase egress | Dashboard, Usage | 5 GB | > 3,5 GB |
   | Supabase database | Dashboard, Usage, en het weekrapport | 500 MB | > 300 MB |
   | Open-Meteo | Weekrapport | 10.000 per dag, 300.000 per maand | warning |
   | MapTiler | Cloud, Analytics (requests) | 100.000 requests per maand, alleen tiles | > 70.000 |
   | GitHub Actions | Actions-tab (publieke repo: minuten onbeperkt) | - | Schedule niet actief, of geen run in de laatste 2 uur |
   | Cloudflare Pages | Builds | 500 per maand | > 350 |
   | SMTP-dienst | Dashboard van de dienst | Resend 100 per dag en 3.000 per maand; Gmail 500 per dag | > 70% |
   | Dependencies | Security, Dependabot alerts | - | Open alert (high of critical) zonder PR: punt 10, handmatig |
   | Dependabot-PR's | Pull requests, filter `is:open author:app/dependabot` | - | Open PR: reviewen en mergen (punt 10) |

   MapTiler rekent Shakka in requests, omdat de kaart MapLibre GL JS gebruikt en niet de MapTiler-SDK; de grens van 5.000 map sessions uit het projectplan geldt alleen voor die SDK en is hier niet van toepassing. Vergelijk bij de eerste maandcheck ook de databasegrootte in het weekrapport met het dashboard.

   Dependabot en Cloudflare: elke push naar een `dependabot/*`-branch (een nieuwe PR of een rebase) is een preview-build. Verwacht wordt hoogstens 15 per maand. Komt Builds boven 350, zet dan in Cloudflare Pages bij de automatische preview-deployments "Custom branches" met include `*` en exclude `dependabot/*`. CI bouwt de web-app toch al.
9. **Open-Meteo-bevestiging.** Stuur een korte mail (Engels) aan info@open-meteo.com. Concept:

   > Hello, Shakka is a free public PWA for kitesurfers in the Netherlands, without ads or subscriptions. It reads Open-Meteo forecasts server-side only, caches them per spot, and makes about 40,000 API calls per month. Open-Meteo is credited in the app. We believe this falls under non-commercial use; could you confirm that this is fine?

   Open-Meteo-bevestiging: datum: nog in te vullen door Lars / uitkomst: nog in te vullen door Lars.
10. **Dependency-updates en -audit** (Dependabot plus een handmatige terugval; geen CI-stap, niet automatisch mergen).
    - `.github/dependabot.yml` kijkt op de eerste dag van de maand naar `github-actions` (`/`), `npm` (`/web`) en `uv` (`/ingest`). Minor- en patch-updates komen per ecosysteem als één PR naar `develop`; een major komt als losse PR (hoogstens 3 open PR's per ecosysteem). Een update binnen de grenzen van `package.json` of `pyproject.toml` wijzigt alleen de lockfile. Een PR die een grens in de manifest verruimt, verdient extra aandacht. Majors van `@types/node` worden overgeslagen; die horen bij een Node-upgrade.
    - Aanzetten (eenmalig): Settings, Advanced Security: "Dependabot alerts" en "Dependabot security updates" op Enable. Security updates komen los en buiten de maandplanning, als PR naar `develop` (de default branch).
    - Dependabot-PR's krijgen geen Actions-secrets en een `GITHUB_TOKEN` met alleen leesrechten. CI gebruikt geen secrets (§7) en draait dus gewoon. Een merge op `develop` komt pas in productie bij de promotie naar `main`.
    - Reviewen: CI is groen; bij de `npm`-PR de preview kort openen (kaart, inloggen); bij een Actions-PR in de diff controleren dat elke `uses:` op een SHA van 40 tekens staat, met de nieuwe versie als `# vX.Y.Z` op dezelfde regel. Twee tests bewaken de SHA en de vorm van het commentaar, maar niet of het commentaar bij de SHA hoort.
    - Een PR die CI breekt of die je niet wilt: niet mergen. Losse PR: `@dependabot ignore this major version` (of `minor version`, `this dependency`). Gegroepeerde PR: `@dependabot ignore <pakket> minor version` (of `major version`, of alleen `<pakket>`). Terugdraaien: `@dependabot unignore <pakket>`.
    - Handmatig, als terugval of bij twijfel:
      - Web: `cd web && npm audit --omit=dev --audit-level=high`. Los een bevinding op met een minimale update (`npm update <pakket>` of `npm audit fix --omit=dev`, nooit `--force`) en draai daarna `npm run check && npm test && npm run build`.
      - Ingest: `cd ingest && uv export --format requirements-txt --frozen --no-emit-project -o /tmp/shakka-req.txt && uvx pip-audit --require-hashes --disable-pip -r /tmp/shakka-req.txt`. Bij een bevinding: `uv lock --upgrade-package <pakket>` binnen de grenzen van `pyproject.toml`, dan de volledige test.
      - Een SHA-pin zelf bijwerken: zoek de SHA van de release met `gh api repos/<eigenaar>/<repo>/git/ref/tags/<tag> --jq .object.sha`. Is `object.type` "tag", dereferentieer dan met `gh api repos/<eigenaar>/<repo>/git/tags/<sha> --jq .object.sha`. Schrijf de versie als `# vX.Y.Z` op dezelfde regel achter de SHA.
