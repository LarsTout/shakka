// @vitest-environment node
import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';
import { PUSH_SUBSCRIPTION_COLUMNS } from '../src/lib/types.js';

const sql = readFileSync(
	new URL('../../supabase/migrations/20261015150000_push_subscriptions.sql', import.meta.url),
	'utf8'
);

function columns(): string[] {
	const lines = sql.split('\n');
	const start = lines.findIndex((l) => l.startsWith('create table public.push_subscriptions ('));
	expect(start).toBeGreaterThanOrEqual(0);
	const out: string[] = [];
	for (const line of lines.slice(start + 1)) {
		if (line.startsWith(');')) break;
		const m = /^ {2}([a-z_][a-z0-9_]*) /.exec(line);
		if (m) out.push(m[1]!);
	}
	return out;
}

describe('push_subscriptions migration (WP-17)', () => {
	it('has every column the PWA reads', () => {
		const cols = columns();
		for (const c of PUSH_SUBSCRIPTION_COLUMNS) expect(cols).toContain(c);
	});
	it('grants insert on the columns the PWA writes', () => {
		const m = /grant insert \(([^)]*)\) on table public\.push_subscriptions to authenticated/.exec(sql);
		expect(m).not.toBeNull();
		const granted = m![1]!.split(',').map((s) => s.trim());
		for (const k of ['endpoint', 'p256dh', 'auth']) expect(granted).toContain(k);
	});
	it('defaults user_id to auth.uid()', () => {
		expect(sql).toMatch(/user_id uuid not null default auth\.uid\(\)/);
	});
});
