// Shapes of the public session RPCs (WP-19 migration 20261015200000_sessions.sql).
// rsvp-contract.test.ts reads that migration and checks these keys, limits and the retention.

export const RIDES = ['own', 'needs_ride', 'offers_ride'] as const;
export type Ride = (typeof RIDES)[number];

export const MAX_FIRST_NAME = 30; // code points, like char_length in Postgres
export const MAX_SEATS = 8;
export const MAX_RSVPS = 30;
export const SESSION_RETENTION_DAYS = 7; // mirrors interval '7 days' in purge_expired_sessions

export const PUBLIC_SESSION_KEYS = [
	'slug',
	'spot_id',
	'spot_name',
	'organizer_name',
	'starts_at',
	'ends_at',
	'note',
	'seats_free',
	'departure_point',
	'tikkie_url',
	'cancelled'
] as const;
export const PUBLIC_RSVP_KEYS = [
	'id',
	'first_name',
	'ride',
	'seats_offered',
	'rides_with',
	'created_at'
] as const;

export interface PublicSessionInfo {
	slug: string;
	spot_id: string;
	spot_name: string | null;
	organizer_name: string;
	starts_at: string; // ISO 8601 with offset; parse, never compare as string
	ends_at: string;
	note: string | null;
	seats_free: number | null;
	departure_point: string | null;
	tikkie_url: string | null;
	cancelled: boolean;
}

export interface PublicRsvp {
	id: string;
	first_name: string;
	ride: Ride;
	seats_offered: number | null;
	rides_with: string | null;
	created_at: string;
}

export interface PublicSession {
	session: PublicSessionInfo;
	rsvps: PublicRsvp[];
}

export interface RsvpInput {
	first_name: string;
	ride: Ride;
	seats_offered: number | null;
}
export interface RsvpUpdateInput extends RsvpInput {
	rides_with: string | null;
}

/** Value under shakka:rsvp:{slug} in localStorage. */
export interface StoredRsvp {
	rsvp_id: string;
	edit_token: string;
}
