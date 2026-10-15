import { self } from '$app/service-worker';
import { version } from '$app/env';
import { immutable, assets } from '$app/manifest';
import { createPushHandlers } from '#lib/sw/push.js';
import { CACHE_PREFIX, SHELL_PATH, createShellHandlers, precacheList } from '#lib/sw/shell.js';

// Manifest paths are relative to the base path; make them absolute pathnames within the SW scope.
// ($app/paths resolve() only accepts typed route ids, not build output paths.)
const toPathname = (path: string) => new URL(path, self.registration.scope).pathname;

const precache = precacheList(
	[...immutable.map((a) => toPathname(a.path)), ...assets.map((a) => toPathname(a.path))],
	SHELL_PATH
);

const handlers = createShellHandlers({
	cacheName: `${CACHE_PREFIX}${version}`,
	precache,
	shellPath: SHELL_PATH,
	origin: self.location.origin,
	caches: self.caches,
	fetch: (request) => self.fetch(request)
});

self.addEventListener('install', handlers.onInstall);
self.addEventListener('activate', handlers.onActivate);
self.addEventListener('fetch', handlers.onFetch);

const push = createPushHandlers({
	origin: self.location.origin,
	showNotification: (title, options) => self.registration.showNotification(title, options),
	matchAll: () => self.clients.matchAll({ type: 'window', includeUncontrolled: true }),
	openWindow: (url) => self.clients.openWindow(url)
});

self.addEventListener('push', push.onPush);
self.addEventListener('notificationclick', push.onNotificationClick);
