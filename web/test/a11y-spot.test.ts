import { render, screen } from '@testing-library/svelte';
import { beforeEach, describe, it, vi } from 'vitest';
import { favoritesState } from './helpers/fake-favorites.js';
import { USER_ID, sessionStore } from './helpers/fake-session.js';
import { expectNoSeriousViolations } from './helpers/axe.js';
import { MARINE_FRESH, SPOT_VERIFIED, pageData } from './fixtures/spot-data.js';

const nav = vi.hoisted(() => ({ refreshAll: vi.fn() }));
vi.mock('$app/navigation', () => ({ refreshAll: nav.refreshAll }));
vi.mock('#lib/supabase.js', () => {
	throw new Error('page tests must not import the Supabase client');
});
vi.mock('#lib/auth.js', async () => (await import('./helpers/fake-session.js')).authModule);
vi.mock('#lib/favorites.js', async () => (await import('./helpers/fake-favorites.js')).favoritesModule);

import Page from '../src/routes/spot/[id]/+page.svelte';

const props = (data: unknown) => ({ data }) as never;

beforeEach(() => {
	vi.clearAllMocks();
	favoritesState.set({ status: 'signed_out' });
	sessionStore.set(null);
});

describe('a11y: spot page', () => {
	it('with waves, signed out', async () => {
		render(Page, props(pageData({ marine: [MARINE_FRESH] })));
		await screen.findByText('14:00', { selector: 'time' });
		await expectNoSeriousViolations();
	});
	it('signed in with the favorite star', async () => {
		favoritesState.set({ status: 'ready', userId: USER_ID, ids: new Set() });
		render(Page, props(pageData()));
		await screen.findByRole('button', { name: 'Favoriet: Teststrand' });
		await expectNoSeriousViolations();
	});
	it('unverified spot', async () => {
		render(Page, props(pageData()));
		await screen.findByText(/niet geverifieerd/i);
		await expectNoSeriousViolations();
	});
	it('verified spot', async () => {
		render(Page, props(pageData({ spot: SPOT_VERIFIED })));
		await screen.findByText('14:00', { selector: 'time' });
		await expectNoSeriousViolations();
	});
});
