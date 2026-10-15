// @vitest-environment node
import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join, relative } from 'node:path';
import { describe, expect, it } from 'vitest';

const SRC = new URL('../src/', import.meta.url).pathname;

function walk(dir: string): string[] {
	return readdirSync(dir).flatMap((n) => {
		const p = join(dir, n);
		return statSync(p).isDirectory() ? walk(p) : [p];
	});
}
const files = walk(SRC).filter((p) => /\.(ts|svelte)$/.test(p));
const text = new Map(files.map((p) => [relative(SRC, p), readFileSync(p, 'utf8')]));

describe('only data.ts and user-data.ts talk to tables', () => {
	it(".from(' occurs in exactly lib/data.ts and lib/user-data.ts", () => {
		const hits = [...text].filter(([, t]) => /\.from\('/.test(t)).map(([f]) => f);
		expect(hits.sort()).toEqual(['lib/data.ts', 'lib/user-data.ts']);
	});
	it('user-data.ts names only the five user tables, each at least once', () => {
		const t = text.get('lib/user-data.ts')!;
		const names = [...t.matchAll(/\.from\('([^']*)'\)/g)].map((m) => m[1]);
		const allowed = ['profiles', 'favorites', 'alert_rules', 'push_subscriptions', 'sessions'];
		for (const n of names) expect(allowed).toContain(n);
		for (const n of allowed) expect(names).toContain(n);
		expect(t).not.toMatch(/\.from\((?!')/);
	});
	it('data.ts never writes', () => {
		expect(text.get('lib/data.ts')!).not.toMatch(/\.(insert|update|upsert|delete)\(/);
	});
	it('user-data.ts writes only where allowed', () => {
		const t = text.get('lib/user-data.ts')!;
		expect(t.match(/\.update\(/g)).toHaveLength(2);
		expect(t).toMatch(/\.from\('profiles'\)\s*\.update\(/);
		expect(t).toMatch(/\.from\('sessions'\)\s*\.update\(/);
		for (const m of t.matchAll(/\.insert\(/g)) {
			expect(t.slice(Math.max(0, m.index! - 40), m.index! + m[0].length)).toMatch(
				/\.from\('(favorites|push_subscriptions|sessions)'\)\s*\.insert\($/
			);
		}
		for (const m of t.matchAll(/\.upsert\(/g)) {
			expect(t.slice(Math.max(0, m.index! - 40), m.index! + m[0].length)).toMatch(/\.from\('alert_rules'\)\s*\.upsert\($/);
		}
	});
	it('no file uses .rpc(', () => {
		for (const [f, t] of text) expect(t, f).not.toMatch(/\.rpc\(/);
	});
});
