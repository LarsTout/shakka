import { render, screen } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, it, vi } from 'vitest';
import { resetRsvpMemory } from '../src/lib/rsvp-storage.js';
import { expectNoSeriousViolations } from './helpers/axe.js';
import {
	NOW,
	SESSION_INFO,
	SLUG,
	TOKEN,
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

const props = (data: unknown) => ({ data }) as never;

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

describe('a11y: public session page', () => {
	it('open session without a saved RSVP (form)', async () => {
		render(Page, props(publicSessionPageData()));
		await screen.findByLabelText('Voornaam');
		await expectNoSeriousViolations();
	});
	it('with a saved RSVP, then the change form open', async () => {
		localStorage.setItem(
			'shakka:rsvp:' + SLUG,
			JSON.stringify({ rsvp_id: TOM_ID, edit_token: TOKEN })
		);
		render(Page, props(publicSessionPageData()));
		const change = await screen.findByRole('button', { name: 'Wijzigen' });
		await expectNoSeriousViolations();
		await userEvent.setup().click(change);
		await screen.findByRole('button', { name: /opslaan/i });
		await expectNoSeriousViolations();
	});
	it('cancelled session', async () => {
		render(Page, props(publicSessionPageData({ session: { ...SESSION_INFO, cancelled: true } })));
		await screen.findByRole('alert');
		await expectNoSeriousViolations();
	});
	it('not found', async () => {
		render(Page, props({ kind: 'not_found', now: NOW, slug: SLUG }));
		await screen.findByRole('heading', { level: 1 });
		await expectNoSeriousViolations();
	});
});
