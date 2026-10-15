import { describe, expect, it } from 'vitest';
import { MAX_RSVPS } from '../src/lib/rsvp-types.js';
import {
	RPC_ERROR_CODES,
	RSVP_FORM_MESSAGES,
	RSVP_MESSAGES,
	RsvpError,
	carpoolView,
	emptyRsvpForm,
	isSessionClosed,
	isValidSessionSlug,
	isolateText,
	optionalText,
	parseCreateResult,
	parsePublicSession,
	parseRsvpForm,
	parseStoredRsvp,
	rideLabel,
	rsvpErrorKind,
	rsvpFormFromRsvp,
	rsvpStorageKey,
	seatsText,
	sessionWindowText,
	tikkieLink
} from '../src/lib/session-view.js';
import {
	EVA_ID,
	NEW_ID,
	RSVP_EVA,
	RSVP_NOOR,
	RSVP_SANNE,
	RSVP_TOM,
	SESSION_INFO,
	SESSION_JSON,
	SLUG,
	TOKEN,
	TOM_ID
} from './fixtures/public-session.js';

const FIXTURES = [RSVP_EVA, RSVP_SANNE, RSVP_NOOR, RSVP_TOM];
const byId = new Map(FIXTURES.map((r) => [r.id, r]));

describe('slug and key', () => {
	it('isValidSessionSlug', () => {
		for (const ok of [SLUG, 'a'.repeat(10), 'a'.repeat(64)]) expect(isValidSessionSlug(ok)).toBe(true);
		for (const bad of ['short', 'a'.repeat(65), 'bad slug!', 'a/bcdefghijk', '']) {
			expect(isValidSessionSlug(bad)).toBe(false);
		}
	});
	it('rsvpStorageKey', () => {
		expect(rsvpStorageKey(SLUG)).toBe('shakka:rsvp:' + SLUG);
	});
});

describe('error kinds', () => {
	it('maps the five PT400 codes', () => {
		for (const k of RPC_ERROR_CODES) expect(rsvpErrorKind({ code: 'PT400', message: k })).toBe(k);
	});
	it('everything else is unknown or network', () => {
		expect(rsvpErrorKind({ code: 'PT400', message: 'boom' })).toBe('unknown');
		expect(rsvpErrorKind({ code: '42501', message: 'x' })).toBe('unknown');
		expect(rsvpErrorKind({ code: 'PT400', message: 'rate_limited' }, 0)).toBe('network');
		expect(rsvpErrorKind(null)).toBe('unknown');
		expect(rsvpErrorKind('x')).toBe('unknown');
		expect(rsvpErrorKind(undefined)).toBe('unknown');
	});
	it('RsvpError message never has server text', () => {
		expect(new RsvpError('session_full', 'createRsvp').message).toBe('createRsvp failed: session_full');
	});
	it('(AC-4) messages are distinct, Dutch, free of codes', () => {
		const texts = Object.values(RSVP_MESSAGES);
		expect(new Set(texts).size).toBe(texts.length);
		for (const t of texts) {
			expect(t).not.toBe('');
			expect(t).not.toContain('_');
		}
		expect(RSVP_MESSAGES.session_full).toContain(String(MAX_RSVPS));
		expect(RSVP_MESSAGES.session_full).toContain('organisator');
		expect(RSVP_MESSAGES.rate_limited).toBe(
			'Er melden zich nu veel mensen tegelijk aan. Probeer het over een paar minuten opnieuw.'
		);
		expect(RSVP_MESSAGES.invalid_token).toBe(
			'Je aanmelding is niet meer gevonden. Meld je opnieuw aan als je nog mee wilt.'
		);
	});
});

describe('parsers', () => {
	it('parsePublicSession round-trips the RPC shape', () => {
		expect(parsePublicSession(SESSION_JSON)).toEqual(SESSION_JSON);
	});
	it('drops unknown keys', () => {
		const dirty = {
			session: { ...SESSION_INFO, edit_token_hash: 'x' },
			rsvps: [{ ...RSVP_EVA, email: 'a@b.c' }]
		};
		const out = parsePublicSession(dirty);
		expect(out.session).not.toHaveProperty('edit_token_hash');
		expect(out.rsvps[0]).not.toHaveProperty('email');
	});
	it('throws RsvpError unknown on malformed input', () => {
		const bad: unknown[] = [
			{ rsvps: [] },
			{ session: SESSION_INFO, rsvps: {} },
			{ session: SESSION_INFO, rsvps: [{ ...RSVP_EVA, ride: 'walk' }] },
			{ session: { ...SESSION_INFO, seats_free: 1.5 }, rsvps: [] },
			{ session: { ...SESSION_INFO, cancelled: 'false' }, rsvps: [] },
			{ session: { ...SESSION_INFO, starts_at: 'gisteren' }, rsvps: [] },
			{ session: { ...SESSION_INFO, ends_at: SESSION_INFO.starts_at }, rsvps: [] }
		];
		for (const b of bad) {
			try {
				parsePublicSession(b);
				expect.unreachable();
			} catch (e) {
				expect(e).toBeInstanceOf(RsvpError);
				expect((e as RsvpError).kind).toBe('unknown');
			}
		}
	});
	it('parseCreateResult', () => {
		const v = { rsvp_id: NEW_ID, edit_token: TOKEN };
		expect(parseCreateResult(v)).toEqual(v);
		expect(() => parseCreateResult({ ...v, edit_token: 'T'.repeat(42) })).toThrow(RsvpError);
		expect(() => parseCreateResult({ ...v, edit_token: '+'.repeat(43) })).toThrow(RsvpError);
		expect(() => parseCreateResult({ ...v, rsvp_id: 'x' })).toThrow(RsvpError);
	});
	it('parseStoredRsvp', () => {
		const v = { rsvp_id: NEW_ID, edit_token: TOKEN };
		expect(parseStoredRsvp(v)).toEqual(v);
		for (const bad of [null, [], {}, { ...v, edit_token: 'x' }]) expect(parseStoredRsvp(bad)).toBeNull();
	});
});

describe('closed and window', () => {
	const ends = SESSION_INFO.ends_at;
	it('isSessionClosed', () => {
		expect(isSessionClosed({ cancelled: true, ends_at: ends }, new Date('2026-07-18T09:00:00Z'))).toBe(true);
		expect(isSessionClosed({ cancelled: false, ends_at: ends }, new Date(ends))).toBe(true);
		expect(isSessionClosed({ cancelled: false, ends_at: ends }, new Date(Date.parse(ends) - 1))).toBe(false);
		expect(isSessionClosed({ cancelled: false, ends_at: ends }, new Date('2026-07-18T13:00:00Z'))).toBe(false);
	});
	it('sessionWindowText (A21)', () => {
		expect(sessionWindowText(SESSION_INFO.starts_at, SESSION_INFO.ends_at)).toBe('za 18 jul 14:00–18:00');
		expect(sessionWindowText('2026-07-18T20:00:00Z', '2026-07-19T00:00:00Z')).toBe(
			'za 18 jul 22:00 – zo 19 jul 02:00'
		);
		expect(sessionWindowText('2026-07-18T20:00:00Z', '2026-07-19T02:00:00Z')).toBe(
			'za 18 jul 22:00 – zo 19 jul 04:00'
		);
		expect(sessionWindowText('2026-07-18T20:00:00Z', '2026-07-18T22:00:00Z')).toBe('za 18 jul 22:00–00:00');
		expect(sessionWindowText('2026-10-25T00:00:00Z', '2026-10-25T02:00:00Z')).toBe('zo 25 okt 02:00–03:00');
		expect(sessionWindowText('2026-10-25T00:00:00Z', '2026-10-25T03:00:00Z')).toBe('zo 25 okt 02:00–04:00');
		expect(() => sessionWindowText('2026-07-18T20:00:00Z', '2026-07-18T20:00:00Z')).toThrow(RangeError);
	});
});

describe('labels and carpool', () => {
	it('seatsText', () => {
		expect(seatsText(null)).toBe('aantal plekken onbekend');
		expect(seatsText(0)).toBe('geen plek meer');
		expect(seatsText(1)).toBe('1 plek');
		expect(seatsText(3)).toBe('3 plekken');
	});
	it('rideLabel', () => {
		expect(rideLabel(RSVP_EVA, byId)).toEqual({ label: 'Biedt een lift aan (2 plekken)', name: null });
		expect(rideLabel(RSVP_SANNE, byId)).toEqual({ label: 'Rijdt mee met', name: 'Eva' });
		expect(rideLabel(RSVP_NOOR, byId)).toEqual({ label: 'Zoekt een lift', name: null });
		expect(rideLabel(RSVP_TOM, byId)).toEqual({ label: 'Rijdt zelf', name: null });
		expect(rideLabel({ ...RSVP_SANNE, rides_with: TOM_ID }, byId).label).toBe('Zoekt een lift');
		expect(rideLabel({ ...RSVP_EVA, seats_offered: null }, byId).label).toBe('Biedt een lift aan');
	});
	it('carpoolView', () => {
		const v = carpoolView(SESSION_INFO, FIXTURES);
		expect(v.organizerSeats).toBe(3);
		expect(v.departurePoint).toBe('Utrecht CS');
		expect(v.drivers).toEqual([{ rsvp: RSVP_EVA, riders: [RSVP_SANNE] }]);
		expect(v.seekers).toEqual([RSVP_NOOR]);
		expect(v.isEmpty).toBe(false);
		const e = carpoolView({ seats_free: null, departure_point: '  ' }, [RSVP_TOM]);
		expect(e.departurePoint).toBeNull();
		expect(e.isEmpty).toBe(true);
		const orphan = carpoolView({ seats_free: null, departure_point: null }, [
			{ ...RSVP_SANNE, rides_with: 'e0000000-0000-4000-8000-0000000000ff' }
		]);
		expect(orphan.seekers).toHaveLength(1);
	});
});

describe('links and text', () => {
	it('tikkieLink (A14)', () => {
		expect(tikkieLink('https://tikkie.me/pay/x')).toBe('https://tikkie.me/pay/x');
		for (const bad of [
			null,
			'',
			'http://tikkie.me/pay/x',
			'javascript:alert(1)',
			'geen url',
			'https://evil.example/pay/x',
			'https://tikkie.me.evil.example/x',
			'https://www.tikkie.me/pay/x',
			'https://tikkie.me:8443/x',
			'https://u@tikkie.me/x',
			'HTTPS://TIKKIE.ME/x',
			'https://tikkie.me/'
		]) {
			expect(tikkieLink(bad)).toBeNull();
		}
	});
	it('optionalText and isolateText', () => {
		for (const v of [null, '', '  ']) expect(optionalText(v)).toBeNull();
		expect(optionalText('x')).toBe('x');
		expect(isolateText('Eva')).toBe('⁨Eva⁩');
	});
});

describe('parseRsvpForm', () => {
	const none = new Set<string>();
	const base = emptyRsvpForm();
	const errs = (r: ReturnType<typeof parseRsvpForm>) => (r.ok ? {} : r.errors);

	it('trims and ignores seats and rides_with when not applicable', () => {
		expect(
			parseRsvpForm({ first_name: '  Sanne ', ride: 'own', seats: '3', rides_with: EVA_ID }, 'create', none)
		).toEqual({ ok: true, value: { first_name: 'Sanne', ride: 'own', seats_offered: null, rides_with: null } });
	});
	it('name rules', () => {
		for (const n of ['', '   ']) {
			expect(errs(parseRsvpForm({ ...base, first_name: n }, 'create', none)).first_name).toBe(
				RSVP_FORM_MESSAGES.nameRequired
			);
		}
		expect(errs(parseRsvpForm({ ...base, first_name: 'x'.repeat(31) }, 'create', none)).first_name).toBe(
			RSVP_FORM_MESSAGES.nameTooLong
		);
		expect(parseRsvpForm({ ...base, first_name: '😀'.repeat(30) }, 'create', none).ok).toBe(true);
		for (const n of ['Sa\nnne', 'Sa\u0007']) {
			expect(errs(parseRsvpForm({ ...base, first_name: n }, 'create', none)).first_name).toBe(
				RSVP_FORM_MESSAGES.nameInvalid
			);
		}
	});
	it('ride required', () => {
		expect(errs(parseRsvpForm({ ...base, first_name: 'A', ride: '' }, 'create', none)).ride).toBe(
			RSVP_FORM_MESSAGES.rideRequired
		);
	});
	it('seats', () => {
		const f = (seats: string) =>
			parseRsvpForm({ ...base, first_name: 'A', ride: 'offers_ride', seats }, 'create', none);
		const seatsOf = (seats: string) => {
			const r = f(seats);
			return r.ok ? r.value.seats_offered : 'err';
		};
		expect(seatsOf('')).toBeNull();
		expect(seatsOf('0')).toBe(0);
		expect(seatsOf('8')).toBe(8);
		for (const bad of ['9', '-1', '2.5']) expect(errs(f(bad)).seats).toBe(RSVP_FORM_MESSAGES.seatsInvalid);
	});
	it('rides_with', () => {
		const f = (mode: 'create' | 'edit', rw: string) =>
			parseRsvpForm({ ...base, first_name: 'A', ride: 'needs_ride', rides_with: rw }, mode, new Set([EVA_ID]));
		const r1 = f('edit', EVA_ID);
		expect(r1.ok && r1.value.rides_with).toBe(EVA_ID);
		expect(errs(f('edit', TOM_ID)).rides_with).toBe(RSVP_FORM_MESSAGES.ridesWithInvalid);
		const r3 = f('edit', '');
		expect(r3.ok && r3.value.rides_with).toBeNull();
		const r4 = f('create', EVA_ID);
		expect(r4.ok && r4.value.rides_with).toBeNull();
	});
	it('collects all errors', () => {
		const r = parseRsvpForm({ ...base, first_name: '', ride: '' }, 'create', none);
		expect(Object.keys(errs(r)).sort()).toEqual(['first_name', 'ride']);
	});
	it('rsvpFormFromRsvp', () => {
		expect(rsvpFormFromRsvp(RSVP_EVA)).toEqual({
			first_name: 'Eva',
			ride: 'offers_ride',
			seats: '2',
			rides_with: ''
		});
	});
});
