import { render, screen } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { createFakeSupabase } from './helpers/fake-supabase.js';
import { SESSION, USER_ID, sessionStore } from './helpers/fake-session.js';

const fake = vi.hoisted(() => ({ current: null as unknown as ReturnType<typeof createFakeSupabase> }));
vi.mock('#lib/supabase.js', async () => {
	const { createFakeSupabase } = await import('./helpers/fake-supabase.js');
	fake.current = createFakeSupabase();
	return { supabase: fake.current.client, initialUrlHash: '' };
});
vi.mock('#lib/auth.js', async () => (await import('./helpers/fake-session.js')).authModule);

import FavoriteStar from '../src/lib/components/FavoriteStar.svelte';

beforeEach(() => {
	vi.clearAllMocks();
	fake.current.reset();
	sessionStore.set(undefined);
});

const star = () => screen.findByRole('button', { name: 'Favoriet: Teststrand' });
const props = { spotId: 'test-strand', spotName: 'Teststrand' };

describe('FavoriteStar (AC-5, AC-6)', () => {
	it('toggles with an insert and a delete', async () => {
		vi.spyOn(console, 'warn').mockImplementation(() => {});
		fake.current.respond('favorites', { data: [], error: null });
		sessionStore.set(SESSION);
		render(FavoriteStar, props);
		const button = await star();
		await vi.waitFor(() => expect(button).not.toBeDisabled());
		expect(button).toHaveAttribute('aria-pressed', 'false');

		const user = userEvent.setup();
		await user.click(button);
		expect(fake.current.calls.at(-1)).toEqual({
			table: 'favorites',
			ops: [['insert', { user_id: USER_ID, spot_id: 'test-strand' }]]
		});
		await vi.waitFor(() => expect(button).toHaveAttribute('aria-pressed', 'true'));

		await vi.waitFor(() => expect(button).not.toBeDisabled());
		await user.click(button);
		expect(fake.current.calls.at(-1)).toEqual({
			table: 'favorites',
			ops: [['delete'], ['eq', 'user_id', USER_ID], ['eq', 'spot_id', 'test-strand']]
		});
		await vi.waitFor(() => expect(button).toHaveAttribute('aria-pressed', 'false'));
	});

	it('shows "Niet opgeslagen" and reverts when the insert fails', async () => {
		vi.spyOn(console, 'warn').mockImplementation(() => {});
		fake.current.respond(
			'favorites',
			{ data: [], error: null },
			{ data: null, error: { code: '42501' } }
		);
		sessionStore.set(SESSION);
		render(FavoriteStar, props);
		const button = await star();
		await vi.waitFor(() => expect(button).not.toBeDisabled());
		await userEvent.setup().click(button);
		expect(await screen.findByText('Niet opgeslagen')).toBeInTheDocument();
		expect(button).toHaveAttribute('aria-pressed', 'false');
	});

	it.each([null, undefined])('renders nothing and queries nothing for session %s', async (s) => {
		sessionStore.set(s);
		render(FavoriteStar, props);
		await new Promise((r) => setTimeout(r, 0));
		expect(screen.queryByRole('button')).toBeNull();
		expect(fake.current.calls).toHaveLength(0);
	});
});
