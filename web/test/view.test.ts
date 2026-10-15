import { describe, expect, it } from 'vitest';
import {
	daySummaryText,
	dayHeading,
	groupByLocalDay,
	isDark,
	isStale,
	latestEvaluatedAt,
	latestOfSummaries,
	shouldRefreshOnResume,
	summarizeSpots,
	tidesForDay,
	visibleHours
} from '../src/lib/view.js';
import type { SummaryRow } from '../src/lib/types.js';
import {
	EVALUATED_AT,
	EVAL_DARK,
	EVAL_GO,
	EVAL_LOWCONF,
	EVAL_OFFSHORE,
	EVAL_TOMORROW,
	NOW_FRESH,
	NOW_STALE,
	TIDES
} from './fixtures/spot-data.js';

describe('freshness', () => {
	it('latestEvaluatedAt', () => {
		expect(latestEvaluatedAt([])).toBeNull();
		const r = latestEvaluatedAt([
			{ evaluated_at: '2026-07-15T10:00:00+00:00' },
			{ evaluated_at: '2026-07-15T12:05:00+00:00' }
		]);
		expect(r?.toISOString()).toBe('2026-07-15T12:05:00.000Z');
	});
	it('isStale', () => {
		const latest = new Date(EVALUATED_AT);
		expect(isStale(latest, new Date(NOW_FRESH))).toBe(false);
		expect(isStale(latest, new Date(NOW_STALE))).toBe(true);
		expect(isStale(latest, new Date('2026-07-15T15:05:00Z'))).toBe(false);
		expect(isStale(latest, new Date('2026-07-15T15:05:00.001Z'))).toBe(true);
		expect(isStale(new Date('2026-07-16T00:00:00Z'), new Date(NOW_FRESH))).toBe(false);
		expect(isStale(null, new Date(NOW_FRESH))).toBe(false);
	});
	it('shouldRefreshOnResume', () => {
		const base = Date.parse(NOW_FRESH);
		expect(shouldRefreshOnResume(NOW_FRESH, base + 10 * 60 * 1000)).toBe(false);
		expect(shouldRefreshOnResume(NOW_FRESH, base + 10 * 60 * 1000 + 1)).toBe(true);
	});
});

describe('grouping', () => {
	const all = [EVAL_TOMORROW, EVAL_DARK, EVAL_GO, EVAL_LOWCONF, EVAL_OFFSHORE];
	it('groupByLocalDay', () => {
		const g = groupByLocalDay(all);
		expect(g.map((x) => x.dateKey)).toEqual(['2026-07-15', '2026-07-16']);
		expect(g[0]!.hours.map((h) => h.valid_at)).toEqual([
			EVAL_GO.valid_at,
			EVAL_OFFSHORE.valid_at,
			EVAL_LOWCONF.valid_at,
			EVAL_DARK.valid_at
		]);
	});
	it('E5: autumn night shares one group', () => {
		const mk = (valid_at: string) => ({ ...EVAL_DARK, valid_at });
		const g = groupByLocalDay([mk('2026-10-25T01:00:00+00:00'), mk('2026-10-25T00:00:00+00:00')]);
		expect(g).toHaveLength(1);
		expect(g[0]!.dateKey).toBe('2026-10-25');
		expect(g[0]!.hours).toHaveLength(2);
	});
	it('dark handling', () => {
		expect(isDark(EVAL_DARK)).toBe(true);
		expect(isDark(EVAL_GO)).toBe(false);
		const hours = [EVAL_GO, EVAL_DARK];
		expect(visibleHours(hours, false)).toEqual([EVAL_GO]);
		expect(visibleHours(hours, true)).toEqual(hours);
	});
	it('tidesForDay', () => {
		expect(tidesForDay(TIDES, '2026-07-15')).toHaveLength(2);
		expect(tidesForDay(TIDES, '2026-07-16')).toEqual([]);
		const late = { ...TIDES[0]!, at: '2026-07-15T22:30:00+00:00' };
		expect(tidesForDay([late], '2026-07-16')).toEqual([late]);
		expect(tidesForDay([late], '2026-07-15')).toEqual([]);
	});
	it('dayHeading', () => {
		expect(dayHeading('2026-07-15', '2026-07-15')).toBe('Vandaag (wo 15 jul)');
		expect(dayHeading('2026-07-16', '2026-07-15')).toBe('Morgen (do 16 jul)');
		expect(dayHeading('2026-07-17', '2026-07-15')).toBe('vr 17 jul');
	});
});

const row = (valid_at: string, verdict: SummaryRow['verdict'], reasons: SummaryRow['reasons'] = []): SummaryRow => ({
	spot_id: 'test-strand',
	valid_at,
	verdict,
	reasons,
	evaluated_at: EVALUATED_AT
});

describe('summarizeSpots', () => {
	const rows = [
		row('2026-07-15T12:00:00+00:00', 'go'),
		row('2026-07-15T13:00:00+00:00', 'go'),
		row('2026-07-15T14:00:00+00:00', 'marginal'),
		row('2026-07-15T21:00:00+00:00', 'no_go', ['dark']),
		row('2026-07-16T08:00:00+00:00', 'no_go'),
		row('2026-07-17T10:00:00+00:00', 'go'),
		row('2026-07-15T11:00:00+00:00', 'go')
	];
	const now = new Date(NOW_FRESH);
	it('summarises today and tomorrow', () => {
		const s = summarizeSpots(rows, now)['test-strand']!;
		expect(s.today).toEqual({
			date: '2026-07-15',
			go: 2,
			marginal: 1,
			no_go: 0,
			best: 'go',
			first_go_at: '2026-07-15T12:00:00+00:00'
		});
		expect(s.tomorrow).toEqual({
			date: '2026-07-16',
			go: 0,
			marginal: 0,
			no_go: 1,
			best: 'no_go',
			first_go_at: null
		});
		expect(s.latest_evaluated_at).toBe(EVALUATED_AT);
	});
	it('first_go_at compares as dates, not strings', () => {
		const s = summarizeSpots(
			[row('2026-07-15T13:00:00Z', 'go'), row('2026-07-15T12:00:00+00:00', 'go')],
			now
		)['test-strand']!;
		expect(s.today.first_go_at).toBe('2026-07-15T12:00:00+00:00');
	});
	it('no key without rows in range', () => {
		expect(summarizeSpots([], now)).toEqual({});
		expect(summarizeSpots([row('2026-07-17T10:00:00+00:00', 'go')], now)).toEqual({});
	});
	it('E6: day of 25 hours', () => {
		const s = summarizeSpots(
			[row('2026-10-24T23:00:00+00:00', 'go'), row('2026-10-25T10:00:00+00:00', 'go')],
			new Date('2026-10-24T22:30:00Z')
		)['test-strand']!;
		expect(s.today.date).toBe('2026-10-25');
		expect(s.tomorrow.date).toBe('2026-10-26');
	});
});

describe('daySummaryText', () => {
	const d = (go: number, marginal: number, no_go: number) => ({
		date: '2026-07-15',
		go,
		marginal,
		no_go,
		best: null,
		first_go_at: go ? '2026-07-15T12:00:00+00:00' : null
	});
	it('variants', () => {
		expect(daySummaryText(d(2, 1, 0), true)).toBe('2 uur go vanaf 14:00, 1 uur twijfel');
		expect(daySummaryText(d(2, 0, 0), true)).toBe('2 uur go vanaf 14:00');
		expect(daySummaryText(d(0, 1, 0), true)).toBe('1 uur twijfel, geen go');
		expect(daySummaryText(d(0, 0, 3), false)).toBe('geen go- of twijfeluren');
		expect(daySummaryText(d(0, 0, 0), true)).toBe('geen daglichturen meer');
		expect(daySummaryText(d(0, 0, 0), false)).toBe('nog geen data');
	});
	it('latestOfSummaries', () => {
		expect(latestOfSummaries({})).toBeNull();
	});
});
