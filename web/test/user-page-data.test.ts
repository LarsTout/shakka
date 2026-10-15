import { beforeEach, describe, expect, it, vi } from 'vitest';
import { SPOT_UNVERIFIED, SPOT_VERIFIED } from './fixtures/spot-data.js';
import { PROFILE_FULL, ruleRow } from './fixtures/user-data.js';
import { USER_ID } from './helpers/fake-session.js';

const userData = vi.hoisted(() => ({
	getProfile: vi.fn(),
	listFavoriteSpotIds: vi.fn(),
	listAlertRules: vi.fn()
}));
const data = vi.hoisted(() => ({ listSpots: vi.fn() }));
vi.mock('#lib/user-data.js', () => userData);
vi.mock('#lib/data.js', () => data);

import { loadAlertsPage, loadProfilePage } from '../src/lib/user-page-data.js';

let warn: ReturnType<typeof vi.spyOn>;
beforeEach(() => {
	vi.clearAllMocks();
	warn = vi.spyOn(console, 'warn').mockImplementation(() => {});
});

const warned = () => JSON.stringify(warn.mock.calls);

describe('loadProfilePage', () => {
	it('ok', async () => {
		userData.getProfile.mockResolvedValue(PROFILE_FULL);
		expect(await loadProfilePage(USER_ID)).toEqual({ kind: 'ok', profile: PROFILE_FULL });
		expect(userData.getProfile).toHaveBeenCalledWith(USER_ID);
	});
	it('missing', async () => {
		userData.getProfile.mockResolvedValue(null);
		expect(await loadProfilePage(USER_ID)).toEqual({ kind: 'missing' });
	});
	it('error does not leak details', async () => {
		userData.getProfile.mockRejectedValue(new Error('secret detail'));
		expect(await loadProfilePage(USER_ID)).toEqual({ kind: 'error' });
		expect(warn).toHaveBeenCalledTimes(1);
		expect(warned()).not.toContain('secret detail');
		expect(warned()).not.toContain(USER_ID);
	});
});

describe('loadAlertsPage', () => {
	it('joins favorites, rules and spots in spot order, skipping unknown spots', async () => {
		const r = ruleRow('test-meer', { min_kn: 18 });
		userData.getProfile.mockResolvedValue(PROFILE_FULL);
		userData.listFavoriteSpotIds.mockResolvedValue(['test-strand', 'test-meer', 'weg']);
		userData.listAlertRules.mockResolvedValue([r]);
		data.listSpots.mockResolvedValue([SPOT_VERIFIED, SPOT_UNVERIFIED]);
		expect(await loadAlertsPage(USER_ID)).toEqual({
			kind: 'ok',
			profile: PROFILE_FULL,
			entries: [
				{ spot: SPOT_VERIFIED, rule: r },
				{ spot: SPOT_UNVERIFIED, rule: null }
			]
		});
		expect(userData.getProfile).toHaveBeenCalledWith(USER_ID);
		expect(userData.listFavoriteSpotIds).toHaveBeenCalledWith(USER_ID);
		expect(userData.listAlertRules).toHaveBeenCalledWith(USER_ID);
	});
	it('a missing profile is null', async () => {
		userData.getProfile.mockResolvedValue(null);
		userData.listFavoriteSpotIds.mockResolvedValue([]);
		userData.listAlertRules.mockResolvedValue([]);
		data.listSpots.mockResolvedValue([]);
		expect(await loadAlertsPage(USER_ID)).toEqual({ kind: 'ok', profile: null, entries: [] });
	});
	it('error does not leak details', async () => {
		userData.getProfile.mockResolvedValue(null);
		userData.listFavoriteSpotIds.mockRejectedValue(new Error('secret detail'));
		userData.listAlertRules.mockResolvedValue([]);
		data.listSpots.mockResolvedValue([]);
		expect(await loadAlertsPage(USER_ID)).toEqual({ kind: 'error' });
		expect(warned()).not.toContain('secret detail');
		expect(warned()).not.toContain(USER_ID);
	});
});
