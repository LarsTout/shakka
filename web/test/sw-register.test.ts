import { beforeEach, describe, expect, it, vi } from 'vitest';
import { registerServiceWorker } from '#lib/sw-register.js';

const register = vi.fn();
beforeEach(() => vi.clearAllMocks());

describe('registerServiceWorker', () => {
	it('does nothing when disabled', async () => {
		expect(await registerServiceWorker({ serviceWorker: { register } }, false)).toBeNull();
		expect(register).not.toHaveBeenCalled();
	});
	it('returns null without navigator or serviceWorker support', async () => {
		expect(await registerServiceWorker(undefined, true)).toBeNull();
		expect(await registerServiceWorker({}, true)).toBeNull();
	});
	it('registers as a module with scope /', async () => {
		const registration = { scope: '/' };
		register.mockResolvedValue(registration);
		expect(await registerServiceWorker({ serviceWorker: { register } }, true)).toBe(registration);
		expect(register).toHaveBeenCalledWith('/service-worker.js', { type: 'module', scope: '/' });
	});
	it('swallows registration errors', async () => {
		register.mockRejectedValue(new Error('nope'));
		const warn = vi.spyOn(console, 'warn').mockImplementation(() => {});
		expect(await registerServiceWorker({ serviceWorker: { register } }, true)).toBeNull();
		warn.mockRestore();
	});
});
