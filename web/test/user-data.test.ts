import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { createFakeSupabase } from './helpers/fake-supabase.js';
import { PROFILE_FULL, ruleRow } from './fixtures/user-data.js';
import { USER_ID } from './helpers/fake-session.js';

const fake = vi.hoisted(() => ({ current: null as unknown as ReturnType<typeof createFakeSupabase> }));
vi.mock('#lib/supabase.js', async () => {
	const { createFakeSupabase } = await import('./helpers/fake-supabase.js');
	fake.current = createFakeSupabase();
	return { supabase: fake.current.client, initialUrlHash: '' };
});

import { DataError } from '../src/lib/data.js';
import {
	addFavorite,
	getProfile,
	listAlertRules,
	listFavoriteSpotIds,
	removeFavorite,
	resetAlertRule,
	saveAlertRule,
	updateProfile
} from '../src/lib/user-data.js';
import {
	ALERT_RULE_COLUMNS,
	PROFILE_COLUMNS,
	PROFILE_EDITABLE_COLUMNS,
	RULE_FIELDS,
	type AlertRuleValues,
	type ProfileUpdate
} from '../src/lib/types.js';

beforeEach(() => {
	vi.clearAllMocks();
	fake.current.reset();
});

const asc = { ascending: true };
const VALUES: ProfileUpdate = {
	weight_kg: 75,
	level: 'intermediate',
	quiver_m2: [9, 12],
	default_min_kn: null,
	default_max_kn: null
};
const RULE_VALUES: AlertRuleValues = {
	enabled: true,
	min_kn: 14,
	max_kn: null,
	dir_classes: null,
	weekdays: [6, 7],
	earliest_local: '17:00:00',
	latest_local: null,
	min_go_hours: null,
	days_ahead: 0
};

describe('profiles', () => {
	it('getProfile', async () => {
		fake.current.respond('profiles', { data: PROFILE_FULL, error: null });
		expect(await getProfile(USER_ID)).toEqual(PROFILE_FULL);
		expect(fake.current.calls).toEqual([
			{
				table: 'profiles',
				ops: [['select', PROFILE_COLUMNS.join(',')], ['eq', 'user_id', USER_ID], ['maybeSingle']]
			}
		]);
	});
	it('getProfile without a row gives null', async () => {
		fake.current.respond('profiles', { data: null, error: null });
		expect(await getProfile(USER_ID)).toBeNull();
	});
	it('getProfile throws a DataError with the code only', async () => {
		fake.current.respond('profiles', { data: null, error: { code: '42501', message: 'secret detail' } });
		const e = await getProfile(USER_ID).catch((x) => x);
		expect(e).toBeInstanceOf(DataError);
		expect(e.code).toBe('42501');
		expect(e.message).not.toContain('secret');
	});
	it('updateProfile writes exactly the five columns', async () => {
		fake.current.respond('profiles', { data: PROFILE_FULL, error: null });
		const withExtra = { ...VALUES, updated_at: 'x', user_id: 'y' } as unknown as ProfileUpdate;
		expect(await updateProfile(USER_ID, withExtra)).toEqual(PROFILE_FULL);
		const call = fake.current.calls[0]!;
		expect(call.ops).toEqual([
			['update', VALUES],
			['eq', 'user_id', USER_ID],
			['select', PROFILE_COLUMNS.join(',')],
			['single']
		]);
		expect(Object.keys(call.ops[0]![1] as object).sort()).toEqual([...PROFILE_EDITABLE_COLUMNS].sort());
	});
	it('updateProfile reports PGRST116', async () => {
		fake.current.respond('profiles', { data: null, error: { code: 'PGRST116' } });
		await expect(updateProfile(USER_ID, VALUES)).rejects.toMatchObject({ code: 'PGRST116' });
	});
	it('selects never mention the legacy column', () => {
		expect(PROFILE_COLUMNS.join(',')).not.toMatch(/telegram/);
	});
});

describe('favorites', () => {
	it('listFavoriteSpotIds', async () => {
		fake.current.respond('favorites', { data: [{ spot_id: 'a' }, { spot_id: 'b' }], error: null });
		expect(await listFavoriteSpotIds(USER_ID)).toEqual(['a', 'b']);
		expect(fake.current.calls).toEqual([
			{
				table: 'favorites',
				ops: [['select', 'spot_id'], ['eq', 'user_id', USER_ID], ['order', 'spot_id', asc], ['range', 0, 999]]
			}
		]);
	});
	it('addFavorite', async () => {
		await addFavorite(USER_ID, 'test-meer');
		expect(fake.current.calls).toEqual([
			{ table: 'favorites', ops: [['insert', { user_id: USER_ID, spot_id: 'test-meer' }]] }
		]);
	});
	it('addFavorite treats 23505 as success and hides details otherwise', async () => {
		fake.current.respond('favorites', { data: null, error: { code: '23505' } });
		await expect(addFavorite(USER_ID, 'x')).resolves.toBeUndefined();
		fake.current.respond('favorites', { data: null, error: { code: '42501', message: 'secret detail' } });
		const e = await addFavorite(USER_ID, 'x').catch((x) => x);
		expect(e).toBeInstanceOf(DataError);
		expect(e.code).toBe('42501');
		expect(e.message).not.toContain('secret');
	});
	it('removeFavorite', async () => {
		await removeFavorite(USER_ID, 'test-meer');
		expect(fake.current.calls).toEqual([
			{
				table: 'favorites',
				ops: [['delete'], ['eq', 'user_id', USER_ID], ['eq', 'spot_id', 'test-meer']]
			}
		]);
		fake.current.respond('favorites', { data: null, error: { code: 'X' } });
		await expect(removeFavorite(USER_ID, 'x')).rejects.toBeInstanceOf(DataError);
	});
});

describe('alert rules', () => {
	it('listAlertRules', async () => {
		const row = ruleRow('test-meer');
		fake.current.respond('alert_rules', { data: [row], error: null });
		expect(await listAlertRules(USER_ID)).toEqual([row]);
		expect(fake.current.calls).toEqual([
			{
				table: 'alert_rules',
				ops: [
					['select', ALERT_RULE_COLUMNS.join(',')],
					['eq', 'user_id', USER_ID],
					['order', 'spot_id', asc],
					['range', 0, 999]
				]
			}
		]);
	});
	it('saveAlertRule upserts exactly user_id, spot_id and the nine fields', async () => {
		const saved = ruleRow('test-meer', { min_kn: 14 });
		fake.current.respond('alert_rules', { data: saved, error: null });
		const withExtra = { ...RULE_VALUES, updated_at: 'x' } as unknown as AlertRuleValues;
		expect(await saveAlertRule(USER_ID, 'test-meer', withExtra)).toEqual(saved);
		const ops = fake.current.calls[0]!.ops;
		expect(ops).toEqual([
			['upsert', { user_id: USER_ID, spot_id: 'test-meer', ...RULE_VALUES }, { onConflict: 'user_id,spot_id' }],
			['select', ALERT_RULE_COLUMNS.join(',')],
			['single']
		]);
		expect(Object.keys(ops[0]![1] as object).sort()).toEqual(['spot_id', 'user_id', ...RULE_FIELDS].sort());
	});
	it('saveAlertRule reports 23503', async () => {
		fake.current.respond('alert_rules', { data: null, error: { code: '23503', message: 'secret detail' } });
		const e = await saveAlertRule(USER_ID, 'x', RULE_VALUES).catch((x) => x);
		expect(e).toBeInstanceOf(DataError);
		expect(e.code).toBe('23503');
		expect(e.message).not.toContain('secret');
	});
	it('resetAlertRule', async () => {
		await resetAlertRule(USER_ID, 'test-meer');
		expect(fake.current.calls).toEqual([
			{
				table: 'alert_rules',
				ops: [['delete'], ['eq', 'user_id', USER_ID], ['eq', 'spot_id', 'test-meer']]
			}
		]);
	});
});
