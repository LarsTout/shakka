import reasonCodesJson from '../../../data/contracts/reason_codes.json';
import dirClassesJson from '../../../data/contracts/dir_classes.json';
import confidenceJson from '../../../data/contracts/confidence.json';
import alertDefaultsJson from '../../../data/contracts/alert_defaults.json';
import {
	RULE_FIELDS,
	RULE_SOURCES,
	type AlertDefaults,
	type DirClass,
	type RuleSource,
	type Verdict
} from './types.js';

export const UNKNOWN_REASON_LABEL = 'Onbekende reden';
export const UNKNOWN_DIR_CLASS_LABEL = 'Onbekende richtingsklasse';
export const UNKNOWN_CONFIDENCE_LABEL = 'Onbekend';

interface Item {
	code: string;
	label_nl: string;
	effect?: string;
	ridable?: boolean;
}

function itemsOf(json: unknown, name: string): Item[] {
	const bad = () => new Error(`contract ${name} is malformed`);
	if (typeof json !== 'object' || json === null) throw bad();
	const obj = json as Record<string, unknown>;
	if (typeof obj._generated !== 'string' || !Array.isArray(obj.items)) throw bad();
	return obj.items.map((raw: unknown) => {
		if (typeof raw !== 'object' || raw === null) throw bad();
		const it = raw as Record<string, unknown>;
		if (typeof it.code !== 'string' || it.code === '') throw bad();
		if (typeof it.label_nl !== 'string' || it.label_nl.trim() === '') throw bad();
		if (name === 'reason_codes' && it.effect !== 'no_go' && it.effect !== 'marginal') throw bad();
		if (name === 'dir_classes' && typeof it.ridable !== 'boolean') throw bad();
		return it as unknown as Item;
	});
}

const reasonItems = itemsOf(reasonCodesJson, 'reason_codes');
const dirItems = itemsOf(dirClassesJson, 'dir_classes');
const confItems = itemsOf(confidenceJson, 'confidence');

const labels = (items: Item[]) => new Map(items.map((i) => [i.code, i.label_nl]));
const reasonLabels = labels(reasonItems);
const dirLabels = labels(dirItems);
const confLabels = labels(confItems);
const effects = new Map(reasonItems.map((i) => [i.code, i.effect as Verdict]));

/** Codes in file order. */
export const CONTRACT_REASON_CODES: readonly string[] = reasonItems.map((i) => i.code);
export const CONTRACT_DIR_CLASSES: readonly string[] = dirItems.map((i) => i.code);
export const CONTRACT_CONFIDENCES: readonly string[] = confItems.map((i) => i.code);
/** Codes with ridable: true in dir_classes.json, in file order. */
export const RIDABLE_DIR_CLASSES: readonly DirClass[] = dirItems
	.filter((i) => i.ridable)
	.map((i) => i.code as DirClass);

const isNum = (v: unknown): v is number => typeof v === 'number' && Number.isFinite(v);
const isNumOrNull = (v: unknown): boolean => v === null || isNum(v);
const isIntList = (v: unknown): v is number[] =>
	Array.isArray(v) && v.length > 0 && v.every((d) => Number.isInteger(d) && d >= 1 && d <= 7);

/** Validates the shape of alert_defaults.json. Any deviation -> Error('contract alert_defaults is malformed'). */
export function parseAlertDefaults(json: unknown): AlertDefaults {
	const bad = () => new Error('contract alert_defaults is malformed');
	if (typeof json !== 'object' || json === null) throw bad();
	const obj = json as Record<string, unknown>;
	if (typeof obj._generated !== 'string' || !Array.isArray(obj.items)) throw bad();
	if (obj.items.length !== RULE_FIELDS.length) throw bad();
	const out: Record<string, unknown> = {};
	obj.items.forEach((raw: unknown, i: number) => {
		if (typeof raw !== 'object' || raw === null) throw bad();
		const it = raw as Record<string, unknown>;
		const field = RULE_FIELDS[i]!;
		if (it.field !== field) throw bad();
		if (typeof it.label_nl !== 'string' || it.label_nl.trim() === '') throw bad();
		const sources = it.sources;
		if (
			!Array.isArray(sources) ||
			sources.length === 0 ||
			!sources.every((s) => RULE_SOURCES.includes(s as RuleSource)) ||
			sources[sources.length - 1] !== 'system'
		)
			throw bad();
		if (!isNumOrNull(it.min) || !isNumOrNull(it.max) || !isNumOrNull(it.min_span_kn)) throw bad();
		if (it.allowed !== null && !Array.isArray(it.allowed)) throw bad();
		switch (field) {
			case 'enabled':
				if (typeof it.default !== 'boolean') throw bad();
				break;
			case 'min_kn':
			case 'max_kn':
			case 'min_go_hours':
			case 'days_ahead':
				if (!isNum(it.default) || !isNum(it.min) || !isNum(it.max)) throw bad();
				if (field === 'max_kn' && !isNum(it.min_span_kn)) throw bad();
				break;
			case 'dir_classes': {
				const allowed = it.allowed as unknown[] | null;
				if (!allowed || allowed.length === 0) throw bad();
				if (!allowed.every((c) => RIDABLE_DIR_CLASSES.includes(c as DirClass))) throw bad();
				const def = it.default;
				if (!Array.isArray(def) || def.length === 0) throw bad();
				if (!def.every((c) => allowed.includes(c))) throw bad();
				break;
			}
			case 'weekdays':
				if (!isIntList(it.allowed) || !isIntList(it.default)) throw bad();
				break;
			case 'earliest_local':
			case 'latest_local':
				if (it.default !== null) throw bad();
				break;
		}
		out[field] = it;
	});
	return out as unknown as AlertDefaults;
}

export const ALERT_DEFAULTS: AlertDefaults = parseAlertDefaults(alertDefaultsJson);

/** Dutch label; never the raw code. */
export function reasonLabel(code: string): string {
	return reasonLabels.get(code) ?? UNKNOWN_REASON_LABEL;
}
/** 'no_go' | 'marginal' from the file; unknown code -> null. */
export function reasonEffect(code: string): Verdict | null {
	return effects.get(code) ?? null;
}
export function dirClassLabel(code: string): string {
	return dirLabels.get(code) ?? UNKNOWN_DIR_CLASS_LABEL;
}
export function confidenceLabel(code: string): string {
	return confLabels.get(code) ?? UNKNOWN_CONFIDENCE_LABEL;
}
