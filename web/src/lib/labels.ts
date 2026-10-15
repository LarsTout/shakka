import { MONTH_ABBR_NL, formatLocal } from './time.js';
import type {
	RuleSource,
	SeasonClosure,
	SpotLevel,
	SpotStatus,
	TideExtreme,
	TideKind,
	TideSensitivity,
	Verdict
} from './types.js';

export const VERDICT_LABEL_NL: Record<Verdict, string> = {
	go: 'Go',
	marginal: 'Twijfel',
	no_go: 'Niet gaan'
};
export const STATUS_LABEL_NL: Record<SpotStatus, string> = {
	allowed: 'Toegestaan',
	limited: 'Beperkt toegestaan',
	forbidden: 'Verboden'
};
export const STATUS_UNKNOWN_NL = 'Onbekend (nog niet ingevuld)';
export const TIDE_SENSITIVITY_LABEL_NL: Record<TideSensitivity, string> = {
	none: 'Geen voorkeur',
	prefer_low: 'Voorkeur laagwater',
	prefer_high: 'Voorkeur hoogwater',
	avoid_low: 'Liever geen laagwater'
};
export const TIDE_KIND_LABEL_NL: Record<TideKind, string> = {
	high: 'Hoogwater',
	low: 'Laagwater'
};
export const LEVEL_LABEL_NL: Record<SpotLevel, string> = {
	beginner: 'Beginner',
	intermediate: 'Gemiddeld',
	advanced: 'Gevorderd'
};
export const SOURCE_LABEL_NL: Record<RuleSource, string> = {
	rule: 'je instelling voor deze spot',
	profile: 'je profiel',
	spot: 'spotprofiel',
	system: 'Shakka'
};
export const NOT_FILLED_NL = 'Niet ingevuld';
export const COMPASS_POINTS_NL = [
	'N',
	'NNO',
	'NO',
	'ONO',
	'O',
	'OZO',
	'ZO',
	'ZZO',
	'Z',
	'ZZW',
	'ZW',
	'WZW',
	'W',
	'WNW',
	'NW',
	'NNW'
] as const;

export function verdictLabel(v: Verdict): string {
	return VERDICT_LABEL_NL[v];
}

export function statusLabel(s: SpotStatus | null): string {
	return s === null ? STATUS_UNKNOWN_NL : STATUS_LABEL_NL[s];
}

/** Same formula as Python compass_label. */
export function compassLabel(deg: number): string {
	return COMPASS_POINTS_NL[Math.floor(((((deg % 360) + 360) % 360) + 11.25) / 22.5) % 16]!;
}

/** Math.floor(x + 0.5) as string (same as WP-08 _kn). */
export function formatKn(x: number): string {
	return String(Math.floor(x + 0.5));
}

/** 0 -> '0', otherwise with sign: '+95', '-70'. */
export function formatLevelCm(cm: number): string {
	if (cm === 0) return '0';
	return cm > 0 ? `+${cm}` : `-${Math.abs(cm)}`;
}

export function windText(windKn: number | null, gustKn: number | null): string {
	if (windKn === null) return 'Wind onbekend';
	const gust = gustKn === null ? 'onbekend' : `${formatKn(gustKn)} kn`;
	return `${formatKn(windKn)} kn, vlagen ${gust}`;
}

export function directionText(deg: number | null): string {
	return deg === null ? 'Richting onbekend' : `Wind uit ${compassLabel(deg)} (${Math.round(deg)}°)`;
}

function monthDay(mmdd: string): string {
	const m = /^(\d{2})-(\d{2})$/.exec(mmdd);
	if (!m) return mmdd;
	const month = Number(m[1]);
	if (month < 1 || month > 12) return mmdd;
	return `${Number(m[2])} ${MONTH_ABBR_NL[month - 1]}`;
}

export function seasonText(c: SeasonClosure): string {
	let out = `${monthDay(c.start)} t/m ${monthDay(c.end)}`;
	if (c.from_time && c.to_time) out += `, ${c.from_time}–${c.to_time}`;
	if (c.note) out += ` (${c.note})`;
	return out;
}

export function tideText(t: TideExtreme): string {
	return `${TIDE_KIND_LABEL_NL[t.kind]} ${formatLocal(new Date(t.at), 'time')} (${formatLevelCm(t.level_cm)} cm)`;
}

/** 0 -> 'alleen vandaag', 1 -> 'vandaag plus 1 dag', n -> `vandaag plus ${n} dagen`. */
export function daysAheadText(n: number): string {
	if (n === 0) return 'alleen vandaag';
	return n === 1 ? 'vandaag plus 1 dag' : `vandaag plus ${n} dagen`;
}
