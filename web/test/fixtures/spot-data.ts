import type { Evaluation, MarineHour, Spot, TideExtreme } from '../../src/lib/types.js';

// Test data only (never in data/spots.yaml).
export const NOW_FRESH = '2026-07-15T12:30:00.000Z';
export const NOW_STALE = '2026-07-15T15:06:00.000Z';
export const EVALUATED_AT = '2026-07-15T12:05:00+00:00';

export const SPOT_UNVERIFIED: Spot = {
	id: 'test-strand',
	name: 'Teststrand',
	region: 'Testregio',
	lat: 52.47,
	lon: 4.57,
	shore_normal_deg: 270,
	ridable_dirs: null,
	hazards: 'Testgevaar: zandbank\nTweede regel',
	tide_sensitive: 'prefer_low',
	tide_min_level_cm: null,
	rws_station: ' teststation ',
	season: [{ start: '05-01', end: '09-30', from_time: '10:00', to_time: '18:00', note: null }],
	status: null,
	level: null,
	default_min_kn: null,
	notes: null,
	verified: false,
	updated_at: '2026-07-01T00:00:00+00:00'
};

export const SPOT_VERIFIED: Spot = {
	...SPOT_UNVERIFIED,
	id: 'test-meer',
	name: 'Testmeer',
	verified: true,
	status: 'allowed',
	rws_station: null,
	tide_sensitive: 'none',
	season: [],
	hazards: null,
	notes: 'Testnotitie'
};

const base = { spot_id: 'test-strand', tide_level_cm: null, evaluated_at: EVALUATED_AT } as const;

export const EVAL_GO: Evaluation = {
	...base,
	valid_at: '2026-07-15T12:00:00+00:00',
	verdict: 'go',
	reasons: [],
	wind_kn: 18.4,
	gust_kn: 23.6,
	dir_deg: 250,
	dir_class: 'onshore',
	confidence: 'high'
};
export const EVAL_OFFSHORE: Evaluation = {
	...base,
	valid_at: '2026-07-15T13:00:00+00:00',
	verdict: 'no_go',
	reasons: ['offshore'],
	wind_kn: 15.2,
	gust_kn: 19.8,
	dir_deg: 90,
	dir_class: 'offshore',
	confidence: 'medium'
};
export const EVAL_LOWCONF: Evaluation = {
	...base,
	valid_at: '2026-07-15T14:00:00+00:00',
	verdict: 'marginal',
	reasons: ['low_confidence'],
	wind_kn: 14.0,
	gust_kn: null,
	dir_deg: 300,
	dir_class: 'side_onshore',
	confidence: 'low'
};
export const EVAL_DARK: Evaluation = {
	...base,
	valid_at: '2026-07-15T21:00:00+00:00',
	verdict: 'no_go',
	reasons: ['dark'],
	wind_kn: 10.0,
	gust_kn: 14.0,
	dir_deg: 260,
	dir_class: 'onshore',
	confidence: 'high'
};
export const EVAL_TOMORROW: Evaluation = {
	...base,
	valid_at: '2026-07-16T08:00:00+00:00',
	verdict: 'go',
	reasons: [],
	wind_kn: 17.0,
	gust_kn: 21.0,
	dir_deg: 255,
	dir_class: 'onshore',
	confidence: 'high'
};

export const TIDES: TideExtreme[] = [
	{ station: 'teststation', at: '2026-07-15T09:10:00+00:00', kind: 'high', level_cm: 95 },
	{ station: 'teststation', at: '2026-07-15T15:40:00+00:00', kind: 'low', level_cm: -70 }
];

export const MARINE_FRESH: MarineHour = {
	spot_id: 'test-strand',
	valid_at: '2026-07-15T12:00:00+00:00',
	wave_height_m: 1.24,
	wave_period_s: 5.4,
	wave_dir_deg: 250,
	fetched_at: '2026-07-15T12:05:00+00:00'
};
// NOW_FRESH is 12:30Z: this row is 3 hours and 1 minute old.
export const MARINE_STALE: MarineHour = {
	...MARINE_FRESH,
	valid_at: '2026-07-15T12:00:00+00:00',
	fetched_at: '2026-07-15T09:29:00+00:00'
};

export function pageData(overrides: Record<string, unknown> = {}) {
	return {
		kind: 'ok' as const,
		now: NOW_FRESH,
		spot: SPOT_UNVERIFIED,
		evaluations: [EVAL_GO, EVAL_OFFSHORE, EVAL_LOWCONF, EVAL_DARK, EVAL_TOMORROW],
		tides: TIDES,
		marine: [] as MarineHour[],
		...overrides
	};
}

// Exact strings from WP-08 (ingest/tests/message_fixtures.py).
export const GO_URL_SUMMER =
	'https://example.org/go?spot=test-strand&start=2026-07-18T12%3A00%3A00Z&end=2026-07-18T16%3A00%3A00Z';
export const GO_URL_WINTER =
	'https://example.org/go?spot=test-strand&start=2026-11-07T11%3A00%3A00Z&end=2026-11-07T14%3A00%3A00Z';
