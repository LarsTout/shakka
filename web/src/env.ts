import { defineEnvVars } from '@sveltejs/kit/env';
import { parseMaptilerKey, parsePublishableKey, parseSupabaseUrl } from './lib/env-schema.js';

export const variables = defineEnvVars({
	PUBLIC_SUPABASE_URL: {
		public: true,
		static: true,
		schema: parseSupabaseUrl,
		description: 'Supabase project URL without path, e.g. https://<ref>.supabase.co'
	},
	PUBLIC_SUPABASE_PUBLISHABLE_KEY: {
		public: true,
		static: true,
		schema: parsePublishableKey,
		description: 'Supabase publishable key (sb_publishable_...). Never the secret key.'
	},
	PUBLIC_MAPTILER_KEY: {
		public: true,
		static: true,
		schema: parseMaptilerKey,
		description:
			'MapTiler API key (public, restricted to allowed HTTP origins). Optional: empty = map unavailable, list keeps working.'
	}
});
