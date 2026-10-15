import { vi } from 'vitest';
import { base64UrlToBytes } from '../../src/lib/env-schema.js';

/** base64url of 0x04 plus 64 zero bytes. Never a real key. */
export const TEST_VAPID_PUBLIC_KEY = 'B' + 'A'.repeat(86);
export const OTHER_VAPID_PUBLIC_KEY = 'B' + 'A'.repeat(42) + 'Q' + 'A'.repeat(43);

export const IPHONE_UA =
	'Mozilla/5.0 (iPhone; CPU iPhone OS 18_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.5 Mobile/15E148 Safari/604.1';
export const IPAD_DESKTOP_UA =
	'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.5 Safari/605.1.15';
export const ANDROID_UA =
	'Mozilla/5.0 (Linux; Android 15; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Mobile Safari/537.36';

/** Mutable stand-in for $app/env/public. */
export const publicEnv = {
	PUBLIC_VAPID_PUBLIC_KEY: TEST_VAPID_PUBLIC_KEY as string,
	PUBLIC_SUPABASE_URL: 'http://127.0.0.1:54321',
	PUBLIC_SUPABASE_PUBLISHABLE_KEY: 'sb_publishable_test',
	PUBLIC_MAPTILER_KEY: ''
};

export interface FakeSubscription {
	endpoint: string;
	options: { applicationServerKey: ArrayBuffer };
	toJSON: () => unknown;
	unsubscribe: ReturnType<typeof vi.fn<() => Promise<boolean>>>;
}

export function fakeSubscription(
	endpoint = 'https://push.example.test/sub-1',
	key = TEST_VAPID_PUBLIC_KEY
): FakeSubscription {
	return {
		endpoint,
		options: { applicationServerKey: base64UrlToBytes(key).buffer },
		toJSON: () => ({
			endpoint,
			expirationTime: null,
			keys: { p256dh: 'p256dh-test', auth: 'auth-test' }
		}),
		unsubscribe: vi.fn(async () => true)
	};
}

export interface PushEnvOptions {
	userAgent?: string;
	maxTouchPoints?: number;
	navigatorStandalone?: boolean;
	displayModeStandalone?: boolean;
	supported?: boolean;
	permission?: NotificationPermission;
	requestResult?: NotificationPermission;
	subscription?: FakeSubscription | null;
	newSubscriptions?: FakeSubscription[];
	ready?: 'resolve' | 'never';
	updateState?: 'none' | 'waiting' | 'installing';
}

/** Installs fake navigator, Notification, PushManager and serviceWorker globals. */
export function installPushEnv(opts: PushEnvOptions = {}) {
	const {
		userAgent = ANDROID_UA,
		maxTouchPoints = 0,
		navigatorStandalone = false,
		displayModeStandalone = false,
		supported = true,
		permission = 'default',
		requestResult = 'granted',
		subscription = null,
		newSubscriptions = [fakeSubscription()],
		ready = 'resolve',
		updateState = 'none'
	} = opts;

	const set: Array<[object, string]> = [];
	const define = (target: object, name: string, value: unknown) => {
		Object.defineProperty(target, name, { configurable: true, writable: true, value });
		set.push([target, name]);
	};

	const uaSpy = vi.spyOn(navigator, 'userAgent', 'get').mockReturnValue(userAgent);
	define(navigator, 'maxTouchPoints', maxTouchPoints);
	define(navigator, 'standalone', navigatorStandalone);
	define(window, 'matchMedia', vi.fn((q: string) => ({
		matches: q === '(display-mode: standalone)' && displayModeStandalone,
		media: q
	})));

	let current: FakeSubscription | null = subscription;
	const queue = [...newSubscriptions];
	const wrap = (s: FakeSubscription): FakeSubscription => {
		const original = s.unsubscribe;
		s.unsubscribe = vi.fn(async () => {
			await original();
			if (current === s) current = null;
			return true;
		});
		return s;
	};
	if (current) wrap(current);

	const getSubscription = vi.fn(async () => current);
	const subscribe = vi.fn(async (_options: unknown) => {
		const next = queue.shift();
		if (!next) throw new Error('no more subscriptions');
		current = wrap(next);
		return current;
	});
	const registration = {
		waiting: updateState === 'waiting' ? {} : null,
		installing: updateState === 'installing' ? {} : null,
		pushManager: { getSubscription, subscribe }
	};

	const N = { permission, requestPermission: vi.fn(async () => requestResult) };
	N.requestPermission.mockImplementation(async () => {
		N.permission = requestResult;
		return requestResult;
	});
	const requestPermission = N.requestPermission;

	if (supported) {
		define(window, 'PushManager', class {});
		define(window, 'Notification', N);
		const getRegistration = vi.fn(async () => registration);
		define(navigator, 'serviceWorker', {
			ready: ready === 'resolve' ? Promise.resolve(registration) : new Promise(() => {}),
			getRegistration
		});
	}

	return {
		requestPermission,
		subscribe,
		getSubscription,
		registration,
		uninstall() {
			uaSpy.mockRestore();
			for (const [target, name] of set) delete (target as Record<string, unknown>)[name];
		}
	};
}
