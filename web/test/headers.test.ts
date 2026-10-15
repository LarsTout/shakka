// @vitest-environment node
import { createHash } from 'node:crypto';
import { mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { spawnSync } from 'node:child_process';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { afterEach, describe, expect, it } from 'vitest';
import { MAP_EXTERNAL_ORIGINS } from '../src/lib/map/config.js';
import {
	ANALYTICS_MARKERS,
	checkHeaders,
	inlineScriptHashes,
	parseCsp,
	parseHeaders,
	renderHeaders,
	supabaseOrigin
} from '../scripts/write-headers.mjs';

const webRoot = process.cwd();
const TEMPLATE = readFileSync(join(webRoot, 'static/_headers'), 'utf8');
const hash = (s: string) => `'sha256-${createHash('sha256').update(s).digest('base64')}'`;
const rules = parseHeaders(TEMPLATE);
const header = (pattern: string, name: string) =>
	rules.find((r) => r.pattern === pattern)?.headers.find(([n]) => n.toLowerCase() === name.toLowerCase())?.[1];
const csp = () => parseCsp(header('/*', 'Content-Security-Policy')!);

const dirs: string[] = [];
afterEach(() => {
	for (const d of dirs.splice(0)) rmSync(d, { recursive: true, force: true });
});
const tmp = () => {
	const d = mkdtempSync(join(tmpdir(), 'shakka-headers-'));
	dirs.push(d);
	return d;
};

describe('static/_headers template', () => {
	it('passes checkHeaders as a template', () => {
		expect(checkHeaders(TEMPLATE, { template: true })).toEqual([]);
	});
	it('connect-src is limited to self, Supabase and MapTiler', () => {
		const connect = csp().get('connect-src')!;
		expect(connect).toEqual(expect.arrayContaining(["'self'", '{{SUPABASE_ORIGIN}}', 'https://api.maptiler.com']));
		for (const [, sources] of csp()) {
			for (const s of sources) {
				expect(s).not.toContain('*');
				expect(s.toLowerCase()).not.toContain('open-meteo');
				for (const marker of ANALYTICS_MARKERS) expect(s.toLowerCase()).not.toContain(marker);
			}
		}
	});
	it('script-src is exactly self plus the hash placeholder', () => {
		expect(csp().get('script-src')).toEqual(["'self'", '{{SCRIPT_HASHES}}']);
	});
	it('every map origin is in connect-src and img-src', () => {
		for (const origin of MAP_EXTERNAL_ORIGINS) {
			expect(csp().get('connect-src')).toContain(origin);
			expect(csp().get('img-src')).toContain(origin);
		}
	});
	it('sets the other headers', () => {
		expect(header('/s/*', 'X-Robots-Tag')).toBe('noindex');
		expect(header('/*', 'Referrer-Policy')).toBe('strict-origin-when-cross-origin');
		expect(header('/_app/immutable/*', 'Cache-Control')).toContain('immutable');
	});
	it('keeps the placeholders out of comments and every line under 2000 characters', () => {
		const comments = TEMPLATE.split('\n').filter((l) => l.startsWith('#'));
		expect(comments.join('\n')).not.toContain('{{');
		expect(Math.max(...TEMPLATE.split('\n').map((l) => l.length))).toBeLessThan(2000);
	});
});

describe('parseHeaders and parseCsp', () => {
	it('parses rules, skipping comments and blank lines', () => {
		const text = ['# comment', '', '/a/*', '  X-One: 1', '  Y: a: b', '', '/b', '  # inner', '  Z: 3'].join('\n');
		expect(parseHeaders(text)).toEqual([
			{ pattern: '/a/*', headers: [['X-One', '1'], ['Y', 'a: b']] },
			{ pattern: '/b', headers: [['Z', '3']] }
		]);
	});
	it('parses a CSP with double spaces and a trailing semicolon', () => {
		const m = parseCsp("Default-Src  'self' ;  script-src   'self'   https://x.test ; ");
		expect(m.get('default-src')).toEqual(["'self'"]);
		expect(m.get('script-src')).toEqual(["'self'", 'https://x.test']);
		expect(m.size).toBe(2);
	});
});

describe('inlineScriptHashes', () => {
	it('hashes inline scripts only', () => {
		expect(inlineScriptHashes('<script>a()</script><script src="/x.js"></script><script type="module">b</script>')).toEqual([
			hash('a()'),
			hash('b')
		]);
	});
});

describe('renderHeaders', () => {
	const h1 = hash('a()');
	it('fills both placeholders and passes checkHeaders as a final file', () => {
		const out = renderHeaders(TEMPLATE, { supabaseOrigin: 'https://abc.supabase.co', scriptHashes: [h1] });
		expect(out).not.toContain('{{');
		expect(checkHeaders(out, { template: false })).toEqual([]);
		const c = parseCsp(parseHeaders(out).find((r) => r.pattern === '/*')!.headers.find(([n]) => n === 'Content-Security-Policy')![1]);
		expect(c.get('connect-src')).toContain('https://abc.supabase.co');
		expect(c.get('script-src')).toEqual(["'self'", h1]);
	});
	it('without hashes script-src is only self, without double spaces', () => {
		const out = renderHeaders(TEMPLATE, { supabaseOrigin: 'https://abc.supabase.co', scriptHashes: [] });
		const line = out.split('\n').find((l) => l.includes('Content-Security-Policy'))!;
		expect(line).toContain("script-src 'self';");
		expect(line.trim()).not.toMatch(/ {2,}/);
		expect(checkHeaders(out, { template: false })).toEqual([]);
	});
	it('throws when a placeholder remains, even in a comment', () => {
		expect(() => renderHeaders('# {{OTHER}}\n/*\n  A: b', { supabaseOrigin: 'https://a.test', scriptHashes: [] })).toThrow(
			'unresolved placeholder in _headers'
		);
	});
});

describe('checkHeaders negative cases', () => {
	const out = renderHeaders(TEMPLATE, { supabaseOrigin: 'https://abc.supabase.co', scriptHashes: [hash('a')] });
	const bad = (from: string | RegExp, to: string) => out.replace(from, to);
	it.each([
		['connect-src *', bad('connect-src', 'connect-src * ')],
		['open-meteo in connect-src', bad('connect-src', 'connect-src https://api.open-meteo.com')],
		['an analytics origin', bad('connect-src', 'connect-src https://www.google-analytics.com')],
		['unsafe-inline scripts', bad("script-src 'self'", "script-src 'self' 'unsafe-inline'")],
		['a missing /s/* rule', bad(/\/s\/\*\n {2}X-Robots-Tag: noindex\n?/, '')],
		['a line over 2000 characters', out + '\n# ' + 'x'.repeat(2001)],
		['a leftover placeholder', bad('Referrer-Policy', '{{X}}-Referrer-Policy')],
		['no Supabase origin in connect-src', bad('https://abc.supabase.co', '')]
	])('flags %s', (_name, text) => {
		expect(checkHeaders(text, { template: false }).length).toBeGreaterThan(0);
	});
	it('template mode requires the placeholder in connect-src', () => {
		expect(checkHeaders(TEMPLATE.replace('connect-src \'self\' {{SUPABASE_ORIGIN}}', "connect-src 'self'"), { template: true }).length).toBeGreaterThan(0);
	});
});

describe('supabaseOrigin', () => {
	it('accepts an https project URL and local http', () => {
		expect(supabaseOrigin('https://abc.supabase.co/')).toBe('https://abc.supabase.co');
		expect(supabaseOrigin('http://127.0.0.1:54321')).toBe('http://127.0.0.1:54321');
	});
	it.each(['http://evil.test', '', 'https://abc.supabase.co/rest'])('rejects %j without echoing it', (v) => {
		let message = '';
		try {
			supabaseOrigin(v);
		} catch (e) {
			message = (e as Error).message;
		}
		expect(message).not.toBe('');
		if (v) expect(message).not.toContain(v);
	});
});

describe('write-headers CLI', () => {
	const run = (env: Record<string, string>, build: string) =>
		spawnSync(process.execPath, ['scripts/write-headers.mjs', '--template', 'static/_headers', '--build', build], {
			cwd: webRoot,
			env: { ...process.env, ...env },
			encoding: 'utf8'
		});
	it('writes build/_headers with the origin and the script hash', () => {
		const dir = tmp();
		writeFileSync(join(dir, 'index.html'), '<html><script>boot()</script></html>');
		const r = run({ PUBLIC_SUPABASE_URL: 'https://abc.supabase.co' }, dir);
		expect(r.status).toBe(0);
		const text = readFileSync(join(dir, '_headers'), 'utf8');
		expect(text).toContain('https://abc.supabase.co');
		expect(text).toContain(hash('boot()'));
	});
	it('fails on an invalid URL without echoing it', () => {
		const dir = tmp();
		writeFileSync(join(dir, 'index.html'), '<html></html>');
		const r = run({ PUBLIC_SUPABASE_URL: 'ftp://x' }, dir);
		expect(r.status).toBe(1);
		expect(r.stderr).not.toContain('ftp://x');
	});
	it('fails when index.html is missing', () => {
		const dir = tmp();
		mkdirSync(dir, { recursive: true });
		const r = run({ PUBLIC_SUPABASE_URL: 'https://abc.supabase.co' }, dir);
		expect(r.status).toBe(1);
		expect(r.stderr).toContain('index.html is missing');
	});
});
