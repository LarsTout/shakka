import { supabase } from '#lib/supabase.js';
import { addDaysToKey, floorHour, localDateKey, startOfLocalDay } from './time.js';
import {
	EVALUATION_COLUMNS,
	MARINE_HOUR_COLUMNS,
	SPOT_COLUMNS,
	SUMMARY_COLUMNS,
	TIDE_EXTREME_COLUMNS,
	type Evaluation,
	type MarineHour,
	type Spot,
	type SpotSummary,
	type SummaryRow,
	type TideExtreme
} from './types.js';
import { summarizeSpots } from './view.js';

export const PAGE_SIZE = 1000; // Supabase default max_rows
export const MAX_PAGES = 50;

const SLUG = /^[a-z0-9]+(-[a-z0-9]+)*$/;

/** Only the operation and the error code; never the Supabase message. */
export class DataError extends Error {
	readonly operation: string;
	readonly code: string | null;
	constructor(operation: string, code: string | null) {
		super(`${operation} failed`);
		this.name = 'DataError';
		this.operation = operation;
		this.code = code;
	}
}

interface Rangeable {
	range(
		from: number,
		to: number
	): PromiseLike<{ data: unknown[] | null; error: { code?: string } | null }>;
}

/**
 * Calls build() per page with .range(offset, offset + pageSize - 1) until a page is shorter than
 * pageSize. After maxPages full pages: DataError(operation, 'too_many_rows') without a further request.
 */
export async function fetchAllPages<T>(
	operation: string,
	build: () => Rangeable,
	pageSize: number = PAGE_SIZE,
	maxPages: number = MAX_PAGES
): Promise<T[]> {
	const out: T[] = [];
	for (let page = 0; page < maxPages; page++) {
		const offset = page * pageSize;
		const { data, error } = await build().range(offset, offset + pageSize - 1);
		if (error) throw new DataError(operation, error.code ?? null);
		const rows = (data ?? []) as T[];
		out.push(...rows);
		if (rows.length < pageSize) return out;
	}
	throw new DataError(operation, 'too_many_rows');
}

export function listSpots(): Promise<Spot[]> {
	return fetchAllPages<Spot>('listSpots', () =>
		supabase
			.from('spots')
			.select(SPOT_COLUMNS.join(','))
			.order('name', { ascending: true })
			.order('id', { ascending: true })
	);
}

export async function getSpot(id: string): Promise<Spot | null> {
	if (!SLUG.test(id)) return null;
	const { data, error } = await supabase
		.from('spots')
		.select(SPOT_COLUMNS.join(','))
		.eq('id', id)
		.maybeSingle();
	if (error) throw new DataError('getSpot', error.code ?? null);
	return (data as unknown as Spot | null) ?? null;
}

export function getEvaluations(spotId: string, from: Date, to: Date): Promise<Evaluation[]> {
	return fetchAllPages<Evaluation>('getEvaluations', () =>
		supabase
			.from('evaluations')
			.select(EVALUATION_COLUMNS.join(','))
			.eq('spot_id', spotId)
			.gte('valid_at', from.toISOString())
			.lt('valid_at', to.toISOString())
			.order('valid_at', { ascending: true })
	);
}

export async function getTideExtremes(station: string, from: Date, to: Date): Promise<TideExtreme[]> {
	const s = station.trim();
	if (s === '') return [];
	return fetchAllPages<TideExtreme>('getTideExtremes', () =>
		supabase
			.from('tide_extremes')
			.select(TIDE_EXTREME_COLUMNS.join(','))
			.eq('station', s)
			.gte('at', from.toISOString())
			.lt('at', to.toISOString())
			.order('at', { ascending: true })
	);
}

export async function getSpotSummaries(now: Date): Promise<Record<string, SpotSummary>> {
	const todayKey = localDateKey(now);
	const rows = await fetchAllPages<SummaryRow>('getSpotSummaries', () =>
		supabase
			.from('evaluations')
			.select(SUMMARY_COLUMNS.join(','))
			.gte('valid_at', floorHour(now).toISOString())
			.lt('valid_at', startOfLocalDay(addDaysToKey(todayKey, 2)).toISOString())
			.not('reasons', 'cs', '{dark}')
			.order('spot_id', { ascending: true })
			.order('valid_at', { ascending: true })
	);
	return summarizeSpots(rows, now);
}

export function getMarineHours(spotId: string, from: Date, to: Date): Promise<MarineHour[]> {
	return fetchAllPages<MarineHour>('getMarineHours', () =>
		supabase
			.from('marine_hours')
			.select(MARINE_HOUR_COLUMNS.join(','))
			.eq('spot_id', spotId)
			.gte('valid_at', from.toISOString())
			.lt('valid_at', to.toISOString())
			.order('valid_at', { ascending: true })
	);
}
