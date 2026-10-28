import { render } from '@testing-library/svelte';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { favoritesState } from './helpers/fake-favorites.js';
import { PROFILE_FULL } from './fixtures/user-data.js';
import { publicSessionPageData } from './fixtures/public-session.js';
import { EVALUATED_AT, NOW_FRESH, SPOT_UNVERIFIED, SPOT_VERIFIED } from './fixtures/spot-data.js';
import type { Profile, SummaryRow } from '../src/lib/types.js';

vi.mock('$app/navigation', () => ({ refreshAll: vi.fn() }));
vi.mock('#lib/supabase.js', () => {
	throw new Error('page tests must not import the Supabase client');
});
vi.mock('#lib/favorites.js', async () => (await import('./helpers/fake-favorites.js')).favoritesModule);
vi.mock('$app/env/public', () => ({ PUBLIC_MAPTILER_KEY: '' }));
vi.mock('#lib/auth.js', () => ({ session: { subscribe: vi.fn() } }));
vi.mock('#lib/rsvp.js', () => ({
	getPublicSession: vi.fn(),
	createRsvp: vi.fn(),
	updateRsvp: vi.fn(),
	deleteRsvp: vi.fn()
}));
vi.mock('#lib/user-data.js', () => ({ updateQuietHours: vi.fn() }));

import ListPage from '../src/routes/+page.svelte';
import SessionPage from '../src/routes/s/[slug]/+page.svelte';
import QuietHoursSettings from '../src/lib/components/QuietHoursSettings.svelte';
import { summarizeSpots } from '../src/lib/view.js';

const props = (data: unknown) => ({ data }) as never;
const row = (valid_at: string, verdict: SummaryRow['verdict']): SummaryRow => ({
	spot_id: 'test-meer',
	valid_at,
	verdict,
	reasons: [],
	evaluated_at: EVALUATED_AT
});

beforeEach(() => {
	favoritesState.set({ status: 'signed_out' });
});

describe('timeline placements', () => {
	it('list: md for today and sm for tomorrow, none without summary', () => {
		const summaries = summarizeSpots(
			[
				row('2026-07-15T12:00:00+00:00', 'go'),
				row('2026-07-15T13:00:00+00:00', 'marginal'),
				row('2026-07-16T08:00:00+00:00', 'no_go')
			],
			new Date(NOW_FRESH)
		);
		render(ListPage, props({ kind: 'ok', now: NOW_FRESH, spots: [SPOT_UNVERIFIED, SPOT_VERIFIED], summaries }));
		const withData = document.querySelector('[data-spot="test-meer"]')!;
		expect(withData.querySelectorAll('.timeline')).toHaveLength(2);
		expect(withData.querySelector('.timeline-md')).not.toBeNull();
		expect(withData.querySelector('.timeline-sm')).not.toBeNull();
		expect(document.querySelector('[data-spot="test-strand"] .timeline')).toBeNull();
	});

	it('public session: bar with window; no bar without evaluations', () => {
		const { unmount } = render(SessionPage, props(publicSessionPageData()));
		expect(document.querySelector('.timeline-lg .timeline-window')).not.toBeNull();
		unmount();
		render(SessionPage, props(publicSessionPageData({ evaluations: null })));
		expect(document.querySelector('.timeline')).toBeNull();
	});

	it('quiet hours: bar for 22-07, none when off', () => {
		const night: Profile = { ...PROFILE_FULL, quiet_from: '22:00:00', quiet_until: '07:00:00' };
		const { unmount } = render(QuietHoursSettings, { userId: 'u', profile: night, onsaved: vi.fn() });
		expect(document.querySelectorAll('.timeline .slot-quiet')).toHaveLength(9);
		unmount();
		render(QuietHoursSettings, {
			userId: 'u',
			profile: { ...night, quiet_from: null, quiet_until: null },
			onsaved: vi.fn()
		});
		expect(document.querySelector('.timeline')).toBeNull();
	});
});
