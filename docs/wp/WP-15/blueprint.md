# Blueprint WP-15: Kaart
Status: DRAFT
Revisie: 1

## Doel
Op `/` komt naast de spotlijst een kaartweergave van de spots, met per spot een marker met het oordeel als tekst en kleur. Een klik op een marker opent de spotpagina. De kaart laadt pas als de gebruiker op "Kaart" klikt. Vóór die klik gaat er geen enkel request naar MapTiler en wordt er geen MapLibre-code geladen. De lijst blijft de standaard. Zonder key, zonder WebGL2 of bij een storing bij MapTiler valt de app terug op de lijst, met een Nederlandse melding. De attributie van MapTiler, OpenStreetMap en MapLibre en het MapTiler-logo zijn zichtbaar.

Deze WP voegt alleen code toe. Wijzigingen aan bestaande bestanden zijn klein, omdat WP-12 en WP-16 tegelijk in `web/` werken.

## Aannames
Voorstellen waar Lars op kan reageren, staan als **Voorstel**.

- **A1. MapLibre GL JS v6 rechtstreeks, niet de MapTiler SDK.** `maplibre-gl` ^6.14.0 komt als npm-package in de bundel, dus geen CDN. De MapTiler SDK zet standaard telemetrie aan (`config.telemetry`, default `true`; verstuurt onder andere de API-key, de sessie-id en de SDK-versie). Dat botst met "geen tracking". De SDK is bovendien een extra laag bovenop MapLibre.
- **A2. Gevolg van A1 voor het budget: MapTiler rekent dan in API-requests, niet in map sessions.** Op de prijspagina staat: "Tile API Requests are billed for usage of MapTiler maps with third-party SDKs". Het gratis plan heeft 100.000 requests per maand (naast 5.000 sessions voor de SDK) en wordt daarna gepauzeerd tot de volgende maand, zonder kosten. Schatting per keer dat de kaart opent: style 1, TileJSON 1, sprites 2–4, glyphs ±6, tiles ±10–40 bij wat pannen en zoomen. Dat is ±25–60 requests, dus ruim 1.500 keer openen per maand. Bij tientallen gebruikers die de kaart een paar keer per week openen, komt dat uit op ±25.000 requests. De HTTP-cache van de browser haalt daar nog wat af. De regel "MapTiler gratis" in "Gecontroleerde externe documentatie" (WORK_PACKAGES) noemt alleen sessions. Die moet de orchestrator bijwerken (zie "Gevolgen").
- **A3. Voorstel: stijl `streets-v4`** (`https://api.maptiler.com/maps/streets-v4/style.json?key=…`, het voorbeeld in de MapTiler-docs voor MapLibre). Een andere stijl wijzigen kost één constante (`MAPTILER_STYLE_ID`).
- **A4. De key is optioneel en publiek.** `PUBLIC_MAPTILER_KEY` komt in `src/env.ts` met `public: true, static: true` en wordt dus bij de build in de bundel gezet. Het is geen secret. Lars beperkt de key in MapTiler Cloud met "Allowed HTTP origins". Ontbreekt de key of is hij leeg, dan is de waarde `''` en geeft de kaartwissel de melding "niet beschikbaar"; de build slaagt gewoon. Een key met andere tekens dan `A–Z a–z 0–9 _ -`, of met een lengte buiten 8–128, laat de build falen met een melding zonder de waarde. Dat volgt het patroon van WP-13.
- **A5. De weergavekeuze wordt niet onthouden.** Elke keer dat `/` opnieuw opent, ook via de terugknop vanaf een spotpagina, staat de lijst er weer. Er is geen `localStorage` en geen snapshot. Zo opent de kaart alleen na een bewuste klik, en dat houdt het aantal requests laag.
- **A6. Voorstel: wat een marker toont.** De marker toont de naam van de spot plus een oordeelsbadge (dezelfde `.verdict-*`-kleuren en labels als de lijst):
  - `today.best` als die er is (bijvoorbeeld "Go");
  - anders, na zonsondergang, `tomorrow.best` met het voorvoegsel "Morgen: " (bijvoorbeeld "Morgen: Twijfel");
  - anders een grijze badge "Nog geen data".

  Een niet-geverifieerde spot krijgt een gestippelde rand plus de verborgen tekst " (niet geverifieerd)" voor schermlezers. Onder de kaart staat een legenda.
- **A7. Een spot zonder bruikbare coördinaten staat niet op de kaart.** Dat geldt voor `lat` of `lon` gelijk aan `null`, niet eindig, of buiten het bereik. Onder de kaart staat dan "N spots zonder coördinaten staan niet op de kaart." Er worden geen coördinaten verzonnen.
- **A8. De attributie staat twee keer, zodat ze in elk geval klopt.**
  - Op de kaart: de `AttributionControl` van MapLibre met `compact: false` (altijd uitgeklapt). Daarin staat de attributie uit de MapTiler-bronnen, plus `customAttribution` = de standaardtekst van MapLibre.
  - Onder de kaart, door Svelte gerenderd en dus te testen: "Kaart: © MapTiler · © OpenStreetMap contributors · MapLibre", met links.
  - Het MapTiler-logo staat linksonder, volgens de HTML van MapTiler voor het gratis plan. Het wordt pas getoond als de kaart geladen is, zodat er bij een fallback ook geen logo-request is.
- **A9. Alleen MapLibre's eigen `import()`-chunks, geen nieuwe precache-regels.** De service worker van WP-13 precachet alle `_app/immutable`-bestanden, dus ook de MapLibre-chunk (±250 kB gzip, same-origin, geen MapTiler-request). Dat laten we zo. Oude shell en oude chunks blijven zo bij elkaar passen (WP-13 A7): zonder precache faalt `import()` na een nieuwe deploy op een oude chunknaam. Of dit binnen het performancebudget past, beoordeelt WP-23.
- **A10. MapLibre v6 vraagt `setWorkerUrl` bij bundlers.** De MapLibre-docs geven voor Vite precies `import workerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url'`, gevolgd door `setWorkerUrl(workerUrl)`. Wij doen dat met een dynamische `import()` van dezelfde specifier (zie R2).
- **A11. Geen geolocatie, geen clustering, geen popups.** De marker is zelf een link naar `/spot/<id>`.

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
- `start.ts` bevat de hele levenscyclus: preflight, laden, kaart maken, `load`/`error`, timeout, markers, opruimen. MapLibre komt binnen als dependency (`load()`), dus alle faalpaden zijn te testen met een nep-MapLibre, zonder WebGL.
- `platform.ts` is het enige bestand dat `$app/env/public` voor de kaart leest, een WebGL2-context maakt en MapLibre importeert. Tests mocken dit ene bestand.

**Lui laden.** `maplibre-gl`, de worker-URL en de CSS staan in de bron alleen als dynamische `import()` in `platform.ts`. Daar staat ook het type `MapLibre = typeof import('maplibre-gl')`, dat bij het compileren verdwijnt. `start.ts` importeert alleen dat type uit `platform.ts`. `loadMapLibre()` wordt pas aangeroepen als `MapView` mount, en dat gebeurt alleen nadat iemand op "Kaart" heeft geklikt en de preflight (key, WebGL2) gelukt is. Vite zet MapLibre daardoor in een eigen chunk buiten `_app/immutable/entry/`. `verify:build` controleert dat na elke build.

**Wissel.** `MapSwitch` toont twee knoppen ("Lijst", "Kaart") met `aria-pressed`. De pagina bindt `view` en verbergt de `<ul class="spot-list">` met het attribuut `hidden` zolang `view === 'map'`. De lijst blijft dus in de DOM, en de wijziging aan `+page.svelte` is vier regels.

Bij elke fout gaat `view` terug naar `'list'` en verschijnt er een melding met `role="status"`. De mogelijke fouten:
- preflight: geen key, geen WebGL2;
- laden van de chunk;
- de constructor van de kaart gooit een fout (`GPUInitializationError` geeft `no_webgl`);
- een `error`-event vóór `load`, bijvoorbeeld een style die 401/403 geeft door een foute key, een domeinrestrictie of het quotum;
- geen `load` binnen 30 s.

Fouten ná `load` (losse tiles) geven alleen één `console.warn` zonder details. De kaart blijft dan staan.

**Waarom zo.** Alle beslislogica is puur of krijgt haar dependencies binnen, dus AC-3, AC-4 en AC-5 zijn zonder netwerk en zonder WebGL te toetsen. AC-2 wordt twee keer bewaakt: in de bron (vitest) en in de build (`verify:build`, draait al in CI). De wijzigingen aan gedeelde bestanden zijn klein: vier regels in `+page.svelte`, één variabele in `env.ts` en `.env.example`, één functie in `env-schema.ts` en één check in `verify-build.mjs`.

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
| `web/test/map-config.test.ts`, `map-markers.test.ts`, `map-start.test.ts`, `map-source.test.ts`, `map-view.test.ts`, `map-switch.test.ts`, `home-no-map.test.ts` | aanmaken | Zie Testplan. |
| `docs/RUNBOOK.md` | wijzigen | §4: een rij erbij. §11: een nieuw punt "Kaart (vanaf WP-15)" aan het eind. |

Niet gewijzigd: `app.css` (de kaartstijlen staan in de `<style>`-blokken van de componenten), `Attribution.svelte`, `/over`, de service worker, `vite.config.ts`, `data.ts`, `types.ts`, `ingest/`, `supabase/`, `.github/`. `docs/STATUS.md` en `docs/WORK_PACKAGES.md` werkt de orchestrator bij.

## Interfaces en contracten
Imports van gedeelde code gaan via `#lib/<pad>.js`. `Spot` en `SpotSummary` komen uit `#lib/types.js` (WP-14), `verdictLabel` uit `#lib/labels.js`.

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
- `value?.trim() ?? ''` is leeg → `''`.
- Komt de waarde niet overeen met `/^[A-Za-z0-9_-]{8,128}$/`, dan volgt `throw new Error('PUBLIC_MAPTILER_KEY must be a MapTiler API key (8-128 letters, digits, - or _)')`.
- Anders: de getrimde key.

### `web/.env.example` (toevoeging aan het eind)
```
# MapTiler API key (public; restrict it to your domains under "Allowed HTTP origins" in MapTiler Cloud). Optional: empty = no map, the list keeps working.
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

/** <a class="map-marker[ map-marker-unverified]" href data-spot data-verdict="go|marginal|no_go|none">
 *    <span class="map-marker-name">{name}</span>
 *    <span class="verdict verdict-{verdict|none}">{badge}</span>
 *    [<span class="sr-only"> (niet geverifieerd)</span>]
 *  </a>
 *  Built with createElement and textContent only. */
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

/** Type only; erased at compile time (no runtime import). */
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
Volgorde (vast; de tests controleren hem):
1. Toestand: `destroyed = false`, `failed = false`, `loaded = false`, `warned = false`, `lib = null`, `map = null`, `markers = []`, `current = { spots, summaries }`, `timer = null`.
2. `fail(reason)`:
   - doet niets als `destroyed || failed`;
   - anders `failed = true`, timer wissen, markers verwijderen en `try { map?.remove() } catch {}`;
   - daarna `map = null` en `callbacks.onFail(reason)`.
3. `renderMarkers()`: verwijder de bestaande markers en maak er een per model uit `markerModels(current.spots, current.summaries).markers`:
   `new lib.Marker({ element: createMarkerElement(m, container.ownerDocument), anchor: 'bottom' }).setLngLat([m.lon, m.lat]).addTo(map)`.
4. Asynchroon, als `void (async () => { … })()`:
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
     Gooit de constructor een fout `e`, dan `fail(e instanceof lib.GPUInitializationError ? 'no_webgl' : 'load_failed')`.
   - f. `map.addControl(new lib.NavigationControl({ showCompass: false }), 'top-right')`.
   - g. `map.on('error', () => …)`:
     - `!loaded` → `fail('load_failed')`;
     - anders, de eerste keer: `warned = true`, `console.warn('map resource error')`;
     - verder niets. De event-inhoud wordt nooit gelogd: de style-URL bevat de key.
   - h. `map.on('load', () => …)`:
     - stop bij `destroyed || failed`;
     - anders `loaded = true`, timer wissen, `renderMarkers()` en `callbacks.onReady()`.
   - i. `timer = setTimeout(() => { if (!loaded) fail('load_failed'); }, MAP_LOAD_TIMEOUT_MS)`.
5. `update(s, su)`: `current = { spots: s, summaries: su }`. Alleen als `loaded && !failed && !destroyed` volgt `renderMarkers()` (de kaart wordt niet opnieuw ingepast).
6. `destroy()`: idempotent. `destroyed = true`, timer wissen, markers verwijderen, `try { map?.remove() } catch {}`, `map = null`.

De typen komen uit `MapLibre` (`InstanceType<MapLibre['Map']>`, `InstanceType<MapLibre['Marker']>`). Er is geen eigen nabootsing van de MapLibre-API en geen cast in `src/`. Exporteert `maplibre-gl` geen `GPUInitializationError` (controleer `node_modules/maplibre-gl/dist/maplibre-gl.d.ts` in stap 2), dan geeft elke constructorfout `'load_failed'`, en dat komt in `deviations.md`.

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
- `let container: HTMLDivElement`; `let ready = $state(false)`; `let controller: MapController | null = null`;
- `const notOnMap = $derived(markerModels(spots, summaries).withoutCoords)`;
- `onMount`: `controller = startMap(container, spots, summaries, { key: getMaptilerKey(), webgl: supportsWebGL2, load: loadMapLibre }, { onReady: () => (ready = true), onFail: (r) => onfail?.(r) })`; de cleanup roept `controller?.destroy()` aan en zet `controller = null`;
- `$effect(() => { controller?.update(spots, summaries); })`.

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
Het element `.map-canvas` krijgt van Svelte geen kinderen (MapLibre eist een lege container).

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
1. Bij de imports: `import MapSwitch from '#lib/components/MapSwitch.svelte';`
2. Na `let { data }: PageProps = $props();`: `let view = $state<'list' | 'map'>('list');`
3. Direct na de regel `<Freshness … />`: `<MapSwitch spots={data.spots} summaries={data.summaries} bind:view />`
4. `<ul class="spot-list">` wordt `<ul class="spot-list" hidden={view === 'map'}>`.

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
- **WP-23 (CSP en privacy):**
  - `connect-src` krijgt `https://api.maptiler.com` (style, TileJSON, tiles, glyphs, sprites);
  - `img-src` krijgt `'self' data: blob: https://api.maptiler.com` (sprite en logo);
  - `worker-src 'self'` (de MapLibre-worker is een same-origin-bestand via `setWorkerUrl`; volgens de MapLibre-docs is `blob:` dan niet nodig);
  - de lijst van origins staat in `MAP_EXTERNAL_ORIGINS`;
  - de privacypagina vermeldt dat MapTiler je IP-adres en de Referer ontvangt als je op "Kaart" klikt (niet eerder);
  - de MapLibre-chunk in de precache (A9) valt onder het bundel- en performancebudget.
- **WP-22:** het MapTiler-verbruik (requests, A2) staat alleen in het MapTiler-dashboard, niet via een API. Neem het op in de handmatige maandcheck.
- **WP-18:** `PUBLIC_VAPID_PUBLIC_KEY` wordt de vierde regel in `.env.example` en `env-example.test.ts`.
- **WP-16:** de favorietenster in `.spot-item` werkt ongewijzigd; markers krijgen geen ster.
- **Orchestrator (docs):**
  - in WORK_PACKAGES, de rij "MapTiler gratis" in "Gecontroleerde externe documentatie": "5.000 map sessions/maand (MapTiler SDK) of 100.000 API-requests/maand (andere SDK's zoals MapLibre GL JS; Shakka valt hieronder)";
  - het doel van WP-15 noemt "5.000 MapTiler-sessies"; lees dat als het requestbudget (A2).

## Edge cases

| # | Geval | Gedrag |
|---|---|---|
| E1 | `PUBLIC_MAPTILER_KEY` leeg of afwezig | Klik op "Kaart": melding `no_key`, "Lijst" blijft `aria-pressed="true"`, geen `import()`, geen request naar MapTiler, geen WebGL-probe. |
| E2 | Ongeldige key-tekens in de build-env | De build faalt met `PUBLIC_MAPTILER_KEY must be …`, zonder de waarde. |
| E3 | Geen WebGL2 (oude browser, uitgeschakeld) | Preflight: melding `no_webgl`, geen `import()`. |
| E4 | WebGL2-probe slaagt maar de constructor gooit `GPUInitializationError` | `no_webgl`. Een andere constructorfout geeft `load_failed`. |
| E5 | Offline of de chunk is weg na een deploy | `import()` rejectet: `load_failed`. Een volgende klik probeert opnieuw (de promise wordt gereset). |
| E6 | Key geweigerd (domeinrestrictie, verkeerde key) of quotum op, MapTiler gepauzeerd | Style 401/403 geeft een `error` vóór `load`: `load_failed`, de kaart wordt opgeruimd, de lijst staat er weer. |
| E7 | MapTiler hangt (geen `load` binnen 30 s) | `load_failed`. |
| E8 | Tiles falen na `load` (quotum halverwege, storing) | De kaart blijft staan met markers; één `console.warn('map resource error')` per kaart. |
| E9 | Gebruiker klikt "Lijst" terwijl de kaart nog laadt | `destroy()`: er wordt geen kaart meer gemaakt (geen style-request als de chunk nog laadde) en er komen geen callbacks. |
| E10 | Dubbelklik op "Kaart" | De tweede klik doet niets. |
| E11 | Spot zonder `lat`/`lon`, met `NaN` of met `lat = 95` | Geen marker, wel meegeteld in "N spots zonder coördinaten …". |
| E12 | Geen enkele spot met coördinaten | De kaart toont Nederland (`NL_CENTER`, zoom 6,5) zonder markers, plus de notitie. |
| E13 | Eén spot | Bounds van ±0,05° rondom; maximale zoom 11. |
| E14 | Spot zonder summary, of `today` en `tomorrow` zonder uren | Grijze badge "Nog geen data" (`data-verdict="none"`). |
| E15 | Na zonsondergang (`today.best = null`, `tomorrow.best = 'go'`) | Badge "Morgen: Go". |
| E16 | `verified: false` | Gestippelde rand plus de verborgen tekst " (niet geverifieerd)"; de legenda legt het uit. |
| E17 | Spotnaam met HTML (`<img src=x onerror=…>`) | Wordt als tekst getoond (`textContent`); er ontstaat geen element. |
| E18 | `refreshAll()` (hervatten) terwijl de kaart open is | `update()` vervangt de markers; geen nieuwe kaart, geen nieuwe style-request. |
| E19 | Data-refresh geeft `kind: 'error'` of `spots: []` | De tak met de wissel verdwijnt, `MapView` wordt opgeruimd (`destroy`). |
| E20 | Terug van een spotpagina naar `/` | Weer de lijst (A5). |
| E21 | Overlappende markers (spots dicht bij elkaar) | Ze overlappen; inzoomen helpt. Clustering valt buiten scope. |
| E22 | Toetsenbord | Markers zijn `<a>`-links en dus te focussen; de wisselknoppen hebben `aria-pressed`; de zoomknoppen van MapLibre zijn er. |
| E23 | Een developer heeft lokaal een echte key in `web/.env` | De tests zijn er niet van afhankelijk: AC-4 mockt `platform`; de AC-3-test controleert alleen dat er zonder klik niets gebeurt. |

## Testplan
Alle tests staan in `web/test/` en draaien met `npm test` (jsdom, tenzij `// @vitest-environment node`). Tests voor de pure en de geïnjecteerde logica komen vóór de implementatie: `env-schema`, `map-config`, `map-markers`, `map-start` en `checkLazyMapLibre`. Elk bestand met mocks heeft `beforeEach(() => vi.clearAllMocks())`. Wie timers gebruikt, roept `vi.useFakeTimers()` aan en ruimt op met `vi.useRealTimers()`. Pagina-tests mocken `$app/navigation` en `#lib/supabase.js` zoals in `spot-list.test.ts`.

### Fixtures (`web/test/fixtures/map-data.ts`)
Alleen testdata, met coördinaten zoals in WP-14.
- `SPOT_NO_COORDS = { ...SPOT_VERIFIED, id: 'test-zonder', name: 'Testzonder', lat: null, lon: null }`
- `SPOT_EVENING = { ...SPOT_VERIFIED, id: 'test-avond', name: 'Testavond', lat: 52.1, lon: 4.2 }`
- `SUMMARY_GO: SpotSummary` voor `test-meer`:
  - `today { date '2026-07-15', go 2, marginal 1, no_go 0, best 'go', first_go_at '2026-07-15T12:00:00+00:00' }`;
  - `tomorrow { date '2026-07-16', go 0, marginal 0, no_go 1, best 'no_go', first_go_at null }`;
  - `latest_evaluated_at EVALUATED_AT`.
- `SUMMARY_TOMORROW: SpotSummary` voor `test-avond`:
  - `today` met alles 0 en `best null`;
  - `tomorrow { date '2026-07-16', go 0, marginal 2, no_go 0, best 'marginal', first_go_at null }`.
- `MAP_SPOTS = [SPOT_UNVERIFIED, SPOT_VERIFIED, SPOT_EVENING, SPOT_NO_COORDS]` en `MAP_SUMMARIES = { 'test-meer': SUMMARY_GO, 'test-avond': SUMMARY_TOMORROW }`.
- `homeData(overrides)` = `{ kind: 'ok', now: NOW_FRESH, spots: MAP_SPOTS, summaries: MAP_SUMMARIES, ...overrides }`.

### `web/test/helpers/fake-maplibre.ts`
```ts
export class FakeGPUInitializationError extends Error {}
export interface FakeMap {
	options: Record<string, unknown>;
	controls: Array<{ control: unknown; position?: string }>;
	remove: Mock;
	emit(type: 'load' | 'error', event?: unknown): void;
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
- `Map` legt `options` vast, gooit `throwOnConstruct.error` als die gezet is, en heeft `on(type, fn)`, `addControl(c, pos)`, `remove` (een `vi.fn`) en `emit`.
- `Marker` legt `options` vast. `setLngLat(ll)` zet `lngLat` en geeft `this` terug. `addTo(map)` hangt `options.element` in `map.options.container` en geeft `this` terug. `remove()` haalt het element weg en zet `removed = true`.
- `NavigationControl` legt de opties vast in `navigationOptions`.
- `GPUInitializationError` is `FakeGPUInitializationError`.

### Testbestanden

| Bestand | Tests |
|---|---|
| `env-schema.test.ts` (uitbreiding) | `parseMaptilerKey(undefined)`, `('')` en `('  ')` geven `''`. `(' abcDEF123456 ')` geeft `'abcDEF123456'`; `('get_your_own_Key-1')` blijft zoals hij is. Gooien met een melding die met `PUBLIC_MAPTILER_KEY` begint en de waarde niet bevat: `'short1'` (6 tekens), `'abc def 12345'`, `'abc/def12345'`, `'x'.repeat(129)`. |
| `env-example.test.ts` (aangepast) | De regels zijn precies `['PUBLIC_SUPABASE_URL=', 'PUBLIC_SUPABASE_PUBLISHABLE_KEY=', 'PUBLIC_MAPTILER_KEY=']`. |
| `map-config.test.ts` (node) | `mapStyleUrl('abcDEF123456') === 'https://api.maptiler.com/maps/streets-v4/style.json?key=abcDEF123456'`. `preflight('', webgl)` geeft `'no_key'` en roept `webgl` niet aan (`vi.fn`). `preflight('k', () => false)` geeft `'no_webgl'`, `preflight('k', () => true)` geeft `null`. Elke waarde in `MAP_FAILURE_MESSAGE_NL` is niet leeg en bevat "lijst" (hoofdletterongevoelig). `MAP_EXTERNAL_ORIGINS` is precies `['https://api.maptiler.com']`. `MAPLIBRE_ATTRIBUTION` bevat `https://maplibre.org/`. |
| `map-markers.test.ts` | `markerModels(MAP_SPOTS, MAP_SUMMARIES)` geeft `withoutCoords 1` en drie modellen in spotvolgorde: `test-strand` (`verdict null`, `day null`, `badge 'Nog geen data'`, `unverified true`, `href '/spot/test-strand'`, `lon 4.57`, `lat 52.47`), `test-meer` (`'go'`, `'today'`, `'Go'`, `unverified false`) en `test-avond` (`'marginal'`, `'tomorrow'`, `'Morgen: Twijfel'`). Ook geteld als zonder coördinaten: `lat: 95`, `lon: NaN`, `lon: null`. Een summary met alles op 0 en `best null` voor vandaag en morgen geeft `'Nog geen data'`. `initialView([])` geeft `{ kind: 'center', center: [5.3, 52.2], zoom: 6.5 }`. Op de drie modellen: `bounds` ≈ `[[4.15, 52.05], [4.62, 52.52]]` (`toBeCloseTo`). Eén model geeft een box van 0,1° breed. `createMarkerElement`: `tagName 'A'`, `href`-attribuut `/spot/test-meer`, `data-spot`, `data-verdict 'go'`, `.map-marker-name` met tekst `Testmeer`, `.verdict.verdict-go` met tekst `Go`, geen `.sr-only`. Voor `test-strand`: `data-verdict 'none'`, `.verdict-none` met `Nog geen data`, klasse `map-marker-unverified` en `.sr-only` met ` (niet geverifieerd)`. Met de naam `'<img src=x onerror=alert(1)>'`: `el.querySelector('img') === null` en `textContent` bevat de ruwe tekst. |
| `map-start.test.ts` | Met `createFakeMapLibre`, `deps = { key: 'testkey123', webgl: () => true, load: vi.fn(async () => fake.lib) }`, callbacks als `vi.fn` en `flush = () => new Promise((r) => setTimeout(r, 0))` (met fake timers: `await vi.advanceTimersByTimeAsync(0)`). (1) **Nooit synchroon:** met `key: ''` is `onFail` direct na `startMap` nog niet aangeroepen; na `flush` wel, met `'no_key'`, en `load` is niet aangeroepen. (2) `webgl: () => false` geeft `'no_webgl'` en geen `load`. (3) `load` rejectet met `new Error('secret detail')`: `'load_failed'`, `console.warn` precies één keer en zonder `'secret detail'`. (4) `throwOnConstruct = new FakeGPUInitializationError()` geeft `'no_webgl'`; `new Error('x')` geeft `'load_failed'`. (5) **AC-5:** `maps[0].options` bevat `container`, `style: mapStyleUrl('testkey123')`, `attributionControl: { compact: false, customAttribution: MAPLIBRE_ATTRIBUTION }` (`toEqual`, en `not.toBe(false)`), `maplibreLogo: false`, `dragRotate: false`, `pitchWithRotate: false`, `touchPitch: false`, `refreshExpiredTiles: false`, `bounds` en `fitBoundsOptions: { padding: 40, maxZoom: 11 }`. Zonder spots met coördinaten: `center` en `zoom` en geen `bounds`. (6) `navigationOptions[0]` is `{ showCompass: false }` en `controls[0].position` is `'top-right'`. (7) `emit('error')` vóór `load` geeft `'load_failed'` en `remove` één keer. Een `emit('load')` daarna roept `onReady` niet aan en maakt geen markers. (8) `emit('load')` roept `onReady` één keer aan. Er zijn drie markers met `anchor 'bottom'` en `lngLat [4.57, 52.47]`, `[4.57, 52.47]` en `[4.2, 52.1]`, en hun elementen zitten in de container. Twee keer `emit('error')` daarna geeft geen `onFail` en `console.warn` precies één keer. (9) Fake timers: zonder `load` geeft `vi.advanceTimersByTime(30_000)` `'load_failed'`. Met `load` vóór 30 s geeft doorspoelen tot 60 s geen `onFail`. (10) `destroy()` vóór de resolve van `load` (een handmatig deferred promise): na de resolve geen `Map`, geen callbacks. (11) `destroy()` na `load`: alle markers `removed`, `remove` één keer. Een tweede `destroy()` roept `remove` niet nog eens aan. (12) `update([SPOT_VERIFIED], {})` na `load`: de oude drie markers zijn `removed` en er is één nieuwe. `update` vóór `load` gevolgd door `load` geeft markers van de nieuwe data. |
| `map-source.test.ts` (node) | **AC-2 (bron) en AC-5 (niet verborgen).** Loopt door alle `.ts`- en `.svelte`-bestanden onder `src/`. (a) Per bestand: het aantal treffers van `/(['"\x60])[^'"\x60\n]*maplibre-gl[^'"\x60\n]*\1/g` is gelijk aan het aantal treffers van `/\bimport\(\s*(['"\x60])[^'"\x60\n]*maplibre-gl[^'"\x60\n]*\1\s*\)/g`. Zo staat elke stringliteral met `maplibre-gl` binnen een `import(…)`. (b) Geen treffer op `/from\s+['"]maplibre-gl/` en `/import\s+['"]maplibre-gl/`. (c) Het enige bestand met `maplibre-gl` is `src/lib/map/platform.ts` (`start.ts` importeert het type `MapLibre` uit `./platform.js`). Gebruik `maplibre-gl` ook niet in commentaar tussen aanhalingstekens. (d) `api.maptiler.com` staat alleen in `src/lib/map/config.ts`. (e) Geen enkel bestand bevat `maplibregl-ctrl`. (f) `PUBLIC_MAPTILER_KEY` staat alleen in `src/env.ts`, `src/lib/env-schema.ts` (foutmelding) en `src/lib/map/platform.ts`. |
| `verify-build.test.ts` (uitbreiding) | `checkLazyMapLibre` op tijdelijke mappen (`mkdtempSync` in `os.tmpdir()`, opruimen met `rmSync(…, { recursive: true })`). (1) `entry/app.js` zonder `maplibre` en `chunks/maplibre-gl.abc.js` met `maplibre`: `[]`. (2) `entry/start.js` met `import("../chunks/maplibre-gl.abc.js")`: één probleem met `entry`. (3) Geen enkel bestand met `maplibre`: één probleem met `no lazily loaded maplibre chunk`. |
| `map-view.test.ts` | Mockt `#lib/map/platform.js` met `p = vi.hoisted(() => ({ key: 'testkey123', webgl: true, load: vi.fn() }))`: `getMaptilerKey: () => p.key`, `supportsWebGL2: () => p.webgl`, `loadMapLibre: () => p.load()`. `p.load.mockResolvedValue(fake.lib)`. Rendert `MapView` met `MAP_SPOTS`, `MAP_SUMMARIES` en `onfail` als `vi.fn`. (1) Vóór `load`: `role="status"` met `Kaart laden…` en geen `img`. (2) Na `fake.maps[0].emit('load')` (binnen `act`/`tick`): **AC-5**, een link met `href` `https://www.maptiler.com` en daarin `img[alt="MapTiler logo"]` met `src` `https://api.maptiler.com/resources/logo.svg`; links `© MapTiler` (`https://www.maptiler.com/copyright/`), `© OpenStreetMap contributors` (`https://www.openstreetmap.org/copyright`) en `MapLibre` (`https://maplibre.org/`). (3) **Marker opent de spotpagina:** `getByRole('link', { name: /Testmeer/ })` heeft `href` `/spot/test-meer` en bevat `Go`; `/Testavond/` bevat `Morgen: Twijfel`. (4) `1 spot zonder coördinaten staat niet op de kaart.` staat er. (5) `emit('error')` vóór `load` (nieuwe render) roept `onfail` aan met `'load_failed'`. (6) `unmount()` na `load` roept `fake.maps[0].remove` aan. (7) De attributie-alinea staat er ook vóór `load` (tekst `© OpenStreetMap contributors`). |
| `map-switch.test.ts` | **AC-4 en de wissel.** Rendert `src/routes/+page.svelte` met `homeData()`. Mockt `$app/navigation`, `#lib/supabase.js` (gooit, zoals in `spot-list.test.ts`) en `#lib/map/platform.js` (zoals in `map-view`). (1) **AC-4, zonder key** (`p.key = ''`): de klik op `Kaart` geeft `role="status"` met de tekst van `MAP_FAILURE_MESSAGE_NL.no_key`. `Lijst` heeft `aria-pressed="true"`, `ul.spot-list` heeft geen `hidden` en is zichtbaar, en de link `Teststrand` heeft `href="/spot/test-strand"`. `p.load` is niet aangeroepen en er is geen `.map-canvas`. Geen `role="alert"`. (2) Zonder WebGL2 (`p.webgl = false`): de melding `no_webgl`, `p.load` niet aangeroepen. (3) **Gelukt:** de klik op `Kaart` geeft `aria-pressed="true"` op `Kaart`, `ul.spot-list` heeft het attribuut `hidden` en `.map-canvas` bestaat. Na `emit('load')` staan de markers erin. Een klik op `Lijst` haalt `hidden` weg, roept `fake.maps[0].remove` aan, en `.map-canvas` is weg. (4) `p.load` rejectet: na `await` staat de melding `load_failed`, de lijst is zichtbaar en `Lijst` heeft `aria-pressed="true"`. Een tweede klik op `Kaart` probeert opnieuw (`p.load` twee keer aangeroepen). (5) Een tweede klik op `Kaart` terwijl de kaart open is: `p.load` blijft op één aanroep. |
| `home-no-map.test.ts` | **AC-3.** Mockt `platform` *niet*. `const probe = vi.hoisted(() => ({ imported: false }))`. `vi.mock('maplibre-gl', () => { probe.imported = true; return {}; })`, plus `$app/navigation` en `#lib/supabase.js` zoals hierboven. `const fetchSpy = vi.fn(); vi.stubGlobal('fetch', fetchSpy)` (opruimen met `vi.unstubAllGlobals()`). Rendert `src/routes/+page.svelte` met `homeData()`, zonder interactie, en wacht een tick. `probe.imported === false`. Geen enkele `fetchSpy`-aanroep met een eerste argument dat `api.maptiler.com` bevat (zelfs geen enkele aanroep). `document.querySelector('[src*="maptiler"], [href*="api.maptiler.com"]') === null`. Geen `.map-canvas`. `Lijst` heeft `aria-pressed="true"` en de lijstlink `Teststrand` is zichtbaar. |

Daarnaast blijven alle bestaande webtests groen, in het bijzonder `spot-list.test.ts` (rendert dezelfde pagina; de wissel doet zonder klik niets), `no-third-party.test.ts`, `layout.test.ts`, `guard.test.ts` en `no-local-date-getters.test.ts`. Ook `cd ingest && uv run pytest` blijft groen.

### Per acceptatiecriterium
- **AC-1:** `cd web && npm ci && npm run check && npm test && npm run build && npm run verify:build`, en vanuit de root `bash scripts/check-no-client-openmeteo.sh`. In CI draait dit via de bestaande job `web`, zonder `PUBLIC_MAPTILER_KEY`: dat test meteen dat de build slaagt zonder key.
- **AC-2:**
  - letterlijk: `grep -rl "maplibre" web/build/_app/immutable/entry/` geeft niets, en `grep -rl "maplibre" web/build/_app/immutable/ | grep -v /entry/` geeft minstens één bestand;
  - automatisch: `checkLazyMapLibre` in `npm run verify:build` (CI) met `verify-build.test.ts`, en `map-source.test.ts` (a)–(c) voor "alleen in een dynamische `import()`".
- **AC-3:** `home-no-map.test.ts`.
- **AC-4:** `map-switch.test.ts` (1), aangevuld met (2) en (4).
- **AC-5:** `map-start.test.ts` (5) (de attributiecontrol staat aan met `compact: false`, dus altijd uitgeklapt), `map-view.test.ts` (2) en (7) (logo en zichtbare attributie), en `map-source.test.ts` (e) (geen CSS die `maplibregl-ctrl` aanpast).
- **AC-6:** `NEEDS_LARS`. Na het instellen van de key (RUNBOOK §11.8) opent Lars op de gedeployde site `/` en klikt op "Kaart". Hij controleert:
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
| Sessions tegenover requests (sessions alleen met de MapTiler SDK of de Leaflet-plugin) | A2 | https://docs.maptiler.com/guides/maps-apis/maps-platform/tile-requests-and-map-sessions-compared/ |
| Maps API: `GET https://api.maptiler.com/maps/{mapId}/style.json?key=…`; voorbeeld-id `streets-v4` | `mapStyleUrl` | https://docs.maptiler.com/cloud/api/maps/, https://docs.maptiler.com/maplibre/ |
| Attributie: tekst "© MapTiler" en "© OpenStreetMap contributors" met links naar `maptiler.com/copyright` en `openstreetmap.org/copyright`, rechtsonder. Gratis plan: logo linksonder met `<a href="https://www.maptiler.com" style="position:absolute;left:10px;bottom:10px;z-index:999;"><img src="https://api.maptiler.com/resources/logo.svg" alt="MapTiler logo"></a>`; met MapLibre moet het logo zelf toegevoegd worden | A8, `MapView` | https://docs.maptiler.com/guides/map-design/attribution/add-attribution/ |
| Key-restrictie "Allowed HTTP origins" (één domein per regel, `*.domein` voor subdomeinen; de browser moet Origin/Referer sturen) | RUNBOOK §11.8, A4 | https://docs.maptiler.com/guides/maps-apis/maps-platform/how-to-protect-your-map-key/ |
| MapTiler SDK: `telemetry` en `session` standaard `true` | A1 (waarom niet de SDK) | https://docs.maptiler.com/sdk-js/api-reference/classes/SdkConfig/ |
| MapLibre v6: alleen ESM (`import * as` of named imports), WebGL2 verplicht, constructor gooit `GPUInitializationError`; bundlers hebben `setWorkerUrl()` nodig; CSP `worker-src 'self'; img-src data: blob: 'self'` | A10, `start.ts`, WP-23 | https://maplibre.org/maplibre-gl-js/docs/guides/v5-to-v6-migration-guide/, https://maplibre.org/maplibre-gl-js/docs/API/classes/GPUInitializationError/ |
| Vite-installatie v6.14: `import workerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url'; setWorkerUrl(workerUrl);` en `import 'maplibre-gl/dist/maplibre-gl.css'` (zonder CSS werken markers niet) | `loadMapLibre` | https://maplibre.org/maplibre-gl-js/docs/, https://maplibre.org/maplibre-gl-js/docs/API/functions/setWorkerUrl/ |
| `MapOptions`: `container`, `style`, `bounds`, `fitBoundsOptions`, `center`, `zoom`, `attributionControl` (`false` = uit), `maplibreLogo`, `dragRotate`, `pitchWithRotate`, `touchPitch`, `refreshExpiredTiles` | `start.ts` | https://maplibre.org/maplibre-gl-js/docs/API/type-aliases/MapOptions/ |
| `AttributionControlOptions`: `compact: false` = altijd uitgeklapt; `customAttribution`; standaardtekst `<a href="https://maplibre.org/" target="_blank">MapLibre</a>`; dubbele tekst (substrings) wordt weggefilterd | A8, AC-5 | https://maplibre.org/maplibre-gl-js/docs/API/type-aliases/AttributionControlOptions/, https://github.com/maplibre/maplibre-gl-js/blob/main/src/ui/control/attribution_control.ts |
| `MarkerOptions`: `element`, `anchor` (`'bottom'`) | Markers | https://maplibre.org/maplibre-gl-js/docs/API/type-aliases/MarkerOptions/ |
| `Map`: events `load` en `error`, `remove()`, `addControl(control, position)` | `start.ts` | https://maplibre.org/maplibre-gl-js/docs/API/classes/Map/ |
| Vite: `?worker&url` geeft de worker als URL; CSS van async chunks wordt apart gezet | A10, R2 | https://vite.dev/guide/features |
| SvelteKit 3 `defineEnvVars`: de schemafunctie krijgt `undefined` bij een ontbrekende variabele en mag een standaardwaarde teruggeven; een ongeldige waarde laat de build falen | `parseMaptilerKey` | https://svelte.dev/docs/kit/environment-variables |

Geen nieuwe dienst naast MapTiler, dat al in het plan staat. Geen Open-Meteo in de browser, geen CDN, geen analytics.

## Risico's
- **R1. Requestbudget (A2).** Bij onverwacht veel gebruik pauzeert MapTiler tot de volgende maand. Dat kost niets: de app valt terug op de lijst (E6). Mitigatie:
  - de kaart laadt nooit vanzelf (A5);
  - `refreshExpiredTiles: false`;
  - kaart open en data verversen geeft geen nieuwe kaart (E18);
  - Lars kijkt na een week in het dashboard (AC-6).
- **R2. Dynamische `import()` met `?worker&url`.** De MapLibre-docs tonen een statische import; de Vite-docs zeggen niet expliciet dat het suffix ook in een dynamische `import()` werkt. Stap 9 controleert dat het workerbestand in de build staat en met 200 laadt. **Terugvaloptie**, alleen als `npm run build` faalt of de worker 404 geeft:
  - `src/lib/map/runtime.ts` krijgt de drie statische imports en `setWorkerUrl`, plus `export { lib }` met `import * as lib from 'maplibre-gl'`;
  - `loadMapLibre` wordt `import('./runtime.js').then((m) => m.lib)`;
  - `map-source.test.ts` (a)–(c) laat `runtime.ts` dan als enige uitzondering toe;
  - het lui laden blijft (AC-2-buildcheck), maar de letterlijke tekst "alleen in een dynamische `import()`" geldt dan per module in plaats van per regel. Dat komt in `deviations.md` en vraagt bevestiging van de reviewer.
- **R3. MapLibre v6 is nieuw (ESM-only, WebGL2).** Oudere apparaten zonder WebGL2 krijgen de melding `no_webgl` (E3). De typen komen uit het package zelf, dus API-fouten vangt `npm run check`.
- **R4. Bundelgrootte.** De MapLibre-chunk is ±800 kB (±250 kB gzip). Vite kan waarschuwen dat een chunk groter is dan 500 kB; dat is een waarschuwing, geen fout. De entry en de pagina-chunk worden niet groter, op enkele kB voor `config`, `markers`, `start` en de componenten na. Wel precachet de SW de chunk (A9).
- **R5. Stijl `streets-v4` op het gratis plan.** De docs gebruiken hem als voorbeeld, maar niet gecontroleerd is of elke stijl in het gratis plan zit. Werkt hij niet (403 op de style), dan volgt `load_failed` en kiest Lars een andere stijl in MapTiler Cloud. Dat is één constante.
- **R6. Attributie dubbel (A8).** De bronattributie van MapTiler in de control en onze regel onder de kaart overlappen. Dat is bewust: de regel onder de kaart is te testen en staat er ook als de style een andere tekst gebruikt.
- **R7. Privacy.** Na de klik krijgt MapTiler het IP-adres en de Referer van de gebruiker. De Referer is nodig voor de domeinrestrictie, dus er komt geen `referrerpolicy`. Er is geen telemetrie (geen SDK). WP-23 neemt dit op in de privacypagina.
- **R8. Mergeconflicten met WP-12 en WP-16.** Deze WP raakt `+page.svelte` (vier regels), `package.json` en `package-lock.json`, `env.ts`, `env-schema.ts`, `.env.example`, `verify-build.mjs` en de RUNBOOK. Geeft de lockfile een conflict, neem dan `develop` over en draai `npm install maplibre-gl@^6.14.0` opnieuw. Stijlen staan in de componenten, niet in `app.css`.
- **R9. Overlappende labels** bij spots dicht bij elkaar (E21). Clustering valt buiten scope.

## Buiten scope
- Geolocatie of de locatie van de gebruiker, clustering, popups, een eigen kaartstijl, 3D, terrein en offline tiles.
- De gekozen weergave onthouden (A5) en een kaart op de spotpagina.
- CSP-headers en de privacypagina (WP-23), en monitoring van het MapTiler-verbruik (WP-22).
- Wijzigingen aan `Attribution.svelte`, `/over`, `app.css`, de service worker, `vite.config.ts`, `data.ts`, `types.ts`, `ingest/`, `supabase/`, `data/` en `.github/`.
- Aanpassingen aan `WORK_PACKAGES.md` (zie "Gevolgen", orchestrator).

## Stappenplan voor de builder
Werk in de worktree `/Users/larst/Dev/Shakka/.claude/worktrees/WP-15` op branch `wp/WP-15`, met Node 24 (`engine-strict`). Lees of print `.env` en `web/.env` nooit. Draai na elke stap vanuit `web/`: `npm run check && npm test`. Maak per stap één commit, in het Engels (bijv. `WP-15: add optional PUBLIC_MAPTILER_KEY`).

1. **Env (tests eerst).**
   - Breid `test/env-schema.test.ts` uit en pas `test/env-example.test.ts` aan. Rood.
   - Voeg `parseMaptilerKey` toe aan `src/lib/env-schema.ts`, de variabele aan `src/env.ts` en de twee regels aan `.env.example`. Groen.
   - Controleer dat `npm run build` slaagt zonder `PUBLIC_MAPTILER_KEY`: gebruik een schone shell met alleen de twee Supabase-placeholders uit WP-13 stap 9, zonder `web/.env` aan te raken. Doe dat bijvoorbeeld met `env -u PUBLIC_MAPTILER_KEY PUBLIC_SUPABASE_URL=http://127.0.0.1:54321 PUBLIC_SUPABASE_PUBLISHABLE_KEY=sb_publishable_ci npm run build` in een kopie van de worktree zonder `.env`, of vertrouw op CI.
   - Controleer ook dat `PUBLIC_MAPTILER_KEY='a b'` de build laat falen zonder de waarde te tonen.
2. **Package.**
   - Draai `npm install maplibre-gl@^6.14.0`.
   - Controleer in `node_modules/maplibre-gl`:
     - `dist/maplibre-gl-worker.mjs` en `dist/maplibre-gl.css` bestaan;
     - `dist/maplibre-gl.d.ts` exporteert `setWorkerUrl`, `Map`, `Marker`, `NavigationControl` en `GPUInitializationError`.
   - Ontbreekt `GPUInitializationError`: zie `start.ts` en schrijf het in `deviations.md`.
3. **Config (tests eerst).** Schrijf `test/map-config.test.ts`. Rood. Maak `src/lib/map/config.ts`. Groen.
4. **Markers (tests eerst).** Schrijf `test/fixtures/map-data.ts` en `test/map-markers.test.ts`. Rood. Maak `src/lib/map/markers.ts`. Groen.
5. **Platform en start (tests eerst).**
   - Schrijf `test/helpers/fake-maplibre.ts`, `test/map-start.test.ts` en `test/map-source.test.ts`. Rood.
   - Maak `src/lib/map/platform.ts` en `src/lib/map/start.ts`. Groen.
   - Meldt `svelte-check` dat de typen voor `?worker&url` of `.css` ontbreken, zet dan `/// <reference types="vite/client" />` bovenaan `src/app.d.ts`.
6. **Componenten.** Maak `MapView.svelte` en `MapSwitch.svelte`. Schrijf `test/map-view.test.ts`. Groen.
7. **Pagina.** Breng de vier wijzigingen aan in `src/routes/+page.svelte`. Schrijf `test/map-switch.test.ts` en `test/home-no-map.test.ts`. Groen, inclusief de bestaande `spot-list.test.ts`.
8. **Buildcheck (tests eerst).**
   - Breid `test/verify-build.test.ts` uit. Rood.
   - Voeg `checkLazyMapLibre` toe aan `scripts/verify-build.mjs`. Groen.
   - Daarna `npm run build && npm run verify:build`.
   - Draai beide AC-2-greps letterlijk. Geeft de eerste grep toch een treffer (MapLibre in de entry): schrijf `deviations.md` en maak `MapView` in `MapSwitch` ook lui (`{#await import('#lib/components/MapView.svelte') then m}<m.default … />{/await}`).
9. **Rooktest (lokaal).**
   - `npm run build && npm run preview`, zonder key: `/` toont de lijst. Een klik op "Kaart" geeft de melding `no_key`, en in DevTools, Network staat geen request naar `maptiler` en geen `maplibre`-chunk.
   - Bouw daarna in een tijdelijke shell met `PUBLIC_MAPTILER_KEY=dummykey12345` (geen echte key; niet committen, niet in `web/.env`) en open preview. Klik op "Kaart" en controleer:
     - de `maplibre`-chunk, de CSS en het workerbestand (`maplibre-gl-worker…`) laden met 200, niet 404 (R2);
     - de style-request naar `api.maptiler.com` geeft 401 of 403;
     - binnen enkele seconden staat de melding `load_failed` er en is de lijst terug.
   - Staat er een echte key in `web/.env` (van Lars), doe dan ook de volledige controle uit AC-6 op `localhost`.
   - Faalt de worker: R2.
10. **Documentatie.** Werk `docs/RUNBOOK.md` bij.
    - §4: een rij `| \`PUBLIC_MAPTILER_KEY\` | \`web/.env\`, Cloudflare Pages | web: kaart (optioneel, publiek) | WP-15 |`.
    - §11: nieuw punt **8. Kaart (vanaf WP-15).** Inhoud:
      - een gratis MapTiler Cloud-account; Account, API keys, een key aanmaken;
      - onder "Allowed HTTP origins" `<project>.pages.dev` en `*.<project>.pages.dev` (previews), en voor lokaal `localhost`. Werkt localhost niet met de restrictie, gebruik dan lokaal een tweede key en zet die alleen in `web/.env`;
      - `PUBLIC_MAPTILER_KEY` zetten in Cloudflare Pages (Production en Preview) en in `web/.env`. Dit is een publieke key, geen secret;
      - zonder key werkt de app gewoon en geeft "Kaart" een melding;
      - de kaart laadt alleen na een klik;
      - MapTiler rekent bij MapLibre in API-requests (100.000 per maand gratis), bij overschrijding gepauzeerd tot de volgende maand (geen kosten, de app valt terug op de lijst);
      - het verbruik staat in MapTiler Cloud, Analytics.

      Krijgt WP-12 of WP-16 eerder een punt 8, neem dan het volgende vrije nummer.
11. **Eindcontrole.**
    - `cd web && npm ci && npm run check && npm test && npm run build && npm run verify:build`;
    - de twee AC-2-greps;
    - vanuit de root `bash scripts/check-no-client-openmeteo.sh` (exit 0);
    - de AC-6-grep van WP-13 (`grep -rEn "googletagmanager|google-analytics|plausible|fonts.googleapis|cdn\." web/src web/static` geeft niets);
    - `cd ingest && uv run pytest`;
    - `git status`: geen `web/.env`, `web/build` of `node_modules` gestaged.

**Nodig van Lars (AC-6):**
- een gratis MapTiler-account en een API-key met "Allowed HTTP origins" (RUNBOOK §11.8);
- `PUBLIC_MAPTILER_KEY` in Cloudflare Pages (Production en Preview) en in `web/.env`;
- de controle uit AC-6 op de gedeployde site, plus na een week een blik op het aantal requests;
- een reactie op de voorstellen A3 (stijl `streets-v4`), A5 (keuze niet onthouden) en A6 (wat een marker toont).
