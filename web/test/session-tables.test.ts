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
const text = new Map(
	walk(SRC)
		.filter((p) => /\.(ts|svelte)$/.test(p))
		.map((p) => [relative(SRC, p), readFileSync(p, 'utf8')])
);
const lib = (n: string) => text.get(`lib/${n}`)!;

const ALL = ['sessions.ts', 'session-model.ts', 'session-form.ts', 'go.ts', 'local-prefs.ts', 'browser-storage.ts'];
const PURE = ['session-model.ts', 'session-form.ts', 'go.ts', 'local-prefs.ts', 'browser-storage.ts'];

describe('session modules stay in their layer (WP-20)', () => {
	it.each(ALL)('%s has no .from(, .rpc( or supabase import', (n) => {
		const t = lib(n);
		expect(t).not.toMatch(/\.from\(/);
		expect(t).not.toMatch(/\.rpc\(/);
		expect(t).not.toMatch(/^\s*(import|export)[^;]*supabase[^;]*;/im);
	});
	it.each(PURE)('%s imports no data layer', (n) => {
		expect(lib(n)).not.toMatch(/from '\.\/(data|user-data|sessions)\.js'/);
	});
	it.each(['session-model.ts', 'session-form.ts', 'go.ts'])('%s has no localStorage', (n) => {
		expect(lib(n)).not.toMatch(/localStorage/);
	});
	it('wa.me appears only in session-model.ts', () => {
		const hits = [...text].filter(([, t]) => t.includes('wa.me')).map(([f]) => f);
		expect(hits).toEqual(['lib/session-model.ts']);
	});
});
