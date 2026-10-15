import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import {
	browserStorage,
	clearStoredRsvp,
	readStoredRsvp,
	resetRsvpMemory,
	writeStoredRsvp,
	type StorageLike
} from '../src/lib/rsvp-storage.js';
import { NEW_ID, SLUG, TOKEN } from './fixtures/public-session.js';

const KEY = 'shakka:rsvp:' + SLUG;
const V = { rsvp_id: NEW_ID, edit_token: TOKEN };

function mapStorage(): StorageLike {
	const m = new Map<string, string>();
	return {
		getItem: (k) => m.get(k) ?? null,
		setItem: (k, v) => void m.set(k, v),
		removeItem: (k) => void m.delete(k)
	};
}

beforeEach(() => {
	vi.clearAllMocks();
	localStorage.clear();
	resetRsvpMemory();
});
afterEach(() => {
	vi.restoreAllMocks();
	vi.useRealTimers();
});

describe('storage (AC-3)', () => {
	for (const [name, make] of [
		['map storage', mapStorage],
		['jsdom localStorage', () => localStorage as StorageLike]
	] as const) {
		it(`writes exactly {rsvp_id, edit_token}, reads and clears (${name})`, () => {
			const s = make();
			expect(readStoredRsvp(s, SLUG)).toBeNull();
			const withExtra = { ...V, extra: 'x' } as typeof V;
			expect(writeStoredRsvp(s, SLUG, withExtra)).toBe(true);
			expect(s.getItem(KEY)).toBe(JSON.stringify(V));
			expect(readStoredRsvp(s, SLUG)).toEqual(V);
			clearStoredRsvp(s, SLUG);
			expect(s.getItem(KEY)).toBeNull();
			expect(readStoredRsvp(s, SLUG)).toBeNull();
		});
		it(`removes malformed values (${name})`, () => {
			const s = make();
			for (const bad of ['{kapot', '{"rsvp_id":"x"}']) {
				s.setItem(KEY, bad);
				expect(readStoredRsvp(s, SLUG)).toBeNull();
				expect(s.getItem(KEY)).toBeNull();
			}
		});
	}

	it('null storage does not throw', () => {
		expect(readStoredRsvp(null, SLUG)).toBeNull();
	});
	it('throwing getItem and removeItem are survived', () => {
		const bad: StorageLike = {
			getItem: () => {
				throw new Error('x');
			},
			setItem: () => {},
			removeItem: () => {
				throw new Error('x');
			}
		};
		expect(readStoredRsvp(bad, SLUG)).toBeNull();
		expect(() => clearStoredRsvp(bad, SLUG)).not.toThrow();
	});
	it('invalid slug never touches storage', () => {
		const s = { getItem: vi.fn(), setItem: vi.fn(), removeItem: vi.fn() };
		expect(readStoredRsvp(s, 'kort')).toBeNull();
		expect(writeStoredRsvp(s, 'kort', V)).toBe(false);
		clearStoredRsvp(s, 'kort');
		expect(s.getItem).not.toHaveBeenCalled();
		expect(s.setItem).not.toHaveBeenCalled();
		expect(s.removeItem).not.toHaveBeenCalled();
	});
	it('browserStorage returns localStorage, or null when access throws', () => {
		expect(browserStorage()).toBe(localStorage);
		const d = Object.getOwnPropertyDescriptor(globalThis, 'localStorage');
		try {
			Object.defineProperty(globalThis, 'localStorage', {
				configurable: true,
				get: () => {
					throw new Error('SecurityError');
				}
			});
			expect(browserStorage()).toBeNull();
		} finally {
			if (d) Object.defineProperty(globalThis, 'localStorage', d);
		}
	});
});

describe('memory fallback (E26)', () => {
	it('(a) null storage keeps the value in memory', () => {
		expect(writeStoredRsvp(null, SLUG, V)).toBe(false);
		expect(readStoredRsvp(null, SLUG)).toEqual(V);
		expect(readStoredRsvp(localStorage, SLUG)).toEqual(V);
		clearStoredRsvp(null, SLUG);
		expect(readStoredRsvp(null, SLUG)).toBeNull();
		expect(readStoredRsvp(localStorage, SLUG)).toBeNull();
	});
	it('(b) a throwing setItem falls back to memory', () => {
		const spy = vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
			throw new Error('quota');
		});
		expect(writeStoredRsvp(localStorage, SLUG, V)).toBe(false);
		spy.mockRestore();
		expect(localStorage.getItem(KEY)).toBeNull();
		expect(readStoredRsvp(localStorage, SLUG)).toEqual(V);
	});
	it('(c) a later successful write clears the memory value', () => {
		writeStoredRsvp(null, SLUG, V);
		expect(writeStoredRsvp(localStorage, SLUG, V)).toBe(true);
		localStorage.removeItem(KEY);
		expect(readStoredRsvp(localStorage, SLUG)).toBeNull();
	});
	it('(d) resetRsvpMemory wipes it', () => {
		writeStoredRsvp(null, SLUG, V);
		resetRsvpMemory();
		expect(readStoredRsvp(null, SLUG)).toBeNull();
	});
	it('(e) is per slug', () => {
		writeStoredRsvp(null, SLUG, V);
		expect(readStoredRsvp(null, 'andere-slug-1234')).toBeNull();
	});
});
