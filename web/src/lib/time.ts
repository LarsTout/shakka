export const LOCAL_TZ = 'Europe/Amsterdam';
export const WEEKDAY_ABBR_NL = ['ma', 'di', 'wo', 'do', 'vr', 'za', 'zo'] as const; // ISO 1..7
export const WEEKDAY_NL = [
	'maandag',
	'dinsdag',
	'woensdag',
	'donderdag',
	'vrijdag',
	'zaterdag',
	'zondag'
] as const;
export const MONTH_ABBR_NL = [
	'jan',
	'feb',
	'mrt',
	'apr',
	'mei',
	'jun',
	'jul',
	'aug',
	'sep',
	'okt',
	'nov',
	'dec'
] as const;
export const MONTH_NL = [
	'januari',
	'februari',
	'maart',
	'april',
	'mei',
	'juni',
	'juli',
	'augustus',
	'september',
	'oktober',
	'november',
	'december'
] as const;

export type LocalPattern = 'time' | 'day' | 'dayLong' | 'dateTime' | 'dateKey';
export interface LocalParts {
	year: number;
	month: number;
	day: number;
	hour: number;
	minute: number;
	isoWeekday: number;
}

const FORMAT = new Intl.DateTimeFormat('en-GB', {
	timeZone: LOCAL_TZ,
	year: 'numeric',
	month: '2-digit',
	day: '2-digit',
	hour: '2-digit',
	minute: '2-digit',
	hourCycle: 'h23'
});

/** Wall-clock parts in Europe/Amsterdam. RangeError on an invalid Date. */
export function localParts(date: Date): LocalParts {
	if (Number.isNaN(date.getTime())) throw new RangeError('invalid date');
	const p: Record<string, number> = {};
	for (const part of FORMAT.formatToParts(date)) {
		if (part.type !== 'literal') p[part.type] = Number(part.value);
	}
	const year = p.year!;
	const month = p.month!;
	const day = p.day!;
	return {
		year,
		month,
		day,
		hour: p.hour!,
		minute: p.minute!,
		isoWeekday: ((new Date(Date.UTC(year, month - 1, day)).getUTCDay() + 6) % 7) + 1
	};
}

const pad = (n: number, w = 2) => String(n).padStart(w, '0');

export function formatLocal(date: Date, pattern: LocalPattern): string {
	const p = localParts(date);
	const time = `${pad(p.hour)}:${pad(p.minute)}`;
	const wdShort = WEEKDAY_ABBR_NL[p.isoWeekday - 1];
	const day = `${wdShort} ${p.day} ${MONTH_ABBR_NL[p.month - 1]}`;
	switch (pattern) {
		case 'time':
			return time;
		case 'day':
			return day;
		case 'dayLong':
			return `${WEEKDAY_NL[p.isoWeekday - 1]} ${p.day} ${MONTH_NL[p.month - 1]}`;
		case 'dateTime':
			return `${day} ${time}`;
		case 'dateKey':
			return `${pad(p.year, 4)}-${pad(p.month)}-${pad(p.day)}`;
	}
}

export function localDateKey(date: Date): string {
	return formatLocal(date, 'dateKey');
}

function parseKey(key: string): { y: number; m: number; d: number } {
	const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(key);
	if (!match) throw new RangeError(`malformed date key: ${key}`);
	const y = Number(match[1]);
	const m = Number(match[2]);
	const d = Number(match[3]);
	if (new Date(Date.UTC(y, m - 1, d)).toISOString().slice(0, 10) !== key) {
		throw new RangeError(`malformed date key: ${key}`);
	}
	return { y, m, d };
}

/** Calendar arithmetic on 'YYYY-MM-DD' (no time zone involved). */
export function addDaysToKey(key: string, days: number): string {
	const { y, m, d } = parseKey(key);
	return new Date(Date.UTC(y, m - 1, d + days)).toISOString().slice(0, 10);
}

/** UTC instant of local midnight at the start of `key`. */
export function startOfLocalDay(key: string): Date {
	const { y, m, d } = parseKey(key);
	const guess = Date.UTC(y, m - 1, d);
	const off = (t: number): number => {
		const p = localParts(new Date(t));
		return Date.UTC(p.year, p.month - 1, p.day, p.hour, p.minute) - Math.floor(t / 60_000) * 60_000;
	};
	const t1 = guess - off(guess);
	const t2 = guess - off(t1);
	return new Date(off(t1) === off(guess) ? t1 : t2);
}

export function formatDateKey(key: string, pattern: 'day' | 'dayLong'): string {
	const { y, m, d } = parseKey(key);
	const wd = ((new Date(Date.UTC(y, m - 1, d)).getUTCDay() + 6) % 7);
	return pattern === 'day'
		? `${WEEKDAY_ABBR_NL[wd]} ${d} ${MONTH_ABBR_NL[m - 1]}`
		: `${WEEKDAY_NL[wd]} ${d} ${MONTH_NL[m - 1]}`;
}

/** Start of the UTC hour (= a whole local hour in Amsterdam). */
export function floorHour(date: Date): Date {
	return new Date(Math.floor(date.getTime() / 3_600_000) * 3_600_000);
}

export interface GoParams {
	spot: string;
	start: Date;
	end: Date;
}

const SLUG = /^[a-z0-9]+(-[a-z0-9]+)*$/;
const GO_TIME = /^\d{4}-\d{2}-\d{2}T\d{2}:00:00Z$/;
export const MAX_SLUG_LENGTH = 100;

function parseGoTime(value: string): Date | null {
	if (!GO_TIME.test(value)) return null;
	const d = new Date(value);
	if (Number.isNaN(d.getTime())) return null;
	return d.toISOString() === value.replace('Z', '.000Z') ? d : null;
}

/** Parses /go?spot&start&end as produced by WP-08 build_go_url. null when anything is invalid. */
export function parseGoParams(url: URL): GoParams | null {
	const spot = url.searchParams.get('spot');
	const start = url.searchParams.get('start');
	const end = url.searchParams.get('end');
	if (spot === null || start === null || end === null) return null;
	if (!SLUG.test(spot) || spot.length > MAX_SLUG_LENGTH) return null;
	const s = parseGoTime(start);
	const e = parseGoTime(end);
	if (!s || !e || s.getTime() >= e.getTime()) return null;
	return { spot, start: s, end: e };
}
