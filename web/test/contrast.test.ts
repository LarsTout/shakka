// @vitest-environment node
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';
import { contrastRatio, hexToRgb } from './helpers/contrast.js';
import { readTokens, stripTokenBlocks } from './helpers/tokens.js';

const SRC = join(process.cwd(), 'src');
const CSS = readFileSync(join(SRC, 'app.css'), 'utf8');
const TOKENS = readTokens(CSS);
const TEXT = 4.5;
const NON_TEXT = 3;

const BG_TEXT = ['bg', 'surface', 'surface-muted', 'warning-bg', 'notice-bg'];
// [foreground, background, minimum, where], all token names without the --color- prefix.
const PAIRS: [string, string, number, string][] = [
	...BG_TEXT.map((bg): [string, string, number, string] => ['text', bg, TEXT, 'body text']),
	...BG_TEXT.map((bg): [string, string, number, string] => ['muted', bg, TEXT, 'muted text, hints, footer']),
	...['bg', 'surface', 'header-bg', 'notice-bg', 'warning-bg'].map(
		(bg): [string, string, number, string] => ['accent', bg, TEXT, 'links']
	),
	['on-accent', 'accent', TEXT, 'primary button'],
	['header-text', 'header-bg', TEXT, 'brand'],
	['on-verdict', 'error', TEXT, 'danger button'],
	...['bg', 'surface', 'warning-bg'].map((bg): [string, string, number, string] => ['error', bg, TEXT, 'error text']),
	...['bg', 'surface', 'header-bg'].map((bg): [string, string, number, string] => ['focus', bg, NON_TEXT, 'focus ring']),
	...['bg', 'surface'].map((bg): [string, string, number, string] => ['border-strong', bg, NON_TEXT, 'field and button borders']),
	...['go', 'marginal', 'no-go'].flatMap((fg) =>
		['bg', 'surface'].map((bg): [string, string, number, string] => [fg, bg, NON_TEXT, 'bar segment and dot'])
	)
];

// Colours that carry no information of their own.
const DECORATIVE: Record<string, string> = {
	'--color-border': 'scheidingslijnen, balk buiten/vrij',
	'--color-brand': 'alias van accent',
	'--color-none': 'arcering geen data; tekst draagt de betekenis'
};

function files(dir: string): string[] {
	return readdirSync(dir).flatMap((name) => {
		const p = join(dir, name);
		return statSync(p).isDirectory() ? files(p) : /\.(svelte|css)$/.test(p) ? [p] : [];
	});
}

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

const colourNames = (set: Record<string, string>) =>
	Object.keys(set).filter((k) => k.startsWith('--color-') || k === '--shadow-card').sort();

describe('design tokens', () => {
	it('colour token sets are equal', () => {
		expect(colourNames(TOKENS.dark)).toEqual(colourNames(TOKENS.light));
		expect(TOKENS.light['--shadow-card']).toBeDefined();
	});

	describe.each(['light', 'dark'] as const)('pairs (%s mode)', (mode) => {
		it.each(PAIRS)('%s on %s needs %d (%s)', (fg, bg, min) => {
			const set = TOKENS[mode];
			const f = set[`--color-${fg}`];
			const b = set[`--color-${bg}`];
			expect(f, `--color-${fg}`).toMatch(/^#[0-9a-f]{6}$/);
			expect(b, `--color-${bg}`).toMatch(/^#[0-9a-f]{6}$/);
			expect(contrastRatio(f, b)).toBeGreaterThanOrEqual(min);
		});
	});

	it('every colour token is in PAIRS or DECORATIVE', () => {
		const used = new Set(PAIRS.flatMap(([a, b]) => [`--color-${a}`, `--color-${b}`]));
		const missing = colourNames(TOKENS.light).filter(
			(k) => k.startsWith('--color-') && !used.has(k) && !(k in DECORATIVE)
		);
		expect(missing).toEqual([]);
	});

	it('no colour values outside the token blocks', () => {
		const found: string[] = [];
		const re = /#(?:[0-9a-f]{3}|[0-9a-f]{6}|[0-9a-f]{8})\b|rgba?\(|hsla?\(/gi;
		const check = (name: string, text: string) => {
			for (const m of text.matchAll(re)) found.push(`${name}: ${m[0]}`);
		};
		for (const f of files(SRC)) {
			if (f.endsWith('app.css')) check(f, stripTokenBlocks(CSS));
			else check(f, readFileSync(f, 'utf8'));
		}
		expect(found).toEqual([]);
	});

	it('every var() used in src is defined', () => {
		const defined = new Set(Object.keys(TOKENS.light));
		const missing = new Set<string>();
		for (const f of files(SRC)) {
			for (const m of readFileSync(f, 'utf8').matchAll(/var\(\s*(--[\w-]+)/g)) {
				if (!defined.has(m[1])) missing.add(`${f}: ${m[1]}`);
			}
		}
		expect([...missing]).toEqual([]);
	});
});
