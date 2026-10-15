import type { Session } from '@supabase/supabase-js';
import { writable, type Readable } from 'svelte/store';
import { initialUrlHash, supabase } from '#lib/supabase.js';

export const AUTH_MESSAGES = {
	invalidEmail: 'Vul een geldig e-mailadres in.',
	rateLimited: 'Te veel inlogpogingen. Wacht een paar minuten en probeer het opnieuw.',
	notAuthorized: 'Met dit e-mailadres kun je nog niet inloggen. Shakka is nog in de testfase.',
	network: 'Geen verbinding met de server. Controleer je internet en probeer het opnieuw.',
	generic: 'Het versturen van de inloglink is niet gelukt. Probeer het later opnieuw.',
	linkExpired: 'Deze inloglink is verlopen of al gebruikt. Vraag een nieuwe aan.',
	linkFailed: 'Inloggen via de link is niet gelukt. Vraag een nieuwe inloglink aan.'
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

/** Signs out on this device only (scope 'local'). Never throws; logs a warning on error. */
export async function signOut(): Promise<void> {
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
