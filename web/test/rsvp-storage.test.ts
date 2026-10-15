import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import {
	clearStoredRsvp,
	readStoredRsvp,
	resetRsvpMemory,
	writeStoredRsvp
} from '../src/lib/rsvp-storage.js';
import type { StorageLike } from '../src/lib/browser-storage.js';
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

	it('undefined storage does not throw', () => {
		expect(readStoredRsvp(undefined, SLUG)).toBeNull();
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
});

describe('memory fallback (E26)', () => {
	it('(a) undefined storage keeps the value in memory', () => {
		expect(writeStoredRsvp(undefined, SLUG, V)).toBe(false);
		expect(readStoredRsvp(undefined, SLUG)).toEqual(V);
		expect(readStoredRsvp(localStorage, SLUG)).toEqual(V);
		clearStoredRsvp(undefined, SLUG);
		expect(readStoredRsvp(undefined, SLUG)).toBeNull();
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
		writeStoredRsvp(undefined, SLUG, V);
		expect(writeStoredRsvp(localStorage, SLUG, V)).toBe(true);
		localStorage.removeItem(KEY);
		expect(readStoredRsvp(localStorage, SLUG)).toBeNull();
	});
	it('(d) resetRsvpMemory wipes it', () => {
		writeStoredRsvp(undefined, SLUG, V);
		resetRsvpMemory();
		expect(readStoredRsvp(undefined, SLUG)).toBeNull();
	});
	it('(e) is per slug', () => {
		writeStoredRsvp(undefined, SLUG, V);
		expect(readStoredRsvp(undefined, 'andere-slug-1234')).toBeNull();
	});
});
