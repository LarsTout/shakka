// Shared with WP-21 (A17): same names and signature as its rsvp-storage.ts, so it can import these after rebasing.
export type StorageLike = Pick<Storage, 'getItem' | 'setItem' | 'removeItem'>;

/** globalThis.localStorage, or undefined when unavailable (access can throw a SecurityError). */
export function browserStorage(): StorageLike | undefined {
	try {
		return globalThis.localStorage ?? undefined;
	} catch {
		return undefined;
	}
}
