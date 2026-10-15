import reasonCodesJson from '../../../data/contracts/reason_codes.json';
import dirClassesJson from '../../../data/contracts/dir_classes.json';
import confidenceJson from '../../../data/contracts/confidence.json';
import type { DirClass, Verdict } from './types.js';

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
