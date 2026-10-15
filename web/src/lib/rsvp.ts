import { supabase } from '#lib/supabase.js';
import type {
	PublicRsvp,
	PublicSession,
	RsvpInput,
	RsvpUpdateInput,
	StoredRsvp
} from './rsvp-types.js';
import {
	EDIT_TOKEN_RE,
	RsvpError,
	isValidSessionSlug,
	parseCreateResult,
	parsePublicRsvp,
	parsePublicSession,
	rsvpErrorKind
} from './session-view.js';

// The only module that calls RPCs (WP-21). Anonymous and signed-in visitors use the same calls;
// nothing here reads or requires an auth session. RPCs go as POST with the arguments in the body
// (supabase-js default): an edit token never ends up in a URL (RUNBOOK §16.7). Never log tokens.

export const RPC_TIMEOUT_MS = 15_000;

interface RpcResult {
	data: unknown;
	error: unknown;
	status: number;
}

async function call(operation: string, fn: string, args: Record<string, unknown>): Promise<unknown> {
	let res: RpcResult;
	try {
		const builder = supabase.rpc(fn, args);
		// postgrest-js catches the rejected fetch (TimeoutError) and resolves with status 0 -> 'network'.
		const timed =
			typeof AbortSignal !== 'undefined' && typeof AbortSignal.timeout === 'function'
				? builder.abortSignal(AbortSignal.timeout(RPC_TIMEOUT_MS))
				: builder;
		res = (await timed) as unknown as RpcResult;
	} catch {
		throw new RsvpError('network', operation);
	}
	if (res.error) throw new RsvpError(rsvpErrorKind(res.error, res.status), operation);
	return res.data;
}

/** null for a malformed slug (no request) or an unknown session. */
export async function getPublicSession(slug: string): Promise<PublicSession | null> {
	if (!isValidSessionSlug(slug)) return null;
	const data = await call('getPublicSession', 'get_public_session', { p_slug: slug });
	return data === null ? null : parsePublicSession(data);
}

export async function createRsvp(slug: string, input: RsvpInput): Promise<StoredRsvp> {
	if (!isValidSessionSlug(slug)) throw new RsvpError('session_closed', 'createRsvp');
	const data = await call('createRsvp', 'rsvp_create', {
		p_slug: slug,
		p_first_name: input.first_name.trim(),
		p_ride: input.ride,
		p_seats_offered: input.seats_offered ?? null
	});
	return parseCreateResult(data);
}

/** Replaces all editable fields; send current values for fields that stay the same. */
export async function updateRsvp(token: string, input: RsvpUpdateInput): Promise<PublicRsvp> {
	if (!EDIT_TOKEN_RE.test(token)) throw new RsvpError('invalid_token', 'updateRsvp');
	const data = await call('updateRsvp', 'rsvp_update', {
		p_edit_token: token,
		p_first_name: input.first_name.trim(),
		p_ride: input.ride,
		p_seats_offered: input.seats_offered ?? null,
		p_rides_with: input.rides_with ?? null
	});
	return parsePublicRsvp(data, 'updateRsvp');
}

/** true: removed; false: unknown or malformed token (already removed). */
export async function deleteRsvp(token: string): Promise<boolean> {
	if (!EDIT_TOKEN_RE.test(token)) return false;
	const data = await call('deleteRsvp', 'rsvp_delete', { p_edit_token: token });
	if (typeof data !== 'boolean') throw new RsvpError('unknown', 'deleteRsvp');
	return data;
}
