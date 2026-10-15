# Work packages Shakka

> Opgesteld door de architect op basis van `docs/PROJECT_PLAN.md` (bron van waarheid). Scope, non-goals en harde randvoorwaarden zijn ongewijzigd. Status per WP staat in `docs/STATUS.md`.

## Afwijkingen van het plan

De opdeling volgt sectie 5, maar is op de volgende punten aangepast. A-1 t/m A-15 maken het bouwen kleiner, beter testbaar of veiliger; geen van die wijzigingen voegt eindgebruikersfunctionaliteit toe of haalt die weg. A-16 en A-17 volgen uit een scopebesluit van Lars (15 oktober 2026) en zijn ook in `docs/PROJECT_PLAN.md` verwerkt.

| # | Afwijking | Reden |
|---|---|---|
| A-1 | **Hernummering.** De WP's zijn opnieuw genummerd (WP-00 t/m WP-23). Zie de mappingtabel hieronder. | Door splitsingen klopte de oude nummering niet meer. Sequentiële nummers houden `/ship WP-XX` eenduidig. |
| A-2 | **Schema per mijlpaal.** WP-01 maakt alleen de tabellen voor M1. `marine_hours` komt in WP-12, `push_subscriptions` in WP-17, `sessions` en `rsvps` in WP-19. Alle tabelnamen en sleutelkolommen staan wel nu al vast (zie de contracten). | RSVP zonder account, edit-tokens en rate limits zijn veiligheidsgevoelig. Die tabellen ontwerp je het best samen met de RPC's die erbij horen. M1 wordt er kleiner door. |
| A-3 | **Tabelnamen.** `forecasts` heet `forecast_hours`, `tides` heet `tide_extremes`, `rules` heet `alert_rules`, `users` heet `profiles`. Erbij komen `favorites`, `api_usage` en `ingest_runs`. | Supabase beheert gebruikers zelf in `auth.users`. De app-gegevens staan in `profiles`. De andere namen beschrijven de inhoud preciezer. `api_usage` is nodig voor de budgetbewaking (sectie 2) en `ingest_runs` voor logging en foutmeldingen (plan-WP-09). |
| A-4 | **Plan-WP-03 is gesplitst.** Wind multi-model zit in WP-03 (M1), golven via de Marine API in WP-12 (M2). | Golven tellen niet mee in de evaluatie of de alerts (sectie 4). Ze worden alleen getoond. M1 heeft ze dus niet nodig. |
| A-5 | **Puur en I/O gescheiden.** Plan-WP-05 en plan-WP-07 worden puur (WP-05, WP-07, WP-08). De koppeling met de database (evaluaties wegschrijven, `alert_state` bijhouden) zit in de nieuwe WP-10; versturen zit sinds A-16 in WP-17. Plan-WP-09 (orkestratie) is daardoor WP-11 en bevat alleen nog workflow, logging en foutmeldingen. | Domeinlogica moet zonder I/O te testen zijn. Als de I/O in dezelfde WP zit, sluipt die er snel toch in. |
| A-6 | **Plan-WP-07 is gesplitst** in WP-07 (alertregels en windows) en WP-08 (deduplicatie en berichtopbouw). | Deduplicatie is de lastigste logica van M1 en verdient een eigen review. |
| A-7 | **Plan-WP-08 is gesplitst.** Telegram was WP-09 (M1; vervallen, zie A-16). Web Push heeft een backend-WP (WP-17) en een PWA-WP (WP-18, was plan-WP-13). | Het plan gaf al M1/M2 aan. De verzendkant en de browserkant hebben elk eigen risico's (VAPID, iOS). |
| A-8 | **Kite-advies (WP-06) hangt af van WP-02, niet van WP-05.** | Kite-advies gebruikt alleen de `Level`-enum en windkracht. Geen evaluatie. |
| A-9 | **Beheer-CLI voor M1** in WP-10 (`shakka admin ...`): profiel, favorieten en alertregels van Lars invoeren en alerts vooraf bekijken zonder UI. | M1 is "geen UI nodig". Zonder deze CLI kun je de alertregels van Lars alleen met losse SQL invoeren. Dit is beheertooling, geen eindgebruikersfunctie. |
| A-10 | **Plan-WP-11 is gesplitst** in WP-14 (spotlijst en spotpagina) en WP-15 (kaart). | De kaart heeft een eigen externe dienst (MapTiler) met een sessielimiet. Lazy laden en de lijst als fallback zijn apart te toetsen. |
| A-11 | **Plan-WP-14 is gesplitst** in WP-19 (datamodel, RLS, RPC's), WP-20 (aanmaken en delen) en WP-21 (publieke pagina en RSVP). | Het was een L. De beveiliging van anonieme RSVP krijgt zo een eigen review. |
| A-12 | **Plan-WP-15 is gesplitst** in WP-22 (backend-hardening en kostenbewaking) en WP-23 (privacy, toegankelijkheid, performance). | Het was een L met twee heel verschillende aandachtsgebieden. |
| A-13 | **Nieuwe Supabase-sleutels.** Er komen `SUPABASE_PUBLISHABLE_KEY` en `SUPABASE_SECRET_KEY` in plaats van `SUPABASE_ANON_KEY` en `SUPABASE_SERVICE_ROLE_KEY`. WP-00 past `.env.example` aan. | Supabase stopt eind 2026 met de legacy `anon`- en `service_role`-sleutels ([bron](https://supabase.com/docs/guides/api/api-keys)). |
| A-14 | **Contractbestanden** in `data/contracts/*.json`. Ze worden gegenereerd uit Python en bevatten redencodes, richtingsklassen en alert-defaults met Nederlandse labels. | De PWA (TypeScript) en de alerts (Python) gebruiken zo exact dezelfde codes en labels. Een test bewaakt dat de bestanden actueel zijn. |
| A-15 | **Database-toegang via de Supabase REST-API (PostgREST over HTTPS)**, niet via een directe Postgres-verbinding. | Op het gratis plan loopt een directe verbinding via IPv6, en GitHub Actions ondersteunt alleen IPv4. Een IPv4-add-on kost geld ([bron](https://supabase.com/docs/guides/database/connecting-to-postgres)). De stack in het plan (httpx) is hiermee voldoende. |
| A-16 | **Telegram vervalt; Web Push is het enige meldingskanaal** (besluit Lars, 15 oktober 2026). WP-09 is `dropped`; de nummering van de andere WP's blijft gelijk. Gevolgen: (1) in M1 berekent WP-10 de alerts en legt ze vast in `alert_state`, zonder kanaal; de berichten zijn controleerbaar via CLI en database. (2) `Notifier`, `DeliveryResult`, `DeliveryTarget` en de afleverregel verhuizen naar WP-17. (3) WP-10 haalt de `telegram_*`-velden uit `Settings` en de `TELEGRAM_*`-variabelen uit `.env.example`; het env-contract wijzigt per WP-10 (WP-00 AC-8 blijft historisch). (4) Operatormeldingen in WP-11 gaan via de ingebouwde e-mailmelding van GitHub bij een gefaalde workflow-run, plus `ingest_runs`. (5) Het wekelijkse gebruiksrapport (WP-22) wordt een pushmelding aan Lars. (6) De kolom `profiles.telegram_chat_id` (WP-01, al gemigreerd) blijft ongebruikt staan en wordt in WP-22 verwijderd. | Scopebesluit van Lars. Eén kanaal minder betekent minder code, geen bot-token en geen tweede account voor gebruikers. De eerste melding op de telefoon schuift daardoor van M1 naar M2. |
| A-17 | **Golven op de spotpagina verhuizen van WP-14 naar WP-12, en WP-14 hangt niet meer af van WP-12.** WP-12 hangt nu af van WP-11 en WP-14. | Gevolg van A-16: om de eerste pushmelding zo vroeg mogelijk te krijgen is de aanbevolen M2-volgorde WP-14 → WP-16 → WP-17 → WP-18 → WP-12 → WP-15. Dat kan alleen als WP-14 niet op de marine-ingest wacht. Golven tellen niet mee in oordeel of alerts (sectie 4), dus de spotpagina is zonder golven al bruikbaar. |

### Mapping plan → work packages

| Plan | Nieuw |
|---|---|
| WP-00 | WP-00 |
| WP-01 | WP-01, plus WP-12 (`marine_hours`), WP-17 (`push_subscriptions`) en WP-19 (`sessions`, `rsvps`) |
| WP-02 | WP-02 |
| WP-03 | WP-03 (wind), WP-12 (golven) |
| WP-04 | WP-04 |
| WP-05 | WP-05 (puur), evaluatiejob in WP-10 |
| WP-06 | WP-06 |
| WP-07 | WP-07, WP-08, alertjob in WP-10 |
| WP-08 | WP-17 (Web Push backend); WP-09 (Telegram) is vervallen, zie A-16 |
| WP-09 | WP-10 (jobs en beheer-CLI), WP-11 (workflow, logging, foutmeldingen) |
| WP-10 | WP-13 |
| WP-11 | WP-14, WP-15 |
| WP-12 | WP-16 |
| WP-13 | WP-18 |
| WP-14 | WP-19, WP-20, WP-21 |
| WP-15 | WP-22, WP-23 |

## Overzicht

| WP | Naam | Mijlpaal | Afhankelijk van | Omvang |
|---|---|---|---|---|
| WP-00 | Repo, tooling, CI en Supabase-koppeling | M1 | - | S |
| WP-01 | Datamodel M1, RLS en database-client | M1 | WP-00 | M |
| WP-02 | Spotprofielen: schema, validatie, sync en startset | M1 | WP-01 | M |
| WP-03 | Forecast-ingest wind (Open-Meteo multi-model) met call-budget | M1 | WP-01 | M |
| WP-04 | Getij-ingest (Rijkswaterstaat) | M1 | WP-01 | M |
| WP-05 | Evaluatie-engine (puur) | M1 | WP-02, WP-03, WP-04 | M |
| WP-06 | Kite-advies (puur) | M1 | WP-02 | S |
| WP-07 | Alertregels en windows (puur) | M1 | WP-05 | S |
| WP-08 | Alert-deduplicatie en berichtopbouw (puur) | M1 | WP-06, WP-07 | M |
| WP-09 | ~~Telegram-kanaal~~ **vervallen** (A-16) | - | - | - |
| WP-10 | Evaluatie- en alertjobs plus beheer-CLI | M1 | WP-02 t/m WP-08 | M |
| WP-11 | Orkestratie: uurlijkse workflow, logging, foutmeldingen | M1 | WP-10 | M |
| WP-12 | Marine-ingest (golven) en golven op de spotpagina | M2 | WP-11, WP-14 | M |
| WP-13 | PWA-basis | M2 | WP-01 | M |
| WP-14 | Spotlijst en spotpagina | M2 | WP-10, WP-13 | M |
| WP-15 | Kaart | M2 | WP-14 | S |
| WP-16 | Profiel, favorieten en alertinstellingen | M2 | WP-07, WP-14 | M |
| WP-17 | Web Push: backend (enige meldingskanaal) | M2 | WP-11 | M |
| WP-18 | Web Push: PWA | M2 | WP-16, WP-17 | M |
| WP-19 | Sessies: datamodel, RLS en RPC's | M3 | WP-11 | M |
| WP-20 | Sessie aanmaken en delen | M3 | WP-14, WP-19 | M |
| WP-21 | Publieke sessiepagina en RSVP zonder account | M3 | WP-14, WP-19 | M |
| WP-22 | Hardening backend en kostenbewaking | M4 | WP-00 t/m WP-21 (zonder het vervallen WP-09) | M |
| WP-23 | Privacy, toegankelijkheid en performance | M4 | WP-00 t/m WP-21 (zonder het vervallen WP-09) | M |

Aantallen: M1 11 (plus het vervallen WP-09), M2 7, M3 3, M4 2. Totaal 23 actieve WP's; nummers WP-00 t/m WP-23.

**Aanbevolen volgorde M2** (A-16, A-17): WP-14 → WP-16 → WP-17 → WP-18 → WP-12 → WP-15. Zo komt de eerste pushmelding zo vroeg mogelijk. De afhankelijkheden laten dit toe: WP-14 wacht alleen op WP-10 en WP-13, WP-16 op WP-07 en WP-14, WP-17 op WP-11, WP-18 op WP-16 en WP-17, WP-12 op WP-11 en WP-14, WP-15 op WP-14. WP-17 hangt niet van de PWA af en mag dus ook parallel aan WP-14 of WP-16 draaien.

## Afspraken die voor alle WP's gelden

### Repository
- De repo is **publiek**: https://github.com/LarsTout/shakka (besluit Lars, 14 oktober 2026). GitHub Actions-minuten zijn daardoor onbeperkt; het runtijdbudget per run is geen acceptatiecriterium.
- Gevolg: alles in de repo is openbaar, ook `data/spots.yaml`. Secrets staan uitsluitend in `.env` en GitHub Secrets.
- Schedules in publieke repo's worden na 60 dagen zonder commits uitgeschakeld; WP-11 neemt hier een maatregel voor op.

### Git en branches (besluit Lars, 14 oktober 2026; geldt vanaf WP-01)
- `main` is stabiel. Lars promoot `develop` naar `main` per mijlpaal (`git merge --ff-only develop` op `main`), na een week gebruik.
- `develop` is de integratiebranch en de default branch op GitHub. Elke WP werkt op `wp/WP-XX`, afgetakt van `origin/develop`, in een eigen git-worktree onder `.claude/worktrees/`. Zo kunnen meerdere WP's tegelijk draaien.
- Een WP komt via een pull request naar `develop`, na groene CI. De orchestrator van `/ship` maakt en merget de PR (`gh`). Nooit direct committen op `main` of `develop`.
- Ook `docs/STATUS.md` wordt op de WP-branch bijgewerkt; de stand op `develop` is dus de stand van wat gemerged is. Afhankelijkheden worden gecheckt tegen `origin/develop`.
- WP-00 is de uitzondering: die is onder de oude regels op `main` gestart en wordt na `done` naar `develop` gefast-forward.
- Gevolgen voor latere WP's: CI (WP-00) draait op `push` en `pull_request` voor alle branches. De uurlijkse cron (WP-11) draait alleen op `main`. Cloudflare Pages (WP-13) bouwt production vanaf `main` en previews vanaf `develop` en PR-branches. Er is één Supabase-project; Lars doet `supabase db push` na de merge van een WP met migraties naar `develop` (zie "Nodig van Lars" per WP).

### Supabase-project
- Aangemaakt op 14 oktober 2026 met: **Data API aan**, **"Automatically expose new tables" uit**, **automatische RLS aan**.
- Gevolg voor elke migratie die een tabel aanmaakt (WP-01, WP-12, WP-17, WP-19): tabellen zijn niet vanzelf bereikbaar via de REST-API. Elke migratie bevat expliciete `grant`-statements per tabel en per rol (`anon`, `authenticated`), naast de RLS-policies. Een tabel zonder grant is onzichtbaar, ook met een geldige policy.
- `supabase/config.toml` en de pgTAP-tests gebruiken dezelfde instelling, zodat de lokale stack het productiegedrag test. De planner van WP-01 controleert hoe dit in `config.toml` wordt vastgelegd.
- Automatische RLS is een vangnet; elke migratie zet `enable row level security` toch expliciet.
- Alle tijden in de database en in Python zijn tz-aware UTC (`timestamptz`, `datetime` met `tzinfo=UTC`). Naive datetimes zijn een fout.
- Lokale logica gebruikt `Europe/Amsterdam`: seizoenssluitingen, weekdagen, tijdvensters, berichten en UI. De constante is `shakka.domain.defaults.LOCAL_TZ`.
- Domein- en jobfuncties krijgen `now: datetime` als parameter. Domeincode roept nooit `datetime.now()`, `date.today()` of `time.time()` aan.
- Wind staat in knopen (`kn`). Richting is in graden (0–359) en geeft aan waar de wind vandaan komt (meteorologisch). Waterstand is in cm ten opzichte van NAP. Golfhoogte is in m, periode in s.
- Uurwaarden horen bij het uur dat begint op `valid_at`. Een window `[start, end)` is halfopen, met `end` = laatste uur + 1 uur.

### Code-indeling `/ingest`
- Het package `shakka` staat in `ingest/src/shakka/`. Tests staan in `ingest/tests/`. Het console-script heet `shakka`.
- **Puur domein:** `shakka.domain.*` importeert alleen de standaardbibliotheek, `pydantic`, `astral`, `zoneinfo` en andere `shakka.domain`-modules. Verboden zijn `httpx`, `ddlpy`, `pywebpush`, `yaml`, `os`, `socket`, `subprocess`, `urllib`, `http`, `pathlib`, `shakka.db`, `shakka.jobs`, `shakka.notify`, `shakka.openmeteo` en `shakka.rws`. Ook `open(`, `.now(`, `.today(`, `utcnow` en `time.time` mogen er niet in staan. De test `ingest/tests/test_domain_purity.py` (uit WP-00) bewaakt dit met AST-analyse.
- I/O-modules: `shakka.db` (database), `shakka.http` (HTTP-clientfabriek), `shakka.openmeteo`, `shakka.rws`, `shakka.notify`, `shakka.spots` (YAML en sync), `shakka.jobs.*` (jobs), `shakka.pipeline` (uurlijkse run), `shakka.contracts` (export van contractbestanden).
- Elke `httpx.Client` komt uit `shakka.http.make_client()` en heeft een expliciete timeout.

### Commando's
- Ingest: `cd ingest && uv run pytest`, en `cd ingest && uv run ruff check . && uv run ruff format --check .`
- Database: `supabase start` (lokaal, Docker), `supabase db reset`, `supabase test db`
- Web: `cd web && npm run check && npm test && npm run build`

### Omgevingsvariabelen (contract)

| Variabele | Waar | Gebruikt door | Vanaf |
|---|---|---|---|
| `SUPABASE_URL` | `.env`, GitHub Secret | ingest | WP-00 |
| `SUPABASE_PUBLISHABLE_KEY` | `.env` | ingest (`shakka doctor`) | WP-00 |
| `SUPABASE_SECRET_KEY` | `.env`, GitHub Secret | ingest | WP-00 |
| `APP_BASE_URL` | `.env`, GitHub Actions variable | ingest: "ik ga"-links in berichten | WP-14 |
| `VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY`, `VAPID_SUBJECT` | `.env`, GitHub Secrets | ingest | WP-17 |
| `OPERATOR_USER_ID` (voorstel, de planner van WP-22 bevestigt) | `.env`, GitHub Secret | ingest: push-abonnementen van Lars vinden voor het gebruiksrapport | WP-22 |
| `PUBLIC_SUPABASE_URL`, `PUBLIC_SUPABASE_PUBLISHABLE_KEY` | `web/.env`, Cloudflare Pages | web | WP-13 |
| `PUBLIC_MAPTILER_KEY` | `web/.env`, Cloudflare Pages | web | WP-15 |
| `PUBLIC_VAPID_PUBLIC_KEY` | `web/.env`, Cloudflare Pages | web | WP-18 |

Het env-contract wijzigt per WP-10 (A-16): `TELEGRAM_BOT_TOKEN` en `TELEGRAM_CHAT_ID` vervallen en verdwijnen uit `.env.example`, `Settings` en de GitHub Secrets. WP-00 AC-8 beschrijft de stand bij WP-00 en blijft als historisch criterium staan.

Het root-bestand `.env.example` bevat alleen de ingest-variabelen. `web/.env.example` (uit WP-13) bevat de `PUBLIC_*`-variabelen. Supabase CLI-gegevens (access token, DB-wachtwoord) blijven bij Lars en komen nergens in de repo.

### Bewaking van de harde regels

| Regel | Waar afgedwongen |
|---|---|
| Offshore en side-offshore zijn altijd `no_go` | WP-05 (evaluatie, eigenschapstests), WP-07 (regels kunnen deze klassen niet bevatten), WP-01 (DB-check op `alert_rules.dir_classes`), WP-10 (alerts nooit bij offshore), WP-16 (UI biedt ze niet aan) |
| Open-Meteo alleen server-side | WP-03 (Open-Meteo-hosts staan alleen in `shakka.openmeteo`), WP-13 (guard-script in CI op `web/`), WP-23 (CSP `connect-src` zonder Open-Meteo) |
| Bronvermelding zichtbaar | WP-13 (`Attribution.svelte` in de footer, getest), WP-14 en WP-21 (op de spot- en sessiepagina) |
| Geen secrets in code | WP-00 (grep-check), WP-11 en WP-17 (tests dat secrets en push-endpoints niet in logs komen) |
| Minimale persoonsgegevens in openbare logs | De repo is publiek, dus de Actions-logs ook. WP-10, WP-11 en WP-17 loggen geen user-id's, e-mailadressen, berichtteksten of push-endpoints. |
| Geen scraping | Geen enkele WP haalt HTML van derden op. Bronnen: Open-Meteo API, Rijkswaterstaat API, handmatige spotdata. |
| €0 per maand | Alleen gratis tiers. Budgetbewaking in WP-03, WP-12 en WP-22. |

### Gecontroleerde externe documentatie (oktober 2026)

| Onderwerp | Bevinding die een contract raakt | Bron |
|---|---|---|
| Open-Meteo Forecast API | Endpoint `https://api.open-meteo.com/v1/forecast`; hourly `wind_speed_10m`, `wind_direction_10m`, `wind_gusts_10m`; `wind_speed_unit=kn`; `models=` kommagescheiden; meerdere coördinaten kommagescheiden; `forecast_days` 0–16 | https://open-meteo.com/en/docs |
| Open-Meteo KNMI | `knmi_harmonie_arome_netherlands` (2 km, 2,5 dag, elk uur) met `wind_gusts_10m` | https://open-meteo.com/en/docs/knmi-api |
| Open-Meteo Marine | Endpoint `https://marine-api.open-meteo.com/v1/marine`; `wave_height`, `wave_period`, `wave_direction`; max. 8 dagen; beperkte nauwkeurigheid aan de kust; vermelding van DWD vereist | https://open-meteo.com/en/docs/marine-weather-api |
| Open-Meteo limieten | 600/min, 5.000/uur, 10.000/dag, 300.000/maand. Meer dan 10 variabelen of meer dan 2 weken telt fractioneel mee. Het gewicht schaalt met variabelen × modellen × dagen en daarna × locaties. | https://open-meteo.com/en/pricing, https://github.com/open-meteo/open-meteo/issues/464 |
| Open-Meteo licentie | CC BY 4.0. Link "Weather data by Open-Meteo.com" bij de data. Onderliggende bronnen zijn o.a. DWD, ECMWF, NOAA en KNMI. | https://open-meteo.com/en/licence |
| Rijkswaterstaat | De oude WaterWebservices zijn uitgezet. Huidig is `https://ddapi20-waterwebservices.rijkswaterstaat.nl/`. CC0. Astronomische voorspelling via `ProcesType: astronomisch`. | https://rijkswaterstaatdata.nl/waterdata/ |
| Rijkswaterstaat DDAPI20 (niet ddlpy, zie WP-04) | ddlpy v0.10.x is alleen nog referentie voor de codes. Selectie via `ProcesType`, `Grootheid.Code` (`WATHTE`), `Groepering.Code` (`GETETBRKD2` voor extremen), `Hoedanigheid.Code` (`NAP`). Stationcodes zoals `hoekvanholland`. | https://deltares.github.io/ddlpy/, https://github.com/Deltares/ddlpy/blob/main/docs/examples/minimal_example.py |
| Supabase sleutels | `sb_publishable_…` en `sb_secret_…` via de `apikey`-header. Legacy-sleutels vervallen eind 2026. | https://supabase.com/docs/guides/api/api-keys |
| Supabase gratis plan | 500 MB DB, 5 GB egress, gepauzeerd na 1 week inactiviteit, max. 2 actieve projecten | https://supabase.com/pricing |
| Supabase e-mail | De standaard-SMTP stuurt alleen naar teamleden van het project, max. 2 per uur. Voor productie is eigen SMTP nodig. | https://supabase.com/docs/guides/auth/auth-smtp |
| Supabase IPv4 | Directe DB-verbinding loopt via IPv6. GitHub Actions is alleen IPv4. De pooler of REST is wel bereikbaar. | https://supabase.com/docs/guides/database/connecting-to-postgres |
| Supabase DB-tests | `supabase test db` (pgTAP) vereist een lokale stack (`supabase start`, Docker) | https://supabase.com/docs/guides/local-development/testing/overview |
| MapTiler gratis | 5.000 map sessions/maand; daarna gepauzeerd tot de volgende maand (geen kosten); MapTiler-logo verplicht; niet-commercieel | https://www.maptiler.com/cloud/pricing/ |
| Cloudflare Pages | 500 builds/maand, 20.000 bestanden. Zonder `404.html` gedraagt de site zich als SPA (onbekende paden serveren `/`). | https://developers.cloudflare.com/pages/platform/limits/, https://developers.cloudflare.com/pages/configuration/serving-pages/ |
| GitHub Actions | Gratis en onbeperkt in publieke repo's. Privé: 2.000 min/maand. In publieke repo's worden schedules na 60 dagen zonder commits stil uitgeschakeld. | https://docs.github.com/en/billing/concepts/product-billing/github-actions, https://docs.github.com/actions/managing-workflow-runs/disabling-and-enabling-a-workflow |
| GitHub Actions-meldingen (gecontroleerd 15 oktober 2026) | Meldingen over geplande workflows gaan naar de gebruiker die de workflow heeft aangemaakt; wijzigt een ander de cron-syntax, dan naar die gebruiker. Instelbaar per gebruiker: e-mail en/of web, eventueel alleen bij gefaalde runs. Er is geen ingebouwde deduplicatie: elke gefaalde run geeft een melding. | https://docs.github.com/en/actions/concepts/workflows-and-actions/notifications-for-workflow-runs |
| GitHub Actions-logs in een publieke repo (gecontroleerd 15 oktober 2026) | Bij een publieke repo zijn de Actions-geschiedenis en -logs voor iedereen zichtbaar. Logs mogen dus geen persoonsgegevens bevatten. | https://docs.github.com/articles/setting-repository-visibility, https://docs.github.com/en/actions/how-tos/monitor-workflows/use-workflow-run-logs |

**De planner verifieert dit per WP opnieuw**, omdat het niet volledig uit de documentatie bleek:
- de exacte Open-Meteo-model-id's voor DWD ICON, ECMWF IFS en NCEP GFS, en de naamgeving van variabelen in een multi-model-respons. Leg daarvoor een echte respons vast als fixture (WP-03);
- hoe hoog- en laagwater in de `GETETBRKD2`-reeks zijn gecodeerd (WP-04);
- de headers voor de secret key richting PostgREST (WP-01);
- de pywebpush-API, hoe je een aanroep een expliciete timeout geeft, en het gedrag van Web Push op iOS: alleen voor PWA's die op het beginscherm staan, iOS 16.4+ (WP-17, WP-18, WP-22);
- de grenzen voor titel (50 tekens) en body (150 tekens) van een pushmelding zijn een besluit van Lars (15 oktober 2026), geen gemeten waarde. Hoeveel tekens iOS en Android werkelijk tonen, is niet gecontroleerd; WP-18 AC-5 laat het op Lars' telefoon zien.

---

## M1: "werkt voor mij"

## WP-00: Repo, tooling, CI en Supabase-koppeling
**Mijlpaal:** M1
**Afhankelijk van:** -
**Doel:** Een repo-basis waarin elke volgende WP meteen kan testen, linten en (lokaal) met Supabase kan werken, met de puurheidsregel en de secret-hygiëne vanaf dag één afgedwongen.
**In scope:**
- `/ingest` als uv-project met Python 3.12 en src-layout (`ingest/src/shakka`), console-script `shakka`, dev-dependencies `pytest` en `ruff`, en een ruff-config voor lint en format.
- `shakka.config` met `Settings` en `get_settings()`. Leest de omgeving en een optioneel `.env` in de repo-root.
- `shakka.http.make_client()`: een httpx-client met een expliciete timeout en een herkenbare User-Agent zonder persoonsgegevens.
- `shakka.cli` met het commando `shakka doctor`. Het controleert of de verplichte variabelen er zijn (zonder waarden te tonen) en doet één GET op `{SUPABASE_URL}/rest/v1/` met de **secret key** (header `apikey`). Bij de nieuwe `sb_`-sleutels weigert dit endpoint de publishable key met 401 "Secret API key required"; gecontroleerd op 14 oktober 2026 tegen Lars' project. Exitcode 0 bij succes, 1 bij een fout.
- `ingest/src/shakka/domain/__init__.py` en `ingest/tests/test_domain_purity.py` met de regels uit "Code-indeling".
- `/supabase` aangemaakt met `supabase init` (`config.toml`). In `.gitignore` komen `supabase/.temp/` en `supabase/.branches/`.
- `.github/workflows/ci.yml` met job `ingest`: `uv sync`, `ruff check`, `ruff format --check` en `pytest`. Draait op `push` en `pull_request`.
- `.env.example` aangepast aan het env-contract (ingest-variabelen, zonder waarden).
- `docs/RUNBOOK.md` met de lokale setup (uv, Supabase CLI, Docker), welke secrets waar staan (alleen namen) en hoe Lars `supabase login` en `supabase link` doet.
**Buiten scope:** databaseschema en de CI-job `db` (WP-01), `/web` en de CI-job `web` (WP-13), de cron-workflow (WP-11).
**Contracten:**
- Paden: `ingest/pyproject.toml`, `ingest/src/shakka/`, `ingest/tests/`, `.github/workflows/ci.yml`, `docs/RUNBOOK.md`.
- `shakka.config.Settings`, velden: `supabase_url: str`, `supabase_publishable_key: str | None`, `supabase_secret_key: SecretStr`, `telegram_bot_token: SecretStr | None`, `telegram_chat_id: str | None`, `app_base_url: str | None`, `vapid_public_key: str | None`, `vapid_private_key: SecretStr | None`, `vapid_subject: str | None`, `spots_path: Path` (standaard `<repo>/data/spots.yaml`). Functie `get_settings() -> Settings`. Per WP-10 vervallen `telegram_bot_token` en `telegram_chat_id` (A-16).
- `shakka.http.make_client(*, timeout: float = 30.0) -> httpx.Client`.
- CLI-groepen die latere WP's toevoegen: `doctor` (WP-00), `spots` (WP-02), `forecast` (WP-03), `tides` (WP-04), `contracts` (WP-05), `alerts` (WP-10, WP-17), `evaluate` en `admin` (WP-10), `run-hourly` (WP-11), `marine` (WP-12).
- De puurheidsregels uit "Code-indeling" staan in `ingest/tests/test_domain_purity.py`.
**Acceptatiecriteria:**
- AC-1: `cd ingest && uv sync && uv run pytest` slaagt en draait minstens `tests/test_domain_purity.py`.
- AC-2: `cd ingest && uv run ruff check . && uv run ruff format --check .` slaagt.
- AC-3: `cd ingest && uv run shakka --help` eindigt met exitcode 0 en toont het subcommando `doctor`.
- AC-4: Een pytest-test start `doctor` met een lege omgeving (gemockt, geen `.env`). Exitcode is 1, de uitvoer noemt de ontbrekende variabelen bij naam en bevat geen waarden van eventueel wel gezette variabelen.
- AC-5: Met Lars' `.env` eindigt `cd ingest && uv run shakka doctor` met exitcode 0. Ontbreekt `.env`, dan is dit `NEEDS_LARS`.
- AC-6: `.github/workflows/ci.yml` draait op `push` en `pull_request` en voert exact de commando's van AC-1 en AC-2 uit. De laatste CI-run van de branch is groen; controleer met `gh run list --workflow ci.yml --limit 1` of in GitHub, anders `NEEDS_LARS`.
- AC-7: `supabase/config.toml` bestaat en `.gitignore` bevat `supabase/.temp/`.
- AC-8: `.env.example` bevat exact `SUPABASE_URL`, `SUPABASE_PUBLISHABLE_KEY`, `SUPABASE_SECRET_KEY`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `APP_BASE_URL`, `VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY` en `VAPID_SUBJECT`, zonder waarden (behalve `VAPID_SUBJECT=mailto:`). `git grep -nE "sb_(secret|publishable)_[A-Za-z0-9_-]{20,}|eyJhbGciOi" -- . ':!docs'` geeft geen treffers. (Historisch: per WP-10 vervallen de twee `TELEGRAM_*`-variabelen, zie A-16 en WP-10 AC-10.)
- AC-9: De puurheidstest is aantoonbaar scherp. Een geparametriseerde test voert de checker uit op broncode-strings met `import httpx`, `from os import environ`, `datetime.now()` en `open("x")`, en elk ervan wordt als overtreding gemeld. Een string met alleen `from pydantic import BaseModel` wordt niet gemeld.
**Nodig van Lars:**
- Een GitHub-repo met remote, en de keuze publiek of privé (zie "Beslissingen voor Lars").
- Een Supabase-project, gratis plan, regio in de EU.
- Een `.env` met `SUPABASE_URL`, `SUPABASE_PUBLISHABLE_KEY` en `SUPABASE_SECRET_KEY` (nieuwe sleutels, aan te maken via Settings > API Keys).
- Lokaal geïnstalleerd: `uv`, Supabase CLI en Docker (Docker Desktop of OrbStack).
- `supabase login` en `supabase link --project-ref <ref>` (access token en DB-wachtwoord blijven bij Lars).
**Omvang:** S

## WP-01: Datamodel M1, RLS en database-client
**Mijlpaal:** M1
**Afhankelijk van:** WP-00
**Doel:** Alle tabellen die M1 nodig heeft, met Row Level Security, als migraties in `/supabase`, plus een dunne Python-client voor de Supabase REST-API en een in-memory nep-database voor tests.
**In scope:**
- Migraties in `supabase/migrations/` voor de tabellen hieronder, met CHECK-constraints voor alle enums, indexen op de sleutels, de trigger voor `profiles`, RLS-policies en grants.
- pgTAP-tests in `supabase/tests/`.
- De CI-job `db` in `.github/workflows/ci.yml`: start lokaal Postgres via de Supabase CLI en draait `supabase test db`.
- `shakka.db.SupabaseRest`: een PostgREST-client op httpx met paginering (PostgREST geeft standaard max. 1000 rijen) en upserts in batches.
- `ingest/tests/fakes.py::FakeSupabase`: een in-memory implementatie met dezelfde publieke methoden, voor alle latere jobtests.
- `docs/RUNBOOK.md` aangevuld met hoe Lars migraties naar het remote project zet (`supabase db push`).
**Buiten scope:** `marine_hours` (WP-12), `push_subscriptions` (WP-17), `sessions` en `rsvps` (WP-19), het vullen van tabellen (WP-02, WP-03, WP-04, WP-10).
**Contracten:**

Tabellen (schema `public`). Latere WP's mogen via een nieuwe migratie kolommen toevoegen als hun blueprint dat onderbouwt. Hernoemen of verwijderen mag niet, met één uitzondering: `profiles.telegram_chat_id` is sinds 15 oktober 2026 ongebruikt (Telegram vervallen, A-16). De migratie is al toegepast, dus de kolom blijft bestaan tot WP-22 hem verwijdert. Geen enkele WP leest of schrijft hem nog. AC-2 (e) hieronder blijft als historisch criterium staan.

| Tabel | Kolommen (type, null) | Sleutel |
|---|---|---|
| `spots` | `id text`, `name text not null`, `region text null`, `lat double precision null`, `lon double precision null`, `shore_normal_deg smallint null` (0–359), `ridable_dirs jsonb null` (lijst `{"from": int, "to": int}`, graden, met de klok mee, inclusief), `hazards text null`, `tide_sensitive text not null default 'none'` (`none`,`prefer_low`,`prefer_high`,`avoid_low`), `tide_min_level_cm integer null`, `rws_station text null`, `season jsonb not null default '[]'` (lijst `{"start":"MM-DD","end":"MM-DD","from_time":"HH:MM"\|null,"to_time":"HH:MM"\|null,"note":str\|null}`, lokale tijd), `status text null` (`allowed`,`limited`,`forbidden`), `level text null` (`beginner`,`intermediate`,`advanced`), `default_min_kn smallint null`, `notes text null`, `verified boolean not null default false`, `updated_at timestamptz not null default now()` | PK `id` |
| `forecast_hours` | `spot_id text` (FK `spots`, on delete cascade), `model text` (`knmi`,`icon`,`ecmwf`,`gfs`), `valid_at timestamptz`, `wind_kn real null`, `gust_kn real null`, `dir_deg smallint null`, `fetched_at timestamptz not null` | PK (`spot_id`,`model`,`valid_at`) |
| `tide_extremes` | `station text`, `at timestamptz`, `kind text` (`high`,`low`), `level_cm integer not null`, `fetched_at timestamptz not null` | PK (`station`,`at`) |
| `evaluations` | `spot_id text` (FK, cascade), `valid_at timestamptz`, `verdict text` (`go`,`marginal`,`no_go`), `reasons text[] not null default '{}'`, `wind_kn real null`, `gust_kn real null`, `dir_deg smallint null`, `dir_class text null` (`onshore`,`side_onshore`,`sideshore`,`side_offshore`,`offshore`), `confidence text null` (`high`,`medium`,`low`), `tide_level_cm integer null`, `evaluated_at timestamptz not null` | PK (`spot_id`,`valid_at`) |
| `profiles` | `user_id uuid` (FK `auth.users`, cascade), `weight_kg smallint null` (30–200), `level text null`, `quiver_m2 real[] not null default '{}'`, `default_min_kn smallint null`, `default_max_kn smallint null`, `telegram_chat_id text null`, `created_at`, `updated_at` | PK `user_id` |
| `favorites` | `user_id uuid` (FK `auth.users`, cascade), `spot_id text` (FK `spots`, cascade), `created_at` | PK (`user_id`,`spot_id`) |
| `alert_rules` | `user_id uuid`, `spot_id text`, `enabled boolean not null default true`, `min_kn smallint null`, `max_kn smallint null`, `dir_classes text[] null` (alleen `onshore`,`side_onshore`,`sideshore`; CHECK), `weekdays smallint[] null` (1–7, ISO, 1 = maandag), `earliest_local time null`, `latest_local time null`, `min_go_hours smallint null`, `days_ahead smallint null`, `updated_at`. `null` = default. | PK (`user_id`,`spot_id`), FK (`user_id`,`spot_id`) → `favorites`, cascade |
| `alert_state` | `id uuid default gen_random_uuid()`, `user_id uuid` (FK, cascade), `spot_id text` (FK, cascade), `window_start timestamptz`, `window_end timestamptz`, `status text` (`active`,`cancelled`,`expired`), `snapshot jsonb not null`, `last_event text` (`new`,`improved`,`worsened`,`cancelled`), `last_notified_at timestamptz null`, `created_at`, `updated_at` | PK `id`, index (`user_id`,`spot_id`) |
| `api_usage` | `day date` (UTC), `source text` (`open_meteo_forecast`,`open_meteo_marine`,`rws`), `calls numeric(10,2) not null default 0`, `requests integer not null default 0` | PK (`day`,`source`) |
| `ingest_runs` | `id bigint generated always as identity`, `started_at timestamptz not null`, `finished_at timestamptz null`, `status text` (`running`,`ok`,`partial`,`failed`), `steps jsonb not null default '[]'`, `error_summary text null` | PK `id` |

- Trigger `on_auth_user_created` op `auth.users` (after insert) roept `public.handle_new_user()` aan. Die maakt een `profiles`-rij aan.
- RLS (aan op alle tabellen):
  - `spots`, `forecast_hours`, `tide_extremes` en `evaluations`: `select` voor `anon` en `authenticated`. Geen schrijfrechten.
  - `profiles`: `select` en `update` op de eigen rij. `telegram_chat_id` is via een kolomprivilege niet te wijzigen door `authenticated`.
  - `favorites` en `alert_rules`: alle CRUD-acties op de eigen rijen.
  - `alert_state`: `select` op de eigen rijen.
  - `api_usage` en `ingest_runs`: geen policies, dus alleen toegankelijk met de secret key.
- `shakka.db`:
  ```python
  class DatabaseError(Exception): ...
  class SupabaseRest:
      def __init__(self, url: str, secret_key: str, *, client: httpx.Client | None = None): ...
      @classmethod
      def from_settings(cls, settings: Settings) -> "SupabaseRest": ...
      def select(self, table: str, *, columns: str = "*", filters: Mapping[str, str] | None = None,
                 order: str | None = None, limit: int | None = None) -> list[dict[str, Any]]: ...
      def upsert(self, table: str, rows: Sequence[Mapping[str, Any]], *, on_conflict: str) -> int: ...
      def insert(self, table: str, rows: Sequence[Mapping[str, Any]], *, returning: bool = False) -> list[dict[str, Any]]: ...
      def update(self, table: str, values: Mapping[str, Any], *, filters: Mapping[str, str]) -> int: ...
      def delete(self, table: str, *, filters: Mapping[str, str]) -> int: ...
      def rpc(self, function: str, args: Mapping[str, Any] | None = None) -> Any: ...
  ```
  Filters gebruiken PostgREST-syntaxis, bijv. `{"valid_at": "lt.2026-10-14T00:00:00Z", "spot_id": "eq.wijk-aan-zee"}`.
- `ingest/tests/fakes.py::FakeSupabase` heeft dezelfde methoden en ondersteunt de operatoren `eq`, `neq`, `lt`, `lte`, `gt`, `gte`, `in.(..)` en `is.null`, plus `order` en `limit`. Het attribuut `writes: list[tuple[str, str]]` (operatie, tabel) dient om "geen schrijfacties" te kunnen toetsen. Met `register_rpc(name, fn)` registreer je nep-RPC's.
**Acceptatiecriteria:**
- AC-1: `supabase db reset` (lokaal) past alle migraties zonder fouten toe.
- AC-2: `supabase test db` is groen. De pgTAP-tests dekken minstens het volgende:
  - (a) alle tabellen en kolommen uit het contract bestaan;
  - (b) `anon` kan `spots`, `forecast_hours`, `tide_extremes` en `evaluations` lezen, maar niet inserten, updaten of deleten;
  - (c) `anon` leest 0 rijen uit `profiles`, `favorites`, `alert_rules`, `alert_state`, `api_usage` en `ingest_runs`;
  - (d) gebruiker A kan `profiles`, `favorites` en `alert_rules` van gebruiker B niet lezen of wijzigen;
  - (e) een gebruiker kan zijn eigen `telegram_chat_id` niet wijzigen;
  - (f) een insert in `auth.users` maakt een `profiles`-rij aan;
  - (g) `alert_rules.dir_classes` met `side_offshore` of `offshore` wordt geweigerd;
  - (h) een favoriet verwijderen verwijdert ook de bijbehorende `alert_rules`-rij.
- AC-3: `cd ingest && uv run pytest tests/test_db.py` is groen. De tests gebruiken `httpx.MockTransport` en tonen het volgende:
  - de key staat in de headers en niet in de URL;
  - filters worden correct geserialiseerd;
  - `upsert` stuurt `on_conflict` en `Prefer: resolution=merge-duplicates`;
  - `select` pagineert bij meer dan 1000 rijen;
  - upserts van meer dan 500 rijen gaan in batches;
  - `delete` en `update` zonder filters geven `ValueError`;
  - HTTP-fouten worden een `DatabaseError` zonder de key in de melding.
- AC-4: `cd ingest && uv run pytest tests/test_fakes.py` toont dat `FakeSupabase` voor alle genoemde filteroperatoren dezelfde rijen teruggeeft als de semantiek van PostgREST, en dat `writes` schrijfacties registreert.
- AC-5: De CI-job `db` draait `supabase test db` op `push` en `pull_request` en is groen.
- AC-6: Geen migratie bevat `create table` voor `sessions`, `rsvps`, `push_subscriptions` of `marine_hours` (controle met `grep -rniE "create table[^;]*(sessions|rsvps|push_subscriptions|marine_hours)" supabase/migrations` geeft niets).
- AC-7: Na `supabase db push` toont `supabase migration list --linked` alle migraties als toegepast op het remote project. Dit is `NEEDS_LARS` als de koppeling ontbreekt.
**Nodig van Lars:** Na de merge `supabase db push` naar het remote project (stappen in `docs/RUNBOOK.md`).
**Omvang:** M

## WP-02: Spotprofielen: schema, validatie, sync en startset
**Mijlpaal:** M1
**Afhankelijk van:** WP-01
**Doel:** `data/spots.yaml` wordt streng gevalideerd en idempotent naar de tabel `spots` gesynchroniseerd. De startset bevat de 25 spots uit het plan zonder verzonnen feitelijke waarden.
**In scope:**
- `shakka.domain.spot` met de pydantic-modellen en enums. Bevroren modellen, `extra="forbid"`.
- `shakka.spots.loader.load_spots(path)`, die alle validatiefouten tegelijk verzamelt.
- `shakka.spots.sync.sync_spots(db, spots)`: upsert op `id`, nooit deletes. Spots die in de database staan maar niet in de YAML worden gerapporteerd.
- CLI: `shakka spots validate [--path P]` en `shakka spots sync [--path P]`.
- Validatieregels:
  - unieke ids met slug-regex `^[a-z0-9]+(-[a-z0-9]+)*$`;
  - `lat` en `lon` beide ingevuld of beide leeg, en binnen Nederland (lat 50,7–53,7, lon 3,2–7,3);
  - `shore_normal_deg` tussen 0 en 359;
  - `ridable_dirs`-grenzen tussen 0 en 359;
  - seizoensdatums zijn geldige `MM-DD`-datums (`02-29` mag);
  - `from_time` en `to_time` beide ingevuld of beide leeg;
  - `tide_min_level_cm` tussen -300 en 300;
  - `default_min_kn` tussen 5 en 40.
  - `verified: true` vereist `lat`, `lon`, `shore_normal_deg`, `status` en `level`, en daarnaast `rws_station` als `tide_sensitive != none`.
- `data/spots.yaml` met de startset.
- `docs/SPOT_DATA.md`: een handleiding voor Lars. Beschrijft elk veld, legt `shore_normal_deg` uit met een rekenvoorbeeld (kust die op het westen ligt geeft 270), laat zien hoe `ridable_dirs` en `season` werken met tijdvensters, geeft de eisen voor `verified: true` en wijst naar `shakka tides stations` (WP-04) voor de keuze van `rws_station`.
**Buiten scope:** feitelijke spotdata invullen (dat doet Lars), stationslijst van Rijkswaterstaat (WP-04), evaluatie (WP-05).
**Contracten:**
- YAML-formaat: een top-level sleutel `spots:` met een lijst. Veldnamen zijn gelijk aan de kolommen van `spots` (zonder `updated_at`). Voorbeeld van een volledig ingevulde fictieve test-spot (alleen als fixture in tests, nooit in `data/spots.yaml`):
  ```yaml
  spots:
    - id: test-strand
      name: Teststrand
      region: Testregio
      lat: 52.0
      lon: 4.2
      shore_normal_deg: 290
      ridable_dirs: [{from: 200, to: 20}]
      tide_sensitive: avoid_low
      tide_min_level_cm: -20
      rws_station: hoekvanholland
      season: [{start: "05-01", end: "09-30", from_time: "10:00", to_time: "18:00", note: "badseizoen"}]
      status: allowed
      level: intermediate
      default_min_kn: 14
      hazards: null
      notes: null
      verified: true
  ```
- `shakka.domain.spot`: `Level` (StrEnum: `beginner`, `intermediate`, `advanced`), `SpotStatus` (`allowed`, `limited`, `forbidden`), `TideSensitivity` (`none`, `prefer_low`, `prefer_high`, `avoid_low`), `DirRange(from_deg: int, to_deg: int)` (aliases `from` en `to`), `SeasonClosure(start: str, end: str, from_time: time | None, to_time: time | None, note: str | None)` en `SpotProfile` (velden = kolommen) met `to_row() -> dict[str, Any]` en `from_row(row: Mapping[str, Any]) -> SpotProfile`.
- `shakka.spots.loader`: `load_spots(path: Path) -> list[SpotProfile]` en `SpotValidationError(errors: list[str])`. Elke fout bevat de spot-id (of de index) en de veldnaam.
- `shakka.spots.sync`: `sync_spots(db: SupabaseRest, spots: Sequence[SpotProfile]) -> SyncResult(upserted: int, orphaned: list[str])`.
- Spot-ids van de startset (vast, want favorieten verwijzen ernaar): `wijk-aan-zee`, `ijmuiden`, `zandvoort`, `bloemendaal`, `noordwijk`, `langevelderslag`, `katwijk`, `scheveningen`, `kijkduin`, `oostvoorne`, `brouwersdam`, `neeltje-jans`, `vrouwenpolder`, `domburg`, `workum`, `makkum`, `hindeloopen`, `lemmer`, `den-helder`, `callantsoog`, `petten`, `camperduin`, `schellinkhout`, `muiderberg`, `lauwersmeer`.
**Acceptatiecriteria:**
- AC-1: `cd ingest && uv run shakka spots validate` geeft exitcode 0 op `data/spots.yaml`.
- AC-2 (eenmalige controle op de diff van deze WP, geen permanente test): `data/spots.yaml` bevat exact de 25 ids uit het contract, met `name` gelijk aan de naam uit het plan en elk `verified: false`. Geen enkele spot heeft andere velden dan `id`, `name` en `verified`.
- AC-3: `cd ingest && uv run pytest tests/test_spots_validation.py` is groen. Elk van deze fixture-gevallen geeft een `SpotValidationError` met spot-id en veldnaam in de melding:
  - dubbele id;
  - ongeldige slug;
  - `lat` zonder `lon`;
  - coördinaat buiten Nederland;
  - `shore_normal_deg: 360`;
  - `ridable_dirs`-grens 400;
  - seizoensdatum `02-30`;
  - `from_time` zonder `to_time`;
  - onbekende enum-waarde;
  - onbekend veld;
  - `verified: true` met ontbrekend `shore_normal_deg`.

  Een YAML met drie fouten geeft drie fouten in één exception. `shakka spots validate` op die YAML geeft exitcode 1 en toont alle drie.
- AC-4: De volledige fixture-spot uit het contract laadt foutloos. `to_row()` geeft exact de kolomnamen van `spots` uit WP-01 (zonder `updated_at`), en `from_row(to_row(s)) == s`.
- AC-5: `sync_spots` gebruikt bij een test met `FakeSupabase` `on_conflict=id`, doet geen delete en rapporteert een id die alleen in de database staat in `orphaned`.
- AC-6: Na `supabase start` en `supabase db reset` vult `cd ingest && uv run shakka spots sync` (met `.env` naar de lokale stack) de tabel `spots` met 25 rijen. Een tweede run verandert het aantal niet.
- AC-7: `docs/SPOT_DATA.md` bestaat en behandelt elk veld uit het contract, het rekenvoorbeeld voor `shore_normal_deg` en de eisen voor `verified: true`.
**Nodig van Lars:** Niets om te starten. Na de merge, los van de pipeline: de spotprofielen invullen en per spot op `verified: true` zetten. Doe dit minstens voor je eigen favoriete spots vóór de M1-testweek.
**Omvang:** M

## WP-03: Forecast-ingest wind (Open-Meteo multi-model) met call-budget
**Mijlpaal:** M1
**Afhankelijk van:** WP-01
**Doel:** Elk uur per spot de windverwachting (snelheid, vlagen, richting) van vier modellen server-side ophalen, in knopen opslaan in `forecast_hours`, oude data opruimen en het Open-Meteo-budget bewaken.
**In scope:**
- `shakka.domain.forecast` met de modellen.
- `shakka.openmeteo.models`: de mapping van `ModelKey` naar het Open-Meteo-model-id. De planner verifieert de id's voor KNMI Harmonie AROME NL, DWD ICON, ECMWF IFS en NCEP GFS.
- `shakka.openmeteo.forecast`: een pure parameterbouwer, een pure parser en de fetch, waarbij meerdere locaties per request worden gebundeld.
- Retries bij 429 en 5xx met backoff, max. 3 pogingen.
- `shakka.budget`: een pure gewichtschatting en `BudgetGuard` op `api_usage`. Grens 80% van de officiële limiet: 8.000 per dag en 240.000 per maand, UTC.
- `shakka.jobs.forecast`: leest spots met coördinaten, controleert het budget vóór elke request, haalt op, doet een upsert en ruimt rijen met `valid_at < now - 48h` op. Rijen waarin wind, vlaag en richting alle drie leeg zijn, worden niet opgeslagen (bijv. KNMI na 2,5 dag).
- CLI: `shakka forecast fetch [--dry-run]`.
- Een vastgelegde echte respons (multi-model, minstens 2 locaties) als fixture in `ingest/tests/fixtures/openmeteo/`.
**Buiten scope:** golven via de Marine API (WP-12), evaluatie (WP-05), scheduling (WP-11).
**Contracten:**
- `shakka.domain.forecast`: `ModelKey` (StrEnum: `knmi`, `icon`, `ecmwf`, `gfs`), `SpotLocation(spot_id: str, lat: float, lon: float)`, `ForecastHour(spot_id: str, model: ModelKey, valid_at: datetime, wind_kn: float | None, gust_kn: float | None, dir_deg: int | None)`.
- `shakka.openmeteo.models.OPEN_METEO_MODELS: dict[ModelKey, str]`.
- `shakka.openmeteo.forecast`: `build_forecast_params(locations: Sequence[SpotLocation], *, forecast_days: int = 7) -> dict[str, str]`, `parse_forecast_response(payload: Any, locations: Sequence[SpotLocation]) -> list[ForecastHour]`, `fetch_forecast(http: httpx.Client, locations: Sequence[SpotLocation], *, forecast_days: int = 7) -> list[ForecastHour]` en `ForecastFetchError`.
- `shakka.budget`: `estimate_call_weight(n_locations: int, n_hourly_vars: int, n_models: int, forecast_days: int) -> float`, `BudgetGuard(db: SupabaseRest, *, daily_limit: float = 8000, monthly_limit: float = 240000)` met `can_spend(weight: float, *, now: datetime) -> bool` en `record(source: str, weight: float, *, now: datetime, requests: int = 1) -> None`. De guard telt alle `api_usage`-bronnen die met `open_meteo_` beginnen samen op.
- `shakka.jobs.forecast`: `run_forecast_ingest(db, http, budget, *, now: datetime) -> ForecastIngestResult(spots: int, rows: int, calls: float, skipped_budget: bool, errors: list[str])` en `delete_old_forecasts(db, *, now: datetime) -> int`.
**Acceptatiecriteria:**
- AC-1: Parsertests op de fixture (`cd ingest && uv run pytest tests/test_openmeteo_forecast.py`):
  - elk `valid_at` is tz-aware UTC;
  - waarden horen bij de juiste `ModelKey` (steekproef van minstens 3 waarden per model tegen de ruwe JSON);
  - `null` in de respons wordt `None` en nooit `0`;
  - er worden geen rijen gemaakt waarin alle drie de waarden `None` zijn.
- AC-2: `build_forecast_params` bevat `wind_speed_unit=kn`, `hourly=wind_speed_10m,wind_direction_10m,wind_gusts_10m`, de vier model-id's uit `OPEN_METEO_MODELS`, `forecast_days=7` en UTC-tijden. De parser geeft een fout als `hourly_units` voor windsnelheid niet in knopen is.
- AC-3: Tests voor `estimate_call_weight`:
  - (1 locatie, 3 variabelen, 1 model, 7 dagen) geeft 1,0;
  - (1, 3, 4, 7) geeft minstens 1,2;
  - (25, 3, 4, 7) geeft 25 keer de waarde van (1, 3, 4, 7);
  - (1, 3, 1, 21) geeft minstens 1,5.
- AC-4: `BudgetGuard`-tests met `FakeSupabase`. Is het dagverbruik plus het gewicht meer dan 8.000, of het maandverbruik plus het gewicht meer dan 240.000, dan gaat er geen HTTP-request naar Open-Meteo (MockTransport registreert 0 calls) en is `skipped_budget=True`. Na een geslaagde request staat het gewicht in `api_usage` onder `open_meteo_forecast`.
- AC-5: Jobtest met `FakeSupabase` en MockTransport:
  - spots zonder `lat` of `lon` worden overgeslagen;
  - de upsert gebruikt `on_conflict=spot_id,model,valid_at`;
  - het opruimen verwijdert alleen rijen met `valid_at < now - 48h`.
- AC-6: Retrytests. Eerst 429 en dan 200 slaagt. Drie keer 500 geeft een resultaat met `errors` gevuld, zonder onafgevangen exception.
- AC-7: `grep -rn "open-meteo.com" ingest/src` vindt alleen treffers onder `ingest/src/shakka/openmeteo/`.
- AC-8: Tegen de lokale stack met één test-spot met coördinaten (in te voegen door de verifier) vult `cd ingest && uv run shakka forecast fetch` de tabel `forecast_hours` voor alle vier de modellen. Een tweede run verdubbelt het aantal rijen niet.
**Nodig van Lars:** Niets.
**Omvang:** M

## WP-04: Getij-ingest (Rijkswaterstaat)
**Mijlpaal:** M1
**Afhankelijk van:** WP-01
**Doel:** Eén keer per dag voor elk gebruikt Rijkswaterstaat-station de astronomische hoog- en laagwaters ophalen en opslaan, plus een pure functie die de waterstand op een willekeurig tijdstip schat.
**In scope:**
- `shakka.domain.tide` met het model en de interpolatie. De interpolatie is een cosinus tussen opeenvolgende extremen en geeft `None` buiten het bereik of bij een gat van meer dan 9 uur.
- `shakka.rws.tides`:
  - extremen ophalen rechtstreeks via de Rijkswaterstaat DDAPI20 met `httpx` (besluit Lars, 15 oktober 2026: geen `ddlpy`, want die doet requests zonder timeout en trekt pandas binnen) met `ProcesType` `astronomisch`, `Grootheid.Code` `WATHTE`, `Groepering.Code` `GETETBRKD2` en `Hoedanigheid.Code` `NAP`;
  - omrekenen naar cm en UTC;
  - het type extreem (hoog of laag) bepalen. De planner verifieert hoe dat in de reeks is gecodeerd.
- Een stationslijst ophalen.
- `shakka.jobs.tides`:
  - gebruikt de unieke, niet-lege `rws_station`-waarden uit `spots`;
  - slaat een station over als het minder dan 20 uur geleden is opgehaald, tenzij `force`;
  - haalt het venster `now - 1 dag` tot `now + 8 dagen` op;
  - doet een upsert en ruimt `at < now - 48h` op;
  - een station dat faalt stopt de andere stations niet.
- CLI: `shakka tides fetch [--force]` en `shakka tides stations`. De laatste toont code, naam, lat en lon van stations met astronomische extremen.
- Fixture: een vastgelegde echte DDAPI20-respons. De fetch is in tests te vervangen.
**Buiten scope:** getij in de evaluatie (WP-05), het kiezen van stations per spot (spotdata van Lars).
**Contracten:**
- `shakka.domain.tide`: `TideExtreme(station: str, at: datetime, kind: Literal["high", "low"], level_cm: int)` en `estimate_tide_level(extremes: Sequence[TideExtreme], at: datetime) -> int | None`.
- `shakka.rws.tides`: `fetch_tide_extremes(station: str, start: datetime, end: datetime) -> list[TideExtreme]`, `list_tide_stations() -> list[StationInfo]` met `StationInfo(code: str, name: str, lat: float, lon: float)`, en `TideFetchError`.
- `shakka.jobs.tides`: `run_tide_ingest(db, *, now: datetime, force: bool = False, fetch=fetch_tide_extremes) -> TideIngestResult(stations: int, rows: int, skipped: list[str], failed: list[str])`.
**Acceptatiecriteria:**
- AC-1: Conversietest op de fixture:
  - het juiste aantal extremen;
  - `kind` wisselt af tussen `high` en `low`;
  - `level_cm` is een int;
  - elke `at` is tz-aware UTC;
  - een brontijd met offset `+01:00` wordt correct naar UTC omgerekend (12:00+01:00 wordt 11:00Z).
- AC-2: Tests voor `estimate_tide_level`:
  - precies op een extreem geeft het niveau van dat extreem;
  - halverwege tussen hoog water (+100) en laag water (-80), met 6 uur ertussen, geeft 10 ± 1;
  - vóór het eerste of na het laatste extreem geeft `None`;
  - een gat van meer dan 9 uur tussen twee extremen geeft `None`.
- AC-3: Jobtest met `FakeSupabase` en een nep-fetch:
  - alleen unieke, niet-lege stations worden opgehaald;
  - een station dat 19 uur geleden is opgehaald wordt overgeslagen, behalve met `force=True`;
  - als één station een exception geeft, worden de andere wel opgeslagen en staat het falende station in `failed`;
  - het opruimen filtert op `at < now - 48h`.
- AC-4: `cd ingest && uv run shakka tides stations` (echte netwerk-call) toont minstens één station waarvan de naam "Hoek van Holland" bevat.
- AC-5: Tegen de lokale stack met een test-spot waarvan `rws_station` de code van Hoek van Holland is (uit AC-4) slaat `uv run shakka tides fetch --force` minstens 25 extremen op voor de komende 8 dagen.
**Nodig van Lars:** Niets.
**Omvang:** M

## WP-05: Evaluatie-engine (puur)
**Mijlpaal:** M1
**Afhankelijk van:** WP-02, WP-03, WP-04
**Doel:** Een deterministische, pure functie die per spot per uur `go`, `marginal` of `no_go` geeft met alle redenen, volgens de regels uit sectie 4 van het plan. Offshore en side-offshore zijn daarbij altijd `no_go`.
**In scope:**
- Richtingsklassen afleiden uit `shore_normal_deg`. `ridable_dirs` kan richtingen alleen verder beperken en kan offshore of side-offshore nooit toestaan. Ontbreekt `shore_normal_deg`, dan is het `no_go` (`direction_unknown`).
- Consensus over de modellen per uur:
  - windsnelheid en vlagen via een robuuste aggregatie (de planner kiest, bijv. de mediaan);
  - richting via een circulair gemiddelde;
  - betrouwbaarheid op basis van de spreiding in snelheid en richting. Lage betrouwbaarheid maakt een `go` hooguit `marginal`.
- Daglicht via `astral`, met marge.
- Seizoenssluitingen in lokale tijd, inclusief tijdvensters, sluitingen over de jaargrens en de overgangen naar zomer- en wintertijd.
- `status`: `forbidden` wordt `no_go`, `limited` en onbekend worden `marginal`.
- Getij-voorkeur via `estimate_tide_level` uit WP-04.
- Windgrenzen van de rider, en vlagerigheid.
- Constanten in `shakka.domain.defaults`. De planner stelt de waarden voor in een blueprint-sectie "Drempelwaarden".
- `shakka.contracts` en de CLI `shakka contracts export [--check]`. Schrijft `data/contracts/reason_codes.json`, `data/contracts/dir_classes.json` en `data/contracts/confidence.json`, elk met de code, het effect of de rijdbaarheid, en `label_nl`.
**Buiten scope:** evaluaties opslaan (WP-10), persoonlijke alertregels (WP-07), golven (niet in de evaluatie volgens het plan).
**Contracten:**
- `shakka.domain.defaults`: `LOCAL_TZ`, `DEFAULT_MIN_KN`, `DEFAULT_MAX_KN`, plus de drempels voor richting, vlagen, daglichtmarge en spreiding. Namen legt de planner vast.
- `shakka.domain.direction`:
  - `DirClass` (StrEnum: `onshore`, `side_onshore`, `sideshore`, `side_offshore`, `offshore`);
  - `RIDABLE_DIR_CLASSES: frozenset[DirClass]` = {`onshore`, `side_onshore`, `sideshore`};
  - `classify_direction(wind_from_deg: float, shore_normal_deg: float) -> DirClass`;
  - `in_ranges(deg: float, ranges: Sequence[DirRange]) -> bool`;
  - `compass_label(deg: float) -> str` (Nederlandse windroos in 16 streken: N, NNO, NO, ONO, O, OZO, ZO, ZZO, Z, ZZW, ZW, WZW, W, WNW, NW, NNW).
- `shakka.domain.consensus`: `Confidence` (StrEnum: `high`, `medium`, `low`), `Consensus(wind_kn: float | None, gust_kn: float | None, dir_deg: int | None, confidence: Confidence, models_used: tuple[ModelKey, ...])` en `compute_consensus(hours: Sequence[ForecastHour]) -> Consensus | None` (`None` als geen enkel model data heeft).
- `shakka.domain.daylight`: `is_daylight(lat: float, lon: float, valid_at: datetime) -> bool`.
- `shakka.domain.evaluation`:
  - `Verdict` (StrEnum: `go`, `marginal`, `no_go`);
  - `ReasonCode` (StrEnum, zie de tabel hieronder) en `REASON_EFFECT: dict[ReasonCode, Verdict]`;
  - `RiderLimits(min_kn: float, max_kn: float)`;
  - `HourEvaluation(spot_id: str, valid_at: datetime, verdict: Verdict, reasons: tuple[ReasonCode, ...], wind_kn: float | None, gust_kn: float | None, dir_deg: int | None, dir_class: DirClass | None, confidence: Confidence | None, tide_level_cm: int | None)`;
  - `default_limits(spot: SpotProfile) -> RiderLimits`;
  - `evaluate_hour(spot, valid_at, hours: Sequence[ForecastHour], tides: Sequence[TideExtreme], limits: RiderLimits) -> HourEvaluation`;
  - `evaluate_spot(spot: SpotProfile, forecasts: Sequence[ForecastHour], tides: Sequence[TideExtreme], limits: RiderLimits) -> list[HourEvaluation]` (één per unieke `valid_at`, gesorteerd).
  - Het oordeel is het zwaarste effect van de redenen. Zonder redenen is het `go`. Redenen staan in een vaste, deterministische volgorde.

| `ReasonCode` | Effect | Betekenis |
|---|---|---|
| `no_data` | `no_go` | geen enkel model heeft data voor dit uur |
| `wind_too_light` | `no_go` | onder `min_kn` |
| `wind_too_strong` | `no_go` | boven `max_kn` |
| `wind_borderline` | `marginal` | binnen de marge van `min_kn` of `max_kn` |
| `too_gusty` | `no_go` | vlagerigheid boven de harde grens |
| `gusty` | `marginal` | vlagerigheid boven de zachte grens |
| `offshore` | `no_go` | richtingsklasse offshore |
| `side_offshore` | `no_go` | richtingsklasse side-offshore |
| `direction_unknown` | `no_go` | `shore_normal_deg` ontbreekt of er is geen richting |
| `direction_not_ridable` | `no_go` | buiten `ridable_dirs` |
| `dark` | `no_go` | buiten daglicht plus marge |
| `season_closed` | `no_go` | binnen een seizoenssluiting |
| `spot_forbidden` | `no_go` | `status: forbidden` |
| `spot_limited` | `marginal` | `status: limited` |
| `status_unknown` | `marginal` | `status` is leeg |
| `tide_too_low` | `no_go` | geschatte waterstand onder `tide_min_level_cm` |
| `tide_unfavorable` | `marginal` | buiten het voorkeursgetij (`prefer_low`, `prefer_high`), of `avoid_low` rond laagwater zonder minimumwaterstand |
| `tide_unknown` | `marginal` | spot is getijgevoelig maar er is geen schatting |
| `low_confidence` | `marginal` | betrouwbaarheid `low` |

**Acceptatiecriteria:**
- AC-1: Richtingstests met `shore_normal_deg = 270`:
  - wind uit 270 is `onshore`;
  - 225 en 315 zijn `side_onshore`;
  - 180 en 0 zijn `sideshore`;
  - 135 en 45 zijn `side_offshore`;
  - 90 is `offshore`.

  Een uitputtende test over `shore_normal_deg` ∈ {0, 45, 270, 359} en elke gehele `wind_from` van 0 tot en met 359 toont twee dingen. De klasse is symmetrisch: een afwijking van +d en -d geeft dezelfde klasse. En de klasse is monotoon in de absolute hoekafwijking, in de volgorde onshore < side_onshore < sideshore < side_offshore < offshore. Rond 0/360 gaat het goed: normaal 10 met wind uit 350 is `onshore`.
- AC-2: Veiligheid. Voor elke `shore_normal_deg` van 0 tot 359 in stappen van 15, en elke `wind_from` die `offshore` of `side_offshore` oplevert, geeft `evaluate_hour` `no_go` met reden `offshore` of `side_offshore`. Dat geldt ongeacht de `RiderLimits`, ook als `ridable_dirs` die richting bevat, en ongeacht getij en betrouwbaarheid. Geen enkele publieke functie heeft een parameter die dit uitschakelt; de verifier controleert de signatures.
- AC-3: Een spot zonder `shore_normal_deg` geeft voor elk uur `no_go` met `direction_unknown`. Met `ridable_dirs: [{from: 200, to: 340}]` en wind uit 190 (klasse sideshore) volgt `direction_not_ridable`. Wind uit 270 binnen het bereik geeft geen richtingsreden.
- AC-4: Windtests:
  - onder `min_kn` geeft `wind_too_light`;
  - boven `max_kn` geeft `wind_too_strong`;
  - net binnen de grenzen geeft `wind_borderline` volgens de gedocumenteerde marge;
  - de gevallen `gusty` en `too_gusty` volgen de gedocumenteerde drempels, met minstens één test per kant van elke drempel.
- AC-5: Daglichttests met fixture-coördinaten 52,47 N en 4,57 O (testdata, geen spotdata):
  - 21-06-2026 03:00Z is `dark`;
  - 21-06-2026 12:00Z is niet `dark`;
  - 21-12-2026 17:00Z is `dark`.
- AC-6: Seizoen en status, met de sluiting `{start: "05-01", end: "09-30", from_time: "10:00", to_time: "18:00"}`:
  - 15-07-2026 12:00 lokaal geeft `season_closed`;
  - 15-07-2026 19:00 lokaal niet;
  - 15-10-2026 12:00 lokaal niet;
  - een sluiting van `11-15` tot `02-15` geldt op 10-01-2027;
  - rond 29-03-2026 en 25-10-2026 (zomer- en wintertijd) klopt de grens in lokale tijd.

  `status: forbidden` geeft elk uur `spot_forbidden`, `limited` geeft `spot_limited`, en een lege status geeft `status_unknown`.
- AC-7: Getij, met een test per variant:
  - `none` geeft nooit een getij-reden;
  - `avoid_low` met `tide_min_level_cm: 0` en een geschatte stand van -50 geeft `tide_too_low`;
  - `prefer_low` op hoogwater geeft `tide_unfavorable`;
  - een getijgevoelige spot zonder extremen geeft `tide_unknown`.

  `tide_level_cm` in `HourEvaluation` is gelijk aan `estimate_tide_level`.
- AC-8: Consensus:
  - vier vrijwel gelijke modellen geven `high`;
  - een spreiding boven de drempel geeft `low`, waardoor een uur dat anders `go` was `marginal` wordt met `low_confidence`, en een `no_go` blijft `no_go`;
  - de betrouwbaarheid bij één beschikbaar model is gedocumenteerd en getest;
  - alle modellen `None` geeft `no_data` en `no_go`;
  - richtingen 350 en 10 geven een consensus van 0 ± 1, niet 180.
- AC-9: Eigenschappen over alle testuitvoer: `verdict` is gelijk aan het zwaarste `REASON_EFFECT` van de redenen, en `verdict == go` precies als `reasons` leeg is. `evaluate_spot` geeft bij dezelfde invoer twee keer gelijke uitvoer, gesorteerd op `valid_at`, met elke `valid_at` één keer.
- AC-10: `cd ingest && uv run shakka contracts export --check` geeft exitcode 0. De JSON-bestanden bevatten elke `ReasonCode`, `DirClass` en `Confidence` met een niet-lege `label_nl`. De test `tests/test_contracts.py` faalt als een bestand niet actueel is.
- AC-11: `tests/test_domain_purity.py` is groen met de nieuwe modules.
**Nodig van Lars:** Bevestiging van de drempelwaarden: grenzen van de richtingsklassen, vlagerigheid (zacht en hard), windmarge, daglichtmarge, spreidingsgrenzen en de standaardwaarden voor min en max kn. Lars kan bij de start waarden meegeven, of de planner zet een voorstel in de blueprint onder "Drempelwaarden" dat Lars in de M1-testweek beoordeelt.
**Omvang:** M

## WP-06: Kite-advies (puur)
**Mijlpaal:** M1
**Afhankelijk van:** WP-02
**Doel:** Een pure functie die op basis van gewicht, niveau, quiver en windkracht een kitemaat uit de eigen quiver adviseert, getoetst aan handmatig gecontroleerde voorbeelden.
**In scope:**
- `shakka.domain.kite` met de formule voor de ideale maat en de keuze uit de quiver. De planner legt formule en tabellen vast in de blueprint.
- Advies per uur en per window.
- De voorbeeldtabel `ingest/tests/fixtures/kite_examples.yaml` met minstens 15 gevallen en een kopveld `checked_by_lars: true | false`.
**Buiten scope:** het profiel opslaan of bewerken (WP-01, WP-10, WP-16), advies in berichten (WP-08).
**Contracten:**
- `shakka.domain.kite`:
  - `RiderProfile(weight_kg: int, level: Level, quiver_m2: tuple[float, ...])`;
  - `KiteFit` (StrEnum: `ideal`, `underpowered`, `overpowered`);
  - `KiteAdvice(size_m2: float, fit: KiteFit, ideal_size_m2: float)`;
  - `ideal_kite_size(weight_kg: int, level: Level, wind_kn: float) -> float`;
  - `recommend_kite(rider: RiderProfile, wind_kn: float) -> KiteAdvice | None`;
  - `recommend_for_window(rider: RiderProfile, wind_kn_values: Sequence[float]) -> KiteAdvice | None`.
**Acceptatiecriteria:**
- AC-1: `cd ingest && uv run pytest tests/test_kite.py` is groen. Voor elk geval in `kite_examples.yaml` geeft `recommend_kite` de verwachte `size_m2`.
- AC-2: `kite_examples.yaml` bevat `checked_by_lars: true`. Staat er `false`, dan is dit `NEEDS_LARS`.
- AC-3: Eigenschapstest over gewichten 50–110 kg (stappen van 5), wind 8–40 kn en minstens 4 verschillende quivers:
  - `size_m2` zit altijd in `quiver_m2`;
  - een lege quiver geeft `None`;
  - een quiver met één kite geeft altijd die kite.
- AC-4: Bij een vaste rider geeft meer wind nooit een grotere `size_m2` of `ideal_size_m2`.
- AC-5: Bij gelijke wind en hetzelfde niveau geeft een hoger gewicht nooit een kleinere `ideal_size_m2`.
- AC-6: `recommend_for_window` gebruikt de gedocumenteerde aggregatie, getest met een window van wisselende windkracht.
**Nodig van Lars:** De voorbeeldtabel controleren en goedkeuren. De planner stelt hem op; Lars zet `checked_by_lars: true`. Optioneel geeft Lars zijn eigen gewicht, niveau en quiver als voorbeeld.
**Omvang:** S

## WP-07: Alertregels en windows (puur)
**Mijlpaal:** M1
**Afhankelijk van:** WP-05
**Doel:** Effectieve alertregels samenstellen uit systeem-, spot-, profiel- en gebruikersinstellingen, en daarmee de aaneengesloten `go`-windows vinden waarop een alert kan afgaan.
**In scope:**
- `shakka.domain.alerts`: de defaults, `resolve_rule`, validatie (`dir_classes` kan alleen rijdbare klassen bevatten), `rider_limits`, `Window` en `find_windows`.
- Prioriteit: gebruikersregel, dan profiel, dan spot, dan systeem.
- `data/contracts/alert_defaults.json` toevoegen aan `shakka contracts export`.
**Buiten scope:** deduplicatie en berichten (WP-08), regels laden uit de database (WP-10), UI (WP-16).
**Contracten:**
- `shakka.domain.alerts`:
  - `DEFAULT_MIN_GO_HOURS`, `DEFAULT_DAYS_AHEAD`, `DEFAULT_WEEKDAYS` (frozenset 1–7) en `DEFAULT_DIR_CLASSES` (= `RIDABLE_DIR_CLASSES`);
  - `AlertRuleOverride` (velden gelijk aan de kolommen van `alert_rules` behalve de sleutels, allemaal optioneel);
  - `ProfileDefaults(default_min_kn: int | None, default_max_kn: int | None)`;
  - `AlertRule(enabled: bool, min_kn: float, max_kn: float, dir_classes: frozenset[DirClass], weekdays: frozenset[int], earliest_local: time | None, latest_local: time | None, min_go_hours: int, days_ahead: int)`. Ongeldige combinaties geven `ValueError`.
  - `resolve_rule(spot: SpotProfile, profile: ProfileDefaults | None, override: AlertRuleOverride | None) -> AlertRule`;
  - `rider_limits(rule: AlertRule) -> RiderLimits`;
  - `Window(spot_id: str, start: datetime, end: datetime, hours: tuple[HourEvaluation, ...])`, halfopen;
  - `find_windows(evaluations: Sequence[HourEvaluation], rule: AlertRule, *, now: datetime) -> list[Window]`.
- Een uur telt mee als:
  - `verdict == go`;
  - `dir_class` in `rule.dir_classes` zit;
  - de lokale weekdag in `weekdays` zit;
  - het lokale uur in `[earliest_local, latest_local)` valt;
  - `valid_at >= now` (het uur waarin `now` valt telt niet);
  - de lokale datum ≤ vandaag + `days_ahead`.

  Een window is een maximale reeks opeenvolgende uren (stap 1 uur) met een lengte van minstens `min_go_hours`. Bij `enabled == False` is de uitkomst `[]`.
**Acceptatiecriteria:**
- AC-1: `cd ingest && uv run pytest tests/test_alert_rules.py`: voor elk veld een test van alle vier de prioriteitsniveaus (regel, profiel, spot, systeem). `min_kn` gebruikt `spot.default_min_kn` als regel en profiel leeg zijn.
- AC-2: `AlertRule` en `resolve_rule` geven een `ValueError` bij `dir_classes` met `side_offshore` of `offshore`, ook als die via `AlertRuleOverride` binnenkomen. Ook `min_kn >= max_kn` en een weekdag buiten 1–7 worden geweigerd.
- AC-3: `cd ingest && uv run pytest tests/test_windows.py` met deze gevallen:
  - 3 go-uren met `min_go_hours=2` geeft 1 window met `end` = laatste uur + 1 uur;
  - 1 go-uur geeft 0 windows;
  - go, marginal, go met minimum 1 geeft 2 windows;
  - een filter op alleen zaterdag en zondag werkt op de lokale datum;
  - `earliest_local=17:00` werkt in zowel zomer- als wintertijd;
  - `days_ahead=1` sluit uren na morgen (lokaal) uit;
  - uren vóór `now` tellen niet mee;
  - een ontbrekend uur in de reeks splitst het window;
  - uren met `dir_class` buiten `rule.dir_classes` splitsen het window.
- AC-4: Bij `enabled=False` geeft `find_windows` `[]`.
- AC-5: `uv run shakka contracts export --check` is groen en `data/contracts/alert_defaults.json` bevat de defaults en de toegestane `dir_classes`.
- AC-6: `tests/test_domain_purity.py` is groen.
**Nodig van Lars:** Bevestiging van de defaults `min_go_hours` en `days_ahead`. De planner doet een voorstel.
**Omvang:** S

## WP-08: Alert-deduplicatie en berichtopbouw (puur)
**Mijlpaal:** M1
**Afhankelijk van:** WP-06, WP-07
**Doel:** Per gebruiker en spot bepalen welke windows een melding verdienen: nieuw, beter, slechter of geannuleerd, met één melding per window. Daarnaast een kanaalonafhankelijk Nederlandstalig bericht opbouwen met een "ik ga"-link.
**In scope:**
- `shakka.domain.dedup`: een snapshot per window, matching van oude statusregels aan nieuwe windows op overlap, drempels voor een wezenlijke verandering (gedocumenteerd in de blueprint), en verlopen windows zonder melding afsluiten.
- `shakka.domain.messages`: titel en body in platte tekst, lokale tijden, de Nederlandse labels uit WP-05, het "ik ga"-URL-contract, en de regel over getij (alleen bij getijgevoelige spots).
**Buiten scope:** versturen (WP-17), state opslaan en laden (WP-10), het `/go`-endpoint in de app (WP-14, WP-20).
**Contracten:**
- `shakka.domain.dedup`:
  - `WindowSnapshot(start: datetime, end: datetime, wind_min_kn: float, wind_max_kn: float, gust_max_kn: float, dir_deg: int, dir_class: DirClass, confidence: Confidence)` met `to_json() -> dict` en `from_json(d) -> WindowSnapshot`;
  - `snapshot_window(window: Window) -> WindowSnapshot`;
  - `AlertStateEntry(id: str | None, spot_id: str, window_start: datetime, window_end: datetime, status: Literal["active", "cancelled", "expired"], snapshot: WindowSnapshot, last_event: AlertEventKind | None, last_notified_at: datetime | None)`;
  - `AlertEventKind` (StrEnum: `new`, `improved`, `worsened`, `cancelled`);
  - `AlertEvent(kind: AlertEventKind, spot_id: str, current: WindowSnapshot | None, previous: WindowSnapshot | None, state_index: int)`. `state_index` is de index in `new_state`.
  - `DiffResult(events: list[AlertEvent], new_state: list[AlertStateEntry])`;
  - `diff_windows(previous: Sequence[AlertStateEntry], current: Sequence[Window], *, now: datetime) -> DiffResult`.
- `shakka.domain.messages`:
  - `AlertMessage(spot_id: str, kind: AlertEventKind, title: str, body: str, go_url: str | None)`;
  - `build_go_url(base_url: str, spot_id: str, start: datetime, end: datetime) -> str`, met het formaat `{base_url}/go?spot={spot_id}&start={start}&end={end}`. `start` en `end` zijn ISO 8601 in UTC met `Z`, URL-gecodeerd. De PWA-route `/go` leest dit formaat (WP-14, WP-20).
  - `render_alert(event: AlertEvent, spot: SpotProfile, *, kite: KiteAdvice | None, tides: Sequence[TideExtreme], base_url: str | None) -> AlertMessage`.
- Het bericht bevat altijd:
  - de spotnaam;
  - het window in lokale tijd (bijv. "za 18 okt 14:00–18:00");
  - het windbereik en de maximale vlagen in kn;
  - de richting als windroos plus graden;
  - het label van de richtingsklasse;
  - de betrouwbaarheid.

  Daarnaast, als het van toepassing is:
  - getij: alleen als `tide_sensitive != none` en er extremen binnen het window of tot 3 uur ervoor of erna zijn;
  - kite-advies: als `kite` niet `None` is;
  - `go_url`: alleen als `base_url` gezet is en `kind != cancelled`.
**Acceptatiecriteria:**
- AC-1: `cd ingest && uv run pytest tests/test_dedup.py`. Twee keer achter elkaar `diff_windows` met dezelfde windows, waarbij de tweede keer de `new_state` van de eerste wordt gebruikt, geeft de tweede keer 0 events.
- AC-2: Een nieuw window geeft precies 1 `new`-event en 1 entry met `status=active`.
- AC-3: Verdwijnt een actief window volledig vóór de start, dan volgt 1 `cancelled`. Is een window afgelopen (`window_end <= now`), dan volgt geen event en wordt de status `expired`. Een al geannuleerd window dat terugkomt, geeft een `new`-event.
- AC-4: Kleine wijzigingen (start of eind ± 1 uur, wind ± 2 kn) geven geen event. Wijzigingen boven de gedocumenteerde drempels geven `improved` of `worsened`, met minstens één test per richting en per drempel.
- AC-5: Splitst één oud window in twee, of smelten twee samen, dan is de uitkomst deterministisch en gedocumenteerd. Elke huidige window is aan hoogstens één entry gekoppeld en andersom, en er ontstaan geen dubbele `new`-events voor dezelfde uren.
- AC-6: `WindowSnapshot.from_json(s.to_json()) == s`, en `to_json()` is JSON-serialiseerbaar (`json.dumps` slaagt).
- AC-7: Golden-tests van `render_alert` voor `new`, `improved`, `worsened` en `cancelled` op een fixture-spot. Getoetst wordt:
  - lokale tijd in Europe/Amsterdam, met een zomertijdgeval en een wintertijdgeval;
  - aanwezigheid van alle verplichte onderdelen;
  - een getij-regel alleen bij een getijgevoelige spot;
  - kite-advies alleen als het is meegegeven;
  - `go_url` is `None` bij `cancelled` of zonder `base_url`.
- AC-8: `build_go_url` is omkeerbaar: met `urllib.parse` zijn `spot`, `start` en `end` terug te lezen en gelijk aan de invoer.
- AC-9: De `body` is in alle golden-tests maximaal 1.000 tekens.
- AC-10: `tests/test_domain_purity.py` is groen.
**Nodig van Lars:** Niets. Optioneel: feedback op de toon van de berichten.
**Omvang:** M

## WP-09: Telegram-kanaal (vervallen)
**Status:** `dropped`.

Vervallen (15 oktober 2026): Telegram is geschrapt; zie WP-17. Besluit van Lars, uitgewerkt in A-16. De interface `shakka.notify.base` (`DeliveryResult`, `Notifier`, `DeliveryTarget`) wordt nu in WP-17 gedefinieerd. Er komt geen `TelegramTarget`, `TelegramNotifier`, `send_text` of `shakka alerts test-telegram`.

## WP-10: Evaluatie- en alertjobs plus beheer-CLI
**Mijlpaal:** M1
**Afhankelijk van:** WP-02, WP-03, WP-04, WP-05, WP-06, WP-07, WP-08
**Doel:** De pure engines aan de database koppelen. Evaluaties per spot opslaan, per gebruiker alerts bepalen en als events in `alert_state` vastleggen, zodat Lars in M1 via CLI en database kan controleren dat de alerts kloppen. Er is in M1 geen meldingskanaal (A-16); versturen komt in WP-17. Lars kan zijn profiel, favorieten en regels zonder UI beheren.
**In scope:**
- `shakka.jobs.inputs`: laadt per spot met coördinaten het profiel, de forecasts (`now - 1h` tot `now + 8 dagen`) en de getij-extremen van het station.
- `shakka.jobs.evaluate`:
  - `evaluate_spot` met `default_limits(spot)`;
  - upsert naar `evaluations`;
  - rijen met `valid_at < now - 48h` opruimen.
- `shakka.jobs.alerts`, per favoriet:
  - effectieve regel bepalen;
  - controleren of de spot in aanmerking komt (zie "Nodig van Lars");
  - `evaluate_spot` met `rider_limits(rule)`;
  - `find_windows`;
  - `diff_windows` op `alert_state`;
  - `render_alert` met kite-advies uit `profiles`;
  - de status opslaan in `alert_state` (`status`, `snapshot`, `last_event`);
  - de gerenderde berichten teruggeven in het resultaat (`AlertJobResult.messages`), zonder kanaal.
- In M1 schuift de state na elk event altijd door, want er is geen aflevering die kan falen. De afleverregel (state niet bijwerken bij een niet-permanente fout) komt in WP-17. De planner houdt "bericht renderen" en "state opslaan" als aparte stappen per event, zodat WP-17 de aflevering ertussen kan zetten zonder de job te herschrijven.
- `last_notified_at`: in M1 wordt niets afgeleverd. De planner legt vast wat dit veld in M1 bevat (voorstel: leeg laten tot WP-17 echt aflevert) en controleert dat tegen de blueprint van WP-08. Open punt, geen besluit.
- Logging: de uurlijkse run draait in een publieke repo, dus de Actions-logs zijn openbaar. `run_alerts` logt alleen aantallen (gebruikers, events per soort), geen user-id's, e-mailadressen of berichtteksten. De berichtteksten zijn lokaal te zien via `shakka alerts run` en `shakka admin alerts preview`.
- Statusregels met `window_end < now - 48h` worden opgeruimd.
- `shakka.jobs.admin` en de CLI-groep `shakka admin`, met dry-run-preview.
- CLI: `shakka evaluate` en `shakka alerts run [--dry-run]`. `alerts run` toont per bericht de spot, het soort event, de titel en de body.
- Env-contract bijwerken (A-16):
  - `shakka.config.Settings` verliest `telegram_bot_token` en `telegram_chat_id`. Omdat `Settings` `extra="ignore"` gebruikt, laadt een oude `.env` met `TELEGRAM_*` nog steeds zonder fout.
  - `.env.example` verliest `TELEGRAM_BOT_TOKEN` en `TELEGRAM_CHAT_ID`.
  - Bestaande tests die deze namen gebruiken worden aangepast: `tests/test_repo_hygiene.py` (`ENV_KEYS`), `tests/test_config.py` en `tests/test_cli.py` (de lektest van `doctor` gebruikt een andere gezette variabele, bijv. `VAPID_PRIVATE_KEY`).
  - `shakka doctor` noemt geen Telegram-variabelen.
  - In `docs/RUNBOOK.md` gaan de `TELEGRAM_*`-rijen uit de tabel met variabelen.
- `docs/RUNBOOK.md`: de M1-setup voor Lars (user aanmaken, profiel en favorieten zetten, preview bekijken, `alert_state` bekijken in het Supabase-dashboard).
**Buiten scope:** de uurlijkse volgorde, logging in `ingest_runs` en operatormeldingen (WP-11), versturen, `Notifier`, `DeliveryTarget`, `load_targets` en de afleverregel (WP-17), UI (WP-16), de kolom `profiles.telegram_chat_id` verwijderen (WP-22).
**Contracten:**
- `shakka.jobs.inputs`: `SpotInputs(spot: SpotProfile, forecasts: list[ForecastHour], tides: list[TideExtreme])` en `load_inputs(db, *, now: datetime) -> dict[str, SpotInputs]`.
- `shakka.jobs.evaluate`: `run_evaluation(db, *, now: datetime) -> EvaluationJobResult(spots: int, rows: int, deleted: int)`.
- `shakka.jobs.alerts`:
  - `RenderedAlert(user_id: str, state_id: str | None, message: AlertMessage)`. `state_id` is de `alert_state.id` van het event na opslaan (WP-17 gebruikt die voor de push-`tag`); bij `dry_run` is het `None` als de rij nog niet bestaat.
  - `run_alerts(db, *, now: datetime, base_url: str | None, dry_run: bool = False) -> AlertJobResult(users: int, events: int, messages: list[RenderedAlert])`.
  - WP-17 breidt dit uit met de keyword-parameter `notifiers` en de velden `sent`, `failed` en `no_target`. Bestaande aanroepen blijven werken.
- CLI `shakka admin`:
  - `profile set --user-id UUID [--weight KG] [--level L] [--quiver 7,9,12] [--min-kn N] [--max-kn N]` (schrijft alleen de opgegeven velden);
  - `profile show --user-id UUID`;
  - `favorite add|remove --user-id UUID --spot ID`;
  - `favorite list --user-id UUID`;
  - `rule set --user-id UUID --spot ID [--min-kn N] [--max-kn N] [--dir-classes onshore,side_onshore,sideshore] [--weekdays 6,7] [--after HH:MM] [--before HH:MM] [--min-go-hours N] [--days-ahead N] [--enable|--disable]`;
  - `alerts preview --user-id UUID`: windows en berichten tonen zonder iets op te slaan.
- `shakka.config.Settings` na deze WP: `supabase_url`, `supabase_publishable_key`, `supabase_secret_key`, `app_base_url`, `vapid_public_key`, `vapid_private_key`, `vapid_subject`, `spots_path`.
**Acceptatiecriteria:**
- AC-1: `cd ingest && uv run pytest tests/test_job_evaluate.py` met `FakeSupabase` (2 spots, waarvan 1 zonder coördinaten, forecasts van 3 modellen, getij). Er komen alleen evaluaties voor de spot met coördinaten, precies één rij per uur. Rijen ouder dan 48 uur worden verwijderd.
- AC-2: `tests/test_job_alerts.py` end-to-end met `FakeSupabase`:
  - de eerste run geeft precies 1 `RenderedAlert` met `message.kind == new` en een titel met de spotnaam, plus 1 `alert_state`-rij met `status = active` en `last_event = new`; `state_id` is gelijk aan de `id` van die rij;
  - een tweede run met dezelfde data geeft 0 berichten en laat de `alert_state`-rij ongewijzigd;
  - als de forecasts daarna zo wijzigen dat het window verdwijnt, volgt 1 `cancelled`-bericht en krijgt de rij `status = cancelled`.
- AC-3: Geen kanaal in M1: `grep -rniE "telegram" ingest/src .env.example` geeft niets, en `grep -rn "shakka.notify" ingest/src/shakka/jobs` geeft niets.
- AC-4: Logging: in een test met caplog en capsys rond `run_alerts` (niet via de CLI) komen de user-id's van de testgebruikers en de body-teksten van de berichten niet voor in de logregels.
- AC-5: Dezelfde spot en data met gebruiker A (`min_kn` 12) en gebruiker B (`min_kn` 20) geven aantoonbaar verschillende windows.
- AC-6: Veiligheid. Forecasts die voor elk uur `offshore` of `side_offshore` zijn, geven bij elke regel 0 events.
- AC-7: Het gedrag voor spots met `verified: false` volgt de beslissing van Lars en is getest.
- AC-8: `shakka alerts run --dry-run` en `shakka admin alerts preview` doen geen schrijfacties (`FakeSupabase.writes` is leeg).
- AC-9: CLI-tests voor de beheer-CLI:
  - `profile set --weight 80` wijzigt alleen `weight_kg`;
  - `profile set --telegram-chat-id 1` geeft een exitcode ongelijk aan 0 (onbekende optie);
  - `rule set --dir-classes offshore` geeft exitcode 1 met een duidelijke melding;
  - `favorite add` voor een onbekende spot geeft exitcode 1.
- AC-10: Env-contract:
  - `.env.example` bevat exact `SUPABASE_URL`, `SUPABASE_PUBLISHABLE_KEY`, `SUPABASE_SECRET_KEY`, `APP_BASE_URL`, `VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY` en `VAPID_SUBJECT`, zonder waarden (behalve `VAPID_SUBJECT=mailto:`), getoetst door `tests/test_repo_hygiene.py`;
  - `Settings` heeft geen veld waarvan de naam met `telegram` begint;
  - een test laat zien dat `Settings` laadt zonder fout als `TELEGRAM_BOT_TOKEN` in de omgeving staat;
  - `cd ingest && uv run pytest` is volledig groen.
- AC-11: Met Lars' gebruiker en minstens één ingevulde favoriete spot toont `uv run shakka evaluate` gevolgd door `uv run shakka admin alerts preview --user-id <id>` de windows of "geen windows" zonder fouten. Daarna maakt `uv run shakka alerts run` bij een gevonden window een `alert_state`-rij aan die in het Supabase-dashboard te zien is. Dit is `NEEDS_LARS`.
**Nodig van Lars:**
- Een auth-user voor jezelf (Supabase dashboard → Authentication → Add user) en de user-id daarvan.
- Beslissing: gaan alerts alleen af voor spots met `verified: true`? Voorstel: ja. Niet-geverifieerde spots worden wel geëvalueerd en getoond, met een label.
- Optioneel: `TELEGRAM_*` uit je lokale `.env` halen. Laten staan kan geen kwaad.
**Omvang:** M

## WP-11: Orkestratie: uurlijkse workflow, logging, foutmeldingen
**Mijlpaal:** M1
**Afhankelijk van:** WP-10
**Doel:** Alle stappen elk uur via GitHub Actions in een vaste volgorde draaien, elke run vastleggen in `ingest_runs` en Lars bij storingen laten waarschuwen via de ingebouwde e-mailmelding van GitHub bij een gefaalde workflow-run. Er is geen eigen meldingskanaal (A-16).
**In scope:**
- `shakka.pipeline` met een geordende stappenlijst en per stap foutisolatie:
  - faalt `spots_sync`, dan gaat de run door met de spots in de database;
  - faalt `forecast` en is de nieuwste `forecast_hours.fetched_at` ouder dan 3 uur, dan wordt `alerts` overgeslagen met de reden `stale_forecast`;
  - de getijstap gebruikt de 20-uursregel uit WP-04.
- Een `ingest_runs`-rij: `running` bij de start, aan het eind `ok`, `partial` of `failed`, met per stap `{name, status, duration_ms, counts, error}`.
- Operatorsignalen, zonder eigen kanaal:
  - de exitcode van `shakka run-hourly` (zie hieronder). Een exitcode 1 laat de workflow-run falen; GitHub mailt Lars dan volgens zijn meldingsinstellingen;
  - de `ingest_runs`-rij is de bron voor de details (welke stap, welke fout);
  - een dagverbruik van Open-Meteo boven 80% van de guard wordt vastgelegd in de `ingest_runs`-rij (in `steps` bij de stap `forecast`) en als `::warning::`-annotatie in de workflow-uitvoer geschreven. Dat geeft geen e-mail; WP-22 voegt pushwaarschuwingen aan Lars toe.
- Exitcode: 1 bij `failed`, en ook bij een run waarin `alerts` is overgeslagen wegens `stale_forecast` (dan komen er geen alerts, en dat moet Lars weten). Anders 0, ook bij `partial`.
- GitHub dedupliceert niet: tijdens een aanhoudende storing komt er elk uur een mail. Dat is bewust geaccepteerd (geen eigen dedup-logica meer); de RUNBOOK beschrijft het.
- Gestructureerde logging naar stdout, zonder secrets en zonder persoonsgegevens (user-id's, e-mailadressen, berichtteksten); de Actions-logs van deze publieke repo zijn openbaar.
- `.github/workflows/hourly.yml`.
- `docs/RUNBOOK.md`:
  - runs bekijken, en de `ingest_runs`-tabel lezen;
  - een run handmatig starten;
  - de GitHub-meldingsinstelling voor Actions (in de meldingsinstellingen van het GitHub-account, onderdeel Actions: e-mail aan, desgewenst alleen bij gefaalde workflows; de builder controleert het exacte menupad), en wie de mail krijgt: de gebruiker die de workflow heeft aangemaakt of als laatste de cron-syntax wijzigde ([bron](https://docs.github.com/en/actions/concepts/workflows-and-actions/notifications-for-workflow-runs));
  - wat een gefaalde run betekent en waar je de oorzaak vindt;
  - de maatregel tegen het uitschakelen van schedules na 60 dagen (als de repo publiek is), met de gekozen aanpak.
**Buiten scope:** marine-stap (WP-12), versturen van alerts (WP-17), opruimen van sessies (WP-19), wekelijks gebruiksrapport en pushwaarschuwingen aan Lars (WP-22).
**Contracten:**
- `shakka.pipeline`:
  - `STEPS`: een geordende lijst van `(name, callable)`. In M1 is de volgorde `spots_sync`, `forecast`, `tides`, `evaluate`, `alerts`. Latere WP's voegen stappen toe op een vaste plek: `marine` direct na `forecast` (WP-12), `sessions_cleanup` aan het eind (WP-19), `usage_report` aan het eind (WP-22).
  - `run_hourly(settings: Settings, *, now: datetime, db=None, http=None) -> RunReport(status: str, steps: list[StepReport], exit_code: int)`. `exit_code` volgt de regel hierboven. WP-17 voegt de keyword-parameter `notifiers=None` toe.
  - CLI: `shakka run-hourly`, met als exitcode `RunReport.exit_code`.
- Workflow `.github/workflows/hourly.yml`:
  - `schedule` met cron `17 * * * *` en `workflow_dispatch`;
  - `concurrency` met group `hourly` en `cancel-in-progress: false`;
  - `timeout-minutes: 15`;
  - draait in `ingest/` het commando `uv run shakka run-hourly`;
  - secrets alleen via `${{ secrets.* }}`: `SUPABASE_URL`, `SUPABASE_SECRET_KEY`;
  - `APP_BASE_URL` via `${{ vars.APP_BASE_URL }}`.
**Acceptatiecriteria:**
- AC-1: `cd ingest && uv run pytest tests/test_pipeline.py` met fakes. Als alle stappen slagen, krijgt de `ingest_runs`-rij status `ok`, met de stappen in exact de contractvolgorde, en is `exit_code` 0.
- AC-2: Als de forecaststap een exception geeft:
  - draaien `tides` en `evaluate` toch;
  - wordt `alerts` overgeslagen als de nieuwste `fetched_at` ouder is dan 3 uur, en anders uitgevoerd;
  - krijgt de run status `partial`, met de fout bij de stap `forecast` in `steps`;
  - is `exit_code` 1 als `alerts` is overgeslagen (`stale_forecast`), en 0 als `alerts` wel is uitgevoerd.

  Een run met status `failed` heeft `exit_code` 1. Een CLI-test laat zien dat `shakka run-hourly` `RunReport.exit_code` als exitcode teruggeeft.
- AC-3: Met de dummy-secret `SUPABASE_SECRET_KEY=sb_secret_TESTVALUE` en een falende stap staat die waarde niet in de log-uitvoer van een run (caplog en capsys).
- AC-4: `hourly.yml` bevat alle elementen uit het contract. `grep -nE "sb_secret_" .github/workflows/*.yml` en `grep -niE "telegram" .github/workflows/*.yml` geven niets.
- AC-5: Budgetwaarschuwing: bij een dagverbruik boven 80% van de guard (fake `api_usage`) staat de waarschuwing in de `steps` van de `ingest_runs`-rij en bevat stdout een regel die begint met `::warning::`. De exitcode wordt er niet 1 door.
- AC-6: Een handmatige `workflow_dispatch`-run op GitHub slaagt en maakt een `ingest_runs`-rij met `status = ok` in het remote project. Binnen 2 uur daarna volgt een geplande run. Lars bevestigt dat e-mailmeldingen voor GitHub Actions aan staan voor zijn account. Dit is `NEEDS_LARS`.
**Nodig van Lars:**
- GitHub Secrets `SUPABASE_URL` en `SUPABASE_SECRET_KEY`.
- Optioneel de Actions-variable `APP_BASE_URL` (pas zinvol na WP-14).
- GitHub Actions aangezet voor de repo.
- In je GitHub-account e-mailmeldingen voor Actions aanzetten (meldingsinstellingen, onderdeel Actions; desgewenst alleen bij gefaalde workflows; stappen in de RUNBOOK). Controleer daarna dat jij de gebruiker bent die `hourly.yml` heeft aangemaakt, want die krijgt de meldingen.
**Omvang:** M

---

## M2: "PWA"

## WP-12: Marine-ingest (golven) en golven op de spotpagina
**Mijlpaal:** M2
**Afhankelijk van:** WP-11, WP-14 (sinds A-17; aanbevolen na WP-18)
**Doel:** Golfhoogte, golfperiode en golfrichting per spot server-side ophalen via de Open-Meteo Marine API, binnen hetzelfde call-budget, en ze op de spotpagina tonen.
**In scope:**
- Een migratie voor `marine_hours` met RLS (`select` voor `anon` en `authenticated`) en een pgTAP-test.
- `shakka.domain.marine`.
- `shakka.openmeteo.marine`: parameters, een pure parser en de fetch.
- `shakka.jobs.marine`: budget via `BudgetGuard` met source `open_meteo_marine`, upsert en opruimen na 48 uur.
- Pipelinestap `marine` direct na `forecast`. Als die faalt, wordt de run `partial` en gaan de andere stappen door.
- CLI: `shakka marine fetch`.
- Een vastgelegde echte respons als fixture, met minstens één binnenwaterlocatie (null-waarden).
- Weergave (verhuisd uit WP-14, A-17):
  - `getMarineHours` in `web/src/lib/data.ts` en het type `MarineHour` in `web/src/lib/types.ts`;
  - op `/spot/[id]` per uur golfhoogte, periode en richting, alleen als er data is. Zonder data verschijnt er niets extra en geen fout.
**Buiten scope:** golven in de evaluatie of alerts (niet in het plan), de rest van de spotpagina (WP-14).
**Contracten:**
- Tabel `marine_hours`: `spot_id text` (FK `spots`, cascade), `valid_at timestamptz`, `wave_height_m real null`, `wave_period_s real null`, `wave_dir_deg smallint null`, `fetched_at timestamptz not null`. PK (`spot_id`, `valid_at`).
- `shakka.domain.marine.MarineHour(spot_id: str, valid_at: datetime, wave_height_m: float | None, wave_period_s: float | None, wave_dir_deg: int | None)`.
- `shakka.openmeteo.marine`: `parse_marine_response(payload, locations) -> list[MarineHour]` en `fetch_marine(http, locations, *, forecast_days: int = 7) -> list[MarineHour]`.
- `shakka.jobs.marine.run_marine_ingest(db, http, budget, *, now: datetime) -> MarineIngestResult(spots: int, rows: int, calls: float, skipped_budget: bool, errors: list[str])`.
- `web/src/lib/data.ts`: `getMarineHours(spotId: string, from: Date, to: Date): Promise<MarineHour[]>`, leest alleen `marine_hours`.
**Acceptatiecriteria:**
- AC-1: Parsertest op de fixture: alle tijden zijn UTC, waarden horen bij de juiste spot, en voor een locatie met alleen `null`-waarden worden geen rijen opgeslagen.
- AC-2: Budget. Het gewicht wordt geregistreerd onder `open_meteo_marine`. Is het forecastverbruik van de dag al zo hoog dat dagverbruik plus het marinegewicht boven 8.000 komt, dan gaat er geen marine-request uit.
- AC-3: Pipelinetest. Als de marinestap faalt, wordt de run `partial` en draaien `tides`, `evaluate` en `alerts` gewoon. `STEPS` heeft de volgorde `spots_sync`, `forecast`, `marine`, `tides`, `evaluate`, `alerts`.
- AC-4: `supabase test db` is groen, inclusief: `anon` leest `marine_hours` en kan er niet in schrijven.
- AC-5: Tegen de lokale stack met een test-spot op de Noordzeekust vult `uv run shakka marine fetch` de tabel `marine_hours`.
- AC-6: `cd web && npm run check && npm test && npm run build` slaagt, en de guard uit WP-13 slaagt. Een componenttest van de spotpagina toont golfhoogte en periode bij een uur met marinedata, en geen golfregel en geen fout bij een spot zonder marinedata.
- AC-7: Alle `.from(...)`-aanroepen in `web/src/lib/data.ts` gebruiken alleen de tabellen `spots`, `evaluations`, `tide_extremes` en `marine_hours`.
**Nodig van Lars:** Na de merge `supabase db push`.
**Omvang:** M (was S; de weergave uit WP-14 is erbij gekomen)

## WP-13: PWA-basis
**Mijlpaal:** M2
**Afhankelijk van:** WP-01
**Doel:** Een installeerbare SvelteKit-PWA op Cloudflare Pages met magic-link-login, layout, bronvermelding op elke pagina en een CI-guard die client-side Open-Meteo-calls onmogelijk maakt.
**In scope:**
- `/web`:
  - SvelteKit 3 (besluit Lars, 15 oktober 2026; `#lib`, config in `vite.config.ts`) met `@sveltejs/adapter-static` in SPA-fallbackmodus, strikt TypeScript;
  - vitest met Testing Library;
  - `svelte-check`;
  - scripts `dev`, `check`, `test` en `build`.
- `web/src/lib/supabase.ts` en `web/src/lib/auth.ts`.
- Routes:
  - `/` (placeholder, wordt de spotlijst in WP-14);
  - `/login`;
  - `/over` (bronnen en een korte uitleg over de app).
- Layout met een header (loginstatus) en een footer met `Attribution`.
- `Attribution.svelte` met links naar:
  - Open-Meteo, met de tekst "Weather data by Open-Meteo.com";
  - CC BY 4.0;
  - KNMI, DWD, ECMWF, NOAA en Rijkswaterstaat.
- PWA:
  - `manifest.webmanifest` met naam Shakka, iconen van 192 en 512 (ook maskable), `display: standalone` en `start_url /`;
  - `src/service-worker/index.ts` (SvelteKit 3) die de app-shell precachet. API-responses van Supabase worden niet gecachet.
- Geen externe scripts of fonts van CDN's. Geen analytics.
- `web/.env.example`.
- CI-job `web` in `ci.yml`: `npm ci`, `check`, `test`, `build` en de guard.
- `scripts/check-no-client-openmeteo.sh`: faalt als `web/src`, `web/static` of `web/build` `api.open-meteo.com`, `marine-api.open-meteo.com` of `open-meteo.com/v1` bevat.
- `docs/RUNBOOK.md`: Cloudflare Pages-setup en de Auth-URL's in Supabase.
**Buiten scope:** spotdata tonen (WP-14), kaart (WP-15), profiel (WP-16), push (WP-18), privacypagina (WP-23).
**Contracten:**
- Omgeving: `PUBLIC_SUPABASE_URL` en `PUBLIC_SUPABASE_PUBLISHABLE_KEY` via `$app/env/public` met `src/env.ts` (`defineEnvVars`, SvelteKit 3; `$env/static/public` is deprecated).
- `web/src/lib/supabase.ts` exporteert `supabase` (supabase-js-client, alleen met de publishable key).
- `web/src/lib/auth.ts` exporteert de store `session`, `signInWithMagicLink(email: string): Promise<{ error?: string }>` (met `emailRedirectTo` = huidige origin) en `signOut()`.
- `web/src/lib/components/Attribution.svelte` met prop `compact?: boolean`. Die wordt hergebruikt in WP-14 en WP-21.
- Routetabel (gereserveerd):

  | Route | WP |
  |---|---|
  | `/` | WP-14 |
  | `/spot/[id]` | WP-14 |
  | `/go` | WP-14, later WP-20 |
  | `/profiel` en `/alerts` | WP-16 |
  | `/sessie/nieuw`, `/sessie/[slug]/delen` en `/mijn-sessies` | WP-20 |
  | `/s/[slug]` | WP-21 |
  | `/privacy` | WP-23 |
**Acceptatiecriteria:**
- AC-1: `cd web && npm ci && npm run check && npm test && npm run build` slaagt.
- AC-2: `web/build` bevat `index.html` en `manifest.webmanifest` met `name`, iconen van 192 en 512 en `display: standalone`. De build bevat een service worker, en `index.html` of de app registreert die (te controleren in de code of met een test).
- AC-3: `scripts/check-no-client-openmeteo.sh` geeft exitcode 1 op een tijdelijk fixturebestand met `https://api.open-meteo.com/v1/forecast` en exitcode 0 op de repo. De CI-job `web` draait het script.
- AC-4: Componenttest van `Attribution`: er is een link naar `https://open-meteo.com/` met een tekst die "Open-Meteo" bevat, een link naar `https://creativecommons.org/licenses/by/4.0/`, en de tekst bevat KNMI, DWD, ECMWF, NOAA en Rijkswaterstaat. Een layouttest laat zien dat de footer `Attribution` bevat.
- AC-5: Logintest met een gemockte supabase: `signInWithOtp` wordt aangeroepen met het ingevoerde e-mailadres en `emailRedirectTo` = origin. Bij een fout toont de pagina een Nederlandstalige melding.
- AC-6: `grep -rEn "googletagmanager|google-analytics|plausible|fonts.googleapis|cdn\." web/src web/static` geeft niets, en `web/build/index.html` bevat geen `<script src="http`.
- AC-7: De Cloudflare Pages-URL laadt, de app is te installeren (Chrome of Safari "Zet op beginscherm") en magic-link-login met Lars' e-mailadres werkt end-to-end. Dit is `NEEDS_LARS`.
**Nodig van Lars:**
- Een Cloudflare-account en een Pages-project gekoppeld aan de repo: root `web`, build `npm run build`, output `build`.
- Build-variabelen `PUBLIC_SUPABASE_URL` en `PUBLIC_SUPABASE_PUBLISHABLE_KEY`.
- In Supabase Auth: Site URL en Redirect URLs (Pages-URL en `http://localhost:5173`).
- Node LTS lokaal.
- Een app-icoon, of akkoord met een placeholder.
**Omvang:** M

## WP-14: Spotlijst en spotpagina
**Mijlpaal:** M2
**Afhankelijk van:** WP-10, WP-13 (WP-12 is sinds A-17 geen afhankelijkheid meer)
**Doel:** Per spot het uuroordeel met redenen, wind, richting, betrouwbaarheid en getij tonen, plus een spotlijst als standaardweergave. Alles uit de database, met eerlijke meldingen over niet-geverifieerde spots en verouderde data.
**In scope:**
- `web/src/lib/types.ts`: types met de kolomnamen uit de database.
- `web/src/lib/data.ts`: getypeerde queries.
- `web/src/lib/contracts.ts`: importeert `data/contracts/*.json`.
- `/`: lijst van alle spots met naam, regio, label "niet geverifieerd", een samenvatting van het oordeel voor de komende daglichturen van vandaag en morgen, en "nog geen data" bij spots zonder evaluaties.
- `/spot/[id]`, per dag een overzicht per uur met:
  - het oordeel als tekst en kleur (niet alleen kleur);
  - wind en vlagen in kn;
  - een richtingspijl met windroos en het label van de richtingsklasse;
  - de betrouwbaarheid;
  - de redenen als Nederlandse labels;
  - getij-extremen van die dag.

  Golven komen er in WP-12 bij (A-17). Daarnaast:
  - profielinfo (status, seizoen, hazards, notes);
  - een banner "niet geverifieerd" bij `verified: false`;
  - de versheid van de data (`evaluated_at`), met een waarschuwing als die ouder is dan 3 uur;
  - `Attribution`.
- Alle tijden in Europe/Amsterdam.
- Route `/go?spot&start&end`: in M2 een redirect naar `/spot/{spot}` (in WP-20 vervangen door sessie aanmaken). Bij ongeldige parameters een redirect naar `/`.
- `tests/test_contracts.py` (ingest) controleert dat `data/contracts/*.json` actueel is. Dat bestaat al uit WP-05.
**Buiten scope:** golven en `marine_hours` (WP-12), kaart (WP-15), favorieten (WP-16), persoonlijke limieten op de spotpagina (alleen in alerts; de pagina toont het oordeel op basis van de spot-defaults), sessies (WP-20).
**Contracten:**
- `web/src/lib/data.ts`:
  - `listSpots(): Promise<Spot[]>`;
  - `getSpot(id: string): Promise<Spot | null>`;
  - `getEvaluations(spotId: string, from: Date, to: Date): Promise<Evaluation[]>`;
  - `getSpotSummaries(now: Date): Promise<Record<string, SpotSummary>>`;
  - `getTideExtremes(station: string, from: Date, to: Date): Promise<TideExtreme[]>`.

  Deze functies lezen alleen `spots`, `evaluations` en `tide_extremes`. WP-12 voegt `getMarineHours` toe.
- `web/src/lib/contracts.ts`: `reasonLabel(code)`, `dirClassLabel(code)`, `confidenceLabel(code)` en `RIDABLE_DIR_CLASSES`.
- `web/src/lib/components/HourVerdict.svelte`: toont één uur met oordeel, wind, richting en redenen. Hergebruikt in WP-21.
- `web/src/lib/time.ts`: `formatLocal(date, pattern)` en `parseGoParams(url): { spot: string; start: Date; end: Date } | null`.
**Acceptatiecriteria:**
- AC-1: `cd web && npm run check && npm test && npm run build` slaagt, en de guard uit WP-13 slaagt.
- AC-2: Een vitest-test laat zien dat `contracts.ts` voor elke code in `reason_codes.json`, `dir_classes.json` en `confidence.json` een niet-leeg Nederlands label geeft, zonder terug te vallen op de ruwe code.
- AC-3: Componenttest van de spotpagina met fixturedata:
  - een uur met `valid_at` 2026-07-15T12:00Z wordt getoond als 14:00;
  - het oordeel staat als tekst op de pagina;
  - redenen staan als Nederlandse labels;
  - een uur met reden `offshore` toont `no_go` en het offshore-label;
  - bij `verified=false` staat de banner "niet geverifieerd" er;
  - bij een `evaluated_at` meer dan 3 uur vóór `now` staat de waarschuwing over verouderde data er;
  - `Attribution` staat op de pagina.
- AC-4: Een lijsttest laat zien dat een spot zonder evaluaties "nog geen data" toont zonder fout.
- AC-5: `parseGoParams` en `/go`:
  - geldige parameters in het formaat uit WP-08 leiden naar `/spot/{spot}`;
  - ontbrekende of ongeldige parameters leiden naar `/`;
  - een test gebruikt een URL die `build_go_url` uit WP-08 genereert (vastgelegd als fixture-string).
- AC-6: Alle `.from(...)`-aanroepen in `web/src/lib/data.ts` (`grep -n "\.from(" web/src/lib/data.ts`) gebruiken alleen de tabellen `spots`, `evaluations` en `tide_extremes`.
- AC-7: Op de gedeployde site toont `/spot/<een ingevulde spot>` actuele uren. Een `/go`-URL die met de Actions-variable `APP_BASE_URL` is gemaakt (bijv. uit `shakka admin alerts preview`), geopend in een browser, leidt naar de spotpagina. Dit is `NEEDS_LARS`. (Een tik op een pushmelding wordt in WP-18 AC-5 getoetst.)
**Nodig van Lars:** De GitHub Actions-variable `APP_BASE_URL` op de productie-URL zetten.
**Omvang:** M

## WP-15: Kaart
**Mijlpaal:** M2
**Afhankelijk van:** WP-14
**Doel:** Een kaartweergave van de spots met hun oordeel, die alleen laadt als de gebruiker erom vraagt. Zo blijven we ruim binnen 5.000 MapTiler-sessies per maand, en de lijst werkt altijd als fallback.
**In scope:**
- Een wissel tussen lijst en kaart op `/`. De lijst is de standaard.
- `MapView.svelte`:
  - laadt `maplibre-gl` alleen via dynamische `import()` na een klik op "Kaart";
  - gebruikt een MapTiler-stijl met `PUBLIC_MAPTILER_KEY`;
  - markers met kleur en een tekstlabel van het oordeel;
  - een klik op een marker opent de spotpagina;
  - de attributie van MapLibre en MapTiler is zichtbaar.
- Fallback naar de lijst, met een Nederlandse melding, als de key ontbreekt, WebGL niet beschikbaar is of de kaart niet laadt.
**Buiten scope:** geolocatie of gebruikerslocatie (privacy, niet in het plan), clustering.
**Contracten:** `web/src/lib/components/MapView.svelte` met props `spots: Spot[]` en `summaries: Record<string, SpotSummary>`. Omgevingsvariabele `PUBLIC_MAPTILER_KEY`.
**Acceptatiecriteria:**
- AC-1: `cd web && npm run check && npm test && npm run build` slaagt.
- AC-2: `grep -rl "maplibre" web/build/_app/immutable/entry/` geeft niets, terwijl een ander chunk in `web/build/_app/immutable/` `maplibre` wel bevat. In de bron staat `maplibre-gl` alleen in een dynamische `import()`.
- AC-3: Een test rendert `/` zonder interactie en toont aan dat er geen import van `maplibre-gl` gebeurt en geen fetch naar `api.maptiler.com` (gemockt).
- AC-4: Een test laat zien dat zonder `PUBLIC_MAPTILER_KEY` de kaartwissel een fallbackmelding geeft en de lijst bruikbaar blijft.
- AC-5: Uit de code of een test blijkt dat de attributiecontrol aan staat en niet verborgen is.
- AC-6: Op de gedeployde site toont de kaart na een klik markers met de juiste oordelen. Dit is `NEEDS_LARS`.
**Nodig van Lars:** Een gratis MapTiler-account en een API-key met domeinrestrictie (Pages-domein en localhost), ingesteld als `PUBLIC_MAPTILER_KEY` in Cloudflare Pages en in `web/.env`.
**Omvang:** S

## WP-16: Profiel, favorieten en alertinstellingen
**Mijlpaal:** M2
**Afhankelijk van:** WP-07, WP-14
**Doel:** Ingelogde gebruikers beheren in de PWA hun profiel (gewicht, niveau, quiver), favorieten en per favoriet de alertregel. Lege velden tonen zichtbaar de effectieve default.
**In scope:**
- `/profiel`: gewicht, niveau, quiver (maten in m², 3–21, max. 10 kites), en standaard min/max kn.
- Favorietenster op de lijst en de spotpagina, alleen voor ingelogde gebruikers.
- `/alerts`, per favoriet:
  - aan/uit;
  - min en max kn;
  - richtingsklassen: alleen de drie rijdbare als checkboxes;
  - weekdagen;
  - tijdvenster;
  - minimaal aantal go-uren;
  - dagen vooruit.

  Een leeg veld toont "standaard: X (bron)".
- `web/src/lib/rules.ts`: `effectiveRule()`, een spiegel van Python `resolve_rule`.
- `data/contracts/rule_resolution_cases.json` met minstens 8 gevallen, getoetst door een Python-test en een vitest-test.
- Validatie in formulieren, gelijk aan de DB-constraints.
- Uitgelogde gebruikers zien een loginprompt.
**Buiten scope:** push-instellingen (WP-18), account verwijderen (WP-23). De ongebruikte kolom `profiles.telegram_chat_id` (A-16) komt niet in de UI en niet in de types; WP-22 verwijdert hem.
**Contracten:**
- `web/src/lib/rules.ts`: `effectiveRule(spot: Spot, profile: Profile | null, override: AlertRuleRow | null, defaults: AlertDefaults): EffectiveRule`.
- `data/contracts/rule_resolution_cases.json`: een lijst `{spot, profile, override, expected}`.
- De UI schrijft alleen naar `profiles` (uitsluitend `weight_kg`, `level`, `quiver_m2`, `default_min_kn` en `default_max_kn`, de kolommen die `authenticated` mag wijzigen), `favorites` en `alert_rules`.
**Acceptatiecriteria:**
- AC-1: `cd web && npm run check && npm test && npm run build` slaagt, en `cd ingest && uv run pytest` slaagt.
- AC-2: Pariteit tussen Python en TypeScript. `cd ingest && uv run pytest -k rule_resolution_cases` en de vitest-test voor `effectiveRule` slagen allebei op hetzelfde JSON-bestand. Het bestand bevat minstens 8 gevallen en dekt alle vier de prioriteitsniveaus.
- AC-3: Een componenttest laat zien dat de richtingskeuze exact de checkboxes `onshore`, `side_onshore` en `sideshore` heeft, met Nederlandse labels.
- AC-4: Formuliervalidatie (componenttests): `min_kn >= max_kn` wordt geweigerd, een quivermaat buiten 3–21 wordt geweigerd, en een gewicht buiten 30–200 wordt geweigerd. Bij een weigering wordt er niets opgeslagen (mock telt 0 writes).
- AC-5: De favorietenster doet met een gemockte supabase een insert of delete op `favorites` met het juiste `spot_id`.
- AC-6: Een uitgelogde gebruiker op `/profiel` of `/alerts` ziet een loginprompt, en er gaan geen queries naar `profiles`, `favorites` of `alert_rules`.
- AC-7: Een regel die in de app is gewijzigd, verandert de uitvoer van `uv run shakka admin alerts preview --user-id <Lars>`. Dit is `NEEDS_LARS`.
- AC-8: `grep -rni "telegram" web/src` geeft niets.
**Nodig van Lars:** Niets.
**Omvang:** M

## WP-17: Web Push: backend
**Mijlpaal:** M2
**Afhankelijk van:** WP-11
**Doel:** Alerts als Web Push versturen, het enige meldingskanaal (besluit Lars, 15 oktober 2026; A-16), naar alle geregistreerde apparaten van een gebruiker, en dode abonnementen automatisch opruimen.
**In scope:**
- Een migratie voor `push_subscriptions` met RLS, plus pgTAP-tests.
- `shakka.notify.base`: de kanaalinterface (overgenomen uit het vervallen WP-09).
- `shakka.domain.push` (puur): de `AlertMessage` uit WP-08 inkorten tot een pushtekst. WP-08 levert berichten tot 1.000 tekens; een melding toont veel minder.
- `shakka.notify.webpush.WebPushNotifier` met `pywebpush` en VAPID:
  - payloadcontract, met titel en body uit `to_push_text`;
  - TTL van 12 uur;
  - `tag` per `alert_state`, zodat een update de oude melding vervangt;
  - 404 en 410 zijn een permanente fout;
  - endpoints, sleutels en de VAPID-private key komen niet in logs of exceptions.
- `shakka.jobs.alerts` (uit WP-10) uitbreiden:
  - `load_targets` geeft de push-doelen van een gebruiker;
  - aflevering tussen "bericht renderen" en "state opslaan";
  - afleverregel (verhuisd uit WP-10): als geen enkele aflevering voor een event slaagt en er minstens één niet-permanente fout is, wordt de state voor dat event niet bijgewerkt, zodat de volgende run het opnieuw probeert. In alle andere gevallen wel, ook als de gebruiker geen abonnementen heeft (`no_target`);
  - bij een permanente pushfout verwijdert de job dat abonnement; bij succes wordt `last_success_at` bijgewerkt;
  - `last_notified_at` krijgt het tijdstip van de eerste geslaagde aflevering van het event (de planner stemt dit af op wat WP-10 voor M1 heeft vastgelegd).
- Overgang van M1 naar push: windows die in M1 al een `new`-event kregen, staan als `active` in `alert_state` en geven door de deduplicatie pas weer een event bij een wezenlijke wijziging. Ze worden dus niet alsnog gepusht. De planner legt vast of dat acceptabel is of dat er bij de livegang een eenmalige stap nodig is (bijv. actieve rijen zonder `last_notified_at` opnieuw als `new` behandelen). Open punt, geen besluit.
- Zonder VAPID-configuratie is het pushkanaal uitgeschakeld, met een waarschuwing in de log. `run_alerts` draait dan zoals in M1: events worden berekend en `alert_state` wordt bijgewerkt, maar er wordt niets afgeleverd.
- `shakka.pipeline.run_hourly` krijgt de keyword-parameter `notifiers` en bouwt de `WebPushNotifier` uit `Settings`.
- `hourly.yml` geeft de VAPID-secrets door.
- CLI: `shakka alerts test-push --user-id UUID`.
- `docs/RUNBOOK.md`: hoe je een VAPID-sleutelpaar genereert.
**Buiten scope:** abonneren in de browser en de service worker (WP-18), pushmeldingen aan Lars over gebruik en drempels (WP-22), andere kanalen.
**Contracten:**
- Tabel `push_subscriptions`: `id uuid default gen_random_uuid()`, `user_id uuid` (FK `auth.users`, cascade), `endpoint text unique not null`, `p256dh text not null`, `auth text not null`, `created_at`, `last_success_at timestamptz null`. PK `id`. RLS: `select`, `insert` en `delete` op de eigen rijen. `anon` heeft geen rechten.
- `shakka.notify.base`:
  - `DeliveryResult(ok: bool, permanent_failure: bool, detail: str)`;
  - `PushTarget(subscription_id: str, endpoint: str, p256dh: str, auth: str)`;
  - `DeliveryTarget = PushTarget` (een alias, zodat een later kanaal de union kan uitbreiden);
  - het `Notifier`-Protocol met `channel: str` en `send(target: DeliveryTarget, message: AlertMessage, *, tag: str) -> DeliveryResult`.
- `shakka.domain.push`:
  - `PUSH_TITLE_MAX = 50` en `PUSH_BODY_MAX = 150` (tekens, Unicode code points; besluit Lars);
  - `PushText(title: str, body: str)`;
  - `to_push_text(message: AlertMessage) -> PushText`. Regels: past de tekst, dan blijft hij ongewijzigd. Is de body te lang, dan worden hele regels vanaf het begin van `body` genomen zolang ze passen. Past zelfs de eerste regel niet, dan wordt die op een woordgrens afgekapt en eindigt hij op "…". Voor de titel geldt hetzelfde afkappen. De titel is nooit leeg. De volledige tekst blijft bereikbaar via de `url` van de melding. De volgorde van de regels in `body` bepaalt WP-08; WP-17 verandert die niet.
- `shakka.notify.webpush.WebPushNotifier(vapid_private_key: str, vapid_subject: str)` met `channel = "webpush"` en `send(target: PushTarget, message: AlertMessage, *, tag: str) -> DeliveryResult`.
- Push-payload (JSON, maximaal 3.000 bytes): `{"title": str, "body": str, "url": str, "tag": str}`. `title` en `body` komen uit `to_push_text`. `url` is de `go_url`, of anders `/spot/{spot_id}`. `tag` is `alert-{alert_state.id}` (de `state_id` uit `RenderedAlert`).
- `shakka.jobs.alerts`:
  - `load_targets(db, user_id: str) -> list[DeliveryTarget]`;
  - `run_alerts(db, *, now: datetime, base_url: str | None, dry_run: bool = False, notifiers: Mapping[str, Notifier] | None = None) -> AlertJobResult(users: int, events: int, messages: list[RenderedAlert], sent: int, failed: int, no_target: int)`. Zonder `notifiers` (of met een lege mapping) gedraagt de functie zich als in WP-10.
- `shakka.pipeline.run_hourly(settings, *, now, db=None, http=None, notifiers=None)`.
**Acceptatiecriteria:**
- AC-1: `supabase test db` is groen. Een gebruiker ziet, maakt en verwijdert alleen eigen abonnementen, en `anon` heeft geen toegang.
- AC-2: Een unittest met een gemockte pywebpush-aanroep laat zien:
  - de payload heeft exact de sleutels `title`, `body`, `url` en `tag`;
  - `title` en `body` zijn gelijk aan `to_push_text(message)`;
  - de payload is maximaal 3.000 bytes;
  - de VAPID-claims bevatten `sub` = `VAPID_SUBJECT`.
- AC-3: `cd ingest && uv run pytest tests/test_push_text.py`:
  - voor elk golden-bericht uit de tests van WP-08 is de titel hoogstens 50 en de body hoogstens 150 tekens;
  - een bericht dat al past blijft ongewijzigd;
  - een lange body met meerdere regels wordt op een regelgrens afgekapt;
  - een eerste regel die te lang is, eindigt op "…" en wordt niet midden in een woord afgekapt;
  - de titel is nooit leeg;
  - `tests/test_domain_purity.py` is groen met `shakka.domain.push`.
- AC-4: Bij een `FakeSupabase`-test volgt op 410 of 404 `permanent_failure`, verwijdert `run_alerts` dat abonnement en schuift de state door. Een 5xx telt als niet-permanent: zonder andere geslaagde aflevering blijft de state ongewijzigd en levert de volgende run opnieuw af.
- AC-5: Een gebruiker met 2 push-abonnementen krijgt per event 2 afleveringen. Faalt één abonnement, dan wordt het andere toch bediend. Een gebruiker zonder abonnementen leidt niet tot een crash, verhoogt `no_target` en de state schuift door.
- AC-6: Zonder VAPID-variabelen draait `run_alerts` (via `run_hourly`) zonder exception en logt een waarschuwing. Er zijn 0 afleveringen, `messages` is gevuld en `alert_state` wordt bijgewerkt zoals in WP-10 AC-2.
- AC-7: `hourly.yml` geeft `VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY` en `VAPID_SUBJECT` door via `${{ secrets.* }}`.
- AC-8: Met dummy-waarden voor endpoint, `p256dh`, `auth` en `VAPID_PRIVATE_KEY` en een falende aflevering staan die waarden en de user-id niet in `DeliveryResult.detail` en niet in caplog of capsys.
**Nodig van Lars:**
- Een VAPID-sleutelpaar genereren (commando in de RUNBOOK) en in `.env` en de GitHub Secrets zetten.
- `VAPID_SUBJECT=mailto:<adres>`.
- `supabase db push`.
**Omvang:** M (was S; de kanaalinterface, de afleverregel en de inkorting zijn erbij gekomen door A-16)

## WP-18: Web Push: PWA
**Mijlpaal:** M2
**Afhankelijk van:** WP-16, WP-17
**Doel:** Gebruikers zetten op hun telefoon met één tik meldingen aan. De service worker toont binnenkomende alerts, en een tik opent de juiste pagina.
**In scope:**
- Op `/alerts` een sectie "Meldingen op dit apparaat":
  - toestemming pas vragen na een tik;
  - `pushManager.subscribe({ userVisibleOnly: true, applicationServerKey })` met `PUBLIC_VAPID_PUBLIC_KEY`;
  - een insert in `push_subscriptions`;
  - uitzetten doet `subscription.unsubscribe()` en een delete van de rij.
- In `src/service-worker/index.ts`:
  - een `push`-handler die `showNotification(title, { body, tag, data: { url } })` aanroept;
  - een `notificationclick`-handler die een bestaand venster focust of `clients.openWindow(url)` aanroept.
- Op iOS buiten standalone-modus: een uitleg om de app eerst op het beginscherm te zetten (iOS 16.4+). Browsers zonder ondersteuning krijgen een melding.
**Buiten scope:** de verzendkant (WP-17), meldingsvoorkeuren (er is maar één kanaal).
**Contracten:** `web/src/lib/push.ts` met `isPushSupported(): boolean`, `needsInstallFirst(): boolean`, `enablePush(): Promise<{ ok: boolean; error?: string }>` en `disablePush(): Promise<void>`. Omgevingsvariabele `PUBLIC_VAPID_PUBLIC_KEY`. De payload is zoals in WP-17.
**Acceptatiecriteria:**
- AC-1: `cd web && npm run check && npm test && npm run build` slaagt.
- AC-2: Unittests met gemockte `Notification`, `PushManager` en supabase:
  - bij het laden van de pagina wordt geen toestemming gevraagd;
  - een tik roept `subscribe` aan met de VAPID-key, omgezet naar een `Uint8Array`, en daarna een insert met `endpoint`, `p256dh` en `auth`;
  - `disablePush` roept `unsubscribe()` aan en verwijdert de rij.
- AC-3: Tests van de service-worker-handlers:
  - een `push`-event met de payload uit WP-17 roept `showNotification` aan met de juiste `title`, `body`, `tag` en `data.url`;
  - `notificationclick` opent of focust `data.url`.
- AC-4: Met een gesimuleerde iOS-user-agent buiten standalone-modus toont de pagina de installatie-uitleg in plaats van de schakelaar.
- AC-5: Op Lars' telefoon: push aanzetten, `uv run shakka alerts test-push --user-id <id>` verschijnt als melding, en een tik opent de juiste pagina. Dit is `NEEDS_LARS`.
**Nodig van Lars:** Testen op je eigen telefoon. Zet `PUBLIC_VAPID_PUBLIC_KEY` in Cloudflare Pages.
**Omvang:** M

---

## M3: "crew"

## WP-19: Sessies: datamodel, RLS en RPC's
**Mijlpaal:** M3
**Afhankelijk van:** WP-11
**Doel:** Een veilig datamodel voor sessies en RSVP's. Organisatoren beheren hun sessies via RLS. Anonieme bezoekers lezen en RSVP'en alleen via strikt begrensde RPC's met een geheime edit-token. Er zijn rate limits en een bewaartermijn.
**In scope:**
- Migraties voor `sessions` en `rsvps` met CHECK-constraints.
- RLS op `sessions` voor de organisator.
- Geen directe tabeltoegang voor `anon` en geen directe toegang tot `rsvps` voor wie dan ook.
- Security-definer-functies met `set search_path = ''`.
- Een slug van minstens 10 tekens, willekeurig, server-side gegenereerd.
- De edit-token is 32 willekeurige bytes in base64url. Opgeslagen wordt alleen een sha256-hash.
- Rate limits zonder IP-adressen:
  - max. 30 RSVP's per sessie;
  - max. 10 keer `rsvp_create` per sessie per 10 minuten;
  - max. 10 sessies per organisator per 24 uur;
  - geen nieuwe RSVP's op een geannuleerde of afgelopen sessie.
- Opruimfunctie, plus pipelinestap `sessions_cleanup` aan het eind van `STEPS`.
- pgTAP-tests.
**Buiten scope:** UI (WP-20, WP-21), IP-gebaseerde rate limiting (geen IP-opslag, privacy).
**Contracten:**
- Tabel `sessions`:
  - `id uuid default gen_random_uuid()`;
  - `slug text unique not null`;
  - `spot_id text` (FK `spots`);
  - `organizer_id uuid` (FK `auth.users`, cascade);
  - `organizer_name text not null` (1–30 tekens);
  - `starts_at timestamptz not null` en `ends_at timestamptz not null`, met `ends_at > starts_at` en max. 16 uur;
  - `note text null` (max. 280);
  - `seats_free smallint null` (0–8);
  - `departure_point text null` (max. 80);
  - `tikkie_url text null` (alleen `https://`, max. 200);
  - `cancelled_at timestamptz null`, `created_at`, `updated_at`.

  PK `id`.
- Tabel `rsvps`:
  - `id uuid default gen_random_uuid()`;
  - `session_id uuid` (FK `sessions`, cascade);
  - `first_name text not null` (1–30, getrimd);
  - `ride text not null default 'own'` (`own`, `needs_ride`, `offers_ride`);
  - `seats_offered smallint null` (0–8);
  - `rides_with uuid null` (FK `rsvps`, on delete set null);
  - `edit_token_hash text not null`;
  - `created_at`, `updated_at`.

  PK `id`.
- RLS op `sessions`: `authenticated` mag `insert` met `organizer_id = auth.uid()`, en `select` en `update` op de eigen rijen. `anon` heeft geen rechten. Op `rsvps` heeft niemand directe rechten.
- RPC's (via PostgREST `/rest/v1/rpc/<naam>`):
  - `get_public_session(p_slug text) returns jsonb`. Uitvoerbaar door `anon` en `authenticated`. Geeft `{session: {slug, spot_id, spot_name, organizer_name, starts_at, ends_at, note, seats_free, departure_point, tikkie_url, cancelled}, rsvps: [{id, first_name, ride, seats_offered, rides_with, created_at}]}` terug, of `null`. Nooit `organizer_id`, e-mailadressen of tokens.
  - `rsvp_create(p_slug text, p_first_name text, p_ride text, p_seats_offered int) returns jsonb` geeft `{rsvp_id, edit_token}` terug. Uitvoerbaar door `anon` en `authenticated`.
  - `rsvp_update(p_edit_token text, p_first_name text, p_ride text, p_seats_offered int, p_rides_with uuid) returns jsonb`. Uitvoerbaar door `anon` en `authenticated`.
  - `rsvp_delete(p_edit_token text) returns boolean`. Uitvoerbaar door `anon` en `authenticated`.
  - `purge_expired_sessions(p_now timestamptz) returns integer`. Alleen uitvoerbaar met de secret key (service role).
  - Fouten hebben een vaste `errcode` en een `message` met een code uit `rate_limited`, `session_closed`, `session_full`, `invalid_input` en `invalid_token`.
- `shakka.jobs.sessions.purge_expired_sessions(db, *, now: datetime) -> int` roept de RPC aan. De pipelinestap heet `sessions_cleanup`.
**Acceptatiecriteria:**
- AC-1: `supabase test db` is groen. `anon` kan in `sessions` en `rsvps` niet selecteren, inserten, updaten of deleten. `authenticated` kan `rsvps` niet direct selecteren.
- AC-2: Een `authenticated` gebruiker:
  - maakt een sessie voor zichzelf, waarbij de slug matcht op `^[A-Za-z0-9_-]{10,}$`;
  - kan geen sessie maken met de `organizer_id` van iemand anders;
  - kan de sessies van een ander niet updaten.
- AC-3: `get_public_session` als `anon` geeft de sessie en de RSVP's terug. De JSON-sleutels bevatten geen `organizer_id`, `edit_token`, `edit_token_hash` of `email`. Een onbekende slug geeft `null`.
- AC-4: `rsvp_create` als `anon` geeft een token terug. `rsvp_update` en `rsvp_delete` met dat token werken. Met een verkeerd token volgt de fout `invalid_token` of `false`. De opgeslagen `edit_token_hash` is niet gelijk aan het token.
- AC-5: Rate limits en validatie:
  - de 31e RSVP geeft `session_full`;
  - de 11e `rsvp_create` binnen 10 minuten geeft `rate_limited`;
  - een RSVP op een geannuleerde of afgelopen sessie geeft `session_closed`;
  - een lege `first_name` of een van 31 tekens geeft `invalid_input`;
  - een `tikkie_url` met `http://` wordt geweigerd;
  - de 11e sessie van een organisator binnen 24 uur wordt geweigerd.
- AC-6: `purge_expired_sessions` verwijdert alleen sessies met `ends_at < p_now - <bewaartermijn>`, inclusief hun RSVP's (cascade). `anon` en `authenticated` kunnen de functie niet uitvoeren.
- AC-7: `cd ingest && uv run pytest tests/test_pipeline.py` is groen. `STEPS` eindigt op `sessions_cleanup`, en als die stap faalt wordt de run `partial` zonder dat andere stappen geraakt worden.
**Nodig van Lars:** Beslissing over de bewaartermijn van sessies en RSVP's na `ends_at` (voorstel: 7 dagen). Na de merge `supabase db push`.
**Omvang:** M

## WP-20: Sessie aanmaken en delen
**Mijlpaal:** M3
**Afhankelijk van:** WP-14, WP-19
**Doel:** Vanuit een alert ("Ik ga") of vanaf de spotpagina met een paar tikken een sessie aanmaken en die als link in WhatsApp delen. De organisator beheert zijn eigen sessies.
**In scope:**
- `/go?spot&start&end`, nu met:
  - ingelogd: door naar `/sessie/nieuw`, vooraf ingevuld;
  - uitgelogd: eerst inloggen, daarna terug naar dezelfde `/go`-URL.
- `/sessie/nieuw`:
  - spot;
  - datum en begin- en eindtijd (lokaal);
  - voornaam van de organisator (alleen lokaal onthouden in `localStorage`);
  - notitie;
  - vrije plekken;
  - vertrekpunt;
  - optionele Tikkie-link.

  Validatie gelijk aan de DB-constraints.
- `/sessie/[slug]/delen`:
  - de link `{origin}/s/{slug}`;
  - een WhatsApp-knop;
  - Web Share API als die beschikbaar is;
  - een kopieerknop.
- Een knop "Ik ga" op de spotpagina bij een reeks go-uren, die naar `/go` linkt.
- `/mijn-sessies`: eigen komende sessies, met bewerken en annuleren (`cancelled_at`).
**Buiten scope:** de publieke pagina en RSVP (WP-21), backendwijzigingen (de `go_url` bestaat sinds WP-08).
**Contracten:**
- `web/src/lib/sessions.ts`:
  - `createSession(input: NewSession): Promise<{ slug: string }>`;
  - `listMySessions(): Promise<Session[]>`;
  - `cancelSession(id: string): Promise<void>`;
  - `updateSession(id: string, patch: Partial<NewSession>): Promise<void>`;
  - `shareText(session, spotName, url): string`;
  - `whatsappUrl(text: string): string`, dat `https://wa.me/?text=` + `encodeURIComponent(text)` geeft.
- `localStorage`-sleutel `shakka:organizer_name`.
**Acceptatiecriteria:**
- AC-1: `cd web && npm run check && npm test && npm run build` slaagt.
- AC-2: `/go` met een URL van `build_go_url` (fixture):
  - ingelogd leidt naar `/sessie/nieuw`, met begin- en eindtijd vooraf ingevuld in lokale tijd (ook een test rond de wisseling naar wintertijd op 25-10-2026);
  - uitgelogd leidt naar `/login`, met terugkeer naar exact dezelfde `/go`-URL.
- AC-3: `whatsappUrl(shareText(...))` begint met `https://wa.me/?text=`. De gedecodeerde tekst bevat de spotnaam, de lokale datum en het tijdvenster, en de absolute URL `.../s/{slug}`.
- AC-4: Componenttests van het formulier:
  - `ends <= starts` wordt geweigerd;
  - `seats_free` buiten 0–8 wordt geweigerd;
  - een Tikkie-link zonder `https://` wordt geweigerd;
  - een voornaam van meer dan 30 tekens wordt geweigerd;
  - bij een weigering volgt geen insert.
- AC-5: `cancelSession` zet `cancelled_at` (gemockt). `/mijn-sessies` vraagt alleen sessies op van de ingelogde gebruiker.
- AC-6: Op een telefoon: op een echte pushmelding van een alert tikken (die opent de `go_url`), sessie aanmaken, delen naar WhatsApp en de link openen. Dit is `NEEDS_LARS`.
**Nodig van Lars:**
- `APP_BASE_URL` gezet (sinds WP-14).
- Beslissing: mogen crewleden in M3 zelf sessies organiseren? Dan moet eerst een eigen SMTP-dienst (gratis tier) in Supabase Auth worden ingesteld, omdat de standaard-SMTP alleen naar teamleden mailt en max. 2 per uur. Zonder eigen SMTP kan in M3 alleen Lars organiseren; de crew RSVP't zonder account.
**Omvang:** M

## WP-21: Publieke sessiepagina en RSVP zonder account
**Mijlpaal:** M3
**Afhankelijk van:** WP-14, WP-19
**Doel:** Iedereen met de link ziet wie er gaat, het actuele oordeel voor het tijdvenster en de carpoolsituatie, en tikt "Ik ook" met alleen een voornaam. Geen account, geen app.
**In scope:**
- `/s/[slug]` via `get_public_session`:
  - spotnaam met een link naar de spotpagina;
  - datum en tijdvenster lokaal;
  - organisator;
  - notitie;
  - carpool (vrije plekken, vertrekpunt, wie zoekt een lift en wie biedt er een aan);
  - Tikkie-link (extern, met `rel="noopener noreferrer"`);
  - deelnemerslijst;
  - de uren van het window met `HourVerdict` uit `evaluations`, de versheid van de data en `Attribution`;
  - een banner als de sessie geannuleerd is.
- Formulier "Ik ook": voornaam en lift-optie. Na `rsvp_create` wordt de token opgeslagen in `localStorage`, en daarna toont de pagina "Jij gaat", met wijzigen en afmelden.
- Nederlandse foutmeldingen voor de RPC-foutcodes.
- `<meta name="robots" content="noindex">`.
**Buiten scope:** dynamische OG-previews per sessie (de site is statisch, dus WhatsApp toont de algemene preview van de app), pushmeldingen naar deelnemers.
**Contracten:** `web/src/lib/rsvp.ts` met `getPublicSession(slug)`, `createRsvp(slug, input)`, `updateRsvp(token, input)` en `deleteRsvp(token)`. De `localStorage`-sleutel is `shakka:rsvp:{slug}` met waarde `{rsvp_id, edit_token}`.
**Acceptatiecriteria:**
- AC-1: `cd web && npm run check && npm test && npm run build` slaagt.
- AC-2: Een test met een gemockte RPC rendert de deelnemers, carpoolinformatie en uren van het window. Er wordt geen auth-sessie vereist of opgevraagd.
- AC-3: RSVP-flowtest:
  - versturen roept `rsvp_create` aan met een getrimde voornaam;
  - de token wordt opgeslagen onder `shakka:rsvp:{slug}`;
  - na het opnieuw renderen toont de pagina wijzigen en afmelden;
  - afmelden roept `rsvp_delete` aan en verwijdert de sleutel.
- AC-4: De RPC-fouten `rate_limited`, `session_full`, `session_closed` en `invalid_input` leiden elk tot een eigen Nederlandse melding.
- AC-5: De pagina bevat `<meta name="robots" content="noindex">` en een geannuleerde sessie toont de banner. Er is geen formulier om je aan te melden voor een geannuleerde of afgelopen sessie.
- AC-6: `Attribution` staat op de pagina.
- AC-7: De link in WhatsApp openen op een telefoon zonder account, en een RSVP plaatsen, wijzigen en afmelden. Dit is `NEEDS_LARS`.
**Nodig van Lars:** Niets.
**Omvang:** M

---

## M4: "klaar voor anderen"

## WP-22: Hardening backend en kostenbewaking
**Mijlpaal:** M4
**Afhankelijk van:** WP-00 t/m WP-21 (alle eerdere WP's, zonder het vervallen WP-09)
**Doel:** De backend betrouwbaar maken bij storingen van externe bronnen, en het verbruik van alle gratis tiers zichtbaar bewaken, zodat Shakka ook met meer gebruikers €0 per maand blijft.
**In scope:**
- Alle externe HTTP-calls (Open-Meteo, Rijkswaterstaat, Supabase REST) via `shakka.http.make_client` met een timeout en een uniforme retry/backoff-helper. De pywebpush-aanroep (WP-17) krijgt een expliciete timeout; de planner verifieert hoe pywebpush dat ondersteunt.
- Een service-only RPC `db_usage()` die de databasegrootte en het aantal rijen per tabel teruggeeft.
- Een wekelijks gebruiksrapport voor Lars als pushmelding (A-16; Web Push is het enige kanaal), als pipelinestap `usage_report`. Die draait op maandag één keer, gededupliceerd via `ingest_runs`.
  - Het volledige rapport wordt opgeslagen in de `steps` van de `ingest_runs`-rij (te lezen in het Supabase-dashboard). Het bevat:
    - Open-Meteo-calls (maximum per dag en totaal per maand, afgezet tegen de limieten);
    - de grootte van de database tegen 500 MB;
    - het aantal rijen per tabel;
    - het succespercentage van `ingest_runs`;
    - het aantal gebruikers en abonnementen.
  - De pushmelding is een korte samenvatting binnen de grenzen van `shakka.domain.push` (titel 50, body 150 tekens), met eventuele waarschuwingen eerst.
  - De melding gaat naar de push-abonnementen van Lars, gevonden via `OPERATOR_USER_ID` (voorstel; de planner bevestigt of kiest een alternatief zonder persoonsgegevens in de repo). Ontbreekt die of heeft Lars geen abonnement, dan wordt het rapport wel opgeslagen en logt de stap een waarschuwing.
- Drempelwaarschuwingen, ook als pushmelding aan Lars: database boven 300 MB, Open-Meteo boven 70% van een limiet.
- Een migratie die de ongebruikte kolom `profiles.telegram_chat_id` (en de check-constraint `profiles_telegram_chat_id_format`) verwijdert, met aangepaste pgTAP-tests (`01_schema`, `02_privileges`, `04_rls_users`). Zie A-16.
- De rate limits van Supabase Auth controleren en documenteren.
- Eigen SMTP voor magic links (gratis tier, keuze van Lars).
- `docs/RUNBOOK.md` aanvullen met:
  - de handmatige maandcheck van MapTiler-sessies en GitHub Actions-minuten;
  - de bevestiging van Open-Meteo over niet-commercieel gebruik (datum en uitkomst).
- Een dependency-audit.
**Buiten scope:** privacy, toegankelijkheid en performance van de PWA (WP-23). Betaalde monitoring.
**Contracten:**
- `shakka.http.with_retries(fn, *, attempts: int = 3, backoff: float = 1.0)`.
- `shakka.domain.usage.build_usage_report(stats: UsageStats) -> str` (puur), `usage_warnings(stats: UsageStats) -> list[str]` (puur) en `usage_push_text(stats: UsageStats) -> PushText` (puur, binnen `PUSH_TITLE_MAX` en `PUSH_BODY_MAX` uit WP-17).
- RPC `db_usage() returns jsonb`, alleen voor de service role.
- Pipelinestap `usage_report`, die verstuurt via de `Notifier` uit WP-17.
- Omgevingsvariabele `OPERATOR_USER_ID` (voorstel, zie het env-contract).
- Tabel `profiles` zonder de kolom `telegram_chat_id`.
**Acceptatiecriteria:**
- AC-1: `grep -rn "httpx.Client(" ingest/src` vindt alleen `shakka/http.py`. Een test laat zien dat clients uit `make_client` een eindige timeout hebben.
- AC-2: `cd ingest && uv run pytest tests/test_usage.py` toetst `build_usage_report` (golden-tekst) en `usage_warnings`. Bij 310 MB volgt een databasewaarschuwing, bij 7.100 calls per dag een Open-Meteo-waarschuwing, en onder de drempels volgt geen waarschuwing.
- AC-3: Een pipelinetest met een nep-notifier laat zien dat `usage_report` alleen op maandag en maar één keer per week een pushmelding verstuurt, naar de abonnementen van de operator. Zonder operator of zonder abonnement crasht de stap niet en staat het rapport toch in `ingest_runs`. De titel en body van de melding blijven binnen 50 en 150 tekens.
- AC-4: `supabase test db` laat zien dat `db_usage()` niet uitvoerbaar is door `anon` en `authenticated`.
- AC-5: `cd web && npm audit --omit=dev --audit-level=high` geeft exitcode 0.
- AC-6: In `docs/RUNBOOK.md` staan de bevestiging van Open-Meteo (datum en uitkomst) en de gekozen SMTP-dienst. Een magic link naar een e-mailadres dat geen teamlid is, komt aan. Dit is `NEEDS_LARS`.
- AC-7: `supabase test db` is groen, en de `columns_are`-test voor `profiles` in `supabase/tests/01_schema.test.sql` noemt `telegram_chat_id` niet meer (de tabel heeft die kolom dus niet). `grep -rni "telegram" ingest/src web/src` geeft niets. De oude migraties blijven ongewijzigd.
**Nodig van Lars:**
- Na de merge `supabase db push` (verwijdert `profiles.telegram_chat_id`).
- `OPERATOR_USER_ID` (je eigen user-id) in `.env` en als GitHub Secret, als de planner dat voorstel overneemt, en push aan op je telefoon (WP-18).
- Een mail aan Open-Meteo met de vraag of een gratis publieke app zonder ads onder niet-commercieel gebruik valt (open punt uit het plan).
- Een keuze en account voor een SMTP-dienst met een gratis tier, ingesteld in Supabase Auth.
- De rate limits van Supabase Auth instellen in het dashboard.
**Omvang:** M

## WP-23: Privacy, toegankelijkheid en performance
**Mijlpaal:** M4
**Afhankelijk van:** WP-00 t/m WP-21 (alle eerdere WP's, zonder het vervallen WP-09)
**Doel:** De PWA klaarmaken voor anderen. Minimale en uitlegbare persoonsgegevens, met de mogelijkheid je account te verwijderen. Toegankelijk, snel, en met een CSP die afdwingt dat de browser alleen met de eigen origin, Supabase en MapTiler praat.
**In scope:**
- `/privacy`: welke gegevens, waarom en hoe lang, en hoe je ze verwijdert. Gelinkt vanuit de footer.
- `docs/PRIVACY.md`: een inventaris van alle persoonsgegevens per tabel en per `localStorage`-sleutel, met bewaartermijnen.
- Een RPC `delete_my_account()` (security definer) die de eigen `auth.users`-rij verwijdert. Alle gekoppelde rijen gaan mee via cascade. In `/profiel` komt een knop met bevestiging.
- `web/static/_headers` met een Content-Security-Policy:
  - `connect-src`: alleen `'self'`, de Supabase-URL en MapTiler;
  - `script-src 'self'`.
- Automatische toegankelijkheidstests met axe-core op de hoofdpagina's.
- Een JS-budget voor het entry-chunk, gecontroleerd in CI.
**Buiten scope:** backend-hardening (WP-22), nieuwe functionaliteit.
**Contracten:** RPC `delete_my_account() returns void`, alleen voor `authenticated`. Het bestand `web/static/_headers`. Het script `scripts/check-bundle-size.mjs`, met de drempel vastgelegd in de blueprint (voorstel: 150 kB gzip voor het entry-chunk, exclusief het kaart-chunk).
**Acceptatiecriteria:**
- AC-1: `supabase test db`:
  - `delete_my_account()` als gebruiker A verwijdert A uit `auth.users` en alle rijen van A in `profiles`, `favorites`, `alert_rules`, `alert_state`, `push_subscriptions` en `sessions` (met RSVP's);
  - de rijen van B blijven intact;
  - `anon` kan de functie niet uitvoeren.
- AC-2: axe-core-tests op `/`, `/spot/[id]`, `/s/[slug]`, `/profiel`, `/alerts` en `/login` met fixturedata geven 0 overtredingen met impact `serious` of `critical`.
- AC-3: `node scripts/check-bundle-size.mjs` draait in CI en faalt boven de drempel.
- AC-4: Een test parseert `web/static/_headers`. De CSP bevat `connect-src`, en die bevat geen `open-meteo`, geen `*` en geen analytics-domeinen.
- AC-5: `/privacy` bestaat en is gelinkt vanuit de footer. De pagina noemt e-mail (login), voornaam (RSVP), profielgegevens en push-abonnementen, en noemt Telegram niet (A-16). De bewaartermijnen komen overeen met de implementatie: forecastdata 48 uur, sessies volgens WP-19.
- AC-6: Lighthouse op de gedeployde site (mobiel): toegankelijkheid minstens 90, performance minstens 80, en de PWA is te installeren. Dit is `NEEDS_LARS`.
**Nodig van Lars:** Akkoord op de privacytekst.
**Omvang:** M

---

## Beslissingen voor Lars

| Wanneer | Beslissing | Voorstel |
|---|---|---|
| Vóór WP-00 | Wordt de repo publiek of privé? | **Publiek.** GitHub Actions is dan onbeperkt gratis; privé geeft 2.000 min/maand en de uurlijkse job gebruikt er naar schatting 720–1.500. Nadeel: schedules worden na 60 dagen zonder commits stil uitgeschakeld. WP-11 legt een maatregel vast. Er staan geen secrets in de repo. |
| Start WP-05 | Drempelwaarden van de evaluatie | De planner doet een voorstel. Lars toetst in de M1-testweek. |
| Start WP-06 | Voorbeeldtabel voor kite-advies | De planner stelt hem op. Lars zet `checked_by_lars: true`. |
| Start WP-07 | Defaults `min_go_hours` en `days_ahead` | De planner doet een voorstel. |
| Start WP-10 | Alerts alleen voor spots met `verified: true`? | Ja. |
| Start WP-11 | GitHub-meldingen bij een gefaalde run aanzetten; accepteren dat er tijdens een storing elk uur een mail komt | Ja (A-16). Wie de mail krijgt, volgt uit wie `hourly.yml` aanmaakt; controleren bij WP-11 AC-6. |
| Start WP-22 | Hoe vindt de pipeline jouw push-abonnementen voor het gebruiksrapport? | `OPERATOR_USER_ID` als secret. |
| Start WP-19 | Bewaartermijn sessies en RSVP's | 7 dagen na `ends_at`. |
| Start WP-20 of WP-22 | Eigen SMTP-dienst (gratis tier) | Uiterlijk vóór M4. Eerder als crewleden in M3 zelf moeten kunnen organiseren. |

Niet opgenomen, omdat het buiten de huidige scope valt: stille uren voor meldingen 's nachts. Een alert kan dus ook om 03:00 binnenkomen. Wil je dit wel, dan is het een scopewijziging via het plan.

## Bevestigde beslissingen (Lars, 15 oktober 2026)

Genomen tijdens de nachtrun van 14 oktober en door Lars bevestigd. Latere planners bouwen hierop.

| WP | Beslissing | Gevolg |
|---|---|---|
| WP-03 | **Vlagen een uur terugschuiven** (A14): `gust_kn` op `valid_at = T` is het maximum over [T, T+1h); het laatste uur van een respons heeft `gust_kn = None`. | WP-05 en WP-07: een ontbrekende vlaag is "onbekend", nooit 0. Tijdsemantiek is consistent met "uurwaarden horen bij het uur dat begint op `valid_at`". |
| WP-03 | `cell_selection=sea` bij Open-Meteo. | Kustspots krijgen het zeerasterpunt. Bij meren met grove modellen kan dat minder passen; per spot te herzien in WP-22. |
| WP-04 | `httpx` rechtstreeks naar DDAPI20 in plaats van `ddlpy`. | Geen extra dependencies; timeout via `make_client`. Stackregel in PROJECT_PLAN aangepast. |
| WP-04 | Agger: `laagwater 1` en `laagwater 2` zijn beide `low`; topagger wordt niet opgeslagen. | WP-05: getijvoorkeur werkt op het geschatte niveau (`estimate_tide_level`), niet op strikte afwisseling hoog/laag. |
| WP-13 | SvelteKit 3 (niet 2). | `#lib`, `$app/env/public` via `src/env.ts`, `src/service-worker/index.ts`, config in `vite.config.ts`. Contractregels van WP-13 en WP-18 zijn aangepast. |
| WP-13 | `shouldCreateUser: false` bij de magic link, tot WP-22. | Nieuwe gebruikers maakt Lars aan in het Dashboard. Open aanmelden komt pas met eigen SMTP. |
| WP-13 | Node 24.22.0 op Cloudflare Pages; placeholder-icoon tot er een echt icoon is. | `NODE_VERSION=24.22.0` als Pages-variabele. |
| Alle | **Telegram vervalt volledig; Web Push (VAPID) is het enige meldingskanaal.** Scopewijziging van 15 oktober 2026. Pushteksten: titel hoogstens 50, body hoogstens 150 tekens. | Zie A-16 en A-17. WP-09 is `dropped`. M1 = alerts berekend en vastgelegd in `alert_state`, controleerbaar via CLI en database; de eerste melding op de telefoon komt in M2 (WP-17, WP-18). Operatormeldingen via GitHub. Aanbevolen M2-volgorde: WP-14 → WP-16 → WP-17 → WP-18 → WP-12 → WP-15. |
