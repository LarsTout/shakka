// @vitest-environment node
import { readFileSync, readdirSync } from 'node:fs';
import { describe, expect, it } from 'vitest';
import {
	ALERT_STATE_RETENTION_HOURS,
	FORECAST_RETENTION_HOURS,
	RETURN_TO_TTL_MINUTES
} from '../src/lib/privacy.js';
import { SESSION_RETENTION_DAYS } from '../src/lib/rsvp-types.js';

const jobs = (f: string) => readFileSync(new URL(`../../ingest/src/shakka/jobs/${f}`, import.meta.url), 'utf8');

function retention(file: string, name: string): { unit: string; value: number } {
	// The anchor stops RETENTION from matching inside TIDE_RETENTION.
	const re = new RegExp(String.raw`(?:^|\n)` + name + String.raw`: Final = timedelta\((hours|days)=(\d+)\)`);
	const m = re.exec(jobs(file));
	if (!m) throw new Error(`${name} not found in ${file}`);
	return { unit: m[1]!, value: Number(m[2]) };
}

describe('retention periods in the text match the implementation', () => {
	it.each([
		['forecast.py', 'RETENTION'],
		['marine.py', 'RETENTION'],
		['tides.py', 'TIDE_RETENTION'],
		['evaluate.py', 'EVALUATION_RETENTION']
	])('%s %s is FORECAST_RETENTION_HOURS', (file, name) => {
		expect(retention(file, name)).toEqual({ unit: 'hours', value: FORECAST_RETENTION_HOURS });
	});
	it('alerts.py ALERT_STATE_RETENTION is ALERT_STATE_RETENTION_HOURS', () => {
		expect(retention('alerts.py', 'ALERT_STATE_RETENTION')).toEqual({
			unit: 'hours',
			value: ALERT_STATE_RETENTION_HOURS
		});
	});
	it('sessions.py SESSION_RETENTION is SESSION_RETENTION_DAYS', () => {
		expect(retention('sessions.py', 'SESSION_RETENTION')).toEqual({
			unit: 'days',
			value: SESSION_RETENTION_DAYS
		});
	});
	it('the sessions migration purges after SESSION_RETENTION_DAYS days', () => {
		const dir = new URL('../../supabase/migrations/', import.meta.url);
		const sql = readdirSync(dir)
			.filter((f) => f.endsWith('sessions.sql'))
			.map((f) => readFileSync(new URL(f, dir), 'utf8'))
			.join('\n');
		expect(sql).toContain(`interval '${SESSION_RETENTION_DAYS} days'`);
	});
	it('shakka:return_to is used for 60 minutes', () => {
		expect(RETURN_TO_TTL_MINUTES).toBe(60);
	});
});
