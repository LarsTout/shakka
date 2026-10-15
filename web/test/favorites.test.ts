import { get } from 'svelte/store';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { createFakeSupabase, Response } from './helpers/fake-supabase.js';
import { writeCalls } from './helpers/fake-supabase.js';
import { SESSION, USER_ID, sessionStore } from './helpers/fake-session.js';

const fake = vi.hoisted(() => ({ current: null as unknown as ReturnType<typeof createFakeSupabase> }));
vi.mock('#lib/supabase.js', async () => {
	const { createFakeSupabase } = await import('./helpers/fake-supabase.js');
	fake.current = createFakeSupabase();
	return { supabase: fake.current.client, initialUrlHash: '' };
});
vi.mock('#lib/auth.js', async () => (await import('./helpers/fake-session.js')).authModule);

import { favorites, toggleFavorite, type FavoritesState } from '../src/lib/favorites.js';

const OTHER = { user: { id: '00000000-0000-4000-8000-000000000002', email: 'b@example.org' } };
const flush = () => new Promise((r) => setTimeout(r, 0));
const ids = (s: FavoritesState) => (s.status === 'ready' ? [...s.ids].sort() : null);

let unsubscribe: (() => void) | null = null;
function watch(): FavoritesState[] {
	const seen: FavoritesState[] = [];
	unsubscribe = favorites.subscribe((s) => seen.push(s));
	return seen;
}
function deferred() {
	let resolve!: (r: Response) => void;
	const promise = new Promise<Response>((r) => (resolve = r));
	return { promise, resolve };
}

beforeEach(() => {
	vi.clearAllMocks();
	unsubscribe?.();
	unsubscribe = null;
	fake.current.reset();
	sessionStore.set(undefined);
});

describe('favorites store', () => {
	it('unknown session and signed out: no queries', () => {
		const seen = watch();
		expect(seen.at(-1)).toEqual({ status: 'unknown' });
		sessionStore.set(null);
		expect(seen.at(-1)).toEqual({ status: 'signed_out' });
		expect(fake.current.calls).toHaveLength(0);
	});

	it('loads on sign-in: loading, then ready', async () => {
		fake.current.respond('favorites', { data: [{ spot_id: 'test-meer' }], error: null });
		sessionStore.set(SESSION);
		const seen = watch();
		expect(seen[0]).toEqual({ status: 'loading', userId: USER_ID });
		await flush();
		expect(ids(seen.at(-1)!)).toEqual(['test-meer']);
	});

	it('a new session object with the same id does not reload; another id does', async () => {
		fake.current.respond('favorites', { data: [], error: null });
		sessionStore.set(SESSION);
		const seen = watch();
		await flush();
		expect(fake.current.calls).toHaveLength(1);
		sessionStore.set({ ...SESSION });
		await flush();
		expect(fake.current.calls).toHaveLength(1);
		sessionStore.set(OTHER);
		await flush();
		expect(fake.current.calls).toHaveLength(2);
		expect(seen.at(-1)).toMatchObject({ status: 'ready', userId: OTHER.user.id });
	});

	it('unsubscribing and subscribing again queries again (A2)', async () => {
		sessionStore.set(SESSION);
		watch();
		await flush();
		unsubscribe!();
		watch();
		await flush();
		expect(fake.current.calls).toHaveLength(2);
	});

	it('a load error gives the error state', async () => {
		fake.current.respond('favorites', { data: null, error: { code: '42501' } });
		sessionStore.set(SESSION);
		const seen = watch();
		await flush();
		expect(seen.at(-1)).toEqual({ status: 'error', userId: USER_ID });
	});

	it('a slow load for A does not overwrite B', async () => {
		const slow = deferred();
		fake.current.respond('favorites', slow.promise as unknown as Response);
		fake.current.respond('favorites', { data: [{ spot_id: 'b-spot' }], error: null });
		sessionStore.set(SESSION);
		const seen = watch();
		sessionStore.set(OTHER);
		await flush();
		slow.resolve({ data: [{ spot_id: 'a-spot' }], error: null });
		await flush();
		expect(seen.at(-1)).toMatchObject({ status: 'ready', userId: OTHER.user.id });
		expect(ids(seen.at(-1)!)).toEqual(['b-spot']);
	});
});

describe('toggleFavorite', () => {
	async function ready(spots: string[]) {
		fake.current.respond('favorites', { data: spots.map((spot_id) => ({ spot_id })), error: null });
		sessionStore.set(SESSION);
		watch();
		await flush();
	}

	it('flips optimistically and inserts', async () => {
		await ready(['test-meer']);
		const p = toggleFavorite('test-strand');
		expect(ids(get(favorites))).toEqual(['test-meer', 'test-strand']);
		expect(await p).toBe(true);
		expect(writeCalls(fake.current.calls)).toEqual([
			{ table: 'favorites', ops: [['insert', { user_id: USER_ID, spot_id: 'test-strand' }]] }
		]);
	});

	it('removes a favorite with a delete', async () => {
		await ready(['test-meer']);
		expect(await toggleFavorite('test-meer')).toBe(true);
		expect(ids(get(favorites))).toEqual([]);
		expect(writeCalls(fake.current.calls)[0]!.ops[0]).toEqual(['delete']);
	});

	it('reverts and returns false on an error', async () => {
		const warn = vi.spyOn(console, 'warn').mockImplementation(() => {});
		await ready(['test-meer']);
		fake.current.respond('favorites', { data: null, error: { code: '42501', message: 'secret detail' } });
		expect(await toggleFavorite('test-strand')).toBe(false);
		expect(ids(get(favorites))).toEqual(['test-meer']);
		expect(JSON.stringify(warn.mock.calls)).not.toContain('secret detail');
	});

	it('does nothing when signed out', async () => {
		sessionStore.set(null);
		watch();
		expect(await toggleFavorite('test-strand')).toBe(false);
		expect(fake.current.calls).toHaveLength(0);
	});
});
