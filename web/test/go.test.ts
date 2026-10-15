import { isRedirect } from '@sveltejs/kit';
import { describe, expect, it } from 'vitest';
import { goTarget } from '../src/lib/go.js';
import { load } from '../src/routes/go/+page.js';
import { GO_URL_SUMMER } from './fixtures/spot-data.js';

const S = '2026-07-18T12%3A00%3A00Z';
const E = '2026-07-18T16%3A00%3A00Z';

describe('goTarget (AC-5)', () => {
	it('valid link goes to the spot', () => {
		expect(goTarget(new URL(GO_URL_SUMMER))).toBe('/spot/test-strand');
	});
	it.each([
		'https://example.org/go',
		`https://example.org/go?spot=../x&start=${S}&end=${E}`,
		`https://example.org/go?spot=Test&start=${S}&end=${E}`,
		`https://example.org/go?spot=a&start=2026-07-18T12%3A30%3A00Z&end=${E}`,
		`https://example.org/go?spot=a&start=${E}&end=${S}`
	])('invalid -> /: %s', (u) => expect(goTarget(new URL(u))).toBe('/'));
});

function redirectOf(url: string) {
	try {
		(load as (e: unknown) => unknown)({ url: new URL(url) });
	} catch (e) {
		return e;
	}
	return null;
}

describe('/go route', () => {
	it('redirects 307 to the spot', () => {
		const e = redirectOf(GO_URL_SUMMER) as { status: number; location: string };
		expect(isRedirect(e)).toBe(true);
		expect(e.location).toBe('/spot/test-strand');
		expect(e.status).toBe(307);
	});
	it('redirects to / for invalid params', () => {
		const e = redirectOf('https://example.org/go?spot=test-strand') as { location: string };
		expect(isRedirect(e)).toBe(true);
		expect(e.location).toBe('/');
	});
});
