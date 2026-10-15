import { listSpots } from '#lib/data.js';
import { getProfile, listAlertRules, listFavoriteSpotIds } from '#lib/user-data.js';
import type { AlertRuleRow, Profile, Spot } from './types.js';

export type ProfilePageData =
	| { kind: 'ok'; profile: Profile }
	| { kind: 'missing' }
	| { kind: 'error' };
export interface FavoriteRuleEntry {
	spot: Spot;
	rule: AlertRuleRow | null;
}
export type AlertsPageData =
	| { kind: 'ok'; profile: Profile | null; entries: FavoriteRuleEntry[] }
	| { kind: 'error' };

/** getProfile; null -> missing; throw -> console.warn('profile load failed') and error. */
export async function loadProfilePage(userId: string): Promise<ProfilePageData> {
	try {
		const profile = await getProfile(userId);
		return profile === null ? { kind: 'missing' } : { kind: 'ok', profile };
	} catch {
		console.warn('profile load failed');
		return { kind: 'error' };
	}
}

/**
 * Favorites with their rule row (or null), in listSpots order. Favorite ids without a spot are
 * skipped. Throw -> console.warn('alerts load failed') and error.
 */
export async function loadAlertsPage(userId: string): Promise<AlertsPageData> {
	try {
		const [profile, favoriteIds, rules, spots] = await Promise.all([
			getProfile(userId),
			listFavoriteSpotIds(userId),
			listAlertRules(userId),
			listSpots()
		]);
		const favorites = new Set(favoriteIds);
		const bySpot = new Map(rules.map((r) => [r.spot_id, r]));
		const entries = spots
			.filter((s) => favorites.has(s.id))
			.map((spot) => ({ spot, rule: bySpot.get(spot.id) ?? null }));
		return { kind: 'ok', profile, entries };
	} catch {
		console.warn('alerts load failed');
		return { kind: 'error' };
	}
}
