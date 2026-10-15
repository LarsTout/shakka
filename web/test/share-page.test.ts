import { render, screen } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { createFakeSupabase } from './helpers/fake-supabase.js';

const fake = vi.hoisted(() => ({ current: null as unknown as ReturnType<typeof createFakeSupabase> }));
vi.mock('#lib/supabase.js', async () => {
	const { createFakeSupabase } = await import('./helpers/fake-supabase.js');
	fake.current = createFakeSupabase();
	return { supabase: fake.current.client, initialUrlHash: '' };
});
vi.mock('#lib/auth.js', async () => (await import('./helpers/fake-session.js')).authModule);

import Page from '../src/routes/sessie/[slug]/delen/+page.svelte';
import { shareText } from '../src/lib/session-model.js';
import { SESSION_CANCELLED, SESSION_ROW, SLUG } from './fixtures/session-data.js';
import { SPOT_UNVERIFIED } from './fixtures/spot-data.js';
import { SESSION, sessionStore } from './helpers/fake-session.js';

const URL_ = `https://example.org/s/${SLUG}`;
const props = (slug = SLUG) => ({ data: { slug, origin: 'https://example.org' } }) as never;
const nav = navigator as unknown as Record<string, unknown>;

async function draw(row = SESSION_ROW, slug = SLUG) {
	fake.current.respond('sessions', { data: row, error: null });
	fake.current.respond('spots', { data: SPOT_UNVERIFIED, error: null });
	sessionStore.set(SESSION);
	render(Page, props(slug));
	await screen.findByText('Teststrand');
}

beforeEach(() => {
	vi.clearAllMocks();
	fake.current.reset();
	sessionStore.set(undefined);
});
afterEach(() => {
	delete nav.share;
	delete nav.clipboard;
});

describe('share page (AC-3)', () => {
	it('(a) WhatsApp link with the golden text', async () => {
		await draw();
		const a = screen.getByRole('link', { name: 'Deel via WhatsApp' });
		const href = a.getAttribute('href')!;
		expect(href.startsWith('https://wa.me/?text=')).toBe(true);
		expect(decodeURIComponent(href.slice('https://wa.me/?text='.length))).toBe(
			shareText(SESSION_ROW, 'Teststrand', URL_)
		);
		expect(a).toHaveAttribute('target', '_blank');
		expect(a.getAttribute('rel')).toContain('noopener');
		expect(a.getAttribute('rel')).toContain('noreferrer');
	});
	it('(b) the link field holds the URL', async () => {
		await draw();
		expect((screen.getByLabelText('Link naar de sessie') as HTMLInputElement).value).toBe(URL_);
	});
	it('(c) copy', async () => {
		const writeText = vi.fn(async () => {});
		Object.defineProperty(navigator, 'clipboard', { configurable: true, value: { writeText } });
		await draw();
		await userEvent.click(screen.getByRole('button', { name: 'Kopieer link' }));
		expect(writeText).toHaveBeenCalledWith(URL_);
		expect(await screen.findByText('Link gekopieerd.')).toBeInTheDocument();
	});
	it('(c) copy failure', async () => {
		Object.defineProperty(navigator, 'clipboard', {
			configurable: true,
			value: { writeText: vi.fn(async () => Promise.reject(new Error('no'))) }
		});
		await draw();
		await userEvent.click(screen.getByRole('button', { name: 'Kopieer link' }));
		expect(await screen.findByText(/Kopiëren is niet gelukt/)).toBeInTheDocument();
	});
	it('(d) no share button without navigator.share', async () => {
		await draw();
		expect(screen.queryByRole('button', { name: 'Delen…' })).toBeNull();
	});
	it('(d) share sends text only; AbortError is silent', async () => {
		const share = vi.fn(async (_d: unknown) => {});
		nav.share = share;
		await draw();
		await userEvent.click(await screen.findByRole('button', { name: 'Delen…' }));
		expect(share).toHaveBeenCalledWith({ text: shareText(SESSION_ROW, 'Teststrand', URL_) });
		share.mockRejectedValueOnce({ name: 'AbortError' });
		await userEvent.click(screen.getByRole('button', { name: 'Delen…' }));
		expect(screen.queryByText(/Delen is niet gelukt/)).toBeNull();
		share.mockRejectedValueOnce({ name: 'NotAllowedError' });
		await userEvent.click(screen.getByRole('button', { name: 'Delen…' }));
		expect(await screen.findByText(/Delen is niet gelukt/)).toBeInTheDocument();
	});
	it('(e) cancelled session: banner, no sharing', async () => {
		await draw(SESSION_CANCELLED, SESSION_CANCELLED.slug);
		expect(screen.getByText('Deze sessie is geannuleerd.')).toBeInTheDocument();
		expect(screen.queryByRole('link', { name: 'Deel via WhatsApp' })).toBeNull();
	});
	it('(f) malformed slug: not found without a query', async () => {
		sessionStore.set(SESSION);
		render(Page, props('abc'));
		expect(await screen.findByText(/Deze sessie bestaat niet/)).toBeInTheDocument();
		expect(fake.current.calls).toHaveLength(0);
	});
	it('(g) signed out: login prompt', () => {
		sessionStore.set(null);
		render(Page, props());
		expect(screen.getByText('Log in om deze sessie te delen.')).toBeInTheDocument();
	});
});
