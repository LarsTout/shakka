import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { clientWithAuthTrap, createFakeRpc } from './helpers/fake-rpc.js';
import { NEW_ID, RSVP_TOM, SESSION_JSON, SLUG, TOKEN } from './fixtures/public-session.js';

const h = vi.hoisted(() => ({ client: null as unknown, fake: null as unknown, trap: null as unknown }));
vi.mock('#lib/supabase.js', async () => {
	const { createFakeRpc, clientWithAuthTrap } = await import('./helpers/fake-rpc.js');
	const fake = createFakeRpc();
	const trap = clientWithAuthTrap({ rpc: fake.rpc });
	h.fake = fake;
	h.trap = trap;
	return { supabase: trap.client, initialUrlHash: '' };
});

import {
	RPC_TIMEOUT_MS,
	createRsvp,
	deleteRsvp,
	getPublicSession,
	updateRsvp
} from '../src/lib/rsvp.js';
import { RPC_ERROR_CODES, RsvpError } from '../src/lib/session-view.js';

const fake = () => h.fake as ReturnType<typeof createFakeRpc>;
const trap = () => h.trap as ReturnType<typeof clientWithAuthTrap>;
const ok = (data: unknown) => ({ data, error: null, status: 200 });
const spies = () => [
	vi.spyOn(console, 'warn').mockImplementation(() => {}),
	vi.spyOn(console, 'error').mockImplementation(() => {}),
	vi.spyOn(console, 'log').mockImplementation(() => {})
];

beforeEach(() => {
	vi.clearAllMocks();
	fake().reset();
});
afterEach(() => vi.restoreAllMocks());

describe('rsvp.ts', () => {
	it('(AC-3) createRsvp sends the trimmed name', async () => {
		fake().respond('rsvp_create', ok({ rsvp_id: NEW_ID, edit_token: TOKEN }));
		const r = await createRsvp(SLUG, { first_name: '  Sanne  ', ride: 'needs_ride', seats_offered: null });
		expect(fake().calls[0]).toMatchObject({
			fn: 'rsvp_create',
			args: { p_slug: SLUG, p_first_name: 'Sanne', p_ride: 'needs_ride', p_seats_offered: null },
			argCount: 2
		});
		expect(r).toEqual({ rsvp_id: NEW_ID, edit_token: TOKEN });
	});

	it('getPublicSession', async () => {
		expect(await getPublicSession('kort')).toBeNull();
		expect(fake().calls).toHaveLength(0);
		fake().respond('get_public_session', ok(SESSION_JSON), ok(null));
		expect(await getPublicSession(SLUG)).toEqual(SESSION_JSON);
		expect(fake().calls[0]).toMatchObject({ fn: 'get_public_session', args: { p_slug: SLUG }, argCount: 2 });
		expect(await getPublicSession(SLUG)).toBeNull();
	});

	it('updateRsvp sends all five keys, also null', async () => {
		fake().respond('rsvp_update', ok(RSVP_TOM));
		const r = await updateRsvp(TOKEN, {
			first_name: ' Eva ',
			ride: 'needs_ride',
			seats_offered: null,
			rides_with: null
		});
		const args = fake().calls[0].args!;
		expect(Object.keys(args).sort()).toEqual(
			['p_edit_token', 'p_first_name', 'p_ride', 'p_seats_offered', 'p_rides_with'].sort()
		);
		expect(args.p_first_name).toBe('Eva');
		expect('p_rides_with' in args).toBe(true);
		expect(args.p_rides_with).toBeNull();
		expect(r).toEqual(RSVP_TOM);
		await expect(
			updateRsvp('abc', { first_name: 'x', ride: 'own', seats_offered: null, rides_with: null })
		).rejects.toMatchObject({ kind: 'invalid_token' });
		expect(fake().calls).toHaveLength(1);
	});

	it('deleteRsvp', async () => {
		fake().respond('rsvp_delete', ok(true), ok(false), ok('yes'));
		expect(await deleteRsvp(TOKEN)).toBe(true);
		expect(fake().calls[0]).toMatchObject({ fn: 'rsvp_delete', args: { p_edit_token: TOKEN } });
		expect(await deleteRsvp(TOKEN)).toBe(false);
		await expect(deleteRsvp(TOKEN)).rejects.toMatchObject({ kind: 'unknown' });
		const n = fake().calls.length;
		expect(await deleteRsvp('abc')).toBe(false);
		expect(fake().calls).toHaveLength(n);
	});

	it('(AC-4) maps the five codes, hides server text', async () => {
		const input = { first_name: 'A', ride: 'own' as const, seats_offered: null };
		for (const code of RPC_ERROR_CODES) {
			fake().respond('rsvp_create', {
				data: null,
				error: { code: 'PT400', message: code, details: null, hint: null },
				status: 400
			});
			await expect(createRsvp(SLUG, input)).rejects.toMatchObject({ kind: code });
		}
		fake().respond('rsvp_create', {
			data: null,
			error: { code: 'XX000', message: 'secret detail' },
			status: 500
		});
		const err = await createRsvp(SLUG, input).catch((e) => e);
		expect(err).toBeInstanceOf(RsvpError);
		expect(err.kind).toBe('unknown');
		expect(String(err)).not.toContain('secret detail');
		expect(err.message).not.toContain('secret detail');
		fake().respond('rsvp_create', { data: null, error: { code: '', message: 'Failed to fetch' }, status: 0 });
		await expect(createRsvp(SLUG, input)).rejects.toMatchObject({ kind: 'network' });
		fake().throwNext('rsvp_create', new Error('secret detail'));
		const thrown = await createRsvp(SLUG, input).catch((e) => e);
		expect(thrown.kind).toBe('network');
		expect(thrown.message).not.toContain('secret detail');
	});

	it('timeout (A6)', async () => {
		const spy = vi.spyOn(AbortSignal, 'timeout');
		fake().respond('get_public_session', ok(null));
		await getPublicSession(SLUG);
		expect(typeof fake().calls[0].signal!.aborted).toBe('boolean');
		expect(spy).toHaveBeenCalledWith(RPC_TIMEOUT_MS);
		expect(RPC_TIMEOUT_MS).toBe(15_000);
		spy.mockRestore();

		const original = Object.getOwnPropertyDescriptor(AbortSignal, 'timeout')!;
		try {
			Object.defineProperty(AbortSignal, 'timeout', { configurable: true, value: undefined });
			fake().respond('get_public_session', ok(null));
			await expect(getPublicSession(SLUG)).resolves.toBeNull();
			expect(fake().calls[1].signal).toBeNull();
		} finally {
			Object.defineProperty(AbortSignal, 'timeout', original);
		}
	});

	it('always POST (no 3rd arg), no auth access, no token in console', async () => {
		const consoleSpies = spies();
		fake().respond('rsvp_delete', ok(true));
		fake().respond('rsvp_update', { data: null, error: { code: 'PT400', message: 'invalid_token' }, status: 400 });
		await deleteRsvp(TOKEN);
		await updateRsvp(TOKEN, { first_name: 'A', ride: 'own', seats_offered: null, rides_with: null }).catch(
			() => {}
		);
		for (const c of fake().calls) expect(c.argCount).toBe(2);
		expect(trap().authAccesses()).toBe(0);
		for (const s of consoleSpies) {
			for (const callArgs of s.mock.calls) expect(JSON.stringify(callArgs)).not.toContain(TOKEN);
		}
	});
});
