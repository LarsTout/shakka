import { fireEvent, render, screen } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { createFakeSupabase } from './helpers/fake-supabase.js';
import { writeCalls } from './helpers/fake-supabase.js';

const fake = vi.hoisted(() => ({ current: null as unknown as ReturnType<typeof createFakeSupabase> }));
vi.mock('#lib/supabase.js', async () => {
	const { createFakeSupabase } = await import('./helpers/fake-supabase.js');
	fake.current = createFakeSupabase();
	return { supabase: fake.current.client, initialUrlHash: '' };
});
vi.mock('#lib/auth.js', async () => (await import('./helpers/fake-session.js')).authModule);
const nav = vi.hoisted(() => ({ goto: vi.fn(async () => {}), refreshAll: vi.fn() }));
vi.mock('$app/navigation', () => ({ goto: nav.goto, refreshAll: nav.refreshAll }));

import { load as goLoad } from '../src/routes/go/+page.js';
import { load } from '../src/routes/sessie/nieuw/+page.js';
import Page from '../src/routes/sessie/nieuw/+page.svelte';
import { SESSION_ERROR_MESSAGES } from '../src/lib/sessions.js';
import { GO_URL_DST_DAY, GO_URL_DST_NIGHT, NOW_SESSIONS, SLUG } from './fixtures/session-data.js';
import { GO_URL_SUMMER, SPOT_UNVERIFIED, SPOT_VERIFIED } from './fixtures/spot-data.js';
import { SESSION, sessionStore } from './helpers/fake-session.js';

const SPOTS = [SPOT_UNVERIFIED, SPOT_VERIFIED];
const dataFor = (goUrl: string) => {
	const { target } = (goLoad as (e: unknown) => { target: string })({ url: new URL(goUrl) });
	return (load as (e: unknown) => unknown)({ url: new URL('https://example.org' + target) });
};
const props = (data: unknown) => ({ data }) as never;
const field = (label: string) => screen.getByLabelText(label) as HTMLInputElement;

beforeEach(() => {
	vi.clearAllMocks();
	fake.current.reset();
	localStorage.clear();
	sessionStore.set(undefined);
	vi.useFakeTimers({ toFake: ['Date'] });
	vi.setSystemTime(new Date(NOW_SESSIONS));
});
afterEach(() => vi.useRealTimers());

async function drawFor(goUrl: string) {
	fake.current.respond('spots', { data: SPOTS, error: null });
	sessionStore.set(SESSION);
	render(Page, props(dataFor(goUrl)));
	await screen.findByLabelText('Datum');
}

describe('new session page', () => {
	it('(a) signed out: login prompt, no calls', async () => {
		sessionStore.set(null);
		render(Page, props(dataFor(GO_URL_SUMMER)));
		expect(screen.getByText('Log in om een sessie aan te maken.')).toBeInTheDocument();
		await new Promise((r) => setTimeout(r, 0));
		expect(fake.current.calls).toHaveLength(0);
	});
	it('(b) prefills from the go link', async () => {
		await drawFor(GO_URL_SUMMER);
		expect(field('Spot').value).toBe('test-strand');
		expect(field('Datum').value).toBe('2026-07-18');
		expect(field('Van').value).toBe('14:00');
		expect(field('Tot').value).toBe('18:00');
	});
	it('(c) prefills around the switch to winter time', async () => {
		await drawFor(GO_URL_DST_DAY);
		expect([field('Van').value, field('Tot').value]).toEqual(['11:00', '15:00']);
	});
	it('(d) remembered name is prefilled', async () => {
		localStorage.setItem('shakka:organizer_name', 'Lars');
		await drawFor(GO_URL_SUMMER);
		expect(field('Je voornaam').value).toBe('Lars');
	});
	it('(e) saves once, goes to the share page and remembers the name', async () => {
		await drawFor(GO_URL_DST_NIGHT);
		expect([field('Datum').value, field('Van').value, field('Tot').value]).toEqual([
			'2026-10-25',
			'02:00',
			'03:00'
		]);
		await fireEvent.input(field('Je voornaam'), { target: { value: 'Lars' } });
		fake.current.respond('sessions', { data: { slug: SLUG }, error: null });
		await fireEvent.click(screen.getByRole('button', { name: 'Sessie aanmaken' }));
		await vi.waitFor(() => expect(nav.goto).toHaveBeenCalled());
		const writes = writeCalls(fake.current.calls);
		expect(writes).toHaveLength(1);
		expect(writes[0]!.ops[0]).toEqual([
			'insert',
			{
				spot_id: 'test-strand',
				organizer_name: 'Lars',
				starts_at: '2026-10-25T00:00:00.000Z',
				ends_at: '2026-10-25T02:00:00.000Z',
				note: null,
				seats_free: null,
				departure_point: null,
				tikkie_url: null
			}
		]);
		expect(nav.goto).toHaveBeenCalledWith(`/sessie/${SLUG}/delen`, { replace: true });
		expect(localStorage.getItem('shakka:organizer_name')).toBe('Lars');
	});
	it('(f) end equal to start: no write', async () => {
		await drawFor(GO_URL_SUMMER);
		await fireEvent.input(field('Je voornaam'), { target: { value: 'Lars' } });
		await fireEvent.input(field('Tot'), { target: { value: '14:00' } });
		await fireEvent.click(screen.getByRole('button', { name: 'Sessie aanmaken' }));
		expect(writeCalls(fake.current.calls)).toHaveLength(0);
	});
	it('(g) rate limited: message, no navigation, name not stored', async () => {
		await drawFor(GO_URL_SUMMER);
		await fireEvent.input(field('Je voornaam'), { target: { value: 'Lars' } });
		fake.current.respond('sessions', { data: null, error: { code: 'PT400', message: 'rate_limited' } });
		await fireEvent.click(screen.getByRole('button', { name: 'Sessie aanmaken' }));
		expect(await screen.findByText(SESSION_ERROR_MESSAGES.rateLimited)).toBeInTheDocument();
		expect(nav.goto).not.toHaveBeenCalled();
		expect(localStorage.getItem('shakka:organizer_name')).toBeNull();
	});
	it('(h) spot load error shows the banner with retry', async () => {
		vi.spyOn(console, 'warn').mockImplementation(() => {});
		fake.current.respond('spots', { data: null, error: { code: 'x' } });
		sessionStore.set(SESSION);
		render(Page, props(dataFor(GO_URL_SUMMER)));
		expect(await screen.findByText(/De spots konden niet worden geladen/)).toBeInTheDocument();
		fake.current.respond('spots', { data: SPOTS, error: null });
		await userEvent.setup({ advanceTimers: () => {} }).click(
			screen.getByRole('button', { name: 'Opnieuw proberen' })
		);
		expect(await screen.findByLabelText('Datum')).toBeInTheDocument();
	});
});
