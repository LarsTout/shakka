import { render, screen, within } from '@testing-library/svelte';
import { tick } from 'svelte';
import { afterEach, beforeEach, describe, it, vi } from 'vitest';
import type { createFakeSupabase } from './helpers/fake-supabase.js';
import { SPOT_UNVERIFIED, SPOT_VERIFIED } from './fixtures/spot-data.js';
import { PROFILE_FULL, ruleRow } from './fixtures/user-data.js';
import { SESSION, sessionStore } from './helpers/fake-session.js';
import { installPushEnv } from './helpers/fake-push.js';
import { expectNoSeriousViolations } from './helpers/axe.js';

const fake = vi.hoisted(() => ({ current: null as unknown as ReturnType<typeof createFakeSupabase> }));
vi.mock('#lib/supabase.js', async () => {
	const { createFakeSupabase } = await import('./helpers/fake-supabase.js');
	fake.current = createFakeSupabase();
	return { supabase: fake.current.client, initialUrlHash: '' };
});
vi.mock('$app/env/public', async () => (await import('./helpers/fake-push.js')).publicEnv);
vi.mock('#lib/auth.js', async () => (await import('./helpers/fake-session.js')).authModule);

import Page from '../src/routes/alerts/+page.svelte';

let env: ReturnType<typeof installPushEnv> | undefined;
beforeEach(() => {
	vi.clearAllMocks();
	fake.current.reset();
	sessionStore.set(undefined);
	vi.spyOn(console, 'warn').mockImplementation(() => {});
	env = installPushEnv();
});
afterEach(() => env?.uninstall());

function serve() {
	fake.current.respond('profiles', { data: PROFILE_FULL, error: null });
	fake.current.respond('favorites', { data: [{ spot_id: 'test-meer' }, { spot_id: 'test-strand' }], error: null });
	fake.current.respond('alert_rules', { data: [ruleRow('test-meer', { min_kn: 18 })], error: null });
	fake.current.respond('spots', { data: [SPOT_VERIFIED, SPOT_UNVERIFIED], error: null });
}

describe('a11y: alerts page', () => {
	it('signed in with push settings', async () => {
		serve();
		sessionStore.set(SESSION);
		render(Page);
		await screen.findByRole('heading', { name: 'Testmeer' });
		await expectNoSeriousViolations();
	});
	it('one rule expanded', async () => {
		serve();
		sessionStore.set(SESSION);
		const { container } = render(Page);
		await screen.findByRole('heading', { name: 'Testmeer' });
		const section = container.querySelector('section.alert-rule') as HTMLElement;
		section.querySelector('details')!.open = true;
		await tick();
		await within(section).findByLabelText('Minimale wind (kn)');
		await expectNoSeriousViolations();
	});
});
