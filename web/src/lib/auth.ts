import type { Session } from '@supabase/supabase-js';
import { writable, type Readable } from 'svelte/store';
import { releasePushForSignOut } from '#lib/push.js';
import { initialUrlHash, supabase, supabaseOrigin } from '#lib/supabase.js';

export const AUTH_MESSAGES = {
	invalidEmail: 'Vul een geldig e-mailadres in.',
	rateLimited: 'Te veel inlogpogingen. Wacht een paar minuten en probeer het opnieuw.',
	notAuthorized: 'Met dit e-mailadres kun je nog niet inloggen. Shakka is nog in de testfase.',
	network: 'Geen verbinding met de server. Controleer je internet en probeer het opnieuw.',
	generic: 'Het versturen van de inloglink is niet gelukt. Probeer het later opnieuw.',
	linkExpired: 'Deze inloglink is verlopen of al gebruikt. Vraag een nieuwe aan.',
	linkFailed: 'Inloggen via de link is niet gelukt. Vraag een nieuwe inloglink aan.',
	linkInvalid: 'Dit is geen geldige inloglink. Kopieer de link uit de mail van Shakka opnieuw.',
	pastedLinkUsed:
		'Deze inloglink is al gebruikt of verlopen. Een voorvertoning van de link in je mail-app telt ook als gebruik. Zet de linkvoorvertoningen uit (zie hierboven) en vraag een nieuwe link aan.'
} as const;

const store = writable<Session | null | undefined>(undefined);

/** undefined = not known yet (auth initialising), null = signed out. */
export const session: Readable<Session | null | undefined> = { subscribe: store.subscribe };

let teardown: (() => void) | null = null;

/** Subscribes the session store to supabase.auth.onAuthStateChange (idempotent).
 *  Returns a teardown that unsubscribes and resets the store to undefined. */
export function initAuth(): () => void {
	if (teardown) return teardown;
	const { data } = supabase.auth.onAuthStateChange((_event, s) => {
		store.set(s);
	});
	const stop = () => {
		data.subscription.unsubscribe();
		store.set(undefined);
		if (teardown === stop) teardown = null;
	};
	teardown = stop;
	return stop;
}

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

/** Sends a magic link. emailRedirectTo is window.location.origin. Never throws.
 *  Returns {} on success or { error } with one of AUTH_MESSAGES.
 *  shouldCreateUser is false until WP-22: unknown addresses must not get a row in auth.users. */
export async function signInWithMagicLink(email: string): Promise<{ error?: string }> {
	const address = email.trim();
	if (!EMAIL_PATTERN.test(address)) return { error: AUTH_MESSAGES.invalidEmail };
	try {
		const { error } = await supabase.auth.signInWithOtp({
			email: address,
			options: { emailRedirectTo: window.location.origin, shouldCreateUser: false }
		});
		return error ? { error: authErrorMessage(error) } : {};
	} catch {
		return { error: AUTH_MESSAGES.network };
	}
}

/** Signs out on this device only (scope 'local'). Never throws; logs a warning on error.
 *  First removes this device's push subscription while the session is still valid (WP-17, WP-18). */
export async function signOut(): Promise<void> {
	try {
		await releasePushForSignOut();
	} catch {
		// never blocks sign-out
	}
	try {
		const { error } = await supabase.auth.signOut({ scope: 'local' });
		if (error) console.warn('signOut failed');
	} catch {
		console.warn('signOut failed');
	}
}

/** Maps a supabase-js auth error (or anything thrown) to a Dutch message. */
export function authErrorMessage(error: unknown): string {
	if (typeof error !== 'object' || error === null) return AUTH_MESSAGES.generic;
	const { name, status, code } = error as { name?: unknown; status?: unknown; code?: unknown };
	if (name === 'AuthRetryableFetchError' || status === 0) return AUTH_MESSAGES.network;
	if (
		status === 429 ||
		code === 'over_email_send_rate_limit' ||
		code === 'over_request_rate_limit'
	) {
		return AUTH_MESSAGES.rateLimited;
	}
	// otp_disabled: sign-up is closed (shouldCreateUser false) and the address is unknown.
	if (code === 'email_address_not_authorized' || code === 'otp_disabled') {
		return AUTH_MESSAGES.notAuthorized;
	}
	if (code === 'email_address_invalid' || code === 'validation_failed') {
		return AUTH_MESSAGES.invalidEmail;
	}
	return AUTH_MESSAGES.generic;
}

/** Parses a magic-link redirect fragment such as '#error=access_denied&error_code=otp_expired&...'.
 *  Returns a Dutch message, or null when the fragment carries no error. */
export function parseAuthRedirectError(hash: string): string | null {
	const params = new URLSearchParams(hash.replace(/^#/, ''));
	if (!params.has('error') && !params.has('error_code')) return null;
	return params.get('error_code') === 'otp_expired'
		? AUTH_MESSAGES.linkExpired
		: AUTH_MESSAGES.linkFailed;
}

/** parseAuthRedirectError(initialUrlHash) */
export function initialAuthRedirectError(): string | null {
	return parseAuthRedirectError(initialUrlHash);
}

/** Link types that sign a user in via verifyOtp({ token_hash, type }). recovery and email_change are refused. */
export type PastedLinkType = 'magiclink' | 'signup' | 'invite';

const PASTED_LINK_TYPES: readonly string[] = ['magiclink', 'signup', 'invite'];

/** Token hash and type from a pasted Supabase Auth link of this project (text is trimmed first). Anything else -> null. */
export function parseMagicLink(
	text: string,
	origin: string
): { tokenHash: string; type: PastedLinkType } | null {
	let url: URL;
	try {
		url = new URL(text.trim());
	} catch {
		return null;
	}
	if (url.origin !== origin || url.pathname !== '/auth/v1/verify') return null;
	const type = url.searchParams.get('type');
	const token = url.searchParams.get('token');
	if (type === null || !PASTED_LINK_TYPES.includes(type)) return null;
	if (!token || /\s/.test(token) || token.length > 256) return null;
	return { tokenHash: token, type: type as PastedLinkType };
}

/** otp_expired -> pastedLinkUsed; network and rate limit as elsewhere; else linkFailed. */
export function pastedLinkErrorMessage(error: unknown): string {
	if (typeof error !== 'object' || error === null) return AUTH_MESSAGES.linkFailed;
	const { name, status, code } = error as { name?: unknown; status?: unknown; code?: unknown };
	if (code === 'otp_expired') return AUTH_MESSAGES.pastedLinkUsed;
	if (name === 'AuthRetryableFetchError' || status === 0) return AUTH_MESSAGES.network;
	if (
		status === 429 ||
		code === 'over_request_rate_limit' ||
		code === 'over_email_send_rate_limit'
	) {
		return AUTH_MESSAGES.rateLimited;
	}
	return AUTH_MESSAGES.linkFailed;
}

/** Signs in with a pasted login link. Never throws and never logs the link.
 *  Success: {} (the session store updates via onAuthStateChange). */
export async function signInWithPastedLink(text: string): Promise<{ error?: string }> {
	const parsed = parseMagicLink(text, supabaseOrigin);
	if (!parsed) return { error: AUTH_MESSAGES.linkInvalid };
	try {
		const { error } = await supabase.auth.verifyOtp({
			token_hash: parsed.tokenHash,
			type: parsed.type
		});
		return error ? { error: pastedLinkErrorMessage(error) } : {};
	} catch {
		return { error: AUTH_MESSAGES.network };
	}
}
