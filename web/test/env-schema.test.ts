// @vitest-environment node
import { describe, expect, it } from 'vitest';
import {
	base64UrlToBytes,
	parseMaptilerKey,
	parsePublishableKey,
	parseSupabaseUrl,
	parseVapidPublicKey
} from '../src/lib/env-schema.js';

const TEST_KEY = 'B' + 'A'.repeat(86);
const OTHER_KEY = 'B' + 'A'.repeat(42) + 'Q' + 'A'.repeat(43);

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

describe('base64UrlToBytes', () => {
	it('decodes plain input', () => {
		expect([...base64UrlToBytes('AQID')]).toEqual([1, 2, 3]);
	});
	it.each(['_-8', '-_', TEST_KEY, OTHER_KEY])('matches Buffer for %s', (x) => {
		expect([...base64UrlToBytes(x)]).toEqual([...Buffer.from(x, 'base64url')]);
	});
	it('decodes 65 bytes starting with 4', () => {
		const b = base64UrlToBytes(OTHER_KEY);
		expect(b).toHaveLength(65);
		expect(b[0]).toBe(4);
	});
	it('accepts padding', () => {
		expect([...base64UrlToBytes('AQ==')]).toEqual([...base64UrlToBytes('AQ')]);
	});
	it.each(['a', 'a b'])('throws for %j', (x) => {
		expect(() => base64UrlToBytes(x)).toThrow('invalid base64url');
	});
});

describe('parseVapidPublicKey', () => {
	it.each([undefined, '', '  '])('returns empty for %j', (v) => {
		expect(parseVapidPublicKey(v)).toBe('');
	});
	it.each([TEST_KEY, OTHER_KEY])('accepts a public key', (k) => {
		expect(parseVapidPublicKey(k)).toBe(k);
		expect(parseVapidPublicKey(`  ${k}  `)).toBe(k);
		expect(parseVapidPublicKey(`${k}=`)).toBe(k);
	});
	function msg(v: string): string {
		try {
			parseVapidPublicKey(v);
		} catch (e) {
			return (e as Error).message;
		}
		return '';
	}
	it('refuses a private-looking key', () => {
		expect(msg('A'.repeat(43))).toContain('private key');
		expect(msg('B' + 'A'.repeat(42))).toContain('private key');
	});
	it('refuses non base64url', () => {
		expect(msg('abc!')).toContain('base64url');
		expect(msg('sb_publishable_test')).not.toBe('');
	});
	it('refuses a 65 byte key that is not uncompressed', () => {
		const bytes = Buffer.alloc(65);
		bytes[0] = 2;
		expect(msg(bytes.toString('base64url'))).toContain('uncompressed P-256');
	});
	it('never echoes the input', () => {
		for (const v of ['abc!', 'A'.repeat(43), 'sb_publishable_test', 'Zm9vYmFy']) {
			expect(msg(v)).not.toContain(v);
		}
	});
});
