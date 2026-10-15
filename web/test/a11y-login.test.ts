import { render, screen } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, it, vi } from 'vitest';

const auth = vi.hoisted(() => ({
	signInWithOtp: vi.fn(),
	signOut: vi.fn(),
	onAuthStateChange: vi.fn(),
	verifyOtp: vi.fn()
}));
vi.mock('#lib/supabase.js', () => ({
	supabase: { auth },
	initialUrlHash: '',
	supabaseOrigin: 'http://127.0.0.1:54321'
}));
vi.mock('#lib/push.js', () => ({ releasePushForSignOut: vi.fn(async () => {}) }));

import { initAuth } from '#lib/auth.js';
import { installPushEnv } from './helpers/fake-push.js';
import { expectNoSeriousViolations } from './helpers/axe.js';
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

function signedOut() {
	auth.onAuthStateChange.mockImplementation((cb: (e: string, s: unknown) => void) => {
		cb('INITIAL_SESSION', null);
		return { data: { subscription: { unsubscribe: vi.fn() } } };
	});
	stop = initAuth();
}
const OK = { data: { user: null, session: null }, error: null };

describe('a11y: login page', () => {
	it('form', async () => {
		render(Login);
		await screen.findByLabelText('E-mailadres');
		await expectNoSeriousViolations();
	});
	it('with an error message', async () => {
		render(Login);
		await userEvent.click(await screen.findByRole('button', { name: 'Stuur inloglink' }));
		await screen.findByRole('alert');
		await expectNoSeriousViolations();
	});
	it('link sent', async () => {
		auth.signInWithOtp.mockResolvedValue(OK);
		render(Login);
		await userEvent.type(await screen.findByLabelText('E-mailadres'), 'lars@example.com');
		await userEvent.click(screen.getByRole('button', { name: 'Stuur inloglink' }));
		await screen.findByText('Check je mail');
		await expectNoSeriousViolations();
	});
	it('standalone with "Inloglink plakken"', async () => {
		env = installPushEnv({ displayModeStandalone: true, supported: false });
		signedOut();
		render(Login);
		await screen.findByRole('heading', { name: 'Inloglink plakken' });
		await expectNoSeriousViolations();
	});
});
