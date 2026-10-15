// @vitest-environment node
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';
import { contrastRatio, hexToRgb } from './helpers/contrast.js';

const SRC = join(process.cwd(), 'src');
const TEXT = 4.5;
const NON_TEXT = 3;

// [foreground, background, minimum, where]
const PAIRS: [string, string, number, string][] = [
	['#1a1a1a', '#ffffff', TEXT, 'body text'],
	['#555555', '#ffffff', TEXT, 'muted text, footer, hints'],
	['#555555', '#fff4e5', TEXT, 'muted text in a banner'],
	['#1a1a1a', '#fff4e5', TEXT, 'text in a banner'],
	['#1a1a1a', '#fdecea', TEXT, 'text in a warning banner'],
	['#a4161a', '#ffffff', TEXT, 'error text'],
	['#a4161a', '#fdecea', TEXT, 'error text in a warning banner'],
	['#ffffff', '#0b5e8a', TEXT, 'header, share and my-sessions buttons'],
	['#0b5e8a', '#ffffff', NON_TEXT, 'focus outline'],
	['#ffffff', '#1b7f3b', TEXT, 'verdict go, go-run button'],
	['#1b7f3b', '#ffffff', TEXT, 'notice-ok'],
	['#ffffff', '#8a5a00', TEXT, 'verdict marginal'],
	['#8a5a00', '#ffffff', TEXT, 'unverified badge, notice'],
	['#8a5a00', '#ffffff', NON_TEXT, 'favorite star'],
	['#ffffff', '#a4161a', TEXT, 'verdict no_go, danger button'],
	['#ffffff', '#555555', TEXT, 'verdict none on the map'],
	['#1a1a1a', '#f4f4f4', TEXT, 'map loading message'],
	['#a4161a', '#ffffff', NON_TEXT, 'border of aria-invalid']
];

// Colours that carry no information of their own.
const DECORATIVE: Record<string, string> = {
	'#dddddd': 'scheidingslijnen',
	'#e0b36b': 'rand banner'
};

function files(dir: string): string[] {
	return readdirSync(dir).flatMap((name) => {
		const p = join(dir, name);
		return statSync(p).isDirectory() ? files(p) : /\.(svelte|css)$/.test(p) ? [p] : [];
	});
}

const normalize = (hex: string) => {
	const h = hex.slice(1).toLowerCase();
	return '#' + (h.length === 3 ? [...h].map((c) => c + c).join('') : h);
};

describe('contrast helpers', () => {
	it('reference values', () => {
		expect(contrastRatio('#ffffff', '#000000')).toBeCloseTo(21, 5);
		const r = contrastRatio('#777777', '#ffffff');
		expect(r).toBeGreaterThan(4.47);
		expect(r).toBeLessThan(4.49);
	});
	it('reads 3 and 6 digit hex', () => {
		expect(hexToRgb('#555')).toEqual(hexToRgb('#555555'));
	});
});

describe('colour pairs in the CSS', () => {
	it.each(PAIRS)('%s on %s needs %d (%s)', (fg, bg, min) => {
		expect(contrastRatio(fg, bg)).toBeGreaterThanOrEqual(min);
	});
});

describe('colour inventory', () => {
	it('every hex colour in src is in PAIRS or DECORATIVE', () => {
		const known = new Set([...PAIRS.flatMap(([a, b]) => [a, b]), ...Object.keys(DECORATIVE)]);
		const found = new Set<string>();
		for (const f of files(SRC)) {
			for (const m of readFileSync(f, 'utf8').matchAll(/#[0-9a-fA-F]{6}\b|#[0-9a-fA-F]{3}\b/g)) {
				found.add(normalize(m[0]));
			}
		}
		expect(found.size).toBeGreaterThan(5);
		expect([...found].filter((c) => !known.has(c))).toEqual([]);
	});
});
