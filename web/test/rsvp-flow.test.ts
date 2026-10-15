import { render, screen, waitFor } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { resetRsvpMemory } from '../src/lib/rsvp-storage.js';
import {
	RSVP_MESSAGES,
	RSVP_NOTICES,
	RsvpError,
	type RsvpErrorKind
} from '../src/lib/session-view.js';
import {
	EVA_ID,
	FOUR_RSVPS,
	NEW_ID,
	NOW,
	RSVP_NEW,
	RSVP_TOM,
	SESSION_INFO,
	SLUG,
	TOKEN,
	TOKEN_NEW,
	TOM_ID,
	publicSessionPageData
} from './fixtures/public-session.js';

const m = vi.hoisted(() => ({
	refreshAll: vi.fn(),
	getPublicSession: vi.fn(),
	createRsvp: vi.fn(),
	updateRsvp: vi.fn(),
	deleteRsvp: vi.fn()
}));
vi.mock('$app/navigation', () => ({ refreshAll: m.refreshAll }));
vi.mock('#lib/supabase.js', () => {
	throw new Error('page tests must not import the Supabase client');
});
vi.mock('#lib/rsvp.js', () => ({
	getPublicSession: m.getPublicSession,
	createRsvp: m.createRsvp,
	updateRsvp: m.updateRsvp,
	deleteRsvp: m.deleteRsvp
}));

import Page from '../src/routes/s/[slug]/+page.svelte';

const KEY = 'shakka:rsvp:' + SLUG;
const props = (data: unknown) => ({ data }) as never;
const storeTom = () => localStorage.setItem(KEY, JSON.stringify({ rsvp_id: TOM_ID, edit_token: TOKEN }));
const withNew = { session: SESSION_INFO, rsvps: [...FOUR_RSVPS, RSVP_NEW] };

let user: ReturnType<typeof userEvent.setup>;

async function signUp(name = 'Sanne') {
	await user.type(await screen.findByLabelText('Voornaam'), name);
	await user.click(screen.getByRole('button', { name: 'Ik ook' }));
}

beforeEach(() => {
	vi.clearAllMocks();
	localStorage.clear();
	resetRsvpMemory();
	vi.useFakeTimers({ toFake: ['Date'] });
	vi.setSystemTime(new Date(NOW));
	user = userEvent.setup();
	m.getPublicSession.mockResolvedValue({ session: SESSION_INFO, rsvps: [...FOUR_RSVPS] });
});
afterEach(() => {
	vi.restoreAllMocks();
	vi.useRealTimers();
});

describe('sign up, change, sign out (AC-3)', () => {
	it('(1) creates an RSVP and stores the key', async () => {
		render(Page, props(publicSessionPageData()));
		m.createRsvp.mockResolvedValue({ rsvp_id: NEW_ID, edit_token: TOKEN_NEW });
		m.getPublicSession.mockResolvedValue(withNew);
		await user.type(await screen.findByLabelText('Voornaam'), '  Sanne  ');
		await user.click(screen.getByRole('button', { name: 'Ik ook' }));
		expect(m.createRsvp).toHaveBeenCalledTimes(1);
		expect(m.createRsvp).toHaveBeenCalledWith(SLUG, {
			first_name: 'Sanne',
			ride: 'own',
			seats_offered: null
		});
		expect(await screen.findByRole('heading', { name: 'Jij gaat' })).toBeInTheDocument();
		expect(localStorage.getItem(KEY)).toBe(JSON.stringify({ rsvp_id: NEW_ID, edit_token: TOKEN_NEW }));
		expect(screen.getByRole('button', { name: 'Wijzigen' })).toBeInTheDocument();
		expect(screen.getByRole('button', { name: 'Afmelden' })).toBeInTheDocument();
		expect(screen.getByRole('status')).toHaveTextContent(RSVP_NOTICES.created);
		await waitFor(() => expect(document.querySelector(`[data-rsvp="${NEW_ID}"]`)).toHaveTextContent('(jij)'));
		// (17) the token is never in the DOM or the URL
		expect(document.body.innerHTML).not.toContain(TOKEN_NEW);
		expect(window.location.href).not.toContain(TOKEN_NEW);
	});

	it('(2) a stored key shows "Jij gaat"', async () => {
		storeTom();
		render(Page, props(publicSessionPageData()));
		expect(await screen.findByRole('heading', { name: 'Jij gaat' })).toBeInTheDocument();
		expect(screen.getByRole('button', { name: 'Wijzigen' })).toBeInTheDocument();
		expect(screen.getByRole('button', { name: 'Afmelden' })).toBeInTheDocument();
		expect(screen.getByText(/Aangemeld als/)).toHaveTextContent('Aangemeld als Tom · Rijdt zelf');
		expect(screen.queryByLabelText('Voornaam')).toBeNull();
	});

	it('(3) sign out calls rsvp_delete and removes the key', async () => {
		storeTom();
		render(Page, props(publicSessionPageData()));
		m.deleteRsvp.mockResolvedValue(true);
		await user.click(await screen.findByRole('button', { name: 'Afmelden' }));
		await user.click(screen.getByRole('button', { name: 'Ja, afmelden' }));
		expect(m.deleteRsvp).toHaveBeenCalledWith(TOKEN);
		expect(localStorage.getItem(KEY)).toBeNull();
		expect(await screen.findByRole('status')).toHaveTextContent(RSVP_NOTICES.deleted);
		expect(await screen.findByLabelText('Voornaam')).toBeInTheDocument();
	});

	it('(4) delete returning false still clears the key', async () => {
		storeTom();
		render(Page, props(publicSessionPageData()));
		m.deleteRsvp.mockResolvedValue(false);
		await user.click(await screen.findByRole('button', { name: 'Afmelden' }));
		await user.click(screen.getByRole('button', { name: 'Ja, afmelden' }));
		expect(await screen.findByText(RSVP_NOTICES.alreadyDeleted)).toBeInTheDocument();
		expect(localStorage.getItem(KEY)).toBeNull();
	});

	it('(5) change: ride along with Eva', async () => {
		storeTom();
		render(Page, props(publicSessionPageData()));
		m.updateRsvp.mockResolvedValue(RSVP_TOM);
		await user.click(await screen.findByRole('button', { name: 'Wijzigen' }));
		await user.click(screen.getByLabelText('Ik zoek een lift'));
		await user.selectOptions(screen.getByLabelText('Rijd mee met'), EVA_ID);
		m.getPublicSession.mockClear();
		await user.click(screen.getByRole('button', { name: 'Opslaan' }));
		expect(m.updateRsvp).toHaveBeenCalledWith(TOKEN, {
			first_name: 'Tom',
			ride: 'needs_ride',
			seats_offered: null,
			rides_with: EVA_ID
		});
		expect(await screen.findByText(RSVP_NOTICES.updated)).toBeInTheDocument();
		expect(m.getPublicSession).toHaveBeenCalledTimes(1);
		expect(document.body.innerHTML).not.toContain(TOKEN);
	});

	it('(6) invalid_token on update clears the key and shows the form', async () => {
		storeTom();
		render(Page, props(publicSessionPageData()));
		m.updateRsvp.mockRejectedValue(new RsvpError('invalid_token', 'updateRsvp'));
		await user.click(await screen.findByRole('button', { name: 'Wijzigen' }));
		await user.click(screen.getByRole('button', { name: 'Opslaan' }));
		expect(await screen.findByRole('alert')).toHaveTextContent(RSVP_MESSAGES.invalid_token);
		expect(localStorage.getItem(KEY)).toBeNull();
		expect(await screen.findByLabelText('Voornaam')).toBeInTheDocument();
	});
});

describe('errors (AC-4)', () => {
	it('(7) each server code gets its own Dutch message', async () => {
		const kinds: RsvpErrorKind[] = ['rate_limited', 'session_full', 'session_closed', 'invalid_input'];
		const seen: string[] = [];
		for (const kind of kinds) {
			vi.clearAllMocks();
			m.getPublicSession.mockResolvedValue({ session: SESSION_INFO, rsvps: [...FOUR_RSVPS] });
			const r = render(Page, props(publicSessionPageData()));
			m.createRsvp.mockRejectedValue(new RsvpError(kind, 'createRsvp'));
			await signUp();
			const alert = await screen.findByRole('alert');
			expect(alert).toHaveTextContent(RSVP_MESSAGES[kind]);
			expect(alert.textContent).toBe(RSVP_MESSAGES[kind]);
			seen.push(alert.textContent!);
			expect(screen.queryByText(/rate_limited|session_full|session_closed|invalid_input/)).toBeNull();
			expect(localStorage.getItem(KEY)).toBeNull();
			if (kind === 'session_full' || kind === 'session_closed') {
				await waitFor(() => expect(m.getPublicSession).toHaveBeenCalled());
			}
			r.unmount();
			localStorage.clear();
		}
		expect(new Set(seen).size).toBe(4);
	});

	it('(8) an unknown error shows the generic message only', async () => {
		render(Page, props(publicSessionPageData()));
		m.createRsvp.mockRejectedValue(new Error('secret detail'));
		await signUp();
		expect(await screen.findByRole('alert')).toHaveTextContent(RSVP_MESSAGES.unknown);
		expect(document.body.textContent).not.toContain('secret detail');
	});
});

describe('other behaviour', () => {
	it('(9) empty name: field error, no RPC', async () => {
		render(Page, props(publicSessionPageData()));
		await user.click(await screen.findByRole('button', { name: 'Ik ook' }));
		expect(screen.getByText('Vul je voornaam in.')).toBeInTheDocument();
		expect(screen.getByLabelText('Voornaam')).toHaveAttribute('aria-invalid', 'true');
		expect(m.createRsvp).not.toHaveBeenCalled();
	});

	it('(10) double click sends one request', async () => {
		render(Page, props(publicSessionPageData()));
		m.createRsvp.mockReturnValue(new Promise(() => {}));
		await user.type(await screen.findByLabelText('Voornaam'), 'Sanne');
		const button = screen.getByRole('button', { name: 'Ik ook' });
		await user.click(button);
		await user.click(screen.getByRole('button', { name: 'Bezig…' }));
		expect(m.createRsvp).toHaveBeenCalledTimes(1);
		expect(screen.getByRole('button', { name: 'Bezig…' })).toBeDisabled();
	});

	it('(11) a stale key is removed and the form shows', async () => {
		localStorage.setItem(KEY, JSON.stringify({ rsvp_id: NEW_ID, edit_token: TOKEN }));
		render(Page, props(publicSessionPageData()));
		expect(await screen.findByLabelText('Voornaam')).toBeInTheDocument();
		expect(localStorage.getItem(KEY)).toBeNull();
	});

	it('(12) a broken key is removed and the form shows', async () => {
		localStorage.setItem(KEY, '{kapot');
		render(Page, props(publicSessionPageData()));
		expect(await screen.findByLabelText('Voornaam')).toBeInTheDocument();
		expect(localStorage.getItem(KEY)).toBeNull();
	});

	it('(13) storage failure: memory fallback survives a reload of data', async () => {
		vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
			throw new Error('quota');
		});
		const r = render(Page, props(publicSessionPageData()));
		m.createRsvp.mockResolvedValue({ rsvp_id: NEW_ID, edit_token: TOKEN_NEW });
		m.getPublicSession.mockResolvedValue(withNew);
		await signUp();
		expect(await screen.findByText(RSVP_NOTICES.storageFailed)).toBeInTheDocument();
		await r.rerender({ data: publicSessionPageData({ rsvps: [...FOUR_RSVPS, RSVP_NEW] }) } as never);
		expect(await screen.findByRole('heading', { name: 'Jij gaat' })).toBeInTheDocument();
		m.deleteRsvp.mockResolvedValue(true);
		await user.click(screen.getByRole('button', { name: 'Afmelden' }));
		await user.click(screen.getByRole('button', { name: 'Ja, afmelden' }));
		expect(m.deleteRsvp).toHaveBeenCalledWith(TOKEN_NEW);
	});

	it('(14) a second tab already signed up: no second RSVP', async () => {
		render(Page, props(publicSessionPageData()));
		await user.type(await screen.findByLabelText('Voornaam'), 'Tom');
		storeTom();
		await user.click(screen.getByRole('button', { name: 'Ik ook' }));
		expect(await screen.findByRole('heading', { name: 'Jij gaat' })).toBeInTheDocument();
		expect(m.createRsvp).not.toHaveBeenCalled();
		expect(m.getPublicSession).toHaveBeenCalledTimes(1);
	});

	it('(15) closed plus key: only Afmelden; aria-labelledby follows the heading', async () => {
		storeTom();
		const cancelled = { ...SESSION_INFO, cancelled: true };
		render(Page, props(publicSessionPageData({ session: cancelled })));
		expect(await screen.findByRole('button', { name: 'Afmelden' })).toBeInTheDocument();
		expect(screen.queryByRole('button', { name: 'Wijzigen' })).toBeNull();
		expect(document.querySelector('.rsvp-panel')).toHaveAttribute('aria-labelledby', 'rsvp-heading');
		m.deleteRsvp.mockResolvedValue(true);
		m.getPublicSession.mockResolvedValue({
			session: cancelled,
			rsvps: FOUR_RSVPS.filter((r) => r.id !== TOM_ID)
		});
		await user.click(screen.getByRole('button', { name: 'Afmelden' }));
		await user.click(screen.getByRole('button', { name: 'Ja, afmelden' }));
		expect(await screen.findByText(RSVP_NOTICES.deleted)).toBeInTheDocument();
		const panel = document.querySelector('.rsvp-panel')!;
		expect(panel).not.toHaveAttribute('aria-labelledby');
		expect(screen.queryByLabelText('Voornaam')).toBeNull();
	});

	it('(16) a refresh returning null after create shows "not found"', async () => {
		render(Page, props(publicSessionPageData()));
		m.createRsvp.mockResolvedValue({ rsvp_id: NEW_ID, edit_token: TOKEN_NEW });
		m.getPublicSession.mockResolvedValue(null);
		await signUp();
		expect(await screen.findByRole('heading', { name: 'Sessie niet gevonden' })).toBeInTheDocument();
		expect(localStorage.getItem(KEY)).toBeNull();
	});

	it('(18) the server closes the session: form disappears', async () => {
		render(Page, props(publicSessionPageData()));
		m.createRsvp.mockRejectedValue(new RsvpError('session_closed', 'createRsvp'));
		await signUp();
		expect(await screen.findByText(RSVP_MESSAGES.session_closed)).toBeInTheDocument();
		await waitFor(() => expect(screen.queryByLabelText('Voornaam')).toBeNull());
		expect(screen.queryByRole('button', { name: 'Ik ook' })).toBeNull();
		expect(m.getPublicSession).toHaveBeenCalledTimes(1);
		expect(m.createRsvp).toHaveBeenCalledTimes(1);
	});

	it('(19) the server closes on update: Wijzigen goes, Afmelden stays', async () => {
		storeTom();
		render(Page, props(publicSessionPageData()));
		m.updateRsvp.mockRejectedValue(new RsvpError('session_closed', 'updateRsvp'));
		await user.click(await screen.findByRole('button', { name: 'Wijzigen' }));
		await user.click(screen.getByRole('button', { name: 'Opslaan' }));
		expect(await screen.findByText(RSVP_MESSAGES.session_closed)).toBeInTheDocument();
		await waitFor(() => expect(screen.queryByRole('button', { name: 'Wijzigen' })).toBeNull());
		expect(screen.getByRole('button', { name: 'Afmelden' })).toBeInTheDocument();
	});
});
