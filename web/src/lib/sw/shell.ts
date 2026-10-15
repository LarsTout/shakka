export const CACHE_PREFIX = 'shakka-shell-';
export const SHELL_PATH = '/';

export interface WaitUntilEvent {
	waitUntil(promise: Promise<unknown>): void;
}
export interface FetchLikeEvent {
	readonly request: Request;
	respondWith(response: Promise<Response>): void;
}
export type RequestKind = 'navigate' | 'precached' | 'passthrough';

/** Host configuration files in static/ that Cloudflare Pages never serves as files. A request for them gets
 *  the SPA fallback (index.html, 200), so precaching them would store a useless copy of index.html. */
export const PRECACHE_EXCLUDED_PATHS: readonly string[] = ['/_headers', '/_redirects'];

/** Unique list of absolute paths to precache, without PRECACHE_EXCLUDED_PATHS, always including shellPath.
 *  Order: input order, shell last if new. */
export function precacheList(paths: readonly string[], shellPath: string): string[] {
	const list = [...new Set(paths)].filter((p) => !PRECACHE_EXCLUDED_PATHS.includes(p));
	if (!list.includes(shellPath)) list.push(shellPath);
	return list;
}

/** Decides how the service worker treats a request. Order of rules:
 *  1. method !== 'GET'                      -> 'passthrough'
 *  2. new URL(url).origin !== origin        -> 'passthrough' (Supabase, MapTiler, ...: never cached)
 *  3. mode === 'navigate'                   -> 'navigate'
 *  4. precached.has(new URL(url).pathname)  -> 'precached'
 *  5. otherwise                             -> 'passthrough' */
export function classifyRequest(
	request: Pick<Request, 'url' | 'method' | 'mode'>,
	origin: string,
	precached: ReadonlySet<string>
): RequestKind {
	if (request.method !== 'GET') return 'passthrough';
	const url = new URL(request.url);
	if (url.origin !== origin) return 'passthrough';
	if (request.mode === 'navigate') return 'navigate';
	if (precached.has(url.pathname)) return 'precached';
	return 'passthrough';
}

export interface ShellDeps {
	cacheName: string; // `${CACHE_PREFIX}${version}`
	precache: readonly string[]; // result of precacheList
	shellPath: string; // SHELL_PATH
	origin: string; // self.location.origin
	caches: Pick<CacheStorage, 'open' | 'keys' | 'delete'>;
	fetch: (request: Request) => Promise<Response>;
}

export function createShellHandlers(deps: ShellDeps): {
	onInstall(event: WaitUntilEvent): void;
	onActivate(event: WaitUntilEvent): void;
	onFetch(event: FetchLikeEvent): void;
} {
	const precached = new Set(deps.precache);

	async function fromCache(key: string): Promise<Response | undefined> {
		const cache = await deps.caches.open(deps.cacheName);
		return cache.match(key);
	}

	return {
		onInstall(event) {
			event.waitUntil(
				deps.caches.open(deps.cacheName).then((cache) => cache.addAll([...deps.precache]))
			);
		},
		onActivate(event) {
			event.waitUntil(
				deps.caches.keys().then((names) =>
					Promise.all(
						names
							.filter((name) => name.startsWith(CACHE_PREFIX) && name !== deps.cacheName)
							.map((name) => deps.caches.delete(name))
					)
				)
			);
		},
		onFetch(event) {
			const { request } = event;
			const kind = classifyRequest(request, deps.origin, precached);
			if (kind === 'passthrough') return;
			if (kind === 'precached') {
				event.respondWith(
					fromCache(new URL(request.url).pathname).then(
						(hit) => hit ?? deps.fetch(request)
					)
				);
				return;
			}
			event.respondWith(
				deps.fetch(request).catch(async (error: unknown) => {
					const shell = await fromCache(deps.shellPath);
					if (shell) return shell;
					throw error;
				})
			);
		}
	};
}
