import { render, screen } from '@testing-library/svelte';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { clientWithAuthTrap, createFakeRpc } from './helpers/fake-rpc.js';
import { createFakeSupabase } from './helpers/fake-supabase.js';
import { resetRsvpMemory } from '../src/lib/rsvp-storage.js';
import { NOW, SESSION_EVALS, SESSION_JSON, SLUG } from './fixtures/public-session.js';

const h = vi.hoisted(() => ({
	fake: null as unknown,
	db: null as unknown,
	trap: null as unknown
}));
vi.mock('#lib/supabase.js', async () => {
	const { clientWithAuthTrap, createFakeRpc } = await import('./helpers/fake-rpc.js');
	const { createFakeSupabase } = await import('./helpers/fake-supabase.js');
	const fake = createFakeRpc();
	const db = createFakeSupabase();
	const trap = clientWithAuthTrap({ rpc: fake.rpc, from: db.client.from });
	h.fake = fake;
	h.db = db;
	h.trap = trap;
	return { supabase: trap.client, initialUrlHash: '' };
});
vi.mock('$app/navigation', () => ({ refreshAll: vi.fn() }));

import { loadPublicSessionPage } from '../src/lib/public-session-data.js';
import Page from '../src/routes/s/[slug]/+page.svelte';

const fake = () => h.fake as ReturnType<typeof createFakeRpc>;
const db = () => h.db as ReturnType<typeof createFakeSupabase>;
const trap = () => h.trap as ReturnType<typeof clientWithAuthTrap>;

beforeEach(() => {
	vi.clearAllMocks();
	localStorage.clear();
	resetRsvpMemory();
	fake().reset();
	db().calls.length = 0;
	vi.useFakeTimers({ toFake: ['Date'] });
	vi.setSystemTime(new Date(NOW));
});
afterEach(() => {
	vi.restoreAllMocks();
	vi.useRealTimers();
});

describe('public session page with a mocked RPC (AC-2)', () => {
	it('loads and renders participants, carpool and hours', async () => {
		fake().respond('get_public_session', { data: SESSION_JSON, error: null, status: 200 });
		db().respond('evaluations', { data: SESSION_EVALS, error: null });
		const data = await loadPublicSessionPage(SLUG, new Date(NOW));
		const { container } = render(Page, { data } as never);

		const list = container.querySelector('.participant-list')!;
		for (const n of ['Eva', 'Sanne', 'Noor', 'Tom']) expect(list).toHaveTextContent(n);
		const carpool = container.querySelector('.carpool')!;
		expect(carpool).toHaveTextContent('Vrije plekken bij Lars: 3');
		expect(carpool).toHaveTextContent('meerijders: Sanne');
		expect(container.querySelector('.carpool-seekers')).toHaveTextContent('Noor');
		expect(container.querySelectorAll('.hour')).toHaveLength(4);
		expect(screen.getByText('17:00', { selector: 'time' })).toBeInTheDocument();

		expect(fake().calls).toHaveLength(1);
		expect(fake().calls[0]).toMatchObject({ fn: 'get_public_session', argCount: 2 });
		expect(db().calls).toHaveLength(1);
		const ops = db().calls[0].ops;
		expect(ops).toContainEqual(['gte', 'valid_at', '2026-07-18T12:00:00.000Z']);
		expect(ops).toContainEqual(['lt', 'valid_at', '2026-07-18T16:00:00.000Z']);
		expect(trap().authAccesses()).toBe(0);
	});
});
