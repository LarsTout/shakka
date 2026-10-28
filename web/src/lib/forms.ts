import { ALERT_DEFAULTS, dirClassLabel } from './contracts.js';
import { SOURCE_LABEL_NL, daysAheadText, formatKn } from './labels.js';
import {
	RuleError,
	effectiveRule,
	normalizeLocalTime,
	type EffectiveRule,
	type RuleConflict
} from './rules.js';
import { WEEKDAY_ABBR_NL } from './time.js';
import {
	LEVELS,
	type AlertDefaults,
	type AlertRuleValues,
	type DirClass,
	type Profile,
	type ProfileEditableColumn,
	type ProfileUpdate,
	type RuleField,
	type Spot,
	type SpotLevel
} from './types.js';

export const WEIGHT_RANGE_KG = [30, 200] as const; // profiles_weight_range
export const QUIVER_SIZE_RANGE_M2 = [3, 21] as const; // profiles_quiver_valid
export const MAX_QUIVER_KITES = 10; // profiles_quiver_valid
export const DAYS_AHEAD_UI_MAX = 7; // WP-26: equals the CHECK max; forecast covers local today+7
/** '01:00', '02:00', ..., '23:00' (never 00:00 or 24:00). */
export const HOUR_OPTIONS: readonly string[] = Array.from(
	{ length: 23 },
	(_, i) => `${String(i + 1).padStart(2, '0')}:00`
);

const knMessage = (lo: number, hi: number) => `Vul een heel getal tussen ${lo} en ${hi} kn in.`;

export const FORM_MESSAGES = {
	weight: `Vul een heel getal tussen ${WEIGHT_RANGE_KG[0]} en ${WEIGHT_RANGE_KG[1]} kg in.`,
	level: 'Kies een niveau uit de lijst.',
	quiverSize: `Elke kitemaat moet tussen ${QUIVER_SIZE_RANGE_M2[0]} en ${QUIVER_SIZE_RANGE_M2[1]} m² liggen (bijv. 9 of 10,5).`,
	quiverCount: `Je kunt maximaal ${MAX_QUIVER_KITES} kites invullen.`,
	kn: knMessage(ALERT_DEFAULTS.min_kn.min ?? 0, ALERT_DEFAULTS.min_kn.max ?? 0),
	minNotBelowMax: 'De maximale wind moet hoger zijn dan de minimale wind.',
	dirEmpty: 'Kies minstens één windrichting.',
	dirInvalid: 'Deze windrichting kun je niet kiezen.',
	weekdaysEmpty: 'Kies minstens één dag.',
	weekdaysInvalid: 'Kies dagen uit de lijst.',
	time: 'Kies een tijd uit de lijst.',
	latestMidnight:
		'"Tot 00:00" telt geen enkel uur. Kies een later tijdstip of geen bovengrens.',
	timeOrder: '"Tot" moet later zijn dan "Vanaf".',
	minGoHours: `Vul een heel getal tussen ${ALERT_DEFAULTS.min_go_hours.min} en ${ALERT_DEFAULTS.min_go_hours.max} in.`,
	daysAhead: 'Kies een waarde uit de lijst.',
	profileInvalid: 'Je profiel heeft ongeldige windgrenzen; pas die aan bij Profiel.',
	ruleInvalid: 'Deze instelling kan niet worden opgeslagen. Controleer de velden.',
	conflict: (c: RuleConflict): string =>
		`Minimale wind ${formatKn(c.min)} kn (${SOURCE_LABEL_NL[c.minSource]}) moet lager zijn dan maximale wind ${formatKn(c.max)} kn (${SOURCE_LABEL_NL[c.maxSource]}).`
};

export type FieldErrors<F extends string> = Partial<Record<F, string>>;
export type FormResult<T, F extends string> =
	| { ok: true; value: T }
	| { ok: false; errors: FieldErrors<F> };

type Parsed = { ok: true; value: number | null } | { ok: false };

/** trim; empty -> null; otherwise /^\d{1,3}$/ and lo <= n <= hi. */
function parseIntField(s: string, lo: number, hi: number): Parsed {
	const t = s.trim();
	if (t === '') return { ok: true, value: null };
	if (!/^\d{1,3}$/.test(t)) return { ok: false };
	const n = Number(t);
	return n >= lo && n <= hi ? { ok: true, value: n } : { ok: false };
}

function parseQuiverSize(s: string): number | null {
	const t = s.trim();
	if (!/^\d{1,2}([.,]\d{1,2})?$/.test(t)) return null;
	const n = Number(t.replace(',', '.'));
	return n >= QUIVER_SIZE_RANGE_M2[0] && n <= QUIVER_SIZE_RANGE_M2[1] ? n : null;
}

// ---------------------------------------------------------------------------------------------
// Profile

export interface ProfileForm {
	weight_kg: string;
	level: '' | SpotLevel;
	quiver: string[];
	default_min_kn: string;
	default_max_kn: string;
}

const str = (n: number | null): string => (n === null ? '' : String(n));

export function profileToForm(p: ProfileUpdate): ProfileForm {
	return {
		weight_kg: str(p.weight_kg),
		level: p.level ?? '',
		quiver: p.quiver_m2.map((n) => String(n).replace('.', ',')),
		default_min_kn: str(p.default_min_kn),
		default_max_kn: str(p.default_max_kn)
	};
}

export function parseProfileForm(
	f: ProfileForm,
	defaults: AlertDefaults
): FormResult<ProfileUpdate, ProfileEditableColumn> {
	const errors: FieldErrors<ProfileEditableColumn> = {};

	const weight = parseIntField(f.weight_kg, WEIGHT_RANGE_KG[0], WEIGHT_RANGE_KG[1]);
	if (!weight.ok) errors.weight_kg = FORM_MESSAGES.weight;

	let level: SpotLevel | null = null;
	if (f.level !== '') {
		if (LEVELS.includes(f.level)) level = f.level;
		else errors.level = FORM_MESSAGES.level;
	}

	const sizes = f.quiver.map((q) => q.trim()).filter((q) => q !== '');
	const quiver: number[] = [];
	if (sizes.length > MAX_QUIVER_KITES) {
		errors.quiver_m2 = FORM_MESSAGES.quiverCount;
	} else {
		for (const s of sizes) {
			const n = parseQuiverSize(s);
			if (n === null) {
				errors.quiver_m2 = FORM_MESSAGES.quiverSize;
				break;
			}
			quiver.push(n);
		}
		quiver.sort((a, b) => a - b);
	}

	const minLo = defaults.min_kn.min ?? 0;
	const minHi = defaults.min_kn.max ?? 0;
	const maxLo = defaults.max_kn.min ?? 0;
	const maxHi = defaults.max_kn.max ?? 0;
	const min = parseIntField(f.default_min_kn, minLo, minHi);
	const max = parseIntField(f.default_max_kn, maxLo, maxHi);
	if (!min.ok) errors.default_min_kn = knMessage(minLo, minHi);
	if (!max.ok) errors.default_max_kn = knMessage(maxLo, maxHi);
	if (min.ok && max.ok && min.value !== null && max.value !== null && min.value >= max.value) {
		errors.default_max_kn = FORM_MESSAGES.minNotBelowMax;
	}

	if (Object.keys(errors).length > 0) return { ok: false, errors };
	return {
		ok: true,
		value: {
			weight_kg: weight.ok ? weight.value : null,
			level,
			quiver_m2: quiver,
			default_min_kn: min.ok ? min.value : null,
			default_max_kn: max.ok ? max.value : null
		}
	};
}

/** Static hints for the empty kn fields of the profile. */
export function profileKnHints(defaults: AlertDefaults): {
	default_min_kn: string;
	default_max_kn: string;
} {
	return {
		default_min_kn: `standaard: de waarde van de spot, anders ${formatKn(defaults.min_kn.default)} kn (${SOURCE_LABEL_NL.system})`,
		default_max_kn: `standaard: ${formatKn(defaults.max_kn.default)} kn, of ${formatKn(defaults.max_kn.min_span_kn ?? 0)} kn boven de minimale wind als dat hoger is (${SOURCE_LABEL_NL.system})`
	};
}

// ---------------------------------------------------------------------------------------------
// Alert rule

export interface AlertRuleForm {
	enabled: boolean;
	min_kn: string;
	max_kn: string;
	dir_classes: DirClass[];
	weekdays: number[];
	earliest_local: string;
	latest_local: string;
	min_go_hours: string;
	days_ahead: string;
}
export interface RuleContext {
	spot: Pick<Spot, 'default_min_kn'>;
	profile: Pick<Profile, 'default_min_kn' | 'default_max_kn'> | null;
	defaults: AlertDefaults;
}

function formTime(value: string | null, field: 'earliest_local' | 'latest_local'): string {
	try {
		return normalizeLocalTime(value, field) ?? '';
	} catch {
		return '';
	}
}

export function ruleToForm(row: AlertRuleValues | null, defaults: AlertDefaults): AlertRuleForm {
	if (row === null) {
		return {
			enabled: defaults.enabled.default,
			min_kn: '',
			max_kn: '',
			dir_classes: [...defaults.dir_classes.default],
			weekdays: [...defaults.weekdays.default],
			earliest_local: '',
			latest_local: '',
			min_go_hours: '',
			days_ahead: ''
		};
	}
	return {
		enabled: row.enabled,
		min_kn: str(row.min_kn),
		max_kn: str(row.max_kn),
		dir_classes: row.dir_classes === null ? [...defaults.dir_classes.default] : [...row.dir_classes],
		weekdays: row.weekdays === null ? [...defaults.weekdays.default] : [...row.weekdays],
		earliest_local: formTime(row.earliest_local, 'earliest_local'),
		latest_local: formTime(row.latest_local, 'latest_local'),
		min_go_hours: str(row.min_go_hours),
		days_ahead: str(row.days_ahead)
	};
}

const FORM_TIME = /^([01]\d|2[0-3]):[0-5]\d(?::[0-5]\d(?:\.\d{6})?)?$/;

function sameSet<T>(a: readonly T[], b: readonly T[]): boolean {
	const sa = new Set(a);
	const sb = new Set(b);
	return sa.size === sb.size && [...sa].every((x) => sb.has(x));
}

/**
 * Step 1 of parseAlertRuleForm, shared with ruleHints. Never throws. `value` holds every field that
 * parsed, with null for empty or failed fields and for the later field of a failed cross-field check,
 * so `value` always passes step 2 of effectiveRule.
 */
export function parseRuleFields(
	f: AlertRuleForm,
	defaults: AlertDefaults
): { value: AlertRuleValues; errors: FieldErrors<RuleField> } {
	const value: AlertRuleValues = {
		enabled: f.enabled,
		min_kn: null,
		max_kn: null,
		dir_classes: null,
		weekdays: null,
		earliest_local: null,
		latest_local: null,
		min_go_hours: null,
		days_ahead: null
	};
	const errors: FieldErrors<RuleField> = {};

	const minLo = defaults.min_kn.min ?? 0;
	const minHi = defaults.min_kn.max ?? 0;
	const maxLo = defaults.max_kn.min ?? 0;
	const maxHi = defaults.max_kn.max ?? 0;
	const min = parseIntField(f.min_kn, minLo, minHi);
	const max = parseIntField(f.max_kn, maxLo, maxHi);
	if (min.ok) value.min_kn = min.value;
	else errors.min_kn = knMessage(minLo, minHi);
	if (max.ok) value.max_kn = max.value;
	else errors.max_kn = knMessage(maxLo, maxHi);
	if (value.min_kn !== null && value.max_kn !== null && value.min_kn >= value.max_kn) {
		errors.max_kn = FORM_MESSAGES.minNotBelowMax;
		value.max_kn = null;
	}

	const allowedDirs = defaults.dir_classes.allowed;
	if (f.dir_classes.length === 0) {
		errors.dir_classes = FORM_MESSAGES.dirEmpty;
	} else if (!f.dir_classes.every((c) => allowedDirs.includes(c))) {
		errors.dir_classes = FORM_MESSAGES.dirInvalid;
	} else if (!sameSet(f.dir_classes, defaults.dir_classes.default)) {
		value.dir_classes = allowedDirs.filter((c) => f.dir_classes.includes(c));
	}

	const allowedDays = defaults.weekdays.allowed;
	if (f.weekdays.length === 0) {
		errors.weekdays = FORM_MESSAGES.weekdaysEmpty;
	} else if (!f.weekdays.every((d) => Number.isInteger(d) && allowedDays.includes(d))) {
		errors.weekdays = FORM_MESSAGES.weekdaysInvalid;
	} else if (!sameSet(f.weekdays, defaults.weekdays.default)) {
		value.weekdays = [...new Set(f.weekdays)].sort((a, b) => a - b);
	}

	const times: Partial<Record<'earliest_local' | 'latest_local', string>> = {};
	for (const field of ['earliest_local', 'latest_local'] as const) {
		const v = f[field];
		if (v === '') continue;
		if (!FORM_TIME.test(v)) {
			errors[field] = FORM_MESSAGES.time;
		} else if (field === 'latest_local' && v === '00:00') {
			errors[field] = FORM_MESSAGES.latestMidnight;
		} else {
			times[field] = v;
		}
	}
	if (times.earliest_local !== undefined) {
		value.earliest_local = /^\d{2}:\d{2}$/.test(times.earliest_local)
			? `${times.earliest_local}:00`
			: times.earliest_local;
	}
	if (times.latest_local !== undefined) {
		if (times.earliest_local !== undefined && !(times.earliest_local < times.latest_local)) {
			errors.latest_local = FORM_MESSAGES.timeOrder;
		} else {
			value.latest_local = /^\d{2}:\d{2}$/.test(times.latest_local)
				? `${times.latest_local}:00`
				: times.latest_local;
		}
	}

	const goLo = defaults.min_go_hours.min ?? 0;
	const goHi = defaults.min_go_hours.max ?? 0;
	const go = parseIntField(f.min_go_hours, goLo, goHi);
	if (go.ok) value.min_go_hours = go.value;
	else errors.min_go_hours = FORM_MESSAGES.minGoHours;

	const d = f.days_ahead.trim();
	if (d !== '') {
		const n = /^\d$/.test(d) ? Number(d) : -1;
		if (n >= (defaults.days_ahead.min ?? 0) && n <= (defaults.days_ahead.max ?? 0)) {
			value.days_ahead = n;
		} else {
			errors.days_ahead = FORM_MESSAGES.daysAhead;
		}
	}

	return { value, errors };
}

export function parseAlertRuleForm(
	f: AlertRuleForm,
	ctx: RuleContext
): FormResult<AlertRuleValues, RuleField> {
	const { value, errors } = parseRuleFields(f, ctx.defaults);
	if (Object.keys(errors).length > 0) return { ok: false, errors };
	try {
		effectiveRule(ctx.spot, ctx.profile, value, ctx.defaults);
	} catch (e) {
		if (e instanceof RuleError) {
			if (e.code === 'conflict' && e.conflict !== null) {
				const c = e.conflict;
				return {
					ok: false,
					errors: { [c.maxSource === 'rule' ? 'max_kn' : 'min_kn']: FORM_MESSAGES.conflict(c) }
				};
			}
			if (e.field === 'default_min_kn' || e.field === 'default_max_kn') {
				return { ok: false, errors: { min_kn: FORM_MESSAGES.profileInvalid } };
			}
			return { ok: false, errors: { [e.field]: FORM_MESSAGES.ruleInvalid } };
		}
		return { ok: false, errors: { min_kn: FORM_MESSAGES.ruleInvalid } };
	}
	return { ok: true, value };
}

export type HintField =
	| 'min_kn'
	| 'max_kn'
	| 'dir_classes'
	| 'weekdays'
	| 'earliest_local'
	| 'latest_local'
	| 'min_go_hours'
	| 'days_ahead';

/** Hints for empty fields ("standaard: X (bron)"). Never throws. */
export function ruleHints(f: AlertRuleForm, ctx: RuleContext): Partial<Record<HintField, string>> {
	const lenient = parseRuleFields(f, ctx.defaults).value;
	let eff: EffectiveRule | null = null;
	try {
		eff = effectiveRule(ctx.spot, ctx.profile, lenient, ctx.defaults);
	} catch {
		eff = null;
	}
	const sys = SOURCE_LABEL_NL.system;
	const out: Partial<Record<HintField, string>> = {};
	for (const field of ['min_kn', 'max_kn'] as const) {
		if (f[field].trim() !== '') continue;
		out[field] =
			eff !== null
				? `standaard: ${formatKn(eff[field])} kn (${SOURCE_LABEL_NL[eff.sources[field]]})`
				: 'standaard: botst met je andere windgrenzen';
	}
	if (sameSet(f.dir_classes, ctx.defaults.dir_classes.default)) {
		out.dir_classes = `standaard: alle rijdbare richtingen (${sys})`;
	}
	if (sameSet(f.weekdays, ctx.defaults.weekdays.default)) {
		out.weekdays = `standaard: alle dagen (${sys})`;
	}
	if (f.earliest_local.trim() === '') out.earliest_local = `standaard: geen ondergrens (${sys})`;
	if (f.latest_local.trim() === '') out.latest_local = `standaard: geen bovengrens (${sys})`;
	if (f.min_go_hours.trim() === '') {
		out.min_go_hours = `standaard: ${ctx.defaults.min_go_hours.default} uur (${sys})`;
	}
	if (f.days_ahead.trim() === '') {
		out.days_ahead = `standaard: ${daysAheadText(ctx.defaults.days_ahead.default)} (${sys})`;
	}
	return out;
}

export function ruleSummary(r: EffectiveRule): string {
	const parts: string[] = [r.enabled ? 'Aan' : 'Uit', `${formatKn(r.min_kn)}–${formatKn(r.max_kn)} kn`];
	if (r.dir_classes.length < ALERT_DEFAULTS.dir_classes.allowed.length) {
		parts.push(r.dir_classes.map((c) => dirClassLabel(c)).join(', '));
	}
	if (r.weekdays.length < 7) {
		parts.push(r.weekdays.map((d) => WEEKDAY_ABBR_NL[d - 1]).join(', '));
	}
	if (r.earliest_local !== null || r.latest_local !== null) {
		parts.push(`${r.earliest_local ?? '00:00'}–${r.latest_local ?? '24:00'}`);
	}
	parts.push(`min. ${r.min_go_hours} uur go`);
	parts.push(daysAheadText(r.days_ahead));
	return parts.join(' · ');
}

export type StoredRuleStatus = { ok: true; rule: EffectiveRule } | { ok: false; problem: string };

export function storedRuleStatus(row: AlertRuleValues | null, ctx: RuleContext): StoredRuleStatus {
	try {
		const rule = effectiveRule(ctx.spot, ctx.profile, row, ctx.defaults);
		if (rule.latest_local === '00:00') {
			return {
				ok: false,
				problem:
					'"Tot 00:00" telt geen enkel uur. Voor deze spot komen geen alerts tot je dit aanpast.'
			};
		}
		return { ok: true, rule };
	} catch (e) {
		if (e instanceof RuleError && e.code === 'conflict' && e.conflict !== null) {
			const c = e.conflict;
			return {
				ok: false,
				problem: `Deze instellingen botsen: minimale wind ${formatKn(c.min)} kn (${SOURCE_LABEL_NL[c.minSource]}) is niet lager dan maximale wind ${formatKn(c.max)} kn (${SOURCE_LABEL_NL[c.maxSource]}). Voor deze spot komen geen alerts tot je dit aanpast.`
			};
		}
		return {
			ok: false,
			problem:
				'De opgeslagen instelling is ongeldig. Voor deze spot komen geen alerts tot je hem opnieuw opslaat.'
		};
	}
}

export function timeOptions(current: string): string[] {
	const out = [...HOUR_OPTIONS];
	if (current !== '' && !out.includes(current)) out.push(current);
	return out.sort();
}

export function daysAheadOptions(current: string): string[] {
	const out = Array.from({ length: DAYS_AHEAD_UI_MAX + 1 }, (_, i) => String(i));
	if (current !== '' && !out.includes(current)) out.push(current);
	return out.sort((a, b) => Number(a) - Number(b));
}
