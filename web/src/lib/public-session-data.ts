import { getEvaluations } from '#lib/data.js';
import { getPublicSession } from '#lib/rsvp.js';
import type { PublicRsvp, PublicSessionInfo } from './rsvp-types.js';
import { isValidSessionSlug } from './session-view.js';
import { floorHour } from './time.js';
import type { Evaluation } from './types.js';

export type PublicSessionPageData =
	| {
			kind: 'ok';
			now: string; // now.toISOString()
			slug: string;
			session: PublicSessionInfo;
			rsvps: PublicRsvp[];
			evaluations: Evaluation[] | null; // null: the verdict could not be loaded (A3)
	  }
	| { kind: 'not_found'; now: string; slug: string }
	| { kind: 'error'; now: string; slug: string };

export async function loadPublicSessionPage(slug: string, now: Date): Promise<PublicSessionPageData> {
	const base = { now: now.toISOString(), slug };
	if (!isValidSessionSlug(slug)) return { kind: 'not_found', ...base };
	let ps;
	try {
		ps = await getPublicSession(slug);
	} catch {
		console.warn('session page load failed');
		return { kind: 'error', ...base };
	}
	if (ps === null) return { kind: 'not_found', ...base };

	let evaluations: Evaluation[] | null = null;
	try {
		evaluations = await getEvaluations(
			ps.session.spot_id,
			floorHour(new Date(ps.session.starts_at)),
			new Date(ps.session.ends_at)
		);
	} catch {
		console.warn('session verdict load failed');
		evaluations = null;
	}
	return { kind: 'ok', ...base, session: ps.session, rsvps: ps.rsvps, evaluations };
}
