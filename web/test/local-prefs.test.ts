import { beforeEach, describe, expect, it } from 'vitest';
import type { StorageLike } from '../src/lib/browser-storage.js';
import {
	ORGANIZER_NAME_KEY,
	RETURN_TO_KEY,
	RETURN_TO_TTL_MS,
	isAllowedReturnPath,
	readOrganizerName,
	saveReturnTo,
	takeReturnTo,
	writeOrganizerName
} from '../src/lib/local-prefs.js';
import { GO_URL_SUMMER } from './fixtures/spot-data.js';

const PATH = new URL(GO_URL_SUMMER).pathname + new URL(GO_URL_SUMMER).search;
const NOW = 1_800_000_000_000;

function memory(): StorageLike & { data: Map<string, string> } {
	const data = new Map<string, string>();
	return {
		data,
		getItem: (k) => data.get(k) ?? null,
		setItem: (k, v) => void data.set(k, v),
		removeItem: (k) => void data.delete(k)
	};
}
const throwing: StorageLike = {
	getItem: () => {
		throw new Error('blocked');
	},
	setItem: () => {
		throw new Error('blocked');
	},
	removeItem: () => {
		throw new Error('blocked');
	}
};

let s: ReturnType<typeof memory>;
beforeEach(() => {
	s = memory();
});

describe('return_to', () => {
	it('keys are exact', () => {
		expect(ORGANIZER_NAME_KEY).toBe('shakka:organizer_name');
		expect(RETURN_TO_KEY).toBe('shakka:return_to');
	});
	it('roundtrip and always removes', () => {
		expect(saveReturnTo(s, PATH, NOW)).toBe(true);
		expect(JSON.parse(s.data.get(RETURN_TO_KEY)!)).toEqual({ path: PATH, saved_at: NOW });
		expect(takeReturnTo(s, NOW + 1000)).toBe(PATH);
		expect(s.data.has(RETURN_TO_KEY)).toBe(false);
	});
	it('TTL boundary', () => {
		saveReturnTo(s, PATH, NOW);
		expect(takeReturnTo(s, NOW + RETURN_TO_TTL_MS)).toBe(PATH);
		saveReturnTo(s, PATH, NOW);
		expect(takeReturnTo(s, NOW + RETURN_TO_TTL_MS + 1)).toBeNull();
		expect(s.data.has(RETURN_TO_KEY)).toBe(false);
	});
	it('future saved_at gives null', () => {
		saveReturnTo(s, PATH, NOW + 5000);
		expect(takeReturnTo(s, NOW)).toBeNull();
	});
	it.each([
		'not json',
		JSON.stringify({ path: PATH, saved_at: 'x' }),
		JSON.stringify({ saved_at: NOW }),
		JSON.stringify(null),
		JSON.stringify({ path: '/login', saved_at: NOW })
	])('malformed %s gives null and is removed', (raw) => {
		s.data.set(RETURN_TO_KEY, raw);
		expect(takeReturnTo(s, NOW)).toBeNull();
		expect(s.data.has(RETURN_TO_KEY)).toBe(false);
	});
	it('refuses /login', () => {
		expect(saveReturnTo(s, '/login', NOW)).toBe(false);
		expect(s.data.size).toBe(0);
	});
	it.each([
		'/login',
		'https://evil.example/go?spot=test-strand',
		'//evil.example/go?spot=test-strand&start=2026-07-18T12%3A00%3A00Z&end=2026-07-18T16%3A00%3A00Z',
		'/go?spot=Bad&start=2026-07-18T12%3A00%3A00Z&end=2026-07-18T16%3A00%3A00Z',
		'/go'
	])('E7 not allowed: %s', (p) => expect(isAllowedReturnPath(p)).toBe(false));
	it('allows the go path', () => expect(isAllowedReturnPath(PATH)).toBe(true));
	it('storage that throws or is undefined', () => {
		expect(saveReturnTo(throwing, PATH, NOW)).toBe(false);
		expect(takeReturnTo(throwing, NOW)).toBeNull();
		expect(readOrganizerName(throwing)).toBe('');
		expect(() => writeOrganizerName(throwing, 'Lars')).not.toThrow();
		expect(saveReturnTo(undefined, PATH, NOW)).toBe(false);
		expect(takeReturnTo(undefined, NOW)).toBeNull();
		expect(readOrganizerName(undefined)).toBe('');
		expect(() => writeOrganizerName(undefined, 'Lars')).not.toThrow();
	});
});

describe('organizer name', () => {
	it('stores the trimmed name', () => {
		writeOrganizerName(s, '  Lars ');
		expect(s.data.get(ORGANIZER_NAME_KEY)).toBe('Lars');
		expect(readOrganizerName(s)).toBe('Lars');
	});
	it('ignores an invalid name', () => {
		writeOrganizerName(s, '');
		writeOrganizerName(s, 'a'.repeat(31));
		expect(s.data.size).toBe(0);
	});
	it('a stored 31-char name reads as empty', () => {
		s.data.set(ORGANIZER_NAME_KEY, 'a'.repeat(31));
		expect(readOrganizerName(s)).toBe('');
	});
});
