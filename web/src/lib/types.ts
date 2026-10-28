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

export const LEVELS: readonly SpotLevel[] = ['beginner', 'intermediate', 'advanced'];

/** Row of public.profiles (the columns the app uses; an unused legacy column is never selected). */
export interface Profile {
	user_id: string;
	weight_kg: number | null;
	level: SpotLevel | null;
	quiver_m2: number[];
	default_min_kn: number | null;
	default_max_kn: number | null;
	created_at: string;
	updated_at: string;
	quiet_from: string | null; // 'HH:MM:SS', Dutch local time (WP-30)
	quiet_until: string | null;
}
export const PROFILE_COLUMNS = [
	'user_id',
	'weight_kg',
	'level',
	'quiver_m2',
	'default_min_kn',
	'default_max_kn',
	'created_at',
	'updated_at',
	'quiet_from',
	'quiet_until'
] as const;
/** The only profile columns `authenticated` may update (column grant, WP-01). */
export const PROFILE_EDITABLE_COLUMNS = [
	'weight_kg',
	'level',
	'quiver_m2',
	'default_min_kn',
	'default_max_kn'
] as const;
export type ProfileEditableColumn = (typeof PROFILE_EDITABLE_COLUMNS)[number];
export type ProfileUpdate = Pick<Profile, ProfileEditableColumn>;
/** Columns `authenticated` may update for quiet hours (column grant, WP-30). */
export const QUIET_HOURS_COLUMNS = ['quiet_from', 'quiet_until'] as const;
export type QuietHoursUpdate = Pick<Profile, (typeof QUIET_HOURS_COLUMNS)[number]>;

export const FAVORITE_COLUMNS = ['user_id', 'spot_id', 'created_at'] as const;

/** Settable columns of alert_rules, in WP-07 RULE_FIELDS order. */
export const RULE_FIELDS = [
	'enabled',
	'min_kn',
	'max_kn',
	'dir_classes',
	'weekdays',
	'earliest_local',
	'latest_local',
	'min_go_hours',
	'days_ahead'
] as const;
export type RuleField = (typeof RULE_FIELDS)[number];
/** Priority order, highest first (WP-07 RuleSource). */
export const RULE_SOURCES = ['rule', 'profile', 'spot', 'system'] as const;
export type RuleSource = (typeof RULE_SOURCES)[number];

/** Row of public.alert_rules. Times as PostgREST returns them ('17:00:00'). */
export interface AlertRuleRow {
	user_id: string;
	spot_id: string;
	enabled: boolean;
	min_kn: number | null;
	max_kn: number | null;
	dir_classes: DirClass[] | null;
	weekdays: number[] | null;
	earliest_local: string | null;
	latest_local: string | null;
	min_go_hours: number | null;
	days_ahead: number | null;
	updated_at: string;
}
export const ALERT_RULE_COLUMNS = [
	'user_id',
	'spot_id',
	'enabled',
	'min_kn',
	'max_kn',
	'dir_classes',
	'weekdays',
	'earliest_local',
	'latest_local',
	'min_go_hours',
	'days_ahead',
	'updated_at'
] as const;
export type AlertRuleValues = Pick<AlertRuleRow, RuleField>;

/** One item of data/contracts/alert_defaults.json (WP-07). A = element type of `allowed`. */
export interface AlertDefaultItem<T, A extends string | number = string | number> {
	field: RuleField;
	label_nl: string;
	default: T;
	sources: RuleSource[];
	min: number | null;
	max: number | null;
	allowed: A[] | null;
	min_span_kn: number | null;
}
/** An item whose `allowed` list is guaranteed by parseAlertDefaults. */
export type AlertDefaultChoiceItem<T, A extends string | number> = AlertDefaultItem<T, A> & {
	allowed: A[];
};
export interface AlertDefaults {
	enabled: AlertDefaultItem<boolean>;
	min_kn: AlertDefaultItem<number>;
	max_kn: AlertDefaultItem<number>;
	dir_classes: AlertDefaultChoiceItem<DirClass[], DirClass>;
	weekdays: AlertDefaultChoiceItem<number[], number>;
	earliest_local: AlertDefaultItem<null>;
	latest_local: AlertDefaultItem<null>;
	min_go_hours: AlertDefaultItem<number>;
	days_ahead: AlertDefaultItem<number>;
}

/** Row of public.marine_hours (all columns). Display only (WP-12). */
export interface MarineHour {
	spot_id: string;
	valid_at: string;
	wave_height_m: number | null;
	wave_period_s: number | null;
	wave_dir_deg: number | null;
	fetched_at: string;
}

export const MARINE_HOUR_COLUMNS = [
	'spot_id',
	'valid_at',
	'wave_height_m',
	'wave_period_s',
	'wave_dir_deg',
	'fetched_at'
] as const;

/** Columns of push_subscriptions the PWA reads (own rows only, RLS). */
export const PUSH_SUBSCRIPTION_COLUMNS = ['id', 'endpoint', 'created_at'] as const;
export interface OwnPushSubscription {
	id: string;
	endpoint: string;
	created_at: string;
}
/** Exactly the columns the PWA inserts; user_id comes from the column default auth.uid() (WP-17). */
export interface PushSubscriptionKeys {
	endpoint: string;
	p256dh: string;
	auth: string;
}
