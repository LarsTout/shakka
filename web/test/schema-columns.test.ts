// @vitest-environment node
import { readdirSync, readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';
import {
	ALERT_RULE_COLUMNS,
	EVALUATION_COLUMNS,
	FAVORITE_COLUMNS,
	PROFILE_COLUMNS,
	PROFILE_EDITABLE_COLUMNS,
	RULE_FIELDS,
	SPOT_COLUMNS,
	SUMMARY_COLUMNS,
	TIDE_EXTREME_COLUMNS
} from '../src/lib/types.js';

const MIGRATIONS = new URL('../../supabase/migrations/', import.meta.url);
const m1 = readFileSync(new URL('20261015090000_m1_schema.sql', MIGRATIONS), 'utf8');
const m1Security = readFileSync(new URL('20261015090100_m1_security.sql', MIGRATIONS), 'utf8');

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

	it('PROFILE_COLUMNS equals public.profiles without the unused legacy column', () => {
		const legacy = ['telegram', 'chat_id'].join('_');
		expect([...PROFILE_COLUMNS]).toEqual(columns('profiles').filter((c) => c !== legacy));
	});
	it('FAVORITE_COLUMNS equals public.favorites', () => {
		expect([...FAVORITE_COLUMNS]).toEqual(columns('favorites'));
	});
	it('ALERT_RULE_COLUMNS equals public.alert_rules; RULE_FIELDS is the settable subset', () => {
		expect([...ALERT_RULE_COLUMNS]).toEqual(columns('alert_rules'));
		expect([...RULE_FIELDS]).toEqual(
			ALERT_RULE_COLUMNS.filter((c) => !['user_id', 'spot_id', 'updated_at'].includes(c))
		);
	});
	it('PROFILE_EDITABLE_COLUMNS equals the column grant for authenticated', () => {
		const m = /grant update \(([^)]*)\)\s+on table public\.profiles to authenticated/.exec(
			m1Security
		);
		expect(m).not.toBeNull();
		const granted = m![1]!.split(',').map((c) => c.trim());
		expect(new Set(PROFILE_EDITABLE_COLUMNS)).toEqual(new Set(granted));
	});

	it('no later migration alters the app tables (update types.ts and this test)', () => {
		const re =
			/alter\s+table\s+(only\s+)?public\.(spots|evaluations|tide_extremes|profiles|favorites|alert_rules)\b[^;]*\b(add|drop|rename)\s+column\b/i;
		for (const f of readdirSync(MIGRATIONS).filter((n) => n.endsWith('.sql'))) {
			const sql = readFileSync(new URL(f, MIGRATIONS), 'utf8');
			expect(re.test(sql), `${f}: update types.ts and this test`).toBe(false);
		}
	});
});
