import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';
import {
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
import { CONFIDENCES, DIR_CLASSES, REASON_CODES, VERDICTS } from '../src/lib/types.js';

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
