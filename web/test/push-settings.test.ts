import { render, screen } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { createFakeSupabase } from './helpers/fake-supabase.js';
import {
	IPAD_DESKTOP_UA,
	IPHONE_UA,
	TEST_VAPID_PUBLIC_KEY,
	fakeSubscription,
	installPushEnv,
	publicEnv
} from './helpers/fake-push.js';

const fake = vi.hoisted(() => ({ current: null as unknown as ReturnType<typeof createFakeSupabase> }));
vi.mock('#lib/supabase.js', async () => {
	const { createFakeSupabase } = await import('./helpers/fake-supabase.js');
	fake.current = createFakeSupabase();
	return { supabase: fake.current.client, initialUrlHash: '' };
});
vi.mock('$app/env/public', async () => (await import('./helpers/fake-push.js')).publicEnv);

import PushSettings from '../src/lib/components/PushSettings.svelte';
import { PUSH_MESSAGES } from '../src/lib/push.js';

let env: ReturnType<typeof installPushEnv> | undefined;
const install = (o: Parameters<typeof installPushEnv>[0] = {}) => (env = installPushEnv(o));
const T = 'push_subscriptions';

beforeEach(() => {
	vi.clearAllMocks();
	fake.current.reset();
	publicEnv.PUBLIC_VAPID_PUBLIC_KEY = TEST_VAPID_PUBLIC_KEY;
	vi.spyOn(console, 'warn').mockImplementation(() => {});
});
afterEach(() => {
	env?.uninstall();
	env = undefined;
});

const enableBtn = () => screen.findByRole('button', { name: 'Meldingen aanzetten' });

describe('PushSettings', () => {
	it('turns notifications on after a tap, never before (AC-2)', async () => {
		install();
		render(PushSettings, { signedIn: true });
		const btn = await enableBtn();
		expect(screen.getByText(PUSH_MESSAGES.newWindowsOnly)).toBeInTheDocument();
		expect(env!.requestPermission).not.toHaveBeenCalled();
		expect(env!.subscribe).not.toHaveBeenCalled();
		await userEvent.setup().click(btn);
		expect(env!.requestPermission).toHaveBeenCalledTimes(1);
		expect(env!.subscribe).toHaveBeenCalledTimes(1);
		const opts = env!.subscribe.mock.calls[0]![0] as { applicationServerKey: unknown };
		expect(opts.applicationServerKey).toBeInstanceOf(Uint8Array);
		const status = await screen.findByRole('status');
		expect(status).toHaveTextContent(PUSH_MESSAGES.enabled);
		expect(screen.getByRole('button', { name: 'Meldingen uitzetten' })).toBeInTheDocument();
		const insert = fake.current.calls.find((c) => c.ops[0]![0] === 'insert')!;
		expect(Object.keys(insert.ops[0]![1] as object).sort()).toEqual(['auth', 'endpoint', 'p256dh']);
	});

	it('turns notifications off (AC-2)', async () => {
		const sub = fakeSubscription();
		install({ permission: 'granted', subscription: sub });
		const rows = { data: [{ id: 'r1', endpoint: sub.endpoint, created_at: 'x' }], error: null };
		fake.current.respond(T, rows, rows); // status check, then the delete lookup
		render(PushSettings, { signedIn: true });
		await userEvent.setup().click(await screen.findByRole('button', { name: 'Meldingen uitzetten' }));
		expect(await screen.findByText(PUSH_MESSAGES.disabled)).toBeInTheDocument();
		expect(sub.unsubscribe).toHaveBeenCalledTimes(1);
		expect(fake.current.calls.some((c) => c.ops[0]![0] === 'delete')).toBe(true);
		expect(screen.getByRole('button', { name: 'Meldingen aanzetten' })).toBeInTheDocument();
	});

	describe('AC-4: iOS needs the home screen app', () => {
		it.each([
			['iPhone', { userAgent: IPHONE_UA }],
			['iPad desktop UA', { userAgent: IPAD_DESKTOP_UA, maxTouchPoints: 5 }]
		])('%s: install text, no button, no queries', async (_n, opts) => {
			for (const signedIn of [true, false]) {
				const e = installPushEnv({ ...opts, supported: false });
				const { unmount } = render(PushSettings, { signedIn });
				expect(screen.getByText(PUSH_MESSAGES.installFirst)).toBeInTheDocument();
				expect(screen.queryByRole('button', { name: 'Meldingen aanzetten' })).toBeNull();
				expect(fake.current.calls).toHaveLength(0);
				unmount();
				e.uninstall();
			}
		});
		it('in the home screen app the button is there', async () => {
			install({ userAgent: IPHONE_UA, navigatorStandalone: true });
			render(PushSettings, { signedIn: true });
			expect(await enableBtn()).toBeInTheDocument();
			expect(screen.queryByText(PUSH_MESSAGES.installFirst)).toBeNull();
		});
	});

	it('renders nothing when signed out on Android', async () => {
		install();
		render(PushSettings, { signedIn: false });
		expect(screen.queryByRole('heading', { name: 'Meldingen op dit apparaat' })).toBeNull();
		expect(fake.current.calls).toHaveLength(0);
		expect(env!.registration.pushManager.getSubscription).not.toHaveBeenCalled();
	});

	it('shows the denied text once, without a button', async () => {
		install({ permission: 'denied' });
		render(PushSettings, { signedIn: true });
		expect(await screen.findByText(PUSH_MESSAGES.denied)).toBeInTheDocument();
		expect(screen.queryByRole('button', { name: 'Meldingen aanzetten' })).toBeNull();
	});

	it('N-6: denied in the prompt shows the denied text once and no alert', async () => {
		install({ requestResult: 'denied' });
		render(PushSettings, { signedIn: true });
		await userEvent.setup().click(await enableBtn());
		await vi.waitFor(() => expect(screen.getAllByText(PUSH_MESSAGES.denied)).toHaveLength(1));
		expect(screen.queryByRole('button', { name: 'Meldingen aanzetten' })).toBeNull();
		expect(screen.queryByRole('alert')).toBeNull();
	});

	it('shows unavailable without a key', async () => {
		install();
		publicEnv.PUBLIC_VAPID_PUBLIC_KEY = '';
		render(PushSettings, { signedIn: true });
		expect(await screen.findByText(PUSH_MESSAGES.unavailable)).toBeInTheDocument();
		expect(screen.queryByRole('button', { name: 'Meldingen aanzetten' })).toBeNull();
	});

	it('shows a banner on a load error and retries', async () => {
		install({ permission: 'granted', subscription: fakeSubscription() });
		fake.current.respond(T, { data: null, error: { code: '42501' } });
		render(PushSettings, { signedIn: true });
		expect(await screen.findByRole('alert')).toHaveTextContent(PUSH_MESSAGES.statusFailed);
		await userEvent.setup().click(screen.getByRole('button', { name: 'Opnieuw proberen' }));
		await vi.waitFor(() => expect(fake.current.calls).toHaveLength(2));
	});

	it('disables the button while enabling', async () => {
		install();
		env!.requestPermission.mockImplementationOnce(() => new Promise(() => {}));
		render(PushSettings, { signedIn: true });
		const btn = await enableBtn();
		await userEvent.setup().click(btn);
		expect(btn).toBeDisabled();
	});

	it('shows updatePending as an alert and keeps the button', async () => {
		install({ updateState: 'waiting' });
		render(PushSettings, { signedIn: true });
		await userEvent.setup().click(await enableBtn());
		expect(await screen.findByRole('alert')).toHaveTextContent(PUSH_MESSAGES.updatePending);
		expect(screen.getByRole('button', { name: 'Meldingen aanzetten' })).toBeEnabled();
		expect(fake.current.calls).toHaveLength(0);
	});
});
