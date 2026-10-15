import { signOut } from '#lib/auth.js';
import { supabase } from '#lib/supabase.js';
import type { StorageLike } from './browser-storage.js';
import { ORGANIZER_NAME_KEY, RETURN_TO_KEY } from './local-prefs.js';

// The only module that calls delete_my_account (WP-23). A POST without arguments; nothing from the server
// response is shown or logged.

export const ACCOUNT_RPC_TIMEOUT_MS = 15_000;

export const ACCOUNT_MESSAGES = {
	failed: 'Je account is niet verwijderd: er ging iets mis. Probeer het later opnieuw.',
	network: 'Je account is niet verwijderd: geen verbinding met de server. Probeer het opnieuw.',
	deleted: 'Je account en alle gegevens die eraan vastzaten, zijn verwijderd. Je bent uitgelogd.'
} as const;

/** Keys in localStorage that belong to the signed-in user (WP-20). shakka:rsvp:* stays (blueprint A10). */
export const ACCOUNT_LOCAL_KEYS: readonly string[] = [ORGANIZER_NAME_KEY, RETURN_TO_KEY];

export type DeleteAccountResult = { ok: true } | { ok: false; error: string };

interface RpcResult {
	error: unknown;
	status: number;
}

/** Never throws. On failure: one console.warn('account delete failed') without details. */
export async function deleteMyAccount(): Promise<DeleteAccountResult> {
	let res: RpcResult;
	try {
		const builder = supabase.rpc('delete_my_account');
		const timed =
			typeof AbortSignal !== 'undefined' && typeof AbortSignal.timeout === 'function'
				? builder.abortSignal(AbortSignal.timeout(ACCOUNT_RPC_TIMEOUT_MS))
				: builder;
		res = (await timed) as unknown as RpcResult;
	} catch {
		console.warn('account delete failed');
		return { ok: false, error: ACCOUNT_MESSAGES.network };
	}
	if (!res.error) return { ok: true };
	console.warn('account delete failed');
	return { ok: false, error: res.status === 0 ? ACCOUNT_MESSAGES.network : ACCOUNT_MESSAGES.failed };
}

/** Removes ACCOUNT_LOCAL_KEYS. Ignores undefined storage and storage errors. Never throws. */
export function clearAccountLocalData(storage: StorageLike | undefined): void {
	if (!storage) return;
	for (const key of ACCOUNT_LOCAL_KEYS) {
		try {
			storage.removeItem(key);
		} catch {
			// Nothing more we can do.
		}
	}
}

/** After a successful deletion: sign out (releases this device's push subscription, then local sign-out),
 *  then clear the account keys. Never throws. */
export async function cleanUpAfterAccountDeletion(storage: StorageLike | undefined): Promise<void> {
	try {
		await signOut();
	} catch {
		// The keys are cleared regardless.
	}
	clearAccountLocalData(storage);
}
