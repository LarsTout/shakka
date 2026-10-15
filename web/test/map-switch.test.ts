import { render, screen, waitFor } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { MAP_FAILURE_MESSAGE_NL } from '../src/lib/map/config.js';
import { homeData } from './fixtures/map-data.js';
import { favoritesState } from './helpers/fake-favorites.js';
import { USER_ID } from './helpers/fake-session.js';
import { createFakeMapLibre } from './helpers/fake-maplibre.js';

const nav = vi.hoisted(() => ({ refreshAll: vi.fn() }));
vi.mock('$app/navigation', () => ({ refreshAll: nav.refreshAll }));
vi.mock('#lib/supabase.js', () => {
	throw new Error('page tests must not import the Supabase client');
});
vi.mock('#lib/favorites.js', async () => (await import('./helpers/fake-favorites.js')).favoritesModule);

const p = vi.hoisted(() => ({ key: 'testkey123', webgl: true, load: vi.fn() }));
vi.mock('#lib/map/platform.js', () => ({
	getMaptilerKey: () => p.key,
	supportsWebGL2: () => p.webgl,
	loadMapLibre: () => p.load()
}));

import Page from '../src/routes/+page.svelte';

let fake: ReturnType<typeof createFakeMapLibre>;
const renderPage = () => render(Page, { data: homeData() } as never);
const list = () => document.querySelector('ul.spot-list') as HTMLElement;
const mapButton = () => screen.getByRole('button', { name: 'Kaart' });
const listButton = () => screen.getByRole('button', { name: 'Lijst' });

beforeEach(() => {
	vi.clearAllMocks();
	favoritesState.set({ status: 'signed_out' });
	fake = createFakeMapLibre();
	p.key = 'testkey123';
	p.webgl = true;
	p.load.mockReset();
	p.load.mockResolvedValue(fake.lib);
});

describe('map switch', () => {
	it('without a key: notice, list stays', async () => {
		p.key = '';
		renderPage();
		await userEvent.click(mapButton());
		expect(screen.getByRole('status')).toHaveTextContent(MAP_FAILURE_MESSAGE_NL.no_key);
		expect(listButton()).toHaveAttribute('aria-pressed', 'true');
		expect(list()).not.toHaveAttribute('hidden');
		expect(list()).toBeVisible();
		expect(screen.getByRole('link', { name: 'Teststrand' })).toHaveAttribute('href', '/spot/test-strand');
		expect(p.load).not.toHaveBeenCalled();
		expect(document.querySelector('.map-canvas')).toBeNull();
		expect(screen.queryByRole('alert')).toBeNull();
	});

	it('without WebGL2: notice and no load', async () => {
		p.webgl = false;
		renderPage();
		await userEvent.click(mapButton());
		expect(screen.getByRole('status')).toHaveTextContent(MAP_FAILURE_MESSAGE_NL.no_webgl);
		expect(p.load).not.toHaveBeenCalled();
	});

	it('success: map visible, list hidden, back to list cleans up', async () => {
		renderPage();
		await userEvent.click(mapButton());
		expect(mapButton()).toHaveAttribute('aria-pressed', 'true');
		expect(list()).toHaveAttribute('hidden');
		expect(document.querySelector('.map-canvas')).not.toBeNull();
		await waitFor(() => expect(fake.maps).toHaveLength(1));
		fake.maps[0]!.emit('load');
		expect(document.querySelectorAll('[data-marker-spot]')).toHaveLength(3);
		expect(document.querySelector('[data-spot="test-meer"]')?.tagName).toBe('LI');
		await userEvent.click(listButton());
		expect(list()).not.toHaveAttribute('hidden');
		expect(fake.maps[0]!.remove).toHaveBeenCalled();
		expect(document.querySelector('.map-canvas')).toBeNull();
	});

	it('load failure: notice, list back, retry possible', async () => {
		p.load.mockRejectedValue(new Error('offline'));
		vi.spyOn(console, 'warn').mockImplementation(() => {});
		renderPage();
		await userEvent.click(mapButton());
		await waitFor(() => expect(screen.getByRole('status')).toHaveTextContent(MAP_FAILURE_MESSAGE_NL.load_failed));
		expect(list()).not.toHaveAttribute('hidden');
		expect(listButton()).toHaveAttribute('aria-pressed', 'true');
		await userEvent.click(mapButton());
		await waitFor(() => expect(p.load).toHaveBeenCalledTimes(2));
	});

	it('a second click while the map is open does nothing', async () => {
		renderPage();
		await userEvent.click(mapButton());
		await userEvent.click(mapButton());
		await waitFor(() => expect(fake.maps).toHaveLength(1));
		expect(p.load).toHaveBeenCalledTimes(1);
	});

	it('favourites survive a trip to the map', async () => {
		favoritesState.set({ status: 'ready', userId: USER_ID, ids: new Set(['test-meer']) });
		renderPage();
		const star = () => screen.getByRole('button', { name: 'Favoriet: Testmeer', hidden: true });
		expect(star()).toHaveAttribute('aria-pressed', 'true');
		await userEvent.click(mapButton());
		await userEvent.click(listButton());
		expect(star()).toHaveAttribute('aria-pressed', 'true');
	});
});
