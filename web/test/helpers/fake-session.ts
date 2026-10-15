import { writable } from 'svelte/store';

export const USER_ID = '00000000-0000-4000-8000-000000000001';
export const SESSION = { user: { id: USER_ID, email: 'test@example.org' } };

export const sessionStore = writable<unknown>(undefined);

/** Stand-in for #lib/auth.js. */
export const authModule = {
	session: sessionStore,
	initAuth: () => () => {},
	signOut: async () => {},
	initialAuthRedirectError: () => null
};
