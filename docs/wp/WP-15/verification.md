# Verificatie WP-15, ronde 1
Resultaat: NEEDS_LARS

Alle criteria die zonder account te toetsen zijn, zijn PASS. Alleen AC-6 (echte MapTiler-key, gedeployde site) is NEEDS_LARS, zoals bedoeld.

| Criterium | Resultaat | Bewijs |
|---|---|---|
| AC-1 | PASS | In `web/`: `npm ci`, `npm run check` (0 errors, 0 warnings), `npm test` (48 bestanden, 492 tests groen), `npm run build` en `npm run verify:build` ("verify-build: ok"), zowel zonder `PUBLIC_MAPTILER_KEY` als met `PUBLIC_MAPTILER_KEY=dummykey12345`. `bash scripts/check-no-client-openmeteo.sh` geeft "ok". Ingest: `uv run pytest` 1550 passed, 24 skipped (lokale-Supabase-tests); `ruff check` en `ruff format --check` schoon. CI op `wp/WP-15`: laatste run `success`. |
| AC-2 | PASS | `grep -rl maplibre web/build/_app/immutable/entry/` geeft niets (exit 1). `grep -rl maplibre build/_app/immutable` vindt `chunks/CV15SaqY.js`, `workers/maplibre-gl-worker-*.js`, de maplibre CSS en de page-chunk `nodes/2.*.js`. `getWorkerCount` staat alleen in `chunks/CV15SaqY.js`, de echte bibliotheek. `checkLazyMapLibre` matcht op `setWorkerUrl` én `getWorkerCount` buiten `entry/`, niet op `maplibre.org`; `verify-build.test.ts` heeft het tegenvoorbeeld en is groen. In de bron: `grep -rn "maplibre-gl" web/src` buiten `platform.ts` geeft niets. In `platform.ts` staan alleen `typeof import('maplibre-gl')` (type, wordt gewist) en drie dynamische `import()`-aanroepen binnen `Promise.all`. `map-source.test.ts` (a)-(g) bewaakt dit en is groen. |
| AC-3 | PASS | `test/home-no-map.test.ts` rendert `/` zonder interactie met een niet-lege key en een `vi.mock('maplibre-gl')`-probe. Geen import (`probe.imported === false`), `fetch` niet aangeroepen, geen `maptiler`-elementen, geen `.map-canvas`. Echte `platform.ts` (niet gemockt). Groen. |
| AC-4 | PASS | `test/map-switch.test.ts`: zonder key geeft "Kaart" een `role="status"`-melding (`no_key`), blijft de lijst zichtbaar (geen `hidden`) en bruikbaar. Ook `no_webgl` en `load_failed` zijn gedekt. Groen. De code (`MapSwitch.svelte`, `preflight`) bevestigt het gedrag: de knop blijft staan, de melding komt bij de klik, `view` valt terug op `list`. |
| AC-5 | PASS | `start.ts` geeft `attributionControl: { compact: false, customAttribution: MAPLIBRE_ATTRIBUTION }` mee (altijd uitgeklapt). Daarnaast staat in `MapView.svelte` een zichtbare regel met links "© MapTiler", "© OpenStreetMap contributors" en "MapLibre", plus het MapTiler-logo (`alt="MapTiler logo"`) zodra de kaart klaar is. `map-source` (e) en `map-start`/`map-view` toetsen dit en zijn groen. Er is geen CSS die de controls verbergt. |
| AC-6 | NEEDS_LARS | Echte MapTiler-key nodig en een gedeployde site. Lars: twee keys aanmaken (productie met alleen het Pages-domein, lokaal met localhost), `PUBLIC_MAPTILER_KEY` in Cloudflare Pages zetten (RUNBOOK §11.9), op `/` klikken op "Kaart" en markers met de juiste oordelen controleren. Na een week het aantal requests in MapTiler Analytics bekijken. |

## Harde regels
- Geen secrets in de diff: PASS. `web/.env` is gitignored en niet getrackt (de lokale `PUBLIC_MAPTILER_KEY` is leeg). `.env.example` bevat alleen een lege waarde. De key wordt niet gelogd (`start.ts` logt alleen een vaste tekst, nooit het event of de style-URL).
- Geen client-side Open-Meteo: PASS. `check-no-client-openmeteo.sh` ok; in `web/src` komt `open-meteo` alleen voor in `Attribution.svelte` (bronvermelding).
- MapLibre alleen via npm: PASS. `maplibre-gl ^6.14.0` in `package.json`. Geen `<script src>` naar extern in `build/index.html` (alleen inline `<script>`). Geen treffers op `unpkg|jsdelivr|cdnjs|telemetry|events.maptiler` in `web/src` en `web/build`. `verify:build` (externe scripts en tracker-markers) is ok.
- Geen MapTiler-SDK of telemetrie: PASS. `grep "@maptiler|maptiler-sdk"` in `web/src`, `package.json` en `package-lock.json` geeft niets.
- Bronvermelding intact: PASS. `Attribution.svelte` (Open-Meteo e.d.) ongewijzigd; MapTiler, OSM en MapLibre zijn toegevoegd.
- Geen scraping, geen nieuwe betaalde dienst: PASS. MapTiler gratis tier, zonder key degradeert de app; RUNBOOK vermeldt het gratis quotum.
- Offshore altijd `no_go`: PASS. De diff raakt de evaluatielogica niet; de markers tonen alleen het bestaande oordeel uit `summaries`.
- Geen tracking: PASS (zie bovenstaande greps).

## Overige controles
- Lui laden en degradatie: zonder key, zonder WebGL2 en bij een laadfout valt de app terug op de lijst met een Nederlandse melding (`MAP_FAILURE_MESSAGE_NL`). Een `error` vóór `style.load` is fataal; daarna geeft het één `console.warn` (`start.ts`, getoetst in `map-start.test.ts`, groen). Een time-out van 30 s geldt. De lijst blijft altijd bereikbaar: de knop "Lijst" is er altijd, en `ul.spot-list` krijgt alleen `hidden` (geen `display`-regel in `app.css` die dat overschrijft).
- Ongeldige key: `PUBLIC_MAPTILER_KEY='a b' npm run build` faalt (exit 1) met "PUBLIC_MAPTILER_KEY must be a MapTiler API key (8-128 letters, digits, - or _)", zonder de waarde te tonen (`grep -c "a b"` op de uitvoer geeft 0). Een lege waarde bouwt.
- Rooktest: `vite preview` plus `curl`: pagina `/`, `_app/immutable/chunks/CV15SaqY.js`, `_app/immutable/assets/maplibre-gl.*.css` en `_app/immutable/workers/maplibre-gl-worker-*.js` geven alle vier 200. Echte browser-rooktest is niet uitgevoerd (geen browserautomatisering in de repo, genoteerd in `deviations.md`).
- Diff versus blueprint: ongedocumenteerde afwijkingen: geen. `deviations.md` vermeldt de afwijkingen (strengere positieve check in `checkLazyMapLibre`, `env.ts`-correctie, één `vi.mock` in `spot-list.test.ts`, geen browser-rooktest).
- `+page.svelte`: precies de vier geplande regels (import `MapSwitch`, `let view`, `<MapSwitch … bind:view />`, `hidden={view === 'map'}`). `FavoriteStar` is ongewijzigd (alleen `spot-list.test.ts` kreeg één mock-regel).
- Scope: alle gewijzigde bestanden vallen onder `web/` (kaartcode, env, tests, verify-build) of `docs/` (RUNBOOK §11.9, STATUS, `docs/wp/WP-15/`). Geen wijzigingen in `ingest/`, `supabase/`, `data/` of `.github/`. Het werkboom is schoon.

## Problemen
Geen blokkerende problemen.

O-1 (NEEDS_LARS): AC-6, zie de tabel hierboven.
