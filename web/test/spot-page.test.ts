import { render, screen, within } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { favoritesState, toggleFavoriteMock } from './helpers/fake-favorites.js';
import { SESSION, USER_ID, sessionStore } from './helpers/fake-session.js';
import { WAVES_NOTE_NL } from '../src/lib/marine.js';
import {
	EVAL_DARK,
	EVAL_LOWCONF,
	EVAL_OFFSHORE,
	EVAL_TOMORROW,
	MARINE_FRESH,
	MARINE_STALE,
	NOW_FRESH,
	NOW_STALE,
	SPOT_VERIFIED,
	pageData
} from './fixtures/spot-data.js';

const nav = vi.hoisted(() => ({ refreshAll: vi.fn() }));
vi.mock('$app/navigation', () => ({ refreshAll: nav.refreshAll }));
// Pages must not create a real Supabase client (review N-2); fail loudly if they do.
vi.mock('#lib/supabase.js', () => {
	throw new Error('page tests must not import the Supabase client');
});

vi.mock('#lib/auth.js', async () => (await import('./helpers/fake-session.js')).authModule);
vi.mock('#lib/favorites.js', async () => (await import('./helpers/fake-favorites.js')).favoritesModule);

import Page from '../src/routes/spot/[id]/+page.svelte';

const props = (data: unknown) => ({ data }) as never;
const hourOf = (time: string): HTMLElement =>
	screen.getByText(time, { selector: 'time' }).closest('.hour') as HTMLElement;

beforeEach(() => {
	vi.clearAllMocks();
	favoritesState.set({ status: 'signed_out' });
	sessionStore.set(null);
});

describe('spot page (AC-3)', () => {
	it('shows hours with verdict text, direction and reasons as Dutch labels', () => {
		render(Page, props(pageData()));
		expect(screen.getByText('14:00', { selector: 'time' })).toHaveAttribute(
			'datetime',
			'2026-07-15T12:00:00+00:00'
		);
		expect(within(hourOf('14:00')).getByText('Go')).toBeInTheDocument();

		const off = hourOf('15:00');
		expect(off.querySelector('[data-verdict="no_go"]')).toHaveTextContent('Niet gaan');
		expect(within(off).getByText('Aflandige wind: niet kiten')).toBeInTheDocument();
		expect(within(off).getByText('Aflandig')).toBeInTheDocument();

		expect(within(hourOf('16:00')).getByText('Weermodellen zijn het oneens')).toBeInTheDocument();
		expect(screen.queryByText('offshore')).toBeNull();
		expect(screen.queryByText('low_confidence')).toBeNull();
	});

	it('unverified banner only for unverified spots', () => {
		const { unmount } = render(Page, props(pageData()));
		expect(screen.getByText(/niet geverifieerd/i)).toBeInTheDocument();
		unmount();
		render(Page, props(pageData({ spot: SPOT_VERIFIED })));
		expect(screen.queryByText(/niet geverifieerd/i)).toBeNull();
	});

	it('freshness: warning when stale, updated line when fresh', () => {
		const { unmount } = render(Page, props(pageData({ now: NOW_STALE })));
		expect(screen.getByRole('alert')).toHaveTextContent('ouder dan 3 uur');
		unmount();
		render(Page, props(pageData({ now: NOW_FRESH })));
		expect(screen.queryByRole('alert')).toBeNull();
		expect(screen.getByText('Bijgewerkt: wo 15 jul 14:05')).toBeInTheDocument();
	});

	it('shows attribution', () => {
		render(Page, props(pageData()));
		const links = screen.getAllByRole('link');
		expect(links.some((l) => l.getAttribute('href') === 'https://open-meteo.com/')).toBe(true);
		expect(screen.getAllByText('Rijkswaterstaat').length).toBeGreaterThan(0);
	});

	it('day headings, dark toggle and tides', async () => {
		render(Page, props(pageData()));
		expect(screen.getByRole('heading', { name: 'Vandaag (wo 15 jul)' })).toBeInTheDocument();
		expect(screen.getByRole('heading', { name: 'Morgen (do 16 jul)' })).toBeInTheDocument();
		expect(screen.queryByText('23:00', { selector: 'time' })).toBeNull();
		const toggle = screen.getByRole('button', { name: 'Toon ook donkere uren' });
		expect(toggle).toHaveAttribute('aria-pressed', 'false');
		await userEvent.click(toggle);
		expect(screen.getByText('23:00', { selector: 'time' })).toBeInTheDocument();
		expect(screen.getByRole('button', { name: 'Verberg donkere uren' })).toHaveAttribute(
			'aria-pressed',
			'true'
		);
		const tides = [...document.querySelectorAll('.tides')].map((t) => t.textContent?.replace(/\s+/g, ' ').trim());
		expect(tides).toEqual([
			'Getij: Hoogwater 11:10 (+95 cm) · Laagwater 17:40 (-70 cm)',
			'Getij: geen gegevens'
		]);
	});

	it('profile', () => {
		render(Page, props(pageData()));
		expect(screen.getByText('Onbekend (nog niet ingevuld)')).toBeInTheDocument();
		expect(screen.getByText('1 mei t/m 30 sep, 10:00–18:00')).toBeInTheDocument();
		expect(screen.getByText('Voorkeur laagwater')).toBeInTheDocument();
		expect(screen.getByText('teststation')).toBeInTheDocument();
		const hazards = screen.getByText(/Testgevaar: zandbank/);
		expect(hazards).toHaveClass('prewrap');
		expect(hazards.textContent).toContain('Tweede regel');
		expect(screen.getByText('Niet ingevuld')).toBeInTheDocument();
	});

	it('no evaluations', () => {
		render(Page, props(pageData({ evaluations: [] })));
		expect(screen.getByText('Nog geen data voor deze spot.')).toBeInTheDocument();
		expect(screen.queryByRole('alert')).toBeNull();
	});

	it('not_found and error states', async () => {
		const { unmount } = render(Page, props({ kind: 'not_found', now: NOW_FRESH, id: 'x' }));
		expect(screen.getByRole('heading', { name: 'Spot niet gevonden' })).toBeInTheDocument();
		unmount();
		render(Page, props({ kind: 'error', now: NOW_FRESH, id: 'x' }));
		expect(screen.getByRole('alert')).toHaveTextContent('De gegevens konden niet worden geladen');
		await userEvent.click(screen.getByRole('button', { name: 'Opnieuw proberen' }));
		expect(nav.refreshAll).toHaveBeenCalledTimes(1);
	});

	describe('resume', () => {
		const fire = () => {
			Object.defineProperty(document, 'visibilityState', { value: 'visible', configurable: true });
			document.dispatchEvent(new Event('visibilitychange'));
		};
		it('refreshes when data is older than 10 minutes', () => {
			render(Page, props(pageData({ now: new Date(Date.now() - 20 * 60_000).toISOString() })));
			fire();
			expect(nav.refreshAll).toHaveBeenCalledTimes(1);
		});
		it('does not refresh fresh data', () => {
			render(Page, props(pageData({ now: new Date().toISOString() })));
			fire();
			expect(nav.refreshAll).not.toHaveBeenCalled();
		});
	});
});

describe('favorite star on the spot page (WP-16)', () => {
	it('signed out: no star', () => {
		render(Page, props(pageData()));
		expect(screen.queryByRole('button', { name: /^Favoriet:/ })).toBeNull();
	});

	it('ready: the star sits in .title-row next to the h1', async () => {
		favoritesState.set({ status: 'ready', userId: USER_ID, ids: new Set() });
		render(Page, props(pageData()));
		const star = screen.getByRole('button', { name: 'Favoriet: Teststrand' });
		expect(star).toHaveAttribute('aria-pressed', 'false');
		const row = star.closest('.title-row') as HTMLElement;
		expect(row).not.toBeNull();
		expect(within(row).getByRole('heading', { level: 1 })).toHaveTextContent('Teststrand');
		await userEvent.click(star);
		expect(toggleFavoriteMock).toHaveBeenCalledWith('test-strand');
	});
});

describe('waves (WP-12, AC-6)', () => {
	it('shows one wave line under the matching hour, plus the note', () => {
		render(Page, props(pageData({ marine: [MARINE_FRESH] })));
		const li = hourOf('14:00').closest('li') as HTMLElement;
		const waves = li.querySelector('.waves');
		expect(waves).toHaveTextContent('Golven 1,2 m, periode 5 s, uit WZW (250°)');
		expect(document.querySelectorAll('.waves')).toHaveLength(1);
		expect(screen.getByText(WAVES_NOTE_NL)).toBeInTheDocument();
	});

	it('without wave data: no wave line, no note, no alert', () => {
		render(Page, props(pageData()));
		expect(document.querySelectorAll('.waves')).toHaveLength(0);
		expect(document.querySelector('.waves-note')).toBeNull();
		expect(screen.queryByRole('alert')).toBeNull();
	});

	it('hides stale wave data', () => {
		render(Page, props(pageData({ marine: [MARINE_STALE] })));
		expect(document.querySelectorAll('.waves')).toHaveLength(0);
		expect(document.querySelector('.waves-note')).toBeNull();
	});

	it('no note when the only wave row belongs to a hidden (dark) hour', () => {
		const dark = { ...MARINE_FRESH, valid_at: '2026-07-15T21:00:00+00:00' };
		render(Page, props(pageData({ marine: [dark] })));
		expect(document.querySelectorAll('.waves')).toHaveLength(0);
		expect(document.querySelector('.waves-note')).toBeNull();
	});
});

describe('Ik ga links (WP-20, A16)', () => {
	const goLinks = () => screen.queryAllByRole('link', { name: /^Ik ga/ });

	it('(a) signed in: one link per go run, with the go href', () => {
		sessionStore.set(SESSION);
		render(Page, props(pageData()));
		const links = goLinks();
		expect(links.map((a) => a.textContent)).toEqual(['Ik ga 14:00–15:00', 'Ik ga 10:00–11:00']);
		expect(links[0]).toHaveAttribute(
			'href',
			'/go?spot=test-strand&start=2026-07-15T12%3A00%3A00Z&end=2026-07-15T13%3A00%3A00Z'
		);
		expect(links[1]).toHaveAttribute(
			'href',
			'/go?spot=test-strand&start=2026-07-16T08%3A00%3A00Z&end=2026-07-16T09%3A00%3A00Z'
		);
	});
	it('(b) a day without go hours has no link', () => {
		sessionStore.set(SESSION);
		render(
			Page,
			props(pageData({ evaluations: [EVAL_OFFSHORE, EVAL_LOWCONF, EVAL_DARK, EVAL_TOMORROW] }))
		);
		expect(goLinks().map((a) => a.textContent)).toEqual(['Ik ga 10:00–11:00']);
	});
	it('(c) signed out or unknown: no links, hours still shown', () => {
		const { unmount } = render(Page, props(pageData()));
		expect(goLinks()).toHaveLength(0);
		expect(screen.getAllByText('14:00', { selector: 'time' }).length).toBeGreaterThan(0);
		unmount();
		sessionStore.set(undefined);
		render(Page, props(pageData()));
		expect(goLinks()).toHaveLength(0);
	});
});
