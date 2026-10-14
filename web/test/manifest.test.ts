// @vitest-environment node
import { existsSync, readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';
import { checkManifest, pngSize } from '../scripts/verify-build.mjs';

const root = new URL('../', import.meta.url);
const manifest = JSON.parse(readFileSync(new URL('static/manifest.webmanifest', root), 'utf8'));

describe('static PWA files', () => {
	it('has a valid manifest', () => {
		expect(checkManifest(manifest)).toEqual([]);
	});
	it('has every icon at the declared size', () => {
		for (const icon of manifest.icons) {
			const file = new URL('static' + icon.src, root);
			expect(existsSync(file)).toBe(true);
			const [w, h] = icon.sizes.split('x').map(Number);
			expect(pngSize(readFileSync(file))).toEqual({ width: w, height: h });
		}
	});
	it('has a 180x180 apple touch icon', () => {
		const buf = readFileSync(new URL('static/icons/apple-touch-icon.png', root));
		expect(pngSize(buf)).toEqual({ width: 180, height: 180 });
	});
	it('links manifest and apple touch icon from app.html', () => {
		const html = readFileSync(new URL('src/app.html', root), 'utf8');
		expect(html).toContain('href="/manifest.webmanifest"');
		expect(html).toContain('href="/icons/apple-touch-icon.png"');
	});
});
