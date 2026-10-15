export const VERDICTS = ['go', 'marginal', 'no_go'] as const;
export type Verdict = (typeof VERDICTS)[number];

export const REASON_CODES = [
	'no_data',
	'wind_too_light',
	'wind_too_strong',
	'wind_borderline',
	'too_gusty',
	'gusty',
	'offshore',
	'side_offshore',
	'direction_unknown',
	'direction_not_ridable',
	'dark',
	'season_closed',
	'spot_forbidden',
	'spot_limited',
	'status_unknown',
	'tide_too_low',
	'tide_unfavorable',
	'tide_unknown',
	'low_confidence'
] as const;
export type ReasonCode = (typeof REASON_CODES)[number];

export const DIR_CLASSES = [
	'onshore',
	'side_onshore',
	'sideshore',
	'side_offshore',
	'offshore'
] as const;
export type DirClass = (typeof DIR_CLASSES)[number];

export const CONFIDENCES = ['high', 'medium', 'low'] as const;
export type Confidence = (typeof CONFIDENCES)[number];

export type SpotStatus = 'allowed' | 'limited' | 'forbidden';
export type SpotLevel = 'beginner' | 'intermediate' | 'advanced';
export type TideSensitivity = 'none' | 'prefer_low' | 'prefer_high' | 'avoid_low';
export type TideKind = 'high' | 'low';

export interface DirRange {
	from: number;
	to: number;
}
export interface SeasonClosure {
	start: string; // 'MM-DD'
	end: string; // 'MM-DD'
	from_time: string | null; // 'HH:MM'
	to_time: string | null; // 'HH:MM'
	note: string | null;
}

/** Row of public.spots (all columns). */
export interface Spot {
	id: string;
	name: string;
	region: string | null;
	lat: number | null;
	lon: number | null;
	shore_normal_deg: number | null;
	ridable_dirs: DirRange[] | null;
	hazards: string | null;
	tide_sensitive: TideSensitivity;
	tide_min_level_cm: number | null;
	rws_station: string | null;
	season: SeasonClosure[];
	status: SpotStatus | null;
	level: SpotLevel | null;
	default_min_kn: number | null;
	notes: string | null;
	verified: boolean;
	updated_at: string;
}

/** Row of public.evaluations (all columns). */
export interface Evaluation {
	spot_id: string;
	valid_at: string;
	verdict: Verdict;
	reasons: ReasonCode[];
	wind_kn: number | null;
	gust_kn: number | null;
	dir_deg: number | null;
	dir_class: DirClass | null;
	confidence: Confidence | null;
	tide_level_cm: number | null;
	evaluated_at: string;
}

/** Row of public.tide_extremes without fetched_at. */
export interface TideExtreme {
	station: string;
	at: string;
	kind: TideKind;
	level_cm: number;
}

export type SummaryRow = Pick<
	Evaluation,
	'spot_id' | 'valid_at' | 'verdict' | 'reasons' | 'evaluated_at'
>;

/** Daylight hours (no 'dark' reason) of one local day, from floorHour(now). */
export interface DaySummary {
	date: string; // local 'YYYY-MM-DD'
	go: number;
	marginal: number;
	no_go: number;
	best: Verdict | null; // most favourable verdict of the day; null without hours
	first_go_at: string | null; // valid_at of the first go hour
}

export interface SpotSummary {
	spot_id: string;
	today: DaySummary;
	tomorrow: DaySummary;
	latest_evaluated_at: string; // max evaluated_at of the summarised rows
}

export const SPOT_COLUMNS = [
	'id',
	'name',
	'region',
	'lat',
	'lon',
	'shore_normal_deg',
	'ridable_dirs',
	'hazards',
	'tide_sensitive',
	'tide_min_level_cm',
	'rws_station',
	'season',
	'status',
	'level',
	'default_min_kn',
	'notes',
	'verified',
	'updated_at'
] as const;
export const EVALUATION_COLUMNS = [
	'spot_id',
	'valid_at',
	'verdict',
	'reasons',
	'wind_kn',
	'gust_kn',
	'dir_deg',
	'dir_class',
	'confidence',
	'tide_level_cm',
	'evaluated_at'
] as const;
export const TIDE_EXTREME_COLUMNS = ['station', 'at', 'kind', 'level_cm'] as const;
export const SUMMARY_COLUMNS = [
	'spot_id',
	'valid_at',
	'verdict',
	'reasons',
	'evaluated_at'
] as const;
