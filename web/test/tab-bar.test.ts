import { render, screen, within } from '@testing-library/svelte';
import { createRawSnippet } from 'svelte';
import type { writable } from 'svelte/store';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
	initAuth: vi.fn(),
	signOut: vi.fn(),
	initialAuthRedirectError: vi.fn(),
	registerServiceWorker: vi.fn()
}));
vi.mock('$app/navigation', () => ({ goto: vi.fn(async () => {}), refreshAll: vi.fn() }));
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

describe('tab bar (WP-34)', () => {
	it('signed in: four links', () => {
		store().set({ user: { email: 'lars@example.com' } });
		render(Layout, { children });
		const bar = screen.getByRole('navigation', { name: 'Tabbalk' });
		const links = within(bar).getAllByRole('link');
		expect(links.map((a) => [a.textContent?.trim(), a.getAttribute('href')])).toEqual([
			['Spots', '/'],
			['Alerts', '/alerts'],
			['Mijn sessies', '/mijn-sessies'],
			['Profiel', '/profiel']
		]);
		const svgs = bar.querySelectorAll('svg');
		expect(svgs).toHaveLength(4);
		svgs.forEach((s) => expect(s).toHaveAttribute('aria-hidden', 'true'));
	});
	it('signed out or unknown: no tab bar', () => {
		const { unmount } = render(Layout, { children });
		expect(screen.queryByRole('navigation', { name: 'Tabbalk' })).toBeNull();
		unmount();
		store().set(undefined);
		render(Layout, { children });
		expect(screen.queryByRole('navigation', { name: 'Tabbalk' })).toBeNull();
	});
	it('footer has-tab-bar only when signed in', () => {
		const { unmount } = render(Layout, { children });
		expect(screen.getByRole('contentinfo')).not.toHaveClass('has-tab-bar');
		unmount();
		store().set({ user: { email: 'lars@example.com' } });
		render(Layout, { children });
		expect(screen.getByRole('contentinfo')).toHaveClass('has-tab-bar');
	});
});
