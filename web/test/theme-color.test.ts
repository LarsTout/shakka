// @vitest-environment node
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';
import { readTokens } from './helpers/tokens.js';

const ROOT = process.cwd();
const tokens = readTokens(readFileSync(join(ROOT, 'src/app.css'), 'utf8'));
const html = readFileSync(join(ROOT, 'src/app.html'), 'utf8');
const manifest = JSON.parse(readFileSync(join(ROOT, 'static/manifest.webmanifest'), 'utf8'));

const metas = (name: string) =>
	[...html.matchAll(/<meta\s+name="([^"]+)"([^>]*)>/g)]
		.filter((m) => m[1] === name)
		.map((m) => ({
			content: /content="([^"]*)"/.exec(m[2])?.[1],
			media: /media="([^"]*)"/.exec(m[2])?.[1]
		}));

describe('theme colour (AC-4)', () => {
	it('two theme-color tags, light first, equal to header-bg per mode', () => {
		const tags = metas('theme-color');
		expect(tags).toHaveLength(2);
		expect(tags[0]).toEqual({ content: tokens.light['--color-header-bg'], media: '(prefers-color-scheme: light)' });
		expect(tags[1]).toEqual({ content: tokens.dark['--color-header-bg'], media: '(prefers-color-scheme: dark)' });
	});
	it('color-scheme meta', () => {
		expect(metas('color-scheme')).toEqual([{ content: 'light dark', media: undefined }]);
	});
	it('manifest uses the light values', () => {
		expect(manifest.theme_color).toBe(tokens.light['--color-header-bg']);
		expect(manifest.background_color).toBe(tokens.light['--color-bg']);
	});
});
