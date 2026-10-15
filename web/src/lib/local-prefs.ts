import type { StorageLike } from './browser-storage.js';
import { isValidOrganizerName } from './session-form.js';
import { parseGoParams } from './time.js';

export const ORGANIZER_NAME_KEY = 'shakka:organizer_name';
export const RETURN_TO_KEY = 'shakka:return_to';
export const RETURN_TO_TTL_MS = 60 * 60 * 1000;

const BASE = 'https://shakka.invalid';

/** Stored name if isValidOrganizerName(name), else ''. '' when storage is undefined. Never throws. */
export function readOrganizerName(storage: StorageLike | undefined): string {
	try {
		const v = storage?.getItem(ORGANIZER_NAME_KEY);
		return typeof v === 'string' && isValidOrganizerName(v) ? v.trim() : '';
	} catch {
		return '';
	}
}

/** Stores name.trim() when valid; ignores invalid names, undefined storage and storage errors. */
export function writeOrganizerName(storage: StorageLike | undefined, name: string): void {
	if (!storage || !isValidOrganizerName(name)) return;
	try {
		storage.setItem(ORGANIZER_NAME_KEY, name.trim());
	} catch {
		// Storage blocked or full: the name is simply not remembered.
	}
}

/** Only '/go?' paths that parseGoParams accepts and that stay on our own origin. */
export function isAllowedReturnPath(path: string): boolean {
	if (typeof path !== 'string' || !path.startsWith('/go?')) return false;
	try {
		const u = new URL(path, BASE);
		return u.origin === BASE && parseGoParams(u) !== null;
	} catch {
		return false;
	}
}

/** Writes JSON {"path", "saved_at"} when allowed; false on refusal, undefined storage or error. */
export function saveReturnTo(
	storage: StorageLike | undefined,
	path: string,
	nowMs: number
): boolean {
	if (!storage || !isAllowedReturnPath(path)) return false;
	try {
		storage.setItem(RETURN_TO_KEY, JSON.stringify({ path, saved_at: nowMs }));
		return true;
	} catch {
		return false;
	}
}

/** Path from a raw stored value when it parses as {path: string, saved_at: number}, its age
 *  (nowMs - saved_at) is within 0..RETURN_TO_TTL_MS, and isAllowedReturnPath(path). Else null. Never throws. */
function freshReturnPath(raw: string | null, nowMs: number): string | null {
	if (raw === null) return null;
	try {
		const v: unknown = JSON.parse(raw);
		if (typeof v !== 'object' || v === null) return null;
		const { path, saved_at } = v as { path?: unknown; saved_at?: unknown };
		if (typeof path !== 'string' || typeof saved_at !== 'number') return null;
		const age = nowMs - saved_at;
		if (!(age >= 0 && age <= RETURN_TO_TTL_MS)) return null;
		return isAllowedReturnPath(path) ? path : null;
	} catch {
		return null;
	}
}

/** Reads and ALWAYS removes the key. Returns the path when fresh (0..TTL) and allowed, else null. */
export function takeReturnTo(storage: StorageLike | undefined, nowMs: number): string | null {
	if (!storage) return null;
	let raw: string | null = null;
	try {
		raw = storage.getItem(RETURN_TO_KEY);
	} catch {
		raw = null;
	}
	try {
		storage.removeItem(RETURN_TO_KEY);
	} catch {
		// Ignore: nothing more we can do.
	}
	return freshReturnPath(raw, nowMs);
}

/** Removes the key unless its value is one takeReturnTo would accept right now. Missing key: no-op.
 *  Returns true when it removed the key; false for undefined storage or storage errors. Never throws. */
export function pruneReturnTo(storage: StorageLike | undefined, nowMs: number): boolean {
	if (!storage) return false;
	try {
		const raw = storage.getItem(RETURN_TO_KEY);
		if (raw === null) return false;
		if (freshReturnPath(raw, nowMs) !== null) return false;
		storage.removeItem(RETURN_TO_KEY);
		return true;
	} catch {
		return false;
	}
}
