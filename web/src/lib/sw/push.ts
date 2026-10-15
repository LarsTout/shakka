import type { WaitUntilEvent } from './shell.js';

export const FALLBACK_TITLE = 'Shakka';
export const FALLBACK_BODY = 'Er is een nieuwe melding. Open Shakka voor de details.';
export const NOTIFICATION_ICON = '/icons/icon-192.png';

export interface ParsedPush {
	title: string;
	body: string;
	url: string;
	tag: string | undefined;
}

const FALLBACK: ParsedPush = { title: FALLBACK_TITLE, body: FALLBACK_BODY, url: '/', tag: undefined };

/** Never throws. Invalid JSON, null or a non-object -> fallback values. */
export function parsePushPayload(text: string | null): ParsedPush {
	if (text === null) return { ...FALLBACK };
	let value: unknown;
	try {
		value = JSON.parse(text);
	} catch {
		return { ...FALLBACK };
	}
	if (value === null || typeof value !== 'object' || Array.isArray(value)) return { ...FALLBACK };
	const o = value as Record<string, unknown>;
	return {
		title: typeof o.title === 'string' && o.title.trim() ? o.title : FALLBACK_TITLE,
		body: typeof o.body === 'string' ? o.body : '',
		url: typeof o.url === 'string' && o.url ? o.url : '/',
		tag: typeof o.tag === 'string' && o.tag ? o.tag : undefined
	};
}

/** Resolves against the origin; only http: and https: are allowed, otherwise the start page. */
export function resolveTargetUrl(raw: unknown, origin: string): string {
	try {
		const url = new URL(String(raw ?? '/'), origin);
		if (url.protocol === 'http:' || url.protocol === 'https:') return url.href;
	} catch {
		// fall through
	}
	return `${origin}/`;
}

export interface PushMessageDataLike {
	text(): string;
}
export interface PushEventLike extends WaitUntilEvent {
	readonly data: PushMessageDataLike | null;
}
export interface NotificationLike {
	readonly data: unknown;
	close(): void;
}
export interface NotificationClickEventLike extends WaitUntilEvent {
	readonly notification: NotificationLike;
}
export interface WindowClientLike {
	readonly url: string;
	focus(): Promise<unknown>;
}
export interface PushDeps {
	origin: string;
	showNotification(title: string, options: NotificationOptions): Promise<void>;
	matchAll(): Promise<readonly WindowClientLike[]>; // window clients, incl. uncontrolled
	openWindow(url: string): Promise<unknown>;
}

function safeText(data: PushMessageDataLike): string | null {
	try {
		return data.text();
	} catch {
		return null;
	}
}

export function createPushHandlers(deps: PushDeps): {
	onPush(event: PushEventLike): void;
	onNotificationClick(event: NotificationClickEventLike): void;
} {
	return {
		onPush(event) {
			const p = parsePushPayload(event.data ? safeText(event.data) : null);
			const options: NotificationOptions = {
				body: p.body,
				icon: NOTIFICATION_ICON,
				data: { url: resolveTargetUrl(p.url, deps.origin) }
			};
			if (p.tag !== undefined) options.tag = p.tag;
			event.waitUntil(deps.showNotification(p.title, options));
		},
		onNotificationClick(event) {
			event.notification.close();
			const url = resolveTargetUrl(
				(event.notification.data as { url?: unknown } | null)?.url,
				deps.origin
			);
			event.waitUntil(
				(async () => {
					const hit = (await deps.matchAll()).find((c) => c.url === url);
					if (hit) {
						await hit.focus();
						return;
					}
					await deps.openWindow(url);
				})().catch(() => undefined)
			);
		}
	};
}
