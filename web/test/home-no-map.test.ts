import { render, screen } from '@testing-library/svelte';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { homeData } from './fixtures/map-data.js';
import { favoritesState } from './helpers/fake-favorites.js';

const nav = vi.hoisted(() => ({ refreshAll: vi.fn() }));
vi.mock('$app/navigation', () => ({ refreshAll: nav.refreshAll }));
vi.mock('#lib/supabase.js', () => {
	throw new Error('page tests must not import the Supabase client');
});
vi.mock('#lib/favorites.js', async () => (await import('./helpers/fake-favorites.js')).favoritesModule);
vi.mock('$app/env/public', () => ({ PUBLIC_MAPTILER_KEY: 'testkey123' }));

const probe = vi.hoisted(() => ({ imported: false }));
vi.mock('maplibre-gl', () => {
	probe.imported = true;
	return {};
});

import Page from '../src/routes/+page.svelte';

const fetchSpy = vi.fn();

beforeEach(() => {
	vi.clearAllMocks();
	favoritesState.set({ status: 'signed_out' });
	vi.stubGlobal('fetch', fetchSpy);
});
afterEach(() => vi.unstubAllGlobals());

describe('home page before any map click (AC-3)', () => {
	it('loads no map code and makes no requests', async () => {
		render(Page, { data: homeData() } as never);
		await new Promise((r) => setTimeout(r, 0));
		expect(probe.imported).toBe(false);
		expect(fetchSpy).not.toHaveBeenCalled();
		expect(document.querySelector('[src*="maptiler"], [href*="api.maptiler.com"]')).toBeNull();
		expect(document.querySelector('.map-canvas')).toBeNull();
		expect(screen.getByRole('button', { name: 'Lijst' })).toHaveAttribute('aria-pressed', 'true');
		expect(screen.getByRole('link', { name: 'Teststrand' })).toBeVisible();
	});
});
