import { render, screen } from '@testing-library/svelte';
import { beforeEach, describe, it, vi } from 'vitest';
import { homeData } from './fixtures/map-data.js';
import { favoritesState } from './helpers/fake-favorites.js';
import { USER_ID } from './helpers/fake-session.js';
import { expectNoSeriousViolations } from './helpers/axe.js';

const nav = vi.hoisted(() => ({ refreshAll: vi.fn() }));
vi.mock('$app/navigation', () => ({ refreshAll: nav.refreshAll }));
vi.mock('#lib/supabase.js', () => {
	throw new Error('page tests must not import the Supabase client');
});
vi.mock('#lib/favorites.js', async () => (await import('./helpers/fake-favorites.js')).favoritesModule);
vi.mock('$app/env/public', () => ({ PUBLIC_MAPTILER_KEY: 'testkey123' }));
vi.mock('maplibre-gl', () => ({}));

import Page from '../src/routes/+page.svelte';

beforeEach(() => {
	vi.clearAllMocks();
	favoritesState.set({ status: 'signed_out' });
});

describe('a11y: home', () => {
	it('list, signed out', async () => {
		render(Page, { data: homeData() } as never);
		await screen.findByRole('link', { name: 'Teststrand' });
		await expectNoSeriousViolations();
	});
	it('list, signed in with favorites (stars)', async () => {
		favoritesState.set({ status: 'ready', userId: USER_ID, ids: new Set(['test-meer']) });
		render(Page, { data: homeData() } as never);
		await screen.findByRole('button', { name: 'Favoriet: Testmeer' });
		await expectNoSeriousViolations();
	});
	it('error banner', async () => {
		render(Page, { data: homeData({ kind: 'error' }) } as never);
		await screen.findByRole('alert');
		await expectNoSeriousViolations();
	});
});
