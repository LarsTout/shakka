// @vitest-environment node
import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';

const SRC = new URL('../src/', import.meta.url).pathname;
const walk = (dir: string): string[] =>
	readdirSync(dir).flatMap((n) => {
		const p = join(dir, n);
		return statSync(p).isDirectory() ? walk(p) : [p];
	});

describe('AC-8', () => {
	it('no file under src/ mentions the removed channel', () => {
		for (const p of walk(SRC)) {
			expect(readFileSync(p, 'utf8'), p).not.toMatch(/telegram/i);
		}
	});
});
