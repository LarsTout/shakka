import { render, screen, within } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { createFakeRpc } from './helpers/fake-rpc.js';
import type { createFakeSupabase } from './helpers/fake-supabase.js';

const h = vi.hoisted(() => ({ rpc: null as unknown, db: null as unknown }));
vi.mock('#lib/supabase.js', async () => {
	const { createFakeRpc } = await import('./helpers/fake-rpc.js');
	const { createFakeSupabase } = await import('./helpers/fake-supabase.js');
	const rpc = createFakeRpc();
	const db = createFakeSupabase();
	h.rpc = rpc;
	h.db = db;
	return { supabase: { rpc: rpc.rpc, from: db.client.from }, initialUrlHash: '' };
});
vi.mock('#lib/auth.js', async () => (await import('./helpers/fake-session.js')).authModule);

import Page from '../src/routes/sessie/[slug]/beheer/+page.svelte';
import { MODERATION_MESSAGES } from '../src/lib/moderation.js';
import { EVA_ID, SESSION_INFO, SESSION_JSON } from './fixtures/public-session.js';
import { NOW_SESSIONS, SESSION_CANCELLED, SESSION_ROW, SLUG } from './fixtures/session-data.js';
import { writeCalls } from './helpers/fake-supabase.js';
import { SESSION, sessionStore } from './helpers/fake-session.js';

const rpc = () => h.rpc as ReturnType<typeof createFakeRpc>;
const db = () => h.db as ReturnType<typeof createFakeSupabase>;
const props = (slug = SLUG) => ({ data: { slug } }) as never;
const ok = (data: unknown) => ({ data, error: null, status: 200 });

async function draw(json: unknown = SESSION_JSON, row = SESSION_ROW) {
	db().respond('sessions', { data: row, error: null });
	rpc().respond('get_public_session', ok(json));
	sessionStore.set(SESSION);
	render(Page, props());
	await screen.findByRole('heading', { name: /Aanmeldingen \(/ });
}
const rowOf = (name: string) =>
	(document.getElementById(`rsvp-name-${name === 'Eva' ? EVA_ID : name}`) as HTMLElement).closest('li') as HTMLElement;
const nameBdi = (id: string) => document.getElementById(`rsvp-name-${id}`);

beforeEach(() => {
	vi.clearAllMocks();
	rpc().reset();
	db().reset();
	sessionStore.set(undefined);
	// A8 hides the switch once the session has ended; the fixture session ends on 2026-07-18.
	vi.useFakeTimers({ toFake: ['Date'] });
	vi.setSystemTime(new Date(NOW_SESSIONS));
});
afterEach(() => {
	vi.restoreAllMocks();
	vi.useRealTimers();
});

describe('manage page (AC-4)', () => {
	it('(a) signed out: login prompt, no queries', async () => {
		sessionStore.set(null);
		render(Page, props());
		expect(await screen.findByText(/Log in om aanmeldingen te beheren\./)).toBeInTheDocument();
		expect(db().calls).toHaveLength(0);
		expect(rpc().calls).toHaveLength(0);
	});

	it('(b) not my session: not found, no RPC', async () => {
		db().respond('sessions', { data: null, error: null });
		sessionStore.set(SESSION);
		render(Page, props());
		expect(await screen.findByText(/Sessie niet gevonden/)).toBeInTheDocument();
		expect(rpc().calls).toHaveLength(0);
	});

	it('(c) delete asks for confirmation, then exactly one call', async () => {
		await draw();
		rpc().respond('organizer_delete_rsvp', ok(true));
		const user = userEvent.setup();
		await user.click(within(rowOf('Eva')).getByRole('button', { name: 'Verwijderen' }));
		expect(rpc().calls.filter((c) => c.fn === 'organizer_delete_rsvp')).toHaveLength(0);
		expect(screen.getByText(/Diegene krijgt hier geen bericht van/)).toBeInTheDocument();
		await user.click(screen.getByRole('button', { name: 'Ja, verwijderen' }));
		const calls = rpc().calls.filter((c) => c.fn === 'organizer_delete_rsvp');
		expect(calls).toHaveLength(1);
		expect(calls[0]!.args).toEqual({ p_rsvp_id: EVA_ID });
		expect(nameBdi(EVA_ID)).toBeNull();
		expect(screen.getByRole('status')).toHaveTextContent(MODERATION_MESSAGES.deleted);
	});

	it('(d) "Nee" cancels without a call', async () => {
		await draw();
		const user = userEvent.setup();
		await user.click(within(rowOf('Eva')).getByRole('button', { name: 'Verwijderen' }));
		await user.click(screen.getByRole('button', { name: 'Nee' }));
		expect(screen.queryByRole('button', { name: 'Ja, verwijderen' })).toBeNull();
		expect(rpc().calls.filter((c) => c.fn === 'organizer_delete_rsvp')).toHaveLength(0);
		expect(nameBdi(EVA_ID)).not.toBeNull();
	});

	it('(e) failure keeps the row', async () => {
		vi.spyOn(console, 'warn').mockImplementation(() => {});
		await draw();
		rpc().respond('organizer_delete_rsvp', {
			data: null,
			error: { code: 'PT400', message: 'x' },
			status: 400
		});
		const user = userEvent.setup();
		await user.click(within(rowOf('Eva')).getByRole('button', { name: 'Verwijderen' }));
		await user.click(screen.getByRole('button', { name: 'Ja, verwijderen' }));
		expect(await screen.findByText(MODERATION_MESSAGES.failed)).toBeInTheDocument();
		expect(nameBdi(EVA_ID)).not.toBeNull();
		expect(screen.queryByRole('button', { name: 'Ja, verwijderen' })).toBeNull();
	});

	it('(f) false removes the row with alreadyGone', async () => {
		vi.spyOn(console, 'warn').mockImplementation(() => {});
		await draw();
		rpc().respond('organizer_delete_rsvp', ok(false));
		const user = userEvent.setup();
		await user.click(within(rowOf('Eva')).getByRole('button', { name: 'Verwijderen' }));
		await user.click(screen.getByRole('button', { name: 'Ja, verwijderen' }));
		expect(await screen.findByText(MODERATION_MESSAGES.alreadyGone)).toBeInTheDocument();
		expect(nameBdi(EVA_ID)).toBeNull();
	});

	it('(g) toggle updates only rsvps_closed_at', async () => {
		await draw();
		db().respond('sessions', { data: [{ id: SESSION_ROW.id }], error: null });
		const user = userEvent.setup();
		expect(screen.getByText(MODERATION_MESSAGES.open)).toBeInTheDocument();
		await user.click(screen.getByRole('button', { name: MODERATION_MESSAGES.closeButton }));
		const writes = writeCalls(db().calls);
		expect(writes).toHaveLength(1);
		expect(writes[0]!.ops).toEqual([
			['update', { rsvps_closed_at: new Date(NOW_SESSIONS).toISOString() }],
			['eq', 'id', SESSION_ROW.id],
			['select', 'id']
		]);
		expect(await screen.findByText(MODERATION_MESSAGES.closed)).toBeInTheDocument();
		expect(screen.getByRole('button', { name: MODERATION_MESSAGES.openButton })).toBeInTheDocument();
	});

	it('(h) reopen sends null', async () => {
		await draw({ ...SESSION_JSON, session: { ...SESSION_INFO, rsvps_closed: true } });
		db().respond('sessions', { data: [{ id: SESSION_ROW.id }], error: null });
		const user = userEvent.setup();
		expect(screen.getByText(MODERATION_MESSAGES.closed)).toBeInTheDocument();
		await user.click(screen.getByRole('button', { name: MODERATION_MESSAGES.openButton }));
		expect(writeCalls(db().calls)[0]!.ops[0]).toEqual(['update', { rsvps_closed_at: null }]);
		expect(await screen.findByText(MODERATION_MESSAGES.open)).toBeInTheDocument();
	});

	it('(i) cancelled session: no toggle, delete still there', async () => {
		await draw({ ...SESSION_JSON, session: { ...SESSION_INFO, cancelled: true } }, SESSION_CANCELLED);
		expect(screen.getByText('Deze sessie is geannuleerd.')).toBeInTheDocument();
		expect(screen.queryByRole('button', { name: MODERATION_MESSAGES.closeButton })).toBeNull();
		expect(within(rowOf('Eva')).getByRole('button', { name: 'Verwijderen' })).toBeInTheDocument();
	});
});
