import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { MAPLIBRE_ATTRIBUTION, mapStyleUrl } from '../src/lib/map/config.js';
import { startMap, type MapDeps } from '../src/lib/map/start.js';
import { MAP_SPOTS, MAP_SUMMARIES } from './fixtures/map-data.js';
import { SPOT_VERIFIED } from './fixtures/spot-data.js';
import { createFakeMapLibre, FakeGPUInitializationError } from './helpers/fake-maplibre.js';

let fake: ReturnType<typeof createFakeMapLibre>;
let deps: MapDeps;
let container: HTMLDivElement;
const onReady = vi.fn();
const onFail = vi.fn();
let warn: ReturnType<typeof vi.spyOn>;
const flush = () => new Promise((r) => setTimeout(r, 0));
const start = (spots = MAP_SPOTS, summaries = MAP_SUMMARIES) =>
	startMap(container, spots, summaries, deps, { onReady, onFail });

beforeEach(() => {
	vi.clearAllMocks();
	fake = createFakeMapLibre();
	deps = { key: 'testkey123', webgl: () => true, load: vi.fn(async () => fake.lib) };
	container = document.createElement('div');
	document.body.append(container);
	warn = vi.spyOn(console, 'warn').mockImplementation(() => {});
});
afterEach(() => {
	vi.useRealTimers();
	container.remove();
	warn.mockRestore();
});

describe('startMap preflight and loading', () => {
	it('never calls back synchronously; no key means no_key and no load', async () => {
		deps.key = '';
		start();
		expect(onFail).not.toHaveBeenCalled();
		await flush();
		expect(onFail).toHaveBeenCalledExactlyOnceWith('no_key');
		expect(deps.load).not.toHaveBeenCalled();
	});

	it('no WebGL2 means no_webgl and no load', async () => {
		deps.webgl = () => false;
		start();
		await flush();
		expect(onFail).toHaveBeenCalledExactlyOnceWith('no_webgl');
		expect(deps.load).not.toHaveBeenCalled();
	});

	it('a rejected load gives load_failed and logs without detail', async () => {
		deps.load = vi.fn(async () => {
			throw new Error('secret detail');
		});
		start();
		await flush();
		expect(onFail).toHaveBeenCalledExactlyOnceWith('load_failed');
		expect(warn).toHaveBeenCalledTimes(1);
		expect(JSON.stringify(warn.mock.calls)).not.toContain('secret detail');
	});

	it('constructor failures: GPU error is no_webgl, others load_failed', async () => {
		fake.throwOnConstruct.error = new FakeGPUInitializationError();
		start();
		await flush();
		expect(onFail).toHaveBeenLastCalledWith('no_webgl');
		fake.throwOnConstruct.error = new Error('x');
		start();
		await flush();
		expect(onFail).toHaveBeenLastCalledWith('load_failed');
	});
});

describe('startMap options', () => {
	it('passes the map options (attribution always expanded, no telemetry-ish extras)', async () => {
		start();
		await flush();
		const o = fake.maps[0]!.options;
		expect(o.container).toBe(container);
		expect(o.style).toBe(mapStyleUrl('testkey123'));
		expect(o.attributionControl).toEqual({ compact: false, customAttribution: MAPLIBRE_ATTRIBUTION });
		expect(o.attributionControl).not.toBe(false);
		expect(o).toMatchObject({
			maplibreLogo: false,
			dragRotate: false,
			pitchWithRotate: false,
			touchPitch: false,
			refreshExpiredTiles: false,
			fitBoundsOptions: { padding: 40, maxZoom: 11 }
		});
		expect(o.bounds).toBeDefined();
	});

	it('uses center and zoom without coordinates', async () => {
		start([], {});
		await flush();
		const o = fake.maps[0]!.options;
		expect(o.center).toEqual([5.3, 52.2]);
		expect(o.zoom).toBe(6.5);
		expect(o.bounds).toBeUndefined();
	});

	it('adds a navigation control top-right without compass', async () => {
		start();
		await flush();
		expect(fake.navigationOptions[0]).toEqual({ showCompass: false });
		expect(fake.maps[0]!.controls[0]!.position).toBe('top-right');
	});
});

describe('startMap errors while loading', () => {
	it('an error before style.load is fatal and never logs the event', async () => {
		start();
		await flush();
		const map = fake.maps[0]!;
		map.emit('error', { error: new Error('401 https://api.maptiler.com/x?key=testkey123') });
		expect(onFail).toHaveBeenCalledExactlyOnceWith('load_failed');
		expect(map.remove).toHaveBeenCalledTimes(1);
		expect(JSON.stringify(warn.mock.calls)).not.toContain('testkey123');
		map.emit('style.load');
		map.emit('load');
		expect(onReady).not.toHaveBeenCalled();
		expect(fake.markers).toHaveLength(0);
	});

	it('errors after style.load only warn once; load still gives markers', async () => {
		start();
		await flush();
		const map = fake.maps[0]!;
		map.emit('style.load');
		map.emit('error', {});
		map.emit('error', {});
		expect(onFail).not.toHaveBeenCalled();
		expect(map.remove).not.toHaveBeenCalled();
		expect(warn).toHaveBeenCalledExactlyOnceWith('map resource error');
		map.emit('load');
		expect(onReady).toHaveBeenCalledTimes(1);
		expect(fake.markers).toHaveLength(3);
	});
});

describe('startMap markers', () => {
	it('load without style.load renders markers in the container', async () => {
		start();
		await flush();
		fake.maps[0]!.emit('load');
		expect(onReady).toHaveBeenCalledTimes(1);
		expect(fake.markers.map((m) => m.options.anchor)).toEqual(['bottom', 'bottom', 'bottom']);
		expect(fake.markers.map((m) => m.lngLat)).toEqual([
			[4.57, 52.47],
			[4.57, 52.47],
			[4.2, 52.1]
		]);
		for (const m of fake.markers) expect(container.contains(m.options.element)).toBe(true);
		fake.maps[0]!.emit('error', {});
		fake.maps[0]!.emit('error', {});
		expect(onFail).not.toHaveBeenCalled();
		expect(warn).toHaveBeenCalledTimes(1);
	});

	it('update replaces markers; update before load uses the new data', async () => {
		const c = start();
		await flush();
		c.update(MAP_SPOTS, {}); // before load
		fake.maps[0]!.emit('load');
		expect(fake.markers).toHaveLength(3);
		c.update([SPOT_VERIFIED], {});
		expect(fake.markers.slice(0, 3).every((m) => m.removed)).toBe(true);
		expect(fake.markers).toHaveLength(4);
		expect(fake.markers[3]!.removed).toBe(false);
	});
});

describe('startMap timer', () => {
	beforeEach(() => vi.useFakeTimers());

	it('no load within 30 s is load_failed', async () => {
		start();
		await vi.advanceTimersByTimeAsync(0);
		await vi.advanceTimersByTimeAsync(30_000);
		expect(onFail).toHaveBeenCalledExactlyOnceWith('load_failed');
	});

	it('style.load plus an error without load still times out', async () => {
		start();
		await vi.advanceTimersByTimeAsync(0);
		fake.maps[0]!.emit('style.load');
		fake.maps[0]!.emit('error', {});
		await vi.advanceTimersByTimeAsync(30_000);
		expect(onFail).toHaveBeenCalledExactlyOnceWith('load_failed');
	});

	it('load in time cancels the timer', async () => {
		start();
		await vi.advanceTimersByTimeAsync(0);
		fake.maps[0]!.emit('load');
		await vi.advanceTimersByTimeAsync(60_000);
		expect(onFail).not.toHaveBeenCalled();
	});
});

describe('startMap destroy', () => {
	it('destroy before the library resolves creates no map and no callbacks', async () => {
		let resolve!: (lib: typeof fake.lib) => void;
		deps.load = vi.fn(() => new Promise<typeof fake.lib>((r) => (resolve = r)));
		const c = start();
		await flush();
		c.destroy();
		resolve(fake.lib);
		await flush();
		expect(fake.maps).toHaveLength(0);
		expect(onReady).not.toHaveBeenCalled();
		expect(onFail).not.toHaveBeenCalled();
	});

	it('destroy after load removes markers and the map once', async () => {
		const c = start();
		await flush();
		fake.maps[0]!.emit('load');
		c.destroy();
		expect(fake.markers.every((m) => m.removed)).toBe(true);
		expect(fake.maps[0]!.remove).toHaveBeenCalledTimes(1);
		c.destroy();
		expect(fake.maps[0]!.remove).toHaveBeenCalledTimes(1);
	});
});
