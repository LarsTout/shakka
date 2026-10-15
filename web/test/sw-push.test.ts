// @vitest-environment node
import { beforeEach, describe, expect, it, vi } from 'vitest';
import {
	FALLBACK_BODY,
	FALLBACK_TITLE,
	createPushHandlers,
	parsePushPayload,
	resolveTargetUrl,
	type WindowClientLike
} from '../src/lib/sw/push.js';

const ORIGIN = 'https://app.test';

function setup(clients: readonly WindowClientLike[] = []) {
	const deps = {
		origin: ORIGIN,
		showNotification: vi.fn(async (_t: string, _o: NotificationOptions) => {}),
		matchAll: vi.fn(async () => clients),
		openWindow: vi.fn(async (_u: string) => null)
	};
	return { deps, handlers: createPushHandlers(deps) };
}

async function push(data: { text(): string } | null, clients?: readonly WindowClientLike[]) {
	const s = setup(clients);
	const waitUntil = vi.fn();
	s.handlers.onPush({ data, waitUntil });
	await waitUntil.mock.calls[0]![0];
	return { ...s, waitUntil };
}
const json = (v: unknown) => ({ text: () => JSON.stringify(v) });

async function click(data: unknown, clients: readonly WindowClientLike[]) {
	const s = setup(clients);
	const close = vi.fn();
	const waitUntil = vi.fn();
	s.handlers.onNotificationClick({ notification: { data, close }, waitUntil });
	await waitUntil.mock.calls[0]![0];
	return { ...s, close, waitUntil };
}

beforeEach(() => vi.clearAllMocks());

describe('onPush', () => {
	it('shows an alert payload', async () => {
		const payload = {
			title: 'Brouwersdam: go za 14–17',
			body: 'ZW 18–22 kn\nIk ga: …',
			url: '/spot/brouwersdam',
			tag: 'alert-11111111-2222-4333-8444-555555555555'
		};
		const { deps, waitUntil } = await push(json(payload));
		expect(deps.showNotification).toHaveBeenCalledWith('Brouwersdam: go za 14–17', {
			body: 'ZW 18–22 kn\nIk ga: …',
			icon: '/icons/icon-192.png',
			tag: 'alert-11111111-2222-4333-8444-555555555555',
			data: { url: 'https://app.test/spot/brouwersdam' }
		});
		expect(waitUntil).toHaveBeenCalledTimes(1);
	});

	it('keeps absolute urls, also on another origin', async () => {
		for (const url of [
			'https://app.test/go?spot=brouwersdam&from=2026-10-17T12:00:00Z',
			'https://shakka.pages.dev/go?x=1'
		]) {
			const { deps } = await push(json({ title: 't', body: 'b', url, tag: 'x' }));
			expect(deps.showNotification.mock.calls[0]![1]).toMatchObject({ data: { url } });
		}
	});

	it('shows the test push', async () => {
		const { deps } = await push(
			json({
				title: 'Shakka: testmelding',
				body: 'Meldingen werken op dit apparaat.',
				url: '/',
				tag: 'shakka-test'
			})
		);
		expect(deps.showNotification.mock.calls[0]![1]).toMatchObject({
			tag: 'shakka-test',
			data: { url: 'https://app.test/' }
		});
	});

	it.each([
		['no data', null],
		['invalid json', { text: () => 'not json' }],
		['array', { text: () => '[]' }],
		['null', { text: () => 'null' }],
		[
			'throwing text',
			{
				text: () => {
					throw new Error('x');
				}
			}
		]
	])('falls back for %s', async (_n, data) => {
		const { deps } = await push(data);
		const [title, options] = deps.showNotification.mock.calls[0]!;
		expect(title).toBe(FALLBACK_TITLE);
		expect(options.body).toBe(FALLBACK_BODY);
		expect(options.data).toEqual({ url: 'https://app.test/' });
		expect(options).not.toHaveProperty('tag');
	});

	it('sanitizes a bad payload', async () => {
		const { deps } = await push(json({ title: '  ', body: 5, url: 'javascript:alert(1)' }));
		const [title, options] = deps.showNotification.mock.calls[0]!;
		expect(title).toBe('Shakka');
		expect(options.body).toBe('');
		expect(options.data).toEqual({ url: 'https://app.test/' });
		expect(options).not.toHaveProperty('tag');
	});
});

describe('onNotificationClick (AC-3)', () => {
	const url = 'https://app.test/spot/x';
	it('focuses a window on exactly that url', async () => {
		const focus = vi.fn(async () => {});
		const { deps, close } = await click({ url }, [{ url, focus }]);
		expect(close).toHaveBeenCalledTimes(1);
		expect(focus).toHaveBeenCalledTimes(1);
		expect(deps.openWindow).not.toHaveBeenCalled();
	});
	it('opens a window when another page is open', async () => {
		const focus = vi.fn(async () => {});
		const { deps, close } = await click({ url }, [{ url: 'https://app.test/', focus }]);
		expect(close).toHaveBeenCalledTimes(1);
		expect(deps.openWindow).toHaveBeenCalledWith(url);
		expect(focus).not.toHaveBeenCalled();
	});
	it('opens a window when none is open', async () => {
		const { deps, close } = await click({ url }, []);
		expect(close).toHaveBeenCalledTimes(1);
		expect(deps.openWindow).toHaveBeenCalledWith(url);
	});
	it('opens the start page without data', async () => {
		const { deps } = await click(null, []);
		expect(deps.openWindow).toHaveBeenCalledWith('https://app.test/');
	});
	it('does not reject when matchAll fails', async () => {
		const s = setup();
		s.deps.matchAll.mockRejectedValueOnce(new Error('x'));
		const waitUntil = vi.fn();
		s.handlers.onNotificationClick({ notification: { data: { url }, close: vi.fn() }, waitUntil });
		await expect(waitUntil.mock.calls[0]![0]).resolves.toBeUndefined();
	});
});

describe('parsing', () => {
	it('resolveTargetUrl', () => {
		expect(resolveTargetUrl('/a?b=1#c', ORIGIN)).toBe('https://app.test/a?b=1#c');
		expect(resolveTargetUrl('data:text/html,x', ORIGIN)).toBe('https://app.test/');
		expect(resolveTargetUrl(undefined, ORIGIN)).toBe('https://app.test/');
	});
	it('parsePushPayload', () => {
		expect(parsePushPayload(null)).toEqual({
			title: FALLBACK_TITLE,
			body: FALLBACK_BODY,
			url: '/',
			tag: undefined
		});
		expect(parsePushPayload('{"title":"a","body":"b","url":"/x","tag":"t"}')).toEqual({
			title: 'a',
			body: 'b',
			url: '/x',
			tag: 't'
		});
	});
});
