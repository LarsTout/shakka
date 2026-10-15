// @vitest-environment node
import { describe, expect, it } from 'vitest';
import { parseNewSessionParams } from '../src/lib/go.js';
import {
	PREFILL_NOTICES,
	SESSION_FORM_MESSAGES as M,
	emptySessionForm,
	isValidOrganizerName,
	parseSessionForm,
	prefillSessionForm,
	sessionDateBounds,
	sessionToForm,
	withKnownSpot,
	type SessionFormContext
} from '../src/lib/session-form.js';
import {
	GO_URL_DST_BEFORE,
	GO_URL_DST_DAY,
	GO_URL_DST_NIGHT,
	SESSION_ROW,
	TIKKIE_URL,
	validForm
} from './fixtures/session-data.js';
import { GO_URL_SUMMER, GO_URL_WINTER } from './fixtures/spot-data.js';

const NOW = new Date('2026-07-15T12:30:00Z');
const ctx = (over: Partial<SessionFormContext> = {}): SessionFormContext => ({
	now: NOW,
	spotIds: new Set(['test-strand', 'test-meer']),
	preferred: null,
	...over
});
const pre = (url: string, now = NOW, name = '') =>
	prefillSessionForm(parseNewSessionParams(new URL(url)), name, now);
const errorsOf = (f = validForm(), c = ctx()) => {
	const r = parseSessionForm(f, c);
	return r.ok ? null : r.errors;
};

describe('prefill (AC-2)', () => {
	it('E11 summer', () => {
		const p = pre(GO_URL_SUMMER);
		expect(p.form).toMatchObject({
			spot_id: 'test-strand',
			date: '2026-07-18',
			start_time: '14:00',
			end_time: '18:00'
		});
		expect(p.notices).toEqual([]);
	});
	it('winter', () => {
		const p = pre(GO_URL_WINTER, new Date('2026-11-01T00:00:00Z'));
		expect(p.form).toMatchObject({ date: '2026-11-07', start_time: '12:00', end_time: '15:00' });
	});
	it('E12 around the switch', () => {
		const now = new Date('2026-10-01T00:00:00Z');
		expect(pre(GO_URL_DST_DAY, now).form).toMatchObject({ start_time: '11:00', end_time: '15:00' });
		expect(pre(GO_URL_DST_BEFORE, now).form).toMatchObject({ start_time: '12:00', end_time: '16:00' });
	});
	it('E13 over the switch round-trips exactly', () => {
		const now = new Date('2026-10-01T00:00:00Z');
		const p = pre(GO_URL_DST_NIGHT, now, 'Lars');
		expect(p.form).toMatchObject({ date: '2026-10-25', start_time: '02:00', end_time: '03:00' });
		const r = parseSessionForm(p.form, ctx({ now, preferred: p.preferred }));
		expect(r.ok && r.value.starts_at).toBe('2026-10-25T00:00:00.000Z');
		expect(r.ok && r.value.ends_at).toBe('2026-10-25T02:00:00.000Z');
	});
	it('E14 across local midnight', () => {
		const p = prefillSessionForm(
			{ spot: 'test-strand', start: '2026-07-18T20:00:00.000Z', end: '2026-07-19T00:00:00.000Z' },
			'',
			NOW
		);
		expect(p.form.end_time).toBe('');
		expect(p.notices).toEqual([PREFILL_NOTICES.otherDay]);
		const p2 = prefillSessionForm(
			{ spot: 'test-strand', start: '2026-07-18T20:00:00.000Z', end: '2026-07-18T22:00:00.000Z' },
			'',
			NOW
		);
		expect(p2.form.end_time).toBe('');
	});
	it('E15 longer than 16 hours is truncated', () => {
		const p = prefillSessionForm(
			{ spot: 'test-strand', start: '2026-07-18T04:00:00.000Z', end: '2026-07-18T22:00:00.000Z' },
			'',
			NOW
		);
		expect(p.notices).toContain(PREFILL_NOTICES.truncated);
		expect(p.form.start_time).toBe('06:00');
		expect(p.form.end_time).toBe('22:00');
	});
	it('E16 window in the past', () => {
		const p = pre(GO_URL_SUMMER, new Date('2026-07-20T00:00:00Z'));
		expect(p.notices).toContain(PREFILL_NOTICES.past);
		expect(p.form.start_time).toBe('14:00');
	});
	it('E17 unknown spot is cleared', () => {
		const p = withKnownSpot(pre(GO_URL_SUMMER), [{ id: 'test-meer' }]);
		expect(p.form.spot_id).toBe('');
		expect(p.notices).toContain(PREFILL_NOTICES.spotUnknown);
		expect(withKnownSpot(pre(GO_URL_SUMMER), [{ id: 'test-strand' }]).form.spot_id).toBe('test-strand');
	});
	it('E18 no params', () => {
		const p = prefillSessionForm({ spot: null, start: null, end: null }, 'Lars', NOW);
		expect(p.form).toEqual({ ...emptySessionForm('Lars', NOW), date: '2026-07-15' });
		expect(p.form.organizer_name).toBe('Lars');
		expect(p.form.spot_id).toBe('');
		expect(p.preferred).toBeNull();
	});
});

describe('parseSessionForm (AC-2, AC-4)', () => {
	it('valid form gives exactly the eight keys', () => {
		const r = parseSessionForm(validForm(), ctx());
		expect(r).toEqual({
			ok: true,
			value: {
				spot_id: 'test-strand',
				organizer_name: 'Lars',
				starts_at: '2026-07-18T12:00:00.000Z',
				ends_at: '2026-07-18T16:00:00.000Z',
				note: null,
				seats_free: null,
				departure_point: null,
				tikkie_url: null
			}
		});
	});
	it('unknown spot', () => {
		expect(errorsOf(validForm({ spot_id: 'x' }))).toEqual({ spot_id: M.spot });
		expect(errorsOf(validForm({ spot_id: '' }))).toEqual({ spot_id: M.spot });
	});
	it('E19 nonexistent time', () => {
		const e = errorsOf(
			validForm({ date: '2027-03-28', start_time: '02:30', end_time: '05:00' }),
			ctx()
		);
		expect(e).toEqual({ start_time: M.timeNonexistent });
	});
	it('E20 overlap takes the first moment', () => {
		const r = parseSessionForm(
			validForm({ date: '2026-10-25', start_time: '02:30', end_time: '05:00' }),
			ctx()
		);
		expect(r.ok && r.value.starts_at).toBe('2026-10-25T00:30:00.000Z');
	});
	it('E21 end before or equal start', () => {
		expect(errorsOf(validForm({ end_time: '14:00' }))).toEqual({ end_time: M.endBeforeStart });
		expect(errorsOf(validForm({ end_time: '13:00' }))).toEqual({ end_time: M.endBeforeStart });
	});
	it('E22 16 hours ok, 17 too long', () => {
		expect(errorsOf(validForm({ start_time: '06:00', end_time: '22:00' }))).toBeNull();
		expect(errorsOf(validForm({ start_time: '06:00', end_time: '23:00' }))).toEqual({
			end_time: M.tooLong
		});
	});
	it('E23 end in the past, start in the past is fine', () => {
		const today = validForm({ date: '2026-07-15', start_time: '10:00', end_time: '12:00' });
		expect(errorsOf(today)).toEqual({ end_time: M.inPast });
		const running = validForm({ date: '2026-07-15', start_time: '10:00', end_time: '16:00' });
		expect(errorsOf(running)).toBeNull();
	});
	it('invalid time format', () => {
		expect(errorsOf(validForm({ start_time: '' }))).toEqual({ start_time: M.time });
		expect(errorsOf(validForm({ end_time: '24:00' }))).toEqual({ end_time: M.time });
	});
	it('E24 organizer name', () => {
		const r = parseSessionForm(validForm({ organizer_name: '  Lars  ' }), ctx());
		expect(r.ok && r.value.organizer_name).toBe('Lars');
		for (const bad of ['', '   ', 'a'.repeat(31), 'Li\nne'])
			expect(errorsOf(validForm({ organizer_name: bad }))).toEqual({ organizer_name: M.organizerName });
		expect(errorsOf(validForm({ organizer_name: '😀'.repeat(30) }))).toBeNull();
	});
	it('E25 seats', () => {
		for (const bad of ['9', '-1', '2,5', 'abc'])
			expect(errorsOf(validForm({ seats_free: bad }))).toEqual({ seats_free: M.seatsFree });
		for (const [v, n] of [['0', 0], ['8', 8], ['', null]] as const) {
			const r = parseSessionForm(validForm({ seats_free: v }), ctx());
			expect(r.ok && r.value.seats_free).toBe(n);
		}
	});
	it('E26 Tikkie', () => {
		for (const bad of [
			'http://tikkie.me/pay/x',
			'HTTPS://tikkie.me/pay/x',
			'https://tikkie.me/pay/a b',
			'https://tikkie.me/',
			'https://example.org/pay/x',
			'https://tikkie.me.evil.example/pay/x',
			'https://tikkie.me@evil.example/x',
			'https://www.tikkie.me/pay/x',
			'https://tikkie.me:8443/pay/x',
			'https://tikkie.me/pay/' + 'a'.repeat(179)
		])
			expect(errorsOf(validForm({ tikkie_url: bad })), bad).toEqual({ tikkie_url: M.tikkieUrl });
		for (const ok of [TIKKIE_URL, 'https://tikkie.me/pay/' + 'a'.repeat(178)]) {
			const r = parseSessionForm(validForm({ tikkie_url: ok }), ctx());
			expect(r.ok && r.value.tikkie_url).toBe(ok);
		}
	});
	it('E27 note and departure point limits', () => {
		expect(errorsOf(validForm({ note: 'a'.repeat(281) }))).toEqual({ note: M.note });
		expect(errorsOf(validForm({ note: 'a\nb'.repeat(90) }))).toBeNull();
		expect(errorsOf(validForm({ departure_point: 'a'.repeat(81) }))).toEqual({
			departure_point: M.departurePoint
		});
		const r = parseSessionForm(validForm({ note: ' hoi ', departure_point: ' Utrecht ' }), ctx());
		expect(r.ok && [r.value.note, r.value.departure_point]).toEqual(['hoi', 'Utrecht']);
	});
	it('E49 date range', () => {
		const t = { start_time: '14:00', end_time: '18:00' };
		expect(errorsOf(validForm({ date: '2026-07-14', ...t }))).toEqual({ date: M.dateRange });
		expect(errorsOf(validForm({ date: '2027-07-16', ...t }))).toEqual({ date: M.dateRange });
		expect(errorsOf(validForm({ date: '2026-07-15', start_time: '14:00', end_time: '18:00' }))).toBeNull();
		expect(errorsOf(validForm({ date: '2027-07-15', ...t }))).toBeNull();
		expect(errorsOf(validForm({ date: '1970-06-01', start_time: '02:30', end_time: '04:00' }))).toEqual({
			date: M.dateRange
		});
		expect(errorsOf(validForm({ date: '2026-02-30' }))).toEqual({ date: M.date });
		expect(errorsOf(validForm({ date: '' }))).toEqual({ date: M.date });
		expect(sessionDateBounds(NOW)).toEqual({ min: '2026-07-15', max: '2027-07-15' });
	});
	it('collects several errors at once', () => {
		const e = errorsOf(validForm({ spot_id: '', organizer_name: '', seats_free: 'x' }))!;
		expect(Object.keys(e).sort()).toEqual(['organizer_name', 'seats_free', 'spot_id']);
	});
});

describe('isValidOrganizerName (N-3)', () => {
	it('accepts a normal space inside', () => {
		expect(isValidOrganizerName('Jan Willem')).toBe(true);
	});
	it('rejects line and paragraph separators and controls', () => {
		expect(isValidOrganizerName('Jan\u2028Willem')).toBe(false);
		expect(isValidOrganizerName('Jan\u2029Willem')).toBe(false);
		expect(isValidOrganizerName('Jan\u0085Willem')).toBe(false);
		expect(isValidOrganizerName('Jan\tWillem')).toBe(false);
	});
	it('counts code points', () => {
		expect(isValidOrganizerName('😀'.repeat(30))).toBe(true);
		expect(isValidOrganizerName('😀'.repeat(31))).toBe(false);
	});
});

describe('sessionToForm (edit mode)', () => {
	it('round-trips to the same values', () => {
		const p = sessionToForm(SESSION_ROW);
		expect(p.form).toEqual({
			spot_id: 'test-strand',
			date: '2026-07-18',
			start_time: '14:00',
			end_time: '18:00',
			organizer_name: 'Lars',
			note: 'Neem een wetsuit mee',
			seats_free: '3',
			departure_point: 'Utrecht CS',
			tikkie_url: ''
		});
		const r = parseSessionForm(p.form, ctx({ preferred: p.preferred }));
		expect(r).toEqual({
			ok: true,
			value: {
				spot_id: 'test-strand',
				organizer_name: 'Lars',
				starts_at: '2026-07-18T12:00:00.000Z',
				ends_at: '2026-07-18T16:00:00.000Z',
				note: 'Neem een wetsuit mee',
				seats_free: 3,
				departure_point: 'Utrecht CS',
				tikkie_url: null
			}
		});
	});
	it('E50 keeps a non-Tikkie link visible but refuses to save it', () => {
		const p = sessionToForm({ ...SESSION_ROW, tikkie_url: 'https://example.org/pay' });
		expect(p.form.tikkie_url).toBe('https://example.org/pay');
		expect(errorsOf(p.form, ctx({ preferred: p.preferred }))).toEqual({ tikkie_url: M.tikkieUrl });
	});
});
