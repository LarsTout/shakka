// Reads the design tokens from app.css (WP-34): the light :root block and the :root inside
// @media (prefers-color-scheme: dark).

export type TokenSet = Record<string, string>;

const DARK_MEDIA = /@media\s*\(\s*prefers-color-scheme\s*:\s*dark\s*\)\s*\{/g;
const ROOT = /:root\s*\{/g;

const stripComments = (css: string) => css.replace(/\/\*[\s\S]*?\*\//g, '');

/** Index just after the brace that closes the block whose opening brace is at `open`. */
function closeOf(css: string, open: number): number {
	let depth = 0;
	for (let i = open; i < css.length; i++) {
		if (css[i] === '{') depth++;
		else if (css[i] === '}' && --depth === 0) return i + 1;
	}
	throw new Error('unbalanced braces in CSS');
}

/** All blocks opened by `re`, as [start of match, end of block, opening brace index]. */
function blocks(css: string, re: RegExp): [number, number, number][] {
	return [...css.matchAll(re)].map((m) => {
		const open = m.index + m[0].length - 1;
		return [m.index, closeOf(css, open), open];
	});
}

function normalizeValue(v: string): string {
	const t = v.trim();
	const m = /^#([0-9a-f]{3}|[0-9a-f]{6})$/i.exec(t);
	if (!m) return t;
	const h = m[1].toLowerCase();
	return '#' + (h.length === 3 ? [...h].map((c) => c + c).join('') : h);
}

function declarations(body: string): TokenSet {
	const out: TokenSet = {};
	for (const part of body.split(';')) {
		const i = part.indexOf(':');
		if (i < 0) continue;
		const name = part.slice(0, i).trim();
		if (name.startsWith('--')) out[name] = normalizeValue(part.slice(i + 1));
	}
	return out;
}

function split(css: string): { light: string; dark: string; rest: string } {
	const clean = stripComments(css);
	const media = blocks(clean, DARK_MEDIA);
	if (media.length !== 1) throw new Error(`expected one dark media block, found ${media.length}`);
	const [mStart, mEnd, mOpen] = media[0];
	const inner = clean.slice(mOpen + 1, mEnd - 1);
	const darkRoots = blocks(inner, ROOT);
	if (darkRoots.length !== 1) throw new Error(`expected one :root in the dark block, found ${darkRoots.length}`);
	const withoutMedia = clean.slice(0, mStart) + clean.slice(mEnd);
	const lightRoots = blocks(withoutMedia, ROOT);
	if (lightRoots.length !== 1) throw new Error(`expected one light :root block, found ${lightRoots.length}`);
	const [lStart, lEnd, lOpen] = lightRoots[0];
	return {
		light: withoutMedia.slice(lOpen + 1, lEnd - 1),
		dark: inner.slice(darkRoots[0][2] + 1, darkRoots[0][1] - 1),
		rest: withoutMedia.slice(0, lStart) + withoutMedia.slice(lEnd)
	};
}

const VAR = /^var\((--[\w-]+)\)$/;

function resolve(set: TokenSet, light: TokenSet): TokenSet {
	const out: TokenSet = {};
	for (const [k, v] of Object.entries(set)) {
		const m = VAR.exec(v);
		out[k] = m ? (set[m[1]] !== undefined && !VAR.test(set[m[1]]) ? set[m[1]] : (light[m[1]] ?? v)) : v;
	}
	return out;
}

/** Custom properties of the light `:root` block and of the `:root` inside
 *  `@media (prefers-color-scheme: dark)`. Comments are stripped, hex values are lowercased and
 *  expanded to 6 digits. A value `var(--x)` is resolved in the same mode, then in light (one level).
 *  Throws if either block is missing or occurs twice. */
export function readTokens(css: string): { light: TokenSet; dark: TokenSet } {
	const parts = split(css);
	const light = declarations(parts.light);
	const dark = declarations(parts.dark);
	return { light: resolve(light, light), dark: resolve(dark, light) };
}

/** The CSS (without comments) with both token blocks removed, for the inventory. */
export function stripTokenBlocks(css: string): string {
	return split(css).rest;
}
