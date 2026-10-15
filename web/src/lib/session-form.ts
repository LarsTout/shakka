import type { FieldErrors, FormResult } from './forms.js';
import type { NewSessionParams } from './go.js';
import {
	DEPARTURE_POINT_MAX,
	NOTE_MAX,
	ORGANIZER_NAME_MAX,
	SEATS_FREE_RANGE,
	SESSION_MAX_HOURS,
	TIKKIE_URL_MAX,
	countCodePoints,
	isTikkieUrl,
	type NewSession,
	type SessionRow
} from './session-model.js';
import { addDaysToKey, formatLocal, localDateKey, localWallTimeToUtc } from './time.js';
import type { Spot } from './types.js';

export interface SessionFormValues {
	spot_id: string;
	date: string;
	start_time: string;
	end_time: string;
	organizer_name: string;
	note: string;
	seats_free: string;
	departure_point: string;
	tikkie_url: string;
}
export type SessionFormField = keyof SessionFormValues;
export interface PreferredWindow {
	start: Date;
	end: Date;
}
export interface SessionFormContext {
	now: Date;
	spotIds: ReadonlySet<string>;
	preferred: PreferredWindow | null;
}

export const SESSION_FORM_MESSAGES = {
	spot: 'Kies een spot uit de lijst.',
	date: 'Kies een geldige datum.',
	dateRange: 'Kies een datum van vandaag tot hoogstens een jaar vooruit.',
	time: 'Kies een tijd.',
	timeNonexistent:
		'Deze tijd bestaat niet op deze dag (de klok gaat een uur vooruit). Kies een andere tijd.',
	endBeforeStart: 'De eindtijd moet na de begintijd liggen.',
	tooLong: `Een sessie duurt hoogstens ${SESSION_MAX_HOURS} uur.`,
	inPast: 'Deze sessie is dan al voorbij. Kies een latere eindtijd.',
	organizerName: `Vul je voornaam in: 1 tot ${ORGANIZER_NAME_MAX} tekens, zonder regeleinden.`,
	note: `De notitie is te lang (hoogstens ${NOTE_MAX} tekens).`,
	seatsFree: `Vul een heel getal van ${SEATS_FREE_RANGE[0]} tot ${SEATS_FREE_RANGE[1]} in, of laat het veld leeg.`,
	departurePoint: `Het vertrekpunt is te lang (hoogstens ${DEPARTURE_POINT_MAX} tekens).`,
	tikkieUrl: `Plak een Tikkie-link: die begint met https://tikkie.me/, bevat geen spaties en is hoogstens ${TIKKIE_URL_MAX} tekens.`,
	summary: 'Niet opgeslagen: controleer de gemarkeerde velden.'
} as const;

export const PREFILL_NOTICES = {
	truncated: `De eindtijd is ingekort: een sessie duurt hoogstens ${SESSION_MAX_HOURS} uur.`,
	otherDay: 'Het tijdvenster loopt door na middernacht. Kies een eindtijd op dezelfde dag.',
	past: 'Dit tijdvenster is al voorbij. Kies een nieuwe tijd.',
	spotUnknown: 'De spot uit de link bestaat niet (meer). Kies een spot.'
} as const;

/** A9: last allowed date = local today + this many days. */
export const SESSION_MAX_DAYS_AHEAD = 365;

const HOUR_MS = 3_600_000;
const TIME_RE = /^([01]\d|2[0-3]):[0-5]\d$/;
// Control characters, C1 controls and the Unicode line/paragraph separators (written as escapes).
const NAME_FORBIDDEN = /[\u0000-\u001f\u007f-\u009f\u2028\u2029]/;

/** trimmed; 1..ORGANIZER_NAME_MAX code points; no control characters or line separators. */
export function isValidOrganizerName(name: string): boolean {
	const t = name.trim();
	const n = countCodePoints(t);
	return n >= 1 && n <= ORGANIZER_NAME_MAX && !NAME_FORBIDDEN.test(t);
}

/** { min: localDateKey(now), max: that + SESSION_MAX_DAYS_AHEAD days }. */
export function sessionDateBounds(now: Date): { min: string; max: string } {
	const min = localDateKey(now);
	return { min, max: addDaysToKey(min, SESSION_MAX_DAYS_AHEAD) };
}

/** All fields '' except organizer_name; date = localDateKey(now). */
export function emptySessionForm(organizerName: string, now: Date): SessionFormValues {
	return {
		spot_id: '',
		date: localDateKey(now),
		start_time: '',
		end_time: '',
		organizer_name: organizerName,
		note: '',
		seats_free: '',
		departure_point: '',
		tikkie_url: ''
	};
}

export interface Prefill {
	form: SessionFormValues;
	preferred: PreferredWindow | null;
	notices: string[];
}

export function prefillSessionForm(
	params: NewSessionParams,
	organizerName: string,
	now: Date
): Prefill {
	const form = emptySessionForm(organizerName, now);
	const notices: string[] = [];
	let preferred: PreferredWindow | null = null;
	if (params.spot !== null) form.spot_id = params.spot;
	if (params.start !== null && params.end !== null) {
		const s = new Date(params.start);
		let e = new Date(params.end);
		if (e.getTime() - s.getTime() > SESSION_MAX_HOURS * HOUR_MS) {
			e = new Date(s.getTime() + SESSION_MAX_HOURS * HOUR_MS);
			notices.push(PREFILL_NOTICES.truncated);
		}
		form.date = localDateKey(s);
		form.start_time = formatLocal(s, 'time');
		if (localDateKey(e) === form.date) form.end_time = formatLocal(e, 'time');
		else notices.push(PREFILL_NOTICES.otherDay);
		preferred = { start: s, end: e };
		if (e.getTime() <= now.getTime()) notices.push(PREFILL_NOTICES.past);
	}
	return { form, preferred, notices };
}

/** Clears form.spot_id (and adds PREFILL_NOTICES.spotUnknown) when it is non-empty and not in spots. */
export function withKnownSpot(p: Prefill, spots: readonly Pick<Spot, 'id'>[]): Prefill {
	if (p.form.spot_id === '' || spots.some((s) => s.id === p.form.spot_id)) return p;
	return {
		...p,
		form: { ...p.form, spot_id: '' },
		notices: [...p.notices, PREFILL_NOTICES.spotUnknown]
	};
}

/** Edit mode: date/start/end in local time, numbers as String(n), null -> ''. */
export function sessionToForm(s: SessionRow): Prefill {
	const start = new Date(s.starts_at);
	const end = new Date(s.ends_at);
	return {
		form: {
			spot_id: s.spot_id,
			date: localDateKey(start),
			start_time: formatLocal(start, 'time'),
			end_time: formatLocal(end, 'time'),
			organizer_name: s.organizer_name,
			note: s.note ?? '',
			seats_free: s.seats_free === null ? '' : String(s.seats_free),
			departure_point: s.departure_point ?? '',
			tikkie_url: s.tikkie_url ?? ''
		},
		preferred: { start, end },
		notices: []
	};
}

const M = SESSION_FORM_MESSAGES;

export function parseSessionForm(
	f: SessionFormValues,
	ctx: SessionFormContext
): FormResult<NewSession, SessionFormField> {
	const errors: FieldErrors<SessionFormField> = {};

	if (f.spot_id === '' || !ctx.spotIds.has(f.spot_id)) errors.spot_id = M.spot;

	let dateOk = false;
	try {
		addDaysToKey(f.date, 0);
		const { min, max } = sessionDateBounds(ctx.now);
		if (f.date < min || f.date > max) errors.date = M.dateRange;
		else dateOk = true;
	} catch {
		errors.date = M.date;
	}

	let s: Date | null = null;
	let e: Date | null = null;
	for (const field of ['start_time', 'end_time'] as const) {
		if (!TIME_RE.test(f[field])) {
			errors[field] = M.time;
			continue;
		}
		if (!dateOk) continue;
		const preferred = field === 'start_time' ? ctx.preferred?.start : ctx.preferred?.end;
		const t = localWallTimeToUtc(f.date, f[field], preferred ?? null);
		if (t === null) errors[field] = M.timeNonexistent;
		else if (field === 'start_time') s = t;
		else e = t;
	}
	if (s !== null && e !== null) {
		const span = e.getTime() - s.getTime();
		if (span <= 0) errors.end_time = M.endBeforeStart;
		else if (span > SESSION_MAX_HOURS * HOUR_MS) errors.end_time = M.tooLong;
		else if (e.getTime() <= ctx.now.getTime()) errors.end_time = M.inPast;
	}

	const organizer_name = f.organizer_name.trim();
	if (!isValidOrganizerName(f.organizer_name)) errors.organizer_name = M.organizerName;

	const noteTrim = f.note.trim();
	if (countCodePoints(noteTrim) > NOTE_MAX) errors.note = M.note;

	const seatsTrim = f.seats_free.trim();
	let seats_free: number | null = null;
	if (seatsTrim !== '') {
		const n = /^\d{1,2}$/.test(seatsTrim) ? Number(seatsTrim) : -1;
		if (n >= SEATS_FREE_RANGE[0] && n <= SEATS_FREE_RANGE[1]) seats_free = n;
		else errors.seats_free = M.seatsFree;
	}

	const depTrim = f.departure_point.trim();
	if (countCodePoints(depTrim) > DEPARTURE_POINT_MAX) errors.departure_point = M.departurePoint;

	const tikkieTrim = f.tikkie_url.trim();
	if (tikkieTrim !== '' && !isTikkieUrl(tikkieTrim)) errors.tikkie_url = M.tikkieUrl;

	if (Object.keys(errors).length > 0 || s === null || e === null) return { ok: false, errors };
	return {
		ok: true,
		value: {
			spot_id: f.spot_id,
			organizer_name,
			starts_at: s.toISOString(),
			ends_at: e.toISOString(),
			note: noteTrim === '' ? null : noteTrim,
			seats_free,
			departure_point: depTrim === '' ? null : depTrim,
			tikkie_url: tikkieTrim === '' ? null : tikkieTrim
		}
	};
}
