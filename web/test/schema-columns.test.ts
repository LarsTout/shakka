// @vitest-environment node
import { readdirSync, readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';
import {
	ALERT_RULE_COLUMNS,
	EVALUATION_COLUMNS,
	FAVORITE_COLUMNS,
	PROFILE_COLUMNS,
	PROFILE_EDITABLE_COLUMNS,
	QUIET_HOURS_COLUMNS,
	RULE_FIELDS,
	SPOT_COLUMNS,
	SUMMARY_COLUMNS,
	TIDE_EXTREME_COLUMNS
} from '../src/lib/types.js';

const MIGRATIONS = new URL('../../supabase/migrations/', import.meta.url);
const m1 = readFileSync(new URL('20261015090000_m1_schema.sql', MIGRATIONS), 'utf8');
const m1Security = readFileSync(new URL('20261015090100_m1_security.sql', MIGRATIONS), 'utf8');

// WP-22 drops the unused legacy profiles column; that migration is the one allowed exception.
const DROP_LEGACY_MIGRATION = '20261015220000_drop_profiles_telegram_chat_id.sql';

// Migrations that only add columns to public.profiles (WP-30; WP-24 appends its own). Their
// columns are appended to PROFILE_COLUMNS in this order.
const PROFILE_ADD_MIGRATIONS = ['20261028120000_quiet_hours.sql'];
const QUIET_MIGRATION = '20261028120000_quiet_hours.sql';

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
		const added = PROFILE_ADD_MIGRATIONS.flatMap((f) => {
			const sql = readFileSync(new URL(f, MIGRATIONS), 'utf8');
			return [...sql.matchAll(/alter table public\.profiles add column (\w+)/g)].map((m) => m[1]!);
		});
		expect([...PROFILE_COLUMNS]).toEqual([
			...columns('profiles').filter((c) => c !== legacy),
			...added
		]);
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
		for (const f of readdirSync(MIGRATIONS).filter(
			(n) => n.endsWith('.sql') && n !== DROP_LEGACY_MIGRATION
		)) {
			let sql = readFileSync(new URL(f, MIGRATIONS), 'utf8');
			// Profile-add migrations may only add columns to profiles; other tables stay checked.
			if (PROFILE_ADD_MIGRATIONS.includes(f)) {
				sql = sql.replace(/alter table public\.profiles add column \w+ [^;]*;/g, '');
			}
			expect(re.test(sql), `${f}: update types.ts and this test`).toBe(false);
		}
	});

	it('the WP-30 migration grants update on exactly QUIET_HOURS_COLUMNS', () => {
		const sql = readFileSync(new URL(QUIET_MIGRATION, MIGRATIONS), 'utf8');
		const m = /grant update \(([^)]*)\)\s+on table public\.profiles to authenticated/.exec(sql);
		expect(m).not.toBeNull();
		const granted = m![1]!.split(',').map((c) => c.trim());
		expect(granted).toEqual([...QUIET_HOURS_COLUMNS]);
	});

	it('the WP-22 migration drops exactly the legacy profiles column', () => {
		const sql = readFileSync(new URL(DROP_LEGACY_MIGRATION, MIGRATIONS), 'utf8');
		const legacy = ['telegram', 'chat_id'].join('_');
		expect(sql).toContain('drop column if exists ' + legacy);
	});
});
