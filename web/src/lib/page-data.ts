import { getEvaluations, getSpot, getSpotSummaries, getTideExtremes, listSpots } from '#lib/data.js';
import { addDaysToKey, floorHour, localDateKey, startOfLocalDay } from './time.js';
import type { Evaluation, Spot, SpotSummary, TideExtreme } from './types.js';

// Pure helpers live in view.ts so page tests need no Supabase client (review N-2).
export { RESUME_REFRESH_MS, shouldRefreshOnResume } from './view.js';

export const SPOT_PAGE_DAYS = 8; // today + 7

export type SpotListData =
	| { kind: 'ok'; now: string; spots: Spot[]; summaries: Record<string, SpotSummary> }
	| { kind: 'error'; now: string };

export type SpotPageData =
	| { kind: 'ok'; now: string; spot: Spot; evaluations: Evaluation[]; tides: TideExtreme[] }
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

export async function loadSpotPage(id: string, now: Date): Promise<SpotPageData> {
	try {
		const spot = await getSpot(id);
		if (spot === null) return { kind: 'not_found', now: now.toISOString(), id };
		const todayKey = localDateKey(now);
		const end = startOfLocalDay(addDaysToKey(todayKey, SPOT_PAGE_DAYS));
		const station = spot.rws_station?.trim() || null;
		const [evaluations, tides] = await Promise.all([
			getEvaluations(spot.id, floorHour(now), end),
			station ? getTideExtremes(station, startOfLocalDay(todayKey), end) : Promise.resolve([])
		]);
		return { kind: 'ok', now: now.toISOString(), spot, evaluations, tides };
	} catch {
		console.warn('spot page load failed');
		return { kind: 'error', now: now.toISOString(), id };
	}
}
