import { createClient, type SupabaseClient } from '@supabase/supabase-js';
import { PUBLIC_SUPABASE_PUBLISHABLE_KEY, PUBLIC_SUPABASE_URL } from '$app/env/public';

/** URL fragment at load time, captured before supabase-js consumes it (used for magic-link error messages). */
export const initialUrlHash: string = typeof window === 'undefined' ? '' : window.location.hash;

/** The only Supabase client in the app. Publishable key only; RLS protects the data. */
export const supabase: SupabaseClient = createClient(
	PUBLIC_SUPABASE_URL,
	PUBLIC_SUPABASE_PUBLISHABLE_KEY,
	{
		auth: {
			flowType: 'implicit',
			persistSession: true,
			autoRefreshToken: true,
			detectSessionInUrl: true
		}
	}
);

/** Origin of the Supabase project (validated by env-schema); used to recognise pasted login links. */
export const supabaseOrigin: string = PUBLIC_SUPABASE_URL;
