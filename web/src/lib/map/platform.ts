import { PUBLIC_MAPTILER_KEY } from '$app/env/public';

/** Type only; erased at compile time (no runtime import). The only non-runtime reference in src/. */
export type MapLibre = typeof import('maplibre-gl');

/** The public MapTiler key ('' when not configured). */
export function getMaptilerKey(): string {
	return PUBLIC_MAPTILER_KEY;
}

/** canvas.getContext('webgl2') !== null; frees the probe context via WEBGL_lose_context; any throw -> false. */
export function supportsWebGL2(doc?: Document): boolean {
	try {
		const gl = (doc ?? document).createElement('canvas').getContext('webgl2');
		if (!gl) return false;
		gl.getExtension('WEBGL_lose_context')?.loseContext();
		return true;
	} catch {
		return false;
	}
}

let pending: Promise<MapLibre> | null = null;

/** Loads the map library, its worker URL and CSS on first call; later calls share the promise; a rejection resets it. */
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
