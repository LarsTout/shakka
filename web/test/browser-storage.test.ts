import { afterEach, describe, expect, it, vi } from 'vitest';
import { browserStorage } from '../src/lib/browser-storage.js';

const original = Object.getOwnPropertyDescriptor(globalThis, 'localStorage');

afterEach(() => {
	vi.unstubAllGlobals();
	if (original) Object.defineProperty(globalThis, 'localStorage', original);
});

describe('browserStorage', () => {
	it('returns localStorage', () => {
		expect(browserStorage()).toBe(globalThis.localStorage);
	});
	it('undefined when missing', () => {
		vi.stubGlobal('localStorage', undefined);
		expect(browserStorage()).toBeUndefined();
	});
	it('undefined when access throws', () => {
		Object.defineProperty(globalThis, 'localStorage', {
			configurable: true,
			get() {
				throw new DOMException('denied', 'SecurityError');
			}
		});
		expect(browserStorage()).toBeUndefined();
	});
});
