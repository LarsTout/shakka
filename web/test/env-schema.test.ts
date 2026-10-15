// @vitest-environment node
import { describe, expect, it } from 'vitest';
import { parseMaptilerKey, parsePublishableKey, parseSupabaseUrl } from '../src/lib/env-schema.js';

describe('parseSupabaseUrl', () => {
	it('normalises to the origin', () => {
		expect(parseSupabaseUrl('https://abc.supabase.co')).toBe('https://abc.supabase.co');
		expect(parseSupabaseUrl('https://abc.supabase.co/')).toBe('https://abc.supabase.co');
	});

	it('allows http for localhost and 127.0.0.1', () => {
		expect(parseSupabaseUrl('http://127.0.0.1:54321')).toBe('http://127.0.0.1:54321');
		expect(parseSupabaseUrl('http://localhost:54321')).toBe('http://localhost:54321');
	});

	it.each([
		undefined,
		'',
		'  ',
		'http://abc.supabase.co',
		'https://abc.supabase.co/rest/v1',
		'https://abc.supabase.co/?x=1',
		'not a url'
	])('rejects %j without echoing the value', (value) => {
		let message = '';
		try {
			parseSupabaseUrl(value);
		} catch (e) {
			message = (e as Error).message;
		}
		expect(message).toMatch(/^PUBLIC_SUPABASE_URL/);
		if (value && value.trim()) expect(message).not.toContain(value);
	});
});

describe('parsePublishableKey', () => {
	it('accepts and trims a publishable key', () => {
		expect(parsePublishableKey(' sb_publishable_test ')).toBe('sb_publishable_test');
	});

	it.each([undefined, '', '  ', 'sb_secret_xyz', 'abc', 'sb_publishable_a b'])(
		'rejects %j without echoing the value',
		(value) => {
			let message = '';
			try {
				parsePublishableKey(value);
			} catch (e) {
				message = (e as Error).message;
			}
			expect(message).toMatch(/^PUBLIC_SUPABASE_PUBLISHABLE_KEY/);
			if (value && value.trim()) expect(message).not.toContain(value.trim());
		}
	);

	it('names the secret key explicitly', () => {
		expect(() => parsePublishableKey('sb_secret_xyz')).toThrow('never the secret key');
	});
});

describe('parseMaptilerKey', () => {
	it.each([undefined, '', '  '])('treats %j as not configured', (value) => {
		expect(parseMaptilerKey(value)).toBe('');
	});

	it('returns the trimmed key', () => {
		expect(parseMaptilerKey(' abcDEF123456 ')).toBe('abcDEF123456');
		expect(parseMaptilerKey('get_your_own_Key-1')).toBe('get_your_own_Key-1');
	});

	it.each(['short1', 'abc def 12345', 'abc/def12345', 'x'.repeat(129)])('rejects %j without echoing it', (value) => {
		let message = '';
		try {
			parseMaptilerKey(value);
		} catch (error) {
			message = (error as Error).message;
		}
		expect(message.startsWith('PUBLIC_MAPTILER_KEY')).toBe(true);
		expect(message).not.toContain(value);
	});
});
