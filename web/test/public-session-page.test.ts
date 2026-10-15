import { render, screen, within } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import { tick } from 'svelte';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { resetRsvpMemory } from '../src/lib/rsvp-storage.js';
import { SESSION_RETENTION_DAYS } from '../src/lib/rsvp-types.js';
import {
	EVA_ID,
	NOOR_ID,
	NOW,
	NOW_ENDED,
	NOW_STALE,
	SANNE_ID,
	SESSION_EVALS,
	SESSION_INFO,
	SLUG,
	TOM_ID,
	publicSessionPageData
} from './fixtures/public-session.js';

const m = vi.hoisted(() => ({
	refreshAll: vi.fn(),
	authSpy: vi.fn(),
	getPublicSession: vi.fn(),
	createRsvp: vi.fn(),
	updateRsvp: vi.fn(),
	deleteRsvp: vi.fn()
}));
vi.mock('$app/navigation', () => ({ refreshAll: m.refreshAll }));
vi.mock('#lib/supabase.js', () => {
	throw new Error('page tests must not import the Supabase client');
});
vi.mock('#lib/auth.js', () => ({ session: { subscribe: m.authSpy } }));
vi.mock('#lib/rsvp.js', () => ({
	getPublicSession: m.getPublicSession,
	createRsvp: m.createRsvp,
	updateRsvp: m.updateRsvp,
	deleteRsvp: m.deleteRsvp
}));

import Page from '../src/routes/s/[slug]/+page.svelte';

const props = (data: unknown) => ({ data }) as never;
const hourOf = (time: string): HTMLElement =>
	screen.getByText(time, { selector: 'time' }).closest('.hour') as HTMLElement;

beforeEach(() => {
	vi.clearAllMocks();
	localStorage.clear();
	resetRsvpMemory();
	vi.useFakeTimers({ toFake: ['Date'] });
	vi.setSystemTime(new Date(NOW));
});
afterEach(() => {
	vi.restoreAllMocks();
	vi.useRealTimers();
});

describe('public session page (AC-2)', () => {
	it('(a) shows the session, participants, carpool and hours', async () => {
		const { container } = render(Page, props(publicSessionPageData()));
		expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('Kitesessie: Teststrand');
		expect(container.querySelector('.session-when')).toHaveTextContent('za 18 jul 14:00–18:00');
		expect(container.querySelector('.session-organizer')).toHaveTextContent('Georganiseerd door Lars');
		expect(screen.getByRole('link', { name: 'Naar de spotpagina van Teststrand' })).toHaveAttribute(
			'href',
			'/spot/test-strand'
		);
		expect(screen.getByText('Parkeren bij de strandopgang')).toBeInTheDocument();
		const tikkie = screen.getByRole('link', { name: 'Open betaalverzoek' });
		expect(tikkie).toHaveAttribute('href', 'https://tikkie.me/pay/test');
		expect(tikkie).toHaveAttribute('target', '_blank');
		expect(tikkie).toHaveAttribute('rel', 'noopener noreferrer');
		expect(screen.getByText('(link naar tikkie.me)')).toBeInTheDocument();

		expect(screen.getByRole('heading', { name: 'Deelnemers (5)' })).toBeInTheDocument();
		const org = container.querySelector('li.organizer')!;
		expect(org).toHaveTextContent('Lars');
		expect(org).toHaveTextContent('organisator');
		const rsvp = (id: string) => container.querySelector(`[data-rsvp="${id}"]`)!;
		expect(rsvp(EVA_ID)).toHaveTextContent('Biedt een lift aan (2 plekken)');
		expect(rsvp(SANNE_ID)).toHaveTextContent('Rijdt mee met Eva');
		expect(rsvp(NOOR_ID)).toHaveTextContent('Zoekt een lift');
		expect(rsvp(TOM_ID)).toHaveTextContent('Rijdt zelf');
		expect(container.querySelector('.carpool')).toHaveTextContent('Vrije plekken bij Lars: 3');
		expect(container.querySelector('.carpool')).toHaveTextContent('Vertrekpunt: Utrecht CS');
		const driver = container.querySelector(`[data-driver="${EVA_ID}"]`)!;
		expect(driver).toHaveTextContent('2 plekken');
		expect(driver).toHaveTextContent('meerijders: Sanne');
		expect(container.querySelector(`[data-seeker="${NOOR_ID}"]`)).toBeInTheDocument();

		for (const t of ['14:00', '15:00', '16:00', '17:00']) {
			expect(screen.getByText(t, { selector: 'time' })).toBeInTheDocument();
		}
		expect(within(hourOf('17:00')).getByText('Niet gaan')).toBeInTheDocument();
		expect(within(hourOf('17:00')).getByText('Aflandige wind: niet kiten')).toBeInTheDocument();
		expect(screen.getByText('Bijgewerkt: za 18 jul 10:05')).toBeInTheDocument();
		expect(m.authSpy).not.toHaveBeenCalled();
		await tick();
		const bdis = [...container.querySelectorAll('bdi')].map((b) => b.textContent);
		expect(bdis).toContain('Eva');
	});

	it('(b) AC-5: noindex, cancelled and ended', () => {
		const first = render(Page, props(publicSessionPageData()));
		expect(document.head.querySelector('meta[name="robots"]')).toHaveAttribute('content', 'noindex');
		first.unmount();
		const nf = render(Page, props({ kind: 'not_found', now: NOW, slug: SLUG }));
		expect(document.head.querySelector('meta[name="robots"]')).toHaveAttribute('content', 'noindex');
		nf.unmount();

		const c = render(
			Page,
			props(publicSessionPageData({ session: { ...SESSION_INFO, cancelled: true } }))
		);
		expect(screen.getByRole('alert')).toHaveTextContent('Deze sessie is geannuleerd');
		expect(screen.queryByLabelText('Voornaam')).toBeNull();
		expect(screen.queryByRole('button', { name: 'Ik ook' })).toBeNull();
		expect(screen.queryByText(/ouder dan 3 uur/)).toBeNull();
		c.unmount();

		render(Page, props(publicSessionPageData({ now: NOW_ENDED })));
		expect(screen.getByText(/Deze sessie is voorbij/)).toBeInTheDocument();
		expect(screen.queryByLabelText('Voornaam')).toBeNull();
	});

	it('(c) AC-6: attribution', () => {
		render(Page, props(publicSessionPageData()));
		const links = screen.getAllByRole('link');
		expect(links.some((l) => l.getAttribute('href') === 'https://open-meteo.com/')).toBe(true);
		expect(screen.getAllByText(/Rijkswaterstaat/).length).toBeGreaterThan(0);
	});

	it('(d) not found and error', async () => {
		const a = render(Page, props({ kind: 'not_found', now: NOW, slug: SLUG }));
		expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('Sessie niet gevonden');
		expect(
			screen.getByText(`Deze sessie bestaat niet (meer). Sessies verdwijnen ${SESSION_RETENTION_DAYS} dagen na afloop.`)
		).toBeInTheDocument();
		a.unmount();
		render(Page, props({ kind: 'error', now: NOW, slug: SLUG }));
		expect(screen.getByRole('alert')).toHaveTextContent('De sessie kon niet worden geladen');
		await userEvent.setup().click(screen.getByRole('button', { name: 'Opnieuw proberen' }));
		expect(m.refreshAll).toHaveBeenCalledTimes(1);
	});

	it('(e) stale data warns', () => {
		render(Page, props(publicSessionPageData({ now: NOW_STALE })));
		expect(screen.getByRole('alert')).toHaveTextContent('ouder dan 3 uur');
	});

	it('(f) evaluations null or empty', () => {
		const a = render(Page, props(publicSessionPageData({ evaluations: null })));
		expect(screen.getByText('Het oordeel kon niet worden geladen.')).toBeInTheDocument();
		a.unmount();
		render(Page, props(publicSessionPageData({ evaluations: [] })));
		expect(screen.getByText('Er is nog geen oordeel voor dit tijdvenster.')).toBeInTheDocument();
	});

	it('(g) window over midnight gets day headings', () => {
		const evals = [
			{ ...SESSION_EVALS[0], valid_at: '2026-07-18T21:00:00+00:00' },
			{ ...SESSION_EVALS[1], valid_at: '2026-07-18T23:00:00+00:00' }
		];
		const { container } = render(
			Page,
			props(
				publicSessionPageData({
					session: {
						...SESSION_INFO,
						starts_at: '2026-07-18T20:00:00+00:00',
						ends_at: '2026-07-19T02:00:00+00:00'
					},
					evaluations: evals
				})
			)
		);
		expect(container.querySelector('.session-when')).toHaveTextContent('za 18 jul 22:00 – zo 19 jul 04:00');
		expect(screen.getByRole('heading', { level: 3, name: 'za 18 jul' })).toBeInTheDocument();
		expect(screen.getByRole('heading', { level: 3, name: 'zo 19 jul' })).toBeInTheDocument();
	});

	it('(h) bad Tikkie links and blank notes are hidden', () => {
		for (const url of ['http://tikkie.me/x', 'https://evil.example/pay/x']) {
			const r = render(
				Page,
				props(publicSessionPageData({ session: { ...SESSION_INFO, tikkie_url: url } }))
			);
			expect(screen.queryByRole('link', { name: 'Open betaalverzoek' })).toBeNull();
			expect(screen.queryByText(/link naar/)).toBeNull();
			r.unmount();
		}
		render(Page, props(publicSessionPageData({ session: { ...SESSION_INFO, note: '   ' } })));
		expect(screen.queryByRole('heading', { name: 'Notitie' })).toBeNull();
	});

	it('(i) resume refreshes when data is old', () => {
		const old = new Date(Date.now() - 20 * 60 * 1000).toISOString();
		render(Page, props(publicSessionPageData({ now: old })));
		Object.defineProperty(document, 'visibilityState', { configurable: true, get: () => 'visible' });
		document.dispatchEvent(new Event('visibilitychange'));
		expect(m.refreshAll).toHaveBeenCalledTimes(1);
	});

	it('(j) clock: the form closes itself after ends_at', async () => {
		vi.useRealTimers();
		vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout', 'Date'] });
		vi.setSystemTime(new Date('2026-07-18T15:59:00.000Z'));
		const r = render(Page, props(publicSessionPageData({ now: '2026-07-18T15:59:00.000Z' })));
		await tick();
		expect(screen.getByLabelText('Voornaam')).toBeInTheDocument();
		expect(screen.getByRole('button', { name: 'Ik ook' })).toBeInTheDocument();
		vi.advanceTimersByTime(61_000);
		await tick();
		expect(screen.queryByLabelText('Voornaam')).toBeNull();
		expect(screen.getByText(/Deze sessie is voorbij/)).toBeInTheDocument();
		r.unmount();
		vi.useRealTimers();
		vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout', 'Date'] });
		vi.setSystemTime(new Date('2026-07-18T15:59:00.000Z'));
		const base = vi.getTimerCount();
		const r2 = render(Page, props(publicSessionPageData({ now: '2026-07-18T15:59:00.000Z' })));
		await tick();
		expect(vi.getTimerCount()).toBeGreaterThan(base);
		r2.unmount();
		expect(vi.getTimerCount()).toBe(base);
	});
});
