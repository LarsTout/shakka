# Review WP-23, ronde 1
Oordeel: CHANGES_REQUIRED

De blueprint is grondig en dekt AC-1 t/m AC-6. Ik heb de contracten tegen de code gecontroleerd: FK's en cascades in de migraties, `07_sessions.test.sql` regels 66-70, `rsvp-contract.test.ts`, `user-tables.test.ts`, `session-tables.test.ts`, `ingest/tests/test_migrations.py`, `local-prefs.ts`, `rsvp-storage.ts`, `push.ts`, `auth.ts`, `sw/shell.ts`, `verify-build.mjs` en `ci.yml`. Daarnaast heb ik de gebouwde output van WP-21 (`.claude/worktrees/WP-21/web/build`) bekeken. Er is één inhoudelijk blokkerend punt, in de "exacte" privacytekst die de builder niet mag aanpassen.

Wat klopt (gecontroleerd):
- **Cascades.** `profiles`, `favorites`, `alert_state`, `push_subscriptions` en `sessions.organizer_id` verwijzen met `on delete cascade` naar `auth.users`. `alert_rules` cascadeert via `favorites` en `rsvps` via `sessions`. De zelfverwijzing `rsvps_rides_with_fkey` (`on delete set null (rides_with)`) staat een cascade niet in de weg. Sessies van een verwijderde organisator verdwijnen met de aanmeldingen van anderen. Dat eist AC-1 ("sessions (met RSVP's)"), en de bevestigingstekst en E7 zeggen het eerlijk.
- **RPC.** De RPC is `security definer`, heeft `search_path = ''`, revoket van `public`, `anon`, `authenticated` en `service_role`, en grant alleen aan `authenticated`. Hij verwijdert alleen `auth.uid()`. De nieuwe migratie botst niet met:
  - de drift-regex van `rsvp-contract.test.ts` (geen RPC-namen, geen `alter table public.rsvps`);
  - `test_no_grants_on_rsvps`;
  - `test_security_definer_functions_pin_search_path`;
  - de bestandsnaamregex.

  Regel 66 (`anon`) en regel 68 (`service_role`) van `07_sessions` blijven kloppen. Ik heb 23 asserties geteld, dat klopt.
- **Inline script en hash.** `index.html` heeft precies één inline script, met `version: "<timestamp>"`. De hash verandert dus per build. Berekenen na `vite build` is daarom de juiste aanpak. Er zijn geen andere HTML-bestanden: `ssr = false`, `prerender = false`.
- **Supabase-URL in de bundel.** De Supabase-URL staat letterlijk in een `_app/immutable`-chunk (`xyD9Kncq.js`). Daar staat ook `X-Client-Info`, en die chunk zit in de modulepreload-lijst. De check van `checkBuiltHeaders` en de gezondheidscheck van `check-bundle-size` werken dus op de echte output.
- **Externe origins.** `connect-src` en `img-src` zijn volledig. De enige cross-origin `<img>` is het MapTiler-logo. Er zijn geen `fetch`, `WebSocket` of `.channel(` naar andere origins. `worker-src 'self'` klopt met `setWorkerUrl` (MapLibre-docs).
- **Bewaartermijnen.** De Python-constanten (`RETENTION`, `TIDE_RETENTION`, `EVALUATION_RETENTION`, `ALERT_STATE_RETENTION`, `SESSION_RETENTION`) bestaan met exact de vorm die de regex in `retention-consistency.test.ts` verwacht.
- **Service worker.** Er staat nu geen `_headers` of `_redirects` in `web/static/`. De SW-aanpassing repareert dus geen bestaande bug in WP-18; de volgorde stap 7 vóór stap 8 is voldoende.
- **Referrer-Policy.** `strict-origin-when-cross-origin` is de standaard van de browser. Er verandert dus niets voor de origin-check van MapTiler (WP-15 N-2).

## Blokkerend

B-1: Twee feitelijke onjuistheden in de privacytekst. Die tekst is "exact" voorgeschreven, dus de builder kan ze niet zelf herstellen.
Waar: Interfaces, `web/src/routes/privacy/+page.svelte`, secties "Op je eigen apparaat" en "Wie er nog meer iets ziet".

**(a) `shakka:return_to`.** De tekst zegt "de spot en het tijdvak, hoogstens {RETURN_TO_TTL_MINUTES} minuten". Zo werkt `local-prefs.ts` niet:
- `takeReturnTo` verwijdert de sleutel alleen als iemand inlogt (de layout roept hem aan zodra `$session` gezet is);
- de 60 minuten bepalen alleen of de waarde nog wordt *gebruikt*;
- logt de bezoeker op dat apparaat nooit in, dan blijft de sleutel onbeperkt staan.

AC-5 eist dat de bewaartermijnen overeenkomen met de implementatie. `docs/PRIVACY.md` zegt het wel correct ("Inloggen (altijd gewist), hoogstens 60 minuten geldig").

**(b) GitHub.** De tekst zegt dat de uurlijkse job "je alertinstellingen en push-abonnementen" leest. `jobs/alerts.py` leest ook het profiel (`PROFILE_COLUMNS`: `weight_kg`, `level`, `quiver_m2`, standaardgrenzen) en de favorieten. `docs/PRIVACY.md` sectie 3 noemt profielen wel. De twee documenten spreken elkaar dus tegen.

Waarom: een privacypagina die een kortere bewaartermijn belooft dan de code waarmaakt, of een verwerker minder gegevens toeschrijft dan hij krijgt, is precies wat AC-5 en de harde regel "minimale en uitlegbare persoonsgegevens" moeten voorkomen.

Voorstel:
- (a) Kies één van twee:
  - pas de tekst aan, bijvoorbeeld: "…de spot en het tijdvak, zodat je na het inloggen verder kunt. Dit wordt gewist zodra je inlogt, en na {RETURN_TO_TTL_MINUTES} minuten niet meer gebruikt.";
  - of laat de layout bij het starten een verlopen `shakka:return_to` ook zonder sessie wissen. Dat is een kleine codewijziging met een test. Dan klopt "hoogstens 60 minuten" ongeveer, namelijk tot het volgende bezoek.

  Tekst aanpassen is het eenvoudigst.
- (b) Maak er bijvoorbeeld van: "Die leest daarvoor je profiel, favorieten, alertinstellingen en push-abonnementen."
- Neem in `privacy-page.test.ts` een assertie op die de zin "hoogstens … minuten" bij `return_to` niet meer toestaat, of de nieuwe formulering eist.

## Niet-blokkerend

N-1: De onderbouwing van A6 klopt waarschijnlijk niet helemaal. Cloudflare serveert `_headers` niet als bestand. Zonder `404.html` valt `/_headers` dan door naar de SPA-fallback (`index.html`, 200), niet naar een 404. `cache.addAll` faalt dan niet, maar zet `index.html` onder `/_headers` in de cache. De fix (uitsluiten in `precacheList`) blijft juist en goedkoop. Pas alleen de tekst van A6 en E13 aan. Er is geen bestaande bug in WP-18 (zie boven), dus geen extra prioriteit nodig.

N-2: De commentaarregel in het sjabloon `web/static/_headers` bevat zelf `{{SUPABASE_ORIGIN}}` en `{{SCRIPT_HASHES}}`. Gebruikt de builder `String.prototype.replace` (alleen het eerste voorkomen), dan vervangt hij de placeholder in het commentaar en blijft die in de CSP staan. `renderHeaders` gooit dan wel, maar het kost zoektijd. Schrijf `replaceAll` voor, of haal de placeholders uit het commentaar (bijvoorbeeld "fills in the two placeholders").

N-3: Er is een eenvoudiger of extra bron voor "initiële JS". In de WP-21-build somt `index.html` met `<link rel="modulepreload">` precies de statische afsluiting op: `entry/start`, `entry/payload`, `entry/app`, `nodes/0` en 12 chunks. Je kunt die lijst als bron gebruiken, of als kruiscontrole op `importClosure`: dezelfde verzameling, anders een melding. Dat maakt de meting minder afhankelijk van de import-regex. Let ook op `entry/payload.*.js`, die de blueprint niet noemt. Hij valt onder "alle `.js` in `entry/`" en telt dus terecht mee.

N-4: AC-3 toets 7 zegt dat 160.000 willekeurige bytes als base64 "±213 kB gzip" geven. Dat klopt niet. Base64 van willekeurige data comprimeert tot ongeveer 6/8, dus ±160.000 bytes, ongeveer 156 KiB. Dat ligt nog boven 150 KiB, maar de marge is klein. Neem `randomBytes(300_000)` en pas het getal in de tekst aan.

N-5: "standaard `web/static/_headers`" en "standaard `web/build`" zijn dubbelzinnig, omdat de scripts vanuit `web/` draaien (A3). Schrijf "`<WEB_ROOT>/static/_headers` en `<WEB_ROOT>/build`", net als `verify-build.mjs` met `WEB_ROOT` doet.

N-6: Stap 12 draait alleen `tests/test_repo_hygiene.py`. `ingest/tests/test_migrations.py` en `alert_fixtures.py` lezen alle migraties, dus draai na het toevoegen van een migratie de volledige `cd ingest && uv run pytest`. CI doet dat ook.

N-7: In de privacytekst ontbreekt de grondslag van de verwerking (AVG art. 13): bijvoorbeeld de overeenkomst voor het account, gerechtvaardigd belang voor logs en toestemming voor push. De AC eist het niet, en Lars keurt de tekst toch goed (A15). Één zin volstaat.

N-8: De inventaris "op je apparaat" is niet volledig. Er staan geen persoonsgegevens in, maar voor een complete inventaris:
- SvelteKit gebruikt `sessionStorage` (`sveltekit:scroll`, `sveltekit:snapshot`);
- MapLibre heeft (in eerdere versies zeker) een tegelcache via de Cache API (`maplibre-tiles`). Die valt niet onder `shakka-shell-*` en wordt dus niet opgeruimd door `onActivate`.

Laat de builder dit controleren en één regel opnemen in `docs/PRIVACY.md`, en eventueel ook "en kaarttegels" op `/privacy`.

N-9: Zet in `retention-consistency.test.ts` een anker voor de naam, bijvoorbeeld `(?:^|\n)` + naam. Dan kan `RETENTION` niet per ongeluk in `TIDE_RETENTION` of `SESSION_RETENTION` matchen als bestanden ooit worden samengevoegd.

N-10: In de bestandentabel noemt de rij `RsvpPanel.svelte` alleen de privacylink. Stap 10 (A19) wijzigt daar ook de import van `browserStorage`. Zet beide in de rij.

N-11: Na een geslaagde verwijdering zien deelnemers van de sessies van de organisator "Sessie niet gevonden", zonder melding. Dat volgt uit AC-1 en staat in E7 en de bevestigingstekst. Ik noem het alleen zodat Lars het bewust accepteert. Een alternatief, zoals sessies anonimiseren in plaats van verwijderen, zou een AC-wijziging zijn.

N-12: De budgetten (A4) kon ik niet meten: er staan geen bestandsgroottes in de repo, en ik kan niet bouwen. Uit de chunkverdeling in de WP-21-build (supabase-js in één preload-chunk, MapLibre en zijn worker apart in `chunks/` en `workers/`) lijken 150 kB initieel en 900 kB precache haalbaar. De stopregel in stap 9 dekt het risico voldoende af.

## Gecontroleerde bronnen
- https://developers.cloudflare.com/pages/configuration/headers/ (`_headers` wordt niet als asset geserveerd; 100 regels en 2.000 tekens per regel; bij meerdere matches erft een verzoek alle headers en worden dubbele headers met komma's samengevoegd; `#`-commentaar; geen toepassing op Functions; redirects gaan vóór headers; SPA-fallback wordt niet genoemd, R2 terecht)
- https://svelte.dev/docs/kit/configuration#csp (CSP via `<meta>` bij prerendering; `frame-ancestors` wordt daar genegeerd)
- https://supabase.com/docs/guides/auth/audit-logs (schakelaar "Write audit logs to the database" onder Authentication → Audit Logs; velden `ip_address` en `user_agent`)
- https://supabase.com/pricing (gratis plan: API- en databaselogs 1 dag, Auth Audit Logs 1 uur)
- https://supabase.com/changelog/34270-restricting-access-on-auth-storage-and-realtime-schemas-on-april-21-2025 (DML-beperking alleen op migratietabellen; foreign keys, triggers en RLS op `auth.users` toegestaan)
- https://registry.npmjs.org/axe-core/latest (4.14.0, MPL-2.0, typings aanwezig)
- https://maplibre.org/maplibre-gl-js/docs/#csp-directives (`worker-src 'self'`; `img-src data: blob: 'self'`; `setWorkerUrl` voor een strikte CSP)
