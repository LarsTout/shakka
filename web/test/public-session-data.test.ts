import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import {
	NOW,
	SESSION_EVALS,
	SESSION_INFO,
	SESSION_JSON,
	SLUG,
	publicSessionPageData
} from './fixtures/public-session.js';

const m = vi.hoisted(() => ({ getPublicSession: vi.fn(), getEvaluations: vi.fn() }));
vi.mock('#lib/rsvp.js', () => ({ getPublicSession: m.getPublicSession }));
vi.mock('#lib/data.js', () => ({ getEvaluations: m.getEvaluations }));

import { loadPublicSessionPage } from '../src/lib/public-session-data.js';

beforeEach(() => {
	vi.clearAllMocks();
	m.getPublicSession.mockResolvedValue(SESSION_JSON);
	m.getEvaluations.mockResolvedValue(SESSION_EVALS);
});
afterEach(() => vi.restoreAllMocks());

describe('loadPublicSessionPage', () => {
	it('invalid slug: not_found without calls', async () => {
		const r = await loadPublicSessionPage('kort', new Date(NOW));
		expect(r.kind).toBe('not_found');
		expect(m.getPublicSession).not.toHaveBeenCalled();
	});
	it('unknown session: not_found, no evaluations', async () => {
		m.getPublicSession.mockResolvedValue(null);
		expect((await loadPublicSessionPage(SLUG, new Date(NOW))).kind).toBe('not_found');
		expect(m.getEvaluations).not.toHaveBeenCalled();
	});
	it('ok: evaluations for the window', async () => {
		const r = await loadPublicSessionPage(SLUG, new Date(NOW));
		const [spot, from, to] = m.getEvaluations.mock.calls[0];
		expect(spot).toBe('test-strand');
		expect(from.toISOString()).toBe('2026-07-18T12:00:00.000Z');
		expect(to.toISOString()).toBe('2026-07-18T16:00:00.000Z');
		expect(r).toEqual(publicSessionPageData());
	});
	it('from is floored to the hour', async () => {
		m.getPublicSession.mockResolvedValue({
			...SESSION_JSON,
			session: { ...SESSION_INFO, starts_at: '2026-07-18T12:30:00+00:00' }
		});
		await loadPublicSessionPage(SLUG, new Date(NOW));
		expect(m.getEvaluations.mock.calls[0][1].toISOString()).toBe('2026-07-18T12:00:00.000Z');
	});
	it('evaluations failure: ok with null and one bare warning', async () => {
		const warn = vi.spyOn(console, 'warn').mockImplementation(() => {});
		m.getEvaluations.mockRejectedValue(new Error('secret detail'));
		const r = await loadPublicSessionPage(SLUG, new Date(NOW));
		expect(r.kind).toBe('ok');
		expect(r.kind === 'ok' && r.evaluations).toBeNull();
		expect(warn).toHaveBeenCalledTimes(1);
		expect(warn).toHaveBeenCalledWith('session verdict load failed');
	});
	it('session failure: error and a bare warning', async () => {
		const warn = vi.spyOn(console, 'warn').mockImplementation(() => {});
		m.getPublicSession.mockRejectedValue(new Error('secret detail'));
		const r = await loadPublicSessionPage(SLUG, new Date(NOW));
		expect(r.kind).toBe('error');
		expect(warn).toHaveBeenCalledWith('session page load failed');
		expect(JSON.stringify(warn.mock.calls)).not.toContain('secret detail');
	});
});
