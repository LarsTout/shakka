// @vitest-environment node
import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';

const ROOT = new URL('../src/', import.meta.url).pathname;
const BAD =
	/\.(getHours|getMinutes|getDate|getDay|getMonth|getFullYear|toLocaleString|toLocaleDateString|toLocaleTimeString)\(/;

function files(dir: string): string[] {
	return readdirSync(dir).flatMap((n) => {
		const p = join(dir, n);
		return statSync(p).isDirectory() ? files(p) : /\.(ts|svelte)$/.test(n) ? [p] : [];
	});
}

describe('no local-time Date getters (A12)', () => {
	it('src/ uses Intl with an explicit time zone only', () => {
		for (const f of files(ROOT)) expect(BAD.test(readFileSync(f, 'utf8')), f).toBe(false);
	});
});
