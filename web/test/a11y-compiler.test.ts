// @vitest-environment node
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join } from 'node:path';
import { vitePreprocess } from '@sveltejs/vite-plugin-svelte';
import { compile, preprocess } from 'svelte/compiler';
import { describe, expect, it } from 'vitest';

const SRC = join(process.cwd(), 'src');

function svelteFiles(dir: string): string[] {
	return readdirSync(dir).flatMap((name) => {
		const p = join(dir, name);
		return statSync(p).isDirectory() ? svelteFiles(p) : p.endsWith('.svelte') ? [p] : [];
	});
}

describe('svelte compiler a11y warnings', () => {
	const files = svelteFiles(SRC);
	it('finds the components', () => expect(files.length).toBeGreaterThan(20));
	it.each(files.map((f) => [f.slice(SRC.length + 1), f]))('%s has no a11y_ warnings', async (_rel, file) => {
		const source = readFileSync(file, 'utf8');
		const pre = await preprocess(source, vitePreprocess(), { filename: file });
		const { warnings } = compile(pre.code, { filename: file, generate: 'client', runes: true });
		const a11y = warnings.filter((w) => w.code.startsWith('a11y_')).map((w) => `${w.code}: ${w.message}`);
		expect(a11y, file).toEqual([]);
	});
});
