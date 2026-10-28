import { getSpot, listSpots } from '#lib/data.js';
import { getPublicSession } from './rsvp.js';
import type { PublicRsvp } from './rsvp-types.js';
import type { SessionRow } from './session-model.js';
import { getMySession, listMySessions } from './sessions.js';
import type { Spot } from './types.js';

export type NewSessionPageData = { kind: 'ok'; spots: Spot[] } | { kind: 'error' };

/** listSpots(); throw -> console.warn('new session load failed') and error. */
export async function loadNewSessionPage(): Promise<NewSessionPageData> {
	try {
		return { kind: 'ok', spots: await listSpots() };
	} catch {
		console.warn('new session load failed');
		return { kind: 'error' };
	}
}

export type SharePageData =
	| { kind: 'ok'; session: SessionRow; spotName: string }
	| { kind: 'not_found' }
	| { kind: 'error' };

/** getMySession(slug); null -> not_found; spotName = spot name, else the spot id. */
export async function loadSharePage(slug: string): Promise<SharePageData> {
	try {
		const session = await getMySession(slug);
		if (session === null) return { kind: 'not_found' };
		const spot = await getSpot(session.spot_id);
		return { kind: 'ok', session, spotName: spot?.name ?? session.spot_id };
	} catch {
		console.warn('share page load failed');
		return { kind: 'error' };
	}
}

export type ManagePageData =
	| { kind: 'ok'; session: SessionRow; spotName: string; rsvps: PublicRsvp[]; rsvpsClosed: boolean }
	| { kind: 'not_found' }
	| { kind: 'error' };

/** getMySession(slug); null -> not_found (no RPC). Then getPublicSession(slug); null -> not_found.
 *  spotName = public spot_name ?? session.spot_id. Throw -> console.warn('manage page load failed'), error. */
export async function loadManagePage(slug: string): Promise<ManagePageData> {
	try {
		const session = await getMySession(slug);
		if (session === null) return { kind: 'not_found' };
		const pub = await getPublicSession(slug);
		if (pub === null) return { kind: 'not_found' };
		return {
			kind: 'ok',
			session,
			spotName: pub.session.spot_name ?? session.spot_id,
			rsvps: pub.rsvps,
			rsvpsClosed: pub.session.rsvps_closed
		};
	} catch {
		console.warn('manage page load failed');
		return { kind: 'error' };
	}
}

export interface MySessionEntry {
	session: SessionRow;
	spotName: string;
}
export type MySessionsPageData =
	| { kind: 'ok'; entries: MySessionEntry[]; spots: Spot[] }
	| { kind: 'error' };

/** Own upcoming sessions plus the spot list; spotName from the list, else spot_id. */
export async function loadMySessionsPage(userId: string, now: Date): Promise<MySessionsPageData> {
	try {
		const [sessions, spots] = await Promise.all([listMySessions(userId, now), listSpots()]);
		const names = new Map(spots.map((s) => [s.id, s.name]));
		const entries = sessions.map((session) => ({
			session,
			spotName: names.get(session.spot_id) ?? session.spot_id
		}));
		return { kind: 'ok', entries, spots };
	} catch {
		console.warn('my sessions load failed');
		return { kind: 'error' };
	}
}
