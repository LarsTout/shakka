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
export const NL_CENTER: [number, number] = [5.3, 52.2]; // [lon, lat], view without any spot coordinates
export const NL_ZOOM = 6.5;
export const BOUNDS_MARGIN_DEG = 0.05;
export const FIT_PADDING_PX = 40;
export const FIT_MAX_ZOOM = 11;

export const MAP_FAILURE_MESSAGE_NL: Record<MapFailure, string> = {
	no_key: 'De kaart is niet beschikbaar in deze versie van de app. De lijst werkt gewoon.',
	no_webgl: 'Je browser kan de kaart niet tonen (WebGL2 ontbreekt). Gebruik de lijst.',
	load_failed: 'De kaart kon niet worden geladen. Probeer het later opnieuw of gebruik de lijst.'
};

export function mapStyleUrl(key: string): string {
	return `${MAPTILER_API_ORIGIN}/maps/${MAPTILER_STYLE_ID}/style.json?key=${encodeURIComponent(key)}`;
}

/** key === '' -> 'no_key' (webgl() not called); !webgl() -> 'no_webgl'; else null. */
export function preflight(key: string, webgl: () => boolean): MapFailure | null {
	if (key === '') return 'no_key';
	if (!webgl()) return 'no_webgl';
	return null;
}
