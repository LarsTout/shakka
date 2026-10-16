import { render, screen } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

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
	supabaseOrigin: 'http://127.0.0.1:54321'
}));
vi.mock('#lib/push.js', () => ({ releasePushForSignOut: push.release }));

import { AUTH_MESSAGES, initAuth } from '#lib/auth.js';
import { IPHONE_UA, installPushEnv } from './helpers/fake-push.js';
import Login from '../src/routes/login/+page.svelte';

let stop: (() => void) | undefined;
let env: ReturnType<typeof installPushEnv> | undefined;
beforeEach(() => vi.clearAllMocks());
afterEach(() => {
	stop?.();
	stop = undefined;
	env?.uninstall();
	env = undefined;
});

const LINK =
	'http://127.0.0.1:54321/auth/v1/verify?token=abc123&type=magiclink&redirect_to=http%3A%2F%2Flocalhost';
function signedOut() {
	auth.onAuthStateChange.mockImplementation((cb: (e: string, s: unknown) => void) => {
		cb('INITIAL_SESSION', null);
		return { data: { subscription: { unsubscribe: vi.fn() } } };
	});
	stop = initAuth();
}

const OK = { data: { user: null, session: null }, error: null };
const fail = (status: number, code: string) => ({
	data: { user: null, session: null },
	error: { name: 'AuthApiError', status, code, message: 'x' }
});

describe('login page', () => {
	it('sends a link and confirms', async () => {
		auth.signInWithOtp.mockResolvedValue(OK);
		render(Login);
		await userEvent.type(screen.getByLabelText('E-mailadres'), 'lars@example.com');
		await userEvent.click(screen.getByRole('button', { name: 'Stuur inloglink' }));
		expect(auth.signInWithOtp).toHaveBeenCalledWith({
			email: 'lars@example.com',
			options: { emailRedirectTo: window.location.origin, shouldCreateUser: true }
		});
		expect(await screen.findByText('Check je mail')).toBeInTheDocument();
		expect(screen.getByText(/lars@example\.com/)).toHaveTextContent('Open de link op dit apparaat');
	});
	it('shows a fixed Dutch message on a server error, never the raw one', async () => {
		auth.signInWithOtp.mockResolvedValue(fail(500, 'unexpected_failure'));
		render(Login);
		await userEvent.type(screen.getByLabelText('E-mailadres'), 'lars@example.com');
		await userEvent.click(screen.getByRole('button', { name: 'Stuur inloglink' }));
		expect(await screen.findByRole('alert')).toHaveTextContent(AUTH_MESSAGES.generic);
		expect(screen.queryByText('x')).toBeNull();
	});
	it('shows the rate limit message', async () => {
		auth.signInWithOtp.mockResolvedValue(fail(429, 'over_email_send_rate_limit'));
		render(Login);
		await userEvent.type(screen.getByLabelText('E-mailadres'), 'lars@example.com');
		await userEvent.click(screen.getByRole('button', { name: 'Stuur inloglink' }));
		expect(await screen.findByRole('alert')).toHaveTextContent(AUTH_MESSAGES.rateLimited);
	});
	it('rejects an empty field without a call', async () => {
		render(Login);
		await userEvent.click(screen.getByRole('button', { name: 'Stuur inloglink' }));
		expect(await screen.findByRole('alert')).toHaveTextContent(AUTH_MESSAGES.invalidEmail);
		expect(auth.signInWithOtp).not.toHaveBeenCalled();
	});
	it('disables the button while sending', async () => {
		let resolve!: (v: unknown) => void;
		auth.signInWithOtp.mockReturnValue(new Promise((r) => (resolve = r)));
		render(Login);
		await userEvent.type(screen.getByLabelText('E-mailadres'), 'lars@example.com');
		await userEvent.click(screen.getByRole('button', { name: 'Stuur inloglink' }));
		expect(await screen.findByRole('button', { name: /Bezig met versturen/ })).toBeDisabled();
		resolve(OK);
		expect(await screen.findByText('Check je mail')).toBeInTheDocument();
	});
});

describe('pasted login link (WP-18, B-1)', () => {
	it('shows nothing extra outside standalone and outside iOS', async () => {
		env = installPushEnv({ supported: false });
		signedOut();
		render(Login);
		expect(screen.queryByRole('heading', { name: 'Inloglink plakken' })).toBeNull();
		expect(screen.queryByText(/Op iPhone of iPad en wil je meldingen\?/)).toBeNull();
	});

	it('standalone, signed out: shows the field with the preview warning', async () => {
		env = installPushEnv({ displayModeStandalone: true, supported: false });
		signedOut();
		render(Login);
		expect(await screen.findByRole('heading', { name: 'Inloglink plakken' })).toBeInTheDocument();
		const warning = screen.getByText(/Verberg linkvoorvertoningen/);
		expect(warning).toHaveTextContent('Kopieer link');
		expect(warning).toHaveTextContent('maar één keer');
		expect(screen.getByLabelText('Inloglink')).toHaveAttribute('aria-describedby', 'paste-link-preview');
	});

	it('standalone, session unknown: no paste section', () => {
		env = installPushEnv({ displayModeStandalone: true, supported: false });
		render(Login);
		expect(screen.queryByRole('heading', { name: 'Inloglink plakken' })).toBeNull();
	});

	it('standalone, valid link: calls verifyOtp', async () => {
		env = installPushEnv({ displayModeStandalone: true, supported: false });
		signedOut();
		auth.verifyOtp.mockResolvedValue(OK);
		render(Login);
		await userEvent.type(await screen.findByLabelText('Inloglink'), LINK);
		await userEvent.click(screen.getByRole('button', { name: 'Inloggen met link' }));
		expect(auth.verifyOtp).toHaveBeenCalledWith({ token_hash: 'abc123', type: 'magiclink' });
	});

	it('standalone, used link: names the preview and hides the raw message', async () => {
		env = installPushEnv({ displayModeStandalone: true, supported: false });
		signedOut();
		auth.verifyOtp.mockResolvedValue(fail(403, 'otp_expired'));
		render(Login);
		await userEvent.type(await screen.findByLabelText('Inloglink'), LINK);
		await userEvent.click(screen.getByRole('button', { name: 'Inloggen met link' }));
		const alert = await screen.findByRole('alert');
		expect(alert).toHaveTextContent(AUTH_MESSAGES.pastedLinkUsed);
		expect(alert).toHaveTextContent('voorvertoning');
		expect(screen.queryByText('x')).toBeNull();
	});

	it('standalone, no valid link: linkInvalid without a verifyOtp call', async () => {
		env = installPushEnv({ displayModeStandalone: true, supported: false });
		signedOut();
		render(Login);
		await userEvent.type(await screen.findByLabelText('Inloglink'), 'geen link');
		await userEvent.click(screen.getByRole('button', { name: 'Inloggen met link' }));
		expect(await screen.findByRole('alert')).toHaveTextContent(AUTH_MESSAGES.linkInvalid);
		expect(auth.verifyOtp).not.toHaveBeenCalled();
	});

	it('standalone, Check je mail: says to copy and paste, with the section below', async () => {
		env = installPushEnv({ displayModeStandalone: true, supported: false });
		signedOut();
		auth.signInWithOtp.mockResolvedValue(OK);
		render(Login);
		await userEvent.type(screen.getByLabelText('E-mailadres'), 'lars@example.com');
		await userEvent.click(screen.getByRole('button', { name: 'Stuur inloglink' }));
		expect(await screen.findByText('Check je mail')).toBeInTheDocument();
		const para = screen.getByText(/We hebben een inloglink gestuurd naar/);
		expect(para).toHaveTextContent('kopieer hem en plak hem hieronder bij ‘Inloglink plakken’');
		expect(para).not.toHaveTextContent('Open de link op dit apparaat');
		expect(screen.getByRole('heading', { name: 'Inloglink plakken' })).toBeInTheDocument();
	});

	it('not standalone, signed out: no paste section', async () => {
		env = installPushEnv({ supported: false });
		signedOut();
		render(Login);
		await screen.findByRole('heading', { name: 'Inloggen' });
		expect(screen.queryByRole('heading', { name: 'Inloglink plakken' })).toBeNull();
	});

	it('iPhone in Safari: shows the install hint', () => {
		env = installPushEnv({ userAgent: IPHONE_UA, supported: false });
		render(Login);
		expect(screen.getByText(/Op iPhone of iPad en wil je meldingen\?/)).toBeInTheDocument();
	});
});
