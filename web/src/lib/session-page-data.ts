import { getSpot, listSpots } from '#lib/data.js';
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
