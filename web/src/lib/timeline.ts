import { addDaysToKey, formatDateKey, formatLocal, localDateKey, localParts } from './time.js';
import type { Evaluation, ReasonCode, TideExtreme, Verdict } from './types.js';

export const HOUR_MS = 3_600_000;
export type SlotKind = Verdict | 'none' | 'outside' | 'quiet' | 'free';
export type TimelineHour = Pick<Evaluation, 'valid_at' | 'verdict'> & {
	reasons?: readonly ReasonCode[];
};
export interface TimelineTick {
	pos: number;
	label: string;
}
export interface TimelineMarker {
	pos: number;
	label: string;
	kind: 'low' | 'high' | 'now';
	row: 0 | 1;
}
export interface Timeline {
	slots: SlotKind[];
	ticks: TimelineTick[];
	markers: TimelineMarker[];
	window: { from: number; to: number } | null;
}

const pad2 = (n: number): string => String(n).padStart(2, '0');

/** Hours whose local date (Europe/Amsterdam) is dateKey. */
export function hoursOnDay<T extends Pick<Evaluation, 'valid_at'>>(
	hours: readonly T[],
	dateKey: string
): T[] {
	return hours.filter((h) => localDateKey(new Date(h.valid_at)) === dateKey);
}

/** 'Vandaag' | 'Morgen' | formatDateKey(dateKey, 'day'). */
export function dayTabLabel(dateKey: string, todayKey: string): string {
	if (dateKey === todayKey) return 'Vandaag';
	if (dateKey === addDaysToKey(todayKey, 1)) return 'Morgen';
	return formatDateKey(dateKey, 'day');
}

/** Daylight hours of one day on an axis from the first to the last daylight hour + 1 h. */
export function dayTimeline(
	hours: readonly TimelineHour[],
	opts: { tides?: readonly TideExtreme[]; now?: Date } = {}
): Timeline | null {
	const byTime = new Map<number, Verdict>();
	for (const h of hours) {
		if (h.reasons?.includes('dark')) continue;
		const t = Date.parse(h.valid_at);
		if (!Number.isNaN(t)) byTime.set(t, h.verdict);
	}
	if (byTime.size === 0) return null;
	const times = [...byTime.keys()];
	const first = Math.min(...times);
	const last = Math.max(...times);
	const n = Math.round((last - first) / HOUR_MS) + 1;

	const slots: SlotKind[] = [];
	for (let i = 0; i < n; i++) slots.push(byTime.get(first + i * HOUR_MS) ?? 'none');

	const ticks: TimelineTick[] = [];
	for (let i = 0; i <= n; i++) {
		const p = localParts(new Date(first + i * HOUR_MS));
		if (p.minute === 0 && p.hour % 3 === 0) ticks.push({ pos: i / n, label: pad2(p.hour) });
	}

	const raw: Omit<TimelineMarker, 'row'>[] = [];
	const posOf = (t: number): number => (t - first) / (n * HOUR_MS);
	for (const td of opts.tides ?? []) {
		const t = Date.parse(td.at);
		if (Number.isNaN(t)) continue;
		const pos = posOf(t);
		if (pos < 0 || pos > 1) continue;
		const time = formatLocal(new Date(t), 'time');
		raw.push(
			td.kind === 'low'
				? { pos, label: `LW ${time}`, kind: 'low' }
				: { pos, label: `HW ${time}`, kind: 'high' }
		);
	}
	if (opts.now) {
		const pos = posOf(opts.now.getTime());
		if (pos >= 0 && pos <= 1) raw.push({ pos, label: 'nu', kind: 'now' });
	}
	raw.sort((a, b) => a.pos - b.pos);
	const markers: TimelineMarker[] = [];
	let lastRow0 = -Infinity;
	for (const m of raw) {
		if (m.pos - lastRow0 < 0.2) {
			markers.push({ ...m, row: 1 });
		} else {
			markers.push({ ...m, row: 0 });
			lastRow0 = m.pos;
		}
	}
	return { slots, ticks, markers, window: null };
}

/** Session window on its local day, on an axis of at least 06 to 22. */
export function sessionTimeline(
	evaluations: readonly TimelineHour[],
	startsAt: string,
	endsAt: string
): Timeline | null {
	const start = new Date(startsAt);
	const end = new Date(endsAt);
	if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime())) return null;
	const sp = localParts(start);
	const ep = localParts(end);
	const startKey = localDateKey(start);
	const endKey = localDateKey(end);
	const startH = sp.hour + sp.minute / 60;
	let endH: number;
	if (endKey === startKey) endH = ep.hour + ep.minute / 60;
	else if (endKey === addDaysToKey(startKey, 1) && ep.hour === 0 && ep.minute === 0) endH = 24;
	else return null;
	if (endH <= startH) return null;

	const from = Math.min(6, Math.floor(startH));
	const to = Math.max(22, Math.ceil(endH));
	const n = to - from;

	const byHour = new Map<number, Verdict>();
	for (const e of evaluations) {
		const d = new Date(e.valid_at);
		if (Number.isNaN(d.getTime()) || localDateKey(d) !== startKey) continue;
		byHour.set(localParts(d).hour, e.verdict);
	}
	const slots: SlotKind[] = [];
	for (let h = from; h < to; h++) {
		slots.push(h + 1 > startH && h < endH ? (byHour.get(h) ?? 'none') : 'outside');
	}
	const ticks: TimelineTick[] = [];
	for (let h = from; h <= to; h++) {
		if (h % 3 === 0) ticks.push({ pos: (h - from) / n, label: pad2(h) });
	}
	return {
		slots,
		ticks,
		markers: [],
		window: { from: (startH - from) / n, to: (endH - from) / n }
	};
}

function toMinutes(value: string | null): number | null {
	if (value === null) return null;
	const m = /^([01]\d|2[0-3]):([0-5]\d)(?::[0-5]\d)?$/.exec(value);
	return m ? Number(m[1]) * 60 + Number(m[2]) : null;
}

/** 24 slots for local hours 0..23: 'quiet' inside [from, until), wrapping past midnight. */
export function quietTimeline(quietFrom: string | null, quietUntil: string | null): Timeline | null {
	const from = toMinutes(quietFrom);
	const until = toMinutes(quietUntil);
	if (from === null || until === null || from === until) return null;
	const slots: SlotKind[] = [];
	for (let h = 0; h < 24; h++) {
		const m = h * 60;
		const quiet = from < until ? m >= from && m < until : m >= from || m < until;
		slots.push(quiet ? 'quiet' : 'free');
	}
	const ticks = [0, 6, 12, 18, 24].map((h) => ({ pos: h / 24, label: pad2(h) }));
	return { slots, ticks, markers: [], window: null };
}
