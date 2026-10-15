import type { Spot, SpotSummary } from '../../src/lib/types.js';
import { EVALUATED_AT, NOW_FRESH, SPOT_UNVERIFIED, SPOT_VERIFIED } from './spot-data.js';

// Test data only (never in data/spots.yaml).
export const SPOT_NO_COORDS: Spot = { ...SPOT_VERIFIED, id: 'test-zonder', name: 'Testzonder', lat: null, lon: null };
export const SPOT_EVENING: Spot = { ...SPOT_VERIFIED, id: 'test-avond', name: 'Testavond', lat: 52.1, lon: 4.2 };

export const SUMMARY_GO: SpotSummary = {
	spot_id: 'test-meer',
	today: { date: '2026-07-15', go: 2, marginal: 1, no_go: 0, best: 'go', first_go_at: '2026-07-15T12:00:00+00:00' },
	tomorrow: { date: '2026-07-16', go: 0, marginal: 0, no_go: 1, best: 'no_go', first_go_at: null },
	latest_evaluated_at: EVALUATED_AT
};
export const SUMMARY_TOMORROW: SpotSummary = {
	spot_id: 'test-avond',
	today: { date: '2026-07-15', go: 0, marginal: 0, no_go: 0, best: null, first_go_at: null },
	tomorrow: { date: '2026-07-16', go: 0, marginal: 2, no_go: 0, best: 'marginal', first_go_at: null },
	latest_evaluated_at: EVALUATED_AT
};

export const MAP_SPOTS: Spot[] = [SPOT_UNVERIFIED, SPOT_VERIFIED, SPOT_EVENING, SPOT_NO_COORDS];
export const MAP_SUMMARIES: Record<string, SpotSummary> = { 'test-meer': SUMMARY_GO, 'test-avond': SUMMARY_TOMORROW };
export function homeData(overrides: Record<string, unknown> = {}) {
	return { kind: 'ok' as const, now: NOW_FRESH, spots: MAP_SPOTS, summaries: MAP_SUMMARIES, ...overrides };
}
