// @vitest-environment node
import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';
import {
	checkManifest,
	findExternalScripts,
	findTrackerRefs,
	pngSize
} from '../scripts/verify-build.mjs';

const manifest = () => JSON.parse(readFileSync(new URL('../static/manifest.webmanifest', import.meta.url), 'utf8'));

describe('checkManifest', () => {
	it('accepts the real manifest', () => {
		expect(checkManifest(manifest())).toEqual([]);
	});
	it('flags a missing 512 icon', () => {
		const m = manifest();
		m.icons = m.icons.filter((i: { sizes: string; purpose: string }) => !(i.sizes === '512x512' && i.purpose === 'any'));
		expect(checkManifest(m).length).toBeGreaterThan(0);
	});
	it('flags a wrong display mode', () => {
		expect(checkManifest({ ...manifest(), display: 'browser' }).length).toBeGreaterThan(0);
	});
	it('flags a missing name', () => {
		const { name: _name, ...rest } = manifest();
		expect(checkManifest(rest).length).toBeGreaterThan(0);
	});
});

describe('findExternalScripts', () => {
	it('ignores local scripts', () => {
		expect(findExternalScripts('<script type="module" src="/_app/x.js"></script>')).toEqual([]);
	});
	it('finds absolute and protocol-relative scripts', () => {
		expect(findExternalScripts('<script src="https://x.test/a.js"></script>')).toHaveLength(1);
		expect(findExternalScripts('<script src="//x.test/a.js"></script>')).toHaveLength(1);
	});
});

describe('findTrackerRefs', () => {
	it('finds a tracker marker', () => {
		expect(findTrackerRefs('x ' + ['google', 'tagmanager'].join('') + ' y').length).toBe(1);
	});
	it('ignores the Open-Meteo attribution link', () => {
		expect(findTrackerRefs('https://open-meteo.com/')).toEqual([]);
	});
});

describe('pngSize', () => {
	it('reads the size of a generated icon', () => {
		const buf = readFileSync(new URL('../static/icons/icon-192.png', import.meta.url));
		expect(pngSize(buf)).toEqual({ width: 192, height: 192 });
	});
	it('rejects non-PNG input', () => {
		expect(() => pngSize(new Uint8Array(30))).toThrow();
	});
});
