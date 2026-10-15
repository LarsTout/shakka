import { RETURN_TO_TTL_MS } from './local-prefs.js';

// Retention periods shown on /privacy. test/retention-consistency.test.ts compares them with the ingest
// (Python timedelta constants) and the sessions migration. Change the implementation and this file together.
export const FORECAST_RETENTION_HOURS = 48; // forecast_hours, marine_hours, tide_extremes, evaluations
export const ALERT_STATE_RETENTION_HOURS = 48; // alert_state rows, counted from window_end
export const RETURN_TO_TTL_MINUTES = RETURN_TO_TTL_MS / 60_000; // shakka:return_to

// Supabase Free plan log retention (supabase.com/pricing, checked 2026-10-15). Valid only when
// "Write audit logs to the database" is off (docs/PRIVACY.md, RUNBOOK).
export const SUPABASE_API_LOG_RETENTION_NL = '1 dag';
export const SUPABASE_AUTH_LOG_RETENTION_NL = '1 uur';

/** Contact address for privacy questions; null until Lars chooses one (blueprint A14). */
export const PRIVACY_CONTACT_EMAIL: string | null = null;

/** Date of the current privacy text, Dutch long format. */
export const PRIVACY_UPDATED_NL = '15 oktober 2026';
