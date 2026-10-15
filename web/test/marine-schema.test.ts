// @vitest-environment node
import { readdirSync, readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';
import { MARINE_HOUR_COLUMNS } from '../src/lib/types.js';

const MIGRATIONS = new URL('../../supabase/migrations/', import.meta.url);
const sql = readFileSync(new URL('20261015180000_marine_hours.sql', MIGRATIONS), 'utf8');

function columns(): string[] {
	const lines = sql.split('\n');
	const start = lines.findIndex((l) => l.startsWith('create table public.marine_hours ('));
	expect(start).toBeGreaterThanOrEqual(0);
	const out: string[] = [];
	for (const line of lines.slice(start + 1)) {
		if (line.startsWith(');')) break;
		const m = /^ {2}([a-z_][a-z0-9_]*) /.exec(line);
		if (m && !['constraint', 'primary', 'foreign', 'unique', 'check'].includes(m[1]!)) {
			out.push(m[1]!);
		}
	}
	return out;
}

describe('marine_hours schema', () => {
	it('MARINE_HOUR_COLUMNS equals public.marine_hours', () => {
		expect([...MARINE_HOUR_COLUMNS]).toEqual(columns());
	});
	it('no migration alters marine_hours columns (update types.ts and this test)', () => {
		const re = /alter\s+table\s+(only\s+)?public\.marine_hours\b[^;]*\b(add|drop|rename)\s+column\b/i;
		for (const f of readdirSync(MIGRATIONS).filter((n) => n.endsWith('.sql'))) {
			const text = readFileSync(new URL(f, MIGRATIONS), 'utf8');
			expect(re.test(text), `${f}: update types.ts and this test`).toBe(false);
		}
	});
});
