import { DataError } from './data.js';
import {
	SESSION_EDITABLE_COLUMNS,
	isValidSessionSlug,
	type NewSession,
	type SessionRow,
	type SessionUpdate
} from './session-model.js';
import { getOwnSession, insertSession, listOwnSessions, updateOwnSession } from './user-data.js';

export { shareText, whatsappUrl, sessionUrl } from './session-model.js';

export const SESSION_ERROR_MESSAGES = {
	rateLimited: 'Je hebt in de afgelopen 24 uur al 10 sessies aangemaakt. Probeer het later opnieuw.',
	spotGone: 'Deze spot bestaat niet meer. Kies een andere spot.',
	invalid: 'De sessie kon niet worden opgeslagen: een van de velden is ongeldig.',
	signedOut: 'Je bent niet meer ingelogd. Log opnieuw in en probeer het nog eens.',
	notFound: 'Deze sessie bestaat niet meer.',
	generic: 'Opslaan is niet gelukt. Controleer je verbinding en probeer het opnieuw.',
	cancelFailed: 'Annuleren is niet gelukt. Probeer het opnieuw.'
} as const;

/** DataError code -> Dutch message. Never the Supabase message. */
export function sessionErrorMessage(e: unknown): string {
	const code = e instanceof DataError ? e.code : null;
	switch (code) {
		case 'rate_limited':
			return SESSION_ERROR_MESSAGES.rateLimited;
		case '23503':
			return SESSION_ERROR_MESSAGES.spotGone;
		case '23514':
		case '23502':
		case '22001':
			return SESSION_ERROR_MESSAGES.invalid;
		case '42501':
		case 'PGRST301':
		case 'PGRST303':
			return SESSION_ERROR_MESSAGES.signedOut;
		case 'not_found':
			return SESSION_ERROR_MESSAGES.notFound;
		default:
			return SESSION_ERROR_MESSAGES.generic;
	}
}

/** insertSession; on DataError code '23505' (slug collision, WP-19) exactly one retry with the same input. */
export async function createSession(input: NewSession): Promise<{ slug: string }> {
	try {
		return await insertSession(input);
	} catch (e) {
		if (e instanceof DataError && e.code === '23505') return insertSession(input);
		throw e;
	}
}

/** listOwnSessions(userId, now). */
export function listMySessions(userId: string, now: Date): Promise<SessionRow[]> {
	return listOwnSessions(userId, now);
}

/** null without a query when the slug is malformed; else getOwnSession(slug). */
export async function getMySession(slug: string): Promise<SessionRow | null> {
	if (!isValidSessionSlug(slug)) return null;
	return getOwnSession(slug);
}

/** updateOwnSession(id, { cancelled_at: now.toISOString() }). */
export function cancelSession(id: string, now: Date = new Date()): Promise<void> {
	return updateOwnSession(id, { cancelled_at: now.toISOString() });
}

/** Payload = the SESSION_EDITABLE_COLUMNS keys whose value in patch is not undefined; empty = no call. */
export async function updateSession(id: string, patch: Partial<NewSession>): Promise<void> {
	const payload: Record<string, unknown> = {};
	for (const key of SESSION_EDITABLE_COLUMNS) {
		if (patch[key] !== undefined) payload[key] = patch[key];
	}
	if (Object.keys(payload).length === 0) return;
	await updateOwnSession(id, payload as SessionUpdate);
}
