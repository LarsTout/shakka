// @vitest-environment node
import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';
import {
	COMPASS_POINTS_NL,
	STATUS_UNKNOWN_NL,
	compassLabel,
	directionText,
	formatKn,
	formatLevelCm,
	seasonText,
	statusLabel,
	tideText,
	verdictLabel,
	windText
} from '../src/lib/labels.js';
import { SPOT_UNVERIFIED, TIDES } from './fixtures/spot-data.js';

describe('compassLabel', () => {
	it.each([
		[0, 'N'],
		[11.24, 'N'],
		[11.25, 'NNO'],
		[250, 'WZW'],
		[359, 'N'],
		[360, 'N'],
		[-10, 'N']
	])('%s -> %s', (deg, label) => expect(compassLabel(deg)).toBe(label));

	it('matches the Python tuple', () => {
		const py = readFileSync(
			new URL('../../ingest/src/shakka/domain/direction.py', import.meta.url),
			'utf8'
		);
		const m = /COMPASS_POINTS_NL[^=]*=\s*\(([\s\S]*?)\)/.exec(py);
		expect(m).not.toBeNull();
		const tuple = [...m![1]!.matchAll(/"([^"]+)"/g)].map((x) => x[1]);
		expect([...COMPASS_POINTS_NL]).toEqual(tuple);
	});
});

describe('formatting', () => {
	it('formatKn', () => {
		expect(formatKn(18.4)).toBe('18');
		expect(formatKn(18.5)).toBe('19');
		expect(formatKn(0)).toBe('0');
	});
	it('formatLevelCm', () => {
		expect(formatLevelCm(0)).toBe('0');
		expect(formatLevelCm(95)).toBe('+95');
		expect(formatLevelCm(-70)).toBe('-70');
	});
	it('windText', () => {
		expect(windText(18.4, 23.6)).toBe('18 kn, vlagen 24 kn');
		expect(windText(14, null)).toBe('14 kn, vlagen onbekend');
		expect(windText(null, 20)).toBe('Wind onbekend');
		expect(windText(0, 3)).toBe('0 kn, vlagen 3 kn');
	});
	it('directionText', () => {
		expect(directionText(250)).toBe('Wind uit WZW (250°)');
		expect(directionText(null)).toBe('Richting onbekend');
	});
	it('seasonText', () => {
		expect(seasonText(SPOT_UNVERIFIED.season[0]!)).toBe('1 mei t/m 30 sep, 10:00–18:00');
		expect(seasonText({ start: '05-01', end: '09-30', from_time: null, to_time: null, note: null })).toBe(
			'1 mei t/m 30 sep'
		);
		expect(
			seasonText({ start: '11-01', end: '02-28', from_time: null, to_time: null, note: 'winter' })
		).toBe('1 nov t/m 28 feb (winter)');
		expect(seasonText({ start: 'xx', end: '09-30', from_time: null, to_time: null, note: null })).toContain(
			'xx'
		);
	});
	it('tideText', () => {
		expect(tideText(TIDES[0]!)).toBe('Hoogwater 11:10 (+95 cm)');
		expect(tideText(TIDES[1]!)).toBe('Laagwater 17:40 (-70 cm)');
	});
	it('status and verdict labels', () => {
		expect(statusLabel(null)).toBe(STATUS_UNKNOWN_NL);
		expect(statusLabel('allowed')).toBe('Toegestaan');
		expect(verdictLabel('no_go')).toBe('Niet gaan');
		expect(verdictLabel('go')).toBe('Go');
		expect(verdictLabel('marginal')).toBe('Twijfel');
	});
});
