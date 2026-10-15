import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { createFakeSupabase } from './helpers/fake-supabase.js';

const fake = vi.hoisted(() => ({ current: null as unknown as ReturnType<typeof createFakeSupabase> }));
vi.mock('#lib/supabase.js', async () => {
	const { createFakeSupabase } = await import('./helpers/fake-supabase.js');
	fake.current = createFakeSupabase();
	return { supabase: fake.current.client, initialUrlHash: '' };
});

import { DataError } from '../src/lib/data.js';
import type { NewSession } from '../src/lib/session-model.js';
import {
	SESSION_ERROR_MESSAGES as MSG,
	cancelSession,
	createSession,
	getMySession,
	listMySessions,
	sessionErrorMessage,
	updateSession
} from '../src/lib/sessions.js';
import { NOW_SESSIONS, SESSION_ID, SESSION_ROW, SLUG } from './fixtures/session-data.js';
import { USER_ID } from './helpers/fake-session.js';
import { writeCalls } from './helpers/fake-supabase.js';

beforeEach(() => {
	vi.clearAllMocks();
	fake.current.reset();
});

const NEW: NewSession = {
	spot_id: 'test-strand',
	organizer_name: 'Lars',
	starts_at: '2026-07-18T12:00:00.000Z',
	ends_at: '2026-07-18T16:00:00.000Z',
	note: null,
	seats_free: null,
	departure_point: null,
	tikkie_url: null
};

describe('createSession', () => {
	it('retries once on a slug collision with the same payload', async () => {
		fake.current.respond(
			'sessions',
			{ data: null, error: { code: '23505' } },
			{ data: { slug: SLUG }, error: null }
		);
		expect(await createSession(NEW)).toEqual({ slug: SLUG });
		const inserts = writeCalls(fake.current.calls);
		expect(inserts).toHaveLength(2);
		expect(inserts[0]!.ops[0]).toEqual(inserts[1]!.ops[0]);
	});
	it('gives up after a second collision', async () => {
		fake.current.respond(
			'sessions',
			{ data: null, error: { code: '23505' } },
			{ data: null, error: { code: '23505' } }
		);
		await expect(createSession(NEW)).rejects.toMatchObject({ code: '23505' });
		expect(writeCalls(fake.current.calls)).toHaveLength(2);
	});
	it('no retry on rate_limited', async () => {
		fake.current.respond('sessions', { data: null, error: { code: 'PT400', message: 'rate_limited' } });
		await expect(createSession(NEW)).rejects.toMatchObject({ code: 'rate_limited' });
		expect(writeCalls(fake.current.calls)).toHaveLength(1);
	});
});

describe('cancelSession (AC-5)', () => {
	it('sets cancelled_at only', async () => {
		fake.current.respond('sessions', { data: [{ id: SESSION_ID }], error: null });
		await cancelSession(SESSION_ID, new Date(NOW_SESSIONS));
		expect(fake.current.calls).toEqual([
			{
				table: 'sessions',
				ops: [
					['update', { cancelled_at: '2026-07-15T12:30:00.000Z' }],
					['eq', 'id', SESSION_ID],
					['select', 'id']
				]
			}
		]);
	});
});

describe('updateSession', () => {
	it('sends only the given editable keys', async () => {
		fake.current.respond('sessions', { data: [{ id: SESSION_ID }], error: null });
		await updateSession(SESSION_ID, { note: 'x', starts_at: NEW.starts_at });
		expect(Object.keys(fake.current.calls[0]!.ops[0]![1] as object)).toEqual(['starts_at', 'note']);
	});
	it('empty patch makes no call', async () => {
		await updateSession(SESSION_ID, {});
		expect(fake.current.calls).toHaveLength(0);
	});
	it('never sends cancelled_at or organizer_id', async () => {
		fake.current.respond('sessions', { data: [{ id: SESSION_ID }], error: null });
		const sneaky = { note: 'x', cancelled_at: 'now', organizer_id: 'z' } as unknown as Partial<NewSession>;
		await updateSession(SESSION_ID, sneaky);
		expect(fake.current.calls[0]!.ops[0]).toEqual(['update', { note: 'x' }]);
	});
});

describe('reads', () => {
	it('getMySession with a malformed slug does not query', async () => {
		expect(await getMySession('abc')).toBeNull();
		expect(fake.current.calls).toHaveLength(0);
	});
	it('listMySessions filters on the organizer', async () => {
		fake.current.respond('sessions', { data: [SESSION_ROW], error: null });
		expect(await listMySessions(USER_ID, new Date(NOW_SESSIONS))).toEqual([SESSION_ROW]);
		const ops = fake.current.calls[0]!.ops;
		expect(ops).toContainEqual(['eq', 'organizer_id', USER_ID]);
		expect(ops).toContainEqual(['gt', 'ends_at', NOW_SESSIONS]);
	});
});

describe('sessionErrorMessage', () => {
	it.each([
		['rate_limited', MSG.rateLimited],
		['23503', MSG.spotGone],
		['23514', MSG.invalid],
		['23502', MSG.invalid],
		['22001', MSG.invalid],
		['42501', MSG.signedOut],
		['PGRST301', MSG.signedOut],
		['PGRST303', MSG.signedOut],
		['PGRST302', MSG.generic],
		['not_found', MSG.notFound],
		[null, MSG.generic]
	])('%s', (code, msg) => {
		expect(sessionErrorMessage(new DataError('x', code))).toBe(msg);
	});
	it('never leaks other errors', () => {
		expect(sessionErrorMessage(new Error('geheim'))).toBe(MSG.generic);
		expect(sessionErrorMessage('geheim')).not.toContain('geheim');
	});
});
