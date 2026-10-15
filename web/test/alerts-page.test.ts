import { render, screen, within } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import { tick } from 'svelte';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { createFakeSupabase } from './helpers/fake-supabase.js';
import { SPOT_UNVERIFIED, SPOT_VERIFIED } from './fixtures/spot-data.js';
import { PROFILE_FULL, ruleRow } from './fixtures/user-data.js';
import { SESSION, sessionStore } from './helpers/fake-session.js';

const fake = vi.hoisted(() => ({ current: null as unknown as ReturnType<typeof createFakeSupabase> }));
vi.mock('#lib/supabase.js', async () => {
	const { createFakeSupabase } = await import('./helpers/fake-supabase.js');
	fake.current = createFakeSupabase();
	return { supabase: fake.current.client, initialUrlHash: '' };
});
vi.mock('#lib/auth.js', async () => (await import('./helpers/fake-session.js')).authModule);

import Page from '../src/routes/alerts/+page.svelte';
import type { AlertRuleRow, Profile } from '../src/lib/types.js';

beforeEach(() => {
	vi.clearAllMocks();
	fake.current.reset();
	sessionStore.set(undefined);
	vi.spyOn(console, 'warn').mockImplementation(() => {});
});

function serve(opts: {
	profile?: Profile | null;
	favorites?: string[];
	rules?: AlertRuleRow[];
}) {
	fake.current.respond('profiles', { data: opts.profile === undefined ? PROFILE_FULL : opts.profile, error: null });
	fake.current.respond('favorites', {
		data: (opts.favorites ?? ['test-meer', 'test-strand']).map((spot_id) => ({ spot_id })),
		error: null
	});
	fake.current.respond('alert_rules', {
		data: opts.rules ?? [ruleRow('test-meer', { min_kn: 18 })],
		error: null
	});
	fake.current.respond('spots', { data: [SPOT_VERIFIED, SPOT_UNVERIFIED], error: null });
}
const sections = (c: HTMLElement) => [...c.querySelectorAll('section.alert-rule')] as HTMLElement[];
async function open(section: HTMLElement) {
	const details = section.querySelector('details')!;
	details.open = true;
	await tick();
	return within(section);
}

describe('alerts page', () => {
	it('AC-6: signed out shows the login prompt, unknown shows Laden..., both without queries', async () => {
		render(Page);
		expect(screen.getByText('Laden…')).toBeInTheDocument();
		sessionStore.set(null);
		await tick();
		expect(screen.getByText('Log in om je alerts in te stellen.')).toBeInTheDocument();
		await new Promise((r) => setTimeout(r, 0));
		expect(fake.current.calls).toHaveLength(0);
	});

	it('shows a section per favorite with its summary', async () => {
		serve({});
		sessionStore.set(SESSION);
		const { container } = render(Page);
		await screen.findByRole('heading', { name: 'Testmeer' });
		const [meer, strand] = sections(container);
		expect(meer).toHaveTextContent('Testmeer');
		expect(meer).toHaveTextContent('Aan · 18–26 kn · min. 2 uur go · vandaag plus 3 dagen');
		expect(strand).toHaveTextContent('Teststrand');
		expect(strand).toHaveTextContent('Deze spot is nog niet geverifieerd.');
		expect(strand).toHaveTextContent('Aan · 14–26 kn');
		expect(meer.querySelector('details')!.open).toBe(false);
	});

	it('warns about a stored conflict', async () => {
		serve({ profile: { ...PROFILE_FULL, default_min_kn: null, default_max_kn: 20 }, rules: [ruleRow('test-meer', { min_kn: 25 })] });
		sessionStore.set(SESSION);
		const { container } = render(Page);
		await screen.findByRole('heading', { name: 'Testmeer' });
		expect(within(sections(container)[0]!).getByRole('note')).toHaveTextContent('Deze instellingen botsen');
	});

	it('E28: no favorites shows the explanation with a link to the list', async () => {
		serve({ favorites: [], rules: [] });
		sessionStore.set(SESSION);
		render(Page);
		expect(await screen.findByText(/Je hebt nog geen favorieten/)).toBeInTheDocument();
		expect(screen.getByRole('link', { name: 'lijst' })).toHaveAttribute('href', '/');
	});

	it('updates the summary after saving a rule', async () => {
		serve({});
		sessionStore.set(SESSION);
		const { container } = render(Page);
		await screen.findByRole('heading', { name: 'Testmeer' });
		const meer = sections(container)[0]!;
		const w = await open(meer);
		fake.current.respond('alert_rules', { data: ruleRow('test-meer', { min_kn: 16 }), error: null });
		const min = w.getByLabelText('Minimale wind (kn)');
		await userEvent.setup().clear(min);
		await userEvent.setup().type(min, '16');
		await userEvent.setup().click(w.getByRole('button', { name: 'Opslaan' }));
		await vi.waitFor(() =>
			expect(meer.querySelector('.rule-summary')).toHaveTextContent(
				'Aan · 16–26 kn · min. 2 uur go · vandaag plus 3 dagen'
			)
		);
	});

	it('a load error shows a banner and retry queries again', async () => {
		fake.current.respond('profiles', { data: null, error: { code: '500' } });
		sessionStore.set(SESSION);
		render(Page);
		expect(await screen.findByRole('alert')).toHaveTextContent(
			'De alertinstellingen konden niet worden geladen.'
		);
		serve({});
		await userEvent.setup().click(screen.getByRole('button', { name: 'Opnieuw proberen' }));
		expect(await screen.findByRole('heading', { name: 'Testmeer' })).toBeInTheDocument();
	});
});
