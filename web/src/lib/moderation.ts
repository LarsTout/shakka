import { supabase } from '#lib/supabase.js';
import { UUID_RE } from './session-view.js';
import { updateOwnSession } from './user-data.js';

// The only module that calls organizer_delete_rsvp (WP-25). Closing and reopening sign-ups goes through
// updateOwnSession, so table access stays in user-data.ts.

export const MODERATION_RPC_TIMEOUT_MS = 15_000;

export const MODERATION_MESSAGES = {
	deleted: 'Aanmelding verwijderd.',
	alreadyGone: 'Deze aanmelding bestond al niet meer.',
	failed: 'Verwijderen is niet gelukt. Probeer het later opnieuw.',
	network: 'Verwijderen is niet gelukt: geen verbinding met de server. Probeer het opnieuw.',
	open: 'Aanmelden is open.',
	closed:
		'Aanmelden is gesloten. Nieuwe mensen kunnen zich niet aanmelden; wie al aangemeld is, kan zich nog afmelden.',
	closeButton: 'Aanmelden sluiten',
	openButton: 'Aanmelden weer openen'
} as const;

interface RpcResult {
	data: unknown;
	error: unknown;
	status: number;
}

/** Never throws. An id that is not a UUID gives { ok: false, error: failed } without a request.
 *  Calls the organizer_delete_rsvp function with p_rsvp_id and a time-out signal, like account.ts.
 *  data true -> ok; data false -> alreadyGone; thrown or status 0 -> network; any other error or
 *  non-boolean data -> failed. On every failure exactly one console.warn('organizer delete failed')
 *  without details. */
export async function deleteRsvpAsOrganizer(rsvpId: string): Promise<{ ok: boolean; error?: string }> {
	if (!UUID_RE.test(rsvpId)) {
		console.warn('organizer delete failed');
		return { ok: false, error: MODERATION_MESSAGES.failed };
	}
	let res: RpcResult;
	try {
		const builder = supabase.rpc('organizer_delete_rsvp', { p_rsvp_id: rsvpId });
		const timed =
			typeof AbortSignal !== 'undefined' && typeof AbortSignal.timeout === 'function'
				? builder.abortSignal(AbortSignal.timeout(MODERATION_RPC_TIMEOUT_MS))
				: builder;
		res = (await timed) as unknown as RpcResult;
	} catch {
		console.warn('organizer delete failed');
		return { ok: false, error: MODERATION_MESSAGES.network };
	}
	if (!res.error && res.data === true) return { ok: true };
	console.warn('organizer delete failed');
	if (res.error) {
		return { ok: false, error: res.status === 0 ? MODERATION_MESSAGES.network : MODERATION_MESSAGES.failed };
	}
	return {
		ok: false,
		error: res.data === false ? MODERATION_MESSAGES.alreadyGone : MODERATION_MESSAGES.failed
	};
}

/** Sets rsvps_closed_at to now (closed) or null (open). Throws DataError like updateOwnSession. */
export function setRsvpsClosed(sessionId: string, closed: boolean, now: Date = new Date()): Promise<void> {
	return updateOwnSession(sessionId, { rsvps_closed_at: closed ? now.toISOString() : null });
}
