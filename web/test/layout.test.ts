import { render, screen, within } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import { createRawSnippet } from 'svelte';
import { writable } from 'svelte/store';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
	initAuth: vi.fn(),
	signOut: vi.fn(),
	initialAuthRedirectError: vi.fn(),
	registerServiceWorker: vi.fn(),
	linkExpired: 'Deze inloglink is verlopen of al gebruikt. Vraag een nieuwe aan.'
}));
const nav = vi.hoisted(() => ({ goto: vi.fn(async () => {}), refreshAll: vi.fn() }));
vi.mock('$app/navigation', () => ({ goto: nav.goto, refreshAll: nav.refreshAll }));
const sessionStore = vi.hoisted(() => ({ current: null as unknown }));

vi.mock('#lib/auth.js', async () => {
	const { writable } = await import('svelte/store');
	sessionStore.current = writable<unknown>(null);
	return {
		session: sessionStore.current,
		initAuth: mocks.initAuth,
		signOut: mocks.signOut,
		initialAuthRedirectError: mocks.initialAuthRedirectError
	};
});
vi.mock('#lib/sw-register.js', () => ({ registerServiceWorker: mocks.registerServiceWorker }));

import { GO_URL_SUMMER } from './fixtures/spot-data.js';
import Layout from '../src/routes/+layout.svelte';

const children = createRawSnippet(() => ({ render: () => '<p>Kind</p>' }));
const store = () => sessionStore.current as ReturnType<typeof writable<unknown>>;

beforeEach(() => {
	vi.clearAllMocks();
	localStorage.clear();
	mocks.initAuth.mockReturnValue(() => {});
	mocks.initialAuthRedirectError.mockReturnValue(null);
	store().set(null);
});

describe('+layout.svelte', () => {
	it('shows attribution in the footer on every page', () => {
		render(Layout, { children });
		const footer = screen.getByRole('contentinfo');
		expect(
			within(footer).getAllByRole('link').some((a) => a.getAttribute('href') === 'https://open-meteo.com/')
		).toBe(true);
		expect(footer.textContent).toContain('Rijkswaterstaat');
	});
	it('has a skip link as the first focusable element and a focusable main (WP-23)', async () => {
		render(Layout, { children });
		const skip = screen.getByRole('link', { name: 'Naar de inhoud' });
		expect(skip).toHaveAttribute('href', '#main');
		await userEvent.tab();
		expect(skip).toHaveFocus();
		const main = screen.getByRole('main');
		expect(main).toHaveAttribute('id', 'main');
		expect(main).toHaveAttribute('tabindex', '-1');
	});
	it('links to the privacy page in the footer (WP-23)', () => {
		render(Layout, { children });
		expect(within(screen.getByRole('contentinfo')).getByRole('link', { name: 'Privacy' })).toHaveAttribute(
			'href',
			'/privacy'
		);
	});
	it('renders children', () => {
		render(Layout, { children });
		expect(screen.getByText('Kind')).toBeInTheDocument();
	});
	it('registers the service worker once, disabled outside production', () => {
		render(Layout, { children });
		expect(mocks.registerServiceWorker).toHaveBeenCalledTimes(1);
		expect(mocks.registerServiceWorker).toHaveBeenCalledWith(navigator, false);
	});
	it('shows Inloggen when signed out', () => {
		render(Layout, { children });
		expect(screen.getByRole('link', { name: 'Inloggen' })).toHaveAttribute('href', '/login');
	});
	it('shows email and Uitloggen when signed in', async () => {
		store().set({ user: { email: 'lars@example.com' } });
		render(Layout, { children });
		expect(screen.getByText('lars@example.com')).toBeInTheDocument();
		await userEvent.click(screen.getByRole('button', { name: 'Uitloggen' }));
		expect(mocks.signOut).toHaveBeenCalled();
	});
	it('WP-18: disables the button while signing out, one call only', async () => {
		store().set({ user: { email: 'lars@example.com' } });
		let resolve!: () => void;
		mocks.signOut.mockReturnValueOnce(new Promise<void>((r) => (resolve = r)));
		render(Layout, { children });
		const user = userEvent.setup();
		await user.click(screen.getByRole('button', { name: 'Uitloggen' }));
		const busy = screen.getByRole('button', { name: 'Uitloggen…' });
		expect(busy).toBeDisabled();
		await user.click(busy);
		expect(mocks.signOut).toHaveBeenCalledTimes(1);
		resolve();
		const again = await screen.findByRole('button', { name: 'Uitloggen' });
		expect(again).toBeEnabled();
	});
	it('WP-16: signed in shows the Alerts and Profiel links', () => {
		store().set({ user: { email: 'lars@example.com' } });
		render(Layout, { children });
		expect(screen.getByRole('link', { name: 'Alerts' })).toHaveAttribute('href', '/alerts');
		expect(screen.getByRole('link', { name: 'Profiel' })).toHaveAttribute('href', '/profiel');
	});
	it('WP-16: signed out or unknown shows neither link', () => {
		const { unmount } = render(Layout, { children });
		expect(screen.queryByRole('link', { name: 'Alerts' })).toBeNull();
		expect(screen.queryByRole('link', { name: 'Profiel' })).toBeNull();
		unmount();
		store().set(undefined);
		render(Layout, { children });
		expect(screen.queryByRole('link', { name: 'Alerts' })).toBeNull();
		expect(screen.queryByRole('link', { name: 'Profiel' })).toBeNull();
	});
	it('shows neither while auth is unknown', () => {
		store().set(undefined);
		render(Layout, { children });
		expect(screen.queryByText('Inloggen')).toBeNull();
		expect(screen.queryByText('Uitloggen')).toBeNull();
	});
	it('shows and dismisses the magic-link error banner', async () => {
		mocks.initialAuthRedirectError.mockReturnValue(mocks.linkExpired);
		render(Layout, { children });
		expect(await screen.findByRole('alert')).toHaveTextContent(mocks.linkExpired);
		await userEvent.click(screen.getByRole('button', { name: 'Sluiten' }));
		expect(screen.queryByRole('alert')).toBeNull();
	});

	describe('WP-20: return after login', () => {
		const PATH = new URL(GO_URL_SUMMER).pathname + new URL(GO_URL_SUMMER).search;
		const save = (savedAt: number) =>
			localStorage.setItem('shakka:return_to', JSON.stringify({ path: PATH, saved_at: savedAt }));

		it('goes back to the saved /go link and removes the key', async () => {
			save(Date.now());
			store().set({ user: { email: 'lars@example.com' } });
			render(Layout, { children });
			await vi.waitFor(() => expect(nav.goto).toHaveBeenCalledWith(PATH, { replace: true }));
			expect(nav.goto).toHaveBeenCalledTimes(1);
			expect(localStorage.getItem('shakka:return_to')).toBeNull();
		});
		it('ignores a key older than 60 minutes but removes it', async () => {
			save(Date.now() - 61 * 60 * 1000);
			store().set({ user: { email: 'lars@example.com' } });
			render(Layout, { children });
			await vi.waitFor(() => expect(localStorage.getItem('shakka:return_to')).toBeNull());
			expect(nav.goto).not.toHaveBeenCalled();
		});
		it('does nothing while signed out and keeps the key', () => {
			save(Date.now());
			render(Layout, { children });
			expect(nav.goto).not.toHaveBeenCalled();
			expect(localStorage.getItem('shakka:return_to')).not.toBeNull();
		});
		it('prunes an expired key at app start while signed out, without navigating', async () => {
			save(Date.now() - 61 * 60 * 1000);
			render(Layout, { children });
			await vi.waitFor(() => expect(localStorage.getItem('shakka:return_to')).toBeNull());
			expect(nav.goto).not.toHaveBeenCalled();
		});
		it('shows Mijn sessies only when signed in', () => {
			const { unmount } = render(Layout, { children });
			expect(screen.queryByRole('link', { name: 'Mijn sessies' })).toBeNull();
			unmount();
			store().set(undefined);
			const second = render(Layout, { children });
			expect(screen.queryByRole('link', { name: 'Mijn sessies' })).toBeNull();
			second.unmount();
			store().set({ user: { email: 'lars@example.com' } });
			render(Layout, { children });
			expect(screen.getByRole('link', { name: 'Mijn sessies' })).toHaveAttribute('href', '/mijn-sessies');
		});
	});
});
