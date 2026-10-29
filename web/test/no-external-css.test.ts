// @vitest-environment node
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';

const ROOT = process.cwd();

function files(dir: string, ext: RegExp): string[] {
	return readdirSync(dir).flatMap((name) => {
		const p = join(dir, name);
		return statSync(p).isDirectory() ? files(p, ext) : ext.test(p) ? [p] : [];
	});
}

describe('no external CSS sources (AC-5)', () => {
	it('no external CSS sources', () => {
		const re = /@import|@font-face|fonts\.googleapis|fonts\.gstatic|cdn\.|url\(\s*['"]?https?:/;
		const list = [
			...files(join(ROOT, 'src'), /\.(css|svelte|html)$/),
			...files(join(ROOT, 'static'), /\.css$/)
		];
		expect(list.length).toBeGreaterThan(5);
		expect(list.filter((f) => re.test(readFileSync(f, 'utf8')))).toEqual([]);
	});
});
