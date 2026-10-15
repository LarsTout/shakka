import { render, screen } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { createFakeSupabase } from './helpers/fake-supabase.js';
import { writeCalls } from './helpers/fake-supabase.js';
import { PROFILE_EMPTY, PROFILE_FULL } from './fixtures/user-data.js';
import { SESSION, USER_ID, sessionStore } from './helpers/fake-session.js';

const fake = vi.hoisted(() => ({ current: null as unknown as ReturnType<typeof createFakeSupabase> }));
vi.mock('#lib/supabase.js', async () => {
	const { createFakeSupabase } = await import('./helpers/fake-supabase.js');
	fake.current = createFakeSupabase();
	return { supabase: fake.current.client, initialUrlHash: '' };
});
vi.mock('#lib/auth.js', async () => (await import('./helpers/fake-session.js')).authModule);

import Page from '../src/routes/profiel/+page.svelte';
import { PROFILE_COLUMNS } from '../src/lib/types.js';

beforeEach(() => {
	vi.clearAllMocks();
	fake.current.reset();
	sessionStore.set(undefined);
	vi.spyOn(console, 'warn').mockImplementation(() => {});
});

const loaded = async (profile = PROFILE_EMPTY) => {
	fake.current.respond('profiles', { data: profile, error: null });
	sessionStore.set(SESSION);
	render(Page);
	return screen.findByLabelText('Gewicht (kg)');
};

describe('profile page', () => {
	it('AC-6: signed out shows the login prompt and queries nothing', async () => {
		sessionStore.set(null);
		render(Page);
		expect(screen.getByText('Log in om je profiel te bewerken.')).toBeInTheDocument();
		expect(screen.getByRole('link', { name: 'Inloggen' })).toHaveAttribute('href', '/login');
		await new Promise((r) => setTimeout(r, 0));
		expect(fake.current.calls).toHaveLength(0);
	});

	it('E1: unknown session shows Laden... and queries nothing', async () => {
		render(Page);
		expect(screen.getByText('Laden…')).toBeInTheDocument();
		await new Promise((r) => setTimeout(r, 0));
		expect(fake.current.calls).toHaveLength(0);
		sessionStore.set(null);
		await new Promise((r) => setTimeout(r, 0));
		expect(fake.current.calls).toHaveLength(0);
	});

	it('AC-4: weight 25 is refused without a write', async () => {
		const weight = await loaded();
		const user = userEvent.setup();
		await user.type(weight, '25');
		await user.click(screen.getByRole('button', { name: 'Opslaan' }));
		expect(screen.getByText('Vul een heel getal tussen 30 en 200 kg in.')).toBeInTheDocument();
		expect(writeCalls(fake.current.calls)).toHaveLength(0);
	});

	it('AC-4: a quiver size of 25 is refused', async () => {
		await loaded();
		const user = userEvent.setup();
		await user.click(screen.getByRole('button', { name: 'Kite toevoegen' }));
		await user.type(screen.getByLabelText('Kite 1 (m²)'), '25');
		await user.click(screen.getByRole('button', { name: 'Opslaan' }));
		expect(screen.getByText(/Elke kitemaat moet tussen 3 en 21 m² liggen/)).toBeInTheDocument();
		expect(writeCalls(fake.current.calls)).toHaveLength(0);
	});

	it('AC-4: min 20 / max 15 is refused', async () => {
		await loaded();
		const user = userEvent.setup();
		await user.type(screen.getByLabelText('Standaard minimale wind (kn)'), '20');
		await user.type(screen.getByLabelText('Standaard maximale wind (kn)'), '15');
		await user.click(screen.getByRole('button', { name: 'Opslaan' }));
		expect(screen.getByText('De maximale wind moet hoger zijn dan de minimale wind.')).toBeInTheDocument();
		expect(writeCalls(fake.current.calls)).toHaveLength(0);
	});

	it('saves exactly one update with the five columns', async () => {
		const weight = await loaded();
		const saved = { ...PROFILE_FULL, default_min_kn: null, default_max_kn: null };
		fake.current.respond('profiles', { data: saved, error: null });
		const user = userEvent.setup();
		await user.type(weight, '75');
		await user.selectOptions(screen.getByLabelText('Niveau'), 'Gemiddeld');
		await user.click(screen.getByRole('button', { name: 'Kite toevoegen' }));
		await user.type(screen.getByLabelText('Kite 1 (m²)'), '9');
		await user.click(screen.getByRole('button', { name: 'Kite toevoegen' }));
		await user.type(screen.getByLabelText('Kite 2 (m²)'), '12');
		await user.click(screen.getByRole('button', { name: 'Opslaan' }));
		expect(await screen.findByText('Opgeslagen.')).toBeInTheDocument();
		const writes = writeCalls(fake.current.calls);
		expect(writes).toHaveLength(1);
		expect(writes[0]).toEqual({
			table: 'profiles',
			ops: [
				[
					'update',
					{ weight_kg: 75, level: 'intermediate', quiver_m2: [9, 12], default_min_kn: null, default_max_kn: null }
				],
				['eq', 'user_id', USER_ID],
				['select', PROFILE_COLUMNS.join(',')],
				['single']
			]
		});
	});

	it('shows the kn hints and can remove a kite', async () => {
		await loaded(PROFILE_FULL);
		expect(screen.getByText('standaard: de waarde van de spot, anders 12 kn (Shakka)')).toBeInTheDocument();
		const user = userEvent.setup();
		expect(screen.getByLabelText('Kite 2 (m²)')).toHaveValue('12');
		await user.click(screen.getByRole('button', { name: 'Verwijder kite 1' }));
		expect(screen.queryByLabelText('Kite 2 (m²)')).toBeNull();
		expect(screen.getByLabelText('Kite 1 (m²)')).toHaveValue('12');
	});

	it('disables adding kites at 10', async () => {
		await loaded({ ...PROFILE_EMPTY, quiver_m2: [3, 4, 5, 6, 7, 8, 9, 10, 11, 12] });
		expect(screen.getByRole('button', { name: 'Kite toevoegen' })).toBeDisabled();
	});

	it('a missing profile shows the message and no form', async () => {
		fake.current.respond('profiles', { data: null, error: null });
		sessionStore.set(SESSION);
		render(Page);
		expect(await screen.findByRole('alert')).toHaveTextContent(
			'Je profiel is niet gevonden. Log uit en weer in. Helpt dat niet, neem dan contact op met de beheerder.'
		);
		expect(screen.queryByLabelText('Gewicht (kg)')).toBeNull();
	});

	it('a load error shows an alert and retry queries again', async () => {
		fake.current.respond('profiles', { data: null, error: { code: '500' } });
		sessionStore.set(SESSION);
		render(Page);
		expect(await screen.findByRole('alert')).toHaveTextContent('Je profiel kon niet worden geladen');
		fake.current.respond('profiles', { data: PROFILE_EMPTY, error: null });
		await userEvent.setup().click(screen.getByRole('button', { name: 'Opnieuw proberen' }));
		expect(await screen.findByLabelText('Gewicht (kg)')).toBeInTheDocument();
		expect(fake.current.calls).toHaveLength(2);
	});

	it('a save failure shows the generic message', async () => {
		const weight = await loaded();
		fake.current.respond('profiles', { data: null, error: { code: 'PGRST116' } });
		await userEvent.setup().type(weight, '75');
		await userEvent.setup().click(screen.getByRole('button', { name: 'Opslaan' }));
		expect(await screen.findByText('Opslaan is niet gelukt. Probeer het opnieuw.')).toBeInTheDocument();
	});
});
