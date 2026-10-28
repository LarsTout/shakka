import { describe, expect, it } from 'vitest';
import {
	dayTabLabel,
	dayTimeline,
	hoursOnDay,
	quietTimeline,
	sessionTimeline,
	type TimelineHour
} from '../src/lib/timeline.js';
import type { TideExtreme } from '../src/lib/types.js';

const h = (iso: string, verdict: TimelineHour['verdict'], reasons: TimelineHour['reasons'] = []) => ({
	valid_at: iso,
	verdict,
	reasons
});
const tide = (at: string, kind: 'high' | 'low'): TideExtreme => ({
	station: 's',
	at,
	kind,
	level_cm: 0
});

describe('dayTimeline', () => {
	it('slots and gaps, skipping dark', () => {
		const tl = dayTimeline([
			h('2026-07-15T12:00:00+00:00', 'go'),
			h('2026-07-15T14:00:00+00:00', 'marginal'),
			h('2026-07-15T21:00:00+00:00', 'no_go', ['dark'])
		]);
		expect(tl?.slots).toEqual(['go', 'none', 'marginal']);
		expect(tl?.window).toBeNull();
	});

	it('ticks at local hours divisible by 3', () => {
		// 12:00Z = 14:00 local (CEST); axis 14..17 local
		const tl = dayTimeline([
			h('2026-07-15T12:00:00+00:00', 'go'),
			h('2026-07-15T13:00:00+00:00', 'go'),
			h('2026-07-15T14:00:00+00:00', 'go')
		])!;
		expect(tl.ticks).toEqual([{ pos: 1 / 3, label: '15' }]);
	});

	it('tide and now markers in range only, with row staggering', () => {
		const hours = ['12', '13', '14', '15', '16', '17'].map((x) =>
			h(`2026-07-15T${x}:00:00+00:00`, 'go')
		);
		const tl = dayTimeline(hours, {
			tides: [
				tide('2026-07-15T09:10:00+00:00', 'high'), // before the axis
				tide('2026-07-15T15:40:00+00:00', 'low'),
				tide('2026-07-15T20:00:00+00:00', 'high') // after the axis
			],
			now: new Date('2026-07-15T15:30:00+00:00')
		})!;
		expect(tl.markers.map((m) => [m.label, m.row])).toEqual([
			['nu', 0],
			['LW 17:40', 1]
		]);
		expect(tl.markers[0]!.pos).toBeCloseTo(3.5 / 6);
	});

	it('null without daylight', () => {
		expect(dayTimeline([])).toBeNull();
		expect(dayTimeline([h('2026-07-15T21:00:00+00:00', 'no_go', ['dark'])])).toBeNull();
	});
});

describe('sessionTimeline', () => {
	const evals = [
		h('2026-07-15T09:00:00+00:00', 'go'), // 11:00 local
		h('2026-07-15T10:00:00+00:00', 'marginal') // 12:00 local
	];
	it('11:00-16:00 on axis 06-22', () => {
		const tl = sessionTimeline(evals, '2026-07-15T09:00:00Z', '2026-07-15T14:00:00Z')!;
		expect(tl.slots).toHaveLength(16);
		expect(tl.window).toEqual({ from: 5 / 16, to: 10 / 16 });
		expect(tl.slots.slice(0, 5).every((k) => k === 'outside')).toBe(true);
		expect(tl.slots.slice(5, 10)).toEqual(['go', 'marginal', 'none', 'none', 'none']);
		expect(tl.slots.slice(10).every((k) => k === 'outside')).toBe(true);
		expect(tl.markers).toEqual([]);
	});
	it('05:30-08:00 starts the axis at 05', () => {
		const tl = sessionTimeline([], '2026-07-15T03:30:00Z', '2026-07-15T06:00:00Z')!;
		expect(tl.slots).toHaveLength(17);
		expect(tl.window!.from).toBeCloseTo(0.5 / 17);
	});
	it('null across two dates, or when end is not after start', () => {
		expect(sessionTimeline([], '2026-07-15T20:00:00Z', '2026-07-16T06:00:00Z')).toBeNull();
		expect(sessionTimeline([], '2026-07-15T09:00:00Z', '2026-07-15T09:00:00Z')).toBeNull();
	});
	it('accepts an end at local midnight', () => {
		const tl = sessionTimeline([], '2026-07-15T18:00:00Z', '2026-07-15T22:00:00Z')!;
		expect(tl.slots).toHaveLength(18); // 06..24
	});
});

describe('quietTimeline', () => {
	const count = (tl: ReturnType<typeof quietTimeline>) => tl!.slots.filter((k) => k === 'quiet').length;
	it('wraps past midnight', () => {
		const tl = quietTimeline('22:00:00', '07:00:00');
		expect(tl!.slots).toHaveLength(24);
		expect(count(tl)).toBe(9);
		expect(tl!.ticks.map((t) => t.label)).toEqual(['00', '06', '12', '18', '24']);
	});
	it('13:00-15:00', () => {
		expect(count(quietTimeline('13:00', '15:00'))).toBe(2);
	});
	it('null when off, equal or invalid', () => {
		expect(quietTimeline(null, null)).toBeNull();
		expect(quietTimeline('08:00', '08:00')).toBeNull();
		expect(quietTimeline('25:00', '08:00')).toBeNull();
	});
});

describe('hoursOnDay and dayTabLabel', () => {
	it('filters on local date', () => {
		const rows = [h('2026-07-15T21:30:00+00:00', 'go'), h('2026-07-15T22:30:00+00:00', 'go')];
		expect(hoursOnDay(rows, '2026-07-15')).toHaveLength(1);
		expect(hoursOnDay(rows, '2026-07-16')).toHaveLength(1);
	});
	it('labels', () => {
		expect(dayTabLabel('2026-07-15', '2026-07-15')).toBe('Vandaag');
		expect(dayTabLabel('2026-07-16', '2026-07-15')).toBe('Morgen');
		expect(dayTabLabel('2026-07-17', '2026-07-15')).toBe('vr 17 jul');
	});
});
