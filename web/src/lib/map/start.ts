import type { Spot, SpotSummary } from '../types.js';
import {
	FIT_MAX_ZOOM,
	FIT_PADDING_PX,
	MAP_LOAD_TIMEOUT_MS,
	MAPLIBRE_ATTRIBUTION,
	mapStyleUrl,
	preflight,
	type MapFailure
} from './config.js';
import { createMarkerElement, initialView, markerModels } from './markers.js';
import type { MapLibre } from './platform.js';

export interface MapDeps {
	key: string;
	webgl: () => boolean;
	load: () => Promise<MapLibre>;
}
export interface MapCallbacks {
	onReady(): void;
	onFail(reason: MapFailure): void;
}
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
): MapController {
	let destroyed = false;
	let failed = false;
	let loaded = false;
	let styleLoaded = false;
	let warned = false;
	let lib: MapLibre | null = null;
	let map: InstanceType<MapLibre['Map']> | null = null;
	let markers: Array<InstanceType<MapLibre['Marker']>> = [];
	let current = { spots, summaries };
	let timer: ReturnType<typeof setTimeout> | null = null;

	function clearTimer() {
		if (timer !== null) clearTimeout(timer);
		timer = null;
	}
	function removeMarkers() {
		for (const marker of markers) marker.remove();
		markers = [];
	}
	function removeMap() {
		removeMarkers();
		try {
			map?.remove();
		} catch {
			// ignore: the map may be half-initialised
		}
		map = null;
	}
	function fail(reason: MapFailure) {
		if (destroyed || failed) return;
		failed = true;
		clearTimer();
		removeMap();
		callbacks.onFail(reason);
	}
	// Never log the event: the style URL contains the key.
	function warnOnce() {
		if (warned) return;
		warned = true;
		console.warn('map resource error');
	}
	function renderMarkers() {
		if (!lib || !map) return;
		removeMarkers();
		for (const m of markerModels(current.spots, current.summaries).markers) {
			markers.push(
				new lib.Marker({ element: createMarkerElement(m, container.ownerDocument), anchor: 'bottom' })
					.setLngLat([m.lon, m.lat])
					.addTo(map)
			);
		}
	}

	void (async () => {
		await Promise.resolve();
		if (destroyed) return;
		const pre = preflight(deps.key, deps.webgl);
		if (pre) {
			fail(pre);
			return;
		}
		try {
			lib = await deps.load();
		} catch {
			console.warn('map library load failed');
			fail('load_failed');
			return;
		}
		if (destroyed || failed) return;
		const view = initialView(markerModels(current.spots, current.summaries).markers);
		try {
			map = new lib.Map({
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
			});
		} catch (e) {
			fail(e instanceof lib.GPUInitializationError ? 'no_webgl' : 'load_failed');
			return;
		}
		map.addControl(new lib.NavigationControl({ showCompass: false }), 'top-right');
		map.on('style.load', () => {
			styleLoaded = true;
		});
		map.on('error', () => {
			if (destroyed || failed) return;
			if (!styleLoaded) fail('load_failed'); // style 401/403: key, origin or quota
			else warnOnce();
		});
		map.on('load', () => {
			if (destroyed || failed) return;
			styleLoaded = true;
			loaded = true;
			clearTimer();
			renderMarkers();
			callbacks.onReady();
		});
		timer = setTimeout(() => {
			if (!loaded) fail('load_failed');
		}, MAP_LOAD_TIMEOUT_MS);
	})();

	return {
		update(s, su) {
			current = { spots: s, summaries: su };
			if (loaded && !failed && !destroyed) renderMarkers();
		},
		destroy() {
			if (destroyed) return;
			destroyed = true;
			clearTimer();
			removeMap();
		}
	};
}
