import { cleanup, render, screen } from '@testing-library/svelte';
import { afterEach, beforeEach, describe, it, vi } from 'vitest';
import type { createFakeRpc } from './helpers/fake-rpc.js';
import type { createFakeSupabase } from './helpers/fake-supabase.js';

// The union of the mocks of new-session-page, share-page and my-sessions-page tests.
const fake = vi.hoisted(() => ({
	current: null as unknown as ReturnType<typeof createFakeSupabase>,
	rpc: null as unknown as ReturnType<typeof createFakeRpc>
}));
vi.mock('#lib/supabase.js', async () => {
	const { createFakeSupabase } = await import('./helpers/fake-supabase.js');
	const { createFakeRpc } = await import('./helpers/fake-rpc.js');
	fake.current = createFakeSupabase();
	fake.rpc = createFakeRpc();
	return { supabase: { ...fake.current.client, rpc: fake.rpc.rpc }, initialUrlHash: '' };
});
vi.mock('#lib/auth.js', async () => (await import('./helpers/fake-session.js')).authModule);
const nav = vi.hoisted(() => ({ goto: vi.fn(async () => {}), refreshAll: vi.fn() }));
vi.mock('$app/navigation', () => ({ goto: nav.goto, refreshAll: nav.refreshAll }));

import { load as goLoad } from '../src/routes/go/+page.js';
import { load } from '../src/routes/sessie/nieuw/+page.js';
import NewSession from '../src/routes/sessie/nieuw/+page.svelte';
import ManagePage from '../src/routes/sessie/[slug]/beheer/+page.svelte';
import SharePage from '../src/routes/sessie/[slug]/delen/+page.svelte';
import MySessions from '../src/routes/mijn-sessies/+page.svelte';
import { SESSION_JSON } from './fixtures/public-session.js';
import { NOW_SESSIONS, SESSION_CANCELLED, SESSION_ROW, SLUG } from './fixtures/session-data.js';
import { GO_URL_SUMMER, SPOT_UNVERIFIED, SPOT_VERIFIED } from './fixtures/spot-data.js';
import { SESSION, sessionStore } from './helpers/fake-session.js';
import { expectNoSeriousViolations } from './helpers/axe.js';

beforeEach(() => {
	vi.clearAllMocks();
	fake.current.reset();
	fake.rpc.reset();
	localStorage.clear();
	sessionStore.set(undefined);
	vi.useFakeTimers({ toFake: ['Date'] });
	vi.setSystemTime(new Date(NOW_SESSIONS));
});
afterEach(() => {
	cleanup();
	vi.useRealTimers();
});

describe('a11y: session pages', () => {
	it('/sessie/nieuw', async () => {
		const { target } = (goLoad as (e: unknown) => { target: string })({ url: new URL(GO_URL_SUMMER) });
		const data = (load as (e: unknown) => unknown)({ url: new URL('https://example.org' + target) });
		fake.current.respond('spots', { data: [SPOT_UNVERIFIED, SPOT_VERIFIED], error: null });
		sessionStore.set(SESSION);
		render(NewSession, { data } as never);
		await screen.findByLabelText('Datum');
		await expectNoSeriousViolations();
	});
	it('/sessie/[slug]/delen', async () => {
		fake.current.respond('sessions', { data: SESSION_ROW, error: null });
		fake.current.respond('spots', { data: SPOT_UNVERIFIED, error: null });
		sessionStore.set(SESSION);
		render(SharePage, { data: { slug: SLUG, origin: 'https://example.org' } } as never);
		await screen.findByText('Teststrand');
		await expectNoSeriousViolations();
	});
	it('/sessie/[slug]/beheer', async () => {
		fake.current.respond('sessions', { data: SESSION_ROW, error: null });
		fake.rpc.respond('get_public_session', { data: SESSION_JSON, error: null, status: 200 });
		sessionStore.set(SESSION);
		render(ManagePage, { data: { slug: SLUG } } as never);
		await screen.findByRole('heading', { name: /Aanmeldingen \(/ });
		await expectNoSeriousViolations();
	});
	it('/mijn-sessies', async () => {
		fake.current.respond('sessions', { data: [SESSION_ROW, SESSION_CANCELLED], error: null });
		fake.current.respond('spots', { data: [SPOT_VERIFIED, SPOT_UNVERIFIED], error: null });
		sessionStore.set(SESSION);
		render(MySessions);
		await screen.findAllByRole('heading', { name: 'Teststrand' });
		await expectNoSeriousViolations();
	});
});
