import type { SessionFormValues } from '../../src/lib/session-form.js';
import type { SessionRow } from '../../src/lib/session-model.js';

// Test data only.
export const SLUG = 'Q2x0aHJ1c3RtZTEyMzQ1Ng'; // 22 chars base64url
export const SESSION_ID = '00000000-0000-4000-8000-0000000000a1';
export const NOW_SESSIONS = '2026-07-15T12:30:00.000Z';

export const SESSION_ROW: SessionRow = {
	id: SESSION_ID,
	slug: SLUG,
	spot_id: 'test-strand',
	organizer_name: 'Lars',
	starts_at: '2026-07-18T12:00:00+00:00',
	ends_at: '2026-07-18T16:00:00+00:00',
	note: 'Neem een wetsuit mee',
	seats_free: 3,
	departure_point: 'Utrecht CS',
	tikkie_url: null,
	cancelled_at: null,
	created_at: '2026-07-15T12:00:00+00:00',
	updated_at: '2026-07-15T12:00:00+00:00'
};
export const SESSION_CANCELLED: SessionRow = {
	...SESSION_ROW,
	id: '00000000-0000-4000-8000-0000000000a2',
	slug: 'Q2FuY2VsbGVkU2Vzc2lvbg',
	cancelled_at: '2026-07-15T13:00:00+00:00'
};

/** /go fixtures in the WP-08 format around the switch to winter time (25-10-2026). */
export const GO_URL_DST_DAY =
	'https://example.org/go?spot=test-strand&start=2026-10-25T10%3A00%3A00Z&end=2026-10-25T14%3A00%3A00Z';
export const GO_URL_DST_BEFORE =
	'https://example.org/go?spot=test-strand&start=2026-10-24T10%3A00%3A00Z&end=2026-10-24T14%3A00%3A00Z';
export const GO_URL_DST_NIGHT =
	'https://example.org/go?spot=test-strand&start=2026-10-25T00%3A00%3A00Z&end=2026-10-25T02%3A00%3A00Z';

export const TIKKIE_URL = 'https://tikkie.me/pay/test'; // test data, A18 format

/** A valid create form: test-strand, 2026-07-18 14:00-18:00 local, Lars, rest empty. */
export function validForm(over: Partial<SessionFormValues> = {}): SessionFormValues {
	return {
		spot_id: 'test-strand',
		date: '2026-07-18',
		start_time: '14:00',
		end_time: '18:00',
		organizer_name: 'Lars',
		note: '',
		seats_free: '',
		departure_point: '',
		tikkie_url: '',
		...over
	};
}
