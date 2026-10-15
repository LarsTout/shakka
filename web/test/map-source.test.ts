// @vitest-environment node
import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join, relative } from 'node:path';
import { describe, expect, it } from 'vitest';

const SRC = new URL('../src', import.meta.url).pathname;

function walk(dir: string): string[] {
	return readdirSync(dir).flatMap((name) => {
		const path = join(dir, name);
		return statSync(path).isDirectory() ? walk(path) : [path];
	});
}
const files = walk(SRC)
	.filter((f) => /\.(ts|svelte)$/.test(f))
	.map((f) => ({ rel: relative(SRC, f), text: readFileSync(f, 'utf8') }));

const LITERAL = /(['"\x60])[^'"\x60\n]*maplibre-gl[^'"\x60\n]*\1/g;
const DYNAMIC = /\bimport\(\s*(['"\x60])[^'"\x60\n]*maplibre-gl[^'"\x60\n]*\1\s*\)/g;
const count = (re: RegExp, text: string) => text.match(re)?.length ?? 0;

describe('map sources stay lazy and contained', () => {
	it('(a) every maplibre-gl string literal sits inside a dynamic import()', () => {
		for (const f of files) expect(count(LITERAL, f.text), f.rel).toBe(count(DYNAMIC, f.text));
	});

	it('(b) no static import of maplibre-gl', () => {
		for (const f of files) {
			expect(f.text, f.rel).not.toMatch(/from\s+['"]maplibre-gl/);
			expect(f.text, f.rel).not.toMatch(/import\s+['"]maplibre-gl/);
		}
	});

	it('(c) only platform.ts mentions maplibre-gl', () => {
		expect(files.filter((f) => f.text.includes('maplibre-gl')).map((f) => f.rel)).toEqual(['lib/map/platform.ts']);
	});

	it('(d) api.maptiler.com only in config.ts', () => {
		expect(files.filter((f) => f.text.includes('api.maptiler.com')).map((f) => f.rel)).toEqual(['lib/map/config.ts']);
	});

	it('(e) the MapLibre controls are never restyled or hidden', () => {
		for (const f of files) expect(f.text, f.rel).not.toContain('maplibregl-ctrl');
	});

	it('(f) PUBLIC_MAPTILER_KEY only where expected', () => {
		expect(files.filter((f) => f.text.includes('PUBLIC_MAPTILER_KEY')).map((f) => f.rel).sort()).toEqual([
			'env.ts',
			'lib/env-schema.ts',
			'lib/map/platform.ts'
		]);
	});

	it('(g) platform.ts: one typeof import and four maplibre-gl literals, all dynamic', () => {
		const text = files.find((f) => f.rel === 'lib/map/platform.ts')!.text;
		expect(count(/\btypeof\s+import\(/g, text)).toBe(1);
		expect(count(LITERAL, text)).toBe(4);
		expect(count(DYNAMIC, text)).toBe(4);
	});
});
