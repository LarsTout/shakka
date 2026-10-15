import type {
	AlertDefaults,
	AlertRuleRow,
	DirClass,
	Profile,
	RuleField,
	RuleSource,
	Spot
} from './types.js';

/** Same table as WP-07 FIELD_SOURCES (highest priority first). */
export const FIELD_SOURCES: Readonly<Record<RuleField, readonly RuleSource[]>> = {
	enabled: ['rule', 'system'],
	min_kn: ['rule', 'profile', 'spot', 'system'],
	max_kn: ['rule', 'profile', 'system'],
	dir_classes: ['rule', 'system'],
	weekdays: ['rule', 'system'],
	earliest_local: ['rule', 'system'],
	latest_local: ['rule', 'system'],
	min_go_hours: ['rule', 'system'],
	days_ahead: ['rule', 'system']
};
/** Postgres `time` allows 24:00:00 (WP-07 END_OF_DAY_TIME_STRINGS). */
export const END_OF_DAY_TIMES: readonly string[] = ['24:00', '24:00:00'];

export interface EffectiveRule {
	enabled: boolean;
	min_kn: number;
	max_kn: number;
	dir_classes: DirClass[]; // in the order of defaults.dir_classes.allowed
	weekdays: number[]; // ascending
	earliest_local: string | null; // 'HH:MM' (see normalizeLocalTime)
	latest_local: string | null;
	min_go_hours: number;
	days_ahead: number;
	sources: Record<RuleField, RuleSource>;
}
export interface RuleConflict {
	min: number;
	minSource: RuleSource;
	max: number;
	maxSource: RuleSource;
}
export type RuleErrorField = RuleField | 'default_min_kn' | 'default_max_kn';

export class RuleError extends Error {
	readonly code: 'conflict' | 'invalid';
	readonly field: RuleErrorField;
	readonly conflict: RuleConflict | null;
	constructor(
		code: 'conflict' | 'invalid',
		field: RuleErrorField,
		message: string,
		conflict: RuleConflict | null = null
	) {
		super(message);
		this.name = 'RuleError';
		this.code = code;
		this.field = field;
		this.conflict = conflict;
	}
}

const TIME_RE = /^([01]\d|2[0-3]):([0-5]\d)(?::([0-5]\d)(?:\.(\d{1,6}))?)?$/;

/**
 * null -> null. '24:00' / '24:00:00': latest_local -> null (no upper bound, WP-07 E36);
 * earliest_local -> RuleError invalid (WP-07 E37). Otherwise 'HH:MM', 'HH:MM:SS' or
 * 'HH:MM:SS.ffffff' (same string as Python time.isoformat(), see A18).
 */
export function normalizeLocalTime(
	value: string | null,
	field: 'earliest_local' | 'latest_local'
): string | null {
	if (value === null) return null;
	if (END_OF_DAY_TIMES.includes(value)) {
		if (field === 'latest_local') return null;
		throw new RuleError('invalid', field, `${field} must be before 24:00`);
	}
	const m = typeof value === 'string' ? TIME_RE.exec(value) : null;
	if (!m) throw new RuleError('invalid', field, `${field} is not a valid time`);
	const ss = m[3] ?? '00';
	const frac = (m[4] ?? '').padEnd(6, '0');
	const hhmm = `${m[1]}:${m[2]}`;
	if (ss === '00' && frac === '000000') return hhmm;
	if (frac === '000000') return `${hhmm}:${ss}`;
	return `${hhmm}:${ss}.${frac}`;
}

type SpotInput = Pick<Spot, 'default_min_kn'>;
type ProfileInput = Pick<Profile, 'default_min_kn' | 'default_max_kn'>;
type OverrideInput = Pick<AlertRuleRow, RuleField>;

interface Normalized {
	enabled: boolean | null;
	min_kn: number | null;
	max_kn: number | null;
	dir_classes: DirClass[] | null;
	weekdays: number[] | null;
	earliest_local: string | null;
	latest_local: string | null;
	min_go_hours: number | null;
	days_ahead: number | null;
}

function intIn(
	field: RuleField,
	v: unknown,
	lo: number | null,
	hi: number | null
): number | null {
	if (v === null) return null;
	if (typeof v !== 'number' || !Number.isInteger(v)) {
		throw new RuleError('invalid', field, `${field} must be an integer`);
	}
	if ((lo !== null && v < lo) || (hi !== null && v > hi)) {
		throw new RuleError('invalid', field, `${field} out of range`);
	}
	return v;
}

function validateOverride(o: OverrideInput, defaults: AlertDefaults): Normalized {
	const raw = o as unknown as Record<string, unknown>;
	for (const f of Object.keys(FIELD_SOURCES) as RuleField[]) {
		if (raw[f] === undefined) throw new RuleError('invalid', f, `missing ${f}`);
	}
	if (raw.enabled !== null && typeof raw.enabled !== 'boolean') {
		throw new RuleError('invalid', 'enabled', 'enabled must be a boolean');
	}
	const min_kn = intIn('min_kn', raw.min_kn, defaults.min_kn.min, defaults.min_kn.max);
	const max_kn = intIn('max_kn', raw.max_kn, defaults.max_kn.min, defaults.max_kn.max);
	if (min_kn !== null && max_kn !== null && min_kn >= max_kn) {
		throw new RuleError('invalid', 'max_kn', 'min_kn must be below max_kn');
	}

	const allowedDirs = defaults.dir_classes.allowed;
	let dir_classes: DirClass[] | null = null;
	if (raw.dir_classes !== null) {
		const list = raw.dir_classes;
		if (
			!Array.isArray(list) ||
			list.length === 0 ||
			!list.every((c) => allowedDirs.includes(c as DirClass))
		) {
			throw new RuleError('invalid', 'dir_classes', 'dir_classes must be ridable classes');
		}
		dir_classes = allowedDirs.filter((c) => list.includes(c));
	}
	const allowedDays = defaults.weekdays.allowed;
	let weekdays: number[] | null = null;
	if (raw.weekdays !== null) {
		const list = raw.weekdays;
		if (
			!Array.isArray(list) ||
			list.length === 0 ||
			!list.every((d) => Number.isInteger(d) && allowedDays.includes(d as number))
		) {
			throw new RuleError('invalid', 'weekdays', 'weekdays must be ISO days');
		}
		weekdays = [...new Set(list as number[])].sort((a, b) => a - b);
	}
	const earliest_local = normalizeLocalTime(raw.earliest_local as string | null, 'earliest_local');
	const latest_local = normalizeLocalTime(raw.latest_local as string | null, 'latest_local');
	if (earliest_local !== null && latest_local !== null && !(earliest_local < latest_local)) {
		throw new RuleError('invalid', 'latest_local', 'earliest_local must be before latest_local');
	}
	return {
		enabled: raw.enabled as boolean | null,
		min_kn,
		max_kn,
		dir_classes,
		weekdays,
		earliest_local,
		latest_local,
		min_go_hours: intIn(
			'min_go_hours',
			raw.min_go_hours,
			defaults.min_go_hours.min,
			defaults.min_go_hours.max
		),
		days_ahead: intIn('days_ahead', raw.days_ahead, defaults.days_ahead.min, defaults.days_ahead.max)
	};
}

function validateProfile(p: ProfileInput, defaults: AlertDefaults): void {
	const check = (
		field: 'default_min_kn' | 'default_max_kn',
		v: unknown,
		lo: number | null,
		hi: number | null
	) => {
		if (v === null) return;
		if (
			typeof v !== 'number' ||
			!Number.isInteger(v) ||
			(lo !== null && v < lo) ||
			(hi !== null && v > hi)
		) {
			throw new RuleError('invalid', field, `${field} is invalid`);
		}
	};
	check('default_min_kn', p.default_min_kn, defaults.min_kn.min, defaults.min_kn.max);
	check('default_max_kn', p.default_max_kn, defaults.max_kn.min, defaults.max_kn.max);
	if (p.default_min_kn !== null && p.default_max_kn !== null && p.default_min_kn >= p.default_max_kn) {
		throw new RuleError('invalid', 'default_max_kn', 'default_min_kn must be below default_max_kn');
	}
}

/** Mirror of shakka.domain.alerts.resolve_rule (WP-07). Throws RuleError. */
export function effectiveRule(
	spot: SpotInput,
	profile: ProfileInput | null,
	override: OverrideInput | null,
	defaults: AlertDefaults
): EffectiveRule {
	if (profile !== null) validateProfile(profile, defaults);
	const o: Normalized | null = override === null ? null : validateOverride(override, defaults);
	const sources = {} as Record<RuleField, RuleSource>;

	// Compare with !== null, never with ||: days_ahead 0 is valid.
	let enabled: boolean;
	if (o !== null && o.enabled !== null) {
		enabled = o.enabled;
		sources.enabled = 'rule';
	} else {
		enabled = defaults.enabled.default;
		sources.enabled = 'system';
	}

	let min_kn: number;
	if (o !== null && o.min_kn !== null) {
		min_kn = o.min_kn;
		sources.min_kn = 'rule';
	} else if (profile !== null && profile.default_min_kn !== null) {
		min_kn = profile.default_min_kn;
		sources.min_kn = 'profile';
	} else if (spot.default_min_kn !== null) {
		min_kn = spot.default_min_kn;
		sources.min_kn = 'spot';
	} else {
		min_kn = defaults.min_kn.default;
		sources.min_kn = 'system';
	}

	let max_kn: number;
	if (o !== null && o.max_kn !== null) {
		max_kn = o.max_kn;
		sources.max_kn = 'rule';
	} else if (profile !== null && profile.default_max_kn !== null) {
		max_kn = profile.default_max_kn;
		sources.max_kn = 'profile';
	} else {
		max_kn = Math.max(defaults.max_kn.default, min_kn + (defaults.max_kn.min_span_kn ?? 0));
		sources.max_kn = 'system';
	}

	let dir_classes: DirClass[];
	if (o !== null && o.dir_classes !== null) {
		dir_classes = [...o.dir_classes];
		sources.dir_classes = 'rule';
	} else {
		dir_classes = defaults.dir_classes.allowed.filter((c) => defaults.dir_classes.default.includes(c));
		sources.dir_classes = 'system';
	}

	let weekdays: number[];
	if (o !== null && o.weekdays !== null) {
		weekdays = [...o.weekdays];
		sources.weekdays = 'rule';
	} else {
		weekdays = [...defaults.weekdays.default].sort((a, b) => a - b);
		sources.weekdays = 'system';
	}

	let earliest_local: string | null = null;
	sources.earliest_local = 'system';
	if (o !== null && o.earliest_local !== null) {
		earliest_local = o.earliest_local;
		sources.earliest_local = 'rule';
	}
	let latest_local: string | null = null;
	sources.latest_local = 'system';
	if (o !== null && o.latest_local !== null) {
		latest_local = o.latest_local;
		sources.latest_local = 'rule';
	}

	let min_go_hours: number;
	if (o !== null && o.min_go_hours !== null) {
		min_go_hours = o.min_go_hours;
		sources.min_go_hours = 'rule';
	} else {
		min_go_hours = defaults.min_go_hours.default;
		sources.min_go_hours = 'system';
	}

	let days_ahead: number;
	if (o !== null && o.days_ahead !== null) {
		days_ahead = o.days_ahead;
		sources.days_ahead = 'rule';
	} else {
		days_ahead = defaults.days_ahead.default;
		sources.days_ahead = 'system';
	}

	if (sources.max_kn !== 'system' && min_kn >= max_kn) {
		throw new RuleError(
			'conflict',
			'min_kn',
			`min_kn ${min_kn} (${sources.min_kn}) must be below max_kn ${max_kn} (${sources.max_kn})`,
			{ min: min_kn, minSource: sources.min_kn, max: max_kn, maxSource: sources.max_kn }
		);
	}

	return {
		enabled,
		min_kn,
		max_kn,
		dir_classes,
		weekdays,
		earliest_local,
		latest_local,
		min_go_hours,
		days_ahead,
		sources
	};
}
