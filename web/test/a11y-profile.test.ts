import { render, screen } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, it, vi } from 'vitest';
import type { createFakeSupabase } from './helpers/fake-supabase.js';
import { PROFILE_EMPTY, PROFILE_FULL } from './fixtures/user-data.js';
import { SESSION, sessionStore } from './helpers/fake-session.js';
import { expectNoSeriousViolations } from './helpers/axe.js';

const fake = vi.hoisted(() => ({ current: null as unknown as ReturnType<typeof createFakeSupabase> }));
vi.mock('#lib/supabase.js', async () => {
	const { createFakeSupabase } = await import('./helpers/fake-supabase.js');
	fake.current = createFakeSupabase();
	return { supabase: fake.current.client, initialUrlHash: '' };
});
vi.mock('#lib/auth.js', async () => (await import('./helpers/fake-session.js')).authModule);
vi.mock('#lib/account.js', async (importOriginal) => ({
	...(await importOriginal<typeof import('../src/lib/account.js')>()),
	deleteMyAccount: vi.fn(async () => ({ ok: true })),
	cleanUpAfterAccountDeletion: vi.fn(async () => {})
}));

import Page from '../src/routes/profiel/+page.svelte';

beforeEach(() => {
	vi.clearAllMocks();
	fake.current.reset();
	sessionStore.set(undefined);
	vi.spyOn(console, 'warn').mockImplementation(() => {});
});

describe('a11y: profile page', () => {
	it('loaded with a full profile', async () => {
		fake.current.respond('profiles', { data: PROFILE_FULL, error: null });
		sessionStore.set(SESSION);
		render(Page);
		await screen.findByLabelText('Gewicht (kg)');
		await expectNoSeriousViolations();
	});
	it('after saving with errors (weight 25)', async () => {
		fake.current.respond('profiles', { data: PROFILE_EMPTY, error: null });
		sessionStore.set(SESSION);
		render(Page);
		const user = userEvent.setup();
		await user.type(await screen.findByLabelText('Gewicht (kg)'), '25');
		await user.click(screen.getByRole('button', { name: 'Opslaan' }));
		await screen.findByText('Vul een heel getal tussen 30 en 200 kg in.');
		await expectNoSeriousViolations();
	});
	it('with the delete confirmation open', async () => {
		fake.current.respond('profiles', { data: PROFILE_EMPTY, error: null });
		sessionStore.set(SESSION);
		render(Page);
		await screen.findByLabelText('Gewicht (kg)');
		await userEvent.setup().click(screen.getByRole('button', { name: 'Account verwijderen…' }));
		await screen.findByText('Weet je het zeker?');
		await expectNoSeriousViolations();
	});
	it('profile missing: banner plus delete section', async () => {
		fake.current.respond('profiles', { data: null, error: null });
		sessionStore.set(SESSION);
		render(Page);
		await screen.findByText(/Je profiel is niet gevonden/);
		await expectNoSeriousViolations();
	});
});
