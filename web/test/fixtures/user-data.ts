import type { AlertRuleRow, Profile } from '../../src/lib/types.js';
import { USER_ID } from '../helpers/fake-session.js';

const STAMP = '2026-10-15T10:00:00+00:00';

export const PROFILE_EMPTY: Profile = {
	user_id: USER_ID,
	weight_kg: null,
	level: null,
	quiver_m2: [],
	default_min_kn: null,
	default_max_kn: null,
	created_at: STAMP,
	updated_at: STAMP,
	quiet_from: null,
	quiet_until: null
};

export const PROFILE_FULL: Profile = {
	...PROFILE_EMPTY,
	weight_kg: 75,
	level: 'intermediate',
	quiver_m2: [9, 12],
	default_min_kn: 14,
	default_max_kn: 26
};

export function ruleRow(spotId: string, overrides: Partial<AlertRuleRow> = {}): AlertRuleRow {
	return {
		user_id: USER_ID,
		spot_id: spotId,
		enabled: true,
		min_kn: null,
		max_kn: null,
		dir_classes: null,
		weekdays: null,
		earliest_local: null,
		latest_local: null,
		min_go_hours: null,
		days_ahead: null,
		updated_at: STAMP,
		...overrides
	};
}
