// @vitest-environment node
import { existsSync, readdirSync, readFileSync, statSync } from 'node:fs';
import { extname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';
import { findTrackerRefs } from '../scripts/verify-build.mjs';

const root = fileURLToPath(new URL('../', import.meta.url));
const EXT = new Set(['.ts', '.js', '.svelte', '.html', '.css', '.json', '.webmanifest', '.svg', '.txt']);

function files(dir: string): string[] {
	if (!existsSync(dir)) return [];
	return readdirSync(dir).flatMap((n) => {
		const p = join(dir, n);
		return statSync(p).isDirectory() ? files(p) : [p];
	});
}

describe('no third-party trackers or CDNs', () => {
	it('src and static are clean', () => {
		const all = [...files(join(root, 'src')), ...files(join(root, 'static'))].filter((f) => EXT.has(extname(f)));
		expect(all.length).toBeGreaterThan(0);
		for (const file of all) expect([file, findTrackerRefs(readFileSync(file, 'utf8'))]).toEqual([file, []]);
	});
});
