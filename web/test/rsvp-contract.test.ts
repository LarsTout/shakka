// @vitest-environment node
import { readdirSync, readFileSync } from 'node:fs';
import { describe, expect, it, vi } from 'vitest';
import {
	MAX_FIRST_NAME,
	MAX_RSVPS,
	MAX_SEATS,
	PUBLIC_RSVP_KEYS,
	PUBLIC_SESSION_KEYS,
	SESSION_RETENTION_DAYS
} from '../src/lib/rsvp-types.js';
import { EDIT_TOKEN_RE, RPC_ERROR_CODES, SESSION_SLUG_RE } from '../src/lib/session-view.js';

const h = vi.hoisted(() => ({ fake: null as unknown }));
vi.mock('#lib/supabase.js', async () => {
	const { createFakeRpc } = await import('./helpers/fake-rpc.js');
	const fake = createFakeRpc();
	h.fake = fake;
	return { supabase: { rpc: fake.rpc }, initialUrlHash: '' };
});

import { createRsvp, deleteRsvp, getPublicSession, updateRsvp } from '../src/lib/rsvp.js';
import type { createFakeRpc } from './helpers/fake-rpc.js';
import { NEW_ID, SLUG, TOKEN } from './fixtures/public-session.js';

const MIGRATIONS = new URL('../../supabase/migrations/', import.meta.url);
const SESSIONS_FILE = '20261015200000_sessions.sql';
const MODERATION_FILE = '20261028090000_organizer_moderation.sql';
// Migrations that define or replace the session RPCs, oldest first. A later WP that touches
// them adds its file here and extends (0b) for its own file.
const CONTRACT_FILES = [SESSIONS_FILE, MODERATION_FILE] as const;
const SESSION_NAMES = ['get_public_session', 'rsvp_create', 'rsvp_update', 'rsvp_delete', 'purge_expired_sessions'];
const read = (file: string) => readFileSync(new URL(file, MIGRATIONS), 'utf8');
const sql = CONTRACT_FILES.map(read).join('\n');

/** The last definition of the function across CONTRACT_FILES. */
function fnBlock(name: string): string {
	const re = new RegExp(`create (?:or replace )?function public\\.${name}\\(`);
	for (const file of [...CONTRACT_FILES].reverse()) {
		const t = read(file);
		const m = re.exec(t);
		if (m) return t.slice(m.index, t.indexOf('$$;', m.index) + 3);
	}
	throw new Error(`function ${name} not found`);
}
function params(name: string): string[] {
	const m = /create (?:or replace )?function public\.\w+\(([\s\S]*?)\)\s*returns/.exec(fnBlock(name));
	return m![1]
		.split(',')
		.map((p) => p.trim().split(/\s+/)[0])
		.filter(Boolean);
}
const keysIn = (text: string) => [...text.matchAll(/'([a-z_]+)',/g)].map((m) => m[1]);

describe('migration drift (0)', () => {
	it('(0a) no other later migration changes the session RPCs or rsvps', () => {
		const later = readdirSync(MIGRATIONS)
			.filter((f) => f.endsWith('.sql'))
			.sort()
			.filter((f) => f > SESSIONS_FILE && !(CONTRACT_FILES as readonly string[]).includes(f));
		for (const file of later) {
			const t = read(file);
			const msg = `${file} changes the session RPCs or rsvps: update rsvp-types.ts, session-view.ts and rsvp-contract.test.ts`;
			expect(
				/\b(get_public_session|rsvp_create|rsvp_update|rsvp_delete|purge_expired_sessions)\b/.test(t),
				msg
			).toBe(false);
			expect(/alter\s+table\s+(if\s+exists\s+)?(only\s+)?public\.rsvps\b/i.test(t), msg).toBe(false);
		}
	});
	it('(0b) the WP-25 migration only touches get_public_session and rsvp_create', () => {
		const t = read(MODERATION_FILE);
		const named = SESSION_NAMES.filter((n) => new RegExp(`\\b${n}\\b`).test(t));
		expect(named.sort()).toEqual(['get_public_session', 'rsvp_create']);
		expect(/alter\s+table\s+(if\s+exists\s+)?(only\s+)?public\.rsvps\b/i.test(t)).toBe(false);
	});
});

describe('RPC contract (WP-19 and WP-25 migrations)', () => {
	it('(1) parameter names', () => {
		expect(params('get_public_session')).toEqual(['p_slug']);
		expect(params('rsvp_create')).toEqual(['p_slug', 'p_first_name', 'p_ride', 'p_seats_offered']);
		expect(params('rsvp_update')).toEqual([
			'p_edit_token',
			'p_first_name',
			'p_ride',
			'p_seats_offered',
			'p_rides_with'
		]);
		expect(params('rsvp_delete')).toEqual(['p_edit_token']);
	});
	it('(1b) the keys rsvp.ts sends equal the migration parameters', async () => {
		const fake = h.fake as ReturnType<typeof createFakeRpc>;
		const ok = (data: unknown) => ({ data, error: null, status: 200 });
		const rsvp = { id: NEW_ID, first_name: 'A', ride: 'own', seats_offered: null, rides_with: null, created_at: 'x' };
		fake.respond('get_public_session', ok(null));
		fake.respond('rsvp_create', ok({ rsvp_id: NEW_ID, edit_token: TOKEN }));
		fake.respond('rsvp_update', ok(rsvp));
		fake.respond('rsvp_delete', ok(true));
		await getPublicSession(SLUG);
		await createRsvp(SLUG, { first_name: 'A', ride: 'own', seats_offered: null });
		await updateRsvp(TOKEN, { first_name: 'A', ride: 'own', seats_offered: null, rides_with: null });
		await deleteRsvp(TOKEN);
		const sent = Object.fromEntries(fake.calls.map((c) => [c.fn, Object.keys(c.args ?? {})]));
		for (const fn of ['get_public_session', 'rsvp_create', 'rsvp_update', 'rsvp_delete']) {
			expect(sent[fn], fn).toEqual(params(fn));
		}
	});
	it('(2) get_public_session keys', () => {
		const b = fnBlock('get_public_session');
		const sStart = b.indexOf("'session', jsonb_build_object(");
		const rStart = b.indexOf("'rsvps',");
		expect(keysIn(b.slice(sStart + "'session', jsonb_build_object(".length, rStart))).toEqual([
			...PUBLIC_SESSION_KEYS
		]);
		const after = b.slice(rStart + "'rsvps',".length, b.indexOf('order by r.created_at'));
		expect(keysIn(after)).toEqual([...PUBLIC_RSVP_KEYS]);
	});
	it('(3) rsvp_update returns the public RSVP keys', () => {
		const b = fnBlock('rsvp_update');
		const start = b.indexOf('return jsonb_build_object(');
		expect(keysIn(b.slice(start + 'return jsonb_build_object('.length))).toEqual([...PUBLIC_RSVP_KEYS]);
	});
	it('(4) rsvp_create returns rsvp_id and edit_token', () => {
		const b = fnBlock('rsvp_create');
		expect(b).toContain("'rsvp_id'");
		expect(b).toContain("'edit_token'");
	});
	it('(5) error codes', () => {
		const t = fnBlock('rsvp_create') + fnBlock('rsvp_update') + fnBlock('rsvp_delete');
		const set = new Set([...t.matchAll(/using message = '([a-z_]+)'/g)].map((m) => m[1]));
		expect([...set].sort()).toEqual([...RPC_ERROR_CODES].sort());
	});
	it('(6) token and slug regexes', () => {
		expect(fnBlock('rsvp_update')).toContain(`'${EDIT_TOKEN_RE.source}'`);
		expect(fnBlock('get_public_session')).toContain(`'${SESSION_SLUG_RE.source}'`);
	});
	it('(7) retention', () => {
		const m = /ends_at < p_now - interval '(\d+) days'/.exec(sql);
		expect(Number(m![1])).toBe(SESSION_RETENTION_DAYS);
	});
	it('(9) sign-ups can be closed', () => {
		expect(fnBlock('get_public_session')).toContain("'rsvps_closed', s.rsvps_closed_at is not null");
		expect(fnBlock('rsvp_create')).toContain('s.rsvps_closed_at is not null');
	});
	it('(8) limits', () => {
		expect(sql).toContain(`between 0 and ${MAX_SEATS}`);
		expect(sql).toContain(`between 1 and ${MAX_FIRST_NAME}`);
		expect(fnBlock('rsvp_create')).toContain(`>= ${MAX_RSVPS}`);
	});
});
