import {
	MAX_FIRST_NAME,
	RIDES,
	type PublicRsvp,
	type PublicSession,
	type PublicSessionInfo,
	type Ride,
	type RsvpUpdateInput,
	type StoredRsvp
} from './rsvp-types.js';
import { countCodePoints, isTikkieUrl } from './session-model.js';
import { formatWindowLocal } from './time.js';

// Slug regex, slug check and code point counting come from WP-20 session-model.ts (blueprint A20, step 9).
export { SESSION_SLUG_RE, isValidSessionSlug, countCodePoints } from './session-model.js';

export const EDIT_TOKEN_RE = /^[A-Za-z0-9_-]{43}$/; // same as the migration
export const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
export const RSVP_STORAGE_PREFIX = 'shakka:rsvp:';

export function rsvpStorageKey(slug: string): string {
	return RSVP_STORAGE_PREFIX + slug;
}

export const RPC_ERROR_CODES = [
	'rate_limited',
	'session_closed',
	'session_full',
	'invalid_input',
	'invalid_token'
] as const;
export type RpcErrorCode = (typeof RPC_ERROR_CODES)[number];
export type RsvpErrorKind = RpcErrorCode | 'network' | 'unknown';

/** The only error the RSVP code throws. message: `${operation} failed: ${kind}`; never server text. */
export class RsvpError extends Error {
	readonly kind: RsvpErrorKind;
	readonly operation: string;
	constructor(kind: RsvpErrorKind, operation: string) {
		super(`${operation} failed: ${kind}`);
		this.name = 'RsvpError';
		this.kind = kind;
		this.operation = operation;
	}
}

/** status === 0 -> 'network'; PT400 with a known message -> that code; everything else -> 'unknown'. */
export function rsvpErrorKind(error: unknown, status?: number): RsvpErrorKind {
	if (status === 0) return 'network';
	if (typeof error !== 'object' || error === null) return 'unknown';
	const e = error as { code?: unknown; message?: unknown };
	if (e.code === 'PT400' && typeof e.message === 'string') {
		const known = (RPC_ERROR_CODES as readonly string[]).includes(e.message);
		if (known) return e.message as RpcErrorCode;
	}
	return 'unknown';
}

export const RSVP_MESSAGES: Record<RsvpErrorKind, string> = {
	rate_limited: 'Er melden zich nu veel mensen tegelijk aan. Probeer het over een paar minuten opnieuw.',
	session_full: 'Deze sessie zit vol: naast de organisator kunnen hoogstens 30 mensen zich aanmelden.',
	session_closed: 'Dit kan niet meer: de sessie is geannuleerd of al voorbij.',
	invalid_input:
		'Dat ging niet goed. Controleer je voornaam (1 tot 30 tekens) en je vervoerskeuze, en probeer het opnieuw.',
	invalid_token: 'Je aanmelding is niet meer gevonden. Meld je opnieuw aan als je nog mee wilt.',
	network: 'Geen verbinding met de server. Controleer je internet en probeer het opnieuw.',
	unknown: 'Er ging iets mis. Probeer het later opnieuw.'
};

export const RSVP_NOTICES = {
	created: 'Je staat op de lijst.',
	storageFailed:
		'Je staat op de lijst, maar deze browser kon je aanmelding niet onthouden. Wijzigen of afmelden lukt daardoor alleen zolang deze pagina open is.',
	updated: 'Je wijziging is opgeslagen.',
	deleted: 'Je bent afgemeld.',
	alreadyDeleted: 'Je aanmelding bestond al niet meer.'
};

export const RSVP_FORM_MESSAGES = {
	nameRequired: 'Vul je voornaam in.',
	nameTooLong: 'Je voornaam mag hoogstens 30 tekens hebben.',
	nameInvalid: 'Je voornaam mag geen regeleinden of andere stuurtekens bevatten.',
	rideRequired: 'Kies hoe je naar de spot gaat.',
	seatsInvalid: 'Kies een aantal plekken van 0 tot 8, of "Weet ik nog niet".',
	ridesWithInvalid: 'Kies iemand die een lift aanbiedt, of "Nog niemand".'
};

export const RIDE_OPTION_LABEL_NL: Record<Ride, string> = {
	own: 'Ik rijd zelf',
	needs_ride: 'Ik zoek een lift',
	offers_ride: 'Ik kan mensen meenemen'
};

// --- Parsers -------------------------------------------------------------------------------------

function isObj(x: unknown): x is Record<string, unknown> {
	return typeof x === 'object' && x !== null && !Array.isArray(x);
}
const isStr = (x: unknown): x is string => typeof x === 'string';
const isStrOrNull = (x: unknown): x is string | null => x === null || typeof x === 'string';
const isIntOrNull = (x: unknown): x is number | null => x === null || Number.isInteger(x);

export function parsePublicRsvp(json: unknown, operation: string): PublicRsvp {
	if (
		!isObj(json) ||
		!isStr(json.id) ||
		!isStr(json.first_name) ||
		!isStr(json.created_at) ||
		!(RIDES as readonly unknown[]).includes(json.ride) ||
		!isIntOrNull(json.seats_offered) ||
		!isStrOrNull(json.rides_with)
	) {
		throw new RsvpError('unknown', operation);
	}
	return {
		id: json.id,
		first_name: json.first_name,
		ride: json.ride as Ride,
		seats_offered: json.seats_offered,
		rides_with: json.rides_with,
		created_at: json.created_at
	};
}

export function parsePublicSession(json: unknown): PublicSession {
	const op = 'getPublicSession';
	if (!isObj(json) || !isObj(json.session) || !Array.isArray(json.rsvps)) {
		throw new RsvpError('unknown', op);
	}
	const s = json.session;
	if (
		!isStr(s.slug) ||
		!isStr(s.spot_id) ||
		!isStr(s.organizer_name) ||
		!isStr(s.starts_at) ||
		!isStr(s.ends_at) ||
		!isStrOrNull(s.spot_name) ||
		!isStrOrNull(s.note) ||
		!isStrOrNull(s.departure_point) ||
		!isStrOrNull(s.tikkie_url) ||
		!isIntOrNull(s.seats_free) ||
		typeof s.cancelled !== 'boolean'
	) {
		throw new RsvpError('unknown', op);
	}
	const start = Date.parse(s.starts_at);
	const end = Date.parse(s.ends_at);
	if (Number.isNaN(start) || Number.isNaN(end) || !(end > start)) throw new RsvpError('unknown', op);
	const session: PublicSessionInfo = {
		slug: s.slug,
		spot_id: s.spot_id,
		spot_name: s.spot_name,
		organizer_name: s.organizer_name,
		starts_at: s.starts_at,
		ends_at: s.ends_at,
		note: s.note,
		seats_free: s.seats_free,
		departure_point: s.departure_point,
		tikkie_url: s.tikkie_url,
		cancelled: s.cancelled
	};
	return { session, rsvps: json.rsvps.map((item) => parsePublicRsvp(item, op)) };
}

export function parseCreateResult(json: unknown): StoredRsvp {
	const v = parseStoredRsvp(json);
	if (v === null) throw new RsvpError('unknown', 'createRsvp');
	return v;
}

/** Value from localStorage (already JSON.parsed); null when the shape is wrong. Never throws. */
export function parseStoredRsvp(json: unknown): StoredRsvp | null {
	if (!isObj(json)) return null;
	const { rsvp_id, edit_token } = json;
	if (!isStr(rsvp_id) || !UUID_RE.test(rsvp_id)) return null;
	if (!isStr(edit_token) || !EDIT_TOKEN_RE.test(edit_token)) return null;
	return { rsvp_id, edit_token };
}

// --- Session state and labels --------------------------------------------------------------------

/** cancelled || Date.parse(ends_at) <= now */
export function isSessionClosed(
	s: Pick<PublicSessionInfo, 'cancelled' | 'ends_at'>,
	now: Date
): boolean {
	return s.cancelled || Date.parse(s.ends_at) <= now.getTime();
}

/** Same notation as WP-20 formatWindowLocal and WP-08 format_window_local (A21). */
export function sessionWindowText(startsAt: string, endsAt: string): string {
	return formatWindowLocal(new Date(startsAt), new Date(endsAt));
}

export function seatsText(n: number | null): string {
	if (n === null) return 'aantal plekken onbekend';
	if (n === 0) return 'geen plek meer';
	if (n === 1) return '1 plek';
	return `${n} plekken`;
}

export function rideLabel(
	r: PublicRsvp,
	byId: ReadonlyMap<string, PublicRsvp>
): { label: string; name: string | null } {
	if (r.ride === 'own') return { label: 'Rijdt zelf', name: null };
	if (r.ride === 'offers_ride') {
		const base = 'Biedt een lift aan';
		return {
			label: r.seats_offered !== null ? `${base} (${seatsText(r.seats_offered)})` : base,
			name: null
		};
	}
	const driver = r.rides_with !== null ? byId.get(r.rides_with) : undefined;
	if (driver && driver.ride === 'offers_ride') {
		return { label: 'Rijdt mee met', name: driver.first_name };
	}
	return { label: 'Zoekt een lift', name: null };
}

export interface CarpoolDriver {
	rsvp: PublicRsvp;
	riders: PublicRsvp[];
}
export interface CarpoolView {
	organizerSeats: number | null;
	departurePoint: string | null;
	drivers: CarpoolDriver[];
	seekers: PublicRsvp[];
	isEmpty: boolean;
}

export function carpoolView(
	session: Pick<PublicSessionInfo, 'seats_free' | 'departure_point'>,
	rsvps: readonly PublicRsvp[]
): CarpoolView {
	const driverIds = new Set(rsvps.filter((r) => r.ride === 'offers_ride').map((r) => r.id));
	const drivers: CarpoolDriver[] = rsvps
		.filter((r) => r.ride === 'offers_ride')
		.map((d) => ({
			rsvp: d,
			riders: rsvps.filter((r) => r.ride === 'needs_ride' && r.rides_with === d.id)
		}));
	const seekers = rsvps.filter(
		(r) => r.ride === 'needs_ride' && (r.rides_with === null || !driverIds.has(r.rides_with))
	);
	const departurePoint = optionalText(session.departure_point);
	const organizerSeats = session.seats_free;
	return {
		organizerSeats,
		departurePoint,
		drivers,
		seekers,
		isEmpty:
			organizerSeats === null && departurePoint === null && drivers.length === 0 && seekers.length === 0
	};
}

export const TIKKIE_PREFIX = 'https://tikkie.me/';
/** A14: only https://tikkie.me/<something>. Delegates to WP-20 isTikkieUrl (stricter: no port, user, whitespace). */
export function tikkieLink(url: string | null): string | null {
	if (url === null || !url.startsWith(TIKKIE_PREFIX) || url.length <= TIKKIE_PREFIX.length) return null;
	if (!isTikkieUrl(url)) return null;
	try {
		return new URL(url).href;
	} catch {
		return null;
	}
}

/** null, '' or whitespace -> null; otherwise the text unchanged. */
export function optionalText(s: string | null): string | null {
	return s === null || s.trim() === '' ? null : s;
}

/** FSI + s + PDI: bidi isolation where <bdi> is impossible, e.g. <option> text (A11). */
export function isolateText(s: string): string {
	return `⁨${s}⁩`;
}

// --- Form ----------------------------------------------------------------------------------------

export type RsvpFormMode = 'create' | 'edit';
export interface RsvpFormValues {
	first_name: string;
	ride: Ride | '';
	seats: string;
	rides_with: string;
}
export type RsvpFormField = 'first_name' | 'ride' | 'seats' | 'rides_with';
export type RsvpFormResult =
	| { ok: true; value: RsvpUpdateInput }
	| { ok: false; errors: Partial<Record<RsvpFormField, string>> };

export function emptyRsvpForm(): RsvpFormValues {
	return { first_name: '', ride: 'own', seats: '', rides_with: '' };
}

export function rsvpFormFromRsvp(r: PublicRsvp): RsvpFormValues {
	return {
		first_name: r.first_name,
		ride: r.ride,
		seats: r.seats_offered === null ? '' : String(r.seats_offered),
		rides_with: r.rides_with ?? ''
	};
}

export function parseRsvpForm(
	values: RsvpFormValues,
	mode: RsvpFormMode,
	driverIds: ReadonlySet<string>
): RsvpFormResult {
	const errors: Partial<Record<RsvpFormField, string>> = {};
	const name = values.first_name.trim();
	if (name === '') errors.first_name = RSVP_FORM_MESSAGES.nameRequired;
	else if (countCodePoints(name) > MAX_FIRST_NAME) errors.first_name = RSVP_FORM_MESSAGES.nameTooLong;
	else if (/\p{Cc}/u.test(name)) errors.first_name = RSVP_FORM_MESSAGES.nameInvalid;

	const ride = values.ride;
	if (!(RIDES as readonly string[]).includes(ride)) errors.ride = RSVP_FORM_MESSAGES.rideRequired;

	let seats: number | null = null;
	if (ride === 'offers_ride' && values.seats !== '') {
		if (/^[0-8]$/.test(values.seats)) seats = Number(values.seats);
		else errors.seats = RSVP_FORM_MESSAGES.seatsInvalid;
	}

	let ridesWith: string | null = null;
	if (mode === 'edit' && ride === 'needs_ride' && values.rides_with !== '') {
		if (driverIds.has(values.rides_with)) ridesWith = values.rides_with;
		else errors.rides_with = RSVP_FORM_MESSAGES.ridesWithInvalid;
	}

	if (Object.keys(errors).length > 0) return { ok: false, errors };
	return {
		ok: true,
		value: { first_name: name, ride: ride as Ride, seats_offered: seats, rides_with: ridesWith }
	};
}
