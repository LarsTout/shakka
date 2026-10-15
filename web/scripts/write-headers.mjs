// Writes build/_headers from static/_headers (WP-23): fills in the Supabase origin and the sha256 hashes
// of the inline scripts in build/index.html. The pure functions are shared with tests and verify-build.
import { existsSync, readFileSync, writeFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

export const PLACEHOLDER_SUPABASE = '{{SUPABASE_ORIGIN}}';
export const PLACEHOLDER_SCRIPTS = '{{SCRIPT_HASHES}}';
export const MAX_LINE = 2000;
export const ANALYTICS_MARKERS = [
	'google-analytics',
	'googletagmanager',
	'doubleclick',
	'plausible',
	'matomo',
	'posthog',
	'segment',
	'mixpanel',
	'hotjar',
	'cloudflareinsights',
	'clarity.ms',
	'facebook'
];

const MAPTILER = 'https://api.maptiler.com';
const SHA256_SOURCE = /^'sha256-[A-Za-z0-9+/]+={0,2}'$/;

/** Rules in file order. Blank lines and lines starting with '#' are skipped. A line without leading
 *  whitespace starts a rule (pattern = trimmed line). An indented line is 'Name: value' (split at the first ': ').
 *  @param {string} text @returns {{ pattern: string, headers: [string, string][] }[]} */
export function parseHeaders(text) {
	/** @type {{ pattern: string, headers: [string, string][] }[]} */
	const rules = [];
	for (const line of text.split(/\r?\n/)) {
		if (line.trim() === '' || line.trim().startsWith('#')) continue;
		if (!/^\s/.test(line)) {
			rules.push({ pattern: line.trim(), headers: [] });
			continue;
		}
		const rule = rules[rules.length - 1];
		if (!rule) continue;
		const body = line.trim();
		const at = body.indexOf(': ');
		if (at === -1) continue;
		rule.headers.push([body.slice(0, at), body.slice(at + 2).trim()]);
	}
	return rules;
}

/** 'a b; c d e' -> Map { 'a' => ['b'], 'c' => ['d','e'] }. Directive names lower-cased; empty parts skipped.
 *  @param {string} value @returns {Map<string, string[]>} */
export function parseCsp(value) {
	/** @type {Map<string, string[]>} */
	const map = new Map();
	for (const part of value.split(';')) {
		const tokens = part.trim().split(/\s+/).filter(Boolean);
		if (tokens.length === 0) continue;
		map.set(tokens[0].toLowerCase(), tokens.slice(1));
	}
	return map;
}

/** "'sha256-<base64>'" for every <script> without a src attribute, hash over the exact text between the tags (UTF-8).
 *  @param {string} html @returns {string[]} */
export function inlineScriptHashes(html) {
	const re = /<script\b(?![^>]*\bsrc\s*=)[^>]*>([\s\S]*?)<\/script>/gi;
	return [...html.matchAll(re)].map(
		(m) => `'sha256-${createHash('sha256').update(m[1] ?? '', 'utf8').digest('base64')}'`
	);
}

/** Same rules as parseSupabaseUrl in src/lib/env-schema.ts; returns url.origin. Messages never contain the value.
 *  @param {string | undefined} value @returns {string} */
export function supabaseOrigin(value) {
	const raw = value?.trim() ?? '';
	if (!raw) throw new Error('PUBLIC_SUPABASE_URL is missing: copy web/.env.example to web/.env (see docs/RUNBOOK.md)');
	let url;
	try {
		url = new URL(raw);
	} catch {
		throw new Error('PUBLIC_SUPABASE_URL is not a valid URL');
	}
	const localHttp = url.protocol === 'http:' && (url.hostname === 'localhost' || url.hostname === '127.0.0.1');
	if (url.protocol !== 'https:' && !localHttp) {
		throw new Error('PUBLIC_SUPABASE_URL must use https (http only for localhost)');
	}
	if (url.pathname !== '/' || url.search || url.hash || url.username || url.password) {
		throw new Error('PUBLIC_SUPABASE_URL must be the project URL without path');
	}
	return url.origin;
}

/** Replaces every occurrence of both placeholders, collapses runs of spaces (and a space before ';') inside header values, and throws
 *  Error('unresolved placeholder in _headers') if '{{' remains anywhere in the text (comments included).
 *  @param {string} template @param {{ supabaseOrigin: string, scriptHashes: string[] }} values @returns {string} */
export function renderHeaders(template, values) {
	const filled = template
		.replaceAll(PLACEHOLDER_SUPABASE, values.supabaseOrigin)
		.replaceAll(PLACEHOLDER_SCRIPTS, values.scriptHashes.join(' '));
	const text = filled
		.split('\n')
		.map((line) => {
			const indent = /^\s*/.exec(line)?.[0] ?? '';
			return line.startsWith('#') || indent === '' ? line : indent + line.slice(indent.length).replace(/ {2,}/g, ' ').replace(/ ;/g, ';').trimEnd();
		})
		.join('\n');
	if (text.includes('{{')) throw new Error('unresolved placeholder in _headers');
	return text;
}

/** Problems (empty = ok). template: placeholders are expected (true) or forbidden (false).
 *  @param {string} text @param {{ template: boolean }} opts @returns {string[]} */
export function checkHeaders(text, opts) {
	/** @type {string[]} */
	const problems = [];
	const lines = text.split(/\r?\n/);
	lines.forEach((line, i) => {
		if (line.length > MAX_LINE) problems.push(`line ${i + 1} is longer than ${MAX_LINE} characters`);
	});
	const rules = parseHeaders(text);
	const named = (/** @type {{ headers: [string, string][] }} */ rule, /** @type {string} */ name) =>
		rule.headers.filter(([n]) => n.toLowerCase() === name.toLowerCase());

	const all = rules.flatMap((r) => named(r, 'Content-Security-Policy'));
	const root = rules.find((r) => r.pattern === '/*');
	const rootCsp = root ? named(root, 'Content-Security-Policy') : [];
	if (!root) problems.push('no /* rule');
	else if (rootCsp.length === 0) problems.push('/* has no Content-Security-Policy');
	if (all.length > 1) problems.push('more than one Content-Security-Policy line');

	if (rootCsp[0]) {
		const csp = parseCsp(rootCsp[0][1]);
		for (const d of ['default-src', 'object-src', 'base-uri', 'frame-ancestors']) {
			if (!csp.has(d)) problems.push(`CSP lacks ${d}`);
		}
		const connect = csp.get('connect-src');
		if (!connect) {
			problems.push('CSP lacks connect-src');
		} else {
			if (!connect.includes("'self'")) problems.push("connect-src lacks 'self'");
			if (!connect.includes(MAPTILER)) problems.push(`connect-src lacks ${MAPTILER}`);
			if (opts.template) {
				if (!connect.includes(PLACEHOLDER_SUPABASE)) problems.push(`connect-src lacks ${PLACEHOLDER_SUPABASE}`);
			} else if (!connect.some((s) => /^https?:\/\//.test(s) && s !== MAPTILER)) {
				problems.push('connect-src lacks the Supabase origin');
			}
		}
		for (const [directive, sources] of csp) {
			for (const s of sources) {
				const lower = s.toLowerCase();
				if (s.includes('*')) problems.push(`${directive} has a wildcard source: ${s}`);
				if (lower.includes('open-meteo')) problems.push(`${directive} allows open-meteo (server-side only)`);
				const marker = ANALYTICS_MARKERS.find((m) => lower.includes(m));
				if (marker) problems.push(`${directive} allows an analytics origin (${marker})`);
			}
		}
		for (const s of csp.get('script-src') ?? []) {
			const ok = s === "'self'" || SHA256_SOURCE.test(s) || (opts.template && s === PLACEHOLDER_SCRIPTS);
			if (!ok) problems.push(`script-src has an unexpected source: ${s}`);
		}
		if (!(csp.get('img-src') ?? []).includes(MAPTILER)) problems.push(`img-src lacks ${MAPTILER}`);
	}

	if (!root || !named(root, 'Referrer-Policy').some(([, v]) => v === 'strict-origin-when-cross-origin')) {
		problems.push('/* lacks Referrer-Policy: strict-origin-when-cross-origin');
	}
	const robots = rules.find((r) => r.pattern === '/s/*');
	if (!robots || !named(robots, 'X-Robots-Tag').some(([, v]) => v === 'noindex')) {
		problems.push('no /s/* rule with X-Robots-Tag: noindex');
	}
	if (!opts.template && text.includes('{{')) problems.push('unresolved placeholder in _headers');
	return problems;
}

/** @param {string} name @param {string} fallback @returns {string} */
function arg(name, fallback) {
	const i = process.argv.indexOf(name);
	return i !== -1 && process.argv[i + 1] ? resolve(process.cwd(), process.argv[i + 1]) : fallback;
}

async function main() {
	const webRoot = join(dirname(fileURLToPath(import.meta.url)), '..');
	const template = arg('--template', join(webRoot, 'static', '_headers'));
	const build = arg('--build', join(webRoot, 'build'));
	try {
		const { loadEnv } = await import('vite');
		const env = loadEnv('production', webRoot, 'PUBLIC_');
		const origin = supabaseOrigin(process.env.PUBLIC_SUPABASE_URL ?? env.PUBLIC_SUPABASE_URL);
		const indexPath = join(build, 'index.html');
		if (!existsSync(indexPath)) {
			console.error('write-headers: build/index.html is missing');
			process.exit(1);
		}
		const hashes = inlineScriptHashes(readFileSync(indexPath, 'utf8'));
		const text = renderHeaders(readFileSync(template, 'utf8'), { supabaseOrigin: origin, scriptHashes: hashes });
		const problems = checkHeaders(text, { template: false });
		if (problems.length) {
			for (const p of problems) console.error(`write-headers: ${p}`);
			process.exit(1);
		}
		writeFileSync(join(build, '_headers'), text);
		console.log(`write-headers: ok (${hashes.length} inline script hash(es))`);
	} catch (e) {
		console.error(`write-headers: ${e instanceof Error ? e.message : 'failed'}`);
		process.exit(1);
	}
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) await main();
