import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { createFakeSupabase } from './helpers/fake-supabase.js';
import {
	IPHONE_UA,
	OTHER_VAPID_PUBLIC_KEY,
	TEST_VAPID_PUBLIC_KEY,
	fakeSubscription,
	installPushEnv,
	publicEnv
} from './helpers/fake-push.js';

const fake = vi.hoisted(() => ({ current: null as unknown as ReturnType<typeof createFakeSupabase> }));
vi.mock('#lib/supabase.js', async () => {
	const { createFakeSupabase } = await import('./helpers/fake-supabase.js');
	fake.current = createFakeSupabase();
	return { supabase: fake.current.client, initialUrlHash: '' };
});
vi.mock('$app/env/public', async () => (await import('./helpers/fake-push.js')).publicEnv);

import { base64UrlToBytes } from '../src/lib/env-schema.js';
import {
	PUSH_MESSAGES,
	SIGN_OUT_PUSH_TIMEOUT_MS,
	SW_READY_TIMEOUT_MS,
	disablePush,
	enablePush,
	getPushStatus,
	isPushSupported,
	releasePushForSignOut,
	subscriptionKeys,
	vapidKeyBytes,
	withTimeout
} from '../src/lib/push.js';

let env: ReturnType<typeof installPushEnv> | undefined;
const T = 'push_subscriptions';
const install = (o: Parameters<typeof installPushEnv>[0] = {}) => (env = installPushEnv(o));
const warn = vi.spyOn(console, 'warn').mockImplementation(() => {});

beforeEach(() => {
	vi.clearAllMocks();
	fake.current.reset();
	publicEnv.PUBLIC_VAPID_PUBLIC_KEY = TEST_VAPID_PUBLIC_KEY;
});
afterEach(() => {
	env?.uninstall();
	env = undefined;
	vi.useRealTimers();
});

const row = (id: string, endpoint: string) => ({ id, endpoint, created_at: 'x' });

describe('helpers', () => {
	it('isPushSupported', () => {
		expect(isPushSupported()).toBe(false);
		install();
		expect(isPushSupported()).toBe(true);
	});
	it('vapidKeyBytes', () => {
		expect(vapidKeyBytes(undefined)).toBeNull();
		expect(vapidKeyBytes('')).toBeNull();
		const b = vapidKeyBytes(TEST_VAPID_PUBLIC_KEY)!;
		expect(b).toHaveLength(65);
		expect(b[0]).toBe(4);
	});
	it('subscriptionKeys', () => {
		expect(subscriptionKeys(fakeSubscription() as unknown as PushSubscription)).toEqual({
			endpoint: 'https://push.example.test/sub-1',
			p256dh: 'p256dh-test',
			auth: 'auth-test'
		});
		const noAuth = {
			endpoint: 'https://x.test/a',
			toJSON: () => ({ endpoint: 'https://x.test/a', keys: { p256dh: 'p' } })
		};
		expect(subscriptionKeys(noAuth as unknown as PushSubscription)).toBeNull();
		const http = {
			endpoint: 'http://x.test/a',
			toJSON: () => ({ endpoint: 'http://x.test/a', keys: { p256dh: 'p', auth: 'a' } })
		};
		expect(subscriptionKeys(http as unknown as PushSubscription)).toBeNull();
	});
	it('withTimeout', async () => {
		await expect(withTimeout(Promise.resolve(1), 100, 2)).resolves.toBe(1);
		vi.useFakeTimers();
		const p = withTimeout(new Promise<number>(() => {}), 100, 2);
		await vi.advanceTimersByTimeAsync(100);
		await expect(p).resolves.toBe(2);
	});
});

describe('getPushStatus (AC-2: no permission prompt on load)', () => {
	const untouched = () => {
		expect(env!.requestPermission).not.toHaveBeenCalled();
		expect(env!.subscribe).not.toHaveBeenCalled();
	};
	it('needs_install on iPhone in the browser', async () => {
		install({ userAgent: IPHONE_UA });
		expect(await getPushStatus()).toBe('needs_install');
		untouched();
	});
	it('unsupported without support', async () => {
		install({ supported: false });
		expect(await getPushStatus()).toBe('unsupported');
	});
	it('unavailable without a key', async () => {
		install();
		publicEnv.PUBLIC_VAPID_PUBLIC_KEY = '';
		expect(await getPushStatus()).toBe('unavailable');
		untouched();
	});
	it('denied', async () => {
		install({ permission: 'denied' });
		expect(await getPushStatus()).toBe('denied');
		untouched();
	});
	it('off without permission, no DB call', async () => {
		install({ permission: 'default' });
		expect(await getPushStatus()).toBe('off');
		expect(fake.current.calls).toHaveLength(0);
		untouched();
	});
	it('off when granted without a subscription', async () => {
		install({ permission: 'granted' });
		expect(await getPushStatus()).toBe('off');
		expect(fake.current.calls).toHaveLength(0);
		untouched();
	});
	it('on with a matching own row, off without', async () => {
		install({ permission: 'granted', subscription: fakeSubscription() });
		fake.current.respond(T, { data: [row('1', 'https://push.example.test/sub-1')], error: null });
		expect(await getPushStatus()).toBe('on');
		fake.current.respond(T, { data: [row('2', 'https://push.example.test/other')], error: null });
		expect(await getPushStatus()).toBe('off');
		untouched();
	});
	it('off with a subscription for another key, no DB call', async () => {
		install({
			permission: 'granted',
			subscription: fakeSubscription('https://push.example.test/sub-1', OTHER_VAPID_PUBLIC_KEY)
		});
		expect(await getPushStatus()).toBe('off');
		expect(fake.current.calls).toHaveLength(0);
	});
	it('error on a select failure', async () => {
		install({ permission: 'granted', subscription: fakeSubscription() });
		fake.current.respond(T, { data: null, error: { code: '42501' } });
		expect(await getPushStatus()).toBe('error');
		untouched();
	});
});

describe('enablePush', () => {
	it('requests permission, subscribes, then inserts', async () => {
		install();
		env!.subscribe.mockImplementationOnce(async () => {
			expect(fake.current.calls).toHaveLength(0); // subscribe before insert
			return fakeSubscription() as never;
		});
		const r = await enablePush();
		expect(r).toEqual({ ok: true });
		expect(env!.requestPermission).toHaveBeenCalledTimes(1);
		expect(env!.subscribe).toHaveBeenCalledTimes(1);
		const opts = env!.subscribe.mock.calls[0]![0] as {
			userVisibleOnly: boolean;
			applicationServerKey: Uint8Array;
		};
		expect(opts.userVisibleOnly).toBe(true);
		expect(opts.applicationServerKey).toBeInstanceOf(Uint8Array);
		expect([...opts.applicationServerKey]).toEqual([...base64UrlToBytes(TEST_VAPID_PUBLIC_KEY)]);
		expect(fake.current.calls[0]).toEqual({
			table: T,
			ops: [
				[
					'insert',
					{ endpoint: 'https://push.example.test/sub-1', p256dh: 'p256dh-test', auth: 'auth-test' }
				]
			]
		});
	});
	it('handles denied, dismissed and a rejecting prompt', async () => {
		install({ requestResult: 'denied' });
		expect(await enablePush()).toEqual({ ok: false, error: PUSH_MESSAGES.denied });
		expect(env!.subscribe).not.toHaveBeenCalled();
		expect(fake.current.calls).toHaveLength(0);
		env!.uninstall();
		install({ requestResult: 'default' });
		expect(await enablePush()).toEqual({ ok: false, error: PUSH_MESSAGES.dismissed });
		env!.requestPermission.mockRejectedValueOnce(new Error('x'));
		expect(await enablePush()).toEqual({ ok: false, error: PUSH_MESSAGES.dismissed });
	});
	it('reuses a subscription with the same key', async () => {
		install({ permission: 'granted', subscription: fakeSubscription() });
		expect(await enablePush()).toEqual({ ok: true });
		expect(env!.subscribe).not.toHaveBeenCalled();
		expect(fake.current.calls.filter((c) => c.ops[0]![0] === 'insert')).toHaveLength(1);
	});
	it('replaces a subscription with another key', async () => {
		const old = fakeSubscription('https://push.example.test/old', OTHER_VAPID_PUBLIC_KEY);
		install({ permission: 'granted', subscription: old });
		expect(await enablePush()).toEqual({ ok: true });
		expect(old.unsubscribe).toHaveBeenCalledTimes(1);
		expect(env!.subscribe).toHaveBeenCalledTimes(1);
	});
	it('23505 with an own row counts as success', async () => {
		install();
		fake.current.respond(T, { data: null, error: { code: '23505' } });
		fake.current.respond(T, { data: [row('1', 'https://push.example.test/sub-1')], error: null });
		expect(await enablePush()).toEqual({ ok: true });
	});
	it('23505 without an own row switches to a new subscription', async () => {
		const s1 = fakeSubscription('https://push.example.test/sub-1');
		const s2 = fakeSubscription('https://push.example.test/sub-2');
		install({ newSubscriptions: [s1, s2] });
		fake.current.respond(T, { data: null, error: { code: '23505' } });
		fake.current.respond(T, { data: [], error: null });
		expect(await enablePush()).toEqual({ ok: true });
		expect(s1.unsubscribe).toHaveBeenCalledTimes(1);
		expect(env!.subscribe).toHaveBeenCalledTimes(2);
		const inserts = fake.current.calls.filter((c) => c.ops[0]![0] === 'insert');
		expect((inserts[1]!.ops[0]![1] as { endpoint: string }).endpoint).toBe(
			'https://push.example.test/sub-2'
		);
	});
	it('two 23505 results give otherAccount', async () => {
		install({
			newSubscriptions: [
				fakeSubscription('https://push.example.test/sub-1'),
				fakeSubscription('https://push.example.test/sub-2')
			]
		});
		fake.current.respond(
			T,
			{ data: null, error: { code: '23505' } },
			{ data: [], error: null },
			{ data: null, error: { code: '23505' } },
			{ data: [], error: null }
		);
		expect(await enablePush()).toEqual({ ok: false, error: PUSH_MESSAGES.otherAccount });
	});
	it('a failing insert gives saveFailed and keeps the subscription', async () => {
		const s = fakeSubscription();
		install({ newSubscriptions: [s] });
		fake.current.respond(T, { data: null, error: { code: '08006' } });
		expect(await enablePush()).toEqual({ ok: false, error: PUSH_MESSAGES.saveFailed });
		expect(s.unsubscribe).not.toHaveBeenCalled();
	});
	it('a failing subscribe or missing keys gives subscribeFailed without DB calls', async () => {
		install();
		env!.subscribe.mockRejectedValueOnce(new Error('AbortError'));
		expect(await enablePush()).toEqual({ ok: false, error: PUSH_MESSAGES.subscribeFailed });
		expect(fake.current.calls).toHaveLength(0);
		const broken = fakeSubscription();
		broken.toJSON = () => ({ endpoint: broken.endpoint });
		env!.uninstall();
		install({ newSubscriptions: [broken] });
		expect(await enablePush()).toEqual({ ok: false, error: PUSH_MESSAGES.subscribeFailed });
		expect(fake.current.calls).toHaveLength(0);
	});
	it('gives noServiceWorker after the timeout', async () => {
		vi.useFakeTimers();
		install({ ready: 'never' });
		const p = enablePush();
		await vi.advanceTimersByTimeAsync(SW_READY_TIMEOUT_MS);
		expect(await p).toEqual({ ok: false, error: PUSH_MESSAGES.noServiceWorker });
	});
	it.each(['waiting', 'installing'] as const)('refuses while an update is %s', async (state) => {
		install({ updateState: state });
		expect(await enablePush()).toEqual({ ok: false, error: PUSH_MESSAGES.updatePending });
		expect(env!.requestPermission).toHaveBeenCalledTimes(1);
		expect(env!.getSubscription).not.toHaveBeenCalled();
		expect(env!.subscribe).not.toHaveBeenCalled();
		expect(fake.current.calls).toHaveLength(0);
	});
	it('prunes the oldest rows beyond 10, never the current one', async () => {
		install();
		const current = row('cur', 'https://push.example.test/sub-1');
		const older = Array.from({ length: 10 }, (_, i) => row(`o${i}`, `https://push.example.test/o${i}`));
		fake.current.respond(T, { data: null, error: null }); // insert
		fake.current.respond(T, { data: [current, ...older], error: null }); // list
		expect(await enablePush()).toEqual({ ok: true });
		const deletes = fake.current.calls.filter((c) => c.ops[0]![0] === 'delete');
		expect(deletes).toHaveLength(1);
		expect(deletes[0]!.ops).toEqual([['delete'], ['eq', 'id', 'o9']]);
	});
	it('a failing prune still succeeds', async () => {
		install();
		fake.current.respond(T, { data: null, error: null });
		fake.current.respond(T, { data: null, error: { code: '42501' } });
		expect(await enablePush()).toEqual({ ok: true });
	});
	it('refuses early on iPhone, without support and without a key', async () => {
		install({ userAgent: IPHONE_UA });
		expect(await enablePush()).toEqual({ ok: false, error: PUSH_MESSAGES.installFirst });
		expect(env!.requestPermission).not.toHaveBeenCalled();
		env!.uninstall();
		install({ supported: false });
		expect(await enablePush()).toEqual({ ok: false, error: PUSH_MESSAGES.unsupported });
		env!.uninstall();
		install();
		publicEnv.PUBLIC_VAPID_PUBLIC_KEY = '';
		expect(await enablePush()).toEqual({ ok: false, error: PUSH_MESSAGES.unavailable });
		expect(env!.requestPermission).not.toHaveBeenCalled();
	});
});

describe('disablePush', () => {
	it('deletes the row before unsubscribing', async () => {
		const s = fakeSubscription();
		install({ permission: 'granted', subscription: s });
		fake.current.respond(T, { data: [row('id-1', s.endpoint)], error: null });
		const original = s.unsubscribe.getMockImplementation()!;
		s.unsubscribe.mockImplementation(async () => {
			expect(fake.current.calls.some((c) => c.ops[0]![0] === 'delete')).toBe(true);
			return original();
		});
		await disablePush();
		const del = fake.current.calls.find((c) => c.ops[0]![0] === 'delete')!;
		expect(del.ops).toEqual([['delete'], ['eq', 'id', 'id-1']]);
		expect(s.unsubscribe).toHaveBeenCalledTimes(1);
	});
	it('unsubscribes without an own row', async () => {
		const s = fakeSubscription();
		install({ permission: 'granted', subscription: s });
		await disablePush();
		expect(fake.current.calls.some((c) => c.ops[0]![0] === 'delete')).toBe(false);
		expect(s.unsubscribe).toHaveBeenCalledTimes(1);
	});
	it('unsubscribes after a select failure without throwing', async () => {
		const s = fakeSubscription();
		install({ permission: 'granted', subscription: s });
		fake.current.respond(T, { data: null, error: { code: '42501' } });
		await expect(disablePush()).resolves.toBeUndefined();
		expect(s.unsubscribe).toHaveBeenCalledTimes(1);
	});
	it('does nothing without subscription or support', async () => {
		install({ permission: 'granted' });
		await disablePush();
		env!.uninstall();
		install({ supported: false });
		await disablePush();
		expect(fake.current.calls).toHaveLength(0);
	});
});

describe('releasePushForSignOut', () => {
	it('resolves after the timeout when the registration hangs', async () => {
		vi.useFakeTimers();
		install({ permission: 'granted' });
		(navigator.serviceWorker as unknown as { getRegistration: () => Promise<never> }).getRegistration =
			() => new Promise(() => {});
		const p = releasePushForSignOut();
		await vi.advanceTimersByTimeAsync(SIGN_OUT_PUSH_TIMEOUT_MS);
		await expect(p).resolves.toBeUndefined();
	});
});

describe('logging', () => {
	it('never logs endpoints or keys', async () => {
		install({ newSubscriptions: [fakeSubscription()] });
		fake.current.respond(T, { data: null, error: { code: '08006', message: 'push.example.test' } });
		await enablePush();
		for (const call of warn.mock.calls) {
			for (const a of call) {
				expect(String(a)).not.toMatch(/push\.example\.test|p256dh-test|auth-test/);
			}
		}
		expect(warn).toHaveBeenCalled();
	});
});
