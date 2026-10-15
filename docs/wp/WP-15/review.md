# Review WP-15, ronde 2
Oordeel: APPROVED

Beoordeeld: `docs/wp/WP-15/blueprint.md`, revisie 2, op branch `wp/WP-15` (gerebased op `develop` met WP-16). Gecontroleerd tegen de code in deze worktree: `web/src/routes/+page.svelte`, `web/test/spot-list.test.ts`, `web/test/helpers/fake-favorites.ts` en `fake-session.ts`, `web/test/fixtures/spot-data.ts`, `web/src/lib/types.ts`, `labels.ts`, `app.css`, `env.ts`, `env-schema.ts`, `web/vite.config.ts`, `web/scripts/verify-build.mjs`, `web/test/no-third-party.test.ts`, `web/test/env-example.test.ts` en `docs/RUNBOOK.md` (§4, §11).

## Status van de punten uit ronde 1
- **B-1 is opgelost.**
  - De vier tekstankers in `+page.svelte` kloppen met de huidige versie. De import van `Freshness` staat op regel 5, `$props()` op regel 10, `<Freshness …/>` op regel 39 en `<ul class="spot-list">` op regel 40. `FavoriteStar` binnen `li.spot-item` blijft ongemoeid.
  - `app.css` geeft `.spot-list` geen `display`, dus het attribuut `hidden` werkt.
  - Het blok "Paginatests" neemt de mocks letterlijk over uit `spot-list.test.ts`: `$app/navigation`, de gooiende `#lib/supabase.js` en `#lib/favorites.js` via `fake-favorites.js`, plus `favoritesState.set({ status: 'signed_out' })` in `beforeEach`. Dat geldt voor `map-switch` en `home-no-map`. De enige andere test die de pagina rendert is `spot-list.test.ts` (`layout.test.ts` rendert alleen de layout).
  - RUNBOOK §11.8 is bezet door WP-16 en §11.9 is vrij. AC-6, stap 10 en "Nodig van Lars" verwijzen naar §11.9, en er is een terugval als het nummer na een rebase toch bezet is.
- **N-1 (R2):** de drie voorwaarden staan letterlijk in R2 en in stap 9: (e) `deviations.md`, (d) een extra brontest voor `runtime` en (f) een melding aan Lars via de orchestrator. Ook de aanpassingen aan `map-source` (a)–(c) en (g) zijn uitgewerkt.
- **N-5:** alleen een `error` vóór `style.load` is fataal. Daarna geeft een fout één `console.warn` en geldt de time-out van 30 s. Dat is consistent in `start.ts` 5g–5i, E8, E24, R10 en `map-start` (7a), (7b) en (9). Ik heb `style.load` zelf gecontroleerd in `MapEventType`.
- **N-6:** het `$effect` leest `spots` en `summaries` onvoorwaardelijk. `map-view` (8) dekt de rerender: markers vervangen, `maps.length === 1`.
- **N-7:** `home-no-map` mockt altijd `$app/env/public` met een niet-lege key en gebruikt de echte `platform.ts`. Voor `spot-list.test.ts` staat er een vangnet van precies één regel plus een notitie in `deviations.md` (stap 7).
- **N-10:** de opzet met twee keys staat consequent in A4, R1, R7, stap 10 (§4-rij en §11.9), "Nodig van Lars", "Gevolgen" en het commentaar in `.env.example`. Dat past bij de MapTiler-docs: geen localhost op een productiekey, aparte keys per omgeving, localhost zonder poort en protocol.
- **N-2, N-8, N-9, N-11 en N-12** zijn verwerkt.
  - Fixtures: ik heb `SUMMARY_*` gecontroleerd tegen `SpotSummary`/`DaySummary`, en de bounds `[[4.15, 52.05], [4.62, 52.52]]` tegen de coördinaten in `spot-data.ts`.
  - `data-marker-spot` staat in de markerspec en in de tests.
  - `map-source` heeft check (g).

## Blokkerend
Geen.

## Niet-blokkerend
N-1: De positieve helft van `checkLazyMapLibre` is zwak, en er is een klein risico op een vals alarm. `config.ts` bevat `maplibre.org` (`MAPLIBRE_URL`, `MAPLIBRE_ATTRIBUTION`). De page-chunk van `/` bevat dus altijd de tekst `maplibre`, ook als de echte MapLibre-chunk ontbreekt. Andersom: komt `config.ts` ooit in een entry-chunk terecht, dan faalt de check zonder dat MapLibre zelf eager geladen wordt. De terugval in stap 8 (`MapView` lui maken) helpt dan niet, omdat `MapSwitch` `config.ts` ook importeert. Dat gebeurt niet als SvelteKit de page-nodes gewoon buiten `entry/` zet, en de AC-greps zijn letterlijk zo geformuleerd. Wil de builder het steviger: laat de positieve check ook zoeken naar een bestand met `maplibre-gl` in de naam, of naar `setWorkerUrl` in de inhoud. Noteer dat dan in `deviations.md`.

N-2: R7 en "Gevolgen" (WP-23) zeggen dat de origin-restrictie van MapTiler naar de `Origin`-header kijkt, niet naar de Referer. De pagina "how to protect your map key" zegt dat bij mijn controle nu niet expliciet. Er staat alleen "List the domains your app runs on". Voor deze WP maakt het niet uit. WP-23 moet het wel zelf testen voordat het een strengere `Referrer-Policy` zet (bijvoorbeeld `no-referrer`), anders kan de kaart dan op 403 lopen.

N-3: `startMap` heeft geen time-out op `deps.load()` (de chunk-`import()`). De timer start pas na `new Map`. Hangt de chunk-download heel lang zonder te falen, dan blijft "Kaart laden…" staan tot de gebruiker op "Lijst" klikt. Dat mag; de lijst blijft altijd bereikbaar.

N-4: Ronde 1 kon niet bevestigen dat `streets-v4` in het gratis plan zit (R5). Dat blijft zo. De rooktest met de lokale key in stap 8 en AC-6 brengen het aan het licht, en de fallback naar `load_failed` werkt.

## Gecontroleerde bronnen
- https://maplibre.org/maplibre-gl-js/docs/ (huidige versie 6.14.0; Vite: `import workerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url'`, `setWorkerUrl(workerUrl)`, `import 'maplibre-gl/dist/maplibre-gl.css'`)
- https://maplibre.org/maplibre-gl-js/docs/API/type-aliases/MapEventType/ (`style.load` met `MapStyleLoadEvent`, `load` en `error` met `ErrorEvent`, plus de beschrijvingen)
- https://docs.maptiler.com/guides/maps-apis/maps-platform/how-to-protect-your-map-key/ ("Never leave this rule on a key used in production"; localhost "matches any machine, including an attacker's"; "Keep the keys for staging and production separate"; `localhost`/`127.0.0.1` zonder poort en protocol)
