# Blueprint WP-23: Privacy, toegankelijkheid en performance
Status: APPROVED
Revisie: 2

## Doel
De PWA klaarmaken voor anderen:
- **Privacy.** Een eerlijke privacypagina `/privacy` (gelinkt in de footer) en een inventaris `docs/PRIVACY.md` per tabel en per `localStorage`-sleutel, met bewaartermijnen die een test naast de implementatie legt. Een account kan zichzelf verwijderen met de RPC `delete_my_account()` en een knop met bevestiging op `/profiel`.
- **Afdwingen wat de browser mag.** `web/static/_headers` met een Content-Security-Policy die de browser alleen laat praten met de eigen origin, Supabase en MapTiler, `script-src 'self'` (plus de hash van het inline bootstrapscript van SvelteKit), een expliciete `Referrer-Policy`, en `X-Robots-Tag: noindex` voor `/s/*`.
- **Toegankelijkheid.** Automatische axe-core-tests op de hoofdpagina's, een compilercheck op a11y-waarschuwingen van Svelte, een contrasttest op alle kleuren in de CSS, een skiplink en focusbeheer bij het verwijderen.
- **Performance.** `scripts/check-bundle-size.mjs` met een budget voor de initiële JavaScript en voor de precache van de service worker, in CI. Lange cache voor `/_app/immutable/*`.

Na deze WP staat er niets meer open uit de "Gevolgen voor WP-23" van WP-12 t/m WP-21, behalve wat hieronder bewust buiten scope staat.

## Aannames
Voorstellen waar Lars op kan reageren staan als **Voorstel**.

- **A1. Eén migratie, als contract voor WP-22.** Account verwijderen vraagt een RPC (`auth.users` is niet via de API te bereiken). Deze WP voegt daarom één migratie toe (`supabase/migrations/20261016090000_delete_my_account.sql`) met alleen `delete_my_account()`, plus pgTAP-test `09_delete_my_account.test.sql` en een aanpassing van twee regels in `07_sessions.test.sql` (die test somt alle uitvoerbare en security-definerfuncties op). `ingest/` blijft ongewijzigd. Zie R8 voor de samenloop met WP-22 (`db_usage`).
- **A2. `web/static/_headers` is een sjabloon; de build vult het in.** De CSP moet de Supabase-URL (een build-variabele) en de sha256-hash van het inline bootstrapscript in `index.html` (verandert per build) bevatten. Dat kan een statisch bestand niet weten. Daarom:
  - `web/static/_headers` bevat twee placeholders: `{{SUPABASE_ORIGIN}}` en `{{SCRIPT_HASHES}}`;
  - `npm run build` wordt `vite build && node scripts/write-headers.mjs`; dat script schrijft `build/_headers` met de echte waarden;
  - `verify:build` controleert dat er in `build/_headers` geen placeholder meer staat en dat elk inline script van `build/index.html` met zijn hash in `script-src` staat.

  Cloudflare Pages bouwt met `cd web && npm ci && npm run build` (RUNBOOK §11) en pakt dit dus vanzelf op. AC-4 parseert het sjabloon `web/static/_headers`; `verify:build` doet dezelfde controles op het ingevulde bestand.
- **A3. Het scriptpad is `web/scripts/check-bundle-size.mjs`.** WORK_PACKAGES noemt `scripts/check-bundle-size.mjs` met `node scripts/check-bundle-size.mjs`. Dat commando werkt vanuit `web/`, net als `verify-build.mjs`; het script heeft de build in `web/build` nodig. De CI-stap is letterlijk `- run: node scripts/check-bundle-size.mjs` in de job `web` (working directory `web`). De orchestrator past het pad in WORK_PACKAGES aan.
- **A4. Voorstel: twee budgetten, in gzip-bytes (niveau 9), 1 kB = 1024 bytes.**
  - **Initiële JS ≤ 150 kB.** Dat is alle JavaScript die nodig is voordat een route rendert: de bestanden in `_app/immutable/entry/` (start, payload en app), de root-layout `_app/immutable/nodes/0.*.js`, en de statische import-afsluiting daarvan (`import … from`, `import "…"`, `export … from`). Dynamische `import()` telt niet mee, dus het MapLibre-chunk en de route-chunks niet. De `<link rel="modulepreload">`-lijst in `index.html` dient als kruiscontrole en telt mee (review N-3). Dit is "het entry-chunk, exclusief het kaart-chunk" uit de WP, nauwkeurig gedefinieerd: één bestand meten zegt weinig, omdat Vite de code over chunks verdeelt.
  - **Precache ≤ 900 kB.** Dat is alles wat de service worker bij installatie downloadt: alle bestanden onder `_app/immutable/`, de bestanden uit `static/` (zonder `_headers` en `_redirects`, zie A6) en `index.html`. Hier zit het MapLibre-chunk (±250 kB gzip) wel in.
  - De getallen zijn schattingen; ik kan niet bouwen. Schatting initiële JS: supabase-js ±55 kB, Svelte en SvelteKit ±30 kB, app-code in de layout ±15 kB, dus ±100 kB. Precache: MapLibre en zijn worker ±370 kB, de rest ±200 kB. De builder meet in stap 9 en schrijft de gemeten waarden in `docs/RUNBOOK.md`. Komt een meting boven een budget uit, dan verhoogt hij het budget **niet** zelf: hij noteert het in `deviations.md` en stopt (beslissing Lars).
- **A5. Het MapLibre-chunk blijft in de precache** (WP-15 A9, N-9). Eruit halen vraagt een oplossing voor oude chunknamen na een deploy (een `import()` op een chunk die niet meer bestaat). Het kost ±250 kB eenmalig per installatie per app-versie; het precachebudget van A4 bewaakt dat het niet ongemerkt groeit.
- **A6. Cloudflare serveert `_headers` niet als bestand.** Volgens de Cloudflare-docs wordt `_headers` "not itself be served as a static asset". De service worker precachet alle bestanden uit `static/` (`$app/manifest` `assets`). Een verzoek naar `/_headers` valt op Pages door naar de SPA-fallback: `index.html` met status 200, geen 404. `cache.addAll` faalt dus niet, maar zou `index.html` onder de sleutel `/_headers` in de cache zetten: een zinloze kopie die bij elke installatie opnieuw wordt gedownload, en een precachelijst die niet klopt met wat er echt bestaat. `precacheList` laat daarom `/_headers` en `/_redirects` weg, omdat het geen echte bestanden van de site zijn. Dit repareert geen bestaande bug (er staat nu geen `_headers` of `_redirects` in `static/`); stap 7 vóór stap 8 is genoeg.
- **A7. Voorstel: `style-src 'self' 'unsafe-inline'`.** `app.html` heeft `style="display: contents"`, en templates met `style="…"` worden door Svelte via template-HTML gemaakt. Zonder `'unsafe-inline'` blokkeert de browser die. Inline stijl kan geen script uitvoeren; de bescherming tegen XSS zit in `script-src`. De WP eist alleen `script-src 'self'` en de beperking van `connect-src`.
- **A8. Voorstel: `Referrer-Policy: strict-origin-when-cross-origin`** (de standaard van moderne browsers, nu expliciet). Bij verzoeken naar een andere origin gaat alleen de origin mee, nooit het pad. Zo lekt de slug van `/s/{slug}` niet naar Supabase, MapTiler of externe links. Niet `no-referrer`: de MapTiler-review (WP-15 N-2) kon niet bevestigen dat de origin-restrictie geen Referer nodig heeft. Deze keuze verandert niets ten opzichte van nu, dus de kaart kan er niet door op 403 lopen.
- **A9. Geen opruimronde over `shakka:rsvp:*` bij het starten** (voorstel van WP-21). Zonder datum in de waarde kan de app niet zien of een sessie weg is, behalve door per sleutel `get_public_session` aan te roepen. Een datum toevoegen verandert het opslagcontract van WP-21 (`{rsvp_id, edit_token}`, met een test die extra velden weert). De sleutel bevat geen naam, staat alleen op het eigen apparaat, en de aanmelding zelf is na de bewaartermijn op de server weg. De privacypagina zegt dit eerlijk en legt uit hoe je hem wist (browsergegevens wissen).
- **A10. Volgorde bij account verwijderen: eerst de RPC, dan pas uitloggen.** Faalt de RPC, dan blijft alles zoals het was (ook push). Lukt hij, dan roept de app `signOut()` uit `#lib/auth.js` aan. Die meldt eerst de push-subscription van dit apparaat af bij de browser (de databaserij is via de cascade al weg; `disablePush` vindt dan niets meer om te verwijderen en meldt toch af) en logt daarna lokaal uit. Daarna verdwijnen `shakka:organizer_name` en `shakka:return_to` uit `localStorage`. `shakka:rsvp:*` blijft staan: die hoort niet bij het account, en zonder de sleutel kan de gebruiker zich niet meer afmelden voor sessies van anderen.
- **A11. Na de verwijdering is het toegangstoken nog tot zijn verloop geldig** (maximaal 1 uur). PostgREST accepteert het dan nog, maar RLS geeft niets terug: er bestaat geen rij meer met die `user_id`, en inserts falen op de foreign key. supabase-js negeert bij `signOut` de fouten 401, 403 en 404 en verwijdert de lokale sessie toch (commentaar "ignore 404s since user might not exist anymore" in `GoTrueClient._signOut`). De builder controleert dat in stap 2 in `node_modules`; zie R7.
- **A12. Niet ingelogd → `PT401` met `not_authenticated`.** `anon` heeft geen `EXECUTE` (fout 42501, via REST 401). Een `authenticated`-token zonder `sub` kan in de praktijk niet, maar de functie weigert dan expliciet. Een tweede aanroep door een al verwijderde gebruiker is een no-op zonder fout.
- **A13. Feiten in de privacytekst die Lars bevestigt vóór AC-5 (zie "Nodig van Lars"):**
  - het Supabase-project draait in een EU-regio (de opdracht noemt "Supabase (EU)"; ik kan de regio niet zien);
  - in Supabase staat "Write audit logs to the database" (Authentication → Audit Logs) **uit**. Anders blijven inloglogs met IP-adres onbeperkt in `auth.audit_log_entries` staan, ook na het verwijderen van een account. Met de schakelaar uit gelden de bewaartermijnen van het gratis plan: API-logs 1 dag, auth-auditlogs 1 uur (supabase.com/pricing, gecontroleerd 15 oktober 2026);
  - Cloudflare Web Analytics staat uit voor het Pages-project;
  - de maildienst voor inloglinks is (nog) die van Supabase. Kiest Lars in WP-22 een eigen SMTP-dienst, dan werkt WP-22 de regel "De maildienst" op `/privacy` en in `docs/PRIVACY.md` bij.
- **A14. Voorstel: contactadres.** `PRIVACY_CONTACT_EMAIL` in `#lib/privacy.ts` is `null`. Dan toont de pagina "neem contact op met de beheerder van Shakka". Lars kiest een adres; dat is één regel code. Ik zet geen e-mailadres in een publieke repo zonder zijn akkoord.
- **A15. De privacytekst is een voorstel.** Hij noemt Lars Toutenhoofd als maker en beheerder (zijn naam staat al in de publieke git-geschiedenis). Lars keurt de tekst goed; wijzigingen in de tekst zijn geen ontwerpwijziging, zolang de tests van AC-5 blijven slagen.
- **A16. axe draait in jsdom zonder `color-contrast`.** jsdom heeft geen layout en geen canvas, dus die regel kan daar niets zeggen. Contrast wordt apart getoetst met een pure test op alle kleurparen in de CSS (`contrast.test.ts`) en op de echte site met Lighthouse (AC-6).
- **A17. Lighthouse heeft geen PWA-categorie meer** (verwijderd in Lighthouse 12, mei 2024). "De PWA is te installeren" (AC-6) toetst Lars in Chrome DevTools → Application → Manifest → "Installability" (geen fouten), en door Shakka op zijn telefoon op het beginscherm te zetten.
- **A18. Bronvermelding: golfmodellen expliciet** (WP-12 review N-9). De volledige `Attribution` krijgt "Weermodellen van KNMI, DWD, ECMWF en NOAA, en golfmodellen van DWD en ECMWF, via Open-Meteo." De compacte stand ("Modellen: KNMI, DWD, ECMWF, NOAA") dekt beide al en blijft gelijk.
- **A19. Opruimpunt `browserStorage`** (WP-20 en WP-21: "uiterlijk WP-23"). `rsvp-storage.ts` gebruikt voortaan `browserStorage()` uit `#lib/browser-storage.js` (`StorageLike | undefined`) en zijn functies accepteren `StorageLike | undefined` in plaats van `| null`. Het gedrag blijft gelijk. `formatWindowLocal` (compact) en `sessionWindowText` (voluit) blijven bewust twee functies (WP-20: "twee formaten voor twee doelen").
- **A20. Geen extra origins.** WP-12, WP-14, WP-16, WP-18, WP-20 en WP-21 voegen niets toe aan `connect-src`; Web Push, Web Share, het klembord en links naar WhatsApp en Tikkie zijn geen fetch-verzoeken. De enige externe origin naast Supabase is `MAP_EXTERNAL_ORIGINS` = `https://api.maptiler.com` (WP-15).
- **A21. `shakka:return_to` wordt ook zonder inloggen opgeruimd** (review B-1a). Nu wist alleen `takeReturnTo` de sleutel, en die draait pas als er een sessie is. Wie op dat apparaat nooit inlogt, houdt de sleutel onbeperkt. Nieuw is `pruneReturnTo(storage, nowMs)` in `local-prefs.ts`: die wist de sleutel tenzij hij een waarde bevat die `takeReturnTo` op dit moment zou accepteren (vers en toegestaan). De layout roept hem één keer aan bij elke app-start (`onMount`, vóór `initAuth`). Een verse waarde blijft staan, dus de terugkeer na inloggen werkt als voorheen. Een sleutel ouder dan 60 minuten verdwijnt bij de eerstvolgende start. Blijft de app langer dan 60 minuten open zonder inloggen, dan staat de sleutel er tot de volgende start, maar wordt hij niet meer gebruikt. De privacytekst beschrijft precies dat, zonder "hoogstens".
- **A22. Wat de uurlijkse job leest** (review B-1b). `jobs/alerts.py` en `jobs/push.py` lezen `profiles` (`PROFILE_COLUMNS`), `favorites`, `alert_rules`, `alert_state` en `push_subscriptions`. Ze schrijven `alert_state` en werken `push_subscriptions` bij (`last_success_at`; verwijderen bij 404/410). `/privacy` en `docs/PRIVACY.md` noemen dezelfde vijf gegevens. `privacy-page.test.ts` toetst beide formuleringen.
- **A23. Grondslag in één zin, als feitelijke tekst** (review N-7). De privacypagina krijgt een korte sectie "Waarom Shakka dit mag". Daarin staat: Shakka verwerkt de gegevens om de dienst te leveren die je zelf aanvraagt. Meldingen komen pas nadat je ze zelf aanzet. De logs zijn nodig om de dienst veilig te laten werken. Shakka gebruikt geen tracking, dus vraagt het niet om toestemming voor cookies. Dit is geen juridisch advies en valt onder het akkoord van Lars op de tekst (A15).
- **A24. Opslag die de browser of een library zelf beheert** (review N-8, gecontroleerd in `node_modules` van de WP-21-build):
  - SvelteKit 3 schrijft in `sessionStorage` de sleutels `sveltekit:history-info` (scrollpositie per history-item) en `sveltekit:snapshot` (leeg: Shakka gebruikt geen `export const snapshot`). `sessionStorage` verdwijnt als je het tabblad sluit. Bron: `@sveltejs/kit/src/runtime/client/constants.js` en `client.js`.
  - MapLibre GL JS 6.14.0 heeft geen tegelcache via de Cache API meer: in `maplibre-gl/dist` staat geen `caches.open` en geen `maplibre-tiles`. De tegelcache van MapLibre zit in het geheugen (`TileCache`). Kaarttegels, fonts en sprites van MapTiler kunnen wel in de gewone HTTP-cache van de browser komen, volgens de `Cache-Control` van MapTiler. Dat is browsercache en geen opslag door de app. De builder controleert dit in stap 5 opnieuw op de geïnstalleerde versie (zie daar).

## Ontwerp

**Account verwijderen.** De RPC `public.delete_my_account()` is `security definer` met `search_path = ''`, eigenaar `postgres`, en doet `delete from auth.users where id = auth.uid()`. Alle app-tabellen hangen met `on delete cascade` aan `auth.users`:
- `profiles`, `favorites` (en via `favorites` `alert_rules`), `alert_state` en `push_subscriptions`;
- `sessions` via `organizer_id`, en via `sessions` de `rsvps` van die sessies.

De auth-tabellen van Supabase (`identities`, `sessions`, `refresh_tokens`, MFA) hangen ook met een cascade aan `auth.users`. De Supabase-changelog van april 2025 beperkt in het `auth`-schema het maken en droppen van objecten, niet het verwijderen van rijen; de bestaande pgTAP-test `04_rls_users` doet al `delete from auth.users` als `postgres`.

In de web-app is `#lib/account.ts` de enige module die de RPC aanroept, met een time-out zoals `rsvp.ts`. `DeleteAccount.svelte` staat op `/profiel` onder het formulier, zichtbaar zodra je ingelogd bent, ook als je profiel niet laadt. De knop toont eerst een bevestiging met de gevolgen, en de focus gaat naar de vraag "Weet je het zeker?". Na succes toont de pagina een statusmelding en logt de app uit (A10).

**Privacy.** `#lib/privacy.ts` bevat de bewaartermijnen die de pagina toont. `retention-consistency.test.ts` leest de Python-bronnen (`timedelta(...)`) en de migratie (`interval '7 days'`) en vergelijkt die met deze constanten en met `SESSION_RETENTION_DAYS`. Gaat een termijn in de ingest omhoog, dan faalt de web-test en moet de tekst mee. `/privacy` is een statische pagina; de footer linkt ernaar. `/over`, `/login` en het RSVP-paneel krijgen een link. `docs/PRIVACY.md` is de technische inventaris voor beheer en review. `privacy-page.test.ts` legt de formuleringen die het snelst uit de pas lopen (de lijst van wat de uurlijkse job leest, en de bewaartermijn van `shakka:return_to`) zowel op `/privacy` als in `docs/PRIVACY.md` vast.

Om de tekst over `shakka:return_to` waar te maken, ruimt de layout bij elke app-start een verlopen sleutel op met `pruneReturnTo` (A21). Dat is een kleine, pure functie naast `takeReturnTo`, met dezelfde versheidsregel.

**Headers.** `web/static/_headers` (sjabloon) bevat drie regels: `/*` (CSP, referrer, nosniff, permissions), `/_app/immutable/*` (een jaar cache, `immutable`) en `/s/*` (`X-Robots-Tag: noindex`). `web/scripts/write-headers.mjs` doet drie dingen:
- het leest `PUBLIC_SUPABASE_URL` zoals Vite dat doet (`loadEnv('production', web, 'PUBLIC_')`; `process.env` gaat voor `.env`);
- het berekent de sha256 van elk inline `<script>` in `build/index.html`;
- het schrijft `build/_headers`.

De pure functies (`parseHeaders`, `parseCsp`, `checkHeaders`, `renderHeaders`, `inlineScriptHashes`) worden zowel in de tests als door `verify-build` gebruikt. Zo bestaat er één definitie van "een goede CSP". `verify-build` controleert ook dat de Supabase-origin uit de CSP in de gebouwde JS staat. Dan kunnen het env-bestand van het script en dat van SvelteKit niet uiteenlopen.

**Waarom niet de `csp`-optie van SvelteKit?** Die zet de policy als `<meta>` in geprerenderde pagina's. Voor de fallbackpagina van een SPA is dat niet gedocumenteerd, en `frame-ancestors` werkt niet in een `<meta>`. De hash zelf berekenen is controleerbaar (verify-build) en hangt niet af van interne werking van kit 3.

**Toegankelijkheid.** Drie lagen:
1. `a11y-compiler.test.ts` compileert elk `.svelte`-bestand met `svelte/compiler` en eist nul waarschuwingen met een code die begint met `a11y_`. Dat vangt statisch klikbare `div`'s, ontbrekende `alt`, labels zonder control, enzovoort.
2. `a11y-*.test.ts` rendert elke hoofdpagina met fixturedata in de relevante toestanden en draait axe-core op `document.body`. Violations met impact `serious` of `critical` laten de test falen.
3. `contrast.test.ts` rekent de WCAG-contrastverhouding uit voor elk kleurpaar uit de CSS. Een inventaris dwingt af dat elke nieuwe hexkleur in een paar of in de lijst "decoratief" komt.

Daarnaast komen er een skiplink ("Naar de inhoud") en `<main id="main" tabindex="-1">` in de layout. Gevonden overtredingen lost de builder op met kleine markup- of CSS-wijzigingen, zonder gedragswijziging; elke fix noemt hij in de commitboodschap.

**Performance.** `check-bundle-size.mjs` meet zoals A4 beschrijft, met pure functies die met een tijdelijke fixture-build te testen zijn. Een gezondheidscheck voorkomt dat de meting stil kapotgaat:
- er moeten entry-bestanden en een `nodes/0` zijn;
- de afsluiting moet supabase-js bevatten (de tekst `X-Client-Info`, een header-literal die niet geminificeerd wordt);
- de afsluiting mag het MapLibre-chunk niet bevatten.

`Cache-Control: public, max-age=31536000, immutable` op `/_app/immutable/*` voorkomt revalidatieverzoeken voor gehashte bestanden.

## Bestanden

| Pad | Actie | Inhoud |
|---|---|---|
| `supabase/migrations/20261016090000_delete_my_account.sql` | aanmaken | Functie, revoke en grant (exact, zie Interfaces). |
| `supabase/tests/09_delete_my_account.test.sql` | aanmaken | pgTAP, 23 asserties (zie Testplan). |
| `supabase/tests/07_sessions.test.sql` | wijzigen | Alleen regels 67 en 69 (zie Interfaces). |
| `web/package.json`, `web/package-lock.json` | wijzigen | `npm install -D axe-core@^4.14.0`; scripts `build` en `size` (zie Interfaces). |
| `web/src/lib/account.ts` | aanmaken | `ACCOUNT_MESSAGES`, `ACCOUNT_RPC_TIMEOUT_MS`, `deleteMyAccount`, `cleanUpAfterAccountDeletion`, `clearAccountLocalData`. |
| `web/src/lib/privacy.ts` | aanmaken | Bewaartermijnen, contact, datum. |
| `web/src/lib/components/DeleteAccount.svelte` | aanmaken | Sectie met bevestiging. |
| `web/src/routes/privacy/+page.svelte` | aanmaken | Privacypagina (tekst exact, zie Interfaces). |
| `web/src/routes/profiel/+page.svelte` | wijzigen | `accountDeleted`, statusmelding, `DeleteAccount`. |
| `web/src/routes/+layout.svelte` | wijzigen | Skiplink, `id`/`tabindex` op `main`, link "Privacy" in de footer, `pruneReturnTo` in `onMount` (A21). |
| `web/src/lib/local-prefs.ts` | wijzigen | Interne helper `freshReturnPath`, nieuwe export `pruneReturnTo`; `takeReturnTo` gebruikt de helper, gedrag gelijk (A21). |
| `web/test/local-prefs.test.ts` | wijzigen | Tests voor `pruneReturnTo` (zie Testplan). |
| `web/src/routes/over/+page.svelte` | wijzigen | Link naar `/privacy` in "Geen advertenties, geen tracking". |
| `web/src/routes/login/+page.svelte` | wijzigen | Eén hint met link naar `/privacy` onder het formulier. |
| `web/src/lib/components/RsvpPanel.svelte` | wijzigen | Link "Meer over privacy" in de hint `#rsvp-privacy` (stap 4), en de import van `browserStorage` uit `#lib/browser-storage.js` (stap 10, A19). |
| `web/src/lib/components/Attribution.svelte` | wijzigen | Tweede alinea van de volledige stand (A18). |
| `web/src/app.css` | wijzigen | `.skip-link`, `main:focus`, `.danger`, `.delete-account`. |
| `web/src/lib/sw/shell.ts` | wijzigen | `PRECACHE_EXCLUDED_PATHS`; `precacheList` filtert die. |
| `web/src/lib/rsvp-storage.ts` | wijzigen | A19: eigen `browserStorage` weg, `null` wordt `undefined`. |
| `web/src/routes/s/[slug]/+page.svelte` | wijzigen | A19: `browserStorage` uit `#lib/browser-storage.js`. |
| `web/static/_headers` | aanmaken | Sjabloon (exact, zie Interfaces). |
| `web/scripts/write-headers.mjs` | aanmaken | Pure functies plus `main()`. |
| `web/scripts/check-bundle-size.mjs` | aanmaken | Pure functies plus `main()`. |
| `web/scripts/verify-build.mjs` | wijzigen | Export `checkBuiltHeaders(buildDir)` en aanroep in `main()`. |
| `.github/workflows/ci.yml` | wijzigen | In job `web` na `- run: npm run verify:build` de stap `- run: node scripts/check-bundle-size.mjs`. |
| `web/test/helpers/axe.ts` | aanmaken | `AXE_OPTIONS`, `seriousViolations`, `expectNoSeriousViolations`. |
| `web/test/helpers/contrast.ts` | aanmaken | `hexToRgb`, `relativeLuminance`, `contrastRatio`. |
| `web/test/a11y-layout.test.ts`, `a11y-home.test.ts`, `a11y-spot.test.ts`, `a11y-public-session.test.ts`, `a11y-profile.test.ts`, `a11y-alerts.test.ts`, `a11y-login.test.ts`, `a11y-static-pages.test.ts`, `a11y-session-pages.test.ts` | aanmaken | axe per pagina (zie Testplan). |
| `web/test/a11y-compiler.test.ts`, `contrast.test.ts`, `account.test.ts`, `delete-account.test.ts`, `privacy-page.test.ts`, `retention-consistency.test.ts`, `headers.test.ts`, `bundle-size.test.ts` | aanmaken | Zie Testplan. |
| `web/test/profile-page.test.ts`, `layout.test.ts`, `attribution.test.ts`, `over.test.ts`, `sw-shell.test.ts`, `verify-build.test.ts`, `user-tables.test.ts`, `rsvp-storage.test.ts` | wijzigen | Zie Testplan. `user-tables.test.ts`: `RPC_FILES = ['lib/rsvp.ts', 'lib/account.ts']`. `profile-page.test.ts` krijgt een mock van `#lib/account.js` (zie Testplan). |
| `docs/PRIVACY.md` | aanmaken | Inventaris (inhoud zie Interfaces). |
| `docs/RUNBOOK.md` | wijzigen | Nieuwe sectie "Privacy, CSP en performance (vanaf WP-23)" (zie Interfaces). |

Niet gewijzigd: `ingest/`, de bestaande migraties, `vite.config.ts`, `src/env.ts`, `src/service-worker/index.ts` (de filter zit in `precacheList`), `supabase/config.toml`. `docs/STATUS.md` en `docs/WORK_PACKAGES.md` werkt de orchestrator bij.

## Interfaces en contracten

### Migratie `supabase/migrations/20261016090000_delete_my_account.sql` (exact)
```sql
-- Self-service account deletion (WP-23). Deleting the auth.users row removes every row that belongs
-- to the account through the existing on-delete-cascade foreign keys: profiles, favorites (and with
-- them alert_rules), alert_state, push_subscriptions, and the sessions the user organizes together
-- with the RSVPs on those sessions. Anonymous RSVPs the user made elsewhere are not linked to the
-- account and are not touched.

create function public.delete_my_account()
returns void
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_uid uuid := auth.uid();
begin
  if v_uid is null then
    raise sqlstate 'PT401' using message = 'not_authenticated';
  end if;
  delete from auth.users where id = v_uid;
end;
$$;

revoke all on function public.delete_my_account() from public, anon, authenticated, service_role;
grant execute on function public.delete_my_account() to authenticated;
```
Er staan bewust geen namen van de sessie-RPC's in dit bestand, en geen `alter table … rsvps`: `rsvp-contract.test.ts` weert die in latere migraties.

### `supabase/tests/07_sessions.test.sql` (alleen deze twee regels)
- Regel 67 wordt:
  ```sql
  select set_eq($$select p.proname::text from pg_proc p where p.pronamespace = 'public'::regnamespace and has_function_privilege('authenticated', p.oid, 'EXECUTE')$$, $$values ('get_public_session'), ('rsvp_create'), ('rsvp_update'), ('rsvp_delete'), ('delete_my_account')$$, 'authenticated can execute exactly the four public RPCs and delete_my_account');
  ```
- Regel 69 wordt:
  ```sql
  select set_eq($$select p.proname::text from pg_proc p where p.pronamespace = 'public'::regnamespace and p.prosecdef$$, $$values ('handle_new_user'), ('get_public_session'), ('rsvp_create'), ('rsvp_update'), ('rsvp_delete'), ('purge_expired_sessions'), ('delete_my_account')$$, 'security definer functions in public');
  ```
- Het `plan(...)`-getal blijft gelijk.

### Contract RPC
- `delete_my_account() returns void`, `EXECUTE` alleen voor `authenticated`.
- Aanroep: `supabase.rpc('delete_my_account')`, een POST zonder argumenten. Succes: `error === null` (PostgREST 204, `data` is `null`).
- Fouten:
  - `PT401` / `not_authenticated` (HTTP 401) bij een token zonder `sub`;
  - `42501` (HTTP 401 via REST) voor `anon`.

### `web/src/lib/account.ts`
```ts
import type { StorageLike } from './browser-storage.js';

export const ACCOUNT_RPC_TIMEOUT_MS = 15_000;

export const ACCOUNT_MESSAGES = {
	failed: 'Je account is niet verwijderd: er ging iets mis. Probeer het later opnieuw.',
	network: 'Je account is niet verwijderd: geen verbinding met de server. Probeer het opnieuw.',
	deleted: 'Je account en alle gegevens die eraan vastzaten, zijn verwijderd. Je bent uitgelogd.'
} as const;

/** Keys in localStorage that belong to the signed-in user (WP-20). shakka:rsvp:* stays (A10). */
export const ACCOUNT_LOCAL_KEYS: readonly string[]; // [ORGANIZER_NAME_KEY, RETURN_TO_KEY] from ./local-prefs.js

export type DeleteAccountResult = { ok: true } | { ok: false; error: string };

/** Calls the delete_my_account RPC (POST, no arguments) with AbortSignal.timeout(ACCOUNT_RPC_TIMEOUT_MS)
 *  when available. Never throws, never logs server text.
 *  - resolved with error === null      -> { ok: true }
 *  - thrown, or status === 0           -> { ok: false, error: ACCOUNT_MESSAGES.network }
 *  - any other error                   -> { ok: false, error: ACCOUNT_MESSAGES.failed }
 *  On failure: one console.warn('account delete failed') without details. */
export function deleteMyAccount(): Promise<DeleteAccountResult>;

/** Removes ACCOUNT_LOCAL_KEYS. Ignores undefined storage and storage errors. Never throws. */
export function clearAccountLocalData(storage: StorageLike | undefined): void;

/** After a successful deletion: await signOut() from #lib/auth.js (releases this device's push
 *  subscription, then local sign-out; never throws), then clearAccountLocalData(storage). Never throws. */
export function cleanUpAfterAccountDeletion(storage: StorageLike | undefined): Promise<void>;
```
- Imports: `supabase` uit `#lib/supabase.js` en `signOut` uit `#lib/auth.js`, plus `ORGANIZER_NAME_KEY` en `RETURN_TO_KEY` uit `./local-prefs.js`.
- De RPC-aanroep volgt hetzelfde patroon als `call()` in `rsvp.ts`: `supabase.rpc('delete_my_account')`, dan `.abortSignal(AbortSignal.timeout(…))` als dat bestaat.
- `cleanUpAfterAccountDeletion` vangt een eventuele throw van `signOut` op en wist de sleutels daarna toch.

### `web/src/lib/components/DeleteAccount.svelte`
Props: `let { ondeleted }: { ondeleted: () => void } = $props();`

Toestand: `mode = $state<'idle' | 'confirm'>('idle')`, `busy = $state(false)`, `error = $state<string | null>(null)`.

Markup (exact):
```svelte
<section class="delete-account" aria-labelledby="delete-account-heading">
	<h2 id="delete-account-heading">Account verwijderen</h2>
	{#if mode === 'idle'}
		<p>
			Hiermee verwijder je je account en alle gegevens die eraan vastzitten. In de
			<a href="/privacy">privacyverklaring</a> staat precies welke.
		</p>
		<button type="button" bind:this={askButton} onclick={ask}>Account verwijderen…</button>
	{:else}
		<div class="banner warning" role="group" aria-labelledby="delete-confirm-title">
			<p id="delete-confirm-title" tabindex="-1" bind:this={confirmTitle}><strong>Weet je het zeker?</strong></p>
			<p>
				Dit verwijdert direct en definitief: je e-mailadres en login, je profiel, je favorieten en
				alertinstellingen, de meldingen op al je apparaten, en de sessies die je organiseert, met de
				aanmeldingen van anderen daarvoor. Dit kun je niet ongedaan maken.
			</p>
			<button type="button" class="danger" disabled={busy} onclick={confirm}>
				{busy ? 'Bezig met verwijderen…' : 'Ja, verwijder mijn account'}
			</button>
			<button type="button" disabled={busy} onclick={cancel}>Annuleren</button>
		</div>
	{/if}
	{#if error}<p class="error" role="alert">{error}</p>{/if}
</section>
```
Gedrag:
- `ask()`: `error = null; mode = 'confirm'; await tick(); confirmTitle?.focus()`.
- `cancel()`: `mode = 'idle'; await tick(); askButton?.focus()`.
- `confirm()`:
  1. doe niets als `busy`; anders `busy = true; error = null`;
  2. `const r = await deleteMyAccount()`;
  3. bij `!r.ok`: `error = r.error; busy = false`, en de bevestiging blijft open;
  4. bij `r.ok`: `ondeleted()`, gevolgd door `await cleanUpAfterAccountDeletion(browserStorage())` (`browserStorage` uit `#lib/browser-storage.js`). Na `ondeleted()` wordt het component meestal ontmanteld; daarna schrijft de functie geen state meer.

### `web/src/routes/profiel/+page.svelte` (wijziging)
- Script: `import DeleteAccount from '#lib/components/DeleteAccount.svelte'`, `import { ACCOUNT_MESSAGES } from '#lib/account.js'`, en `let accountDeleted = $state(false)`.
- De bestaande `{#if $session === undefined} … {/if}`-keten krijgt een nieuwe eerste tak:
  ```svelte
  {#if accountDeleted}
  	<p role="status">{ACCOUNT_MESSAGES.deleted}</p>
  	<p><a href="/">Naar de start</a></p>
  {:else if $session === undefined}
  	… (ongewijzigd)
  {/if}
  ```
- Direct na die keten:
  ```svelte
  {#if $session && !accountDeleted}
  	<DeleteAccount ondeleted={() => (accountDeleted = true)} />
  {/if}
  ```

### `web/src/lib/local-prefs.ts` (wijziging, A21)
```ts
/** Path from a raw stored value when it parses as {path: string, saved_at: number}, its age
 *  (nowMs - saved_at) is within 0..RETURN_TO_TTL_MS, and isAllowedReturnPath(path). Else null. Never throws.
 *  Not exported. */
function freshReturnPath(raw: string | null, nowMs: number): string | null;

/** Reads and ALWAYS removes the key. Returns freshReturnPath(raw, nowMs). (Behaviour unchanged.) */
export function takeReturnTo(storage: StorageLike | undefined, nowMs: number): string | null;

/** Removes RETURN_TO_KEY unless freshReturnPath(stored value, nowMs) is not null. Missing key: no-op.
 *  Returns true when it removed the key. undefined storage or storage errors: false. Never throws. */
export function pruneReturnTo(storage: StorageLike | undefined, nowMs: number): boolean;
```
- `takeReturnTo` houdt exact zijn huidige volgorde: eerst lezen, dan altijd verwijderen, dan `freshReturnPath`. De bestaande tests in `local-prefs.test.ts` en `layout.test.ts` blijven ongewijzigd groen.
- Geen nieuwe imports: `session-tables.test.ts` rekent `local-prefs.ts` tot de pure modules.

`+layout.svelte`, in `onMount`, als eerste regel:
```ts
pruneReturnTo(browserStorage(), Date.now());
```
De import wordt `import { pruneReturnTo, takeReturnTo } from '#lib/local-prefs.js';`. Het `$effect` met `takeReturnTo` blijft gelijk. De volgorde ten opzichte van dat effect maakt niet uit: een verse sleutel laat `pruneReturnTo` staan, een verlopen sleutel zou `takeReturnTo` ook weigeren.

### `web/src/lib/privacy.ts` (exact)
```ts
import { RETURN_TO_TTL_MS } from './local-prefs.js';

// Retention periods shown on /privacy. test/retention-consistency.test.ts compares them with the ingest
// (Python timedelta constants) and the sessions migration. Change the implementation and this file together.
export const FORECAST_RETENTION_HOURS = 48; // forecast_hours, marine_hours, tide_extremes, evaluations
export const ALERT_STATE_RETENTION_HOURS = 48; // alert_state rows, counted from window_end
export const RETURN_TO_TTL_MINUTES = RETURN_TO_TTL_MS / 60_000; // shakka:return_to

// Supabase Free plan log retention (supabase.com/pricing, checked 2026-10-15). Valid only when
// "Write audit logs to the database" is off (docs/PRIVACY.md, RUNBOOK).
export const SUPABASE_API_LOG_RETENTION_NL = '1 dag';
export const SUPABASE_AUTH_LOG_RETENTION_NL = '1 uur';

/** Contact address for privacy questions; null until Lars chooses one (blueprint A14). */
export const PRIVACY_CONTACT_EMAIL: string | null = null;

/** Date of the current privacy text, Dutch long format. */
export const PRIVACY_UPDATED_NL = '<datum van stap 4, bijv. 16 oktober 2026>';
```
De builder vult `PRIVACY_UPDATED_NL` in met de datum waarop hij stap 4 uitvoert, in de vorm "16 oktober 2026".

### `web/src/routes/privacy/+page.svelte` (tekst exact; `{…}` = constante)
Imports: de constanten uit `#lib/privacy.js` en `SESSION_RETENTION_DAYS` uit `#lib/rsvp-types.js`. Alle externe links krijgen `target="_blank" rel="noopener noreferrer"`.

```svelte
<svelte:head><title>Privacy · Shakka</title></svelte:head>

<h1>Privacy</h1>
<p class="muted">Laatst bijgewerkt: {PRIVACY_UPDATED_NL}</p>
<p>
	Shakka is een gratis app zonder advertenties, gemaakt en beheerd door Lars Toutenhoofd. Shakka
	bewaart zo weinig mogelijk over jou. Hieronder staat wat, waarom, hoe lang, en hoe je het weghaalt.
</p>

<h2>Kort</h2>
<ul>
	<li>Geen advertenties, geen analytics, geen trackers. Shakka zet zelf geen cookies.</li>
	<li>Shakka vraagt nooit om je locatie.</li>
	<li>De weerdata komt van de server van Shakka. Je browser praat nooit met Open-Meteo.</li>
	<li>Je account en alles wat eraan vastzit, verwijder je zelf op je <a href="/profiel">profielpagina</a>.</li>
</ul>

<h2>Waarom Shakka dit mag</h2>
<p>
	Shakka verwerkt deze gegevens om de dienst te leveren die je zelf aanvraagt: inloggen, je alerts,
	meldingen, en de sessies die je organiseert of waarvoor je je aanmeldt. Meldingen krijg je pas als
	je ze zelf aanzet. De logs bij Supabase en Cloudflare zijn nodig om de dienst veilig te laten werken.
	Shakka gebruikt geen tracking en vraagt daarom niet om toestemming voor cookies.
</p>

<h2>Wat Shakka bewaart als je inlogt</h2>
<ul>
	<li>
		<strong>E-mailadres</strong>, om je een inloglink te sturen en je te herkennen. Supabase, de
		database- en inlogdienst van Shakka, bewaart daarbij wanneer je account is gemaakt en wanneer je
		voor het laatst inlogde, en per ingelogd apparaat technische gegevens zoals het tijdstip, je
		IP-adres en je browser. Tot je je account verwijdert.
	</li>
	<li>
		<strong>Profiel</strong>, alles optioneel: je gewicht, niveau, kitematen en standaard windgrenzen.
		Voor het kite-advies en je alerts. Tot je het aanpast of je account verwijdert.
	</li>
	<li>
		<strong>Favorieten en alertinstellingen</strong>: welke spots, en per spot je windgrenzen,
		windrichtingen, dagen en tijden. Tot je ze weghaalt of je account verwijdert.
	</li>
	<li>
		<strong>Verstuurde alerts</strong>: per spot en tijdvak wat je laatste melding was, zodat je niet
		twee keer hetzelfde krijgt. Verdwijnt {ALERT_STATE_RETENTION_HOURS} uur na het einde van het tijdvak.
	</li>
	<li>
		<strong>Push-abonnementen</strong>: per apparaat waarop je meldingen aanzet, een adres en sleutels
		van de pushdienst van je browser. Verdwijnt als je meldingen uitzet, als je uitlogt, als de
		pushdienst meldt dat het adres niet meer werkt, of als je je account verwijdert.
	</li>
	<li>
		<strong>Sessies die je organiseert</strong>: je voornaam, de spot, het tijdvak, en wat je verder
		invult (notitie, vertrekpunt, vrije plekken, Tikkie-link). Iedereen met de link kan dit zien.
		Verdwijnt {SESSION_RETENTION_DAYS} dagen na het einde van de sessie, of eerder als je je account
		verwijdert.
	</li>
</ul>

<h2>Als je je aanmeldt voor een sessie</h2>
<p>
	Voor "Ik ook" heb je geen account nodig. Shakka bewaart dan alleen je <strong>voornaam</strong> en
	je keuze voor vervoer: eigen vervoer, een lift zoeken of plekken aanbieden, en met wie je meerijdt.
	Iedereen met de link kan dit zien. Het verdwijnt als je je afmeldt, en anders
	{SESSION_RETENTION_DAYS} dagen na het einde van de sessie. In de database van Shakka staat geen
	e-mailadres of IP-adres bij je aanmelding.
</p>

<h2>Weerdata</h2>
<p>
	Verwachtingen, getij en oordelen per spot zijn geen persoonsgegevens. Shakka bewaart ze tot
	{FORECAST_RETENTION_HOURS} uur na het uur waar ze over gaan.
</p>

<h2>Op je eigen apparaat</h2>
<p>
	Een paar dingen staan in de opslag van je browser (localStorage). Ze blijven op je apparaat. Je
	wist ze met "Websitegegevens wissen" in je browser.
</p>
<ul>
	<li>Je inlogsessie. Verdwijnt als je uitlogt.</li>
	<li>De voornaam die je als organisator invulde, zodat je hem niet opnieuw hoeft te typen.</li>
	<li>
		Na "Ik ga" als je nog niet bent ingelogd: de spot en het tijdvak, zodat je na het inloggen verder
		kunt. Dit wordt gewist zodra je inlogt. Log je niet in, dan gebruikt Shakka het na
		{RETURN_TO_TTL_MINUTES} minuten niet meer, en wist het de eerstvolgende keer dat je Shakka opent.
	</li>
	<li>
		Per sessie waarvoor je je aanmeldde: een code waarmee je je aanmelding kunt wijzigen of
		afmelden. Die verdwijnt als je je afmeldt, of als je de sessiepagina opent nadat de sessie is
		verwijderd. Anders blijft hij staan tot je je browsergegevens wist; je aanmelding zelf is dan al
		verwijderd.
	</li>
	<li>De bestanden van de app zelf, zodat Shakka ook offline opent. Daarin staat niets over jou.</li>
</ul>
<p>
	Daarnaast houdt je browser zelf een paar dingen bij, zoals bij elke website: per tabblad de
	scrollpositie (verdwijnt als je het tabblad sluit), en in de gewone browsercache bijvoorbeeld
	kaarttegels van MapTiler. Shakka slaat daar zelf niets in op.
</p>

<h2>Wie er nog meer iets ziet</h2>
<ul>
	<li>
		<strong>Supabase</strong> host de database en het inloggen, in een datacenter in de EU. Verzoeken
		van de app worden daar gelogd, onder andere met je IP-adres, en {SUPABASE_API_LOG_RETENTION_NL}
		bewaard. Inloglogs worden {SUPABASE_AUTH_LOG_RETENTION_NL} bewaard.
	</li>
	<li>
		<strong>Cloudflare</strong> host de app en ziet daarbij je IP-adres, om de pagina's te kunnen
		leveren. Shakka gebruikt geen analytics van Cloudflare.
	</li>
	<li>
		<strong>GitHub</strong> draait elk uur de berekening van oordelen en alerts. Die leest daarvoor je
		profiel, favorieten, alertinstellingen, push-abonnementen en welke alerts je al kreeg. In de logs
		komen geen persoonsgegevens.
	</li>
	<li>
		<strong>De pushdienst van je browser</strong> (bijvoorbeeld van Apple, Google, Mozilla of
		Microsoft) bezorgt je meldingen. De inhoud is versleuteld; de pushdienst ziet wel dat er een
		melding naar je apparaat gaat.
	</li>
	<li>
		<strong>MapTiler</strong> levert de kaart. Pas als je op "Kaart" tikt, haalt je browser kaartdata
		op bij MapTiler. MapTiler ziet dan je IP-adres, je browser en dat je van Shakka komt (het domein,
		niet de pagina). Zonder kaart praat je browser niet met MapTiler.
	</li>
	<li>
		<strong>De maildienst</strong> die de inloglink verstuurt, krijgt je e-mailadres. Nu is dat
		Supabase zelf.
	</li>
	<li>
		Links naar andere sites (bronnen, WhatsApp, Tikkie) openen die sites. Shakka stuurt daarbij niet
		mee van welke pagina je komt.
	</li>
	<li>De beheerder heeft technisch toegang tot de database, om problemen op te lossen.</li>
</ul>

<h2>Account verwijderen</h2>
<p>
	Op je <a href="/profiel">profielpagina</a> staat "Account verwijderen". Shakka verwijdert dan direct
	en definitief: je e-mailadres en login, je profiel, favorieten, alertinstellingen, verstuurde
	alerts, de push-abonnementen van al je apparaten, en de sessies die je organiseert, met de
	aanmeldingen daarvoor. Aanmeldingen die je zonder account bij sessies van anderen deed, hangen niet
	aan je account: meld je af op de sessiepagina, of ze verdwijnen {SESSION_RETENTION_DAYS} dagen na
	de sessie. Logs bij Supabase verlopen vanzelf (zie hierboven). Wat Cloudflare als hostingdienst
	bijhoudt, valt onder het privacybeleid van Cloudflare.
</p>

<h2>Je rechten</h2>
<p>
	Je mag weten welke gegevens Shakka over je heeft, en je mag ze laten verbeteren of verwijderen. Het
	meeste kun je zelf in de app.
	{#if PRIVACY_CONTACT_EMAIL}
		Vragen of een verzoek? Mail naar <a href={`mailto:${PRIVACY_CONTACT_EMAIL}`}>{PRIVACY_CONTACT_EMAIL}</a>.
	{:else}
		Vragen of een verzoek? Neem contact op met de beheerder van Shakka.
	{/if}
	Ben je het niet eens met hoe Shakka met je gegevens omgaat, dan kun je een klacht indienen bij de
	<a href="https://autoriteitpersoonsgegevens.nl/" target="_blank" rel="noopener noreferrer">Autoriteit Persoonsgegevens</a>.
</p>
```

### Kleine tekstwijzigingen
- `+layout.svelte`:
  - als eerste element: `<a class="skip-link" href="#main">Naar de inhoud</a>`;
  - `<main>` wordt `<main id="main" tabindex="-1">`;
  - de footerregel wordt `<p><a href="/over">Over Shakka en bronnen</a> · <a href="/privacy">Privacy</a></p>`.
- `/over`: de alinea onder "Geen advertenties, geen tracking" wordt `<p>Shakka heeft geen advertenties en gebruikt geen analytics of trackers van derden. Lees de <a href="/privacy">privacyverklaring</a>.</p>`.
- `/login`, in de `{:else}`-tak direct na `</form>`: `<p class="hint">Shakka gebruikt je e-mailadres alleen om je in te loggen. <a href="/privacy">Privacy</a></p>`.
- `RsvpPanel.svelte`: in `#rsvp-privacy`, na "…op dit apparaat.", de tekst ` <a href="/privacy">Meer over privacy</a>`.
- `Attribution.svelte`, volledige stand, tweede `<p>`: `Weermodellen van [KNMI], [DWD], [ECMWF] en [NOAA], en golfmodellen van [DWD] en [ECMWF], via Open-Meteo.` (bestaande `link`-snippet; de compacte stand blijft gelijk).

### `web/src/app.css` (toevoegen aan het eind)
```css
/* WP-23: accessibility and account deletion */
.skip-link { position: absolute; left: -9999px; top: 0; }
.skip-link:focus { left: 1rem; top: 0.5rem; z-index: 10; padding: 0.5rem 0.75rem; background: #fff; color: #1a1a1a; }
main:focus:not(:focus-visible) { outline: none; }
.delete-account { margin-top: 2rem; padding-top: 0.75rem; border-top: 1px solid #ddd; }
.delete-account h2 { font-size: 1.1rem; margin: 0 0 0.25rem; }
.danger { background: #a4161a; color: #fff; border: 1px solid #a4161a; padding: 0.25rem 0.75rem; border-radius: 0.25rem; }
```

### `web/src/lib/sw/shell.ts` (wijziging)
```ts
/** Host configuration files in static/ that Cloudflare Pages never serves as files. A request for them gets
 *  the SPA fallback (index.html, 200), so precaching them would store a useless copy of index.html. */
export const PRECACHE_EXCLUDED_PATHS: readonly string[] = ['/_headers', '/_redirects'];

/** Unique list of absolute paths to precache, without PRECACHE_EXCLUDED_PATHS, always including shellPath.
 *  Order: input order, shell last if new. */
export function precacheList(paths: readonly string[], shellPath: string): string[];
```

### `web/static/_headers` (exact)
```
# Cloudflare Pages response headers (WP-23). This file is a template: `npm run build` runs
# scripts/write-headers.mjs, which writes build/_headers with the two placeholders (Supabase origin,
# inline script hashes) filled in. Never put secrets here. Checked by test/headers.test.ts and verify-build.
/*
  Content-Security-Policy: default-src 'self'; script-src 'self' {{SCRIPT_HASHES}}; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob: https://api.maptiler.com; font-src 'self'; connect-src 'self' {{SUPABASE_ORIGIN}} https://api.maptiler.com; worker-src 'self'; manifest-src 'self'; frame-src 'none'; frame-ancestors 'none'; object-src 'none'; base-uri 'self'; form-action 'self'
  Referrer-Policy: strict-origin-when-cross-origin
  X-Content-Type-Options: nosniff
  Permissions-Policy: camera=(), microphone=(), geolocation=(), payment=(), usb=()
/_app/immutable/*
  Cache-Control: public, max-age=31536000, immutable
/s/*
  X-Robots-Tag: noindex
```
Inspringing: twee spaties. Elke regel is korter dan 2.000 tekens (limiet van Cloudflare). De placeholders `{{SUPABASE_ORIGIN}}` en `{{SCRIPT_HASHES}}` staan alleen in de CSP-regel, niet in het commentaar.

### `web/scripts/write-headers.mjs`
```js
export const PLACEHOLDER_SUPABASE = '{{SUPABASE_ORIGIN}}';
export const PLACEHOLDER_SCRIPTS = '{{SCRIPT_HASHES}}';
export const MAX_LINE = 2000;
export const ANALYTICS_MARKERS = ['google-analytics', 'googletagmanager', 'doubleclick', 'plausible', 'matomo',
	'posthog', 'segment', 'mixpanel', 'hotjar', 'cloudflareinsights', 'clarity.ms', 'facebook'];

/** Rules in file order. Blank lines and lines starting with '#' are skipped. A line without leading
 *  whitespace starts a rule (pattern = trimmed line). An indented line is 'Name: value' (split at the first ': ').
 *  @param {string} text @returns {{ pattern: string, headers: [string, string][] }[]} */
export function parseHeaders(text);

/** 'a b; c d e' -> Map { 'a' => ['b'], 'c' => ['d','e'] }. Directive names lower-cased; empty parts skipped.
 *  @param {string} value @returns {Map<string, string[]>} */
export function parseCsp(value);

/** "'sha256-<base64>'" for every <script> without a src attribute, hash over the exact text between the tags (UTF-8).
 *  Regex: /<script\b(?![^>]*\bsrc\s*=)[^>]*>([\s\S]*?)<\/script>/gi
 *  @param {string} html @returns {string[]} */
export function inlineScriptHashes(html);

/** Same rules as parseSupabaseUrl in src/lib/env-schema.ts; returns url.origin. Messages never contain the value.
 *  @param {string | undefined} value @returns {string} */
export function supabaseOrigin(value);

/** Replaces every occurrence of both placeholders with String.prototype.replaceAll (hashes joined by one
 *  space), collapses runs of spaces inside header values, and throws
 *  Error('unresolved placeholder in _headers') if '{{' remains anywhere in the text (comments included).
 *  @param {string} template @param {{ supabaseOrigin: string, scriptHashes: string[] }} values @returns {string} */
export function renderHeaders(template, values);

/** Problems (empty = ok). template: placeholders are expected (true) or forbidden (false).
 *  @param {string} text @param {{ template: boolean }} opts @returns {string[]} */
export function checkHeaders(text, opts);
```
`checkHeaders` geeft een probleem als:
1. een regel langer is dan `MAX_LINE`;
2. er geen regel `/*` is, of die geen `Content-Security-Policy` heeft, of er meer dan één regel met een CSP is;
3. in de CSP:
   - `connect-src` ontbreekt, of mist `'self'` of `https://api.maptiler.com`;
   - bij `template: true` mist `connect-src` `{{SUPABASE_ORIGIN}}`; bij `template: false` mist hij een `https://`- of `http://`-bron naast MapTiler;
   - een bron in welke directive dan ook `*` bevat;
   - een bron (case-insensitive) `open-meteo` bevat;
   - een bron een van de `ANALYTICS_MARKERS` bevat;
   - `script-src` andere bronnen heeft dan `'self'`, `'sha256-…'` (regex `^'sha256-[A-Za-z0-9+/]+={0,2}'$`) of (alleen bij `template: true`) `{{SCRIPT_HASHES}}`;
   - `img-src` `https://api.maptiler.com` mist;
   - `default-src`, `object-src`, `base-uri` of `frame-ancestors` ontbreekt;
4. `/*` geen `Referrer-Policy: strict-origin-when-cross-origin` heeft;
5. er geen regel `/s/*` is met `X-Robots-Tag: noindex`;
6. bij `template: false` er nog `{{` in de tekst staat.

`main()`:
- `WEB_ROOT = join(dirname(fileURLToPath(import.meta.url)), '..')`, net als in `verify-build.mjs`;
- args: `--template <pad>` (standaard `<WEB_ROOT>/static/_headers`), `--build <dir>` (standaard `<WEB_ROOT>/build`). Relatieve paden in args worden opgelost vanaf `process.cwd()`;
- `const { loadEnv } = await import('vite')`; `env = loadEnv('production', WEB_ROOT, 'PUBLIC_')`;
- `origin = supabaseOrigin(env.PUBLIC_SUPABASE_URL)`;
- lees `<build>/index.html`. Ontbreekt dat, dan `write-headers: build/index.html is missing` en exit 1;
- `text = renderHeaders(template, { supabaseOrigin: origin, scriptHashes: inlineScriptHashes(html) })`;
- `problems = checkHeaders(text, { template: false })`. Niet leeg: print elk probleem met prefix `write-headers: ` en exit 1;
- schrijf `<build>/_headers` en print `write-headers: ok (<n> inline script hash(es))`;
- elke fout gaat naar stderr zonder de URL.

Het script start alleen `main()` als het direct wordt uitgevoerd (hetzelfde patroon als `verify-build.mjs`).

### `web/scripts/verify-build.mjs` (toevoeging)
```js
/** build/_headers exists, checkHeaders(text, { template: false }) is empty, every inlineScriptHashes(build/index.html)
 *  occurs in script-src, and the connect-src origin that is not api.maptiler.com occurs literally in at least one
 *  .js file under build/_app/immutable (same Supabase URL as the bundle).
 *  @param {string} buildDir @returns {string[]} */
export function checkBuiltHeaders(buildDir);
```
`main()` voegt na `checkLazyMapLibre` toe: `problems.push(...checkBuiltHeaders(build))`. Imports komen uit `./write-headers.mjs`.

### `web/scripts/check-bundle-size.mjs`
```js
export const KB = 1024;
export const BUDGETS = { initialJsGzip: 150 * KB, precacheGzip: 900 * KB };
export const PRECACHE_EXCLUDED = ['/_headers', '/_redirects']; // = PRECACHE_EXCLUDED_PATHS in src/lib/sw/shell.ts
export const SUPABASE_MARKER = 'X-Client-Info';

/** gzip (level 9) length. @param {Uint8Array | string} data @returns {number} */
export function gzipSize(data);

/** Relative specifiers ('./' or '../') of static imports and re-exports, in order, unique.
 *  Matches: import{…}from"x", import x from"x", import*as x from"x", import"x", export{…}from"x", export*from"x".
 *  Never matches import("x"). Preceding character must not be [\w$.].
 *  @param {string} code @returns {string[]} */
export function staticImports(code);

/** Static import closure (absolute paths) of the start files, resolved relative to each importing file.
 *  Missing targets are ignored. @param {string[]} startFiles @returns {string[]} sorted */
export function importClosure(startFiles);

/** text includes 'setWorkerUrl' and 'getWorkerCount' (same rule as verify-build). @param {string} text */
export function isMapLibreChunk(text);

/** Absolute paths of the .js files that index.html lists as <link rel="modulepreload" href="…">.
 *  Tags: /<link\b[^>]*>/gi whose attributes contain rel="modulepreload" (quotes optional, case-insensitive).
 *  href: drop '?…' and '#…', strip leading '/', './' and any number of '../', keep only paths that start
 *  with '_app/immutable/' and end with '.js', resolve against buildDir. Unique, sorted.
 *  @param {string} html @param {string} buildDir @returns {string[]} */
export function modulepreloadFiles(html, buildDir);

/** @param {string} buildDir @param {string} staticDir
 *  @returns {{ initial: { files: string[], gzip: number }, precache: { files: string[], gzip: number },
 *              maplibre: { file: string | null, gzip: number }, problems: string[] }} */
export function measure(buildDir, staticDir);

/** Problems for every budget exceeded, plus m.problems.
 *  @param {ReturnType<typeof measure>} m @param {typeof BUDGETS} [budgets] @returns {string[]} */
export function checkBudgets(m, budgets = BUDGETS);
```
Regels voor `measure`:
- **Startbestanden:** alle `.js` in `<build>/_app/immutable/entry/`, plus het eerste bestand in `<build>/_app/immutable/nodes/` dat past op `/^0(\.[^.]+)?\.js$/`.
- `problems` krijgt een melding bij:
  - geen entry-JS: `no entry chunks in _app/immutable/entry`;
  - geen `nodes/0`: `root layout chunk _app/immutable/nodes/0.*.js not found`;
  - geen bestand in de afsluiting met `SUPABASE_MARKER`: `initial JS does not contain supabase-js: import parsing is probably broken`;
  - een bestand in de afsluiting waarvoor `isMapLibreChunk` geldt: `MapLibre is in the initial JS: <relpath>`;
  - `modulepreloadFiles(<build>/index.html)` is leeg: `index.html has no modulepreload links: cannot cross-check the import closure`;
  - de modulepreload-lijst bevat bestanden die niet in `importClosure(startFiles)` zitten: `modulepreload files missing from the import closure (import parsing is probably broken): <relpaths, komma-gescheiden>`.
  Bestanden die wel in de afsluiting zitten maar niet in de modulepreload-lijst, zijn geen probleem (ze tellen gewoon mee).
- **Initial:** de vereniging van `importClosure(startFiles)` en `modulepreloadFiles(...)`, met `gzip` als som van `gzipSize` per bestand. Zo telt alles wat de browser vóór de eerste route laadt mee, ook als de import-regex iets mist (en dan faalt de check toch, via het probleem hierboven). Onder "alle `.js` in `entry/`" valt ook `entry/payload.*.js`; die telt terecht mee. In de WP-21-build somt `index.html` precies `entry/start`, `entry/payload`, `entry/app`, `nodes/0` en 12 chunks op (review N-3).
- **Precache:** alle bestanden onder `<build>/_app/immutable/`, plus voor elk bestand in `staticDir` (recursief, relatief pad; `/`+pad niet in `PRECACHE_EXCLUDED`) het bestand in `<build>` als dat bestaat, plus `<build>/index.html`.
- **MapLibre:** het eerste bestand onder `_app/immutable` (buiten `entry/`) waarvoor `isMapLibreChunk` geldt. Alleen ter informatie.

`checkBudgets` meldt:
- `initial JS is <x> kB gzip, budget <y> kB`;
- `precache is <x> kB gzip, budget <y> kB`.

Waarden worden afgerond op één decimaal.

`main()`:
- `WEB_ROOT` zoals in `write-headers.mjs`; args `--build <dir>` (standaard `<WEB_ROOT>/build`) en `--static <dir>` (standaard `<WEB_ROOT>/static`);
- print drie regels: `initial JS: <x> kB gzip (<n> files, budget 150 kB)`, `precache: <x> kB gzip (<n> files, budget 900 kB)`, `maplibre chunk: <x> kB gzip` (of `maplibre chunk: not found`);
- daarna elk probleem met prefix `check-bundle-size: `; exit 1 bij problemen, anders 0.

### `web/package.json` (scripts, wijziging)
```json
"build": "vite build && node scripts/write-headers.mjs",
"size": "node scripts/check-bundle-size.mjs",
```
Bij `devDependencies` komt `"axe-core": "^4.14.0"` (via `npm install -D`). De andere scripts blijven gelijk.

### `.github/workflows/ci.yml` (job `web`)
Na `- run: npm run verify:build` komt `- run: node scripts/check-bundle-size.mjs`. Verder niets: `test_ci_workflow_contract` in `ingest/tests` checkt een deelverzameling en blijft groen.

### Test-helpers
```ts
// web/test/helpers/axe.ts
import axe from 'axe-core'; // when the default import does not type-check: import * as axeNs + axeNs.default ?? axeNs
export const AXE_OPTIONS = { rules: { 'color-contrast': { enabled: false } }, resultTypes: ['violations'] } as const;
export interface AxeFinding { id: string; impact: string; targets: string[] }
/** axe.run(root, AXE_OPTIONS); violations with impact 'serious' or 'critical', flattened to id/impact/targets. */
export function seriousViolations(root?: Element): Promise<AxeFinding[]>; // default root: document.body
/** expect(await seriousViolations(root)).toEqual([]) — the diff names the rule and the selector. */
export function expectNoSeriousViolations(root?: Element): Promise<void>;

// web/test/helpers/contrast.ts
export function hexToRgb(hex: string): [number, number, number]; // '#555' and '#555555'
export function relativeLuminance(hex: string): number;           // WCAG 2.x definition
export function contrastRatio(a: string, b: string): number;      // (L1 + 0.05) / (L2 + 0.05), L1 >= L2
```

### `docs/PRIVACY.md` (inhoud)
Kop "Privacy-inventaris Shakka", een regel "Bijgewerkt in WP-23; wijzig dit bestand samen met `/privacy` en `#lib/privacy.ts`", en vijf secties.

1. **Database (Supabase).** Tabel met de kolommen Gegeven | Tabel en kolommen | Doel | Zichtbaar voor | Bewaartermijn | Verwijderd door.

   | Gegeven | Tabel en kolommen | Doel | Zichtbaar voor | Bewaartermijn | Verwijderd door |
   |---|---|---|---|---|---|
   | Account | `auth.users` (o.a. `email`, `created_at`, `last_sign_in_at`), `auth.identities` | Inloggen | Gebruiker zelf, beheerder | Tot het account wordt verwijderd | `delete_my_account()`, of Lars in het dashboard |
   | Inlogsessies | `auth.sessions` (o.a. tijdstip, IP-adres, user agent), `auth.refresh_tokens` | Ingelogd blijven | Beheerder | Tot uitloggen of verlopen; met het account | Supabase Auth; cascade |
   | Auth-auditlog | `auth.audit_log_entries` | Beveiliging | Beheerder | Leeg als "Write audit logs to the database" uit staat (A13); anders onbeperkt | n.v.t. bij uit |
   | Profiel | `public.profiles` (`weight_kg`, `level`, `quiver_m2`, `default_min_kn`, `default_max_kn`); plus een ongebruikte, altijd lege legacy-kolom die WP-22 verwijdert | Kite-advies, alerts | Gebruiker (RLS), ingest | Tot het account wordt verwijderd | cascade |
   | Favorieten | `public.favorites` | Alerts, ster | Gebruiker (RLS), ingest | Tot ontfavorieten of het account wordt verwijderd | gebruiker; cascade |
   | Alertregels | `public.alert_rules` | Alerts | Gebruiker (RLS), ingest | Idem | gebruiker; cascade via `favorites` |
   | Alertstatus | `public.alert_state` (`window_*`, `status`, `snapshot`, `last_*`) | Deduplicatie | Gebruiker (lezen), ingest | 48 uur na `window_end` | `jobs/alerts.py` (`ALERT_STATE_RETENTION`); cascade |
   | Push-abonnementen | `public.push_subscriptions` (`endpoint`, `p256dh`, `auth`, `created_at`, `last_success_at`) | Meldingen bezorgen | Gebruiker (RLS), ingest | Tot uitzetten, uitloggen, 404/410 van de pushdienst, of verwijdering van het account | `disablePush`, `jobs/push.py`; cascade |
   | Georganiseerde sessies | `public.sessions` (`organizer_id`, `organizer_name`, `note`, `departure_point`, `tikkie_url`, `seats_free`, spot en tijden, `recent_rsvp_creates`) | "Ik ga" | Organisator (RLS); publiek via `get_public_session` (zonder `organizer_id`) | 7 dagen na `ends_at` | `purge_expired_sessions` (`sessions_cleanup`); cascade |
   | Aanmeldingen | `public.rsvps` (`first_name`, `ride`, `seats_offered`, `rides_with`, `edit_token_hash`, `created_at`) | "Ik ook" | Publiek via `get_public_session` (zonder hash) | Tot afmelden; 7 dagen na `ends_at` | `rsvp_delete`; cascade via `sessions` |
   | Geen persoonsgegevens | `spots`, `forecast_hours`, `marine_hours`, `tide_extremes`, `evaluations`, `api_usage`, `ingest_runs` | — | — | Forecast-, golf-, getij- en evaluatiedata 48 uur | `jobs/*` |

   Onder de tabel: "In de database staat nergens een IP-adres in een `public`-tabel. Er wordt geen locatie opgeslagen."
2. **Browser.**

   | Opslag | Sleutel | Inhoud | Bewaard tot |
   |---|---|---|---|
   | `localStorage` | `sb-<project-ref>-auth-token` | supabase-js-sessie | Uitloggen of account verwijderen |
   | `localStorage` | `shakka:organizer_name` | voornaam van de organisator | Account verwijderen (`clearAccountLocalData`), of browsergegevens wissen |
   | `localStorage` | `shakka:return_to` | `{path, saved_at}` van een `/go`-link | Gewist bij inloggen (`takeReturnTo`). Zonder inloggen: na 60 minuten niet meer gebruikt, en gewist bij de eerstvolgende app-start (`pruneReturnTo`). Ook gewist bij account verwijderen |
   | `localStorage` | `shakka:rsvp:{slug}` | `{rsvp_id, edit_token}` | Afmelden, of het openen van de sessiepagina nadat de sessie weg is; anders tot browsergegevens wissen (A9) |
   | `sessionStorage` (SvelteKit) | `sveltekit:history-info`, `sveltekit:snapshot` | scrollpositie per history-item; snapshots (leeg, Shakka gebruikt ze niet) | Tabblad sluiten |
   | Cache API (service worker) | `shakka-shell-<versie>` | alleen app-bestanden | Volgende app-versie (`onActivate`) |
   | HTTP-cache van de browser | — | o.a. kaarttegels, fonts en sprites van MapTiler, volgens hun `Cache-Control` | Beheerd door de browser; geen opslag door de app |

   Onder de tabel: "MapLibre GL JS <versie uit `package-lock.json`> heeft geen eigen tegelcache in de Cache API (gecontroleerd in WP-23: geen `caches.open` in `maplibre-gl/dist`). Er zijn geen cookies van Shakka."
3. **Logs en derden.**
   - Supabase: API-logs 1 dag, auth-auditlogs 1 uur (gratis plan), regio EU (A13).
   - Cloudflare Pages: hosting; Web Analytics uit.
   - GitHub Actions: de uurlijkse job leest profielen, favorieten, alertregels, push-abonnementen en `alert_state` (de laatst gemelde windows). Hij schrijft `alert_state`, en werkt `push_subscriptions` bij (`last_success_at`; verwijderen bij 404/410). De logs bevatten geen persoonsgegevens (tests in WP-10, WP-11 en WP-17). De repo is publiek, dus de logs ook.
   - Pushdiensten (Apple, Google, Mozilla, Microsoft): endpoint plus versleutelde payload.
   - MapTiler: alleen na een klik op "Kaart"; IP, origin, user agent; Referer alleen de origin (`Referrer-Policy`).
   - Maildienst: Supabase (tot WP-22).
   - Open-Meteo en Rijkswaterstaat: alleen de server, zonder gebruikersgegevens.
4. **Afdwinging.** Een korte lijst met waar het getest wordt: `09_delete_my_account.test.sql`, `retention-consistency.test.ts`, `headers.test.ts` en `verify-build` (CSP), `no-third-party.test.ts` en `verify-build` (trackers), en `check-no-client-openmeteo.sh`.
5. **Checklist bij wijzigingen.** Een nieuwe tabel of kolom met persoonsgegevens, een nieuwe `localStorage`-sleutel, een nieuwe externe origin, of een nieuwe kolom die de uurlijkse job leest → werk dit bestand, `/privacy` en zo nodig `_headers` bij.

De regel die met `- GitHub Actions:` begint en de rij van `shakka:return_to` worden door `privacy-page.test.ts` getoetst (zie Testplan AC-5). Pas die test mee aan als de formulering verandert.

### `docs/RUNBOOK.md` (nieuwe sectie)
Nummer: het eerstvolgende vrije nummer bij de merge (nu §17; neemt WP-22 §17, dan wordt dit §18). Titel: "Privacy, CSP en performance (vanaf WP-23)". Punten:
1. `npm run build` schrijft `build/_headers` uit het sjabloon `static/_headers`. Een nieuwe externe origin (fetch, img, worker) vraagt een aanpassing van het sjabloon, van `checkHeaders` en van `docs/PRIVACY.md`.
2. `node scripts/check-bundle-size.mjs` (vanuit `web/`, na een build). Gemeten bij WP-23: initiële JS `<x>` kB, precache `<y>` kB, MapLibre `<z>` kB (gzip). De builder vult de waarden in.
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
6. Terugdraaien bij een CSP-probleem in productie: verwijder de regel `Content-Security-Policy` uit `static/_headers` (en de check in `checkHeaders` tijdelijk), push en deploy. Andere headers blijven staan.

## Edge cases

| # | Geval | Gedrag |
|---|---|---|
| E1 | `anon` roept `delete_my_account` aan | 42501 (REST: 401). Niets verwijderd. |
| E2 | Token zonder `sub` | `PT401` `not_authenticated`. |
| E3 | Gebruiker roept het twee keer aan (dubbel tikken, twee tabbladen) | De UI blokkeert met `busy`. Op de server is de tweede aanroep een no-op zonder fout. |
| E4 | Netwerkfout of time-out (15 s) bij de RPC | `ACCOUNT_MESSAGES.network`; de bevestiging blijft open; niets veranderd. Kwam de RPC toch aan, dan is het account weg en geeft een volgende poging een no-op met `ok`. |
| E5 | RPC lukt, `signOut` faalt | `cleanUpAfterAccountDeletion` vangt het op en wist de lokale sleutels toch. De statusmelding staat er al. Zie A11 en R7. |
| E6 | Profiel laadt niet of ontbreekt | De sectie "Account verwijderen" staat er toch (zichtbaar zodra `$session` gezet is). |
| E7 | Gebruiker organiseert sessies met aanmeldingen van anderen | Die verdwijnen mee (cascade). De bevestiging zegt dat expliciet. Deelnemers zien daarna "Sessie niet gevonden". |
| E8 | Gebruiker heeft zelf zonder account aangemeld bij sessies van anderen | Blijft staan; `shakka:rsvp:*` blijft in `localStorage` zodat afmelden kan (A10). |
| E9 | Push staat aan op een ander apparaat | De rij verdwijnt (cascade); de ingest stuurt niets meer. De browser daar houdt een dode subscription tot die een keer wordt opgeruimd; er komen geen meldingen. |
| E10 | `index.html` heeft geen inline script (kit verandert) | `inlineScriptHashes` geeft `[]`; `script-src 'self'`. De checks blijven werken. |
| E11 | `PUBLIC_SUPABASE_URL` ontbreekt of is ongeldig bij de build | `write-headers` faalt met exit 1, zonder de waarde te tonen; de build faalt (zoals `env-schema`). |
| E12 | Iemand draait alleen `vite build` | `build/_headers` is dan het sjabloon met placeholders. `verify:build` faalt ("unresolved placeholder"). Pages draait `npm run build`, dus het script loopt daar altijd mee. |
| E13 | Service worker precache met `_headers` in `static/` | Zonder filter zou de SPA-fallback (`index.html`, 200) onder `/_headers` in de cache komen. `precacheList` laat `/_headers` en `/_redirects` weg (A6). |
| E14 | Offline: de shell uit de cache | Bevat de CSP-header van het moment van cachen, die bij dezelfde `index.html` (en hash) hoort. |
| E15 | Nieuwe deploy: andere inline-scripthash | De netwerkrespons van een navigatie brengt nieuwe HTML en een nieuwe header tegelijk mee. |
| E16 | Lokale dev (`vite dev`, `vite preview`) | Geen `_headers`, dus geen CSP. Bewust: CSP-gedrag wordt op een Pages-preview getoetst (RUNBOOK). |
| E17 | Import-parsing in `check-bundle-size` mist alles (ander outputformaat) | Gezondheidscheck: geen `X-Client-Info` in de afsluiting geeft een probleem (exit 1). |
| E18 | Een nieuwe kleur in CSS of een component | `contrast.test.ts` faalt tot de kleur in een paar of in `DECORATIVE` staat. |
| E19 | `PRIVACY_CONTACT_EMAIL` gezet | `mailto:`-link; anders de algemene zin. |
| E20 | De bewaartermijn in de ingest wordt bijvoorbeeld 72 uur | `retention-consistency.test.ts` faalt tot `#lib/privacy.ts` (en dus de tekst) meegaat. |
| E21 | Bezoeker tikt "Ik ga", logt nooit in, en opent Shakka twee uur later opnieuw | `pruneReturnTo` wist de sleutel bij die start (A21); er volgt geen navigatie. |
| E22 | Bezoeker tikt "Ik ga" en opent binnen 60 minuten de magic link | `pruneReturnTo` laat de verse sleutel staan; `takeReturnTo` stuurt na inloggen terug naar de `/go`-link (gedrag van WP-20 ongewijzigd). |
| E23 | `shakka:return_to` met kapotte JSON, een `saved_at` in de toekomst of een niet-toegestaan pad | `pruneReturnTo` wist hem bij de start: `takeReturnTo` zou hem nooit gebruiken. |
| E24 | Modulepreload-lijst in `index.html` ontbreekt of bevat iets buiten de import-afsluiting | `check-bundle-size` meldt een probleem (exit 1); de meting telt de vereniging. |

## Testplan
Tests eerst voor de pure logica: `account.ts`, `write-headers.mjs`, `check-bundle-size.mjs`, `contrast.ts` en `precacheList`. Alle webtests draaien in `npm test`; de DB-tests in `supabase test db`.

### AC-1: `supabase test db`
`supabase/tests/09_delete_my_account.test.sql`, met `begin; … select plan(23); … select * from finish(); rollback;`.

Fixture (als `postgres`):
- users A `aaaaaaaa-0000-4000-8000-00000000000a` en B `bbbbbbbb-0000-4000-8000-00000000000b` in `auth.users` (profielen via de trigger);
- spot `pgtap-del-spot`;
- per gebruiker een favoriet, een alertregel (`min_kn` 12 en 20), een `alert_state` (zoals in `04_rls_users`) en een push-subscription (`https://push.example.test/a` en `/b`, `p256dh` `'BAAA'`, `auth` `'AAAA'`);
- sessie SA (`id` `5a000000-0000-4000-8000-00000000000a`, organisator A, `organizer_name` `'Anna'`) en SB (`5b000000-…0b`, organisator B, `'Bram'`), beide `starts_at` `'2026-10-20T10:00:00Z'` en `ends_at` `'2026-10-20T14:00:00Z'`;
- RSVP's (direct als `postgres`):
  - op SA: `'Bram'`, hash `repeat('a',64)`;
  - op SB: `'Anna'` (A's anonieme aanmelding), hash `repeat('b',64)`, en `'Cas'`, hash `repeat('c',64)`.

Asserties:
1. `has_function('public','delete_my_account','{}'::name[])`
2. `function_returns('public','delete_my_account','{}'::name[],'void')`
3. `is_definer('public','delete_my_account','{}'::name[])`
4. `ok(...)`: `proconfig @> array['search_path=""']`
5. `function_privs_are(…,'anon','{}')`
6. `function_privs_are(…,'authenticated',array['EXECUTE'])`
7. `function_privs_are(…,'service_role','{}')`
8. `set local role anon` → `throws_ok('select public.delete_my_account()','42501',null,…)`; `reset role`
9. `set local role authenticated` met claims `{"role":"authenticated"}` (zonder `sub`) → `throws_ok(…,'PT401','not_authenticated',…)`; `reset role`
10. als `authenticated` met `sub` = A → `lives_ok('select public.delete_my_account()')`; `reset role`
11. tot en met 18: `is_empty` voor A in `auth.users`, `profiles`, `favorites`, `alert_rules`, `alert_state`, `push_subscriptions`, `sessions` (`organizer_id` = A) en `rsvps` (`session_id` = SA)
19. `isnt_empty` B in `auth.users`
20. `results_eq` op één rij met de aantallen van B in `profiles`, `favorites`, `alert_rules`, `alert_state`, `push_subscriptions` en `sessions` = `(1,1,1,1,1,1)`
21. `results_eq`: `count(*)` van `rsvps` op SB = 2 (A's anonieme aanmelding blijft)
22. als `authenticated` met `sub` = A opnieuw → `lives_ok` (no-op)
23. `isnt_empty` B in `auth.users` na stap 22

Daarnaast `07_sessions.test.sql` (twee aangepaste `set_eq`'s). De volledige suite is groen.

### AC-2: axe-core, 0 overtredingen `serious`/`critical`
Elke file mockt precies zoals het genoemde bestaande testbestand. Elke `it` rendert, wacht tot de toestand er is (`findBy…`), en roept `await expectNoSeriousViolations()` aan. Na elke test `cleanup()` (standaard via testing-library).

| Bestand | Pagina | Toestanden (elk een eigen `it`) | Mocks en fixtures zoals in |
|---|---|---|---|
| `a11y-home.test.ts` | `/` | lijst met `homeData()` (uitgelogd); ingelogd met favorieten (sterren); `kind: 'error'`-banner | `spot-list.test.ts`, `fixtures/map-data.ts` |
| `a11y-spot.test.ts` | `/spot/[id]` | `pageData()` met golven; uitgelogd en ingelogd (ster); onverifieerde spot | `spot-page.test.ts` |
| `a11y-public-session.test.ts` | `/s/[slug]` | open sessie zonder opgeslagen RSVP (formulier); met opgeslagen RSVP (`TOKEN` in `localStorage`) en daarna "Wijzigen" open; geannuleerde sessie; `not_found` | `public-session-page.test.ts`, `fixtures/public-session.ts` |
| `a11y-profile.test.ts` | `/profiel` | geladen met `PROFILE_FULL`; na opslaan met fouten (`weight_kg` 25, `aria-invalid`); bevestiging "Account verwijderen" open; profiel ontbreekt (banner plus verwijdersectie) | `profile-page.test.ts` |
| `a11y-alerts.test.ts` | `/alerts` | `serve()` ingelogd met `installPushEnv` (PushSettings), één regel opengeklapt | `alerts-page.test.ts` |
| `a11y-login.test.ts` | `/login` | formulier; met foutmelding; verzonden; standalone met "Inloglink plakken" | `login.test.ts` |
| `a11y-layout.test.ts` | layout | uitgelogd; ingelogd; met foutbanner | `layout.test.ts` |
| `a11y-static-pages.test.ts` | `/privacy`, `/over` | standaard | geen mocks |
| `a11y-session-pages.test.ts` | `/sessie/nieuw`, `/sessie/[slug]/delen`, `/mijn-sessies` | standaardtoestand met fixture (WP-20 Gevolgen) | `new-session-page.test.ts`, `share-page.test.ts`, `my-sessions-page.test.ts` |

Omdat `vi.mock` per bestand geldt, heeft `a11y-session-pages.test.ts` de vereniging van de mocks van die drie bestanden nodig. Botsen die, dan splitst de builder het in drie bestanden (`a11y-session-new.test.ts` enz.); dat is geen ontwerpwijziging.

Aanvullend:
- `a11y-compiler.test.ts` (`@vitest-environment node`): voor elk `.svelte`-bestand onder `src/` geldt `compile(code, { filename, generate: 'client', runes: true }).warnings.filter(w => w.code.startsWith('a11y_'))` is `[]`, met de bestandsnaam in de assert. Faalt `compile` op TypeScript-syntax die geen pure type is, dan gebruikt de test eerst `preprocess(code, vitePreprocess(), { filename })` uit `svelte/compiler` en `@sveltejs/vite-plugin-svelte`.
- `contrast.test.ts` (node):
  - `contrastRatio('#ffffff', '#000000')` is 21 en `contrastRatio('#777777', '#ffffff')` ligt tussen 4,47 en 4,49 (referentiewaarden);
  - een tabel `PAIRS` (`[voorgrond, achtergrond, minimum, waar]`) eist per paar `contrastRatio >= minimum`. Voor tekst geldt 4,5, voor niet-tekst (focusrand, ster, rand van `aria-invalid`) 3. De paren:
    - `#1a1a1a`/`#ffffff` (tekst), `#555555`/`#ffffff` (muted, footer, hint), `#555555`/`#fff4e5` (muted in banner), `#1a1a1a`/`#fff4e5`, `#1a1a1a`/`#fdecea`, `#a4161a`/`#ffffff` (fout), `#a4161a`/`#fdecea`;
    - `#ffffff`/`#0b5e8a` (header, knoppen delen/mijn-sessies), `#0b5e8a`/`#ffffff` (3, focus), `#ffffff`/`#1b7f3b` (go, go-run), `#1b7f3b`/`#ffffff` (notice-ok), `#ffffff`/`#8a5a00` (marginal), `#8a5a00`/`#ffffff` (onverifieerd, notice), `#8a5a00`/`#ffffff` (3, ster), `#ffffff`/`#a4161a` (no_go, `.danger`), `#ffffff`/`#555555` (verdict-none op de kaart), `#1a1a1a`/`#f4f4f4` (laadmelding kaart), `#a4161a`/`#ffffff` (3, `aria-invalid`);
  - inventaris: elke hexkleur (`/#[0-9a-fA-F]{6}\b|#[0-9a-fA-F]{3}\b/`, genormaliseerd naar 6 tekens en kleine letters) in `src/app.css` en in alle `src/**/*.svelte` komt voor in `PAIRS` of in `DECORATIVE = { '#dddddd': 'scheidingslijnen', '#e0b36b': 'rand banner' }`. Vindt de test meer kleuren, dan voegt de builder een paar toe op basis van het gebruik (tekst 4,5, niet-tekst 3). Faalt een paar, dan past hij de kleur aan en noteert dat in `deviations.md`.
- `layout.test.ts`: de skiplink is het eerste focusbare element, met `href="#main"`; `main` heeft `id="main"` en `tabindex="-1"`.

### AC-3: bundelbudget in CI
`bundle-size.test.ts` (node), met een fixture-build in `mkdtempSync(join(tmpdir(), 'shakka-size-'))`:
- `entry/start.a.js`: `import{a as b}from"../chunks/x.js";import"../chunks/y.js";const l=()=>import("../chunks/lazy.js");`
- `entry/app.b.js`: `export{c}from"../chunks/x.js";export*from"../chunks/z.js";`
- `nodes/0.c.js`: `import{s}from"../chunks/supa.js";`
- `nodes/1.d.js`: `import"../chunks/route.js";`
- de chunks `x`, `y`, `z`, `supa` (met `"X-Client-Info"`), `lazy`, `route` en `maplibre.e.js` (met `setWorkerUrl` en `getWorkerCount`);
- `index.html` met zeven modulepreload-links: `<link rel="modulepreload" href="/_app/immutable/entry/start.a.js">` en op dezelfde manier `entry/app.b.js`, `nodes/0.c.js`, `chunks/y.js`, `chunks/z.js` en `chunks/supa.js`, plus voor `x` de vorm `<link href="./_app/immutable/chunks/x.js?v=1" rel=modulepreload>` (andere attribuutvolgorde, geen quotes, `./` en query). Daarnaast één `<link rel="stylesheet" href="/_app/immutable/assets/a.css">` (geen modulepreload, telt niet);
- een `static/` met `favicon.svg` en `_headers`, plus de kopieën in de build.

Toetsen:
1. `staticImports` vindt in de bovenstaande strings precies de statische specifiers, ook met spaties (`import { a } from './x.js'`) en `import * as m from"./m.js"`; nooit `import(`; niet `foo.import"x"`.
2. `measure(...).initial.files` (relatief) = `start.a.js`, `app.b.js`, `nodes/0.c.js`, `x`, `y`, `z`, `supa`; dus niet `lazy`, `route`, `nodes/1` of `maplibre`. `problems` is `[]`.
3. `measure(...).precache.files` bevat alle immutable-bestanden, `favicon.svg` en `index.html`, maar niet `_headers`.
4. `maplibre.file` eindigt op `maplibre.e.js`.
5. `checkBudgets(m, { initialJsGzip: 1, precacheGzip: 1 })` geeft twee meldingen; met `BUDGETS` geeft het `[]`.
6. Zonder `nodes/0`: probleem `root layout chunk …`. Zonder `X-Client-Info`: probleem `… supabase-js …`. Met `import"../chunks/maplibre.e.js"` in `start`: probleem `MapLibre is in the initial JS`.
7. CLI: `spawnSync(process.execPath, ['scripts/check-bundle-size.mjs', '--build', dir, '--static', staticDir], { cwd: webRoot })` geeft exit 0. Met `crypto.randomBytes(300_000).toString('base64')` als inhoud van `chunks/x.js`: exit 1, en stderr of stdout bevat `initial JS is`. Base64 van willekeurige bytes comprimeert tot ongeveer 6/8 van zijn lengte: 400.000 tekens worden ±300.000 bytes gzip, ±293 kB. Dat ligt ruim boven 150 kB.
7a. `modulepreloadFiles`: op de fixture-`index.html` geeft het precies de zeven bestanden van toets 2 (absoluut, gesorteerd); `?v=1` en `./` zijn genormaliseerd; de stylesheet-link telt niet.
7b. Zonder modulepreload-links in `index.html`: probleem `index.html has no modulepreload links …`. Met een extra `<link rel="modulepreload" href="/_app/immutable/chunks/route.js">`: probleem `modulepreload files missing from the import closure …` met `route.js` erin, en `initial.files` bevat `route.js` (vereniging).
8. `PRECACHE_EXCLUDED` is gelijk aan `PRECACHE_EXCLUDED_PATHS` uit `src/lib/sw/shell.ts`.
9. `.github/workflows/ci.yml`: de regels (getrimd) bevatten `- run: node scripts/check-bundle-size.mjs`, ná `- run: npm run build`.

Plus: de CI-job `web` draait het script op de echte build (AC-3, "draait in CI").

### AC-4: `_headers`
`headers.test.ts` (node):
1. `checkHeaders(read('static/_headers'), { template: true })` is `[]`.
2. Expliciet, zodat de AC leesbaar is: de CSP van `/*` heeft `connect-src`, dat `'self'`, `{{SUPABASE_ORIGIN}}` en `https://api.maptiler.com` bevat, geen bron met `*`, geen `open-meteo` en geen `ANALYTICS_MARKERS`; `script-src` is precies `['\'self\'', '{{SCRIPT_HASHES}}']`.
3. Elke origin uit `MAP_EXTERNAL_ORIGINS` (`#lib/map/config.js`) staat in `connect-src` en `img-src`.
4. `/s/*` heeft `X-Robots-Tag: noindex`; `/*` heeft `Referrer-Policy: strict-origin-when-cross-origin`; `/_app/immutable/*` heeft `Cache-Control` met `immutable`.
5. `parseHeaders` op een tekst met commentaar, lege regels en twee rules geeft de juiste structuur; `parseCsp` op een waarde met dubbele spaties en een afsluitende `;`.
6. `inlineScriptHashes('<script>a()</script><script src="/x.js"></script><script type="module">b</script>')` geeft twee hashes, gelijk aan `'sha256-' + createHash('sha256').update('a()').digest('base64') + "'"` en die van `'b'`.
7. `renderHeaders(template, { supabaseOrigin: 'https://abc.supabase.co', scriptHashes: [h1] })`: geen `{{`, `checkHeaders(…, { template: false })` is `[]`, `connect-src` bevat `https://abc.supabase.co`, `script-src` is `'self'` plus `h1`. Met `scriptHashes: []` is `script-src` alleen `'self'` (geen dubbele spaties).
8. Negatieve gevallen voor `checkHeaders`: `connect-src *`, `connect-src https://api.open-meteo.com`, `https://www.google-analytics.com`, `script-src 'self' 'unsafe-inline'`, een ontbrekende `/s/*`-regel en een regel van 2.001 tekens geven elk minstens één probleem.
9. `supabaseOrigin`: `'https://abc.supabase.co/'` geeft de origin; `'http://127.0.0.1:54321'` is ok; `'http://evil.test'`, `''` en `'https://abc.supabase.co/rest'` gooien, en de foutmelding bevat de waarde niet.
10. CLI `write-headers.mjs --template static/_headers --build <tmp>`, met `env: { ...process.env, PUBLIC_SUPABASE_URL: 'https://abc.supabase.co' }` en `<tmp>/index.html` met één inline script: exit 0 en `<tmp>/_headers` bevat de origin en de hash. Met `PUBLIC_SUPABASE_URL: 'ftp://x'`: exit 1, en stderr bevat `ftp://x` niet.

`verify-build.test.ts` (uitbreiding): `checkBuiltHeaders` op een tijdelijke build:
- ok-geval: gerenderde `_headers`, `index.html` met inline script, en een `.js` onder `_app/immutable` die `https://abc.supabase.co` bevat;
- fout als `_headers` ontbreekt, als er een placeholder in staat, als de hash van het inline script niet in `script-src` staat, of als de origin in geen enkel JS-bestand voorkomt.

### AC-5: `/privacy`
- `privacy-page.test.ts`:
  1. `heading` level 1 is "Privacy";
  2. `document.title` is "Privacy · Shakka";
  3. de tekst bevat (case-insensitive): `e-mailadres`, `voornaam`, `profiel`, `push-abonnementen`, `Supabase`, `Cloudflare`, `GitHub`, `MapTiler`, `Apple`, `Google`;
  4. de tekst bevat `${FORECAST_RETENTION_HOURS} uur`, `${ALERT_STATE_RETENTION_HOURS} uur` en `${SESSION_RETENTION_DAYS} dagen`;
  4a. `shakka:return_to` (B-1a): de tekst bevat `gewist zodra je inlogt` en `na ${RETURN_TO_TTL_MINUTES} minuten niet meer, en wist het de eerstvolgende keer dat je Shakka opent` (witruimte genormaliseerd naar één spatie), en matcht niet op `/hoogstens\s*\d+\s*minuten/i`;
  4b. GitHub (B-1b): het `listitem` dat "GitHub" bevat, bevat `profiel, favorieten, alertinstellingen, push-abonnementen en welke alerts je al kreeg`;
  4c. grondslag (N-7): `heading` level 2 "Waarom Shakka dit mag" bestaat, en de tekst bevat `dienst te leveren die je zelf aanvraagt` en `vraagt daarom niet om toestemming voor cookies`;
  4d. browseropslag (N-8): de tekst bevat `kaarttegels` en `scrollpositie`;
  4e. `docs/PRIVACY.md` (gelezen met `readFileSync(new URL('../../docs/PRIVACY.md', import.meta.url))`):
     - de regel die met `- GitHub Actions:` begint (na trimmen), bevat `profielen`, `favorieten`, `alertregels`, `push-abonnementen` en `` `alert_state` ``;
     - de tabelrij die `` `shakka:return_to` `` bevat, bevat `pruneReturnTo` en `takeReturnTo`, en niet `hoogstens`;
     - het bestand bevat `sessionStorage` en `sveltekit:history-info`;
  5. de tekst bevat geen `/telegram/i`;
  6. er is een link naar `/profiel`;
  7. de link naar de Autoriteit Persoonsgegevens heeft `rel` met `noopener`;
  8. met `PRIVACY_CONTACT_EMAIL` `null` staat er geen `mailto:`-link. Bij gezette waarde: zie E19. Die test mockt `#lib/privacy.js` met `vi.doMock` en een dynamische import.
- `retention-consistency.test.ts` (node). Leest de bronnen van `../../ingest/src/shakka/jobs/` en haalt met `new RegExp(String.raw`(?:^|\n)` + name + String.raw`: Final = timedelta\((hours|days)=(\d+)\)`)` de waarden op (het anker voorkomt dat `RETENTION` in `TIDE_RETENTION` matcht):
  - `forecast.py` `RETENTION`, `marine.py` `RETENTION`, `tides.py` `TIDE_RETENTION` en `evaluate.py` `EVALUATION_RETENTION` = `hours`, `FORECAST_RETENTION_HOURS`;
  - `alerts.py` `ALERT_STATE_RETENTION` = `hours`, `ALERT_STATE_RETENTION_HOURS`;
  - `sessions.py` `SESSION_RETENTION` = `days`, `SESSION_RETENTION_DAYS`;
  - de sessie-migratie bevat `interval '${SESSION_RETENTION_DAYS} days'`;
  - `RETURN_TO_TTL_MINUTES` is 60.
- `layout.test.ts`:
  - de footer heeft een link "Privacy" met `href="/privacy"`;
  - (A21) uitgelogd (dezelfde opzet als de bestaande test "does nothing while signed out and keeps the key"), met `shakka:return_to` van 61 minuten oud: na `render` is de sleutel weg (`vi.waitFor`) en is `goto` niet aangeroepen;
  - de bestaande test "does nothing while signed out and keeps the key" (verse sleutel) blijft ongewijzigd groen.
- `local-prefs.test.ts` (A21), met de bestaande fake storage en `NOW`:
  1. verse sleutel (`saved_at = NOW`, en ook `NOW - RETURN_TO_TTL_MS`): `pruneReturnTo` geeft `false` en de sleutel staat er nog;
  2. `saved_at = NOW - RETURN_TO_TTL_MS - 1`: `true`, sleutel weg;
  3. `saved_at = NOW + 1000` (toekomst), kapotte JSON, `{path: '/elders', saved_at: NOW}` en `{path: 1, saved_at: NOW}`: elk `true`, sleutel weg;
  4. geen sleutel: `false`, en `removeItem` is niet aangeroepen;
  5. `undefined` storage, en een storage waarvan `getItem` of `removeItem` gooit: `false`, geen throw;
  6. de bestaande tests van `takeReturnTo` blijven ongewijzigd groen.
- `over.test.ts`: er is een link naar `/privacy`.
- `attribution.test.ts`: de volledige stand bevat "golfmodellen van DWD en ECMWF"; de bestaande tests blijven groen.

### AC-6: Lighthouse en installeerbaarheid (`NEEDS_LARS`)
Procedure in de RUNBOOK-sectie, punt 5. De verifier noteert de scores die Lars aanlevert.

### Overige tests (ontwerp)
- `account.test.ts`. Mocks: `#lib/supabase.js` → `{ supabase: { rpc: fake.rpc } }` (`createFakeRpc`), en `#lib/auth.js` → `{ signOut: vi.fn() }`.
  1. succes: één aanroep `fn === 'delete_my_account'`, `argCount === 1` (geen args), `signal` gezet, en het resultaat is `{ ok: true }`;
  2. `status: 0` geeft `network`;
  3. `{ code: 'PT401', message: 'not_authenticated' }` met status 401 geeft `failed`;
  4. `throwNext` geeft `network`;
  5. bij een fout precies één `console.warn('account delete failed')`;
  6. `cleanUpAfterAccountDeletion(localStorage)`: `signOut` één keer; `shakka:organizer_name` en `shakka:return_to` weg; `shakka:rsvp:<slug>` en `other` blijven;
  7. gooit `signOut`, dan worden de sleutels toch gewist en resolvet de functie;
  8. `clearAccountLocalData(undefined)` en een storage die gooit, geven geen throw.
- `delete-account.test.ts`. Mock: `#lib/account.js` met `deleteMyAccount` en `cleanUpAfterAccountDeletion` als `vi.fn`.
  1. "Account verwijderen…" opent de bevestiging, en de focus staat op "Weet je het zeker?";
  2. "Annuleren" sluit, en de focus staat weer op de knop;
  3. "Ja, verwijder mijn account": `deleteMyAccount` één keer, daarna `ondeleted` en `cleanUpAfterAccountDeletion`;
  4. tijdens `busy` zijn de knoppen `disabled` en geeft een tweede klik geen tweede aanroep;
  5. bij `{ ok:false, error }`: `role="alert"` met de melding, `ondeleted` niet aangeroepen, de bevestiging nog open.
- `profile-page.test.ts` (uitbreiding, met `vi.mock('#lib/account.js', …)`):
  1. ingelogd en geladen: er is een `region`/sectie met kop "Account verwijderen";
  2. uitgelogd: geen sectie;
  3. profiel ontbreekt: de sectie is er wel;
  4. na een geslaagde verwijdering: `role="status"` met `ACCOUNT_MESSAGES.deleted` en geen formulier.
- `user-tables.test.ts`: `RPC_FILES = ['lib/rsvp.ts', 'lib/account.ts']`.
- `sw-shell.test.ts`: `precacheList(['/a.js', '/_headers', '/_redirects', '/a.js'], '/')` is `['/a.js', '/']`.
- `rsvp-storage.test.ts` (A19): de aanroepen met `null` worden `undefined`; verder zijn de verwachtingen gelijk.

## Externe afhankelijkheden

| Wat | Gebruik | Gecontroleerd | Bron |
|---|---|---|---|
| `axe-core` ^4.14.0 (devDependency, licentie MPL-2.0) | `axe.run(context, { rules: { 'color-contrast': { enabled: false } }, resultTypes: ['violations'] })`; `violations[].impact` ∈ minor/moderate/serious/critical | `latest` = 4.14.0 op 15 oktober 2026 | https://registry.npmjs.org/axe-core/latest, https://github.com/dequelabs/axe-core/blob/develop/doc/API.md |
| Cloudflare Pages `_headers` | Locatie `static/` (komt in de build-output); regels: patroon plus ingesprongen `Name: value`; splat `*`; bij meerdere matches erven requests alle headers (dezelfde header wordt met komma's samengevoegd); max. 100 regels, 2.000 tekens per regel; commentaar met `#`; het bestand wordt zelf niet geserveerd; niet van toepassing op Pages Functions (Shakka heeft er geen) | 15 oktober 2026 | https://developers.cloudflare.com/pages/configuration/headers/ |
| Supabase: beperkingen `auth`-schema (april 2025) | Objecten maken of droppen en indexes zijn beperkt; DML op `auth.users` niet genoemd; triggers en RLS op `auth.users` toegestaan | 15 oktober 2026 | https://supabase.com/changelog/34270-restricting-access-on-auth-storage-and-realtime-schemas-on-april-21-2025 |
| Supabase: Auth-auditlogs | Opslag extern en/of in `auth.audit_log_entries`; velden o.a. `ip_address`, `user_agent`; schakelaar "Write audit logs to the database" | 15 oktober 2026 | https://supabase.com/docs/guides/auth/audit-logs |
| Supabase gratis plan: logretentie | API- en database-logs 1 dag; Auth Audit Logs 1 uur | 15 oktober 2026 | https://supabase.com/pricing |
| supabase-js `signOut` | Negeert 401/403/404 bij het afmelden en verwijdert de lokale sessie (A11). De builder bevestigt dit in `node_modules` (stap 2) | Niet via documentatie te bevestigen (de signout-docs zeggen alleen "removes the session stored in the local storage medium") | https://supabase.com/docs/guides/auth/signout, broncode `@supabase/auth-js` `GoTrueClient._signOut` |
| Vite `loadEnv(mode, envDir, prefixes)` | Laadt `.env*` uit `envDir`; bestaande `process.env`-waarden gaan voor | 15 oktober 2026 | https://vite.dev/guide/api-javascript.html, https://vite.dev/guide/env-and-mode |
| `svelte/compiler` `compile(source, options)` | `CompileResult.warnings[].code`; opties `filename`, `generate`, `runes` | 15 oktober 2026 | https://svelte.dev/docs/svelte/svelte-compiler |
| Lighthouse 12 | PWA-categorie verwijderd; installeerbaarheid via DevTools → Application → Manifest | 15 oktober 2026 | https://github.com/GoogleChrome/lighthouse/releases/tag/v12.0.0, https://developer.chrome.com/blog/update-install-criteria |
| MapLibre en MapTiler (CSP) | `connect-src` en `img-src` `https://api.maptiler.com`, `img-src data: blob:`, `worker-src 'self'` | Overgenomen uit WP-15 (gecontroleerd daar) | WP-15 blueprint, "Gevolgen voor latere WP's" |
| Autoriteit Persoonsgegevens | Link in `/privacy` | — | https://autoriteitpersoonsgegevens.nl/ |
| SvelteKit 3: `sessionStorage` | Sleutels `sveltekit:snapshot`, `sveltekit:navigation-snapshot` (constante), `sveltekit:history-info`; `client.js` schrijft `history-info` en `snapshot` (A24) | 15 oktober 2026, in `node_modules` van de WP-21-worktree | `@sveltejs/kit/src/runtime/client/constants.js`, `client.js` |
| MapLibre GL JS 6.14.0: tegelcache | Geen `caches.open` en geen `maplibre-tiles` in `dist/`; alleen de in-memory `TileCache` (A24) | 15 oktober 2026, in `node_modules` van de WP-21-worktree | `maplibre-gl/dist/maplibre-gl-dev.mjs`, `maplibre-gl-worker-dev.mjs` |

Geen nieuwe runtime-dependency, geen nieuwe dienst, geen kosten.

## Risico's
- **R1. De CSP blokkeert iets dat de tests niet zien** (MapLibre-worker, een sprite via blob, supabase-js). Mitigaties:
  - de directives komen uit de MapLibre-docs (WP-15);
  - de controle op een Pages-preview vóór de promotie naar `main` (RUNBOOK punt 5, console zonder CSP-meldingen);
  - terugdraaien is één regel (punt 6).
- **R2. Pages past `_headers` misschien niet toe op paden die via de SPA-fallback `index.html` krijgen** (bijv. `/s/…`). De docs zeggen dat niet expliciet; de matching gaat op de URL van het verzoek. Lars controleert het met `curl -sI` (punt 5). Zonder header blijft de `<meta name="robots">` van WP-21 staan, en is er geen CSP op die paden (dan melden bij de verifier).
- **R3. De env-bron van het script en van SvelteKit lopen uiteen.** Mitigatie: `checkBuiltHeaders` eist dat de Supabase-origin uit de CSP letterlijk in de gebouwde JS staat.
- **R4. De budgetten zijn niet gemeten** (A4). De builder meet in stap 9. Boven budget betekent stoppen en een beslissing van Lars; niet stilletjes ophogen.
- **R5. axe in jsdom ziet geen layoutproblemen** (contrast, doelgrootte, overlap). Die worden gedekt door `contrast.test.ts` en Lighthouse (AC-6). axe kan in jsdom ook valse meldingen geven; als een melding aantoonbaar door jsdom komt, mag de builder die ene regel voor die ene `it` uitzetten (`rules: { '<id>': { enabled: false } }`), met een commentaar met de reden en een regel in `deviations.md`. Nooit globaal.
- **R6. Rechten op `auth.users` in het gehoste project.** Lokaal toont AC-1 dat het werkt. Mocht het gehoste project `delete` als `postgres` weigeren, dan ziet de gebruiker `ACCOUNT_MESSAGES.failed` en blijft alles staan. Lars test het met een testaccount (punt 5) vóór de promotie naar `main`.
- **R7. Lokale sessie na het verwijderen.** Wijkt supabase-js af van A11 (gooit bij 403/404 een fout en houdt de sessie), dan staat het e-mailadres nog in de header tot de token-refresh faalt (maximaal 1 uur), zonder toegang tot data. De builder controleert in stap 2 `grep -n "ignore 404s" node_modules/@supabase/auth-js/dist/module/GoTrueClient.js`. Ontbreekt dat, dan noteert hij het in `deviations.md` en stopt; de oplossing (bijvoorbeeld de supabase-sleutel in `localStorage` zelf wissen) is een ontwerpbeslissing.
- **R8. Samenloop met WP-22.**
  - Regel 69 van `07_sessions.test.sql`: WP-22 voegt `db_usage` toe (regel 68 en 69). Wie als tweede merget, neemt beide namen op.
  - Het nummer van de RUNBOOK-sectie (eerstvolgende vrije).
  - `ci.yml`: WP-22 kan een `npm audit`-stap toevoegen; dan staan beide regels erin.
  - `package-lock.json`: bij een conflict opnieuw `npm install` op de gemergde `package.json`.
  - Migraties: verschillende bestanden, onafhankelijk. Merget de migratie met de vroegste tijdstempel als laatste, dan heeft Lars `supabase db push --include-all` nodig.
  - Na de verwijdering van de telegram-kolom door WP-22 klopt de regel "ongebruikte legacy-kolom" in `docs/PRIVACY.md` niet meer; WP-22 haalt die regel weg (zie Gevolgen).
- **R9. De privacytekst klopt alleen met de instellingen van A13.** Daarom zijn die "Nodig van Lars" vóór de goedkeuring van de tekst.
- **R10. Functies van Cloudflare die scripts injecteren** (Rocket Loader, Email Obfuscation, Web Analytics) worden door de CSP geblokkeerd. Op `*.pages.dev` staan ze uit. Het staat in de RUNBOOK (punt 4).
- **R11. Login-CSRF met een geplakte link** (WP-18 review N-4). Geaccepteerd: het risico bestaat bij elke magic link; het plakveld voegt geen nieuw type toe. Geen actie.
- **R12. Sessies ver in de toekomst** (WP-19 review). De bewaartermijn telt vanaf het einde van de sessie; de tekst zegt dat letterlijk, dus de belofte klopt. Een bovengrens op `starts_at` hoort niet bij deze WP.
- **R13. Een gebruiker die zijn account verwijdert, kan zich niet zelf opnieuw aanmelden** zolang `shouldCreateUser: false` geldt (tot WP-22). Lars moet hem dan opnieuw toevoegen. Dat staat niet in de UI-tekst, omdat het na WP-22 niet meer klopt.

## Buiten scope
- Een opruimronde over `shakka:rsvp:*` (A9) en een knop "gegevens op dit apparaat wissen".
- Een data-export (inzage gaat via de app zelf: profiel, favorieten, alerts).
- `auth.audit_log_entries` opschonen via SQL (de schakelaar in het dashboard is de oplossing, A13).
- Wijzigingen in `ingest/`, eigen SMTP, Auth-rate-limits en `db_usage` (WP-22).
- Een moderatie-RPC voor organisatoren (WP-22).
- De MapLibre-chunk uit de precache halen (A5).
- Nonces, `strict-dynamic`, Trusted Types, CSP-rapportage (geen rapportagedienst: geen extra dienst).
- `formatWindowLocal` en `sessionWindowText` samenvoegen (A19).
- Betaalde of externe monitoring- en testdiensten. PageSpeed Insights is niet nodig; Lighthouse draait in DevTools.

## Gevolgen voor latere WP's en orchestrator
- **WP-22:**
  - neemt `delete_my_account` mee in regel 69 van `07_sessions.test.sql` als WP-23 eerder merget;
  - werkt bij de keuze voor een SMTP-dienst de regel "De maildienst" op `/privacy` en in `docs/PRIVACY.md` bij;
  - haalt na het droppen van de telegram-kolom de regel "ongebruikte legacy-kolom" uit `docs/PRIVACY.md`;
  - opent het aanmelden (`shouldCreateUser`): `/privacy` noemt geen aanmeldbeperking, dus daar hoeft niets te veranderen.
- **Orchestrator:**
  - in WORK_PACKAGES het contractpad `scripts/check-bundle-size.mjs` → `web/scripts/check-bundle-size.mjs` (A3);
  - de drempel 150 kB plus het precachebudget van 900 kB vastleggen;
  - noteren dat `web/static/_headers` een sjabloon is (A2).
- **Elke latere WP met een nieuwe externe origin, een nieuwe tabel of kolom met persoonsgegevens, of een nieuwe `localStorage`-sleutel:** werkt `_headers`, `checkHeaders`, `/privacy` en `docs/PRIVACY.md` bij.

## Nodig van Lars
- Akkoord op de privacytekst (A15), met nadruk op de sectie "Waarom Shakka dit mag" (A23): dat is een feitelijke tekst, geen juridisch advies. Daarnaast een keuze voor `PRIVACY_CONTACT_EMAIL` (A14).
- Bewust akkoord dat deelnemers aan sessies van een verwijderd account daarna "Sessie niet gevonden" zien, zonder melding (E7, review N-11). Een alternatief, zoals anonimiseren, is een AC-wijziging.
- Bevestigen dat het Supabase-project in een EU-regio staat.
- "Write audit logs to the database" uitzetten (Authentication → Audit Logs).
- Bevestigen dat Cloudflare Web Analytics uit staat.
- Na de merge: `supabase db push` (nieuwe migratie).
- AC-6 op een preview van `develop` volgens de RUNBOOK (headers, console, Lighthouse, installeerbaarheid, account verwijderen met een testaccount).

## Stappenplan voor de builder
Werk op branch `wp/WP-23` in `/Users/larst/Dev/Shakka/.claude/worktrees/WP-23`. Lees of print `.env` en `web/.env` nooit. Draai na elke webstap vanuit `web/` `npm run check && npm test`; na stap 8, 9 en aan het eind ook `npm run build && npm run verify:build && node scripts/check-bundle-size.mjs`. Na stap 1 en aan het eind: `supabase db reset && supabase test db` (Docker nodig; lukt dat niet, meld het aan de verifier). Eén commit per stap, commitberichten in het Engels.

0. **Uitgangspunt controleren.**
   - `git merge-base --is-ancestor origin/develop HEAD` slaagt;
   - `grep -q RSVP_STORAGE_PREFIX web/src/lib/session-view.ts` en `grep -q MAP_EXTERNAL_ORIGINS web/src/lib/map/config.ts` slagen;
   - de volledige suite is groen.

   Zo niet: stop en meld het. Geen commit.
1. **Database.** Migratie (exact), `09_delete_my_account.test.sql` (23 asserties), en de twee regels in `07_sessions.test.sql`. `supabase db reset && supabase test db` is groen, en `cd ingest && uv run pytest` (volledige suite: `test_migrations.py` en `alert_fixtures.py` lezen alle migraties) is groen.
2. **`account.ts` (tests eerst).**
   - Controleer A11: `grep -n "ignore 404s" node_modules/@supabase/auth-js/dist/module/GoTrueClient.js` (of het pad onder `dist/main`). Geen treffer: `deviations.md`, en stop (R7).
   - Schrijf `account.test.ts`, daarna `account.ts`, en zet `RPC_FILES` in `user-tables.test.ts`.
3. **Account verwijderen in de UI.** `delete-account.test.ts`, `DeleteAccount.svelte`, de wijziging aan `profiel/+page.svelte`, de uitbreiding van `profile-page.test.ts`, en `.danger` en `.delete-account` in `app.css`.
4. **Privacy.**
   - Eerst A21, tests eerst: de nieuwe tests in `local-prefs.test.ts`, dan `freshReturnPath` en `pruneReturnTo` in `local-prefs.ts`; daarna de layouttest en de aanroep in `onMount` van `+layout.svelte`. Alle bestaande tests van `takeReturnTo` en van de terugkeer na inloggen blijven groen;
   - `privacy.ts` (datum invullen), `retention-consistency.test.ts`, `/privacy`, en `privacy-page.test.ts` zonder toets 4e (die volgt in stap 5);
   - de footerlink, en de links op `/over`, `/login` en in `RsvpPanel`;
   - de tekst in `Attribution` (A18) en de bijbehorende tests.
5. **`docs/PRIVACY.md`** volgens de inhoud hierboven.
   - Controleer A24 eerst op de geïnstalleerde versies:
     - `grep -c "caches.open" node_modules/maplibre-gl/dist/*.mjs` geeft overal 0, en `grep -rl "maplibre-tiles" node_modules/maplibre-gl/dist` vindt niets;
     - `grep -n "KEY = 'sveltekit:" node_modules/@sveltejs/kit/src/runtime/client/constants.js` toont `sveltekit:snapshot` en `sveltekit:history-info`.
   - Vindt de eerste grep wel iets, dan voeg je in de browsertabel een rij "Cache API (MapLibre) | `maplibre-tiles` | kaarttegels | beheerd door MapLibre" toe, en vervang je de zin onder de tabel door "MapLibre bewaart kaarttegels ook in de Cache API (`maplibre-tiles`)." De tekst op `/privacy` ("kaarttegels") dekt beide gevallen. Wijken de sleutels van SvelteKit af, dan neem je de echte namen over. Geen van beide is een ontwerpwijziging.
   - Vul de MapLibre-versie in uit `package-lock.json`;
   - voeg daarna toets 4e toe aan `privacy-page.test.ts`.
6. **Toegankelijkheid.**
   - `npm install -D axe-core@^4.14.0`;
   - helpers `axe.ts` en `contrast.ts`;
   - `a11y-compiler.test.ts`, `contrast.test.ts` en de `a11y-*.test.ts`-bestanden;
   - skiplink en `main` in de layout (met de layouttest);
   - los elke gevonden overtreding op met een kleine markup- of CSS-fix. Noem per fix de regel en het bestand in de commitboodschap. Vraagt een fix een gedrags- of ontwerpwijziging (bijv. een andere kleur dan nodig voor het contrast, of een andere structuur van een pagina), noteer het dan in `deviations.md` en stop.
7. **Service worker.** `PRECACHE_EXCLUDED_PATHS` en de filter in `precacheList`, met de test in `sw-shell.test.ts`. Deze stap moet vóór stap 8 (A6).
8. **Headers.**
   - Tests eerst: `headers.test.ts` met de pure functies;
   - daarna `write-headers.mjs`, `static/_headers` (exact), de `build`-regel in `package.json`, en `checkBuiltHeaders` in `verify-build.mjs` met de tests;
   - `npm run build && npm run verify:build` is groen. Controleer in `build/_headers` dat `connect-src` de CI- of lokale Supabase-origin bevat en `script-src` minstens één hash heeft (als `index.html` een inline script heeft).
9. **Bundelbudget.**
   - Tests eerst: `bundle-size.test.ts`;
   - daarna `check-bundle-size.mjs`, het `size`-script, en de CI-stap;
   - draai het op de echte build en noteer de drie getallen. Boven budget: `deviations.md`, en stop (A4). Meldt de echte build een modulepreload-probleem (geen links, of bestanden buiten de afsluiting), dan is dat een fout in `staticImports` of `modulepreloadFiles`: herstel de parser. Komt het door het outputformaat van kit, noteer het dan in `deviations.md` en stop.
10. **Opruimen `browserStorage`** (A19). `rsvp-storage.ts` (eigen `browserStorage` weg, `| null` wordt `| undefined`), de imports in `RsvpPanel.svelte` en `s/[slug]/+page.svelte`, en `rsvp-storage.test.ts`. Verder geen gedragswijziging; alle RSVP-tests blijven groen.
11. **RUNBOOK.** Nieuwe sectie met de gemeten getallen uit stap 9.
12. **Eindcontrole.**
    - Vanuit `web/`: `npm run check && npm test && npm run build && npm run verify:build && node scripts/check-bundle-size.mjs`;
    - vanuit de repo-root: `bash scripts/check-no-client-openmeteo.sh`;
    - `supabase test db`;
    - `cd ingest && uv run pytest` (de volledige suite, zoals CI: `test_migrations.py` en `alert_fixtures.py` lezen alle migraties, dus ook de nieuwe; geen wijziging in `ingest/`);
    - `cd ingest && uv run ruff check . && uv run ruff format --check .`.

## Verwerking review
Ronde 1 (`review.md`, CHANGES_REQUIRED).

| Punt | Wat ik deed |
|---|---|
| **B-1a** `shakka:return_to` | Code en tekst aangepast. Nieuw is `pruneReturnTo` in `local-prefs.ts`. De layout roept die bij elke app-start aan (`onMount`) en wist dan een sleutel die `takeReturnTo` niet meer zou accepteren (A21, Interfaces `local-prefs.ts`, E21-E23). De tekst op `/privacy` zegt nu: gewist zodra je inlogt; zonder inloggen na 60 minuten niet meer gebruikt en gewist bij de eerstvolgende keer dat je Shakka opent. Het woord "hoogstens" is weg. De rij in `docs/PRIVACY.md` zegt hetzelfde. Tests: `local-prefs.test.ts` (6 gevallen), `layout.test.ts` (verlopen sleutel uitgelogd gewist), `privacy-page.test.ts` 4a (eist de nieuwe formulering, weert `/hoogstens\s*\d+\s*minuten/i`) en 4e (PRIVACY.md-rij). Stappenplan stap 4. |
| **B-1b** GitHub | Tekst op `/privacy`: "profiel, favorieten, alertinstellingen, push-abonnementen en welke alerts je al kreeg". In `docs/PRIVACY.md` sectie 3: profielen, favorieten, alertregels, push-abonnementen en `alert_state`, plus wat de job schrijft (A22, gecontroleerd in `jobs/alerts.py` en `jobs/push.py`). Getoetst in `privacy-page.test.ts` 4b en 4e. |
| N-1 | A6 en E13 gecorrigeerd: `/_headers` geeft op Pages de SPA-fallback (`index.html`, 200) en geen 404. Weglaten blijft nodig, omdat het geen echt bestand is en anders `index.html` onder `/_headers` in de cache komt. Het commentaar bij `PRECACHE_EXCLUDED_PATHS` zegt nu hetzelfde. Er is geen bestaande bug, dus geen extra prioriteit. |
| N-2 | Placeholders uit het commentaar van `static/_headers` gehaald. `renderHeaders` gebruikt voorgeschreven `replaceAll` en gooit bij elke resterende `{{`, ook in commentaar. |
| N-3 | Overgenomen als kruiscontrole: `modulepreloadFiles(html, buildDir)`. De initiële JS is de vereniging van afsluiting en modulepreload-lijst. Een probleem volgt bij geen links, of bij modulepreload-bestanden buiten de afsluiting. `entry/payload` staat nu expliciet in A4 en de meetregels. Tests 7a en 7b, fixture uitgebreid. |
| N-4 | Toets 7: `randomBytes(300_000)` (±293 kB gzip), met de rekensom (base64 van willekeur ≈ 6/8). |
| N-5 | Overgenomen (kleine verduidelijking): standaardpaden zijn `<WEB_ROOT>/static/_headers`, `<WEB_ROOT>/build` en `<WEB_ROOT>/static`, met `WEB_ROOT` zoals in `verify-build.mjs`. |
| N-6 | Stap 1 en stap 12 draaien de volledige `cd ingest && uv run pytest`. Stap 12 draait ook ruff. |
| N-7 | Sectie "Waarom Shakka dit mag" toegevoegd (A23): uitvoering van de dienst die je zelf aanvraagt, meldingen pas na je eigen keuze, logs voor een veilige dienst, geen tracking en dus geen toestemmingsvraag voor cookies. Feitelijk geformuleerd, geen juridisch advies. Gemarkeerd als tekst die Lars goedkeurt ("Nodig van Lars"). Getoetst in 4c. |
| N-8 | Gecontroleerd in `node_modules`: SvelteKit 3 gebruikt `sessionStorage` (`sveltekit:history-info`, `sveltekit:snapshot`). MapLibre 6.14.0 heeft geen Cache-API-tegelcache meer; tegels van MapTiler komen hooguit in de gewone HTTP-cache. Dit staat in de inventaris van `docs/PRIVACY.md` (nieuwe browsertabel) en in één alinea op `/privacy` ("scrollpositie", "kaarttegels"). De builder controleert het opnieuw in stap 5, met een vaste uitwijkregel. Getoetst in 4d en 4e (A24). |
| N-9 | Overgenomen (één regex): anker `(?:^|\n)` vóór de constantenaam in `retention-consistency.test.ts`. |
| N-10 | Overgenomen: de rij `RsvpPanel.svelte` noemt nu ook de import van `browserStorage` (stap 10). |
| N-11 | Geen ontwerpwijziging (volgt uit AC-1, staat in E7 en de bevestigingstekst). Toegevoegd aan "Nodig van Lars" als punt om bewust te accepteren. |
| N-12 | Geen wijziging: de stopregel in stap 9 blijft het vangnet. |
