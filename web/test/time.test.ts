import { describe, expect, it } from 'vitest';
import {
	addDaysToKey,
	floorHour,
	formatDateKey,
	formatLocal,
	localDateKey,
	parseGoParams,
	startOfLocalDay
} from '../src/lib/time.js';
import { GO_URL_SUMMER, GO_URL_WINTER } from './fixtures/spot-data.js';

const d = (s: string) => new Date(s);

describe('formatLocal', () => {
	it('time in CEST and CET', () => {
		expect(formatLocal(d('2026-07-15T12:00:00Z'), 'time')).toBe('14:00');
		expect(formatLocal(d('2026-01-15T12:00:00Z'), 'time')).toBe('13:00');
	});
	it('patterns', () => {
		const x = d('2026-07-15T12:00:00Z');
		expect(formatLocal(x, 'day')).toBe('wo 15 jul');
		expect(formatLocal(x, 'dayLong')).toBe('woensdag 15 juli');
		expect(formatLocal(x, 'dateTime')).toBe('wo 15 jul 14:00');
		expect(formatLocal(x, 'dateKey')).toBe('2026-07-15');
		expect(localDateKey(d('2026-07-14T22:30:00Z'))).toBe('2026-07-15');
	});
	it('DST edges', () => {
		expect(formatLocal(d('2026-10-25T00:00:00Z'), 'time')).toBe('02:00');
		expect(formatLocal(d('2026-10-25T01:00:00Z'), 'time')).toBe('02:00');
		expect(formatLocal(d('2026-03-29T01:00:00Z'), 'time')).toBe('03:00');
	});
	it('invalid date throws', () => {
		expect(() => formatLocal(new Date('nope'), 'time')).toThrow(RangeError);
	});
});

describe('addDaysToKey', () => {
	it('calendar arithmetic', () => {
		expect(addDaysToKey('2026-12-31', 1)).toBe('2027-01-01');
		expect(addDaysToKey('2026-03-01', -1)).toBe('2026-02-28');
		expect(addDaysToKey('2026-10-25', 1)).toBe('2026-10-26');
	});
	it('malformed key', () => {
		expect(() => addDaysToKey('2026-02-30', 1)).toThrow(RangeError);
		expect(() => addDaysToKey('nope', 1)).toThrow(RangeError);
	});
});

describe('startOfLocalDay', () => {
	it.each([
		['2026-07-15', '2026-07-14T22:00:00.000Z'],
		['2026-01-15', '2026-01-14T23:00:00.000Z'],
		['2026-03-29', '2026-03-28T23:00:00.000Z'],
		['2026-03-30', '2026-03-29T22:00:00.000Z'],
		['2026-10-25', '2026-10-24T22:00:00.000Z'],
		['2026-10-26', '2026-10-25T23:00:00.000Z']
	])('%s', (key, iso) => {
		expect(startOfLocalDay(key).toISOString()).toBe(iso);
	});
	it('malformed key', () => {
		expect(() => startOfLocalDay('2026-13-01')).toThrow(RangeError);
	});
});

describe('misc', () => {
	it('formatDateKey', () => {
		expect(formatDateKey('2026-07-18', 'day')).toBe('za 18 jul');
		expect(formatDateKey('2026-07-18', 'dayLong')).toBe('zaterdag 18 juli');
	});
	it('floorHour', () => {
		expect(floorHour(d('2026-07-15T12:30:45.5Z')).toISOString()).toBe('2026-07-15T12:00:00.000Z');
	});
});

describe('parseGoParams (AC-5)', () => {
	it('summer and winter fixtures', () => {
		const s = parseGoParams(new URL(GO_URL_SUMMER))!;
		expect(s.spot).toBe('test-strand');
		expect(s.start.getTime()).toBe(Date.parse('2026-07-18T12:00:00Z'));
		expect(s.end.getTime()).toBe(Date.parse('2026-07-18T16:00:00Z'));
		const w = parseGoParams(new URL(GO_URL_WINTER))!;
		expect(w.start.getTime()).toBe(Date.parse('2026-11-07T11:00:00Z'));
		expect(w.end.getTime()).toBe(Date.parse('2026-11-07T14:00:00Z'));
	});

	const S = '2026-07-18T12:00:00Z';
	const E = '2026-07-18T16:00:00Z';
	const u = (q: string) => new URL(`https://example.org/go?${q}`);
	it.each([
		['', 'no params'],
		[`spot=../x&start=${S}&end=${E}`, 'path spot'],
		[`spot=Test&start=${S}&end=${E}`, 'uppercase spot'],
		[`spot=a&start=2026-07-18T12:30:00Z&end=${E}`, 'minutes'],
		[`spot=a&start=2026-02-30T12:00:00Z&end=${E}`, 'invalid date'],
		[`spot=a&start=2026-07-18T24:00:00Z&end=${E}`, 'hour 24'],
		[`spot=a&start=2026-07-18T12:00:00%2B00:00&end=${E}`, 'offset'],
		[`spot=a&start=${S}&end=${S}`, 'start == end'],
		[`spot=a&start=${E}&end=${S}`, 'start > end'],
		[`spot=a&start=${S}`, 'missing end'],
		[`spot=${'a'.repeat(101)}&start=${S}&end=${E}`, 'slug too long']
	])('invalid: %s (%s)', (q) => {
		expect(parseGoParams(u(q))).toBeNull();
	});
	it('accepts a slug of exactly 100 characters', () => {
		expect(parseGoParams(u(`spot=${'a'.repeat(100)}&start=${S}&end=${E}`))).not.toBeNull();
	});
	it('first value wins, extras ignored', () => {
		const r = parseGoParams(u(`spot=a&spot=b&x=1&start=${S}&end=${E}`));
		expect(r?.spot).toBe('a');
	});
});
