const MISSING_HINT = 'is missing: copy web/.env.example to web/.env (see docs/RUNBOOK.md)';

/** Validates PUBLIC_SUPABASE_URL. Returns the normalised origin (no trailing slash). Never echoes the value. */
export function parseSupabaseUrl(value: string | undefined): string {
	const raw = value?.trim() ?? '';
	if (!raw) throw new Error(`PUBLIC_SUPABASE_URL ${MISSING_HINT}`);
	let url: URL;
	try {
		url = new URL(raw);
	} catch {
		throw new Error('PUBLIC_SUPABASE_URL is not a valid URL');
	}
	const localHttp =
		url.protocol === 'http:' && (url.hostname === 'localhost' || url.hostname === '127.0.0.1');
	if (url.protocol !== 'https:' && !localHttp) {
		throw new Error('PUBLIC_SUPABASE_URL must use https (http only for localhost)');
	}
	if (url.pathname !== '/' || url.search || url.hash || url.username || url.password) {
		throw new Error('PUBLIC_SUPABASE_URL must be the project URL without path');
	}
	return url.origin;
}

/** Validates PUBLIC_SUPABASE_PUBLISHABLE_KEY. Returns the trimmed key. Never echoes the value. */
export function parsePublishableKey(value: string | undefined): string {
	const key = value?.trim() ?? '';
	if (!key) throw new Error(`PUBLIC_SUPABASE_PUBLISHABLE_KEY ${MISSING_HINT}`);
	if (key.startsWith('sb_secret_')) {
		throw new Error('PUBLIC_SUPABASE_PUBLISHABLE_KEY must be the publishable key, never the secret key');
	}
	if (!key.startsWith('sb_publishable_') || /\s/.test(key)) {
		throw new Error('PUBLIC_SUPABASE_PUBLISHABLE_KEY must start with sb_publishable_');
	}
	return key;
}

/** Validates PUBLIC_MAPTILER_KEY. Missing or blank -> '' (map disabled). Returns the trimmed key. Never echoes the value. */
export function parseMaptilerKey(value: string | undefined): string {
	const key = value?.trim() ?? '';
	if (!key) return '';
	if (!/^[A-Za-z0-9_-]{8,128}$/.test(key)) {
		throw new Error('PUBLIC_MAPTILER_KEY must be a MapTiler API key (8-128 letters, digits, - or _)');
	}
	return key;
}

/** Decodes base64url (with or without '=' padding) to bytes.
 *  Throws Error('invalid base64url') for other characters or a length that is 1 mod 4. */
export function base64UrlToBytes(value: string): Uint8Array<ArrayBuffer> {
	if (!/^[A-Za-z0-9_-]*={0,2}$/.test(value)) throw new Error('invalid base64url');
	const bare = value.replace(/=+$/, '');
	if (bare.length % 4 === 1) throw new Error('invalid base64url');
	const std = bare.replace(/-/g, '+').replace(/_/g, '/');
	const padded = std + '='.repeat((4 - (std.length % 4)) % 4);
	const bin = atob(padded);
	const out = new Uint8Array(bin.length);
	for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
	return out;
}

/** Validates PUBLIC_VAPID_PUBLIC_KEY. Missing or blank -> '' (push disabled in this build).
 *  Returns the key without '=' padding. Never echoes the value. */
export function parseVapidPublicKey(value: string | undefined): string {
	const raw = value?.trim() ?? '';
	if (!raw) return '';
	const key = raw.replace(/=+$/, '');
	let bytes: Uint8Array;
	try {
		if (/[^A-Za-z0-9_-]/.test(key)) throw new Error('invalid base64url');
		bytes = base64UrlToBytes(key);
	} catch {
		throw new Error(
			'PUBLIC_VAPID_PUBLIC_KEY must be base64url: use VAPID_PUBLIC_KEY from shakka alerts vapid-keys'
		);
	}
	if (bytes.length === 32) {
		throw new Error(
			'PUBLIC_VAPID_PUBLIC_KEY looks like a private key: use VAPID_PUBLIC_KEY, never VAPID_PRIVATE_KEY'
		);
	}
	if (bytes.length !== 65 || bytes[0] !== 0x04) {
		throw new Error('PUBLIC_VAPID_PUBLIC_KEY must be an uncompressed P-256 public key (65 bytes)');
	}
	return key;
}
