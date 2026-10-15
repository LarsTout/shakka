import { addDaysToKey, floorHour, formatDateKey, formatLocal, localDateKey, startOfLocalDay } from './time.js';
import type {
	DaySummary,
	Evaluation,
	SpotSummary,
	SummaryRow,
	TideExtreme,
	Verdict
} from './types.js';

export const STALE_AFTER_MS = 3 * 60 * 60 * 1000;
export const RESUME_REFRESH_MS = 10 * 60 * 1000;

/** Max evaluated_at; null for an empty list. */
export function latestEvaluatedAt(rows: ReadonlyArray<Pick<Evaluation, 'evaluated_at'>>): Date | null {
	let max: number | null = null;
	for (const r of rows) {
		const t = Date.parse(r.evaluated_at);
		if (!Number.isNaN(t) && (max === null || t > max)) max = t;
	}
	return max === null ? null : new Date(max);
}

/** Strictly older than 3 hours. */
export function isStale(latest: Date | null, now: Date): boolean {
	return latest !== null && now.getTime() - latest.getTime() > STALE_AFTER_MS;
}

/** nowMs - Date.parse(loadedAtIso) > RESUME_REFRESH_MS */
export function shouldRefreshOnResume(loadedAtIso: string, nowMs: number): boolean {
	return nowMs - Date.parse(loadedAtIso) > RESUME_REFRESH_MS;
}

export function isDark(e: Pick<Evaluation, 'reasons'>): boolean {
	return e.reasons.includes('dark');
}

export interface DayGroup {
	dateKey: string;
	hours: Evaluation[];
}

/** Sorted by valid_at, grouped by local date key, groups in date order. */
export function groupByLocalDay(evals: readonly Evaluation[]): DayGroup[] {
	const sorted = [...evals].sort((a, b) => Date.parse(a.valid_at) - Date.parse(b.valid_at));
	const groups: DayGroup[] = [];
	for (const e of sorted) {
		const key = localDateKey(new Date(e.valid_at));
		const last = groups[groups.length - 1];
		if (last && last.dateKey === key) last.hours.push(e);
		else groups.push({ dateKey: key, hours: [e] });
	}
	return groups;
}

export function visibleHours(hours: readonly Evaluation[], showDark: boolean): Evaluation[] {
	return showDark ? [...hours] : hours.filter((h) => !isDark(h));
}

export function tidesForDay(tides: readonly TideExtreme[], dateKey: string): TideExtreme[] {
	return tides
		.filter((t) => localDateKey(new Date(t.at)) === dateKey)
		.sort((a, b) => Date.parse(a.at) - Date.parse(b.at));
}

export function dayHeading(dateKey: string, todayKey: string): string {
	const label = formatDateKey(dateKey, 'day');
	if (dateKey === todayKey) return `Vandaag (${label})`;
	if (dateKey === addDaysToKey(todayKey, 1)) return `Morgen (${label})`;
	return label;
}

function emptyDay(date: string): DaySummary {
	return { date, go: 0, marginal: 0, no_go: 0, best: null, first_go_at: null };
}

function finishDay(d: DaySummary): void {
	const best: Verdict | null = d.go > 0 ? 'go' : d.marginal > 0 ? 'marginal' : d.no_go > 0 ? 'no_go' : null;
	d.best = best;
}

/** One SpotSummary per spot with at least one daylight row in [floorHour(now), end of tomorrow). */
export function summarizeSpots(rows: readonly SummaryRow[], now: Date): Record<string, SpotSummary> {
	const todayKey = localDateKey(now);
	const tomorrowKey = addDaysToKey(todayKey, 1);
	const from = floorHour(now).getTime();
	const to = startOfLocalDay(addDaysToKey(todayKey, 2)).getTime();
	const out: Record<string, SpotSummary> = {};
	const firstGo: Record<string, number> = {};
	const latest: Record<string, number> = {};
	for (const r of rows) {
		const t = Date.parse(r.valid_at);
		if (Number.isNaN(t) || t < from || t >= to || r.reasons.includes('dark')) continue;
		const key = localDateKey(new Date(t));
		if (key !== todayKey && key !== tomorrowKey) continue;
		const summary = (out[r.spot_id] ??= {
			spot_id: r.spot_id,
			today: emptyDay(todayKey),
			tomorrow: emptyDay(tomorrowKey),
			latest_evaluated_at: r.evaluated_at
		});
		const day = key === todayKey ? summary.today : summary.tomorrow;
		day[r.verdict] += 1;
		if (r.verdict === 'go') {
			const fk = `${r.spot_id}|${key}`;
			if (firstGo[fk] === undefined || t < firstGo[fk]) {
				firstGo[fk] = t;
				day.first_go_at = r.valid_at;
			}
		}
		const ev = Date.parse(r.evaluated_at);
		if (latest[r.spot_id] === undefined || ev > latest[r.spot_id]!) {
			latest[r.spot_id] = ev;
			summary.latest_evaluated_at = r.evaluated_at;
		}
	}
	for (const s of Object.values(out)) {
		finishDay(s.today);
		finishDay(s.tomorrow);
	}
	return out;
}

/** Text after 'Vandaag: ' / 'Morgen: '. */
export function daySummaryText(d: DaySummary, isToday: boolean): string {
	if (d.go + d.marginal + d.no_go === 0) return isToday ? 'geen daglichturen meer' : 'nog geen data';
	if (d.go > 0) {
		const t = d.first_go_at ? formatLocal(new Date(d.first_go_at), 'time') : '';
		return `${d.go} uur go vanaf ${t}` + (d.marginal > 0 ? `, ${d.marginal} uur twijfel` : '');
	}
	if (d.marginal > 0) return `${d.marginal} uur twijfel, geen go`;
	return 'geen go- of twijfeluren';
}

export function latestOfSummaries(s: Record<string, SpotSummary>): Date | null {
	return latestEvaluatedAt(Object.values(s).map((x) => ({ evaluated_at: x.latest_evaluated_at })));
}
