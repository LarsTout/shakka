// @vitest-environment node
import { describe, expect, it } from 'vitest';
import {
	countCodePoints,
	isTikkieUrl,
	isValidSessionSlug,
	sessionPath,
	sessionUrl,
	shareText,
	whatsappUrl
} from '../src/lib/session-model.js';
import { SLUG } from './fixtures/session-data.js';

const SESSION = {
	organizer_name: 'Lars',
	starts_at: '2026-07-18T12:00:00.000Z',
	ends_at: '2026-07-18T16:00:00.000Z'
};
const URL_ = `https://example.org/s/${SLUG}`;

describe('shareText (AC-3)', () => {
	it('golden', () => {
		expect(shareText(SESSION, 'Teststrand', URL_)).toBe(
			[
				'Lars gaat kiten bij Teststrand.',
				'za 18 jul 14:00–18:00',
				'Ga je mee? Meld je aan via de link, een account is niet nodig:',
				URL_
			].join('\n')
		);
	});
});

describe('whatsappUrl (AC-3)', () => {
	it('has only the text parameter', () => {
		const u = whatsappUrl(shareText(SESSION, 'Teststrand', URL_));
		expect(u.startsWith('https://wa.me/?text=')).toBe(true);
		expect([...new URL(u).searchParams.keys()]).toEqual(['text']);
		const text = decodeURIComponent(u.slice('https://wa.me/?text='.length));
		expect(text).toContain('Teststrand');
		expect(text).toContain('za 18 jul');
		expect(text).toContain('14:00–18:00');
		expect(text).toContain(URL_);
	});
	it('round-trips awkward characters (E39)', () => {
		const t = 'a & b # c ? d + e f 😀 <script>';
		expect(decodeURIComponent(whatsappUrl(t).slice('https://wa.me/?text='.length))).toBe(t);
	});
});

describe('session URLs', () => {
	it('sessionUrl strips a trailing slash', () => {
		expect(sessionUrl('https://example.org/', SLUG)).toBe(URL_);
		expect(sessionUrl('https://example.org', SLUG)).toBe(URL_);
	});
	it('sessionPath rejects bad slugs', () => {
		expect(sessionPath(SLUG)).toBe(`/s/${SLUG}`);
		expect(() => sessionPath('abc')).toThrow(RangeError);
		expect(() => sessionPath('a/b' + 'c'.repeat(12))).toThrow(RangeError);
	});
	it('isValidSessionSlug', () => {
		expect(isValidSessionSlug(SLUG)).toBe(true);
		expect(isValidSessionSlug('abc')).toBe(false);
		expect(isValidSessionSlug('a'.repeat(65))).toBe(false);
	});
	it('countCodePoints counts code points', () => {
		expect(countCodePoints('😀')).toBe(1);
		expect(countCodePoints('ab')).toBe(2);
	});
});

describe('isTikkieUrl (A18, E26)', () => {
	it.each([
		'https://tikkie.me/pay/abc',
		'https://tikkie.me/pay/Tikkie/qzdnzr8hnVWTgXXcFRLUMc',
		'https://tikkie.me/pay/' + 'a'.repeat(178)
	])('valid: %s', (u) => expect(isTikkieUrl(u)).toBe(true));
	it.each([
		'',
		'http://tikkie.me/pay/x',
		'HTTPS://tikkie.me/pay/x',
		'https://tikkie.me/pay/a b',
		'https://tikkie.me/',
		'https://example.org/pay/x',
		'https://tikkie.me.evil.example/pay/x',
		'https://tikkie.me@evil.example/x',
		'https://www.tikkie.me/pay/x',
		'https://tikkie.me:8443/pay/x',
		'https://tikkie.me/pay/' + 'a'.repeat(179),
		'javascript:alert(1)'
	])('invalid: %s', (u) => expect(isTikkieUrl(u)).toBe(false));
});
