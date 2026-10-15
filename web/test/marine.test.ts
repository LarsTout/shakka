// @vitest-environment node
import { describe, expect, it } from 'vitest';
import { MARINE_STALE_AFTER_MS, formatMeters, marineByHour, waveText } from '../src/lib/marine.js';
import { MARINE_FRESH, MARINE_STALE, NOW_FRESH } from './fixtures/spot-data.js';

const now = new Date(NOW_FRESH);

describe('formatMeters', () => {
	it('one decimal with a comma', () => {
		expect(formatMeters(1.24)).toBe('1,2');
		expect(formatMeters(1.25)).toBe('1,3');
		expect(formatMeters(0)).toBe('0,0');
		expect(formatMeters(0.84)).toBe('0,8');
		expect(formatMeters(2)).toBe('2,0');
	});
});

describe('waveText', () => {
	it('full line', () => {
		expect(waveText(MARINE_FRESH)).toBe('Golven 1,2 m, periode 5 s, uit WZW (250°)');
	});
	it('unknown parts', () => {
		expect(waveText({ ...MARINE_FRESH, wave_height_m: null })).toBe(
			'Golven hoogte onbekend, periode 5 s, uit WZW (250°)'
		);
		expect(waveText({ wave_height_m: 1.24, wave_period_s: null, wave_dir_deg: null })).toBe(
			'Golven 1,2 m, periode onbekend, richting onbekend'
		);
	});
});

describe('marineByHour', () => {
	it('keys on Date.parse of valid_at, also with a Z suffix (E33)', () => {
		const map = marineByHour([MARINE_FRESH], now);
		expect(map.get(Date.parse('2026-07-15T12:00:00Z'))).toBe(MARINE_FRESH);
		const z = { ...MARINE_FRESH, valid_at: '2026-07-15T12:00:00Z' };
		expect(marineByHour([z], now).get(Date.parse('2026-07-15T12:00:00+00:00'))).toBe(z);
	});
	it('hides rows fetched more than 3 hours ago, shows exactly 3 hours', () => {
		expect(marineByHour([MARINE_STALE], now).size).toBe(0);
		const edge = {
			...MARINE_FRESH,
			fetched_at: new Date(now.getTime() - MARINE_STALE_AFTER_MS).toISOString()
		};
		expect(marineByHour([edge], now).size).toBe(1);
	});
	it('skips rows without values and unparseable timestamps', () => {
		const empty = { ...MARINE_FRESH, wave_height_m: null, wave_period_s: null, wave_dir_deg: null };
		expect(marineByHour([empty], now).size).toBe(0);
		expect(marineByHour([{ ...MARINE_FRESH, valid_at: 'nope' }], now).size).toBe(0);
		expect(marineByHour([{ ...MARINE_FRESH, fetched_at: 'nope' }], now).size).toBe(0);
	});
	it('later rows overwrite earlier ones; empty input gives an empty map', () => {
		const later = { ...MARINE_FRESH, wave_height_m: 2 };
		expect(marineByHour([MARINE_FRESH, later], now).get(Date.parse(MARINE_FRESH.valid_at))).toBe(later);
		expect(marineByHour([], now).size).toBe(0);
	});
});
