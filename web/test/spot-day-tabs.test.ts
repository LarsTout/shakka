import { render, screen } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { favoritesState } from './helpers/fake-favorites.js';
import { sessionStore } from './helpers/fake-session.js';
import { EVAL_TOMORROW, pageData } from './fixtures/spot-data.js';

vi.mock('$app/navigation', () => ({ refreshAll: vi.fn() }));
vi.mock('#lib/supabase.js', () => {
	throw new Error('page tests must not import the Supabase client');
});
vi.mock('#lib/auth.js', async () => (await import('./helpers/fake-session.js')).authModule);
vi.mock('#lib/favorites.js', async () => (await import('./helpers/fake-favorites.js')).favoritesModule);

import Page from '../src/routes/spot/[id]/+page.svelte';

const props = (data: unknown) => ({ data }) as never;
const panel = (key: string) => document.getElementById(`dagpaneel-${key}`) as HTMLElement;
const tab = (name: string) => screen.getByRole('button', { name });

beforeEach(() => {
	favoritesState.set({ status: 'signed_out' });
	sessionStore.set(null);
});

describe('spot day tabs (AC-10)', () => {
	it('tabs per day, first pressed', () => {
		render(Page, props(pageData()));
		expect(tab('Vandaag')).toHaveAttribute('aria-pressed', 'true');
		expect(tab('Morgen')).toHaveAttribute('aria-pressed', 'false');
		expect(panel('2026-07-15')).not.toHaveClass('day-inactive');
		expect(panel('2026-07-16')).toHaveClass('day-inactive');
	});

	it('click switches', async () => {
		render(Page, props(pageData()));
		await userEvent.setup().click(tab('Morgen'));
		expect(tab('Morgen')).toHaveAttribute('aria-pressed', 'true');
		expect(tab('Vandaag')).toHaveAttribute('aria-pressed', 'false');
		expect(panel('2026-07-15')).toHaveClass('day-inactive');
		expect(panel('2026-07-16')).not.toHaveClass('day-inactive');
		expect(document.getElementById(tab('Morgen').getAttribute('aria-controls')!)).not.toBeNull();
	});

	it('falls back when the day disappears', async () => {
		const { rerender } = render(Page, props(pageData()));
		await userEvent.setup().click(tab('Vandaag'));
		await rerender(props(pageData({ evaluations: [EVAL_TOMORROW] })));
		expect(tab('Morgen')).toHaveAttribute('aria-pressed', 'true');
		expect(panel('2026-07-16')).not.toHaveClass('day-inactive');
	});
});
