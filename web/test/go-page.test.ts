import { render, screen } from '@testing-library/svelte';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const nav = vi.hoisted(() => ({ goto: vi.fn(async () => {}), refreshAll: vi.fn() }));
vi.mock('$app/navigation', () => ({ goto: nav.goto, refreshAll: nav.refreshAll }));
vi.mock('#lib/auth.js', async () => (await import('./helpers/fake-session.js')).authModule);

import GoPage from '../src/routes/go/+page.svelte';
import { load } from '../src/routes/go/+page.js';
import { GO_URL_SUMMER, GO_URL_WINTER } from './fixtures/spot-data.js';
import { SESSION, sessionStore } from './helpers/fake-session.js';

const props = (data: unknown) => ({ data }) as never;
const dataFor = async (url: string) =>
	(await (load as (e: unknown) => unknown)({ url: new URL(url) })) as {
		returnPath: string;
		target: string;
	};

beforeEach(() => {
	vi.clearAllMocks();
	localStorage.clear();
	sessionStore.set(undefined);
});

describe('/go page (AC-2)', () => {
	it('(a) waits while the session is unknown', async () => {
		render(GoPage, props(await dataFor(GO_URL_SUMMER)));
		expect(screen.getByText('Doorsturen…')).toBeInTheDocument();
		expect(nav.goto).not.toHaveBeenCalled();
		expect(localStorage.length).toBe(0);
	});
	it('(b) signed out: stores the exact URL and goes to /login once', async () => {
		sessionStore.set(null);
		const data = await dataFor(GO_URL_SUMMER);
		render(GoPage, props(data));
		await vi.waitFor(() => expect(nav.goto).toHaveBeenCalledWith('/login', { replace: true }));
		expect(nav.goto).toHaveBeenCalledTimes(1);
		const saved = JSON.parse(localStorage.getItem('shakka:return_to')!);
		expect(saved.path).toBe(data.returnPath);
		expect(saved.path).toBe(new URL(GO_URL_SUMMER).pathname + new URL(GO_URL_SUMMER).search);
	});
	it('(c) signed in: goes to the target, stores nothing', async () => {
		sessionStore.set(SESSION);
		const data = await dataFor(GO_URL_SUMMER);
		render(GoPage, props(data));
		await vi.waitFor(() => expect(nav.goto).toHaveBeenCalledWith(data.target, { replace: true }));
		expect(nav.goto).toHaveBeenCalledTimes(1);
		expect(localStorage.getItem('shakka:return_to')).toBeNull();
	});
	it('(d) a token refresh does not navigate again', async () => {
		render(GoPage, props(await dataFor(GO_URL_SUMMER)));
		sessionStore.set(SESSION);
		await vi.waitFor(() => expect(nav.goto).toHaveBeenCalledTimes(1));
		sessionStore.set({ ...SESSION });
		await Promise.resolve();
		await new Promise((r) => setTimeout(r, 20));
		expect(nav.goto).toHaveBeenCalledTimes(1);
	});
	it('(e) a reused component for another /go URL redirects again', async () => {
		sessionStore.set(SESSION);
		const first = await dataFor(GO_URL_SUMMER);
		const { rerender } = render(GoPage, props(first));
		await vi.waitFor(() => expect(nav.goto).toHaveBeenCalledTimes(1));
		const second = await dataFor(GO_URL_WINTER);
		await rerender(props(second));
		await vi.waitFor(() => expect(nav.goto).toHaveBeenCalledTimes(2));
		expect(nav.goto).toHaveBeenLastCalledWith(second.target, { replace: true });
	});
});
