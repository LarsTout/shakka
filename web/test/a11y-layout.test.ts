import { render, screen } from '@testing-library/svelte';
import { createRawSnippet } from 'svelte';
import type { writable } from 'svelte/store';
import { beforeEach, describe, it, vi } from 'vitest';

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
import { expectNoSeriousViolations } from './helpers/axe.js';

const children = createRawSnippet(() => ({ render: () => '<h1>Kind</h1>' }));
const store = () => sessionStore.current as ReturnType<typeof writable<unknown>>;

beforeEach(() => {
	vi.clearAllMocks();
	localStorage.clear();
	mocks.initAuth.mockReturnValue(() => {});
	mocks.initialAuthRedirectError.mockReturnValue(null);
	store().set(null);
});

describe('a11y: layout', () => {
	it('signed out', async () => {
		render(Layout, { children });
		await screen.findByRole('link', { name: 'Inloggen' });
		await expectNoSeriousViolations();
	});
	it('signed in', async () => {
		store().set({ user: { email: 'lars@example.com' } });
		render(Layout, { children });
		await screen.findByRole('link', { name: 'Profiel' });
		await expectNoSeriousViolations();
	});
	it('with the error banner', async () => {
		mocks.initialAuthRedirectError.mockReturnValue('Deze inloglink is verlopen.');
		render(Layout, { children });
		await screen.findByRole('alert');
		await expectNoSeriousViolations();
	});
});
