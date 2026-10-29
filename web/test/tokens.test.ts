// @vitest-environment node
import { describe, expect, it } from 'vitest';
import { readTokens, stripTokenBlocks } from './helpers/tokens.js';

const FIXTURE = `
/* comment with :root { --color-x: #123456; } */
:root {
	color-scheme: light dark;
	--color-bg: #FFF;
	--color-text: #1D2125;
	--color-accent: #0369A1;
	--color-brand: var(--color-accent);
	--color-focus: var(--color-text);
	--space-1: 0.25rem;
}
@media (prefers-color-scheme: dark) {
	:root {
		--color-bg: #15181b;
		--color-accent: #4fb3e8;
		--color-brand: var(--color-accent);
		--color-focus: var(--color-text);
	}
}
body { color: var(--color-text); }
`;

describe('readTokens', () => {
	it('reads light and dark blocks', () => {
		const t = readTokens(FIXTURE);
		expect(t.light['--color-bg']).toBe('#ffffff');
		expect(t.light['--color-text']).toBe('#1d2125');
		expect(t.dark['--color-bg']).toBe('#15181b');
		expect(t.light['--color-x']).toBeUndefined();
		expect(t.light['--space-1']).toBe('0.25rem');
		expect(t.dark['--space-1']).toBeUndefined();
	});
	it('resolves var() in mode, then light', () => {
		const t = readTokens(FIXTURE);
		expect(t.light['--color-brand']).toBe('#0369a1');
		expect(t.dark['--color-brand']).toBe('#4fb3e8');
		expect(t.dark['--color-focus']).toBe('#1d2125');
	});
	it('throws without dark block / with two light blocks', () => {
		expect(() => readTokens(':root { --a: #fff; }')).toThrow();
		expect(() => readTokens(`${FIXTURE}\n:root { --b: #000; }`)).toThrow();
	});
});

describe('stripTokenBlocks', () => {
	it('removes both blocks and keeps the rest', () => {
		const rest = stripTokenBlocks(FIXTURE);
		expect(rest).toContain('body { color: var(--color-text); }');
		expect(rest).not.toContain('--color-bg');
		expect(rest).not.toContain('prefers-color-scheme');
	});
});
