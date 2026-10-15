// @vitest-environment node
import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';

describe('.env.example', () => {
	it('declares exactly the public variables, empty', () => {
		const lines = readFileSync(new URL('../.env.example', import.meta.url), 'utf8')
			.split('\n')
			.map((l) => l.trim())
			.filter((l) => l && !l.startsWith('#'));
		expect(lines).toEqual([
			'PUBLIC_SUPABASE_URL=',
			'PUBLIC_SUPABASE_PUBLISHABLE_KEY=',
			'PUBLIC_MAPTILER_KEY=',
			'PUBLIC_VAPID_PUBLIC_KEY='
		]);
	});
});
