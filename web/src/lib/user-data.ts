import { supabase } from '#lib/supabase.js';
import { DataError, fetchAllPages } from './data.js';
import {
	ALERT_RULE_COLUMNS,
	PROFILE_COLUMNS,
	type AlertRuleRow,
	type AlertRuleValues,
	type Profile,
	type ProfileUpdate
} from './types.js';

// The only module that reads or writes profiles, favorites and alert_rules.

export async function getProfile(userId: string): Promise<Profile | null> {
	const { data, error } = await supabase
		.from('profiles')
		.select(PROFILE_COLUMNS.join(','))
		.eq('user_id', userId)
		.maybeSingle();
	if (error) throw new DataError('getProfile', error.code ?? null);
	return (data as unknown as Profile | null) ?? null;
}

/** Writes exactly the five columns `authenticated` may update (column grant, WP-01). */
export async function updateProfile(userId: string, values: ProfileUpdate): Promise<Profile> {
	const payload = {
		weight_kg: values.weight_kg,
		level: values.level,
		quiver_m2: values.quiver_m2,
		default_min_kn: values.default_min_kn,
		default_max_kn: values.default_max_kn
	};
	const { data, error } = await supabase
		.from('profiles')
		.update(payload)
		.eq('user_id', userId)
		.select(PROFILE_COLUMNS.join(','))
		.single();
	if (error) throw new DataError('updateProfile', error.code ?? null);
	return data as unknown as Profile;
}

export async function listFavoriteSpotIds(userId: string): Promise<string[]> {
	const rows = await fetchAllPages<{ spot_id: string }>('listFavoriteSpotIds', () =>
		supabase
			.from('favorites')
			.select('spot_id')
			.eq('user_id', userId)
			.order('spot_id', { ascending: true })
	);
	return rows.map((r) => r.spot_id);
}

export async function addFavorite(userId: string, spotId: string): Promise<void> {
	const { error } = await supabase.from('favorites').insert({ user_id: userId, spot_id: spotId });
	// 23505: already a favorite (another tab); that is the desired state.
	if (error && error.code !== '23505') throw new DataError('addFavorite', error.code ?? null);
}

export async function removeFavorite(userId: string, spotId: string): Promise<void> {
	const { error } = await supabase
		.from('favorites')
		.delete()
		.eq('user_id', userId)
		.eq('spot_id', spotId);
	if (error) throw new DataError('removeFavorite', error.code ?? null);
}

export function listAlertRules(userId: string): Promise<AlertRuleRow[]> {
	return fetchAllPages<AlertRuleRow>('listAlertRules', () =>
		supabase
			.from('alert_rules')
			.select(ALERT_RULE_COLUMNS.join(','))
			.eq('user_id', userId)
			.order('spot_id', { ascending: true })
	);
}

export async function saveAlertRule(
	userId: string,
	spotId: string,
	values: AlertRuleValues
): Promise<AlertRuleRow> {
	const { data, error } = await supabase
		.from('alert_rules')
		.upsert(
			{
				user_id: userId,
				spot_id: spotId,
				enabled: values.enabled,
				min_kn: values.min_kn,
				max_kn: values.max_kn,
				dir_classes: values.dir_classes,
				weekdays: values.weekdays,
				earliest_local: values.earliest_local,
				latest_local: values.latest_local,
				min_go_hours: values.min_go_hours,
				days_ahead: values.days_ahead
			},
			{ onConflict: 'user_id,spot_id' }
		)
		.select(ALERT_RULE_COLUMNS.join(','))
		.single();
	if (error) throw new DataError('saveAlertRule', error.code ?? null);
	return data as unknown as AlertRuleRow;
}

export async function resetAlertRule(userId: string, spotId: string): Promise<void> {
	const { error } = await supabase
		.from('alert_rules')
		.delete()
		.eq('user_id', userId)
		.eq('spot_id', spotId);
	if (error) throw new DataError('resetAlertRule', error.code ?? null);
}
