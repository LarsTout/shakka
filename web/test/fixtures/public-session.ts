import type { PublicRsvp, PublicSessionInfo } from '../../src/lib/rsvp-types.js';
import type { Evaluation } from '../../src/lib/types.js';

// Test data only. Own file, separate from fixtures/session-data.ts (WP-20).
export const SLUG = 'Q2x0aHJ1c3RtZTEyMzQ1Ng';
export const NOW = '2026-07-18T09:00:00.000Z'; // local za 18 jul 11:00
export const NOW_STALE = '2026-07-18T11:06:00.000Z';
export const NOW_ENDED = '2026-07-18T16:00:00.000Z'; // equals ends_at

export const TOKEN = 'T'.repeat(43);
export const TOKEN_NEW = 'U'.repeat(43);

export const EVA_ID = 'e0000000-0000-4000-8000-000000000001';
export const SANNE_ID = 'e0000000-0000-4000-8000-000000000002';
export const NOOR_ID = 'e0000000-0000-4000-8000-000000000003';
export const TOM_ID = 'e0000000-0000-4000-8000-000000000004';
export const NEW_ID = 'e0000000-0000-4000-8000-000000000005';

export const SESSION_INFO: PublicSessionInfo = {
	slug: SLUG,
	spot_id: 'test-strand',
	spot_name: 'Teststrand',
	organizer_name: 'Lars',
	starts_at: '2026-07-18T12:00:00+00:00',
	ends_at: '2026-07-18T16:00:00+00:00',
	note: 'Parkeren bij de strandopgang',
	seats_free: 3,
	departure_point: 'Utrecht CS',
	tikkie_url: 'https://tikkie.me/pay/test',
	cancelled: false,
	rsvps_closed: false
};

export const RSVP_EVA: PublicRsvp = {
	id: EVA_ID,
	first_name: 'Eva',
	ride: 'offers_ride',
	seats_offered: 2,
	rides_with: null,
	created_at: '2026-07-17T18:01:00+00:00'
};
export const RSVP_SANNE: PublicRsvp = {
	id: SANNE_ID,
	first_name: 'Sanne',
	ride: 'needs_ride',
	seats_offered: null,
	rides_with: EVA_ID,
	created_at: '2026-07-17T18:02:00+00:00'
};
export const RSVP_NOOR: PublicRsvp = {
	id: NOOR_ID,
	first_name: 'Noor',
	ride: 'needs_ride',
	seats_offered: null,
	rides_with: null,
	created_at: '2026-07-17T18:03:00+00:00'
};
export const RSVP_TOM: PublicRsvp = {
	id: TOM_ID,
	first_name: 'Tom',
	ride: 'own',
	seats_offered: null,
	rides_with: null,
	created_at: '2026-07-17T18:04:00+00:00'
};
export const RSVP_NEW: PublicRsvp = {
	id: NEW_ID,
	first_name: 'Ilse',
	ride: 'own',
	seats_offered: null,
	rides_with: null,
	created_at: '2026-07-17T18:05:00+00:00'
};

export const FOUR_RSVPS: PublicRsvp[] = [RSVP_EVA, RSVP_SANNE, RSVP_NOOR, RSVP_TOM];

export const SESSION_JSON = { session: SESSION_INFO, rsvps: FOUR_RSVPS };

const EVAL_BASE = {
	spot_id: 'test-strand',
	tide_level_cm: null,
	evaluated_at: '2026-07-18T08:05:00+00:00'
};
export const SESSION_EVALS: Evaluation[] = [
	{
		...EVAL_BASE,
		valid_at: '2026-07-18T12:00:00+00:00',
		verdict: 'go',
		reasons: [],
		wind_kn: 18.4,
		gust_kn: 23.6,
		dir_deg: 250,
		dir_class: 'onshore',
		confidence: 'high'
	},
	{
		...EVAL_BASE,
		valid_at: '2026-07-18T13:00:00+00:00',
		verdict: 'go',
		reasons: [],
		wind_kn: 19.0,
		gust_kn: 24.0,
		dir_deg: 255,
		dir_class: 'onshore',
		confidence: 'high'
	},
	{
		...EVAL_BASE,
		valid_at: '2026-07-18T14:00:00+00:00',
		verdict: 'marginal',
		reasons: ['low_confidence'],
		wind_kn: 14.0,
		gust_kn: null,
		dir_deg: 300,
		dir_class: 'side_onshore',
		confidence: 'low'
	},
	{
		...EVAL_BASE,
		valid_at: '2026-07-18T15:00:00+00:00',
		verdict: 'no_go',
		reasons: ['offshore'],
		wind_kn: 15.2,
		gust_kn: 19.8,
		dir_deg: 90,
		dir_class: 'offshore',
		confidence: 'medium'
	}
];

export function publicSessionPageData(overrides: Record<string, unknown> = {}) {
	return {
		kind: 'ok' as const,
		now: NOW,
		slug: SLUG,
		session: SESSION_INFO,
		rsvps: [...FOUR_RSVPS],
		evaluations: SESSION_EVALS,
		...overrides
	};
}
