import axe from 'axe-core';

// jsdom has no layout, so color-contrast cannot work here; contrast.test.ts covers the colours (blueprint A16).
export const AXE_OPTIONS = {
	rules: { 'color-contrast': { enabled: false } },
	resultTypes: ['violations']
} as const;

export interface AxeFinding {
	id: string;
	impact: string;
	targets: string[];
}

/** axe.run(root, AXE_OPTIONS); violations with impact 'serious' or 'critical', flattened to id/impact/targets. */
export async function seriousViolations(root: Element = document.body): Promise<AxeFinding[]> {
	const result = await axe.run(root, { ...AXE_OPTIONS, rules: { ...AXE_OPTIONS.rules } });
	return result.violations
		.filter((v) => v.impact === 'serious' || v.impact === 'critical')
		.map((v) => ({
			id: v.id,
			impact: String(v.impact),
			targets: v.nodes.map((n) => n.target.join(' '))
		}));
}

/** The diff names the rule and the selector. */
export async function expectNoSeriousViolations(root?: Element): Promise<void> {
	const { expect } = await import('vitest');
	expect(await seriousViolations(root)).toEqual([]);
}
