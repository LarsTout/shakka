import { get } from 'svelte/store';
import type { Session } from '@supabase/supabase-js';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const auth = vi.hoisted(() => ({
	signInWithOtp: vi.fn(),
	signOut: vi.fn(),
	onAuthStateChange: vi.fn(),
	verifyOtp: vi.fn()
}));
const push = vi.hoisted(() => ({ release: vi.fn(async () => {}) }));
vi.mock('#lib/supabase.js', () => ({
	supabase: { auth },
	initialUrlHash: '',
	supabaseOrigin: 'https://abc.supabase.co'
}));
vi.mock('#lib/push.js', () => ({ releasePushForSignOut: push.release }));

import {
	AUTH_MESSAGES,
	authErrorMessage,
	initAuth,
	parseAuthRedirectError,
	parseMagicLink,
	signInWithPastedLink,
	session,
	signInWithMagicLink,
	signOut
} from '#lib/auth.js';

const OK = { data: { user: null, session: null }, error: null };

beforeEach(() => {
	vi.clearAllMocks();
	push.release.mockImplementation(async () => {});
});

describe('signInWithMagicLink', () => {
	it('trims the address and calls signInWithOtp with exactly the expected options', async () => {
		auth.signInWithOtp.mockResolvedValue(OK);
		const result = await signInWithMagicLink(' lars@example.com ');
		expect(result).toEqual({});
		expect(auth.signInWithOtp).toHaveBeenCalledTimes(1);
		expect(auth.signInWithOtp).toHaveBeenCalledWith({
			email: 'lars@example.com',
			options: { emailRedirectTo: window.location.origin, shouldCreateUser: true }
		});
	});

	it.each(['', 'lars', 'lars@x'])('rejects invalid address %j without a call', async (value) => {
		const result = await signInWithMagicLink(value);
		expect(result).toEqual({ error: AUTH_MESSAGES.invalidEmail });
		expect(auth.signInWithOtp).not.toHaveBeenCalled();
	});

	it('maps returned errors', async () => {
		auth.signInWithOtp.mockResolvedValue({ data: {}, error: { status: 500, code: 'x' } });
		expect(await signInWithMagicLink('a@b.nl')).toEqual({ error: AUTH_MESSAGES.generic });
	});

	it('maps a rejected promise to network', async () => {
		auth.signInWithOtp.mockRejectedValue(new Error('boom'));
		expect(await signInWithMagicLink('a@b.nl')).toEqual({ error: AUTH_MESSAGES.network });
	});
});

describe('authErrorMessage', () => {
	it('maps rate limits', () => {
		expect(authErrorMessage({ code: 'over_email_send_rate_limit' })).toBe(AUTH_MESSAGES.rateLimited);
		expect(authErrorMessage({ code: 'over_request_rate_limit' })).toBe(AUTH_MESSAGES.rateLimited);
		expect(authErrorMessage({ status: 429 })).toBe(AUTH_MESSAGES.rateLimited);
	});
	it('maps unauthorised addresses, including unknown users while sign-up is closed', () => {
		expect(authErrorMessage({ code: 'email_address_not_authorized' })).toBe(
			AUTH_MESSAGES.notAuthorized
		);
		expect(authErrorMessage({ code: 'otp_disabled' })).toBe(AUTH_MESSAGES.notAuthorized);
		expect(authErrorMessage({ code: 'signup_disabled' })).toBe(AUTH_MESSAGES.notAuthorized);
	});
	it('maps invalid addresses', () => {
		expect(authErrorMessage({ code: 'email_address_invalid' })).toBe(AUTH_MESSAGES.invalidEmail);
		expect(authErrorMessage({ code: 'validation_failed' })).toBe(AUTH_MESSAGES.invalidEmail);
	});
	it('maps network errors', () => {
		expect(authErrorMessage({ name: 'AuthRetryableFetchError', status: 0 })).toBe(
			AUTH_MESSAGES.network
		);
	});
	it('falls back to generic', () => {
		expect(authErrorMessage(null)).toBe(AUTH_MESSAGES.generic);
		expect(authErrorMessage('x')).toBe(AUTH_MESSAGES.generic);
	});
});

describe('parseAuthRedirectError', () => {
	it('returns null without an error', () => {
		expect(parseAuthRedirectError('')).toBeNull();
		expect(parseAuthRedirectError('#access_token=a')).toBeNull();
	});
	it('maps otp_expired and others', () => {
		expect(
			parseAuthRedirectError('#error=access_denied&error_code=otp_expired&error_description=x')
		).toBe(AUTH_MESSAGES.linkExpired);
		expect(parseAuthRedirectError('#error=server_error')).toBe(AUTH_MESSAGES.linkFailed);
	});
});

describe('initAuth', () => {
	it('follows onAuthStateChange, is idempotent and tears down', () => {
		const unsubscribe = vi.fn();
		auth.onAuthStateChange.mockReturnValue({ data: { subscription: { unsubscribe } } });
		const stop = initAuth();
		initAuth();
		expect(auth.onAuthStateChange).toHaveBeenCalledTimes(1);
		const callback = auth.onAuthStateChange.mock.calls[0][0];
		expect(get(session)).toBeUndefined();
		callback('INITIAL_SESSION', null);
		expect(get(session)).toBeNull();
		const fake = { user: { email: 'lars@example.com' } } as unknown as Session;
		callback('SIGNED_IN', fake);
		expect(get(session)).toBe(fake);
		stop();
		expect(unsubscribe).toHaveBeenCalledTimes(1);
		expect(get(session)).toBeUndefined();
	});
});

describe('signOut', () => {
	it('signs out locally and does not throw on error', async () => {
		auth.signOut.mockResolvedValue({ error: { message: 'x' } });
		const warn = vi.spyOn(console, 'warn').mockImplementation(() => {});
		await expect(signOut()).resolves.toBeUndefined();
		expect(auth.signOut).toHaveBeenCalledWith({ scope: 'local' });
		expect(warn).toHaveBeenCalledWith('signOut failed');
		warn.mockRestore();
	});
});

describe('signOut and push (WP-18)', () => {
	it('releases the push subscription before signing out', async () => {
		auth.signOut.mockResolvedValue({ error: null });
		await signOut();
		expect(push.release).toHaveBeenCalledTimes(1);
		expect(push.release.mock.invocationCallOrder[0]!).toBeLessThan(
			auth.signOut.mock.invocationCallOrder[0]!
		);
	});
	it('still signs out when the release rejects', async () => {
		push.release.mockRejectedValueOnce(new Error('x'));
		auth.signOut.mockResolvedValue({ error: null });
		await expect(signOut()).resolves.toBeUndefined();
		expect(auth.signOut).toHaveBeenCalledWith({ scope: 'local' });
	});
});

describe('parseMagicLink', () => {
	const base = 'https://abc.supabase.co/auth/v1/verify';
	const link = `${base}?token=abc123&type=magiclink&redirect_to=https%3A%2F%2Fapp.test`;
	const O = 'https://abc.supabase.co';
	it('parses a magic link, also with surrounding spaces', () => {
		expect(parseMagicLink(link, O)).toEqual({ tokenHash: 'abc123', type: 'magiclink' });
		expect(parseMagicLink(`  ${link}\n`, O)).toEqual({ tokenHash: 'abc123', type: 'magiclink' });
	});
	it('accepts signup and invite', () => {
		expect(parseMagicLink(`${base}?token=abc123&type=signup`, O)).toEqual({
			tokenHash: 'abc123',
			type: 'signup'
		});
		expect(parseMagicLink(`${base}?token=abc123&type=invite`, O)).toEqual({
			tokenHash: 'abc123',
			type: 'invite'
		});
	});
	it.each([
		['other origin', 'https://evil.supabase.co/auth/v1/verify?token=abc123&type=magiclink'],
		['other path', 'https://abc.supabase.co/auth/v1/other?token=abc123&type=magiclink'],
		['recovery', `${base}?token=abc123&type=recovery`],
		['email_change', `${base}?token=abc123&type=email_change`],
		['no type', `${base}?token=abc123`],
		['empty token', `${base}?token=&type=magiclink`],
		['token with a space', `${base}?token=ab%20c&type=magiclink`],
		['long token', `${base}?token=${'a'.repeat(257)}&type=magiclink`],
		['no link', 'geen link']
	])('refuses %s', (_n, text) => {
		expect(parseMagicLink(text, O)).toBeNull();
	});
});

describe('signInWithPastedLink', () => {
	const link = 'https://abc.supabase.co/auth/v1/verify?token=abc123&type=magiclink';
	it('calls verifyOtp with the token hash and type', async () => {
		auth.verifyOtp.mockResolvedValue(OK);
		expect(await signInWithPastedLink(link)).toEqual({});
		expect(auth.verifyOtp).toHaveBeenCalledWith({ token_hash: 'abc123', type: 'magiclink' });
	});
	it('passes the signup type on', async () => {
		auth.verifyOtp.mockResolvedValue(OK);
		await signInWithPastedLink(link.replace('magiclink', 'signup'));
		expect(auth.verifyOtp).toHaveBeenCalledWith({ token_hash: 'abc123', type: 'signup' });
	});
	it('refuses an invalid link without a call', async () => {
		expect(await signInWithPastedLink('geen link')).toEqual({ error: AUTH_MESSAGES.linkInvalid });
		expect(auth.verifyOtp).not.toHaveBeenCalled();
	});
	it('maps errors', async () => {
		auth.verifyOtp.mockResolvedValue({ data: {}, error: { code: 'otp_expired', status: 403 } });
		expect(await signInWithPastedLink(link)).toEqual({ error: AUTH_MESSAGES.pastedLinkUsed });
		auth.verifyOtp.mockResolvedValue({
			data: {},
			error: { name: 'AuthRetryableFetchError', status: 0 }
		});
		expect(await signInWithPastedLink(link)).toEqual({ error: AUTH_MESSAGES.network });
		auth.verifyOtp.mockRejectedValue(new Error('x'));
		expect(await signInWithPastedLink(link)).toEqual({ error: AUTH_MESSAGES.network });
		auth.verifyOtp.mockResolvedValue({ data: {}, error: { status: 500 } });
		expect(await signInWithPastedLink(link)).toEqual({ error: AUTH_MESSAGES.linkFailed });
		auth.verifyOtp.mockResolvedValue({ data: {}, error: { status: 429 } });
		expect(await signInWithPastedLink(link)).toEqual({ error: AUTH_MESSAGES.rateLimited });
	});
	it('parseAuthRedirectError still gives linkExpired for otp_expired', () => {
		expect(parseAuthRedirectError('#error=access_denied&error_code=otp_expired')).toBe(
			AUTH_MESSAGES.linkExpired
		);
	});
});
