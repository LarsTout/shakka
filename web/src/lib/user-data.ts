import { supabase } from '#lib/supabase.js';
import { DataError, fetchAllPages } from './data.js';
import {
	SESSION_COLUMNS,
	type NewSession,
	type SessionRow,
	type SessionUpdate
} from './session-model.js';
import {
	ALERT_RULE_COLUMNS,
	PROFILE_COLUMNS,
	PUSH_SUBSCRIPTION_COLUMNS,
	type AlertRuleRow,
	type AlertRuleValues,
	type OwnPushSubscription,
	type Profile,
	type ProfileUpdate,
	type QuietHoursUpdate,
	type PushSubscriptionKeys
} from './types.js';

// The only module that reads or writes profiles, favorites, alert_rules, push_subscriptions and sessions.

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

/** Writes exactly quiet_from and quiet_until (column grant, WP-30). */
export async function updateQuietHours(
	userId: string,
	values: QuietHoursUpdate
): Promise<Profile> {
	const payload = { quiet_from: values.quiet_from, quiet_until: values.quiet_until };
	const { data, error } = await supabase
		.from('profiles')
		.update(payload)
		.eq('user_id', userId)
		.select(PROFILE_COLUMNS.join(','))
		.single();
	if (error) throw new DataError('updateQuietHours', error.code ?? null);
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

/** Own push subscriptions, newest first (RLS limits this to the signed-in user). */
export async function listOwnPushSubscriptions(): Promise<OwnPushSubscription[]> {
	const { data, error } = await supabase
		.from('push_subscriptions')
		.select(PUSH_SUBSCRIPTION_COLUMNS.join(','))
		.order('created_at', { ascending: false });
	if (error) throw new DataError('listOwnPushSubscriptions', error.code ?? null);
	return (data as unknown as OwnPushSubscription[] | null) ?? [];
}

/** Inserts exactly endpoint, p256dh and auth; user_id comes from the column default (WP-17). */
export async function addPushSubscription(keys: PushSubscriptionKeys): Promise<'added' | 'exists'> {
	const { error } = await supabase
		.from('push_subscriptions')
		.insert({ endpoint: keys.endpoint, p256dh: keys.p256dh, auth: keys.auth });
	if (!error) return 'added';
	if (error.code === '23505') return 'exists';
	throw new DataError('addPushSubscription', error.code ?? null);
}

export async function removePushSubscription(id: string): Promise<void> {
	const { error } = await supabase.from('push_subscriptions').delete().eq('id', id);
	if (error) throw new DataError('removePushSubscription', error.code ?? null);
}

/**
 * Inserts exactly the eight organizer columns. organizer_id comes from the column default
 * auth.uid(), slug from the trigger (WP-19). PT400 'rate_limited' -> DataError code 'rate_limited'.
 */
export async function insertSession(values: NewSession): Promise<{ slug: string }> {
	const payload = {
		spot_id: values.spot_id,
		organizer_name: values.organizer_name,
		starts_at: values.starts_at,
		ends_at: values.ends_at,
		note: values.note,
		seats_free: values.seats_free,
		departure_point: values.departure_point,
		tikkie_url: values.tikkie_url
	};
	const { data, error } = await supabase.from('sessions').insert(payload).select('slug').single();
	if (error) {
		if (error.code === 'PT400' && error.message === 'rate_limited') {
			throw new DataError('insertSession', 'rate_limited');
		}
		throw new DataError('insertSession', error.code ?? null);
	}
	const slug = (data as { slug?: unknown } | null)?.slug;
	if (typeof slug !== 'string') throw new DataError('insertSession', 'no_slug');
	return { slug };
}

/** Own sessions with ends_at > now, by starts_at then id (RLS limits to the organizer as well). */
export function listOwnSessions(userId: string, now: Date): Promise<SessionRow[]> {
	return fetchAllPages<SessionRow>('listOwnSessions', () =>
		supabase
			.from('sessions')
			.select(SESSION_COLUMNS.join(','))
			.eq('organizer_id', userId)
			.gt('ends_at', now.toISOString())
			.order('starts_at', { ascending: true })
			.order('id', { ascending: true })
	);
}

/** Own session by slug (RLS), or null. */
export async function getOwnSession(slug: string): Promise<SessionRow | null> {
	const { data, error } = await supabase
		.from('sessions')
		.select(SESSION_COLUMNS.join(','))
		.eq('slug', slug)
		.maybeSingle();
	if (error) throw new DataError('getOwnSession', error.code ?? null);
	return (data as unknown as SessionRow | null) ?? null;
}

/** Updates exactly the given keys; 0 rows -> DataError('updateOwnSession', 'not_found'). */
export async function updateOwnSession(id: string, payload: SessionUpdate): Promise<void> {
	const { data, error } = await supabase
		.from('sessions')
		.update(payload)
		.eq('id', id)
		.select('id');
	if (error) throw new DataError('updateOwnSession', error.code ?? null);
	if (((data as unknown[] | null) ?? []).length === 0) {
		throw new DataError('updateOwnSession', 'not_found');
	}
}
