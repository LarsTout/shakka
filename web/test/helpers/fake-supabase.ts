export type Op = [name: string, ...args: unknown[]];
export interface Call {
	table: string;
	ops: Op[];
}
export interface Response {
	data: unknown;
	error: { code?: string; message?: string } | null;
}

interface Builder {
	[method: string]: unknown;
}

export function createFakeSupabase() {
	const calls: Call[] = [];
	const queues = new Map<string, Response[]>();

	function from(table: string): Builder {
		const call: Call = { table, ops: [] };
		calls.push(call);
		const builder: Builder = {};
		for (const name of ['select', 'eq', 'gte', 'lt', 'not', 'order', 'range', 'maybeSingle']) {
			builder[name] = (...args: unknown[]) => {
				call.ops.push([name, ...args]);
				return builder;
			};
		}
		builder.then = (
			resolve: (r: Response) => unknown,
			reject?: (e: unknown) => unknown
		): Promise<unknown> => {
			const next = queues.get(table)?.shift() ?? { data: [], error: null };
			return Promise.resolve(next).then(resolve, reject);
		};
		return builder;
	}

	return {
		client: { from },
		calls,
		/** Queue responses per table; an empty queue answers { data: [], error: null }. */
		respond(table: string, ...responses: Response[]): void {
			queues.set(table, [...(queues.get(table) ?? []), ...responses]);
		},
		reset(): void {
			calls.length = 0;
			queues.clear();
		}
	};
}
