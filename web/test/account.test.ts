import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { createFakeRpc } from './helpers/fake-rpc.js';

const h = vi.hoisted(() => ({ fake: null as unknown, signOut: null as unknown }));
vi.mock('#lib/supabase.js', async () => {
	const { createFakeRpc } = await import('./helpers/fake-rpc.js');
	const fake = createFakeRpc();
	h.fake = fake;
	return { supabase: { rpc: fake.rpc }, initialUrlHash: '' };
});
vi.mock('#lib/auth.js', () => {
	const signOut = vi.fn(async () => {});
	h.signOut = signOut;
	return { signOut };
});

import {
	ACCOUNT_LOCAL_KEYS,
	ACCOUNT_MESSAGES,
	ACCOUNT_RPC_TIMEOUT_MS,
	cleanUpAfterAccountDeletion,
	clearAccountLocalData,
	deleteMyAccount
} from '../src/lib/account.js';
import { ORGANIZER_NAME_KEY, RETURN_TO_KEY } from '../src/lib/local-prefs.js';

const fake = () => h.fake as ReturnType<typeof createFakeRpc>;
const signOut = () => h.signOut as ReturnType<typeof vi.fn>;

beforeEach(() => {
	vi.clearAllMocks();
	fake().reset();
	signOut().mockImplementation(async () => {});
	localStorage.clear();
});
afterEach(() => vi.restoreAllMocks());

describe('deleteMyAccount', () => {
	it('calls delete_my_account once, without arguments, with a time-out signal', async () => {
		await expect(deleteMyAccount()).resolves.toEqual({ ok: true });
		expect(fake().calls).toHaveLength(1);
		const c = fake().calls[0]!;
		expect(c.fn).toBe('delete_my_account');
		expect(c.argCount).toBe(1);
		expect(c.signal).not.toBeNull();
		expect(ACCOUNT_RPC_TIMEOUT_MS).toBe(15_000);
	});
	it('maps status 0 to the network message', async () => {
		vi.spyOn(console, 'warn').mockImplementation(() => {});
		fake().respond('delete_my_account', { data: null, error: { message: 'fetch failed' }, status: 0 });
		await expect(deleteMyAccount()).resolves.toEqual({ ok: false, error: ACCOUNT_MESSAGES.network });
	});
	it('maps any other error to the failed message', async () => {
		vi.spyOn(console, 'warn').mockImplementation(() => {});
		fake().respond('delete_my_account', {
			data: null,
			error: { code: 'PT401', message: 'not_authenticated' },
			status: 401
		});
		await expect(deleteMyAccount()).resolves.toEqual({ ok: false, error: ACCOUNT_MESSAGES.failed });
	});
	it('maps a thrown client to the network message', async () => {
		vi.spyOn(console, 'warn').mockImplementation(() => {});
		fake().throwNext('delete_my_account', new Error('boom'));
		await expect(deleteMyAccount()).resolves.toEqual({ ok: false, error: ACCOUNT_MESSAGES.network });
	});
	it('warns once without details on failure', async () => {
		const warn = vi.spyOn(console, 'warn').mockImplementation(() => {});
		fake().respond('delete_my_account', {
			data: null,
			error: { code: 'XX000', message: 'secret server text' },
			status: 500
		});
		await deleteMyAccount();
		expect(warn).toHaveBeenCalledTimes(1);
		expect(warn).toHaveBeenCalledWith('account delete failed');
	});
	it('does not warn on success', async () => {
		const warn = vi.spyOn(console, 'warn').mockImplementation(() => {});
		await deleteMyAccount();
		expect(warn).not.toHaveBeenCalled();
	});
});

describe('local data after deletion', () => {
	it('lists exactly the keys that belong to the account', () => {
		expect([...ACCOUNT_LOCAL_KEYS]).toEqual([ORGANIZER_NAME_KEY, RETURN_TO_KEY]);
	});
	it('signs out once and clears the account keys, keeping the RSVP keys', async () => {
		localStorage.setItem(ORGANIZER_NAME_KEY, 'Anna');
		localStorage.setItem(RETURN_TO_KEY, '{}');
		localStorage.setItem('shakka:rsvp:abcdefghij', '{"rsvp_id":"x"}');
		localStorage.setItem('other', '1');
		await cleanUpAfterAccountDeletion(localStorage);
		expect(signOut()).toHaveBeenCalledTimes(1);
		expect(localStorage.getItem(ORGANIZER_NAME_KEY)).toBeNull();
		expect(localStorage.getItem(RETURN_TO_KEY)).toBeNull();
		expect(localStorage.getItem('shakka:rsvp:abcdefghij')).not.toBeNull();
		expect(localStorage.getItem('other')).toBe('1');
	});
	it('still clears the keys when signOut throws', async () => {
		signOut().mockRejectedValueOnce(new Error('nope'));
		localStorage.setItem(ORGANIZER_NAME_KEY, 'Anna');
		await expect(cleanUpAfterAccountDeletion(localStorage)).resolves.toBeUndefined();
		expect(localStorage.getItem(ORGANIZER_NAME_KEY)).toBeNull();
	});
	it('never throws on undefined or failing storage', () => {
		expect(() => clearAccountLocalData(undefined)).not.toThrow();
		const bad = {
			getItem: () => null,
			setItem: () => {},
			removeItem: () => {
				throw new Error('blocked');
			}
		};
		expect(() => clearAccountLocalData(bad)).not.toThrow();
	});
});
