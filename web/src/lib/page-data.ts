import {
	getEvaluations,
	getMarineHours,
	getSpot,
	getSpotSummaries,
	getTideExtremes,
	listSpots
} from '#lib/data.js';
import { addDaysToKey, floorHour, localDateKey, startOfLocalDay } from './time.js';
import type { Evaluation, MarineHour, Spot, SpotSummary, TideExtreme } from './types.js';

// Pure helpers live in view.ts so page tests need no Supabase client (review N-2).
export { RESUME_REFRESH_MS, shouldRefreshOnResume } from './view.js';

export const SPOT_PAGE_DAYS = 8; // today + 7

export type SpotListData =
	| { kind: 'ok'; now: string; spots: Spot[]; summaries: Record<string, SpotSummary> }
	| { kind: 'error'; now: string };

export type SpotPageData =
	| {
			kind: 'ok';
			now: string;
			spot: Spot;
			evaluations: Evaluation[];
			tides: TideExtreme[];
			marine: MarineHour[];
	  }
	| { kind: 'not_found'; now: string; id: string }
	| { kind: 'error'; now: string; id: string };

export async function loadSpotList(now: Date): Promise<SpotListData> {
	try {
		const [spots, summaries] = await Promise.all([listSpots(), getSpotSummaries(now)]);
		return { kind: 'ok', now: now.toISOString(), spots, summaries };
	} catch {
		console.warn('spot list load failed');
		return { kind: 'error', now: now.toISOString() };
	}
}

/** Waves are optional: a failing query gives [] and one console.warn without details (A11). */
async function loadMarine(spotId: string, from: Date, to: Date): Promise<MarineHour[]> {
	try {
		return await getMarineHours(spotId, from, to);
	} catch {
		console.warn('wave data load failed');
		return [];
	}
}

export async function loadSpotPage(id: string, now: Date): Promise<SpotPageData> {
	try {
		const spot = await getSpot(id);
		if (spot === null) return { kind: 'not_found', now: now.toISOString(), id };
		const todayKey = localDateKey(now);
		const end = startOfLocalDay(addDaysToKey(todayKey, SPOT_PAGE_DAYS));
		const station = spot.rws_station?.trim() || null;
		const hasCoords = spot.lat !== null && spot.lon !== null;
		const [evaluations, tides, marine] = await Promise.all([
			getEvaluations(spot.id, floorHour(now), end),
			station ? getTideExtremes(station, startOfLocalDay(todayKey), end) : Promise.resolve([]),
			hasCoords ? loadMarine(spot.id, floorHour(now), end) : Promise.resolve([])
		]);
		return { kind: 'ok', now: now.toISOString(), spot, evaluations, tides, marine };
	} catch {
		console.warn('spot page load failed');
		return { kind: 'error', now: now.toISOString(), id };
	}
}
