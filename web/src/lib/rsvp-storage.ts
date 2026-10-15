import type { StorageLike } from './browser-storage.js';
import type { StoredRsvp } from './rsvp-types.js';
import { isValidSessionSlug, parseStoredRsvp, rsvpStorageKey } from './session-view.js';

// Fallback for the lifetime of this page when localStorage is unavailable or full (E26).
// Lost on reload; never written anywhere else.
const memory = new Map<string, StoredRsvp>();

/** Tests only: forget the in-memory fallback. */
export function resetRsvpMemory(): void {
	memory.clear();
}

/** The stored RSVP for this slug, else the in-memory fallback, else null. A malformed value is removed. Never throws. */
export function readStoredRsvp(storage: StorageLike | undefined, slug: string): StoredRsvp | null {
	if (!isValidSessionSlug(slug)) return null;
	const fallback = memory.get(slug) ?? null;
	if (!storage) return fallback;
	let raw: string | null;
	try {
		raw = storage.getItem(rsvpStorageKey(slug));
	} catch {
		return fallback;
	}
	if (raw === null) return fallback;
	let parsed: StoredRsvp | null = null;
	try {
		parsed = parseStoredRsvp(JSON.parse(raw));
	} catch {
		parsed = null;
	}
	if (parsed === null) clearStoredRsvp(storage, slug);
	return parsed;
}

/** Stores exactly {rsvp_id, edit_token}. true when persisted; false when storage is unavailable or full,
 *  in which case the value is kept in memory for this page lifetime. Never throws. */
export function writeStoredRsvp(storage: StorageLike | undefined, slug: string, value: StoredRsvp): boolean {
	if (!isValidSessionSlug(slug)) return false;
	const clean: StoredRsvp = { rsvp_id: value.rsvp_id, edit_token: value.edit_token };
	if (!storage) {
		memory.set(slug, clean);
		return false;
	}
	try {
		storage.setItem(rsvpStorageKey(slug), JSON.stringify(clean));
		memory.delete(slug);
		return true;
	} catch {
		memory.set(slug, clean);
		return false;
	}
}

/** Removes the key and the in-memory fallback. Never throws. */
export function clearStoredRsvp(storage: StorageLike | undefined, slug: string): void {
	if (!isValidSessionSlug(slug)) return;
	memory.delete(slug);
	if (!storage) return;
	try {
		storage.removeItem(rsvpStorageKey(slug));
	} catch {
		// nothing to do: the key stays until the next successful removal
	}
}
