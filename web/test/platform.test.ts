// @vitest-environment node
import { afterEach, describe, expect, it, vi } from 'vitest';
import { IPAD_DESKTOP_UA, ANDROID_UA, IPHONE_UA } from './helpers/fake-push.js';
import {
	isIos,
	isStandalone,
	needsInstallFirst,
	readPlatform,
	type PlatformInfo
} from '../src/lib/platform.js';

afterEach(() => vi.unstubAllGlobals());

const info = (over: Partial<PlatformInfo>): PlatformInfo => ({
	userAgent: ANDROID_UA,
	maxTouchPoints: 0,
	navigatorStandalone: false,
	displayModeStandalone: false,
	...over
});

describe('isIos', () => {
	it('detects an iPhone', () => {
		expect(isIos(info({ userAgent: IPHONE_UA }))).toBe(true);
	});
	it('detects iPadOS with a desktop UA only with touch points', () => {
		expect(isIos(info({ userAgent: IPAD_DESKTOP_UA, maxTouchPoints: 5 }))).toBe(true);
		expect(isIos(info({ userAgent: IPAD_DESKTOP_UA, maxTouchPoints: 0 }))).toBe(false);
	});
	it('does not detect Android', () => {
		expect(isIos(info({}))).toBe(false);
	});
});

describe('isStandalone', () => {
	it('is true for either signal', () => {
		expect(isStandalone(info({ navigatorStandalone: true }))).toBe(true);
		expect(isStandalone(info({ displayModeStandalone: true }))).toBe(true);
		expect(isStandalone(info({}))).toBe(false);
	});
});

describe('needsInstallFirst', () => {
	it('is true for iOS in the browser only', () => {
		expect(needsInstallFirst(info({ userAgent: IPHONE_UA }))).toBe(true);
		expect(needsInstallFirst(info({ userAgent: IPHONE_UA, navigatorStandalone: true }))).toBe(false);
		expect(needsInstallFirst(info({}))).toBe(false);
	});
});

describe('readPlatform', () => {
	it('survives a missing navigator', () => {
		vi.stubGlobal('navigator', undefined);
		expect(readPlatform()).toEqual({
			userAgent: '',
			maxTouchPoints: 0,
			navigatorStandalone: false,
			displayModeStandalone: false
		});
	});
	it('does not throw in plain node', () => {
		expect(() => readPlatform()).not.toThrow();
		expect(isIos(readPlatform())).toBe(false);
		expect(isStandalone(readPlatform())).toBe(false);
	});
});
