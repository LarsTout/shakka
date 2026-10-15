import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { createFakeSupabase } from './helpers/fake-supabase.js';

const fake = vi.hoisted(() => ({ current: null as unknown as ReturnType<typeof createFakeSupabase> }));
vi.mock('#lib/supabase.js', async () => {
	const { createFakeSupabase } = await import('./helpers/fake-supabase.js');
	fake.current = createFakeSupabase();
	return { supabase: fake.current.client, initialUrlHash: '' };
});

import { loadMySessionsPage, loadNewSessionPage, loadSharePage } from '../src/lib/session-page-data.js';
import { NOW_SESSIONS, SESSION_ROW, SLUG } from './fixtures/session-data.js';
import { SPOT_UNVERIFIED, SPOT_VERIFIED } from './fixtures/spot-data.js';
import { USER_ID } from './helpers/fake-session.js';

beforeEach(() => {
	vi.clearAllMocks();
	fake.current.reset();
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
