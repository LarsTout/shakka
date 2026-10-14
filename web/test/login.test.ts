import { render, screen } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const auth = vi.hoisted(() => ({
	signInWithOtp: vi.fn(),
	signOut: vi.fn(),
	onAuthStateChange: vi.fn()
}));
vi.mock('#lib/supabase.js', () => ({ supabase: { auth }, initialUrlHash: '' }));

import { AUTH_MESSAGES } from '#lib/auth.js';
import Login from '../src/routes/login/+page.svelte';

beforeEach(() => vi.clearAllMocks());

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
			options: { emailRedirectTo: window.location.origin, shouldCreateUser: false }
		});
		expect(await screen.findByText('Check je mail')).toBeInTheDocument();
		expect(screen.getByText(/lars@example\.com/)).toBeInTheDocument();
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
