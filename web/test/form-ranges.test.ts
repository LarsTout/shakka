// @vitest-environment node
import { readdirSync, readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';
import { ALERT_DEFAULTS } from '../src/lib/contracts.js';

const MIGRATIONS = new URL('../../supabase/migrations/', import.meta.url);
const sql = readdirSync(MIGRATIONS)
	.filter((n) => n.endsWith('.sql'))
	.sort()
	.map((f) => readFileSync(new URL(f, MIGRATIONS), 'utf8'))
	.join('\n');

/** Fragment of 1500 characters after the constraint name (same approach as WP-07). */
function fragment(name: string): string {
	const i = sql.indexOf(`constraint ${name}`);
	expect(i, `constraint ${name} not found`).toBeGreaterThanOrEqual(0);
	return sql.slice(i, i + 1500);
}
function between(name: string): [number, number] {
	const m = /between\s+(\d+)\s+and\s+(\d+)/.exec(fragment(name));
	expect(m, `${name}: no between`).not.toBeNull();
	return [Number(m![1]), Number(m![2])];
}
function list(name: string, re: RegExp): string[] {
	const m = re.exec(fragment(name));
	expect(m, `${name}: no list`).not.toBeNull();
	return m![1]!.split(',').map((x) => x.trim().replace(/'/g, ''));
}

describe('form ranges equal the database constraints', () => {
	it('profiles kn ranges', () => {
		expect(between('profiles_min_kn_range')).toEqual([ALERT_DEFAULTS.min_kn.min, ALERT_DEFAULTS.min_kn.max]);
		expect(between('profiles_max_kn_range')).toEqual([ALERT_DEFAULTS.max_kn.min, ALERT_DEFAULTS.max_kn.max]);
	});
	it('alert_rules ranges', () => {
		expect(between('alert_rules_min_kn_range')).toEqual([ALERT_DEFAULTS.min_kn.min, ALERT_DEFAULTS.min_kn.max]);
		expect(between('alert_rules_max_kn_range')).toEqual([ALERT_DEFAULTS.max_kn.min, ALERT_DEFAULTS.max_kn.max]);
		expect(between('alert_rules_min_go_hours_range')).toEqual([
			ALERT_DEFAULTS.min_go_hours.min,
			ALERT_DEFAULTS.min_go_hours.max
		]);
		expect(between('alert_rules_days_ahead_range')).toEqual([
			ALERT_DEFAULTS.days_ahead.min,
			ALERT_DEFAULTS.days_ahead.max
		]);
	});
	it('dir_classes and weekdays allowed lists', () => {
		const dirs = list('alert_rules_dir_classes_ridable', /<@\s*array\[([^\]]*)\]/);
		expect(new Set(dirs)).toEqual(new Set(ALERT_DEFAULTS.dir_classes.allowed));
		const days = list('alert_rules_weekdays_iso', /<@\s*array\[([^\]]*)\]/);
		expect(new Set(days.map(Number))).toEqual(new Set(ALERT_DEFAULTS.weekdays.allowed));
	});
});
