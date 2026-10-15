import { get, readable, writable, type Readable } from 'svelte/store';
import { session } from '#lib/auth.js';
import { addFavorite, listFavoriteSpotIds, removeFavorite } from '#lib/user-data.js';

export type FavoritesState =
	| { status: 'unknown' } // session not known yet
	| { status: 'signed_out' }
	| { status: 'loading'; userId: string }
	| { status: 'ready'; userId: string; ids: ReadonlySet<string> }
	| { status: 'error'; userId: string };

const state = writable<FavoritesState>({ status: 'unknown' });

/** Loads on the first subscriber (every page with stars) and when the user id changes. */
export const favorites: Readable<FavoritesState> = readable<FavoritesState>(
	{ status: 'unknown' },
	(set) => {
		let loadedFor: string | null = null;
		state.set({ status: 'unknown' });
		const stopState = state.subscribe(set);
		const stopSession = session.subscribe((s) => {
			if (s === undefined) {
				loadedFor = null;
				state.set({ status: 'unknown' });
			} else if (s === null) {
				loadedFor = null;
				state.set({ status: 'signed_out' });
			} else if (s.user.id !== loadedFor) {
				const id = s.user.id;
				loadedFor = id;
				state.set({ status: 'loading', userId: id });
				listFavoriteSpotIds(id).then(
					(ids) => {
						if (loadedFor === id) state.set({ status: 'ready', userId: id, ids: new Set(ids) });
					},
					() => {
						if (loadedFor === id) state.set({ status: 'error', userId: id });
					}
				);
			}
		});
		return () => {
			stopSession();
			stopState();
			loadedFor = null;
		};
	}
);

/**
 * Signed in and ready: flips spotId optimistically, calls addFavorite/removeFavorite, reverts on
 * error. Returns true on success, false on error or when the state is not 'ready'.
 */
export async function toggleFavorite(spotId: string): Promise<boolean> {
	const before = get(state);
	if (before.status !== 'ready') return false;
	const { userId } = before;
	const adding = !before.ids.has(spotId);
	const next = new Set(before.ids);
	if (adding) next.add(spotId);
	else next.delete(spotId);
	state.set({ status: 'ready', userId, ids: next });
	try {
		if (adding) await addFavorite(userId, spotId);
		else await removeFavorite(userId, spotId);
		return true;
	} catch {
		console.warn('favorite update failed');
		const now = get(state);
		if (now.status === 'ready' && now.userId === userId) {
			const reverted = new Set(now.ids);
			if (adding) reverted.delete(spotId);
			else reverted.add(spotId);
			state.set({ status: 'ready', userId, ids: reverted });
		}
		return false;
	}
}
