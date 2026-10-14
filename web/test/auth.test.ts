import { get } from 'svelte/store';
import type { Session } from '@supabase/supabase-js';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const auth = vi.hoisted(() => ({
	signInWithOtp: vi.fn(),
	signOut: vi.fn(),
	onAuthStateChange: vi.fn()
}));
vi.mock('#lib/supabase.js', () => ({ supabase: { auth }, initialUrlHash: '' }));

import {
	AUTH_MESSAGES,
	authErrorMessage,
	initAuth,
	parseAuthRedirectError,
	session,
	signInWithMagicLink,
	signOut
} from '#lib/auth.js';

const OK = { data: { user: null, session: null }, error: null };

beforeEach(() => {
	vi.clearAllMocks();
});

describe('signInWithMagicLink', () => {
	it('trims the address and calls signInWithOtp with exactly the expected options', async () => {
		auth.signInWithOtp.mockResolvedValue(OK);
		const result = await signInWithMagicLink(' lars@example.com ');
		expect(result).toEqual({});
		expect(auth.signInWithOtp).toHaveBeenCalledTimes(1);
		expect(auth.signInWithOtp).toHaveBeenCalledWith({
			email: 'lars@example.com',
			options: { emailRedirectTo: window.location.origin, shouldCreateUser: false }
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
