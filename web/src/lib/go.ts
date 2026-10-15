import type { Evaluation } from './types.js';
import { isSpotSlug, parseGoParams, type GoParams } from './time.js';

export const GO_RUN_MIN_HOURS = 1; // A10
const HOUR_MS = 3_600_000;

/** [start, end), end = last go hour + 1 h. */
export interface GoRun {
	start: Date;
	end: Date;
}

/**
 * Sorted by valid_at; consecutive 'go' hours exactly one hour apart form one run. Runs shorter
 * than GO_RUN_MIN_HOURS are dropped. Non-go hours (also 'dark') break a run.
 */
export function goRuns(hours: readonly Evaluation[]): GoRun[] {
	const sorted = [...hours].sort(
		(a, b) => new Date(a.valid_at).getTime() - new Date(b.valid_at).getTime()
	);
	const runs: GoRun[] = [];
	let current: { start: number; end: number } | null = null;
	const flush = () => {
		if (current && (current.end - current.start) / HOUR_MS >= GO_RUN_MIN_HOURS) {
			runs.push({ start: new Date(current.start), end: new Date(current.end) });
		}
		current = null;
	};
	for (const h of sorted) {
		const t = new Date(h.valid_at).getTime();
		if (h.verdict !== 'go') {
			flush();
			continue;
		}
		if (current && t === current.end) {
			current.end = t + HOUR_MS;
		} else {
			flush();
			current = { start: t, end: t + HOUR_MS };
		}
	}
	flush();
	return runs;
}

/** 'YYYY-MM-DDTHH:MM:SSZ' (toISOString without milliseconds), as WP-08 iso(). */
export function isoHour(d: Date): string {
	return d.toISOString().replace('.000Z', 'Z');
}

function goQuery(spotId: string, start: Date, end: Date): string {
	const enc = encodeURIComponent;
	return `?spot=${enc(spotId)}&start=${enc(isoHour(start))}&end=${enc(isoHour(end))}`;
}

/** `/go?spot=..&start=..&end=..` (':' -> '%3A', equal to WP-08 build_go_url without the base). */
export function goHref(spotId: string, start: Date, end: Date): string {
	return `/go${goQuery(spotId, start, end)}`;
}

/** Same query on /sessie/nieuw. */
export function newSessionHref(p: GoParams): string {
	return `/sessie/nieuw${goQuery(p.spot, p.start, p.end)}`;
}

export interface NewSessionParams {
	spot: string | null;
	start: string | null; // ISO strings
	end: string | null;
}

/** parseGoParams ok -> all three; else a valid spot param -> spot only; else all null. */
export function parseNewSessionParams(url: URL): NewSessionParams {
	const p = parseGoParams(url);
	if (p) return { spot: p.spot, start: p.start.toISOString(), end: p.end.toISOString() };
	const spot = url.searchParams.get('spot');
	if (spot !== null && isSpotSlug(spot)) return { spot, start: null, end: null };
	return { spot: null, start: null, end: null };
}
