import { render, screen } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { SummaryRow } from '../src/lib/types.js';
import { EVALUATED_AT, NOW_FRESH, SPOT_UNVERIFIED, SPOT_VERIFIED } from './fixtures/spot-data.js';

const nav = vi.hoisted(() => ({ refreshAll: vi.fn() }));
vi.mock('$app/navigation', () => ({ refreshAll: nav.refreshAll }));
vi.mock('#lib/supabase.js', () => {
	throw new Error('page tests must not import the Supabase client');
});

import Page from '../src/routes/+page.svelte';
import { summarizeSpots } from '../src/lib/view.js';

const props = (data: unknown) => ({ data }) as never;
const row = (valid_at: string, verdict: SummaryRow['verdict']): SummaryRow => ({
	spot_id: 'test-meer',
	valid_at,
	verdict,
	reasons: [],
	evaluated_at: EVALUATED_AT
});
const S = summarizeSpots(
	[
		row('2026-07-15T12:00:00+00:00', 'go'),
		row('2026-07-15T13:00:00+00:00', 'go'),
		row('2026-07-15T14:00:00+00:00', 'marginal'),
		row('2026-07-16T08:00:00+00:00', 'no_go')
	],
	new Date(NOW_FRESH)
)['test-meer']!;

const item = (id: string) => document.querySelector(`[data-spot="${id}"]`) as HTMLElement;
const summaries = (el: HTMLElement) => [...el.querySelectorAll('p.day-summary')] as HTMLElement[];

beforeEach(() => {
	vi.clearAllMocks();
});

describe('spot list (AC-4)', () => {
	const ok = {
		kind: 'ok',
		now: NOW_FRESH,
		spots: [SPOT_UNVERIFIED, SPOT_VERIFIED],
		summaries: { 'test-meer': S }
	};

	it('shows a spot without data', () => {
		render(Page, props(ok));
		const el = item('test-strand');
		expect(el).toHaveTextContent('Nog geen data');
		expect(el).toHaveTextContent('niet geverifieerd');
		expect(screen.getByRole('link', { name: 'Teststrand' })).toHaveAttribute('href', '/spot/test-strand');
		expect(screen.queryByRole('alert')).toBeNull();
	});

	it('shows today and tomorrow for a spot with data', () => {
		render(Page, props(ok));
		const el = item('test-meer');
		expect(el).not.toHaveTextContent('niet geverifieerd');
		const [today, tomorrow] = summaries(el);
		expect(today).toHaveTextContent(/Vandaag:/);
		expect(today!.querySelector('[data-verdict="go"]')).toHaveTextContent('Go');
		expect(today).toHaveTextContent(/2 uur go vanaf 14:00, 1 uur twijfel/);
		expect(tomorrow).toHaveTextContent(/Morgen:/);
		expect(tomorrow!.querySelector('[data-verdict="no_go"]')).toHaveTextContent('Niet gaan');
		expect(tomorrow).toHaveTextContent(/geen go- of twijfeluren/);
		expect(tomorrow).not.toHaveTextContent(/niet gaan niet gaan/i);
	});

	it('empty list', () => {
		render(Page, props({ ...ok, spots: [] }));
		expect(screen.getByText('Er staan nog geen spots in de database.')).toBeInTheDocument();
	});

	it('error state retries', async () => {
		render(Page, props({ kind: 'error', now: NOW_FRESH }));
		expect(screen.getByRole('alert')).toBeInTheDocument();
		await userEvent.click(screen.getByRole('button', { name: 'Opnieuw proberen' }));
		expect(nav.refreshAll).toHaveBeenCalledTimes(1);
	});

	it('warns when the newest evaluation is older than 3 hours', () => {
		const old = { ...S, latest_evaluated_at: '2026-07-15T08:00:00+00:00' };
		render(Page, props({ ...ok, summaries: { 'test-meer': old } }));
		expect(screen.getByRole('alert')).toHaveTextContent('ouder dan 3 uur');
	});
});
