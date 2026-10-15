// @vitest-environment node
import { describe, expect, it, vi } from 'vitest';
import {
	MAP_EXTERNAL_ORIGINS,
	MAP_FAILURE_MESSAGE_NL,
	MAPLIBRE_ATTRIBUTION,
	mapStyleUrl,
	preflight
} from '../src/lib/map/config.js';

describe('map config', () => {
	it('builds the style URL', () => {
		expect(mapStyleUrl('abcDEF123456')).toBe(
			'https://api.maptiler.com/maps/streets-v4/style.json?key=abcDEF123456'
		);
	});

	it('preflight: no key means no_key and the WebGL probe is not called', () => {
		const webgl = vi.fn(() => true);
		expect(preflight('', webgl)).toBe('no_key');
		expect(webgl).not.toHaveBeenCalled();
	});

	it('preflight: no WebGL2 means no_webgl, otherwise null', () => {
		expect(preflight('k', () => false)).toBe('no_webgl');
		expect(preflight('k', () => true)).toBeNull();
	});

	it('every failure message is Dutch and points at the list', () => {
		for (const message of Object.values(MAP_FAILURE_MESSAGE_NL)) {
			expect(message).not.toBe('');
			expect(message.toLowerCase()).toContain('lijst');
		}
	});

	it('exposes the external origins and the MapLibre attribution', () => {
		expect([...MAP_EXTERNAL_ORIGINS]).toEqual(['https://api.maptiler.com']);
		expect(MAPLIBRE_ATTRIBUTION).toContain('https://maplibre.org/');
	});
});
