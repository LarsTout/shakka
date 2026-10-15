// @vitest-environment node
import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';

const SRC = new URL('../src/', import.meta.url);
const FILES = [
	'routes/s/[slug]/+page.svelte',
	'routes/s/[slug]/+page.ts',
	'lib/rsvp.ts',
	'lib/rsvp-storage.ts',
	'lib/session-view.ts',
	'lib/rsvp-types.ts',
	'lib/public-session-data.ts',
	'lib/components/RsvpPanel.svelte',
	'lib/components/RsvpForm.svelte',
	'lib/components/SessionParticipants.svelte'
];
const text = (f: string) => readFileSync(new URL(f, SRC), 'utf8');

describe('anonymous session code (AC-2, A1)', () => {
	it('never touches auth, @html or console.log', () => {
		for (const f of FILES) {
			const t = text(f);
			expect(t, f).not.toMatch(/#lib\/auth\.js|\.\/auth\.js|\.auth\b|getSession|getUser|\$session/);
			expect(t, f).not.toMatch(/\{@html/);
			expect(t, f).not.toMatch(/console\.(log|info|debug)\(/);
		}
	});
	it('rsvp.ts: POST only, no tables, one rpc call', () => {
		const t = text('lib/rsvp.ts');
		expect(t).not.toMatch(/get:\s*true|head:\s*true/);
		expect(t).not.toMatch(/\.from\(/);
		expect(t.match(/supabase\.rpc\(/g)).toHaveLength(1);
	});
	it('page has the noindex meta inside svelte:head', () => {
		const t = text('routes/s/[slug]/+page.svelte');
		const head = /<svelte:head>([\s\S]*?)<\/svelte:head>/.exec(t);
		expect(head?.[1]).toContain('<meta name="robots" content="noindex" />');
	});
});
