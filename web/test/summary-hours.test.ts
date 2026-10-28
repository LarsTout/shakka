import { describe, expect, it } from 'vitest';
import { summarizeSpots } from '../src/lib/view.js';
import type { SummaryRow } from '../src/lib/types.js';
import { EVALUATED_AT, NOW_FRESH } from './fixtures/spot-data.js';

const row = (valid_at: string, verdict: SummaryRow['verdict'], reasons: SummaryRow['reasons'] = []): SummaryRow => ({
	spot_id: 'a',
	valid_at,
	verdict,
	reasons,
	evaluated_at: EVALUATED_AT
});

describe('summarizeSpots hours', () => {
	const s = summarizeSpots(
		[
			row('2026-07-16T08:00:00+00:00', 'no_go'),
			row('2026-07-15T13:00:00+00:00', 'marginal'),
			row('2026-07-15T12:00:00+00:00', 'go'),
			row('2026-07-15T21:00:00+00:00', 'no_go', ['dark']),
			row('2026-07-15T11:00:00+00:00', 'go'), // before floorHour(now)
			row('2026-07-17T08:00:00+00:00', 'go') // after tomorrow
		],
		new Date(NOW_FRESH)
	)['a']!;

	it('keeps counted rows sorted, without dark or out-of-range rows', () => {
		expect(s.hours).toEqual([
			{ valid_at: '2026-07-15T12:00:00+00:00', verdict: 'go', reasons: [] },
			{ valid_at: '2026-07-15T13:00:00+00:00', verdict: 'marginal', reasons: [] },
			{ valid_at: '2026-07-16T08:00:00+00:00', verdict: 'no_go', reasons: [] }
		]);
	});
	it('leaves today and tomorrow as before', () => {
		expect(s.today).toMatchObject({ go: 1, marginal: 1, no_go: 0, best: 'go' });
		expect(s.tomorrow).toMatchObject({ go: 0, marginal: 0, no_go: 1, best: 'no_go' });
	});
});
