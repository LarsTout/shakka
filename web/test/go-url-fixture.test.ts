// @vitest-environment node
import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';
import { GO_URL_SUMMER, GO_URL_WINTER } from './fixtures/spot-data.js';

const py = readFileSync(
	new URL('../../ingest/tests/message_fixtures.py', import.meta.url),
	'utf8'
);

function literal(name: string): string {
	const m = new RegExp(`${name} = \\(([\\s\\S]*?)\\n\\)`).exec(py);
	expect(m, `${name} block`).not.toBeNull();
	return [...m![1]!.matchAll(/"([^"]*)"/g)].map((x) => x[1]).join('');
}

describe('go URL fixtures match WP-08 (AC-5)', () => {
	it('summer', () => expect(literal('URL_SUMMER')).toBe(GO_URL_SUMMER));
	it('winter', () => expect(literal('URL_WINTER')).toBe(GO_URL_WINTER));
});
