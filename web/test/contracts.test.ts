// @vitest-environment node
import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';
import {
	ALERT_DEFAULTS,
	parseAlertDefaults,
	CONTRACT_CONFIDENCES,
	CONTRACT_DIR_CLASSES,
	CONTRACT_REASON_CODES,
	RIDABLE_DIR_CLASSES,
	UNKNOWN_CONFIDENCE_LABEL,
	UNKNOWN_DIR_CLASS_LABEL,
	UNKNOWN_REASON_LABEL,
	confidenceLabel,
	dirClassLabel,
	reasonEffect,
	reasonLabel
} from '../src/lib/contracts.js';
import { CONFIDENCES, DIR_CLASSES, REASON_CODES, RULE_FIELDS, VERDICTS } from '../src/lib/types.js';

interface Item {
	code: string;
	label_nl: string;
	effect?: string;
}
const read = (name: string): Item[] =>
	JSON.parse(readFileSync(new URL(`../../data/contracts/${name}.json`, import.meta.url), 'utf8'))
		.items;

const reasons = read('reason_codes');
const dirs = read('dir_classes');
const confs = read('confidence');

function checkLabels(items: Item[], fn: (c: string) => string, fallback: string) {
	for (const it of items) {
		const label = fn(it.code);
		expect(label.trim()).not.toBe('');
		expect(label).not.toBe(it.code);
		expect(label).not.toBe(fallback);
		expect(label).toBe(it.label_nl);
	}
}

describe('contract labels (AC-2)', () => {
	it('reason codes', () => checkLabels(reasons, reasonLabel, UNKNOWN_REASON_LABEL));
	it('dir classes', () => checkLabels(dirs, dirClassLabel, UNKNOWN_DIR_CLASS_LABEL));
	it('confidences', () => checkLabels(confs, confidenceLabel, UNKNOWN_CONFIDENCE_LABEL));

	it('falls back for unknown codes', () => {
		expect(reasonLabel('bogus')).toBe(UNKNOWN_REASON_LABEL);
		expect(dirClassLabel('bogus')).toBe(UNKNOWN_DIR_CLASS_LABEL);
		expect(confidenceLabel('bogus')).toBe(UNKNOWN_CONFIDENCE_LABEL);
	});

	it('ridable dir classes', () => {
		expect([...RIDABLE_DIR_CLASSES]).toEqual(['onshore', 'side_onshore', 'sideshore']);
	});

	it('reason effects', () => {
		expect(reasonEffect('offshore')).toBe('no_go');
		expect(reasonEffect('gusty')).toBe('marginal');
		expect(reasonEffect('bogus')).toBeNull();
	});

	it('TypeScript unions equal the contract files', () => {
		expect(new Set(REASON_CODES)).toEqual(new Set(CONTRACT_REASON_CODES));
		expect(new Set(DIR_CLASSES)).toEqual(new Set(CONTRACT_DIR_CLASSES));
		expect(new Set(CONFIDENCES)).toEqual(new Set(CONTRACT_CONFIDENCES));
		const effects = new Set(reasons.map((r) => r.effect));
		expect(new Set([...effects, 'go'])).toEqual(new Set(VERDICTS));
	});
});

const alertDefaultsJson = (): { _generated: string; items: Record<string, unknown>[] } =>
	JSON.parse(
		readFileSync(new URL('../../data/contracts/alert_defaults.json', import.meta.url), 'utf8')
	);

describe('ALERT_DEFAULTS', () => {
	it('has the keys in RULE_FIELDS order', () => {
		expect(Object.keys(ALERT_DEFAULTS)).toEqual([...RULE_FIELDS]);
	});
	it('exposes the ridable classes only and the system defaults', () => {
		expect([...ALERT_DEFAULTS.dir_classes.allowed]).toEqual(['onshore', 'side_onshore', 'sideshore']);
		expect(ALERT_DEFAULTS.min_kn.default).toBe(12);
		expect(ALERT_DEFAULTS.max_kn.min_span_kn).toBe(5);
	});
});

describe('parseAlertDefaults', () => {
	const MALFORMED = 'contract alert_defaults is malformed';
	const mutate = (fn: (j: ReturnType<typeof alertDefaultsJson>) => void) => {
		const j = alertDefaultsJson();
		fn(j);
		return j;
	};
	const item = (j: ReturnType<typeof alertDefaultsJson>, field: string) =>
		j.items.find((i) => i.field === field)!;

	it('accepts the real file', () => {
		expect(() => parseAlertDefaults(alertDefaultsJson())).not.toThrow();
	});
	it('rejects offshore in allowed', () => {
		const j = mutate((x) => (item(x, 'dir_classes').allowed as string[]).push('offshore'));
		expect(() => parseAlertDefaults(j)).toThrow(MALFORMED);
	});
	it('rejects side_offshore in default', () => {
		const j = mutate((x) => (item(x, 'dir_classes').default as string[]).push('side_offshore'));
		expect(() => parseAlertDefaults(j)).toThrow(MALFORMED);
	});
	it('rejects 8 items', () => {
		const j = mutate((x) => x.items.pop());
		expect(() => parseAlertDefaults(j)).toThrow(MALFORMED);
	});
	it('rejects a wrong field order', () => {
		const j = mutate((x) => x.items.reverse());
		expect(() => parseAlertDefaults(j)).toThrow(MALFORMED);
	});
	it('rejects an empty label_nl', () => {
		const j = mutate((x) => (item(x, 'min_kn').label_nl = '  '));
		expect(() => parseAlertDefaults(j)).toThrow(MALFORMED);
	});
	it('rejects sources that do not end in system', () => {
		const j = mutate((x) => (item(x, 'min_kn').sources = ['system', 'rule']));
		expect(() => parseAlertDefaults(j)).toThrow(MALFORMED);
	});
	it('rejects non-objects', () => {
		expect(() => parseAlertDefaults(null)).toThrow(MALFORMED);
		expect(() => parseAlertDefaults({ _generated: 'x', items: 'no' })).toThrow(MALFORMED);
	});
});
