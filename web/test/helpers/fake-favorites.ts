import { writable } from 'svelte/store';
import { vi } from 'vitest';
import type { FavoritesState } from '../../src/lib/favorites.js';

export const favoritesState = writable<FavoritesState>({ status: 'signed_out' });
export const toggleFavoriteMock = vi.fn(async () => true);

/** Stand-in for #lib/favorites.js in page tests. */
export const favoritesModule = { favorites: favoritesState, toggleFavorite: toggleFavoriteMock };
