/** Minimal in-memory CacheStorage for service worker tests. Casts are allowed: only the used subset exists. */
export class FakeCache {
	entries = new Map<string, Response>();
	putCalls = 0;

	async addAll(paths: readonly string[]): Promise<void> {
		for (const path of paths) this.entries.set(path, new Response('cached:' + path));
	}
	async match(request: string | Request): Promise<Response | undefined> {
		const key = typeof request === 'string' ? request : new URL(request.url).pathname;
		return this.entries.get(key)?.clone();
	}
	async put(request: string | Request, response: Response): Promise<void> {
		this.putCalls += 1;
		const key = typeof request === 'string' ? request : new URL(request.url).pathname;
		this.entries.set(key, response);
	}
	async keys(): Promise<string[]> {
		return [...this.entries.keys()];
	}
}

export class FakeCacheStorage {
	caches = new Map<string, FakeCache>();

	async open(name: string): Promise<Cache> {
		let cache = this.caches.get(name);
		if (!cache) {
			cache = new FakeCache();
			this.caches.set(name, cache);
		}
		return cache as unknown as Cache;
	}
	async keys(): Promise<string[]> {
		return [...this.caches.keys()];
	}
	async delete(name: string): Promise<boolean> {
		return this.caches.delete(name);
	}
	async has(name: string): Promise<boolean> {
		return this.caches.has(name);
	}
	get totalPutCalls(): number {
		return [...this.caches.values()].reduce((n, c) => n + c.putCalls, 0);
	}
}
