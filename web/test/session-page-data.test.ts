import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { createFakeRpc } from './helpers/fake-rpc.js';
import type { createFakeSupabase } from './helpers/fake-supabase.js';

const fake = vi.hoisted(() => ({
	current: null as unknown as ReturnType<typeof createFakeSupabase>,
	rpc: null as unknown as ReturnType<typeof createFakeRpc>
}));
vi.mock('#lib/supabase.js', async () => {
	const { createFakeSupabase } = await import('./helpers/fake-supabase.js');
	const { createFakeRpc } = await import('./helpers/fake-rpc.js');
	fake.current = createFakeSupabase();
	fake.rpc = createFakeRpc();
	return { supabase: { ...fake.current.client, rpc: fake.rpc.rpc }, initialUrlHash: '' };
});

import {
	loadManagePage,
	loadMySessionsPage,
	loadNewSessionPage,
	loadSharePage
} from '../src/lib/session-page-data.js';
import { SESSION_INFO, SESSION_JSON } from './fixtures/public-session.js';
import { NOW_SESSIONS, SESSION_ROW, SLUG } from './fixtures/session-data.js';
import { SPOT_UNVERIFIED, SPOT_VERIFIED } from './fixtures/spot-data.js';
import { USER_ID } from './helpers/fake-session.js';

beforeEach(() => {
	vi.clearAllMocks();
	fake.current.reset();
	fake.rpc.reset();
});

describe('loadSharePage', () => {
	it('malformed slug: not_found without a query', async () => {
		expect(await loadSharePage('abc')).toEqual({ kind: 'not_found' });
		expect(fake.current.calls).toHaveLength(0);
	});
	it('no row: not_found', async () => {
		fake.current.respond('sessions', { data: null, error: null });
		expect(await loadSharePage(SLUG)).toEqual({ kind: 'not_found' });
	});
	it('ok with the spot name', async () => {
		fake.current.respond('sessions', { data: SESSION_ROW, error: null });
		fake.current.respond('spots', { data: SPOT_UNVERIFIED, error: null });
		expect(await loadSharePage(SLUG)).toEqual({
			kind: 'ok',
			session: SESSION_ROW,
			spotName: 'Teststrand'
		});
	});
	it('unknown spot: spot id as name', async () => {
		fake.current.respond('sessions', { data: SESSION_ROW, error: null });
		fake.current.respond('spots', { data: null, error: null });
		const r = await loadSharePage(SLUG);
		expect(r.kind === 'ok' && r.spotName).toBe('test-strand');
	});
	it('error: warns without details', async () => {
		const warn = vi.spyOn(console, 'warn').mockImplementation(() => {});
		fake.current.respond('sessions', { data: null, error: { code: '42501', message: 'secret' } });
		expect(await loadSharePage(SLUG)).toEqual({ kind: 'error' });
		expect(warn).toHaveBeenCalledWith('share page load failed');
		warn.mockRestore();
	});
});

describe('loadManagePage', () => {
	const ok = (data: unknown) => ({ data, error: null, status: 200 });
	it('ok with the public spot name and rsvps', async () => {
		fake.current.respond('sessions', { data: SESSION_ROW, error: null });
		fake.rpc.respond('get_public_session', ok(SESSION_JSON));
		expect(await loadManagePage(SLUG)).toEqual({
			kind: 'ok',
			session: SESSION_ROW,
			spotName: 'Teststrand',
			rsvps: SESSION_JSON.rsvps,
			rsvpsClosed: false
		});
	});
	it('spot_name null: the spot id', async () => {
		fake.current.respond('sessions', { data: SESSION_ROW, error: null });
		fake.rpc.respond('get_public_session', ok({ ...SESSION_JSON, session: { ...SESSION_INFO, spot_name: null } }));
		const r = await loadManagePage(SLUG);
		expect(r.kind === 'ok' && r.spotName).toBe('test-strand');
	});
	it('no row: not_found and no RPC', async () => {
		fake.current.respond('sessions', { data: null, error: null });
		expect(await loadManagePage(SLUG)).toEqual({ kind: 'not_found' });
		expect(fake.rpc.calls).toHaveLength(0);
	});
	it('malformed slug: not_found without any request', async () => {
		expect(await loadManagePage('abc')).toEqual({ kind: 'not_found' });
		expect(fake.current.calls).toHaveLength(0);
		expect(fake.rpc.calls).toHaveLength(0);
	});
	it('public session null: not_found', async () => {
		fake.current.respond('sessions', { data: SESSION_ROW, error: null });
		fake.rpc.respond('get_public_session', ok(null));
		expect(await loadManagePage(SLUG)).toEqual({ kind: 'not_found' });
	});
	it('error: warns without details', async () => {
		const warn = vi.spyOn(console, 'warn').mockImplementation(() => {});
		fake.current.respond('sessions', { data: null, error: { code: '42501', message: 'secret' } });
		expect(await loadManagePage(SLUG)).toEqual({ kind: 'error' });
		expect(warn).toHaveBeenCalledWith('manage page load failed');
		warn.mockRestore();
	});
});

describe('loadMySessionsPage', () => {
	it('links spot names', async () => {
		fake.current.respond('sessions', { data: [SESSION_ROW], error: null });
		fake.current.respond('spots', { data: [SPOT_VERIFIED, SPOT_UNVERIFIED], error: null });
		const r = await loadMySessionsPage(USER_ID, new Date(NOW_SESSIONS));
		expect(r.kind === 'ok' && r.entries.map((e) => e.spotName)).toEqual(['Teststrand']);
	});
	it('error', async () => {
		const warn = vi.spyOn(console, 'warn').mockImplementation(() => {});
		fake.current.respond('sessions', { data: null, error: { code: 'x' } });
		expect(await loadMySessionsPage(USER_ID, new Date(NOW_SESSIONS))).toEqual({ kind: 'error' });
		expect(warn).toHaveBeenCalledWith('my sessions load failed');
		warn.mockRestore();
	});
});

describe('loadNewSessionPage', () => {
	it('ok and error', async () => {
		fake.current.respond('spots', { data: [SPOT_UNVERIFIED], error: null });
		expect(await loadNewSessionPage()).toEqual({ kind: 'ok', spots: [SPOT_UNVERIFIED] });
		const warn = vi.spyOn(console, 'warn').mockImplementation(() => {});
		fake.current.respond('spots', { data: null, error: { code: 'x' } });
		expect(await loadNewSessionPage()).toEqual({ kind: 'error' });
		warn.mockRestore();
	});
});
