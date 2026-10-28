// @vitest-environment node
import { describe, expect, it } from 'vitest';
import { ALERT_DEFAULTS } from '../src/lib/contracts.js';
import {
	FORM_MESSAGES,
	DAYS_AHEAD_UI_MAX,
	HOUR_OPTIONS,
	QUIET_HOUR_OPTIONS,
	daysAheadOptions,
	parseAlertRuleForm,
	parseProfileForm,
	parseRuleFields,
	profileKnHints,
	parseQuietHours,
	profileToForm,
	quietHourOptions,
	quietHoursSummary,
	quietToForm,
	ruleHints,
	ruleSummary,
	ruleToForm,
	storedRuleStatus,
	timeOptions,
	type AlertRuleForm,
	type ProfileForm,
	type RuleContext
} from '../src/lib/forms.js';
import { effectiveRule } from '../src/lib/rules.js';
import { PROFILE_EDITABLE_COLUMNS, RULE_FIELDS, type DirClass } from '../src/lib/types.js';
import { SPOT_VERIFIED } from './fixtures/spot-data.js';
import { PROFILE_FULL, ruleRow } from './fixtures/user-data.js';

const D = ALERT_DEFAULTS;
const pform = (o: Partial<ProfileForm> = {}): ProfileForm => ({
	weight_kg: '',
	level: '',
	quiver: [],
	default_min_kn: '',
	default_max_kn: '',
	...o
});
const rform = (o: Partial<AlertRuleForm> = {}): AlertRuleForm => ({
	...ruleToForm(null, D),
	...o
});
const ctx = (o: Partial<RuleContext> = {}): RuleContext => ({
	spot: { default_min_kn: null },
	profile: null,
	defaults: D,
	...o
});
const CTX_FULL = ctx({ profile: PROFILE_FULL });

describe('parseProfileForm', () => {
	it.each(['25', '201', '75,5', 'abc'])('weight %s is an error', (w) => {
		const r = parseProfileForm(pform({ weight_kg: w }), D);
		expect(r).toEqual({ ok: false, errors: { weight_kg: FORM_MESSAGES.weight } });
	});
	it.each(['30', '200'])('weight %s is ok', (w) => {
		const r = parseProfileForm(pform({ weight_kg: w }), D);
		expect(r.ok && r.value.weight_kg).toBe(Number(w));
	});
	it('empty weight and level are null', () => {
		const r = parseProfileForm(pform(), D);
		expect(r).toEqual({
			ok: true,
			value: { weight_kg: null, level: null, quiver_m2: [], default_min_kn: null, default_max_kn: null }
		});
	});
	it('rejects an unknown level', () => {
		const r = parseProfileForm(pform({ level: 'expert' as never }), D);
		expect(r.ok === false && r.errors.level).toBe(FORM_MESSAGES.level);
	});
	it.each([['2,5'], ['22'], ['9,123']])('quiver %s is an error', (m) => {
		const r = parseProfileForm(pform({ quiver: [m] }), D);
		expect(r.ok === false && r.errors.quiver_m2).toBe(FORM_MESSAGES.quiverSize);
	});
	it('rejects 11 kites', () => {
		const r = parseProfileForm(pform({ quiver: Array.from({ length: 11 }, () => '9') }), D);
		expect(r.ok === false && r.errors.quiver_m2).toBe(FORM_MESSAGES.quiverCount);
	});
	it('sorts, trims and drops empties; accepts 3, 21 and 10,5', () => {
		const r = parseProfileForm(pform({ quiver: ['12', '', '10,5', ' 9 ', '3', '21'] }), D);
		expect(r.ok && r.value.quiver_m2).toEqual([3, 9, 10.5, 12, 21]);
	});
	it('min 20 / max 20 gives minNotBelowMax on default_max_kn', () => {
		const r = parseProfileForm(pform({ default_min_kn: '20', default_max_kn: '20' }), D);
		expect(r).toEqual({ ok: false, errors: { default_max_kn: FORM_MESSAGES.minNotBelowMax } });
	});
	it("kn '4' is an error", () => {
		const r = parseProfileForm(pform({ default_min_kn: '4' }), D);
		expect(r.ok === false && r.errors.default_min_kn).toBe(FORM_MESSAGES.kn);
	});
	it('the result has exactly the five editable keys', () => {
		const r = parseProfileForm(pform({ default_min_kn: '14' }), D);
		expect(r.ok && Object.keys(r.value).sort()).toEqual([...PROFILE_EDITABLE_COLUMNS].sort());
	});
});

describe('profileToForm and hints', () => {
	it('converts numbers to strings with a decimal comma', () => {
		expect(profileToForm(PROFILE_FULL).quiver).toEqual(['9', '12']);
		expect(profileToForm({ ...PROFILE_FULL, quiver_m2: [10.5] }).quiver).toEqual(['10,5']);
		expect(profileToForm(PROFILE_FULL).weight_kg).toBe('75');
		expect(profileToForm({ ...PROFILE_FULL, level: null, weight_kg: null }).level).toBe('');
	});
	it('profileKnHints', () => {
		expect(profileKnHints(D)).toEqual({
			default_min_kn: 'standaard: de waarde van de spot, anders 12 kn (Shakka)',
			default_max_kn: 'standaard: 30 kn, of 5 kn boven de minimale wind als dat hoger is (Shakka)'
		});
	});
});

describe('ruleToForm', () => {
	it('null gives the defaults', () => {
		const f = ruleToForm(null, D);
		expect(f.enabled).toBe(true);
		expect(f.dir_classes).toEqual(D.dir_classes.default);
		expect(f.dir_classes).not.toBe(D.dir_classes.default);
		expect(f.weekdays).toEqual([1, 2, 3, 4, 5, 6, 7]);
		expect(f.min_kn).toBe('');
		expect(f.days_ahead).toBe('');
	});
	it('times', () => {
		expect(ruleToForm(ruleRow('x', { latest_local: '24:00:00' }), D).latest_local).toBe('');
		expect(ruleToForm(ruleRow('x', { earliest_local: '24:00:00' }), D).earliest_local).toBe('');
		expect(ruleToForm(ruleRow('x', { earliest_local: '20:30:00' }), D).earliest_local).toBe('20:30');
		expect(ruleToForm(ruleRow('x', { earliest_local: '17:00:30.5' }), D).earliest_local).toBe(
			'17:00:30.500000'
		);
		expect(ruleToForm(ruleRow('x', { earliest_local: 'garbage' }), D).earliest_local).toBe('');
	});
	it('numbers become strings, 0 included', () => {
		const f = ruleToForm(ruleRow('x', { min_kn: 14, days_ahead: 0 }), D);
		expect(f.min_kn).toBe('14');
		expect(f.days_ahead).toBe('0');
	});
});

describe('parseAlertRuleForm', () => {
	it('E14: min 20 / max 15', () => {
		const r = parseAlertRuleForm(rform({ min_kn: '20', max_kn: '15' }), ctx());
		expect(r).toEqual({ ok: false, errors: { max_kn: FORM_MESSAGES.minNotBelowMax } });
	});
	it('E15: min 25 against profile max 20', () => {
		const r = parseAlertRuleForm(
			rform({ min_kn: '25' }),
			ctx({ profile: { default_min_kn: null, default_max_kn: 20 } })
		);
		expect(r).toEqual({
			ok: false,
			errors: {
				min_kn:
					'Minimale wind 25 kn (je instelling voor deze spot) moet lager zijn dan maximale wind 20 kn (je profiel).'
			}
		});
	});
	it('E16: spot min 22 with profile max 20', () => {
		const c = ctx({ spot: { default_min_kn: 22 }, profile: { default_min_kn: null, default_max_kn: 20 } });
		const r = parseAlertRuleForm(rform(), c);
		expect(r.ok === false && Object.keys(r.errors)).toEqual(['min_kn']);
		expect(parseAlertRuleForm(rform({ max_kn: '26' }), c).ok).toBe(true);
	});
	it('E17: no directions', () => {
		const r = parseAlertRuleForm(rform({ dir_classes: [] }), ctx());
		expect(r.ok === false && r.errors.dir_classes).toBe(FORM_MESSAGES.dirEmpty);
	});
	it('offshore is dirInvalid', () => {
		const r = parseAlertRuleForm(rform({ dir_classes: ['offshore'] as DirClass[] }), ctx());
		expect(r.ok === false && r.errors.dir_classes).toBe(FORM_MESSAGES.dirInvalid);
		const r2 = parseAlertRuleForm(rform({ dir_classes: ['onshore', 'side_offshore'] as DirClass[] }), ctx());
		expect(r2.ok === false && r2.errors.dir_classes).toBe(FORM_MESSAGES.dirInvalid);
	});
	it('E18: all directions and all days are null', () => {
		const r = parseAlertRuleForm(rform(), ctx());
		expect(r.ok && r.value.dir_classes).toBeNull();
		expect(r.ok && r.value.weekdays).toBeNull();
		const sub = parseAlertRuleForm(rform({ weekdays: [6, 7], dir_classes: ['sideshore', 'onshore'] }), ctx());
		expect(sub.ok && sub.value.weekdays).toEqual([6, 7]);
		expect(sub.ok && sub.value.dir_classes).toEqual(['onshore', 'sideshore']);
	});
	it('E19 style: no days is weekdaysEmpty, bad day is weekdaysInvalid', () => {
		expect(parseAlertRuleForm(rform({ weekdays: [] }), ctx())).toEqual({
			ok: false,
			errors: { weekdays: FORM_MESSAGES.weekdaysEmpty }
		});
		const r = parseAlertRuleForm(rform({ weekdays: [8] }), ctx());
		expect(r.ok === false && r.errors.weekdays).toBe(FORM_MESSAGES.weekdaysInvalid);
	});
	it('E24: Vanaf 18:00 / Tot 17:00 gives timeOrder', () => {
		const r = parseAlertRuleForm(rform({ earliest_local: '18:00', latest_local: '17:00' }), ctx());
		expect(r).toEqual({ ok: false, errors: { latest_local: FORM_MESSAGES.timeOrder } });
	});
	it('Tot 00:00 gives latestMidnight; a malformed time gives time', () => {
		expect(parseAlertRuleForm(rform({ latest_local: '00:00' }), ctx())).toEqual({
			ok: false,
			errors: { latest_local: FORM_MESSAGES.latestMidnight }
		});
		const r = parseAlertRuleForm(rform({ earliest_local: '17:0' }), ctx());
		expect(r.ok === false && r.errors.earliest_local).toBe(FORM_MESSAGES.time);
	});
	it('days_ahead: 7 valid, 8 invalid, 0 -> 0', () => {
		const ok = (v: string) => parseAlertRuleForm(rform({ days_ahead: v }), ctx());
		expect(ok('7').ok).toBe(true);
		const bad = ok('8');
		expect(bad.ok === false && bad.errors.days_ahead).toBe(FORM_MESSAGES.daysAhead);
		const zero = ok('0');
		expect(zero.ok && zero.value.days_ahead).toBe(0);
	});
	it('a valid form yields exactly the nine keys, times as HH:MM:00', () => {
		const r = parseAlertRuleForm(
			rform({ min_kn: '14', earliest_local: '17:00', latest_local: '21:00', min_go_hours: '3' }),
			ctx()
		);
		expect(r.ok && Object.keys(r.value)).toEqual([...RULE_FIELDS]);
		expect(r.ok && r.value).toEqual({
			enabled: true,
			min_kn: 14,
			max_kn: null,
			dir_classes: null,
			weekdays: null,
			earliest_local: '17:00:00',
			latest_local: '21:00:00',
			min_go_hours: 3,
			days_ahead: null
		});
	});
	it('E33: seconds and fractions are written unchanged', () => {
		const w = (v: string) => {
			const r = parseAlertRuleForm(rform({ earliest_local: v }), ctx());
			return r.ok ? r.value.earliest_local : null;
		};
		expect(w('17:00:30.500000')).toBe('17:00:30.500000');
		expect(w('17:00:30')).toBe('17:00:30');
		expect(w('17:00')).toBe('17:00:00');
	});
	it('E36: an invalid profile gives profileInvalid on min_kn', () => {
		const r = parseAlertRuleForm(
			rform(),
			ctx({ profile: { default_min_kn: 20, default_max_kn: 20 } })
		);
		expect(r).toEqual({ ok: false, errors: { min_kn: FORM_MESSAGES.profileInvalid } });
	});
	it('min_go_hours out of range', () => {
		const r = parseAlertRuleForm(rform({ min_go_hours: '25' }), ctx());
		expect(r.ok === false && r.errors.min_go_hours).toBe(FORM_MESSAGES.minGoHours);
	});
});

describe('parseRuleFields (B-1, E24, E34)', () => {
	it('Vanaf 18:00 / Tot 17:00', () => {
		const r = parseRuleFields(rform({ earliest_local: '18:00', latest_local: '17:00' }), D);
		expect(r.errors.latest_local).toBe(FORM_MESSAGES.timeOrder);
		expect(r.value.earliest_local).toBe('18:00:00');
		expect(r.value.latest_local).toBeNull();
	});
	it('min 20 / max 15', () => {
		const r = parseRuleFields(rform({ min_kn: '20', max_kn: '15' }), D);
		expect(r.errors.max_kn).toBe(FORM_MESSAGES.minNotBelowMax);
		expect(r.value.min_kn).toBe(20);
		expect(r.value.max_kn).toBeNull();
	});
	it('Tot 00:00', () => {
		expect(parseRuleFields(rform({ latest_local: '00:00' }), D).value.latest_local).toBeNull();
	});

	const BAD: [string, AlertRuleForm, RuleContext][] = [
		['inverted window', rform({ earliest_local: '18:00', latest_local: '17:00' }), ctx()],
		['min above max', rform({ min_kn: '20', max_kn: '15' }), ctx()],
		['Tot 00:00', rform({ latest_local: '00:00' }), ctx()],
		['invalid profile', rform(), ctx({ profile: { default_min_kn: 20, default_max_kn: 20 } })],
		[
			'conflict',
			rform(),
			ctx({ spot: { default_min_kn: 22 }, profile: { default_min_kn: null, default_max_kn: 20 } })
		]
	];
	it.each(BAD)('ruleHints never throws: %s', (_n, f, c) => {
		expect(() => ruleHints(f, c)).not.toThrow();
		// N-4: only step 2 of effectiveRule is checked here, hence profile null: this tests the guarantee
		// of parseRuleFields (its value always passes validation), not conflict detection.
		expect(() =>
			effectiveRule(c.spot, null, parseRuleFields(f, D).value, D)
		).not.toThrow();
	});
	it('keeps the profile hint despite an inverted window', () => {
		const h = ruleHints(rform({ earliest_local: '18:00', latest_local: '17:00' }), CTX_FULL);
		expect(h.min_kn).toBe('standaard: 14 kn (je profiel)');
		expect(h.latest_local).toBeUndefined();
	});
	it('invalid profile and conflict give the conflict hint', () => {
		for (const [, f, c] of BAD.slice(3)) {
			const h = ruleHints(f, c);
			expect(h.min_kn).toBe('standaard: botst met je andere windgrenzen');
			expect(h.min_go_hours).toBe('standaard: 2 uur (Shakka)');
		}
	});
});

describe('ruleHints', () => {
	it('profile values', () => {
		const h = ruleHints(rform(), CTX_FULL);
		expect(h.min_kn).toBe('standaard: 14 kn (je profiel)');
		expect(h.max_kn).toBe('standaard: 26 kn (je profiel)');
	});
	it('spot value and system max', () => {
		const h = ruleHints(rform(), ctx({ spot: { default_min_kn: 16 } }));
		expect(h.min_kn).toBe('standaard: 16 kn (spotprofiel)');
		expect(h.max_kn).toBe('standaard: 30 kn (Shakka)');
	});
	it('derived max', () => {
		expect(ruleHints(rform({ min_kn: '28' }), ctx()).max_kn).toBe('standaard: 33 kn (Shakka)');
		expect(ruleHints(rform({ min_kn: '60' }), ctx()).max_kn).toBe('standaard: 65 kn (Shakka)');
	});
	it('static hints', () => {
		const h = ruleHints(rform(), ctx());
		expect(h.days_ahead).toBe('standaard: vandaag plus 3 dagen (Shakka)');
		expect(h.min_go_hours).toBe('standaard: 2 uur (Shakka)');
		expect(h.dir_classes).toBe('standaard: alle rijdbare richtingen (Shakka)');
		expect(h.weekdays).toBe('standaard: alle dagen (Shakka)');
		expect(h.earliest_local).toBe('standaard: geen ondergrens (Shakka)');
		expect(h.latest_local).toBe('standaard: geen bovengrens (Shakka)');
	});
	it('filled fields have no hint', () => {
		const h = ruleHints(
			rform({ min_kn: '14', max_kn: '20', days_ahead: '1', weekdays: [6], dir_classes: ['onshore'] }),
			ctx()
		);
		expect(h.min_kn).toBeUndefined();
		expect(h.max_kn).toBeUndefined();
		expect(h.days_ahead).toBeUndefined();
		expect(h.weekdays).toBeUndefined();
		expect(h.dir_classes).toBeUndefined();
	});
});

describe('ruleSummary and storedRuleStatus', () => {
	it('defaults', () => {
		expect(ruleSummary(effectiveRule({ default_min_kn: null }, null, null, D))).toBe(
			'Aan · 12–30 kn · min. 2 uur go · vandaag plus 3 dagen'
		);
	});
	it('case 7', () => {
		const row = ruleRow('x', {
			enabled: false,
			min_kn: 18,
			max_kn: 24,
			dir_classes: ['sideshore'],
			weekdays: [6, 7],
			earliest_local: '17:00:00',
			latest_local: '21:00:00',
			min_go_hours: 3,
			days_ahead: 5
		});
		expect(ruleSummary(effectiveRule({ default_min_kn: 16 }, null, row, D))).toBe(
			'Uit · 18–24 kn · Sideshore (langs de kust) · za, zo · 17:00–21:00 · min. 3 uur go · vandaag plus 5 dagen'
		);
	});
	it('E16 and E21 problems', () => {
		const c = ctx({ spot: { default_min_kn: 22 }, profile: { default_min_kn: null, default_max_kn: 20 } });
		const s = storedRuleStatus(null, c);
		expect(s).toEqual({
			ok: false,
			problem:
				'Deze instellingen botsen: minimale wind 22 kn (spotprofiel) is niet lager dan maximale wind 20 kn (je profiel). Voor deze spot komen geen alerts tot je dit aanpast.'
		});
		expect(storedRuleStatus(ruleRow('x', { earliest_local: '24:00:00' }), ctx())).toEqual({
			ok: false,
			problem:
				'De opgeslagen instelling is ongeldig. Voor deze spot komen geen alerts tot je hem opnieuw opslaat.'
		});
	});
	it('E19: Tot 00:00 is a problem, 00:30 is fine', () => {
		const bad = storedRuleStatus(ruleRow('test-meer', { latest_local: '00:00:00' }), CTX_FULL);
		expect(bad).toEqual({
			ok: false,
			problem:
				'"Tot 00:00" telt geen enkel uur. Voor deze spot komen geen alerts tot je dit aanpast.'
		});
		expect(storedRuleStatus(ruleRow('test-meer', { latest_local: '00:30:00' }), CTX_FULL).ok).toBe(true);
	});
	it('uses the SPOT_VERIFIED fixture shape', () => {
		expect(storedRuleStatus(null, ctx({ spot: SPOT_VERIFIED })).ok).toBe(true);
	});
});

describe('options', () => {
	it('timeOptions', () => {
		expect(timeOptions('')).toHaveLength(23);
		expect(timeOptions('')[0]).toBe('01:00');
		expect(timeOptions('')[22]).toBe('23:00');
		expect(timeOptions('')).not.toContain('00:00');
		expect(timeOptions('')).not.toContain('24:00');
		expect(HOUR_OPTIONS).toHaveLength(23);
		const o = timeOptions('20:30');
		expect(o.indexOf('20:30')).toBe(o.indexOf('20:00') + 1);
		expect(o[o.indexOf('20:30') + 1]).toBe('21:00');
		expect(timeOptions('00:00')[0]).toBe('00:00');
	});
	it('daysAheadOptions', () => {
		expect(daysAheadOptions('')).toEqual(['0', '1', '2', '3', '4', '5', '6', '7']);
		expect(daysAheadOptions('3')).toHaveLength(8);
		expect(daysAheadOptions('7')).toHaveLength(8);
		expect(daysAheadOptions('7').filter((o) => o === '7')).toHaveLength(1);
	});
	it('DAYS_AHEAD_UI_MAX matches the contract max', () => {
		expect(DAYS_AHEAD_UI_MAX).toBe(ALERT_DEFAULTS.days_ahead.max);
	});
});

describe('quiet hours forms (WP-30)', () => {
	it('parseQuietHours: both empty switches off', () => {
		expect(parseQuietHours('', '')).toEqual({ quiet_from: null, quiet_until: null });
		expect(parseQuietHours(' ', ' ')).toEqual({ quiet_from: null, quiet_until: null });
	});
	it('parseQuietHours: one empty is incomplete, in both orders', () => {
		expect(parseQuietHours('22:00', '')).toEqual({ error: FORM_MESSAGES.quietIncomplete });
		expect(parseQuietHours('', '07:00')).toEqual({ error: FORM_MESSAGES.quietIncomplete });
	});
	it('parseQuietHours: rejects values outside HH:MM', () => {
		for (const bad of ['24:00', '7:00', '22:00:00', 'abc', '22:60']) {
			expect(parseQuietHours(bad, '07:00')).toEqual({ error: FORM_MESSAGES.time });
			expect(parseQuietHours('22:00', bad)).toEqual({ error: FORM_MESSAGES.time });
		}
	});
	it('parseQuietHours: equal times are rejected', () => {
		expect(parseQuietHours('22:00', '22:00')).toEqual({ error: FORM_MESSAGES.quietEqual });
	});
	it('parseQuietHours: a valid pair gets seconds', () => {
		expect(parseQuietHours('22:00', '07:00')).toEqual({
			quiet_from: '22:00:00',
			quiet_until: '07:00:00'
		});
		expect(parseQuietHours(' 13:00 ', '14:00')).toEqual({
			quiet_from: '13:00:00',
			quiet_until: '14:00:00'
		});
	});
	it('quiet messages are Dutch', () => {
		expect(FORM_MESSAGES.quietIncomplete).toBe(
			'Kies een begin- én een eindtijd, of zet stille uren uit.'
		);
		expect(FORM_MESSAGES.quietEqual).toBe(
			'Begin en einde van de stille uren mogen niet gelijk zijn.'
		);
	});
	it('quietToForm', () => {
		expect(quietToForm(null)).toEqual({ from: '', until: '' });
		expect(quietToForm({ quiet_from: null, quiet_until: null })).toEqual({ from: '', until: '' });
		expect(quietToForm({ quiet_from: '22:00:00', quiet_until: '07:00' })).toEqual({
			from: '22:00',
			until: '07:00'
		});
		expect(quietToForm({ quiet_from: 'kapot', quiet_until: '07:00:00' })).toEqual({
			from: '',
			until: '07:00'
		});
	});
	it('quietHourOptions', () => {
		expect(QUIET_HOUR_OPTIONS).toHaveLength(24);
		expect(QUIET_HOUR_OPTIONS[0]).toBe('00:00');
		expect(QUIET_HOUR_OPTIONS[23]).toBe('23:00');
		expect(quietHourOptions('22:00')).toEqual([...QUIET_HOUR_OPTIONS]);
		expect(quietHourOptions('')).toEqual([...QUIET_HOUR_OPTIONS]);
		const extra = quietHourOptions('22:30');
		expect(extra).toHaveLength(25);
		expect(extra.indexOf('22:30')).toBe(extra.indexOf('22:00') + 1);
	});
	it('quietHoursSummary', () => {
		expect(quietHoursSummary(null)).toBe('Stille uren staan uit.');
		expect(quietHoursSummary({ quiet_from: null, quiet_until: null })).toBe(
			'Stille uren staan uit.'
		);
		expect(quietHoursSummary({ quiet_from: '13:00:00', quiet_until: '14:00:00' })).toBe(
			'Elke dag van 13:00 tot 14:00 geen alerts.'
		);
		expect(quietHoursSummary({ quiet_from: '22:00:00', quiet_until: '07:00:00' })).toBe(
			'Elke dag van 22:00 tot 07:00 (de volgende dag) geen alerts.'
		);
		const invalid = 'De opgeslagen stille uren zijn ongeldig. Stel ze opnieuw in.';
		expect(quietHoursSummary({ quiet_from: '22:00:00', quiet_until: null })).toBe(invalid);
		expect(quietHoursSummary({ quiet_from: 'x', quiet_until: '07:00:00' })).toBe(invalid);
		expect(quietHoursSummary({ quiet_from: '22:00:00', quiet_until: '22:00:00' })).toBe(invalid);
	});
});
