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
