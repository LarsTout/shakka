import { PUBLIC_VAPID_PUBLIC_KEY } from '$app/env/public';
import { DataError } from './data.js';
import { base64UrlToBytes } from './env-schema.js';
import { needsInstallFirst } from './platform.js';
import type { PushSubscriptionKeys } from './types.js';
import {
	addPushSubscription,
	listOwnPushSubscriptions,
	removePushSubscription
} from './user-data.js';

export { needsInstallFirst } from './platform.js';

export const MAX_PUSH_SUBSCRIPTIONS = 10; // = MAX_TARGETS_PER_USER in shakka.jobs.push (WP-17)
export const SW_READY_TIMEOUT_MS = 10_000;
export const SIGN_OUT_PUSH_TIMEOUT_MS = 5_000;

export const PUSH_MESSAGES = {
	installFirst:
		'Meldingen op iPhone en iPad werken alleen in de app op je beginscherm (iOS 16.4 of nieuwer). Tik op de deelknop en kies ‘Zet op beginscherm’. Open Shakka daarna vanaf je beginscherm, log daar in en zet hier meldingen aan.',
	unsupported:
		'Deze browser ondersteunt geen pushmeldingen. Op iPhone en iPad werkt het vanaf iOS 16.4, in de app op je beginscherm.',
	unavailable: 'Meldingen zijn in deze versie van Shakka nog niet beschikbaar.',
	denied:
		'Meldingen zijn geblokkeerd voor Shakka. Sta ze toe in de instellingen van je browser of telefoon en herlaad deze pagina.',
	dismissed: 'Meldingen staan nog uit: je hebt geen toestemming gegeven.',
	noServiceWorker: 'Meldingen zijn nu niet beschikbaar. Herlaad de pagina en probeer het opnieuw.',
	updatePending:
		'Er staat een nieuwe versie van Shakka klaar. Sluit de app helemaal af (op iPhone en iPad: veeg hem weg in de appkiezer), open hem opnieuw en zet dan meldingen aan.',
	subscribeFailed: 'Aanzetten is niet gelukt. Probeer het opnieuw.',
	saveFailed: 'Aanzetten is niet gelukt: geen verbinding met de server. Probeer het opnieuw.',
	otherAccount:
		'Aanzetten is niet gelukt: dit apparaat is nog gekoppeld aan een ander account. Probeer het opnieuw.',
	statusFailed: 'De status van meldingen kon niet worden geladen.',
	intro:
		'Krijg een melding op dit apparaat als er voor een van je favoriete spots een kitebaar window aankomt.',
	newWindowsOnly:
		'Je krijgt meldingen over nieuwe windows en over wijzigingen. Een window dat al liep voordat je meldingen aanzette, meldt Shakka pas bij een wijziging.',
	on: 'Je krijgt meldingen op dit apparaat.',
	enabled: 'Meldingen staan aan op dit apparaat.',
	disabled: 'Meldingen staan uit op dit apparaat.'
} as const;

export type PushStatus =
	| 'needs_install'
	| 'unsupported'
	| 'unavailable'
	| 'denied'
	| 'off'
	| 'on'
	| 'error';

/** Read at call time, never copied at module level (testable per test). */
function currentVapidKey(): string | undefined {
	return PUBLIC_VAPID_PUBLIC_KEY;
}

export function isPushSupported(): boolean {
	return (
		typeof navigator !== 'undefined' &&
		typeof window !== 'undefined' &&
		'serviceWorker' in navigator &&
		'PushManager' in window &&
		'Notification' in window
	);
}

/** Key bytes for applicationServerKey, or null for an empty/undefined key. */
export function vapidKeyBytes(key: string | undefined): Uint8Array<ArrayBuffer> | null {
	if (!key) return null;
	return base64UrlToBytes(key);
}

/** Resolves with the promise's value, or with fallback after ms. Clears its timer. Never rejects on timeout. */
export function withTimeout<T>(promise: Promise<T>, ms: number, fallback: T): Promise<T> {
	return new Promise<T>((resolve, reject) => {
		const timer = setTimeout(() => resolve(fallback), ms);
		promise.then(
			(v) => {
				clearTimeout(timer);
				resolve(v);
			},
			(e) => {
				clearTimeout(timer);
				reject(e);
			}
		);
	});
}

/** endpoint, p256dh and auth from sub.toJSON(); null if any is missing or the endpoint is not https (DB CHECK, WP-17). */
export function subscriptionKeys(
	sub: Pick<PushSubscription, 'endpoint' | 'toJSON'>
): PushSubscriptionKeys | null {
	const json = sub.toJSON();
	const endpoint = json.endpoint ?? sub.endpoint;
	const p256dh = json.keys?.p256dh;
	const auth = json.keys?.auth;
	if (!endpoint || !p256dh || !auth) return null;
	if (!endpoint.startsWith('https://')) return null;
	return { endpoint, p256dh, auth };
}

function bytesEqual(a: Uint8Array, b: Uint8Array): boolean {
	return a.length === b.length && a.every((v, i) => v === b[i]);
}

function sameKey(sub: PushSubscription, key: Uint8Array): boolean {
	const k = sub.options?.applicationServerKey;
	return !k || bytesEqual(new Uint8Array(k), key);
}

async function currentSubscription(): Promise<PushSubscription | null> {
	const reg = await withTimeout<ServiceWorkerRegistration | undefined>(
		navigator.serviceWorker.getRegistration(),
		SW_READY_TIMEOUT_MS,
		undefined
	);
	return reg ? await reg.pushManager.getSubscription() : null;
}

async function register(sub: PushSubscription): Promise<'ok' | 'other_account'> {
	const keys = subscriptionKeys(sub);
	if (!keys) throw new Error('push keys missing');
	if ((await addPushSubscription(keys)) === 'added') return 'ok';
	return (await listOwnPushSubscriptions()).some((r) => r.endpoint === keys.endpoint)
		? 'ok'
		: 'other_account';
}

/** Removes own rows beyond the number the backend serves (oldest first, never the current endpoint). */
async function pruneOld(endpoint: string): Promise<void> {
	try {
		const rows = await listOwnPushSubscriptions();
		const extra = rows.filter((r) => r.endpoint !== endpoint).slice(MAX_PUSH_SUBSCRIPTIONS - 1);
		for (const r of extra) await removePushSubscription(r.id);
	} catch {
		console.warn('push prune failed');
	}
}

export async function getPushStatus(): Promise<PushStatus> {
	if (needsInstallFirst()) return 'needs_install';
	if (!isPushSupported()) return 'unsupported';
	const key = vapidKeyBytes(currentVapidKey());
	if (!key) return 'unavailable';
	if (Notification.permission === 'denied') return 'denied';
	if (Notification.permission !== 'granted') return 'off'; // no DB call
	try {
		const sub = await currentSubscription();
		if (!sub || !sameKey(sub, key)) return 'off';
		const keys = subscriptionKeys(sub);
		if (!keys) return 'off';
		return (await listOwnPushSubscriptions()).some((r) => r.endpoint === keys.endpoint)
			? 'on'
			: 'off';
	} catch {
		console.warn('push status failed');
		return 'error';
	}
}

export async function enablePush(): Promise<{ ok: boolean; error?: string }> {
	if (needsInstallFirst()) return { ok: false, error: PUSH_MESSAGES.installFirst };
	if (!isPushSupported()) return { ok: false, error: PUSH_MESSAGES.unsupported };
	const key = vapidKeyBytes(currentVapidKey());
	if (!key) return { ok: false, error: PUSH_MESSAGES.unavailable };
	let permission: NotificationPermission;
	try {
		permission = await Notification.requestPermission(); // first await: still inside the tap (iOS)
	} catch {
		return { ok: false, error: PUSH_MESSAGES.dismissed };
	}
	if (permission === 'denied') return { ok: false, error: PUSH_MESSAGES.denied };
	if (permission !== 'granted') return { ok: false, error: PUSH_MESSAGES.dismissed };
	const reg = await withTimeout<ServiceWorkerRegistration | null>(
		navigator.serviceWorker.ready,
		SW_READY_TIMEOUT_MS,
		null
	);
	if (!reg) return { ok: false, error: PUSH_MESSAGES.noServiceWorker };
	if (reg.waiting || reg.installing) return { ok: false, error: PUSH_MESSAGES.updatePending }; // A14
	const options = { userVisibleOnly: true, applicationServerKey: key };
	try {
		let sub = await reg.pushManager.getSubscription();
		if (sub && !sameKey(sub, key)) {
			await sub.unsubscribe();
			sub = null;
		}
		sub ??= await reg.pushManager.subscribe(options);
		let outcome = await register(sub);
		if (outcome === 'other_account') {
			// A7: the endpoint belongs to another account on this device.
			await sub.unsubscribe();
			sub = await reg.pushManager.subscribe(options);
			outcome = await register(sub);
			if (outcome === 'other_account') return { ok: false, error: PUSH_MESSAGES.otherAccount };
		}
		await pruneOld(sub.endpoint); // A8, never throws
		return { ok: true };
	} catch (e) {
		console.warn('push enable failed');
		return {
			ok: false,
			error: e instanceof DataError ? PUSH_MESSAGES.saveFailed : PUSH_MESSAGES.subscribeFailed
		};
	}
}

export async function disablePush(): Promise<void> {
	if (!isPushSupported()) return;
	let found: PushSubscription | null = null;
	try {
		found = await currentSubscription();
	} catch {
		console.warn('push status failed');
		return;
	}
	if (!found) return;
	const sub = found;
	try {
		const own = (await listOwnPushSubscriptions()).find((r) => r.endpoint === sub.endpoint);
		if (own) await removePushSubscription(own.id);
	} catch {
		console.warn('push subscription delete failed'); // A5: unsubscribe anyway
	}
	try {
		await sub.unsubscribe();
	} catch {
		console.warn('push unsubscribe failed');
	}
}

export function releasePushForSignOut(): Promise<void> {
	return withTimeout<void>(disablePush(), SIGN_OUT_PUSH_TIMEOUT_MS, undefined);
}
