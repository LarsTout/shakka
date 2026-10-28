import { fireEvent, render, screen, within } from '@testing-library/svelte';
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

import Page from '../src/routes/mijn-sessies/+page.svelte';
import { NOW_SESSIONS, SESSION_CANCELLED, SESSION_ID, SESSION_ROW, SLUG } from './fixtures/session-data.js';
import { SPOT_UNVERIFIED, SPOT_VERIFIED } from './fixtures/spot-data.js';
import { SESSION, USER_ID, sessionStore } from './helpers/fake-session.js';

beforeEach(() => {
	vi.clearAllMocks();
	fake.current.reset();
	sessionStore.set(undefined);
	vi.useFakeTimers({ toFake: ['Date'] });
	vi.setSystemTime(new Date(NOW_SESSIONS));
});
afterEach(() => vi.useRealTimers());

async function draw(rows = [SESSION_ROW, SESSION_CANCELLED]) {
	fake.current.respond('sessions', { data: rows, error: null });
	fake.current.respond('spots', { data: [SPOT_VERIFIED, SPOT_UNVERIFIED], error: null });
	sessionStore.set(SESSION);
	render(Page);
	if (rows.length) await screen.findAllByRole('heading', { name: 'Teststrand' });
	else await screen.findByText(/Je hebt geen komende sessies/);
}
const section = () => document.querySelector(`[data-slug="${SLUG}"]`) as HTMLElement;
const user = () => userEvent.setup({ advanceTimers: () => {} });

describe('my sessions page (AC-5)', () => {
	it('(a) signed out: login prompt, no calls', async () => {
		sessionStore.set(null);
		render(Page);
		expect(screen.getByText('Log in om je sessies te zien.')).toBeInTheDocument();
		await new Promise((r) => setTimeout(r, 0));
		expect(fake.current.calls).toHaveLength(0);
	});
	it('(b) only asks for own, upcoming sessions', async () => {
		await draw();
		const call = fake.current.calls.find((c) => c.table === 'sessions')!;
		expect(call.ops).toContainEqual(['eq', 'organizer_id', USER_ID]);
		expect(call.ops).toContainEqual(['gt', 'ends_at', '2026-07-15T12:30:00.000Z']);
		const owners = fake.current.calls
			.flatMap((c) => c.ops)
			.filter(([n, col]) => n === 'eq' && col === 'organizer_id');
		expect(owners.every((o) => o[2] === USER_ID)).toBe(true);
	});
	it('(c) shows both entries with the right actions', async () => {
		await draw();
		const s = within(section());
		expect(s.getByText('za 18 jul 14:00–18:00')).toBeInTheDocument();
		expect(s.getByRole('link', { name: 'Delen' })).toHaveAttribute('href', `/sessie/${SLUG}/delen`);
		expect(s.getByRole('link', { name: 'Sessiepagina' })).toHaveAttribute('href', `/s/${SLUG}`);
		const cancelled = document.querySelector(
			`[data-slug="${SESSION_CANCELLED.slug}"]`
		) as HTMLElement;
		expect(within(cancelled).getByText('Geannuleerd')).toBeInTheDocument();
		expect(within(cancelled).queryByRole('button', { name: 'Sessie annuleren' })).toBeNull();
	});
	it('(d) cancel in two steps sets cancelled_at', async () => {
		await draw();
		const u = user();
		await u.click(within(section()).getByRole('button', { name: 'Sessie annuleren' }));
		fake.current.respond('sessions', { data: [{ id: SESSION_ID }], error: null });
		await u.click(within(section()).getByRole('button', { name: 'Ja, annuleer de sessie' }));
		expect(await within(section()).findByText('Sessie geannuleerd.')).toBeInTheDocument();
		const writes = writeCalls(fake.current.calls);
		expect(writes).toHaveLength(1);
		expect(writes[0]!.ops).toEqual([
			['update', { cancelled_at: '2026-07-15T12:30:00.000Z' }],
			['eq', 'id', SESSION_ID],
			['select', 'id']
		]);
		expect(within(section()).getByText('Geannuleerd')).toBeInTheDocument();
	});
	it('(e) Nee cancels the confirmation without a write', async () => {
		await draw();
		const u = user();
		await u.click(within(section()).getByRole('button', { name: 'Sessie annuleren' }));
		await u.click(within(section()).getByRole('button', { name: 'Nee' }));
		expect(within(section()).getByRole('button', { name: 'Sessie annuleren' })).toBeInTheDocument();
		expect(writeCalls(fake.current.calls)).toHaveLength(0);
	});
	it('(f) editing writes the eight editable keys', async () => {
		await draw();
		const field = within(section()).getByLabelText('Vertrekpunt (optioneel)');
		await fireEvent.input(field, { target: { value: 'Amersfoort' } });
		fake.current.respond('sessions', { data: [{ id: SESSION_ID }], error: null });
		await user().click(within(section()).getByRole('button', { name: 'Wijzigingen opslaan' }));
		expect(await within(section()).findByText('Opgeslagen.')).toBeInTheDocument();
		const writes = writeCalls(fake.current.calls);
		expect(writes).toHaveLength(1);
		const payload = writes[0]!.ops[0]![1] as Record<string, unknown>;
		expect(Object.keys(payload).sort()).toEqual(
			['departure_point', 'ends_at', 'note', 'organizer_name', 'seats_free', 'spot_id', 'starts_at', 'tikkie_url']
		);
		expect(payload.departure_point).toBe('Amersfoort');
	});
	it('(h) manage link, also for a cancelled session', async () => {
		await draw();
		for (const slug of [SLUG, SESSION_CANCELLED.slug]) {
			const el = document.querySelector(`[data-slug="${slug}"]`) as HTMLElement;
			expect(within(el).getByRole('link', { name: 'Aanmeldingen beheren' })).toHaveAttribute(
				'href',
				`/sessie/${slug}/beheer`
			);
		}
	});
	it('(g) empty list shows the explanation and the new-session link', async () => {
		await draw([]);
		expect(screen.getByRole('link', { name: 'Nieuwe sessie' })).toHaveAttribute('href', '/sessie/nieuw');
	});
});
