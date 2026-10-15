export interface RpcResponse {
	data: unknown;
	error: { code?: string; message?: string; details?: unknown; hint?: unknown } | null;
	status: number;
}
export interface FakeRpcCall {
	fn: string;
	args: Record<string, unknown> | undefined;
	options: unknown;
	argCount: number;
	signal: AbortSignal | null; // set by .abortSignal(); null when never called
}
/** What rpc() returns: thenable like the postgrest builder, plus abortSignal() that records the signal. */
export interface FakeRpcBuilder extends PromiseLike<RpcResponse> {
	abortSignal(signal: AbortSignal): FakeRpcBuilder;
}

export function createFakeRpc() {
	const calls: FakeRpcCall[] = [];
	const queues = new Map<string, RpcResponse[]>();
	const throwers = new Map<string, unknown[]>();

	function rpc(fn: string, args?: Record<string, unknown>, options?: unknown): FakeRpcBuilder {
		const call: FakeRpcCall = { fn, args, options, argCount: arguments.length, signal: null };
		calls.push(call);
		const thrown = throwers.get(fn);
		const toThrow = thrown && thrown.length > 0 ? { err: thrown.shift() } : null;
		const response: RpcResponse = queues.get(fn)?.shift() ?? { data: null, error: null, status: 200 };
		const builder: FakeRpcBuilder = {
			abortSignal(signal: AbortSignal) {
				call.signal = signal;
				return builder;
			},
			then(resolve, reject) {
				const p = toThrow ? Promise.reject(toThrow.err) : Promise.resolve(response);
				return p.then(resolve, reject);
			}
		};
		return builder;
	}

	return {
		rpc,
		calls,
		/** Queue responses per function; an empty queue answers { data: null, error: null, status: 200 }. */
		respond(fn: string, ...responses: RpcResponse[]): void {
			queues.set(fn, [...(queues.get(fn) ?? []), ...responses]);
		},
		/** The next call of fn rejects with err when awaited (simulates a thrown client). */
		throwNext(fn: string, err: unknown): void {
			throwers.set(fn, [...(throwers.get(fn) ?? []), err]);
		},
		reset(): void {
			calls.length = 0;
			queues.clear();
			throwers.clear();
		}
	};
}

/** Client for vi.mock('#lib/supabase.js'): { rpc, from } plus an `auth` getter that only counts accesses. */
export function clientWithAuthTrap(parts: { rpc: unknown; from?: unknown }): {
	client: object;
	authAccesses: () => number;
} {
	let accesses = 0;
	const client = {
		rpc: parts.rpc,
		from: parts.from,
		get auth() {
			accesses += 1;
			return undefined;
		}
	};
	return { client, authAccesses: () => accesses };
}
