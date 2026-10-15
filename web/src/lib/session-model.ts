// Pure: imports only ./time.js (no data.js, no supabase), so session-form.ts and local-prefs.ts stay pure too.
import { formatWindowLocal } from './time.js';

/** Columns of public.sessions that the app selects: all except organizer_id and recent_rsvp_creates. */
export const SESSION_COLUMNS = [
	'id',
	'slug',
	'spot_id',
	'organizer_name',
	'starts_at',
	'ends_at',
	'note',
	'seats_free',
	'departure_point',
	'tikkie_url',
	'cancelled_at',
	'created_at',
	'updated_at'
] as const;
/** Columns the organizer sets on insert and may update (column grants, WP-19; without organizer_id and cancelled_at). */
export const SESSION_EDITABLE_COLUMNS = [
	'spot_id',
	'organizer_name',
	'starts_at',
	'ends_at',
	'note',
	'seats_free',
	'departure_point',
	'tikkie_url'
] as const;
export type SessionEditableColumn = (typeof SESSION_EDITABLE_COLUMNS)[number];

export interface NewSession {
	spot_id: string;
	organizer_name: string; // trimmed, 1-30 code points, no control characters
	starts_at: string; // ISO 8601 UTC (Date.toISOString())
	ends_at: string;
	note: string | null;
	seats_free: number | null;
	departure_point: string | null;
	tikkie_url: string | null;
}
export interface SessionRow extends NewSession {
	id: string;
	slug: string;
	cancelled_at: string | null;
	created_at: string;
	updated_at: string; // also changes on a new RSVP (WP-19 A4): never "last edited"
}
/** Payload of updateOwnSession: editable columns plus cancelled_at. */
export type SessionUpdate = Partial<NewSession> & { cancelled_at?: string };

export const ORGANIZER_NAME_MAX = 30; // sessions_organizer_name_valid
export const NOTE_MAX = 280; // sessions_note_length
export const DEPARTURE_POINT_MAX = 80; // sessions_departure_point_length
export const TIKKIE_URL_MAX = 200; // sessions_tikkie_url_https
export const SEATS_FREE_RANGE = [0, 8] as const; // sessions_seats_free_range
export const SESSION_MAX_HOURS = 16; // sessions_window_max_16h

/** Same name and regex as WP-21 session-view.ts (A17); equals CHECK sessions_slug_format. */
export const SESSION_SLUG_RE = /^[A-Za-z0-9_-]{10,64}$/;

/** SESSION_SLUG_RE.test(slug). */
export function isValidSessionSlug(slug: string): boolean {
	return SESSION_SLUG_RE.test(slug);
}

/** '/s/' + slug. RangeError('invalid session slug') when !isValidSessionSlug(slug). */
export function sessionPath(slug: string): string {
	if (!isValidSessionSlug(slug)) throw new RangeError('invalid session slug');
	return `/s/${slug}`;
}

/** origin with trailing '/' removed + sessionPath(slug). */
export function sessionUrl(origin: string, slug: string): string {
	return origin.replace(/\/+$/, '') + sessionPath(slug);
}

/** [...s].length: code points, as Postgres char_length counts them (WP-19 A8). */
export function countCodePoints(s: string): number {
	return [...s].length;
}

/** A18: only Tikkie payment links. Case-sensitive, like the https:// CHECK. */
export const TIKKIE_URL_RE = /^https:\/\/tikkie\.me\/\S+$/;

/** TIKKIE_URL_RE and length and a parsed URL with host exactly tikkie.me. Never throws. */
export function isTikkieUrl(s: string): boolean {
	if (!TIKKIE_URL_RE.test(s) || countCodePoints(s) > TIKKIE_URL_MAX) return false;
	try {
		const u = new URL(s);
		return (
			u.protocol === 'https:' &&
			u.hostname === 'tikkie.me' &&
			u.username === '' &&
			u.password === '' &&
			u.port === ''
		);
	} catch {
		return false;
	}
}

/**
 * Exactly four lines joined with '\n': who/where, the local window, the invitation, the URL.
 */
export function shareText(
	session: Pick<NewSession, 'organizer_name' | 'starts_at' | 'ends_at'>,
	spotName: string,
	url: string
): string {
	return [
		`${session.organizer_name} gaat kiten bij ${spotName}.`,
		formatWindowLocal(new Date(session.starts_at), new Date(session.ends_at)),
		'Ga je mee? Meld je aan via de link, een account is niet nodig:',
		url
	].join('\n');
}

/** 'https://wa.me/?text=' + encodeURIComponent(text). No other parameters. */
export function whatsappUrl(text: string): string {
	return `https://wa.me/?text=${encodeURIComponent(text)}`;
}
