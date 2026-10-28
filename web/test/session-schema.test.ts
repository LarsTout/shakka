// @vitest-environment node
import { readdirSync, readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';
import {
	DEPARTURE_POINT_MAX,
	NOTE_MAX,
	ORGANIZER_NAME_MAX,
	SEATS_FREE_RANGE,
	SESSION_COLUMNS,
	SESSION_EDITABLE_COLUMNS,
	SESSION_MAX_HOURS,
	SESSION_SLUG_RE,
	TIKKIE_URL_MAX
} from '../src/lib/session-model.js';

const MIGRATIONS = new URL('../../supabase/migrations/', import.meta.url);
const SESSIONS_FILE = '20261015200000_sessions.sql';
const MODERATION_FILE = '20261028090000_organizer_moderation.sql';
const SQL = readFileSync(new URL(SESSIONS_FILE, MIGRATIONS), 'utf8');

function columns(table: string): string[] {
	const lines = SQL.split('\n');
	const start = lines.findIndex((l) => l.startsWith(`create table public.${table} (`));
	expect(start).toBeGreaterThanOrEqual(0);
	const out: string[] = [];
	for (const line of lines.slice(start + 1)) {
		if (line.startsWith(');')) break;
		const m = /^ {2}([a-z_][a-z0-9_]*) /.exec(line);
		if (m && !['constraint', 'primary', 'foreign', 'unique', 'check'].includes(m[1]!)) {
			out.push(m[1]!);
		}
	}
	return out;
}

function grantList(re: RegExp): string[] {
	const m = re.exec(SQL);
	expect(m).not.toBeNull();
	return m![1]!.split(',').map((s) => s.trim());
}

function after(name: string): string {
	const i = SQL.indexOf(name);
	expect(i).toBeGreaterThanOrEqual(0);
	return SQL.slice(i, i + 300);
}

describe('sessions schema drift (AC-4)', () => {
	const hint = 'update session-model.ts and this test';
	it(`SESSION_COLUMNS equals public.sessions without internal columns (${hint})`, () => {
		const cols = columns('sessions').filter(
			(c) => c !== 'organizer_id' && c !== 'recent_rsvp_creates'
		);
		expect([...SESSION_COLUMNS]).toEqual(cols);
	});
	it('SESSION_EDITABLE_COLUMNS equals the insert and update grants', () => {
		const ins = grantList(/grant insert \(([^)]*)\)\s+on table public\.sessions/).filter(
			(c) => c !== 'organizer_id'
		);
		const upd = grantList(/grant update \(([^)]*)\)\s+on table public\.sessions/).filter(
			(c) => c !== 'cancelled_at'
		);
		expect(new Set(ins)).toEqual(new Set(SESSION_EDITABLE_COLUMNS));
		expect(new Set(upd)).toEqual(new Set(SESSION_EDITABLE_COLUMNS));
	});
	it('limits equal the CHECK constraints', () => {
		expect(after('sessions_organizer_name_valid')).toContain(`between 1 and ${ORGANIZER_NAME_MAX}`);
		expect(after('sessions_note_length')).toContain(`<= ${NOTE_MAX}`);
		expect(after('sessions_seats_free_range')).toContain(
			`between ${SEATS_FREE_RANGE[0]} and ${SEATS_FREE_RANGE[1]}`
		);
		expect(after('sessions_departure_point_length')).toContain(`<= ${DEPARTURE_POINT_MAX}`);
		const t = after('sessions_tikkie_url_https');
		expect(t).toContain("'^https://");
		expect(t).toContain(`<= ${TIKKIE_URL_MAX}`);
		expect(after('sessions_window_max_16h')).toContain(`interval '${SESSION_MAX_HOURS} hours'`);
		expect(after('sessions_slug_format')).toContain('{10,64}');
		expect(SESSION_SLUG_RE.source).toContain('{10,64}');
	});
});

describe('later migrations on public.sessions (WP-25)', () => {
	it('later migrations change public.sessions only by adding rsvps_closed_at', () => {
		const found: string[] = [];
		const alter = /alter\s+table\s+(?:if\s+exists\s+)?(?:only\s+)?public\.sessions\b([^;]*);/gi;
		const clause = /\b(add|drop|rename)\s+(?:column\s+)?(?:if\s+(?:not\s+)?exists\s+)?(\w+)/gi;
		const later = readdirSync(MIGRATIONS)
			.filter((f) => f.endsWith('.sql') && f > SESSIONS_FILE)
			.sort();
		for (const file of later) {
			const t = readFileSync(new URL(file, MIGRATIONS), 'utf8');
			for (const a of t.matchAll(alter)) {
				// Match per comma-separated clause; a comma inside parentheses (types, defaults) never starts one.
				const clauses = a[1]!.split(/,(?![^(]*\))/);
				for (const c of clauses) {
					for (const m of c.matchAll(clause)) {
						// "add constraint", "add primary key" etc. are not columns: report them too.
						found.push(`${file}:${m[1]!.toLowerCase()}:${m[2]}`);
					}
				}
			}
		}
		expect(found).toEqual([`${MODERATION_FILE}:add:rsvps_closed_at`]);
	});
	it('the WP-25 migration grants update on rsvps_closed_at and SESSION_COLUMNS leaves it out', () => {
		const t = readFileSync(new URL(MODERATION_FILE, MIGRATIONS), 'utf8');
		expect(t).toContain('grant update (rsvps_closed_at) on table public.sessions to authenticated');
		expect(SESSION_COLUMNS as readonly string[]).not.toContain('rsvps_closed_at');
	});
});
