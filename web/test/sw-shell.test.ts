// @vitest-environment node
import { beforeEach, describe, expect, it, vi } from 'vitest';
import {
	CACHE_PREFIX,
	classifyRequest,
	createShellHandlers,
	precacheList,
	type FetchLikeEvent
} from '#lib/sw/shell.js';
import { FakeCacheStorage } from './helpers/fake-cache.js';

const ORIGIN = 'https://app.test';
const PRECACHE = ['/_app/immutable/entry/start.js', '/manifest.webmanifest', '/'];
const CACHE_NAME = `${CACHE_PREFIX}v2`;

function req(path: string, init: { method?: string; mode?: RequestMode } = {}): Request {
	const request = new Request(new URL(path, ORIGIN), { method: init.method ?? 'GET' });
	// Request constructor refuses mode 'navigate'; override it.
	Object.defineProperty(request, 'mode', { value: init.mode ?? 'cors' });
	return request;
}

function fetchEvent(request: Request) {
	const respondWith = vi.fn<(r: Promise<Response>) => void>();
	const event: FetchLikeEvent = { request, respondWith };
	return { event, respondWith };
}

let storage: FakeCacheStorage;
let netFetch: ReturnType<typeof vi.fn<(r: Request) => Promise<Response>>>;

function setup() {
	return createShellHandlers({
		cacheName: CACHE_NAME,
		precache: PRECACHE,
		shellPath: '/',
		origin: ORIGIN,
		caches: storage,
		fetch: netFetch
	});
}

async function install() {
	let p: Promise<unknown> = Promise.resolve();
	const handlers = setup();
	handlers.onInstall({ waitUntil: (x) => (p = x) });
	await p;
	return handlers;
}

beforeEach(() => {
	storage = new FakeCacheStorage();
	netFetch = vi.fn<(r: Request) => Promise<Response>>();
});

describe('precacheList', () => {
	it('dedupes and appends the shell last', () => {
		expect(precacheList(['/a', '/a', '/b'], '/')).toEqual(['/a', '/b', '/']);
		expect(precacheList(['/', '/a'], '/')).toEqual(['/', '/a']);
	});
	it('leaves out host configuration files (WP-23, A6)', () => {
		expect(precacheList(['/a.js', '/_headers', '/_redirects', '/a.js'], '/')).toEqual(['/a.js', '/']);
	});
});

describe('classifyRequest', () => {
	const set = new Set(PRECACHE);
	it('classifies requests', () => {
		expect(classifyRequest(req('/x', { method: 'POST' }), ORIGIN, set)).toBe('passthrough');
		expect(
			classifyRequest(
				{ url: 'https://abc.supabase.co/rest/v1/spots', method: 'GET', mode: 'cors' },
				ORIGIN,
				set
			)
		).toBe('passthrough');
		expect(classifyRequest(req('/login', { mode: 'navigate' }), ORIGIN, set)).toBe('navigate');
		expect(classifyRequest(req('/', { mode: 'navigate' }), ORIGIN, set)).toBe('navigate');
		expect(classifyRequest(req('/_app/immutable/entry/start.js'), ORIGIN, set)).toBe('precached');
		expect(classifyRequest(req('/_app/version.json'), ORIGIN, set)).toBe('passthrough');
	});
});

describe('handlers', () => {
	it('install fills the cache with every precache path', async () => {
		await install();
		const cache = storage.caches.get(CACHE_NAME)!;
		expect(await cache.keys()).toEqual(PRECACHE);
	});

	it('activate removes old shell caches only', async () => {
		await storage.open(`${CACHE_PREFIX}v1`);
		await storage.open(CACHE_NAME);
		await storage.open('other-cache');
		let p: Promise<unknown> = Promise.resolve();
		setup().onActivate({ waitUntil: (x) => (p = x) });
		await p;
		expect(await storage.keys()).toEqual([CACHE_NAME, 'other-cache']);
	});

	it('does not intercept POST or Supabase requests', async () => {
		const h = await install();
		for (const request of [
			req('/x', { method: 'POST' }),
			new Request('https://abc.supabase.co/rest/v1/spots')
		]) {
			const { event, respondWith } = fetchEvent(request);
			h.onFetch(event);
			expect(respondWith).not.toHaveBeenCalled();
		}
	});

	it('serves precached assets from the cache without the network', async () => {
		const h = await install();
		const { event, respondWith } = fetchEvent(req('/_app/immutable/entry/start.js'));
		h.onFetch(event);
		const res = await respondWith.mock.calls[0][0];
		expect(await res.text()).toBe('cached:/_app/immutable/entry/start.js');
		expect(netFetch).not.toHaveBeenCalled();
	});

	it('navigates network-first', async () => {
		const h = await install();
		netFetch.mockResolvedValue(new Response('net'));
		const { event, respondWith } = fetchEvent(req('/over', { mode: 'navigate' }));
		h.onFetch(event);
		expect(await (await respondWith.mock.calls[0][0]).text()).toBe('net');
	});

	it('returns an HTTP error response unchanged', async () => {
		const h = await install();
		netFetch.mockResolvedValue(new Response('err', { status: 500 }));
		const { event, respondWith } = fetchEvent(req('/over', { mode: 'navigate' }));
		h.onFetch(event);
		expect((await respondWith.mock.calls[0][0]).status).toBe(500);
	});

	it('falls back to the cached shell when offline', async () => {
		const h = await install();
		netFetch.mockRejectedValue(new TypeError('offline'));
		const { event, respondWith } = fetchEvent(req('/over', { mode: 'navigate' }));
		h.onFetch(event);
		expect(await (await respondWith.mock.calls[0][0]).text()).toBe('cached:/');
	});

	it('rethrows the network error when there is no shell', async () => {
		const h = setup();
		netFetch.mockRejectedValue(new TypeError('offline'));
		const { event, respondWith } = fetchEvent(req('/over', { mode: 'navigate' }));
		h.onFetch(event);
		await expect(respondWith.mock.calls[0][0]).rejects.toThrow('offline');
	});

	it('never writes to the cache outside install', async () => {
		expect(storage.totalPutCalls).toBe(0);
		await install();
		expect(storage.totalPutCalls).toBe(0);
	});
});
