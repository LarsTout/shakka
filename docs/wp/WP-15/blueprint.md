# Blueprint WP-15: Kaart
Status: DRAFT
Revisie: 2

## Doel
Op `/` komt naast de spotlijst een kaartweergave van de spots, met per spot een marker met het oordeel als tekst en kleur. Een klik op een marker opent de spotpagina. De kaart start pas als de gebruiker op "Kaart" klikt. Vóór die klik wordt er geen MapLibre-code uitgevoerd en gaat er geen enkel request naar MapTiler. (De service worker van WP-13 downloadt de MapLibre-chunk wel mee bij het precachen van een nieuwe versie, zonder hem uit te voeren; zie A9.) De lijst blijft de standaard. Zonder key, zonder WebGL2 of bij een storing bij MapTiler valt de app terug op de lijst, met een Nederlandse melding. De attributie van MapTiler, OpenStreetMap en MapLibre en het MapTiler-logo zijn zichtbaar.

Deze WP voegt vooral code toe. Wijzigingen aan bestaande bestanden zijn klein. Basis is `develop` met WP-16 (`FavoriteStar` op de lijst, `#lib/favorites.js`, `#lib/user-data.js`, RUNBOOK §11.8). WP-12 kan later via een rebase binnenkomen (golfregel op de spotpagina, `test/fixtures/spot-data.ts`, RUNBOOK §15 en tekst in §11.7). Deze WP raakt die plekken niet.

## Verwerking review
Ronde 1 (`review.md`): CHANGES_REQUIRED, met één blokkerend punt en dertien niet-blokkerende.

| Punt | Verwerking |
|---|---|
| **B-1** Verouderde basis (WP-16) | De orchestrator heeft `wp/WP-15` op `develop` gerebased. Er is dus geen stap 0 "develop mergen" meer. (a) `map-switch.test.ts` en `home-no-map.test.ts` renderen `+page.svelte` en mocken nu ook `#lib/favorites.js`, precies zoals `spot-list.test.ts` op `develop`: `vi.mock('#lib/favorites.js', async () => (await import('./helpers/fake-favorites.js')).favoritesModule)` plus `favoritesState.set({ status: 'signed_out' })` in `beforeEach` (Testplan, inleiding en tabel). (b) Het RUNBOOK-punt is vast §11.9, en AC-6, stap 10 en "Nodig van Lars" verwijzen daarnaar. (c) De vier wijzigingen in `+page.svelte` zijn gecontroleerd tegen de huidige versie: `<Freshness … />` staat op regel 39 en `<ul class="spot-list">` op regel 40. `FavoriteStar` binnen `li.spot-item` blijft ongewijzigd (Interfaces). "Gevolgen" en R8 zijn bijgewerkt. |
| N-1 (R2) | De terugvaloptie staat in R2 en in stap 9 met de drie voorwaarden van de reviewer, letterlijk: `deviations.md`, een extra brontest in `map-source.test.ts` dat `runtime` in `src/` alleen binnen `import(…)` voorkomt, en een melding aan Lars via de orchestrator. |
| N-2 (budget) | A2 aangepast: alleen tiles tellen (vector 1 per tile, raster 512 px 4 per tile). Style, TileJSON en glyphs zijn gratis. Het worst case met een rasterbron (hillshade) staat erbij. De tekst voor WORK_PACKAGES onder "Gevolgen" is aangepast. |
| N-3, N-4, N-13 | Geen actie nodig (bevestigingen). |
| **N-5** (`error` vóór `load`) | Overgenomen. Alleen een `error` vóór `style.load` is fataal (style 401/403: key, origin, quotum). Daarna, ook vóór `load`, geeft een fout één `console.warn`, en de time-out van 30 s blijft gelden. `start.ts` stap 4g/4h, E8, E24 en `map-start` (7a), (7b) en (9) zijn aangepast. Het event `style.load` is gecontroleerd in `MapEventType`. |
| **N-6** (`$effect`) | Overgenomen. Het effect leest `spots` en `summaries` onvoorwaardelijk, vóór `controller?.update(…)`. `map-view.test.ts` (8) doet een `rerender` met nieuwe `summaries` na `load`: de markers worden vervangen en er komt geen tweede `Map`. |
| **N-7** (`$app/env/public` in vitest) | Overgenomen en vastgelegd. `home-no-map.test.ts` mockt altijd `$app/env/public` met `{ PUBLIC_MAPTILER_KEY: 'testkey123' }` en mockt `platform` niet. Zo draait de echte `platform.ts` met `loadMapLibre`, onafhankelijk van `web/.env` of van het resolven van de virtuele module. Er staat bewust een niet-lege key in: AC-3 hangt dan niet af van een ontbrekende key. Omdat `+page.svelte` via `MapSwitch` nu `platform.ts` importeert, laadt ook de bestaande `spot-list.test.ts` `$app/env/public`. Faalt die test daarop, dan krijgt hij precies één extra regel, `vi.mock('$app/env/public', () => ({ PUBLIC_MAPTILER_KEY: '' }))`, plus een notitie in `deviations.md` (stap 7). |
| **N-8** (fixtures) | Overgenomen. `SUMMARY_GO` en `SUMMARY_TOMORROW` staan volledig in het Testplan, met `spot_id`, alle velden van `today` en `tomorrow` en `latest_evaluated_at: EVALUATED_AT`. |
| **N-9** (Doel en A9) | Overgenomen. Het Doel zegt nu "geen MapLibre-code uitgevoerd en geen MapTiler-request". A9 en "Gevolgen" (WP-23) noemen het datavolume van de precache expliciet: ±250 kB gzip (±800 kB onverpakt) per installatie per nieuwe versie. |
| **N-10** (localhost) | Overgenomen, zoals de orchestrator besliste. Op de productiekey staat geen `localhost` en geen `127.0.0.1`. Lokaal komt een aparte key met origin `localhost`/`127.0.0.1`, alleen in `web/.env`. Vastgelegd in stap 10 (RUNBOOK §4 en §11.9), "Nodig van Lars", R7 en "Gevolgen" (tekst voor WORK_PACKAGES). De restrictie kijkt naar de origin van het verzoek, niet naar de Referer (R7 aangepast). |
| **N-11** (`data-spot`) | Overgenomen. De marker krijgt `data-marker-spot` in plaats van `data-spot`. `[data-spot="…"]` vindt daardoor altijd `li.spot-item`. |
| **N-12** (type-import) | Overgenomen. `map-source` (a) noemt `export type MapLibre = typeof import('maplibre-gl')` in `platform.ts` als de enige niet-runtime-treffer. Nieuwe check (g) telt precies één `typeof import(` en precies vier `maplibre-gl`-literals in `platform.ts`. |

## Aannames
Voorstellen waar Lars op kan reageren, staan als **Voorstel**.

- **A1. MapLibre GL JS v6 rechtstreeks, niet de MapTiler SDK.** `maplibre-gl` ^6.14.0 komt als npm-package in de bundel, dus geen CDN. De MapTiler SDK zet standaard telemetrie aan (`config.telemetry`, default `true`; verstuurt onder andere de API-key, de sessie-id en de SDK-versie). Dat botst met "geen tracking". De SDK is bovendien een extra laag bovenop MapLibre.
- **A2. Gevolg van A1 voor het budget: MapTiler rekent dan in API-requests, niet in map sessions.** Op de prijspagina staat: "Tile API Requests are billed for usage of MapTiler maps with third-party SDKs". Het gratis plan heeft 100.000 requests per maand (naast 5.000 sessions voor de SDK). Daarna wordt het gepauzeerd tot de volgende maand, zonder kosten. Volgens de vergelijkingspagina van MapTiler tellen alleen tiles: een vectortile is 1 request, een rastertile van 512 px telt als 4. Style-JSON, TileJSON en fonts (glyphs) zijn gratis.
  - Schatting per keer dat de kaart opent, met wat pannen en zoomen: ±10–40 vectortiles, dus ±10–40 requests. Dat is ruim 2.500 keer openen per maand.
  - Heeft `streets-v4` een rasterbron (bijvoorbeeld hillshade), dan komen daar per keer ±10–40 × 4 requests bij. Worst case is dat ±200 requests per keer, dus ±500 keer openen per maand.
  - Bij tientallen gebruikers die de kaart een paar keer per week openen, gaat het om enkele honderden keren per maand. De HTTP-cache van de browser haalt daar nog wat af. Lars controleert het werkelijke verbruik in het dashboard (AC-6).

  De regel "MapTiler gratis" in "Gecontroleerde externe documentatie" (WORK_PACKAGES) noemt alleen sessions. Die moet de orchestrator bijwerken (zie "Gevolgen").
- **A3. Voorstel: stijl `streets-v4`** (`https://api.maptiler.com/maps/streets-v4/style.json?key=…`, het voorbeeld in de MapTiler-docs voor MapLibre). Een andere stijl kiezen kost één constante (`MAPTILER_STYLE_ID`).
- **A4. De key is optioneel en publiek.** `PUBLIC_MAPTILER_KEY` komt in `src/env.ts` met `public: true, static: true` en wordt dus bij de build in de bundel gezet. Het is geen secret. Lars beperkt de productiekey in MapTiler Cloud met "Allowed HTTP origins", alleen voor het Pages-domein. Lokaal gebruikt hij een aparte key (N-10, RUNBOOK §11.9).
  - Ontbreekt de key of is hij leeg, dan is de waarde `''` en geeft de kaartwissel de melding "niet beschikbaar". De build slaagt gewoon.
  - Een key met andere tekens dan `A–Z a–z 0–9 _ -`, of met een lengte buiten 8–128, laat de build falen met een melding zonder de waarde. Dat volgt het patroon van WP-13.
- **A5. De weergavekeuze wordt niet onthouden.** Elke keer dat `/` opnieuw opent, ook via de terugknop vanaf een spotpagina, staat de lijst er weer. Er is geen `localStorage` en geen snapshot. Zo opent de kaart alleen na een bewuste klik, en dat houdt het aantal requests laag.
- **A6. Voorstel: wat een marker toont.** De marker toont de naam van de spot plus een oordeelsbadge (dezelfde `.verdict-*`-kleuren en labels als de lijst):
  - `today.best` als die er is (bijvoorbeeld "Go");
  - anders, na zonsondergang, `tomorrow.best` met het voorvoegsel "Morgen: " (bijvoorbeeld "Morgen: Twijfel");
  - anders een grijze badge "Nog geen data".

  Een niet-geverifieerde spot krijgt een gestippelde rand plus de verborgen tekst " (niet geverifieerd)" voor schermlezers. Onder de kaart staat een legenda.
- **A7. Een spot zonder bruikbare coördinaten staat niet op de kaart.** Dat geldt als `lat` of `lon` `null` is, niet eindig, of buiten het bereik valt. Onder de kaart staat dan "N spots zonder coördinaten staan niet op de kaart." Er worden geen coördinaten verzonnen.
- **A8. De attributie staat twee keer, zodat ze in elk geval klopt.**
  - Op de kaart: de `AttributionControl` van MapLibre met `compact: false` (altijd uitgeklapt). Daarin staat de attributie uit de MapTiler-bronnen, plus `customAttribution` met de standaardtekst van MapLibre.
  - Onder de kaart, door Svelte gerenderd en dus te testen: "Kaart: © MapTiler · © OpenStreetMap contributors · MapLibre", met links.
  - Het MapTiler-logo staat linksonder, volgens de HTML van MapTiler voor het gratis plan. Het verschijnt pas als de kaart geladen is, zodat er bij een fallback ook geen logo-request is.
- **A9. Alleen MapLibre's eigen `import()`-chunks, geen nieuwe precache-regels.** De service worker van WP-13 precachet alle `_app/immutable`-bestanden, dus ook de MapLibre-chunk (±800 kB, ±250 kB gzip, same-origin, geen MapTiler-request).
  - Elke installatie downloadt die chunk dus één keer per nieuwe versie van de app, ook wie nooit op "Kaart" klikt. De chunk wordt dan niet uitgevoerd.
  - Dat laten we zo. Oude shell en oude chunks blijven zo bij elkaar passen (WP-13 A7): zonder precache faalt `import()` na een nieuwe deploy op een oude chunknaam.
  - Of dit datavolume binnen het performancebudget past, beoordeelt WP-23 (zie "Gevolgen").
- **A10. MapLibre v6 vraagt `setWorkerUrl` bij bundlers.** De MapLibre-docs geven voor Vite precies `import workerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url'`, gevolgd door `setWorkerUrl(workerUrl)`. Wij doen dat met een dynamische `import()` van dezelfde specifier (zie R2).
- **A11. Geen geolocatie, geen clustering, geen popups.** De marker is zelf een link naar `/spot/<id>`.
- **A12. Markers gebruiken `data-marker-spot`, niet `data-spot`.** `data-spot` blijft uniek voor `li.spot-item` (WP-14, WP-16), zodat `[data-spot="…"]` in paginatests altijd het lijstitem vindt, ook als de kaart open is.

## Ontwerp

**Lagen.**
```
+page.svelte ──> MapSwitch.svelte (wissel, melding)  ──> MapView.svelte (container, logo, attributie)
                        │                                     │
                        └── #lib/map/config.ts (puur) <───────┤
                        └── #lib/map/platform.ts  <───────────┤  (key, WebGL2-check, lazy loader: de enige plek met import('maplibre-gl'))
                                                              └── #lib/map/start.ts (orkestratie; MapLibre geïnjecteerd)
                                                                     └── #lib/map/markers.ts (marker-modellen, DOM-element, startbeeld)
```
- `config.ts` is puur: constanten, URL's, meldingen en `preflight`.
- `markers.ts` is puur, op `createMarkerElement` na (DOM via `document.createElement` en `textContent`, nooit `innerHTML`).
- `start.ts` bevat de hele levenscyclus: preflight, laden, kaart maken, `style.load`/`load`/`error`, time-out, markers, opruimen. MapLibre komt binnen als dependency (`load()`), dus alle faalpaden zijn te testen met een nep-MapLibre, zonder WebGL.
- `platform.ts` is het enige bestand dat `$app/env/public` voor de kaart leest, een WebGL2-context maakt en MapLibre importeert. Componenttests mocken dit ene bestand. Alleen `home-no-map.test.ts` gebruikt het echte bestand.

**Lui laden.** `maplibre-gl`, de worker-URL en de CSS staan in de bron alleen als dynamische `import()` in `platform.ts`. Daar staat ook het type `MapLibre = typeof import('maplibre-gl')`. Dat verdwijnt bij het compileren en is de enige niet-runtime-treffer (N-12). `start.ts` importeert alleen dat type uit `platform.ts`. `loadMapLibre()` wordt pas aangeroepen als `MapView` mount. Dat gebeurt alleen nadat iemand op "Kaart" heeft geklikt en de preflight (key, WebGL2) gelukt is. Vite zet MapLibre daardoor in een eigen chunk buiten `_app/immutable/entry/`. `verify:build` controleert dat na elke build.

**Wissel.** `MapSwitch` toont twee knoppen ("Lijst", "Kaart") met `aria-pressed`. De pagina bindt `view` en verbergt de `<ul class="spot-list">` met het attribuut `hidden` zolang `view === 'map'`. De lijst, inclusief de favorietensterren van WP-16, blijft dus in de DOM. De wijziging aan `+page.svelte` is vier regels.

**Fouten.** Bij elke fatale fout gaat `view` terug naar `'list'` en verschijnt er een melding met `role="status"`. De fatale fouten:
- preflight: geen key, geen WebGL2;
- laden van de chunk;
- de constructor van de kaart gooit een fout (`GPUInitializationError` geeft `no_webgl`);
- een `error`-event vóór `style.load`, bijvoorbeeld een style die 401/403 geeft door een foute key, de origin-restrictie of het quotum;
- geen `load` binnen 30 s.

Een `error` na `style.load` (een losse tile of sprite, ook tijdens het eerste beeld op een slecht mobiel netwerk) geeft alleen één `console.warn` zonder details. De kaart blijft dan staan. Komt `load` daarna nooit, dan grijpt de time-out in (N-5).

**Waarom zo.** Alle beslislogica is puur of krijgt haar dependencies binnen, dus AC-3, AC-4 en AC-5 zijn zonder netwerk en zonder WebGL te toetsen. AC-2 wordt twee keer bewaakt: in de bron (vitest) en in de build (`verify:build`, draait al in CI). De wijzigingen aan gedeelde bestanden zijn klein:
- vier regels in `+page.svelte`;
- één variabele in `env.ts` en `.env.example`;
- één functie in `env-schema.ts`;
- één check in `verify-build.mjs`.

## Bestanden

| Pad | Actie | Inhoud |
|---|---|---|
| `web/package.json`, `web/package-lock.json` | wijzigen | `npm install maplibre-gl@^6.14.0` (in `dependencies`). Verder niets. |
| `web/src/env.ts` | wijzigen | Variabele `PUBLIC_MAPTILER_KEY` erbij (zie Interfaces). |
| `web/src/lib/env-schema.ts` | wijzigen | `parseMaptilerKey` erbij; de bestaande functies blijven ongewijzigd. |
| `web/.env.example` | wijzigen | Twee regels erbij (commentaar en `PUBLIC_MAPTILER_KEY=`). |
| `web/src/lib/map/config.ts` | aanmaken | Constanten, URL's, `MapFailure`, `ViewMode`, meldingen, `mapStyleUrl`, `preflight`. |
| `web/src/lib/map/markers.ts` | aanmaken | `markerModels`, `initialView`, `createMarkerElement`. |
| `web/src/lib/map/platform.ts` | aanmaken | `MapLibre` (type), `getMaptilerKey`, `supportsWebGL2`, `loadMapLibre`. |
| `web/src/lib/map/start.ts` | aanmaken | `startMap`, `MapController`, `MapDeps`, `MapCallbacks`. |
| `web/src/lib/map/runtime.ts` | alleen bij terugval R2 | Statische MapLibre-imports; alleen te laden via `import('./runtime.js')`. |
| `web/src/lib/components/MapView.svelte` | aanmaken | Kaartcontainer, laadmelding, logo, attributie, legenda en de notitie over coördinaten. |
| `web/src/lib/components/MapSwitch.svelte` | aanmaken | Wissel lijst/kaart, preflight, melding, `MapView`. |
| `web/src/routes/+page.svelte` | wijzigen | 1 import, 1 state-regel, 1 componentregel, `hidden` op de `<ul>` (zie Interfaces). |
| `web/src/app.d.ts` | alleen indien nodig | `/// <reference types="vite/client" />` bovenaan, als `svelte-check` de typen van `?worker&url` of `.css` niet vindt (stap 5). |
| `web/scripts/verify-build.mjs` | wijzigen | Export `checkLazyMapLibre(buildDir)` en aanroep in `main()`. |
| `web/test/helpers/fake-maplibre.ts` | aanmaken | Nep-MapLibre voor de tests. |
| `web/test/fixtures/map-data.ts` | aanmaken | Kaartfixtures (`spot-data.ts` blijft ongewijzigd). |
| `web/test/env-schema.test.ts` | wijzigen | `describe('parseMaptilerKey')` onderaan erbij. |
| `web/test/env-example.test.ts` | wijzigen | Verwacht drie regels. |
| `web/test/verify-build.test.ts` | wijzigen | `describe('checkLazyMapLibre')` erbij. |
| `web/test/spot-list.test.ts` | alleen indien nodig | Eén regel `vi.mock('$app/env/public', …)` als `$app/env/public` in vitest niet resolvet (stap 7, N-7). |
| `web/test/map-config.test.ts`, `map-markers.test.ts`, `map-start.test.ts`, `map-source.test.ts`, `map-view.test.ts`, `map-switch.test.ts`, `home-no-map.test.ts` | aanmaken | Zie Testplan. |
| `docs/RUNBOOK.md` | wijzigen | §4: een rij erbij. §11: een nieuw punt **9. Kaart (vanaf WP-15)** na het bestaande punt 8 (WP-16). |

Niet gewijzigd: `app.css` (de kaartstijlen staan in de `<style>`-blokken van de componenten), `Attribution.svelte`, `FavoriteStar.svelte`, `favorites.ts`, `/over`, de service worker, `vite.config.ts`, `data.ts`, `types.ts`, `test/fixtures/spot-data.ts`, `test/helpers/fake-favorites.ts`, `ingest/`, `supabase/` en `.github/`. `docs/STATUS.md` en `docs/WORK_PACKAGES.md` werkt de orchestrator bij.

## Interfaces en contracten
Imports van gedeelde code gaan via `#lib/<pad>.js`. `Spot`, `SpotSummary` en `Verdict` komen uit `#lib/types.js` (WP-14), `verdictLabel` uit `#lib/labels.js`.

### `web/src/env.ts` (toevoeging)
```ts
import { parseMaptilerKey, parsePublishableKey, parseSupabaseUrl } from './lib/env-schema.js';
// ...existing two variables unchanged, then:
	PUBLIC_MAPTILER_KEY: {
		public: true,
		static: true,
		schema: parseMaptilerKey,
		description: 'MapTiler API key (public, restricted to allowed HTTP origins). Optional: empty = map unavailable, list keeps working.'
	}
```

### `web/src/lib/env-schema.ts` (toevoeging)
```ts
/** Validates PUBLIC_MAPTILER_KEY. Missing or blank -> '' (map disabled). Returns the trimmed key. Never echoes the value. */
export function parseMaptilerKey(value: string | undefined): string;
```
- Is `value?.trim() ?? ''` leeg, dan `''`.
- Komt de waarde niet overeen met `/^[A-Za-z0-9_-]{8,128}$/`, dan volgt `throw new Error('PUBLIC_MAPTILER_KEY must be a MapTiler API key (8-128 letters, digits, - or _)')`.
- Anders: de getrimde key.

### `web/.env.example` (toevoeging aan het eind)
```
# MapTiler API key (public). Locally: use a separate key restricted to localhost, never the production key. Optional: empty = no map, the list keeps working.
PUBLIC_MAPTILER_KEY=
```

### `web/src/lib/map/config.ts`
```ts
export type ViewMode = 'list' | 'map';
export type MapFailure = 'no_key' | 'no_webgl' | 'load_failed';

export const MAPTILER_API_ORIGIN = 'https://api.maptiler.com';
/** External origins the map talks to (for WP-23 CSP: connect-src and img-src). */
export const MAP_EXTERNAL_ORIGINS = [MAPTILER_API_ORIGIN] as const;
export const MAPTILER_STYLE_ID = 'streets-v4';
export const MAPTILER_LOGO_URL = `${MAPTILER_API_ORIGIN}/resources/logo.svg`;
export const MAPTILER_HOME_URL = 'https://www.maptiler.com';
export const MAPTILER_COPYRIGHT_URL = 'https://www.maptiler.com/copyright/';
export const OSM_COPYRIGHT_URL = 'https://www.openstreetmap.org/copyright';
export const MAPLIBRE_URL = 'https://maplibre.org/';
/** Same text as MapLibre's default customAttribution (replaced when attributionControl gets options). */
export const MAPLIBRE_ATTRIBUTION = '<a href="https://maplibre.org/" target="_blank">MapLibre</a>';

export const MAP_LOAD_TIMEOUT_MS = 30_000;
export const NL_CENTER: [number, number] = [5.3, 52.2];   // [lon, lat], view without any spot coordinates
export const NL_ZOOM = 6.5;
export const BOUNDS_MARGIN_DEG = 0.05;
export const FIT_PADDING_PX = 40;
export const FIT_MAX_ZOOM = 11;

export const MAP_FAILURE_MESSAGE_NL: Record<MapFailure, string> = {
	no_key: 'De kaart is niet beschikbaar in deze versie van de app. De lijst werkt gewoon.',
	no_webgl: 'Je browser kan de kaart niet tonen (WebGL2 ontbreekt). Gebruik de lijst.',
	load_failed: 'De kaart kon niet worden geladen. Probeer het later opnieuw of gebruik de lijst.'
};

/** `${MAPTILER_API_ORIGIN}/maps/${MAPTILER_STYLE_ID}/style.json?key=${encodeURIComponent(key)}` */
export function mapStyleUrl(key: string): string;
/** key === '' -> 'no_key' (webgl() not called); !webgl() -> 'no_webgl'; else null. */
export function preflight(key: string, webgl: () => boolean): MapFailure | null;
```
`api.maptiler.com` staat in de hele `src/` alleen in dit bestand (test `map-source`).

### `web/src/lib/map/markers.ts`
```ts
export interface MarkerModel {
	id: string;
	name: string;
	lon: number;
	lat: number;
	verdict: Verdict | null;          // null -> grey "Nog geen data"
	day: 'today' | 'tomorrow' | null;
	badge: string;                    // 'Go' | 'Morgen: Twijfel' | 'Nog geen data'
	unverified: boolean;              // !spot.verified
	href: string;                     // '/spot/' + encodeURIComponent(id)
}

/** In spot order. Skips spots whose lat/lon is null, not finite, |lat| > 90 or |lon| > 180 (counted in withoutCoords). */
export function markerModels(
	spots: readonly Spot[],
	summaries: Readonly<Record<string, SpotSummary>>
): { markers: MarkerModel[]; withoutCoords: number };

export type InitialView =
	| { kind: 'bounds'; bounds: [[number, number], [number, number]] }   // [[minLon, minLat], [maxLon, maxLat]]
	| { kind: 'center'; center: [number, number]; zoom: number };
/** No markers -> { kind: 'center', center: NL_CENTER, zoom: NL_ZOOM }.
 *  Otherwise min/max over all markers, widened by BOUNDS_MARGIN_DEG on each side (so a single spot is never a degenerate box). */
export function initialView(markers: readonly MarkerModel[]): InitialView;

/** <a class="map-marker[ map-marker-unverified]" href data-marker-spot={id} data-verdict="go|marginal|no_go|none">
 *    <span class="map-marker-name">{name}</span>
 *    <span class="verdict verdict-{verdict|none}">{badge}</span>
 *    [<span class="sr-only"> (niet geverifieerd)</span>]
 *  </a>
 *  Built with createElement and textContent only. Never sets data-spot (reserved for li.spot-item). */
export function createMarkerElement(model: MarkerModel, doc: Document): HTMLAnchorElement;
```
Regels voor `badge` en `day`, met `s = summaries[spot.id]`:
- `!s` → `null`, `null`, `'Nog geen data'`;
- `s.today.best` → `today`, `verdictLabel(best)`;
- anders `s.tomorrow.best` → `tomorrow`, `` `Morgen: ${verdictLabel(best)}` ``;
- anders `null`, `null`, `'Nog geen data'`.

### `web/src/lib/map/platform.ts`
```ts
import { PUBLIC_MAPTILER_KEY } from '$app/env/public';

/** Type only; erased at compile time (no runtime import). The only non-runtime maplibre-gl reference in src/. */
export type MapLibre = typeof import('maplibre-gl');

export function getMaptilerKey(): string;   // returns PUBLIC_MAPTILER_KEY ('' when not configured)

/** canvas.getContext('webgl2') !== null; frees the probe context via WEBGL_lose_context; any throw -> false. */
export function supportsWebGL2(doc?: Document): boolean;   // default: document

/** Loads MapLibre, its worker URL and CSS on first call; later calls share the promise; a rejection resets it (retry possible). */
export function loadMapLibre(): Promise<MapLibre>;
```
Implementatie van `loadMapLibre` (letterlijk; de drie specifiers staan in de bron nergens anders):
```ts
let pending: Promise<MapLibre> | null = null;
export function loadMapLibre(): Promise<MapLibre> {
	pending ??= Promise.all([
		import('maplibre-gl'),
		import('maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url'),
		import('maplibre-gl/dist/maplibre-gl.css')
	])
		.then(([lib, worker]) => {
			lib.setWorkerUrl(worker.default);
			return lib;
		})
		.catch((error: unknown) => {
			pending = null;
			throw error;
		});
	return pending;
}
```
`supportsWebGL2`:
```ts
try {
	const gl = (doc ?? document).createElement('canvas').getContext('webgl2');
	if (!gl) return false;
	gl.getExtension('WEBGL_lose_context')?.loseContext();
	return true;
} catch { return false; }
```
In `platform.ts` staan dus precies vier stringliterals met `maplibre-gl`, alle vier binnen `import(…)`: één in `typeof import(…)` (type, wordt gewist) en drie runtime-`import()`'s (test `map-source` (g)).

### `web/src/lib/map/start.ts`
```ts
import type { MapLibre } from './platform.js';

export interface MapDeps { key: string; webgl: () => boolean; load: () => Promise<MapLibre> }
export interface MapCallbacks { onReady(): void; onFail(reason: MapFailure): void }
export interface MapController {
	update(spots: readonly Spot[], summaries: Readonly<Record<string, SpotSummary>>): void;
	destroy(): void;
}
/** Callbacks are never invoked synchronously, never after destroy(), and onFail at most once. */
export function startMap(
	container: HTMLElement,
	spots: readonly Spot[],
	summaries: Readonly<Record<string, SpotSummary>>,
	deps: MapDeps,
	callbacks: MapCallbacks
): MapController;
```
De volgorde ligt vast; de tests controleren hem.
1. Toestand: `destroyed = false`, `failed = false`, `styleLoaded = false`, `loaded = false`, `warned = false`, `lib = null`, `map = null`, `markers = []`, `current = { spots, summaries }`, `timer = null`.
2. `fail(reason)`:
   - doet niets als `destroyed || failed`;
   - anders `failed = true`, timer wissen, markers verwijderen en `try { map?.remove() } catch {}`;
   - daarna `map = null` en `callbacks.onFail(reason)`.
3. `warnOnce()`: als `!warned`, dan `warned = true` en `console.warn('map resource error')`. De inhoud van het event wordt nooit gelogd: de style-URL bevat de key.
4. `renderMarkers()`: verwijder de bestaande markers en maak er een per model uit `markerModels(current.spots, current.summaries).markers`:
   `new lib.Marker({ element: createMarkerElement(m, container.ownerDocument), anchor: 'bottom' }).setLngLat([m.lon, m.lat]).addTo(map)`.
5. Asynchroon, als `void (async () => { … })()`:
   - a. `await Promise.resolve()`; stop bij `destroyed`.
   - b. `const pre = preflight(deps.key, deps.webgl)`; bij een fout `fail(pre)` en stoppen.
   - c. `lib = await deps.load()`. Bij een throw: `console.warn('map library load failed')` (zonder de fout zelf) en `fail('load_failed')`. Na de await stoppen bij `destroyed || failed`.
   - d. `const view = initialView(markerModels(current.spots, current.summaries).markers)`.
   - e. `map = new lib.Map(options)` met:
     ```ts
     {
     	container,
     	style: mapStyleUrl(deps.key),
     	...(view.kind === 'bounds'
     		? { bounds: view.bounds, fitBoundsOptions: { padding: FIT_PADDING_PX, maxZoom: FIT_MAX_ZOOM } }
     		: { center: view.center, zoom: view.zoom }),
     	attributionControl: { compact: false, customAttribution: MAPLIBRE_ATTRIBUTION },
     	maplibreLogo: false,
     	dragRotate: false,
     	pitchWithRotate: false,
     	touchPitch: false,
     	refreshExpiredTiles: false
     }
     ```
     Gooit de constructor een fout `e`, dan `fail(e instanceof lib.GPUInitializationError ? 'no_webgl' : 'load_failed')` en stoppen.
   - f. `map.addControl(new lib.NavigationControl({ showCompass: false }), 'top-right')`.
   - g. `map.on('style.load', () => { styleLoaded = true; })`.
   - h. `map.on('error', () => …)`:
     - stop bij `destroyed || failed`;
     - `!styleLoaded` → `fail('load_failed')` (style 401/403: key, origin of quotum);
     - anders `warnOnce()`, zowel vóór als na `load`.
   - i. `map.on('load', () => …)`:
     - stop bij `destroyed || failed`;
     - anders `styleLoaded = true`, `loaded = true`, timer wissen, `renderMarkers()` en `callbacks.onReady()`.
   - j. `timer = setTimeout(() => { if (!loaded) fail('load_failed'); }, MAP_LOAD_TIMEOUT_MS)`.
6. `update(s, su)`: `current = { spots: s, summaries: su }`. Alleen als `loaded && !failed && !destroyed` volgt `renderMarkers()` (de kaart wordt niet opnieuw ingepast).
7. `destroy()`: idempotent. `destroyed = true`, timer wissen, markers verwijderen, `try { map?.remove() } catch {}`, `map = null`.

De typen komen uit `MapLibre` (`InstanceType<MapLibre['Map']>`, `InstanceType<MapLibre['Marker']>`). Er is geen eigen nabootsing van de MapLibre-API en geen cast in `src/`. Exporteert `maplibre-gl` geen `GPUInitializationError` (controleer `node_modules/maplibre-gl/dist/maplibre-gl.d.ts` in stap 2), dan geeft elke constructorfout `'load_failed'`, en dat komt in `deviations.md`. Accepteert de getypte `map.on` de eventnaam `'style.load'` niet, dan is dat een fout in deze blueprint: meld het in `deviations.md` en gebruik geen cast. `MapEventType` documenteert `style.load` wel.

### `web/src/lib/components/MapView.svelte`
Props:
```ts
interface Props {
	spots: Spot[];
	summaries: Record<string, SpotSummary>;
	onfail?: (reason: MapFailure) => void;   // additive, optional (WP-15 contract: spots + summaries)
}
```
Script:
- `let container: HTMLDivElement`; `let ready = $state(false)`; `let controller: MapController | null = null` (bewust geen `$state`);
- `const notOnMap = $derived(markerModels(spots, summaries).withoutCoords)`;
- `onMount`: `controller = startMap(container, spots, summaries, { key: getMaptilerKey(), webgl: supportsWebGL2, load: loadMapLibre }, { onReady: () => (ready = true), onFail: (r) => onfail?.(r) })`. De cleanup roept `controller?.destroy()` aan en zet `controller = null`;
- het effect leest de props onvoorwaardelijk (N-6), zodat het ook reageert als het vóór `onMount` voor het eerst draait:
  ```ts
  $effect(() => {
  	const s = spots;
  	const su = summaries;
  	controller?.update(s, su);
  });
  ```

Markup, in deze volgorde:
```svelte
<section class="map-wrap" aria-label="Kaart met spots">
	<div class="map-canvas" bind:this={container}></div>
	{#if ready}
		<a class="maptiler-logo" href={MAPTILER_HOME_URL} target="_blank" rel="noopener noreferrer">
			<img src={MAPTILER_LOGO_URL} alt="MapTiler logo" />
		</a>
	{:else}
		<p class="map-loading" role="status">Kaart laden…</p>
	{/if}
</section>
<p class="map-attribution">
	Kaart: <a href={MAPTILER_COPYRIGHT_URL} target="_blank" rel="noopener noreferrer">© MapTiler</a> ·
	<a href={OSM_COPYRIGHT_URL} target="_blank" rel="noopener noreferrer">© OpenStreetMap contributors</a> ·
	<a href={MAPLIBRE_URL} target="_blank" rel="noopener noreferrer">MapLibre</a>. De kaarttegels komen van MapTiler.
</p>
<p class="map-legend muted">Tik op een spot voor het overzicht per uur. Gestippelde rand: spot niet geverifieerd.</p>
{#if notOnMap > 0}
	<p class="muted">{notOnMap === 1 ? '1 spot zonder coördinaten staat' : `${notOnMap} spots zonder coördinaten staan`} niet op de kaart.</p>
{/if}
```
Svelte rendert geen kinderen in `.map-canvas`, want MapLibre eist een lege container.

`<style>`:
- `.map-wrap { position: relative; }`
- `.map-canvas { width: 100%; height: min(70vh, 32rem); }`
- `.map-loading { position: absolute; inset: 0; margin: 0; display: grid; place-items: center; background: #f4f4f4; }`
- `.maptiler-logo { position: absolute; left: 10px; bottom: 10px; z-index: 999; }` (positie en z-index zoals in het fragment van MapTiler)
- `:global(.map-marker) { display: inline-flex; align-items: center; gap: 0.25rem; padding: 0.15rem 0.35rem; background: #fff; color: #1a1a1a; border: 1px solid #555; border-radius: 0.25rem; font-size: 0.8rem; text-decoration: none; white-space: nowrap; box-shadow: 0 1px 3px rgba(0, 0, 0, 0.3); }`
- `:global(.map-marker-unverified) { border-style: dashed; }`
- `:global(.verdict-none) { background: #555; }`
- `:global(.map-marker .sr-only) { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); white-space: nowrap; }`

De selector `maplibregl-ctrl` komt nergens in `src/` voor. De besturingselementen van MapLibre worden dus nooit overschreven of verborgen.

### `web/src/lib/components/MapSwitch.svelte`
```ts
interface Props { spots: Spot[]; summaries: Record<string, SpotSummary>; view?: ViewMode }
let { spots, summaries, view = $bindable<ViewMode>('list') }: Props = $props();
let notice = $state<string | null>(null);
function showList() { view = 'list'; notice = null; }
function showMap() {
	if (view === 'map') return;
	const failure = preflight(getMaptilerKey(), supportsWebGL2);
	if (failure) { fail(failure); return; }
	notice = null;
	view = 'map';
}
function fail(reason: MapFailure) { view = 'list'; notice = MAP_FAILURE_MESSAGE_NL[reason]; }
```
```svelte
<div class="view-toggle" role="group" aria-label="Weergave">
	<button type="button" aria-pressed={view === 'list'} onclick={showList}>Lijst</button>
	<button type="button" aria-pressed={view === 'map'} onclick={showMap}>Kaart</button>
</div>
{#if notice}<p class="banner map-notice" role="status">{notice}</p>{/if}
{#if view === 'map'}<MapView {spots} {summaries} onfail={fail} />{/if}
```
`<style>`: `.view-toggle { display: flex; gap: 0.5rem; margin: 0.75rem 0; }`, `.view-toggle button[aria-pressed='true'] { font-weight: 700; text-decoration: underline; }`.

### `web/src/routes/+page.svelte` (de vier wijzigingen, verder niets)
Gecontroleerd tegen de huidige versie op `develop` (met WP-16):
1. Bij de imports, direct na `import Freshness from '#lib/components/Freshness.svelte';` (regel 5): `import MapSwitch from '#lib/components/MapSwitch.svelte';`
2. Direct na `let { data }: PageProps = $props();` (regel 10): `let view = $state<'list' | 'map'>('list');`
3. Direct na `<Freshness latest={latestOfSummaries(data.summaries)} now={new Date(data.now)} />` (regel 39): `<MapSwitch spots={data.spots} summaries={data.summaries} bind:view />`
4. `<ul class="spot-list">` (regel 40) wordt `<ul class="spot-list" hidden={view === 'map'}>`.

De inhoud van `li.spot-item` (met `FavoriteStar`) blijft ongewijzigd. Staan de regels na een rebase op een ander nummer, dan zoek je op de genoemde tekst; de ankers blijven hetzelfde.

### `web/scripts/verify-build.mjs` (toevoeging)
```js
/** @param {string} buildDir @returns {string[]} problems: maplibre must be lazy (never in entry chunks) but present in some other chunk. */
export function checkLazyMapLibre(buildDir) { … }
```
- `immutable = join(buildDir, '_app', 'immutable')` en `entry = join(immutable, 'entry')`.
- Elk `.js`- of `.css`-bestand onder `entry` dat `maplibre` bevat, geeft `maplibre referenced in entry chunk <pad relatief aan buildDir>`.
- Bevat geen enkel `.js`-, `.mjs`- of `.css`-bestand onder `immutable` buiten `entry` de tekst `maplibre`, dan volgt `no lazily loaded maplibre chunk in _app/immutable`.
- `main()` voegt `problems.push(...checkLazyMapLibre(build))` toe na de check op de service worker.
- Gebruikt de bestaande `listFiles`.

### Gevolgen voor latere WP's
- **WP-23 (CSP, privacy, performance):**
  - `connect-src` krijgt `https://api.maptiler.com` (style, TileJSON, tiles, glyphs, sprites);
  - `img-src` krijgt `'self' data: blob: https://api.maptiler.com` (sprite en logo);
  - `worker-src 'self'` (de MapLibre-worker is een same-origin-bestand via `setWorkerUrl`; volgens de MapLibre-docs is `blob:` dan niet nodig);
  - de lijst van origins staat in `MAP_EXTERNAL_ORIGINS`;
  - de privacypagina vermeldt dat MapTiler je IP-adres, de origin en (volgens de standaard Referrer-Policy van de browser) de herkomst ontvangt als je op "Kaart" klikt, en niet eerder. Een eventuele `Referrer-Policy` is aan WP-23; de origin-restrictie van MapTiler kijkt naar de origin, niet naar de Referer;
  - **datavolume (N-9):** de service worker precachet de MapLibre-chunk (±800 kB, ±250 kB gzip) plus de CSS. Elke installatie downloadt die één keer per nieuwe app-versie, ook zonder klik op "Kaart". WP-23 beoordeelt dit binnen het bundel- en performancebudget en kan de chunk eventueel uit de precache halen (met een oplossing voor oude chunknamen na een deploy, zie A9).
- **WP-22:** het MapTiler-verbruik (requests, A2) staat alleen in het MapTiler-dashboard, niet via een API. Neem het op in de handmatige maandcheck.
- **WP-18:** `PUBLIC_VAPID_PUBLIC_KEY` wordt de vierde regel in `.env.example` en `env-example.test.ts`.
- **WP-16 (gemerged):** de favorietenster in `li.spot-item` werkt ongewijzigd; markers krijgen geen ster. Paginatests mocken `#lib/favorites.js`.
- **WP-12 (volgt via rebase):** raakt de spotpagina, `test/fixtures/spot-data.ts` (additief; `map-data.ts` importeert er alleen uit) en de RUNBOOK (§15 en de tekst van §11.7). Geen overlap met §4-rij of §11.9 van deze WP.
- **Orchestrator (docs):**
  - in WORK_PACKAGES, de rij "MapTiler gratis" in "Gecontroleerde externe documentatie": "5.000 map sessions/maand (MapTiler SDK) of 100.000 API-requests/maand (andere SDK's zoals MapLibre GL JS; alleen tiles tellen: vector 1 per tile, raster 512 px 4 per tile; style, TileJSON en fonts gratis; Shakka valt hieronder)";
  - het doel van WP-15 noemt "5.000 MapTiler-sessies"; lees dat als het requestbudget (A2);
  - "Nodig van Lars" bij WP-15 noemt "Pages-domein en localhost"; dat wordt "productiekey met alleen het Pages-domein; een aparte key voor localhost, alleen in `web/.env`" (N-10);
  - meld Lars de afwijking als de terugval van R2 nodig was.

## Edge cases

| # | Geval | Gedrag |
|---|---|---|
| E1 | `PUBLIC_MAPTILER_KEY` leeg of afwezig | Klik op "Kaart": melding `no_key`. "Lijst" blijft `aria-pressed="true"`. Geen `import()`, geen request naar MapTiler, geen WebGL-probe. |
| E2 | Ongeldige key-tekens in de build-env | De build faalt met `PUBLIC_MAPTILER_KEY must be …`, zonder de waarde. |
| E3 | Geen WebGL2 (oude browser, uitgeschakeld) | Preflight: melding `no_webgl`, geen `import()`. |
| E4 | WebGL2-probe slaagt, maar de constructor gooit `GPUInitializationError` | `no_webgl`. Een andere constructorfout geeft `load_failed`. |
| E5 | Offline, of de chunk is weg na een deploy | `import()` rejectet: `load_failed`. Een volgende klik probeert opnieuw (de promise wordt gereset). |
| E6 | Key geweigerd (origin-restrictie, verkeerde key, productiekey op localhost) of quotum op, MapTiler gepauzeerd | De style geeft 401/403, dus een `error` vóór `style.load`: `load_failed`. De kaart wordt opgeruimd en de lijst staat er weer. |
| E7 | MapTiler hangt (geen `load` binnen 30 s) | `load_failed`. |
| E8 | Tiles of sprites falen na `style.load` (kort netwerkprobleem, quotum halverwege, storing) | De kaart blijft staan; één `console.warn('map resource error')` per kaart. Komt `load` binnen 30 s, dan verschijnen de markers (eventueel op een lege ondergrond). Anders `load_failed`. |
| E9 | Gebruiker klikt "Lijst" terwijl de kaart nog laadt | `destroy()`: er wordt geen kaart meer gemaakt (geen style-request als de chunk nog laadde) en er komen geen callbacks. |
| E10 | Dubbelklik op "Kaart" | De tweede klik doet niets. |
| E11 | Spot zonder `lat`/`lon`, met `NaN` of met `lat = 95` | Geen marker, wel meegeteld in "N spots zonder coördinaten …". |
| E12 | Geen enkele spot met coördinaten | De kaart toont Nederland (`NL_CENTER`, zoom 6,5) zonder markers, plus de notitie. |
| E13 | Eén spot | Bounds van ±0,05° rondom; maximale zoom 11. |
| E14 | Spot zonder summary, of `today` en `tomorrow` zonder uren | Grijze badge "Nog geen data" (`data-verdict="none"`). |
| E15 | Na zonsondergang (`today.best = null`, `tomorrow.best = 'go'`) | Badge "Morgen: Go". |
| E16 | `verified: false` | Gestippelde rand plus de verborgen tekst " (niet geverifieerd)"; de legenda legt het uit. |
| E17 | Spotnaam met HTML (`<img src=x onerror=…>`) | Wordt als tekst getoond (`textContent`); er ontstaat geen element. |
| E18 | `refreshAll()` (hervatten) terwijl de kaart open is | Het `$effect` roept `update()` aan, dat de markers vervangt. Geen nieuwe kaart, geen nieuwe style-request. |
| E19 | Data-refresh geeft `kind: 'error'` of `spots: []` | De tak met de wissel verdwijnt, `MapView` wordt opgeruimd (`destroy`). |
| E20 | Terug van een spotpagina naar `/` | Weer de lijst (A5). |
| E21 | Overlappende markers (spots dicht bij elkaar) | Ze overlappen; inzoomen helpt. Clustering valt buiten scope. |
| E22 | Toetsenbord | Markers zijn `<a>`-links en dus te focussen; de wisselknoppen hebben `aria-pressed`; de zoomknoppen van MapLibre zijn er. |
| E23 | Een developer heeft lokaal een key in `web/.env` | De tests zijn er niet van afhankelijk. `map-view` en `map-switch` mocken `platform`, `home-no-map` mockt `$app/env/public`, en `spot-list` klikt niet. |
| E24 | Eén tile faalt kort tijdens het eerste beeld (na `style.load`, vóór `load`) | Geen fallback (N-5). Eén `console.warn`; `load` volgt normaal. |
| E25 | Ingelogde gebruiker met favorieten opent de kaart | De sterren blijven in de verborgen lijst; terug naar "Lijst" toont ze ongewijzigd. Markers hebben geen ster. |

## Testplan
Alle tests staan in `web/test/` en draaien met `npm test` (jsdom, tenzij `// @vitest-environment node`). Tests voor de pure en de geïnjecteerde logica komen vóór de implementatie: `env-schema`, `map-config`, `map-markers`, `map-start` en `checkLazyMapLibre`. Elk bestand met mocks heeft `beforeEach(() => vi.clearAllMocks())`. Wie timers gebruikt, roept `vi.useFakeTimers()` aan en ruimt op met `vi.useRealTimers()`.

**Paginatests (B-1).** Elke test die `src/routes/+page.svelte` rendert (`map-switch.test.ts` en `home-no-map.test.ts`), mockt precies zoals `spot-list.test.ts` op `develop`:
```ts
const nav = vi.hoisted(() => ({ refreshAll: vi.fn() }));
vi.mock('$app/navigation', () => ({ refreshAll: nav.refreshAll }));
vi.mock('#lib/supabase.js', () => {
	throw new Error('page tests must not import the Supabase client');
});
vi.mock('#lib/favorites.js', async () => (await import('./helpers/fake-favorites.js')).favoritesModule);
```
Met in `beforeEach`: `vi.clearAllMocks(); favoritesState.set({ status: 'signed_out' });` (`favoritesState` uit `./helpers/fake-favorites.js`).

### Fixtures (`web/test/fixtures/map-data.ts`)
Alleen testdata, met coördinaten zoals in WP-14. Importeert `EVALUATED_AT`, `NOW_FRESH`, `SPOT_UNVERIFIED` en `SPOT_VERIFIED` uit `./spot-data.js` en `Spot` en `SpotSummary` als type uit `../../src/lib/types.js`.
```ts
export const SPOT_NO_COORDS: Spot = { ...SPOT_VERIFIED, id: 'test-zonder', name: 'Testzonder', lat: null, lon: null };
export const SPOT_EVENING: Spot = { ...SPOT_VERIFIED, id: 'test-avond', name: 'Testavond', lat: 52.1, lon: 4.2 };

export const SUMMARY_GO: SpotSummary = {
	spot_id: 'test-meer',
	today: { date: '2026-07-15', go: 2, marginal: 1, no_go: 0, best: 'go', first_go_at: '2026-07-15T12:00:00+00:00' },
	tomorrow: { date: '2026-07-16', go: 0, marginal: 0, no_go: 1, best: 'no_go', first_go_at: null },
	latest_evaluated_at: EVALUATED_AT
};
export const SUMMARY_TOMORROW: SpotSummary = {
	spot_id: 'test-avond',
	today: { date: '2026-07-15', go: 0, marginal: 0, no_go: 0, best: null, first_go_at: null },
	tomorrow: { date: '2026-07-16', go: 0, marginal: 2, no_go: 0, best: 'marginal', first_go_at: null },
	latest_evaluated_at: EVALUATED_AT
};

export const MAP_SPOTS: Spot[] = [SPOT_UNVERIFIED, SPOT_VERIFIED, SPOT_EVENING, SPOT_NO_COORDS];
export const MAP_SUMMARIES: Record<string, SpotSummary> = { 'test-meer': SUMMARY_GO, 'test-avond': SUMMARY_TOMORROW };
export function homeData(overrides: Record<string, unknown> = {}) {
	return { kind: 'ok' as const, now: NOW_FRESH, spots: MAP_SPOTS, summaries: MAP_SUMMARIES, ...overrides };
}
```
Met `latest_evaluated_at = EVALUATED_AT` (12:05Z) en `now = NOW_FRESH` (12:30Z) is de data vers, dus `Freshness` toont geen `role="alert"`.

### `web/test/helpers/fake-maplibre.ts`
```ts
export class FakeGPUInitializationError extends Error {}
export interface FakeMap {
	options: Record<string, unknown>;
	controls: Array<{ control: unknown; position?: string }>;
	remove: Mock;
	emit(type: 'style.load' | 'load' | 'error', event?: unknown): void;
}
export interface FakeMarker { options: { element: HTMLElement; anchor: string }; lngLat: [number, number] | null; removed: boolean }
export function createFakeMapLibre(): {
	lib: MapLibre;                         // cast once here: `as unknown as MapLibre` (test code only)
	maps: FakeMap[];
	markers: FakeMarker[];
	navigationOptions: unknown[];
	throwOnConstruct: { error: Error | null };   // set to make new Map(...) throw
};
```
- `Map` legt `options` vast, gooit `throwOnConstruct.error` als die gezet is, en heeft `on(type, fn)` (meerdere handlers per type), `addControl(c, pos)`, `remove` (een `vi.fn`) en `emit` (roept de handlers van dat type synchroon aan).
- `Marker` legt `options` vast. `setLngLat(ll)` zet `lngLat` en geeft `this` terug. `addTo(map)` hangt `options.element` in `map.options.container` en geeft `this` terug. `remove()` haalt het element weg en zet `removed = true`.
- `NavigationControl` legt de opties vast in `navigationOptions`.
- `GPUInitializationError` is `FakeGPUInitializationError`.

### Testbestanden

| Bestand | Tests |
|---|---|
| `env-schema.test.ts` (uitbreiding) | `parseMaptilerKey(undefined)`, `('')` en `('  ')` geven `''`. `(' abcDEF123456 ')` geeft `'abcDEF123456'`; `('get_your_own_Key-1')` blijft zoals hij is. Gooien met een melding die met `PUBLIC_MAPTILER_KEY` begint en de waarde niet bevat: `'short1'` (6 tekens), `'abc def 12345'`, `'abc/def12345'`, `'x'.repeat(129)`. |
| `env-example.test.ts` (aangepast) | De regels zijn precies `['PUBLIC_SUPABASE_URL=', 'PUBLIC_SUPABASE_PUBLISHABLE_KEY=', 'PUBLIC_MAPTILER_KEY=']`. |
| `map-config.test.ts` (node) | `mapStyleUrl('abcDEF123456') === 'https://api.maptiler.com/maps/streets-v4/style.json?key=abcDEF123456'`. `preflight('', webgl)` geeft `'no_key'` en roept `webgl` niet aan (`vi.fn`). `preflight('k', () => false)` geeft `'no_webgl'`, `preflight('k', () => true)` geeft `null`. Elke waarde in `MAP_FAILURE_MESSAGE_NL` is niet leeg en bevat "lijst" (hoofdletterongevoelig). `MAP_EXTERNAL_ORIGINS` is precies `['https://api.maptiler.com']`. `MAPLIBRE_ATTRIBUTION` bevat `https://maplibre.org/`. |
| `map-markers.test.ts` | Zie de lijst hieronder. |
| `map-start.test.ts` | Zie de lijst hieronder. |
| `map-source.test.ts` (node) | Zie de lijst hieronder. |
| `verify-build.test.ts` (uitbreiding) | `checkLazyMapLibre` op tijdelijke mappen (`mkdtempSync` in `os.tmpdir()`, opruimen met `rmSync(…, { recursive: true })`). (1) `entry/app.js` zonder `maplibre` en `chunks/maplibre-gl.abc.js` met `maplibre`: `[]`. (2) `entry/start.js` met `import("../chunks/maplibre-gl.abc.js")`: één probleem met `entry`. (3) Geen enkel bestand met `maplibre`: één probleem met `no lazily loaded maplibre chunk`. |
| `map-view.test.ts` | Zie de lijst hieronder. |
| `map-switch.test.ts` | Zie de lijst hieronder. |
| `home-no-map.test.ts` | Zie de lijst hieronder. |

**`map-markers.test.ts`**
- `markerModels(MAP_SPOTS, MAP_SUMMARIES)` geeft `withoutCoords 1` en drie modellen in spotvolgorde:
  - `test-strand`: `verdict null`, `day null`, `badge 'Nog geen data'`, `unverified true`, `href '/spot/test-strand'`, `lon 4.57`, `lat 52.47`;
  - `test-meer`: `'go'`, `'today'`, `'Go'`, `unverified false`;
  - `test-avond`: `'marginal'`, `'tomorrow'`, `'Morgen: Twijfel'`.
- Ook geteld als zonder coördinaten: `lat: 95`, `lon: NaN`, `lon: null`.
- Een summary met alles op 0 en `best null` voor vandaag en morgen geeft `'Nog geen data'`.
- `initialView([])` geeft `{ kind: 'center', center: [5.3, 52.2], zoom: 6.5 }`. Op de drie modellen: `bounds` ≈ `[[4.15, 52.05], [4.62, 52.52]]` (`toBeCloseTo`). Eén model geeft een box van 0,1° breed.
- `createMarkerElement` voor `test-meer`: `tagName 'A'`, `href`-attribuut `/spot/test-meer`, `data-marker-spot 'test-meer'`, **geen** attribuut `data-spot` (A12), `data-verdict 'go'`, `.map-marker-name` met tekst `Testmeer`, `.verdict.verdict-go` met tekst `Go`, geen `.sr-only`.
- Voor `test-strand`: `data-verdict 'none'`, `.verdict-none` met `Nog geen data`, klasse `map-marker-unverified` en `.sr-only` met ` (niet geverifieerd)`.
- Met de naam `'<img src=x onerror=alert(1)>'`: `el.querySelector('img') === null` en `textContent` bevat de ruwe tekst.

**`map-start.test.ts`**

Opzet: `createFakeMapLibre`, `deps = { key: 'testkey123', webgl: () => true, load: vi.fn(async () => fake.lib) }`, callbacks als `vi.fn`, `vi.spyOn(console, 'warn').mockImplementation(() => {})` en `flush = () => new Promise((r) => setTimeout(r, 0))` (met fake timers: `await vi.advanceTimersByTimeAsync(0)`).
1. **Nooit synchroon:** met `key: ''` is `onFail` direct na `startMap` nog niet aangeroepen; na `flush` wel, met `'no_key'`, en `load` is niet aangeroepen.
2. `webgl: () => false` geeft `'no_webgl'` en geen `load`.
3. `load` rejectet met `new Error('secret detail')`: `'load_failed'`, `console.warn` precies één keer en zonder `'secret detail'`.
4. `throwOnConstruct = new FakeGPUInitializationError()` geeft `'no_webgl'`; `new Error('x')` geeft `'load_failed'`.
5. **AC-5:** `maps[0].options` bevat:
   - `container` en `style: mapStyleUrl('testkey123')`;
   - `attributionControl: { compact: false, customAttribution: MAPLIBRE_ATTRIBUTION }` (`toEqual`, en `not.toBe(false)`);
   - `maplibreLogo: false`, `dragRotate: false`, `pitchWithRotate: false`, `touchPitch: false`, `refreshExpiredTiles: false`;
   - `bounds` en `fitBoundsOptions: { padding: 40, maxZoom: 11 }`.

   Zonder spots met coördinaten: `center` en `zoom`, en geen `bounds`.
6. `navigationOptions[0]` is `{ showCompass: false }` en `controls[0].position` is `'top-right'`.
7. Fouten tijdens het laden (N-5):
   - a. `emit('error', { error: new Error('401 https://api.maptiler.com/…?key=testkey123') })` vóór `style.load` geeft `'load_failed'` en `remove` één keer. `console.warn` is niet aangeroepen met iets dat `testkey123` bevat. Een `emit('style.load')` en `emit('load')` daarna roepen `onReady` niet aan en maken geen markers.
   - b. `emit('style.load')`, daarna twee keer `emit('error')`: geen `onFail`, `remove` niet aangeroepen, `console.warn` precies één keer met `'map resource error'`. Daarna roept `emit('load')` `onReady` één keer aan en zijn er drie markers.
8. `emit('load')` (zonder `style.load` vooraf) roept `onReady` één keer aan. Er zijn drie markers met `anchor 'bottom'` en `lngLat` `[4.57, 52.47]`, `[4.57, 52.47]` en `[4.2, 52.1]`, en hun elementen zitten in de container. Twee keer `emit('error')` daarna geeft geen `onFail` en `console.warn` precies één keer.
9. Fake timers:
   - zonder `load` geeft `vi.advanceTimersByTime(30_000)` `'load_failed'`;
   - met `emit('style.load')` en `emit('error')`, maar zonder `load`, geeft 30 s ook `'load_failed'`;
   - met `load` vóór 30 s geeft doorspoelen tot 60 s geen `onFail`.
10. `destroy()` vóór de resolve van `load` (een handmatig deferred promise): na de resolve geen `Map` en geen callbacks.
11. `destroy()` na `load`: alle markers `removed`, `remove` één keer. Een tweede `destroy()` roept `remove` niet nog eens aan.
12. `update([SPOT_VERIFIED], {})` na `load`: de oude drie markers zijn `removed` en er is één nieuwe. `update` vóór `load`, gevolgd door `load`, geeft markers van de nieuwe data.

**`map-source.test.ts` (node). AC-2 (bron) en AC-5 (niet verborgen).**

Loopt door alle `.ts`- en `.svelte`-bestanden onder `src/`.
- a. Per bestand is het aantal treffers van `/(['"\x60])[^'"\x60\n]*maplibre-gl[^'"\x60\n]*\1/g` gelijk aan het aantal treffers van `/\bimport\(\s*(['"\x60])[^'"\x60\n]*maplibre-gl[^'"\x60\n]*\1\s*\)/g`. Zo staat elke stringliteral met `maplibre-gl` binnen een `import(…)`. De enige niet-runtime-treffer is `export type MapLibre = typeof import('maplibre-gl')` in `platform.ts`; die wordt bij het compileren gewist (N-12).
- b. Geen treffer op `/from\s+['"]maplibre-gl/` en `/import\s+['"]maplibre-gl/`.
- c. Het enige bestand met `maplibre-gl` is `src/lib/map/platform.ts` (`start.ts` importeert het type `MapLibre` uit `./platform.js`). Gebruik `maplibre-gl` ook niet in commentaar tussen aanhalingstekens.
- d. `api.maptiler.com` staat alleen in `src/lib/map/config.ts`.
- e. Geen enkel bestand bevat `maplibregl-ctrl`.
- f. `PUBLIC_MAPTILER_KEY` staat alleen in `src/env.ts`, `src/lib/env-schema.ts` (foutmelding) en `src/lib/map/platform.ts`.
- g. In `platform.ts`: precies één treffer op `/\btypeof\s+import\(/` en precies vier treffers van de regex uit (a).

Alleen bij de terugval van R2 worden (a)–(c) en (g) aangepast; zie stap 9.

**`map-view.test.ts`**

Mockt `#lib/map/platform.js` met `p = vi.hoisted(() => ({ key: 'testkey123', webgl: true, load: vi.fn() }))`: `getMaptilerKey: () => p.key`, `supportsWebGL2: () => p.webgl`, `loadMapLibre: () => p.load()`. `p.load.mockResolvedValue(fake.lib)`. Rendert `MapView` met `MAP_SPOTS`, `MAP_SUMMARIES` en `onfail` als `vi.fn`.
1. Vóór `load`: `role="status"` met `Kaart laden…` en geen `img`.
2. **AC-5:** na `fake.maps[0].emit('load')` (binnen `act`/`tick`) staat er een link met `href` `https://www.maptiler.com`, met daarin `img[alt="MapTiler logo"]` met `src` `https://api.maptiler.com/resources/logo.svg`. Verder de links `© MapTiler` (`https://www.maptiler.com/copyright/`), `© OpenStreetMap contributors` (`https://www.openstreetmap.org/copyright`) en `MapLibre` (`https://maplibre.org/`).
3. **Marker opent de spotpagina:** `getByRole('link', { name: /Testmeer/ })` heeft `href` `/spot/test-meer` en bevat `Go`. `/Testavond/` bevat `Morgen: Twijfel`.
4. `1 spot zonder coördinaten staat niet op de kaart.` staat er.
5. `emit('error')` vóór `style.load` (nieuwe render) roept `onfail` aan met `'load_failed'`.
6. `unmount()` na `load` roept `fake.maps[0].remove` aan.
7. De attributie-alinea staat er ook vóór `load` (tekst `© OpenStreetMap contributors`).
8. **Nieuwe data (N-6, E18):** na `emit('load')` doe je `await rerender({ spots: MAP_SPOTS, summaries: {} })`. Daarna zijn de eerste drie `fake.markers` `removed`, zijn er drie nieuwe niet-verwijderde markers, is `fake.maps.length` nog steeds 1 en bevat de link `/Testmeer/` nu `Nog geen data`.

**`map-switch.test.ts`. AC-4 en de wissel.**

Rendert `src/routes/+page.svelte` met `homeData()`. Mockt de vier modules uit "Paginatests" plus `#lib/map/platform.js` (zoals in `map-view`; `p.key`, `p.webgl` en `p.load` worden in `beforeEach` teruggezet op `'testkey123'`, `true` en `mockResolvedValue(fake.lib)` met een nieuwe `fake`).
1. **AC-4, zonder key** (`p.key = ''`): de klik op `Kaart` geeft `role="status"` met de tekst van `MAP_FAILURE_MESSAGE_NL.no_key`. Verder:
   - `Lijst` heeft `aria-pressed="true"`;
   - `ul.spot-list` heeft geen `hidden` en is zichtbaar;
   - de link `Teststrand` heeft `href="/spot/test-strand"`;
   - `p.load` is niet aangeroepen en er is geen `.map-canvas`;
   - er is geen `role="alert"`.
2. Zonder WebGL2 (`p.webgl = false`): de melding `no_webgl`, `p.load` niet aangeroepen.
3. **Gelukt:** de klik op `Kaart` geeft `aria-pressed="true"` op `Kaart`. `ul.spot-list` heeft het attribuut `hidden` en `.map-canvas` bestaat. Na `emit('load')` staan de markers erin, en `document.querySelector('[data-spot="test-meer"]')` is nog steeds het `li.spot-item` (A12). Een klik op `Lijst` haalt `hidden` weg, roept `fake.maps[0].remove` aan, en `.map-canvas` is weg.
4. `p.load` rejectet: na `await` staat de melding `load_failed`, de lijst is zichtbaar en `Lijst` heeft `aria-pressed="true"`. Een tweede klik op `Kaart` probeert opnieuw (`p.load` twee keer aangeroepen).
5. Een tweede klik op `Kaart` terwijl de kaart open is: `p.load` blijft op één aanroep.
6. **Favorieten (WP-16):** met `favoritesState.set({ status: 'ready', userId: USER_ID, ids: new Set(['test-meer']) })` (`USER_ID` uit `./helpers/fake-session.js`) staat de knop `Favoriet: Testmeer` met `aria-pressed="true"` er. Na `Kaart` en terug naar `Lijst` staat die er nog, met dezelfde status.

**`home-no-map.test.ts`. AC-3.**

Mockt `platform` *niet*, zodat de echte `platform.ts` met `loadMapLibre` geladen wordt. Mocks:
- de vier modules uit "Paginatests";
- `vi.mock('$app/env/public', () => ({ PUBLIC_MAPTILER_KEY: 'testkey123' }))`, altijd (N-7). Daardoor hangt de test niet af van `web/.env` of van het resolven van de virtuele module. Er staat bewust een niet-lege key in, zodat het lui laden niet steunt op een ontbrekende key;
- `const probe = vi.hoisted(() => ({ imported: false }))` en `vi.mock('maplibre-gl', () => { probe.imported = true; return {}; })`.

Verder: `const fetchSpy = vi.fn(); vi.stubGlobal('fetch', fetchSpy)` (opruimen met `vi.unstubAllGlobals()`). De test rendert `src/routes/+page.svelte` met `homeData()`, zonder interactie, en wacht een tick. Dan geldt:
- `probe.imported === false`;
- geen enkele `fetchSpy`-aanroep (dus ook geen met een eerste argument dat `api.maptiler.com` bevat);
- `document.querySelector('[src*="maptiler"], [href*="api.maptiler.com"]') === null`;
- geen `.map-canvas`;
- `Lijst` heeft `aria-pressed="true"` en de lijstlink `Teststrand` is zichtbaar.

Daarnaast blijven alle bestaande webtests groen, in het bijzonder:
- `spot-list.test.ts`: rendert dezelfde pagina, de wissel doet zonder klik niets. Zie stap 7 voor `$app/env/public`;
- `favorite-star.test.ts`, `no-third-party.test.ts`, `layout.test.ts`, `guard.test.ts` en `no-local-date-getters.test.ts`.

Ook `cd ingest && uv run pytest` blijft groen.

### Per acceptatiecriterium
- **AC-1:** `cd web && npm ci && npm run check && npm test && npm run build && npm run verify:build`, en vanuit de root `bash scripts/check-no-client-openmeteo.sh`. In CI draait dit via de bestaande job `web`, zonder `PUBLIC_MAPTILER_KEY`: dat test meteen dat de build slaagt zonder key.
- **AC-2:**
  - letterlijk: `grep -rl "maplibre" web/build/_app/immutable/entry/` geeft niets, en `grep -rl "maplibre" web/build/_app/immutable/ | grep -v /entry/` geeft minstens één bestand;
  - automatisch: `checkLazyMapLibre` in `npm run verify:build` (CI) met `verify-build.test.ts`, en `map-source.test.ts` (a)–(c) en (g) voor "alleen in een dynamische `import()`".
- **AC-3:** `home-no-map.test.ts`.
- **AC-4:** `map-switch.test.ts` (1), aangevuld met (2) en (4).
- **AC-5:**
  - `map-start.test.ts` (5): de attributiecontrol staat aan met `compact: false`, dus altijd uitgeklapt;
  - `map-view.test.ts` (2) en (7): logo en zichtbare attributie;
  - `map-source.test.ts` (e): geen CSS die `maplibregl-ctrl` aanpast.
- **AC-6:** `NEEDS_LARS`. Na het instellen van de productiekey (RUNBOOK §11.9) opent Lars op de gedeployde site `/` en klikt op "Kaart". Hij controleert:
  - markers met dezelfde oordelen als de lijst;
  - een klik op een marker opent de spotpagina;
  - rechtsonder "© MapTiler © OpenStreetMap contributors | MapLibre", linksonder het MapTiler-logo;
  - in het MapTiler-dashboard (Analytics) na een week het aantal requests (A2).

## Externe afhankelijkheden
Gecontroleerd op 15 oktober 2026.

| Package | Versie | Reden |
|---|---|---|
| `maplibre-gl` | ^6.14.0 (`latest` op npm; BSD-3-Clause; alleen ESM; `exports` met `"."` en `"./dist/*"`) | Kaartrenderer, open source, zonder telemetrie. Gebundeld via npm (geen CDN). |

| Onderwerp | Gebruik | Bron |
|---|---|---|
| MapTiler gratis plan: 5.000 map sessions, **100.000 API-requests**/maand, gepauzeerd bij overschrijding, logo verplicht, niet commercieel; "Tile API Requests are billed for usage of MapTiler maps with third-party SDKs" | A2, R1 | https://www.maptiler.com/cloud/pricing/ |
| Sessions tegenover requests (sessions alleen met de MapTiler SDK of de Leaflet-plugin); alleen tiles tellen (vector 1, raster 512 px 4); style, TileJSON en fonts gratis | A2 | https://docs.maptiler.com/guides/maps-apis/maps-platform/tile-requests-and-map-sessions-compared/ |
| Maps API: `GET https://api.maptiler.com/maps/{mapId}/style.json?key=…`; voorbeeld-id `streets-v4` | `mapStyleUrl` | https://docs.maptiler.com/cloud/api/maps/, https://docs.maptiler.com/maplibre/ |
| Attributie: tekst "© MapTiler" en "© OpenStreetMap contributors" met links naar `maptiler.com/copyright` en `openstreetmap.org/copyright`, rechtsonder. Gratis plan: logo linksonder met `<a href="https://www.maptiler.com" style="position:absolute;left:10px;bottom:10px;z-index:999;"><img src="https://api.maptiler.com/resources/logo.svg" alt="MapTiler logo"></a>`; met MapLibre moet het logo zelf toegevoegd worden | A8, `MapView` | https://docs.maptiler.com/guides/map-design/attribution/add-attribution/ |
| Key-restrictie "Allowed HTTP origins": één domein per regel, `*.domein` voor subdomeinen, localhost zonder poort en protocol (`localhost`, `127.0.0.1`). "Allowing localhost isn't real security – it matches any machine, including an attacker's"; "Never leave this rule on a key used in production"; aparte keys per omgeving. Het verkeer van alle keys telt mee voor hetzelfde accountquotum | A4, R7, RUNBOOK §11.9 | https://docs.maptiler.com/guides/maps-apis/maps-platform/how-to-protect-your-map-key/ |
| MapTiler SDK: `telemetry` en `session` standaard `true` | A1 (waarom niet de SDK) | https://docs.maptiler.com/sdk-js/api-reference/classes/SdkConfig/ |
| MapLibre v6: alleen ESM (`import * as` of named imports), WebGL2 verplicht, de constructor gooit `GPUInitializationError`; bundlers hebben `setWorkerUrl()` nodig; CSP `worker-src 'self'; img-src data: blob: 'self'` | A10, `start.ts`, WP-23 | https://maplibre.org/maplibre-gl-js/docs/guides/v5-to-v6-migration-guide/, https://maplibre.org/maplibre-gl-js/docs/API/classes/GPUInitializationError/ |
| Vite-installatie v6.14: `import workerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url'; setWorkerUrl(workerUrl);` en `import 'maplibre-gl/dist/maplibre-gl.css'` (zonder CSS werken markers niet) | `loadMapLibre`, R2 | https://maplibre.org/maplibre-gl-js/docs/, https://maplibre.org/maplibre-gl-js/docs/API/functions/setWorkerUrl/ |
| `MapOptions`: `container`, `style`, `bounds`, `fitBoundsOptions`, `center`, `zoom`, `attributionControl` (`false` = uit), `maplibreLogo`, `dragRotate`, `pitchWithRotate`, `touchPitch`, `refreshExpiredTiles` | `start.ts` | https://maplibre.org/maplibre-gl-js/docs/API/type-aliases/MapOptions/ |
| `MapEventType`: `style.load` ("once the map's style has fully loaded or changed, after all necessary resources referenced by the style have been requested"), `load` ("after all necessary resources have been downloaded and the first visually complete rendering"), `error` | `start.ts` stap 5g–5i (N-5) | https://maplibre.org/maplibre-gl-js/docs/API/type-aliases/MapEventType/ |
| `AttributionControlOptions`: `compact: false` = altijd uitgeklapt; `customAttribution`; standaardtekst `<a href="https://maplibre.org/" target="_blank">MapLibre</a>`; dubbele tekst (substrings) wordt weggefilterd | A8, AC-5 | https://maplibre.org/maplibre-gl-js/docs/API/type-aliases/AttributionControlOptions/, https://github.com/maplibre/maplibre-gl-js/blob/main/src/ui/control/attribution_control.ts |
| `MarkerOptions`: `element`, `anchor` (`'bottom'`) | Markers | https://maplibre.org/maplibre-gl-js/docs/API/type-aliases/MarkerOptions/ |
| `Map`: events `style.load`, `load` en `error`, `remove()`, `addControl(control, position)` | `start.ts` | https://maplibre.org/maplibre-gl-js/docs/API/classes/Map/ |
| Vite: `?worker&url` geeft de worker als URL; CSS van async chunks wordt apart gezet | A10, R2 | https://vite.dev/guide/features |
| SvelteKit 3 `defineEnvVars`: de schemafunctie krijgt `undefined` bij een ontbrekende variabele en mag een standaardwaarde teruggeven; een ongeldige waarde laat de build falen | `parseMaptilerKey` | https://svelte.dev/docs/kit/environment-variables |

Geen nieuwe dienst naast MapTiler, dat al in het plan staat. Geen Open-Meteo in de browser, geen CDN, geen analytics.

## Risico's
- **R1. Requestbudget (A2).** Bij onverwacht veel gebruik pauzeert MapTiler tot de volgende maand. Dat kost niets: de app valt terug op de lijst (E6). Mitigatie:
  - de kaart laadt nooit vanzelf (A5);
  - `refreshExpiredTiles: false`;
  - kaart open en data verversen geeft geen nieuwe kaart (E18);
  - geen `localhost` op de productiekey, dus niemand kan de publieke key vanaf zijn eigen machine gebruiken (N-10). De lokale key staat nergens publiek;
  - Lars kijkt na een week in het dashboard (AC-6).
- **R2. Dynamische `import()` met `?worker&url`.** De MapLibre-docs tonen een statische import; de Vite-docs zeggen niet expliciet dat het suffix ook in een dynamische `import()` werkt. Een `import()` met een vaste string loopt wel door dezelfde resolve- en load-hooks, dus de verwachting is dat het werkt. Stap 8 controleert dat het workerbestand in de build staat en met 200 laadt. **Terugvaloptie**, alleen als `npm run build` faalt of de worker 404 geeft. De reviewer heeft hem vooraf aanvaard onder drie voorwaarden; zie stap 9 voor de exacte uitvoering:
  - `src/lib/map/runtime.ts` krijgt de drie statische imports en `setWorkerUrl`, en dat bestand wordt alleen via `import('./runtime.js')` geladen;
  - **voorwaarde 1:** de afwijking komt in `deviations.md`;
  - **voorwaarde 2:** `map-source.test.ts` krijgt een extra test die bewijst dat `runtime` in `src/` alleen binnen een `import(…)` voorkomt;
  - **voorwaarde 3:** de orchestrator meldt de afwijking aan Lars.

  Het lui laden blijft gewaarborgd (AC-2-buildcheck), maar "alleen in een dynamische `import()`" geldt dan per module in plaats van per regel.
- **R3. MapLibre v6 is nieuw (ESM-only, WebGL2).** Oudere apparaten zonder WebGL2 krijgen de melding `no_webgl` (E3). De typen komen uit het package zelf, dus API-fouten vangt `npm run check`.
- **R4. Bundelgrootte.** De MapLibre-chunk is ±800 kB (±250 kB gzip). Vite kan waarschuwen dat een chunk groter is dan 500 kB; dat is een waarschuwing, geen fout. De entry en de pagina-chunk worden niet groter, op enkele kB voor `config`, `markers`, `start` en de componenten na. Wel precachet de SW de chunk (A9, doorgegeven aan WP-23).
- **R5. Stijl `streets-v4` op het gratis plan.** De docs gebruiken hem als voorbeeld, en de vooraf ingestelde Street-kaarten zitten in het gratis plan. Dat juist `streets-v4` erin zit, staat er niet expliciet. Werkt hij niet (403 op de style), dan volgt `load_failed` en kiest Lars een andere stijl in MapTiler Cloud. Dat is één constante.
- **R6. Attributie dubbel (A8).** De bronattributie van MapTiler in de control en onze regel onder de kaart overlappen. Dat is bewust: de regel onder de kaart is te testen en staat er ook als de style een andere tekst gebruikt.
- **R7. Privacy.** Na de klik krijgt MapTiler het IP-adres van de gebruiker, de origin (bij cross-origin-requests stuurt de browser altijd een `Origin`-header) en, volgens de standaard Referrer-Policy van de browser, de herkomst. De origin-restrictie kijkt naar de origin van het verzoek, niet naar de Referer. Deze WP zet geen `referrerpolicy`: dat is aan WP-23. Er is geen telemetrie (geen SDK). WP-23 neemt dit op in de privacypagina.
- **R8. Rebase met WP-12 en latere WP's.** Deze WP raakt `+page.svelte` (vier regels, ankers op tekst), `package.json` en `package-lock.json`, `env.ts`, `env-schema.ts`, `.env.example`, `verify-build.mjs` en de RUNBOOK (§4 en §11.9). WP-12 raakt andere RUNBOOK-secties en de spotpagina. Geeft de lockfile een conflict, neem dan `develop` over en draai `npm install maplibre-gl@^6.14.0` opnieuw. Stijlen staan in de componenten, niet in `app.css`.
- **R9. Overlappende labels** bij spots dicht bij elkaar (E21). Clustering valt buiten scope.
- **R10. Lege ondergrond (E8).** Lukt de style wel maar falen alle tiles (bijvoorbeeld een quotum dat midden in een sessie opraakt), dan kan `load` toch komen en ziet de gebruiker markers op een lege kaart, met één `console.warn`. De markers en de lijst blijven bruikbaar. Bewust geaccepteerd (N-5): een fallback bij elke tilefout zou de kaart op mobiele netwerken te snel afbreken.

## Buiten scope
- Geolocatie of de locatie van de gebruiker, clustering, popups, een eigen kaartstijl, 3D, terrein en offline tiles.
- De gekozen weergave onthouden (A5) en een kaart op de spotpagina.
- Favorietensterren op markers.
- CSP-headers, `Referrer-Policy`, de privacypagina en de precache-afweging (WP-23), en monitoring van het MapTiler-verbruik (WP-22).
- Wijzigingen aan `Attribution.svelte`, `FavoriteStar.svelte`, `favorites.ts`, `/over`, `app.css`, de service worker, `vite.config.ts`, `data.ts`, `types.ts`, `ingest/`, `supabase/`, `data/` en `.github/`.
- Aanpassingen aan `WORK_PACKAGES.md` (zie "Gevolgen", orchestrator).

## Stappenplan voor de builder
Werk in de worktree `/Users/larst/Dev/Shakka/.claude/worktrees/WP-15` op branch `wp/WP-15`, met Node 24 (`engine-strict`). De branch is al gerebased op `develop` (met WP-16); er is geen merge-stap nodig. Lees of print `.env` en `web/.env` nooit. Draai na elke stap vanuit `web/`: `npm run check && npm test`. Maak per stap één commit, in het Engels (bijv. `WP-15: add optional PUBLIC_MAPTILER_KEY`).

1. **Env (tests eerst).**
   - Breid `test/env-schema.test.ts` uit en pas `test/env-example.test.ts` aan. Rood.
   - Voeg `parseMaptilerKey` toe aan `src/lib/env-schema.ts`, de variabele aan `src/env.ts` en de twee regels aan `.env.example`. Groen.
   - Controleer dat `npm run build` slaagt zonder key: `PUBLIC_MAPTILER_KEY= npm run build`. Een lege variabele in de shell gaat vóór `web/.env`, en het schema maakt er `''` van.
   - Controleer ook dat `PUBLIC_MAPTILER_KEY='a b' npm run build` faalt zonder de waarde te tonen.
2. **Package.**
   - Draai `npm install maplibre-gl@^6.14.0`.
   - Controleer in `node_modules/maplibre-gl`:
     - `dist/maplibre-gl-worker.mjs` en `dist/maplibre-gl.css` bestaan;
     - `dist/maplibre-gl.d.ts` exporteert `setWorkerUrl`, `Map`, `Marker`, `NavigationControl` en `GPUInitializationError`.
   - Ontbreekt `GPUInitializationError`: zie `start.ts` en schrijf het in `deviations.md`.
3. **Config (tests eerst).** Schrijf `test/map-config.test.ts`. Rood. Maak `src/lib/map/config.ts`. Groen.
4. **Markers (tests eerst).** Schrijf `test/fixtures/map-data.ts` en `test/map-markers.test.ts`. Rood. Maak `src/lib/map/markers.ts` (met `data-marker-spot`). Groen.
5. **Platform en start (tests eerst).**
   - Schrijf `test/helpers/fake-maplibre.ts`, `test/map-start.test.ts` (inclusief (7a), (7b) en (9)) en `test/map-source.test.ts` (inclusief (g)). Rood.
   - Maak `src/lib/map/platform.ts` en `src/lib/map/start.ts`. Groen.
   - Meldt `svelte-check` dat de typen voor `?worker&url` of `.css` ontbreken, zet dan `/// <reference types="vite/client" />` bovenaan `src/app.d.ts`.
6. **Componenten.** Maak `MapView.svelte` (met het `$effect` uit N-6) en `MapSwitch.svelte`. Schrijf `test/map-view.test.ts` (inclusief (8)). Groen.
7. **Pagina.**
   - Breng de vier wijzigingen aan in `src/routes/+page.svelte`, op de tekstankers uit Interfaces.
   - Schrijf `test/map-switch.test.ts` en `test/home-no-map.test.ts`, met de mocks uit "Paginatests" (inclusief `#lib/favorites.js`). `home-no-map` mockt ook `$app/env/public`.
   - Draai de hele suite. Groen, inclusief de bestaande `spot-list.test.ts` en `favorite-star.test.ts`.
   - Faalt `spot-list.test.ts` (of een andere bestaande test die de pagina rendert) doordat `$app/env/public` in vitest niet resolvet: voeg in dat bestand, naast de bestaande mocks, precies `vi.mock('$app/env/public', () => ({ PUBLIC_MAPTILER_KEY: '' }));` toe en noteer het in `deviations.md`. Pas verder niets aan in die tests.
8. **Buildcheck (tests eerst).**
   - Breid `test/verify-build.test.ts` uit. Rood.
   - Voeg `checkLazyMapLibre` toe aan `scripts/verify-build.mjs`. Groen.
   - Daarna `npm run build && npm run verify:build`.
   - Draai beide AC-2-greps letterlijk. Geeft de eerste grep toch een treffer (MapLibre in de entry): schrijf `deviations.md` en maak `MapView` in `MapSwitch` ook lui (`{#await import('#lib/components/MapView.svelte') then m}<m.default … />{/await}`).
   - **Rooktest (lokaal):**
     - `PUBLIC_MAPTILER_KEY= npm run build && npm run preview`: `/` toont de lijst. Een klik op "Kaart" geeft de melding `no_key`, en in DevTools, Network staat geen request naar `maptiler` en geen `maplibre`-chunk.
     - `PUBLIC_MAPTILER_KEY=dummykey12345 npm run build && npm run preview` (geen echte key; niet committen, niet in `web/.env`). Klik op "Kaart" en controleer:
       - de `maplibre`-chunk, de CSS en het workerbestand (`maplibre-gl-worker…`) laden met 200, niet 404 (R2);
       - de style-request naar `api.maptiler.com` geeft 401 of 403;
       - binnen enkele seconden staat de melding `load_failed` er en is de lijst terug.
     - Daarna gewoon `npm run build && npm run preview`. Toont de kaart dan echt tegels, dan staat er een lokale key van Lars in `web/.env` (lees het bestand niet). Doe in dat geval ook de controle uit AC-6 op `localhost`. Noteer in de DevTools of er rastertiles (`.png`/`.webp`/`.jpg`) worden geladen; dat is relevant voor A2.
   - Faalt de build of geeft de worker 404: stap 9. Anders sla je stap 9 over.
9. **Alleen bij falen van R2: terugvaloptie.** Voer alles uit; de reviewer heeft deze terugval alleen onder deze drie voorwaarden aanvaard.
   - a. Maak `src/lib/map/runtime.ts`:
      ```ts
      import * as lib from 'maplibre-gl';
      import workerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url';
      import 'maplibre-gl/dist/maplibre-gl.css';
      lib.setWorkerUrl(workerUrl);
      export { lib };
      ```
   - b. In `platform.ts` wordt de `Promise.all` in `loadMapLibre`: `import('./runtime.js').then((m) => m.lib)`, met dezelfde `pending`/reset-logica. `export type MapLibre = typeof import('maplibre-gl')` blijft.
   - c. Pas `map-source.test.ts` aan:
      - (a) en (b) slaan alleen `src/lib/map/runtime.ts` over;
      - (c) wordt "de enige bestanden met `maplibre-gl` zijn `platform.ts` en `runtime.ts`";
      - (g) wordt "in `platform.ts` precies één treffer op `typeof import(` en precies één `maplibre-gl`-literal".
   - d. **Voorwaarde 2, extra brontest** in `map-source.test.ts` (`describe('runtime is only loaded lazily')`). Voor elk `.ts`- en `.svelte`-bestand onder `src/` behalve `runtime.ts` zelf:
      - het aantal treffers van `/(['"\x60])[^'"\x60\n]*\bruntime(?:\.js|\.ts)?\1/g` is gelijk aan het aantal treffers van `/\bimport\(\s*(['"\x60])[^'"\x60\n]*\bruntime(?:\.js|\.ts)?\1\s*\)/g`;
      - het enige bestand met een treffer is `src/lib/map/platform.ts`, met precies één `import('./runtime.js')`;
      - geen treffer op `/from\s+['"][^'"]*\bruntime(?:\.js|\.ts)?['"]/` en `/import\s+['"][^'"]*\bruntime/`. Dat geldt ook voor `import type`.
   - e. **Voorwaarde 1:** schrijf in `docs/wp/WP-15/deviations.md` een kopje "R2: terugval naar runtime.ts". Zet erin: wat faalde (de foutmelding van de build of de 404 op de worker, zonder keys), de nieuwe opzet, dat AC-2 nu per module geldt in plaats van per regel, en welke tests het lui laden bewaken (`checkLazyMapLibre`, `map-source` (a)–(d)).
   - f. **Voorwaarde 3:** zet in `deviations.md` de regel "Melden aan Lars door de orchestrator: AC-2 (bron) wordt per module gehaald via `runtime.ts`." De orchestrator neemt dat over in de PR-beschrijving en meldt het aan Lars. Als builder meld je het ook expliciet in je eindrapport.
   - g. Herhaal stap 8 (build, `verify:build`, de greps en de rooktest met `dummykey12345`).
10. **Documentatie.** Werk `docs/RUNBOOK.md` bij.
    - §4: een rij `| \`PUBLIC_MAPTILER_KEY\` | \`web/.env\` (lokale key), Cloudflare Pages (productiekey) | web: kaart (optioneel, publiek) | WP-15 |`.
    - §11: een nieuw punt **9. Kaart (vanaf WP-15).**, direct na punt 8 (WP-16). Inhoud, in deze volgorde:
      - Maak een gratis MapTiler Cloud-account. Maak onder Account, API keys **twee** keys: één voor productie en één voor lokaal.
      - **Productiekey:** onder "Allowed HTTP origins" alleen `<project>.pages.dev` en `*.<project>.pages.dev` (previews), één per regel. **Nooit `localhost` of `127.0.0.1` op deze key.** De key staat publiek in de app, en volgens MapTiler matcht localhost elke machine, dus iedereen zou dan je quotum kunnen opmaken.
      - **Lokale key (optioneel):** onder "Allowed HTTP origins" `localhost` en `127.0.0.1` (zonder poort en protocol). Zet hem alleen in `web/.env`, nooit in Cloudflare Pages en nooit in de repo. Zonder lokale key werkt de lijst gewoon.
      - Alle keys delen het quotum van het account.
      - Zet `PUBLIC_MAPTILER_KEY` = de productiekey in Cloudflare Pages (Production en Preview). Het is een publieke key, geen secret. De waarde komt bij de build in de app, dus na een wijziging is een nieuwe deploy nodig.
      - Zonder key werkt de app gewoon, en geeft "Kaart" een melding.
      - De kaart laadt alleen na een klik op "Kaart".
      - MapTiler rekent bij MapLibre in API-requests: 100.000 per maand gratis, en alleen tiles tellen. Bij overschrijding is het gepauzeerd tot de volgende maand (geen kosten; de app valt terug op de lijst).
      - Het verbruik staat in MapTiler Cloud, Analytics.
      - **Key vervangen** (bijvoorbeeld bij misbruik): maak een nieuwe productiekey met dezelfde origins, zet hem in Cloudflare Pages, deploy opnieuw en verwijder daarna de oude key in MapTiler Cloud.

      Is §11.9 bij een rebase al bezet, neem dan het volgende vrije nummer en noteer het nummer in `deviations.md`; de orchestrator past de verwijzingen in AC-6 en "Nodig van Lars" aan.
11. **Eindcontrole.**
    - `cd web && npm ci && npm run check && npm test && npm run build && npm run verify:build`;
    - de twee AC-2-greps;
    - vanuit de root `bash scripts/check-no-client-openmeteo.sh` (exit 0);
    - de AC-6-grep van WP-13 (`grep -rEn "googletagmanager|google-analytics|plausible|fonts.googleapis|cdn\." web/src web/static` geeft niets);
    - `cd ingest && uv run pytest`;
    - `git status`: geen `web/.env`, `web/build` of `node_modules` gestaged.

**Nodig van Lars (AC-6):**
- een gratis MapTiler-account met twee API-keys (RUNBOOK §11.9):
  - een **productiekey** met "Allowed HTTP origins" alleen `<project>.pages.dev` en `*.<project>.pages.dev`, **zonder** `localhost`;
  - optioneel een **lokale key** met origin `localhost` en `127.0.0.1`, alleen in `web/.env`;
- `PUBLIC_MAPTILER_KEY` = de productiekey in Cloudflare Pages (Production en Preview), daarna een nieuwe deploy;
- de controle uit AC-6 op de gedeployde site, plus na een week een blik op het aantal requests;
- een reactie op de voorstellen A3 (stijl `streets-v4`), A5 (keuze niet onthouden) en A6 (wat een marker toont);
- alleen als de terugval van R2 nodig was: kennisnemen van de afwijking in `deviations.md` (via de orchestrator).
