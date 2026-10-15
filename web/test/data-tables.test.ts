// @vitest-environment node
import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';

const src = readFileSync(new URL('../src/lib/data.ts', import.meta.url), 'utf8');

describe('data.ts only reads allowed tables (AC-6)', () => {
	it('every .from( names an allowed table', () => {
		const all = src.match(/\.from\(/g) ?? [];
		const allowed = src.match(/\.from\('(spots|evaluations|tide_extremes)'\)/g) ?? [];
		expect(all.length).toBeGreaterThan(0);
		expect(allowed.length).toBe(all.length);
	});
	it('reads each table at least once', () => {
		for (const t of ['spots', 'evaluations', 'tide_extremes']) {
			expect(src).toContain(`.from('${t}')`);
		}
	});
});
