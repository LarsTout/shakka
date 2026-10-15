// @vitest-environment node
import { readdirSync, readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';
import {
	EVALUATION_COLUMNS,
	SPOT_COLUMNS,
	SUMMARY_COLUMNS,
	TIDE_EXTREME_COLUMNS
} from '../src/lib/types.js';

const MIGRATIONS = new URL('../../supabase/migrations/', import.meta.url);
const m1 = readFileSync(new URL('20261015090000_m1_schema.sql', MIGRATIONS), 'utf8');

function columns(table: string): string[] {
	const lines = m1.split('\n');
	const start = lines.findIndex((l) => l.startsWith(`create table public.${table} (`));
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

describe('schema columns (A1)', () => {
	it('SPOT_COLUMNS equals public.spots', () => {
		expect([...SPOT_COLUMNS]).toEqual(columns('spots'));
	});
	it('EVALUATION_COLUMNS equals public.evaluations', () => {
		expect([...EVALUATION_COLUMNS]).toEqual(columns('evaluations'));
	});
	it('TIDE_EXTREME_COLUMNS is a subset of tide_extremes', () => {
		const cols = columns('tide_extremes');
		for (const c of TIDE_EXTREME_COLUMNS) expect(cols).toContain(c);
	});
	it('SUMMARY_COLUMNS is a subset of evaluations', () => {
		const cols = columns('evaluations');
		for (const c of SUMMARY_COLUMNS) expect(cols).toContain(c);
	});

	it('no later migration alters the read tables (update types.ts and this test)', () => {
		const re =
			/alter\s+table\s+(only\s+)?public\.(spots|evaluations|tide_extremes)\b[^;]*\b(add|drop|rename)\s+column\b/i;
		for (const f of readdirSync(MIGRATIONS).filter((n) => n.endsWith('.sql'))) {
			const sql = readFileSync(new URL(f, MIGRATIONS), 'utf8');
			expect(re.test(sql), `${f}: update types.ts and this test`).toBe(false);
		}
	});
});
