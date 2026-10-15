// @vitest-environment node
import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';
import { ALERT_DEFAULTS } from '../src/lib/contracts.js';
import { FIELD_SOURCES, RuleError, effectiveRule, normalizeLocalTime } from '../src/lib/rules.js';
import { RULE_FIELDS, RULE_SOURCES, type AlertRuleRow } from '../src/lib/types.js';
import { SPOT_VERIFIED } from './fixtures/spot-data.js';
import { PROFILE_EMPTY, ruleRow } from './fixtures/user-data.js';

interface Case {
	name: string;
	spot: { default_min_kn: number | null };
	profile: { default_min_kn: number | null; default_max_kn: number | null } | null;
	override: Record<string, unknown> | null;
	expected: Record<string, unknown> & { error?: string; sources?: Record<string, string> };
}
const CASES: Case[] = JSON.parse(
	readFileSync(new URL('../../data/contracts/rule_resolution_cases.json', import.meta.url), 'utf8')
);

const run = (c: Case) =>
	effectiveRule(
		{ ...SPOT_VERIFIED, default_min_kn: c.spot.default_min_kn },
		c.profile ? { ...PROFILE_EMPTY, ...c.profile } : null,
		c.override ? ({ ...ruleRow('test-meer'), ...c.override } as AlertRuleRow) : null,
		ALERT_DEFAULTS
	);
const eff = (override: Record<string, unknown> | null, profile = null as null | object) =>
	effectiveRule(
		SPOT_VERIFIED,
		profile as never,
		override ? ({ ...ruleRow('test-meer'), ...override } as AlertRuleRow) : null,
		ALERT_DEFAULTS
	);
const errorOf = (fn: () => unknown): RuleError => {
	try {
		fn();
	} catch (e) {
		expect(e).toBeInstanceOf(RuleError);
		return e as RuleError;
	}
	throw new Error('did not throw');
};

describe('effectiveRule rule_resolution_cases', () => {
	it.each(CASES.map((c) => [c.name, c] as const))('%s', (_name, c) => {
		if (c.expected.error) {
			expect(errorOf(() => run(c)).code).toBe(c.expected.error);
		} else {
			expect(run(c)).toEqual(c.expected);
		}
	});

	it('covers the file as specified', () => {
		expect(CASES).toHaveLength(20);
		expect(new Set(CASES.map((c) => c.name)).size).toBe(20);
		for (const c of CASES) {
			expect(Object.keys(c).sort()).toEqual(['expected', 'name', 'override', 'profile', 'spot']);
			if (c.override) expect(Object.keys(c.override).sort()).toEqual([...RULE_FIELDS].sort());
		}
		const used = new Set(CASES.flatMap((c) => Object.values(c.expected.sources ?? {})));
		for (const s of RULE_SOURCES) expect(used.has(s)).toBe(true);
		const errors = CASES.map((c) => c.expected.error);
		expect(errors).toContain('conflict');
		expect(errors).toContain('invalid');
	});
});

describe('FIELD_SOURCES', () => {
	it('equals alert_defaults.json', () => {
		for (const f of RULE_FIELDS) expect([...FIELD_SOURCES[f]]).toEqual(ALERT_DEFAULTS[f].sources);
	});
});

describe('normalizeLocalTime', () => {
	it.each([
		['17:00:00', '17:00'],
		['17:00', '17:00'],
		['17:00:30', '17:00:30'],
		['17:00:00.000', '17:00'],
		['17:00:30.000', '17:00:30'],
		['17:00:30.5', '17:00:30.500000'],
		['17:00:00.5', '17:00:00.500000'],
		['17:00:00.000123', '17:00:00.000123']
	])('%s -> %s', (input, out) => expect(normalizeLocalTime(input, 'earliest_local')).toBe(out));

	it('handles null and 24:00', () => {
		expect(normalizeLocalTime(null, 'latest_local')).toBeNull();
		expect(normalizeLocalTime('24:00:00', 'latest_local')).toBeNull();
		expect(normalizeLocalTime('24:00', 'latest_local')).toBeNull();
		const e = errorOf(() => normalizeLocalTime('24:00', 'earliest_local'));
		expect(e.code).toBe('invalid');
		expect(e.field).toBe('earliest_local');
	});
	it.each(['25:00', '7:00', '17:00+02', '17:00:00.1234567'])('rejects %s', (v) => {
		expect(errorOf(() => normalizeLocalTime(v, 'latest_local')).code).toBe('invalid');
	});
});

describe('effectiveRule validation and edge cases', () => {
	it.each([
		['min_kn 4', { min_kn: 4 }],
		['min_kn 61', { min_kn: 61 }],
		['min_kn 12.5', { min_kn: 12.5 }],
		['days_ahead 8', { days_ahead: 8 }],
		['weekdays [0]', { weekdays: [0] }],
		['weekdays []', { weekdays: [] }],
		['dir_classes []', { dir_classes: [] }],
		['enabled yes', { enabled: 'yes' }],
		['min >= max', { min_kn: 20, max_kn: 20 }],
		['earliest == latest', { earliest_local: '17:00:30', latest_local: '17:00:30' }]
	])('%s is invalid', (_n, o) => {
		expect(errorOf(() => eff(o)).code).toBe('invalid');
	});

	it('a missing field is invalid', () => {
		const row = { ...ruleRow('test-meer') } as Record<string, unknown>;
		delete row.min_kn;
		expect(errorOf(() => effectiveRule(SPOT_VERIFIED, null, row as never, ALERT_DEFAULTS)).code).toBe(
			'invalid'
		);
	});

	it('earliest == latest is invalid on latest_local', () => {
		expect(errorOf(() => eff({ earliest_local: '17:00:30', latest_local: '17:00:30' })).field).toBe(
			'latest_local'
		);
	});

	it('enabled null falls back to true with source system (mirror of Python)', () => {
		const r = eff({ enabled: null });
		expect(r.enabled).toBe(true);
		expect(r.sources.enabled).toBe('system');
	});

	it('profile {20, 20} is invalid on default_max_kn', () => {
		const e = errorOf(() => eff(null, { default_min_kn: 20, default_max_kn: 20 }));
		expect(e.code).toBe('invalid');
		expect(e.field).toBe('default_max_kn');
	});

	it('conflict case 14 carries the details', () => {
		const c = CASES.find((x) => x.name === 'conflict_rule_min_profile_max')!;
		expect(errorOf(() => run(c)).conflict).toEqual({
			min: 25,
			minSource: 'rule',
			max: 20,
			maxSource: 'profile'
		});
	});

	it('days_ahead 0 stays 0', () => {
		expect(eff({ days_ahead: 0 }).days_ahead).toBe(0);
	});
});
