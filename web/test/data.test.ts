import { beforeEach, describe, expect, it, vi } from 'vitest';
import { createFakeSupabase } from './helpers/fake-supabase.js';
import { EVALUATED_AT, NOW_FRESH, SPOT_UNVERIFIED } from './fixtures/spot-data.js';

const fake = vi.hoisted(() => ({ current: null as unknown as ReturnType<typeof createFakeSupabase> }));
vi.mock('#lib/supabase.js', async () => {
	const { createFakeSupabase } = await import('./helpers/fake-supabase.js');
	fake.current = createFakeSupabase();
	return { supabase: fake.current.client, initialUrlHash: '' };
});

import {
	DataError,
	fetchAllPages,
	getEvaluations,
	getSpot,
	getSpotSummaries,
	getTideExtremes,
	listSpots
} from '../src/lib/data.js';
import { EVALUATION_COLUMNS, SPOT_COLUMNS, SUMMARY_COLUMNS, TIDE_EXTREME_COLUMNS } from '../src/lib/types.js';

beforeEach(() => {
	vi.clearAllMocks();
	fake.current.reset();
});

const asc = { ascending: true };

describe('data queries', () => {
	it('listSpots', async () => {
		fake.current.respond('spots', { data: [SPOT_UNVERIFIED], error: null });
		expect(await listSpots()).toEqual([SPOT_UNVERIFIED]);
		expect(fake.current.calls).toEqual([
			{
				table: 'spots',
				ops: [
					['select', SPOT_COLUMNS.join(',')],
					['order', 'name', asc],
					['order', 'id', asc],
					['range', 0, 999]
				]
			}
		]);
	});

	it('getSpot', async () => {
		expect(await getSpot('Bad_ID')).toBeNull();
		expect(fake.current.calls).toHaveLength(0);
		fake.current.respond('spots', { data: null, error: null });
		expect(await getSpot('test-strand')).toBeNull();
		expect(fake.current.calls[0]!.ops).toEqual([
			['select', SPOT_COLUMNS.join(',')],
			['eq', 'id', 'test-strand'],
			['maybeSingle']
		]);
		fake.current.respond('spots', { data: SPOT_UNVERIFIED, error: null });
		expect(await getSpot('test-strand')).toEqual(SPOT_UNVERIFIED);
	});

	it('getEvaluations', async () => {
		await getEvaluations('test-strand', new Date('2026-07-15T12:00:00Z'), new Date('2026-07-22T22:00:00Z'));
		expect(fake.current.calls[0]).toEqual({
			table: 'evaluations',
			ops: [
				['select', EVALUATION_COLUMNS.join(',')],
				['eq', 'spot_id', 'test-strand'],
				['gte', 'valid_at', '2026-07-15T12:00:00.000Z'],
				['lt', 'valid_at', '2026-07-22T22:00:00.000Z'],
				['order', 'valid_at', asc],
				['range', 0, 999]
			]
		});
	});

	it('getTideExtremes trims and skips empty stations', async () => {
		const from = new Date('2026-07-14T22:00:00Z');
		const to = new Date('2026-07-22T22:00:00Z');
		expect(await getTideExtremes('  ', from, to)).toEqual([]);
		expect(fake.current.calls).toHaveLength(0);
		await getTideExtremes(' teststation ', from, to);
		expect(fake.current.calls[0]).toEqual({
			table: 'tide_extremes',
			ops: [
				['select', TIDE_EXTREME_COLUMNS.join(',')],
				['eq', 'station', 'teststation'],
				['gte', 'at', '2026-07-14T22:00:00.000Z'],
				['lt', 'at', '2026-07-22T22:00:00.000Z'],
				['order', 'at', asc],
				['range', 0, 999]
			]
		});
	});

	it('getSpotSummaries', async () => {
		fake.current.respond('evaluations', {
			data: [
				{
					spot_id: 'test-strand',
					valid_at: '2026-07-15T12:00:00+00:00',
					verdict: 'go',
					reasons: [],
					evaluated_at: EVALUATED_AT
				}
			],
			error: null
		});
		const res = await getSpotSummaries(new Date(NOW_FRESH));
		expect(fake.current.calls[0]).toEqual({
			table: 'evaluations',
			ops: [
				['select', SUMMARY_COLUMNS.join(',')],
				['gte', 'valid_at', '2026-07-15T12:00:00.000Z'],
				['lt', 'valid_at', '2026-07-16T22:00:00.000Z'],
				['not', 'reasons', 'cs', '{dark}'],
				['order', 'spot_id', asc],
				['order', 'valid_at', asc],
				['range', 0, 999]
			]
		});
		expect(res['test-strand']?.today.go).toBe(1);
	});
});

describe('fetchAllPages', () => {
	it('paginates per 1000 rows', async () => {
		const page = (n: number) => Array.from({ length: n }, (_, i) => ({ id: String(i) }));
		fake.current.respond('spots', { data: page(1000), error: null }, { data: page(3), error: null });
		const rows = await listSpots();
		expect(rows).toHaveLength(1003);
		const ranges = fake.current.calls.map((c) => c.ops.find((o) => o[0] === 'range'));
		expect(ranges).toEqual([
			['range', 0, 999],
			['range', 1000, 1999]
		]);
	});

	it('stops after maxPages full pages without a further request', async () => {
		const build = () => fake.current.client.from('spots') as never;
		fake.current.respond(
			'spots',
			...Array.from({ length: 5 }, () => ({ data: [{}, {}], error: null }))
		);
		const err = await fetchAllPages('x', build, 2, 3).catch((e: unknown) => e);
		expect(err).toBeInstanceOf(DataError);
		expect((err as DataError).code).toBe('too_many_rows');
		expect(fake.current.calls).toHaveLength(3);
	});

	it('wraps errors without the message', async () => {
		fake.current.respond('spots', { data: null, error: { code: '42501', message: 'secret detail' } });
		const err = await listSpots().catch((e: unknown) => e);
		expect(err).toBeInstanceOf(DataError);
		const e = err as DataError;
		expect(e.operation).toBe('listSpots');
		expect(e.code).toBe('42501');
		expect(e.message).not.toContain('secret detail');
	});
});
