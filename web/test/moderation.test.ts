// @vitest-environment node
import { readFileSync } from 'node:fs';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { createFakeRpc } from './helpers/fake-rpc.js';
import type { createFakeSupabase } from './helpers/fake-supabase.js';

const h = vi.hoisted(() => ({ rpc: null as unknown, db: null as unknown }));
vi.mock('#lib/supabase.js', async () => {
	const { createFakeRpc } = await import('./helpers/fake-rpc.js');
	const { createFakeSupabase } = await import('./helpers/fake-supabase.js');
	const rpc = createFakeRpc();
	const db = createFakeSupabase();
	h.rpc = rpc;
	h.db = db;
	return { supabase: { rpc: rpc.rpc, from: db.client.from }, initialUrlHash: '' };
});

import { DataError } from '../src/lib/data.js';
import {
	MODERATION_MESSAGES,
	MODERATION_RPC_TIMEOUT_MS,
	deleteRsvpAsOrganizer,
	setRsvpsClosed
} from '../src/lib/moderation.js';
import { EVA_ID } from './fixtures/public-session.js';
import { SESSION_ROW } from './fixtures/session-data.js';
import { writeCalls } from './helpers/fake-supabase.js';

const rpc = () => h.rpc as ReturnType<typeof createFakeRpc>;
const db = () => h.db as ReturnType<typeof createFakeSupabase>;
const FN = 'organizer_delete_rsvp';
const ok = (data: unknown) => ({ data, error: null, status: 200 });

beforeEach(() => {
	rpc().reset();
	db().reset();
	vi.spyOn(console, 'warn').mockImplementation(() => {});
});
afterEach(() => vi.restoreAllMocks());

describe('deleteRsvpAsOrganizer', () => {
	it('sends exactly the migration parameters', async () => {
		const sql = readFileSync(
			new URL('../../supabase/migrations/20261028090000_organizer_moderation.sql', import.meta.url),
			'utf8'
		);
		const m = /create function public\.organizer_delete_rsvp\(([\s\S]*?)\)\s*returns/.exec(sql)!;
		const params = m[1]!
			.split(',')
			.map((p) => p.trim().split(/\s+/)[0])
			.filter(Boolean);
		rpc().respond(FN, ok(true));
		await deleteRsvpAsOrganizer(EVA_ID);
		expect(Object.keys(rpc().calls[0]!.args ?? {})).toEqual(params);
		expect(rpc().calls[0]!.args).toEqual({ p_rsvp_id: EVA_ID });
	});
	it('true -> ok', async () => {
		rpc().respond(FN, ok(true));
		await expect(deleteRsvpAsOrganizer(EVA_ID)).resolves.toEqual({ ok: true });
		expect(console.warn).not.toHaveBeenCalled();
	});
	it('false -> alreadyGone', async () => {
		rpc().respond(FN, ok(false));
		await expect(deleteRsvpAsOrganizer(EVA_ID)).resolves.toEqual({
			ok: false,
			error: MODERATION_MESSAGES.alreadyGone
		});
	});
	it('PT error -> failed', async () => {
		rpc().respond(FN, { data: null, error: { code: 'PT400', message: 'x' }, status: 400 });
		await expect(deleteRsvpAsOrganizer(EVA_ID)).resolves.toEqual({ ok: false, error: MODERATION_MESSAGES.failed });
	});
	it('status 0 -> network', async () => {
		rpc().respond(FN, { data: null, error: { message: 'fetch failed' }, status: 0 });
		await expect(deleteRsvpAsOrganizer(EVA_ID)).resolves.toEqual({
			ok: false,
			error: MODERATION_MESSAGES.network
		});
	});
	it('thrown -> network', async () => {
		rpc().throwNext(FN, new TypeError('offline'));
		await expect(deleteRsvpAsOrganizer(EVA_ID)).resolves.toEqual({
			ok: false,
			error: MODERATION_MESSAGES.network
		});
	});
	it('non-boolean -> failed', async () => {
		rpc().respond(FN, ok('yes'));
		await expect(deleteRsvpAsOrganizer(EVA_ID)).resolves.toEqual({ ok: false, error: MODERATION_MESSAGES.failed });
	});
	it('invalid uuid: no request', async () => {
		await expect(deleteRsvpAsOrganizer('nope')).resolves.toEqual({ ok: false, error: MODERATION_MESSAGES.failed });
		expect(rpc().calls).toHaveLength(0);
	});
	it('sets an abort signal', async () => {
		rpc().respond(FN, ok(true));
		await deleteRsvpAsOrganizer(EVA_ID);
		expect(rpc().calls[0]!.signal).not.toBeNull();
		expect(MODERATION_RPC_TIMEOUT_MS).toBe(15_000);
	});
	it('warns once without details', async () => {
		rpc().respond(FN, { data: null, error: { code: 'PT400', message: 'secret detail' }, status: 400 });
		await deleteRsvpAsOrganizer(EVA_ID);
		expect(console.warn).toHaveBeenCalledTimes(1);
		expect(console.warn).toHaveBeenCalledWith('organizer delete failed');
	});
});

describe('setRsvpsClosed', () => {
	const NOW = new Date('2026-07-18T09:00:00.000Z');
	const hit = { data: [{ id: SESSION_ROW.id }], error: null };
	it('closing sends the exact update payload', async () => {
		db().respond('sessions', hit);
		await setRsvpsClosed(SESSION_ROW.id, true, NOW);
		expect(writeCalls(db().calls)).toEqual([
			{
				table: 'sessions',
				ops: [
					['update', { rsvps_closed_at: NOW.toISOString() }],
					['eq', 'id', SESSION_ROW.id],
					['select', 'id']
				]
			}
		]);
	});
	it('opening sends null', async () => {
		db().respond('sessions', hit);
		await setRsvpsClosed(SESSION_ROW.id, false, NOW);
		expect(writeCalls(db().calls)[0]!.ops[0]).toEqual(['update', { rsvps_closed_at: null }]);
	});
	it('0 rows -> DataError not_found', async () => {
		db().respond('sessions', { data: [], error: null });
		const err = await setRsvpsClosed(SESSION_ROW.id, true, NOW).catch((e: unknown) => e);
		expect(err).toBeInstanceOf(DataError);
		expect(err).toMatchObject({ operation: 'updateOwnSession', code: 'not_found' });
	});
});
