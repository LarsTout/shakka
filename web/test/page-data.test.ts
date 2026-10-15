import { beforeEach, describe, expect, it, vi } from 'vitest';
import { MARINE_FRESH, NOW_FRESH, SPOT_UNVERIFIED, SPOT_VERIFIED } from './fixtures/spot-data.js';

const data = vi.hoisted(() => ({
	listSpots: vi.fn(),
	getSpot: vi.fn(),
	getEvaluations: vi.fn(),
	getTideExtremes: vi.fn(),
	getMarineHours: vi.fn(),
	getSpotSummaries: vi.fn()
}));
vi.mock('#lib/data.js', () => data);

import { loadSpotList, loadSpotPage, shouldRefreshOnResume } from '../src/lib/page-data.js';

const now = new Date(NOW_FRESH);
let warn: ReturnType<typeof vi.spyOn>;

beforeEach(() => {
	vi.clearAllMocks();
	data.getMarineHours.mockResolvedValue([]);
	warn = vi.spyOn(console, 'warn').mockImplementation(() => {});
});

describe('loadSpotPage', () => {
	it('loads evaluations and tides for a spot with a station', async () => {
		data.getSpot.mockResolvedValue(SPOT_UNVERIFIED);
		data.getEvaluations.mockResolvedValue([]);
		data.getTideExtremes.mockResolvedValue([]);
		const res = await loadSpotPage('test-strand', now);
		expect(res.kind).toBe('ok');
		expect(res.now).toBe(NOW_FRESH);
		expect(data.getEvaluations).toHaveBeenCalledWith(
			'test-strand',
			new Date('2026-07-15T12:00:00Z'),
			new Date('2026-07-22T22:00:00Z')
		);
		expect(data.getTideExtremes).toHaveBeenCalledWith(
			'teststation',
			new Date('2026-07-14T22:00:00Z'),
			new Date('2026-07-22T22:00:00Z')
		);
	});
	it('skips tides without a station', async () => {
		data.getSpot.mockResolvedValue(SPOT_VERIFIED);
		data.getEvaluations.mockResolvedValue([]);
		const res = await loadSpotPage('test-meer', now);
		expect(data.getTideExtremes).not.toHaveBeenCalled();
		expect(res.kind === 'ok' && res.tides).toEqual([]);
	});
	it('not_found', async () => {
		data.getSpot.mockResolvedValue(null);
		expect((await loadSpotPage('nope', now)).kind).toBe('not_found');
	});
	it('error without leaking the message', async () => {
		data.getSpot.mockResolvedValue(SPOT_VERIFIED);
		data.getEvaluations.mockRejectedValue(new Error('secret detail'));
		const res = await loadSpotPage('test-meer', now);
		expect(res.kind).toBe('error');
		expect(warn).toHaveBeenCalledTimes(1);
		expect(JSON.stringify(warn.mock.calls)).not.toContain('secret detail');
		expect(JSON.stringify(warn.mock.calls)).not.toContain('test-meer');
	});
});

describe('loadSpotPage waves (WP-12)', () => {
	it('loads marine hours for the same window as the evaluations', async () => {
		data.getSpot.mockResolvedValue(SPOT_UNVERIFIED);
		data.getEvaluations.mockResolvedValue([]);
		data.getTideExtremes.mockResolvedValue([]);
		data.getMarineHours.mockResolvedValue([MARINE_FRESH]);
		const res = await loadSpotPage('test-strand', now);
		expect(data.getMarineHours).toHaveBeenCalledWith(
			'test-strand',
			new Date('2026-07-15T12:00:00Z'),
			new Date('2026-07-22T22:00:00Z')
		);
		expect(res.kind === 'ok' && res.marine).toEqual([MARINE_FRESH]);
	});
	it('no coordinates: no wave query', async () => {
		data.getSpot.mockResolvedValue({ ...SPOT_UNVERIFIED, lat: null, lon: null });
		data.getEvaluations.mockResolvedValue([]);
		data.getTideExtremes.mockResolvedValue([]);
		const res = await loadSpotPage('test-strand', now);
		expect(data.getMarineHours).not.toHaveBeenCalled();
		expect(res.kind === 'ok' && res.marine).toEqual([]);
	});
	it('a failing wave query does not break the page', async () => {
		data.getSpot.mockResolvedValue(SPOT_UNVERIFIED);
		data.getEvaluations.mockResolvedValue([]);
		data.getTideExtremes.mockResolvedValue([]);
		data.getMarineHours.mockRejectedValue(new Error('secret detail'));
		const res = await loadSpotPage('test-strand', now);
		expect(res.kind).toBe('ok');
		expect(res.kind === 'ok' && res.marine).toEqual([]);
		expect(warn).toHaveBeenCalledTimes(1);
		const logged = JSON.stringify(warn.mock.calls);
		expect(logged).not.toContain('secret detail');
		expect(logged).not.toContain('test-strand');
	});
});

describe('loadSpotList', () => {
	it('ok', async () => {
		data.listSpots.mockResolvedValue([SPOT_UNVERIFIED]);
		data.getSpotSummaries.mockResolvedValue({});
		expect(await loadSpotList(now)).toEqual({
			kind: 'ok',
			now: NOW_FRESH,
			spots: [SPOT_UNVERIFIED],
			summaries: {}
		});
		expect(data.getSpotSummaries).toHaveBeenCalledWith(now);
	});
	it('error', async () => {
		data.listSpots.mockRejectedValue(new Error('secret detail'));
		data.getSpotSummaries.mockResolvedValue({});
		expect(await loadSpotList(now)).toEqual({ kind: 'error', now: NOW_FRESH });
		expect(warn).toHaveBeenCalledTimes(1);
		expect(JSON.stringify(warn.mock.calls)).not.toContain('secret detail');
	});
});

describe('shouldRefreshOnResume', () => {
	it('boundary', () => {
		const t = Date.parse(NOW_FRESH);
		expect(shouldRefreshOnResume(NOW_FRESH, t + 600_000)).toBe(false);
		expect(shouldRefreshOnResume(NOW_FRESH, t + 600_001)).toBe(true);
	});
});
