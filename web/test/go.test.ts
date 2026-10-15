import { isRedirect } from '@sveltejs/kit';
import { describe, expect, it } from 'vitest';
import {
	goHref,
	goRuns,
	newSessionHref,
	parseNewSessionParams
} from '../src/lib/go.js';
import { parseGoParams } from '../src/lib/time.js';
import type { Evaluation } from '../src/lib/types.js';
import { load } from '../src/routes/go/+page.js';
import { GO_URL_DST_DAY, GO_URL_DST_NIGHT } from './fixtures/session-data.js';
import { EVAL_DARK, EVAL_GO, EVAL_LOWCONF, EVAL_OFFSHORE, GO_URL_SUMMER } from './fixtures/spot-data.js';

const S = '2026-07-18T12%3A00%3A00Z';
const E = '2026-07-18T16%3A00%3A00Z';
const d = (s: string) => new Date(s);
const pathOf = (u: string) => new URL(u).pathname + new URL(u).search;

function run(url: string) {
	try {
		return (load as (e: unknown) => unknown)({ url: new URL(url) });
	} catch (e) {
		return e;
	}
}

describe('/go load (AC-2)', () => {
	it('valid link gives returnPath and target', () => {
		expect(run(GO_URL_SUMMER)).toEqual({
			returnPath: `/go?spot=test-strand&start=${S}&end=${E}`,
			target: `/sessie/nieuw?spot=test-strand&start=${S}&end=${E}`
		});
	});
	it.each([
		'https://example.org/go',
		'https://example.org/go?spot=test-strand',
		`https://example.org/go?spot=../x&start=${S}&end=${E}`,
		`https://example.org/go?spot=Test&start=${S}&end=${E}`,
		`https://example.org/go?spot=a&start=2026-07-18T12%3A30%3A00Z&end=${E}`,
		`https://example.org/go?spot=a&start=${E}&end=${S}`
	])('invalid -> 307 /: %s', (u) => {
		const e = run(u) as { status: number; location: string };
		expect(isRedirect(e)).toBe(true);
		expect(e.status).toBe(307);
		expect(e.location).toBe('/');
	});
});

describe('goHref', () => {
	it('equals the WP-08 format', () => {
		expect(goHref('test-strand', d('2026-07-18T12:00:00Z'), d('2026-07-18T16:00:00Z'))).toBe(
			pathOf(GO_URL_SUMMER)
		);
		expect(goHref('test-strand', d('2026-10-25T10:00:00Z'), d('2026-10-25T14:00:00Z'))).toBe(
			pathOf(GO_URL_DST_DAY)
		);
		expect(goHref('test-strand', d('2026-10-25T00:00:00Z'), d('2026-10-25T02:00:00Z'))).toBe(
			pathOf(GO_URL_DST_NIGHT)
		);
	});
	it('parses back', () => {
		const p = parseGoParams(
			new URL(goHref('test-strand', d('2026-07-18T12:00:00Z'), d('2026-07-18T16:00:00Z')), 'https://x')
		);
		expect(p?.spot).toBe('test-strand');
		expect(p?.start.toISOString()).toBe('2026-07-18T12:00:00.000Z');
		expect(p?.end.toISOString()).toBe('2026-07-18T16:00:00.000Z');
	});
	it('newSessionHref uses the same query', () => {
		const p = parseGoParams(new URL(GO_URL_SUMMER))!;
		expect(newSessionHref(p)).toBe(`/sessie/nieuw?spot=test-strand&start=${S}&end=${E}`);
	});
});

const ev = (iso: string, verdict: Evaluation['verdict'], reasons: Evaluation['reasons'] = []): Evaluation => ({
	...EVAL_GO,
	valid_at: iso,
	verdict,
	reasons
});

describe('goRuns', () => {
	it('splits on a no_go (E44)', () => {
		const r = goRuns([
			ev('2026-07-15T12:00:00Z', 'go'),
			ev('2026-07-15T13:00:00Z', 'go'),
			ev('2026-07-15T14:00:00Z', 'no_go'),
			ev('2026-07-15T15:00:00Z', 'go')
		]);
		expect(r.map((x) => [x.start.toISOString(), x.end.toISOString()])).toEqual([
			['2026-07-15T12:00:00.000Z', '2026-07-15T14:00:00.000Z'],
			['2026-07-15T15:00:00.000Z', '2026-07-15T16:00:00.000Z']
		]);
	});
	it('a gap in the data makes two runs (E45)', () => {
		expect(goRuns([ev('2026-07-15T12:00:00Z', 'go'), ev('2026-07-15T14:00:00Z', 'go')])).toHaveLength(2);
	});
	it('sorts unsorted input', () => {
		const r = goRuns([ev('2026-07-15T13:00:00Z', 'go'), ev('2026-07-15T12:00:00Z', 'go')]);
		expect(r).toHaveLength(1);
		expect(r[0]!.end.toISOString()).toBe('2026-07-15T14:00:00.000Z');
	});
	it('ignores non-go hours and dark breaks a run', () => {
		expect(goRuns([EVAL_OFFSHORE, EVAL_LOWCONF])).toEqual([]);
		const r = goRuns([
			ev('2026-07-15T11:00:00Z', 'go'),
			{ ...EVAL_DARK, valid_at: '2026-07-15T12:00:00Z' },
			ev('2026-07-15T13:00:00Z', 'go')
		]);
		expect(r).toHaveLength(2);
	});
});

describe('parseNewSessionParams', () => {
	it('full link', () => {
		expect(parseNewSessionParams(new URL(GO_URL_SUMMER))).toEqual({
			spot: 'test-strand',
			start: '2026-07-18T12:00:00.000Z',
			end: '2026-07-18T16:00:00.000Z'
		});
	});
	it('spot only', () => {
		expect(parseNewSessionParams(new URL('https://x/sessie/nieuw?spot=test-meer'))).toEqual({
			spot: 'test-meer',
			start: null,
			end: null
		});
	});
	it('invalid spot', () => {
		expect(parseNewSessionParams(new URL('https://x/sessie/nieuw?spot=Bad'))).toEqual({
			spot: null,
			start: null,
			end: null
		});
	});
});
