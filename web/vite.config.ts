import adapter from '@sveltejs/adapter-static';
import { sveltekit } from '@sveltejs/kit/vite';
import { svelteTesting } from '@testing-library/svelte/vite';
import { defineConfig } from 'vitest/config';

// Placeholders so tests never need web/.env. Tests mock #lib/supabase.js; nothing talks to this URL.
const TEST_ENV: Record<string, string> = {
	PUBLIC_SUPABASE_URL: 'http://127.0.0.1:54321',
	PUBLIC_SUPABASE_PUBLISHABLE_KEY: 'sb_publishable_test'
};

export default defineConfig(({ mode }) => {
	if (mode === 'test') {
		for (const [key, value] of Object.entries(TEST_ENV)) process.env[key] ??= value;
	}
	return {
		plugins: [
			sveltekit({
				compilerOptions: {
					// Force runes mode for the project, except for libraries. Can be removed in svelte 6.
					runes: ({ filename }) =>
						filename.split(/[/\\]/).includes('node_modules') ? undefined : true
				},
				adapter: adapter({
					pages: 'build',
					assets: 'build',
					fallback: 'index.html',
					precompress: false,
					strict: true
				}),
				// Registered by #lib/sw-register.js (testable, never in dev).
				serviceWorker: { register: false },
				// Poll for a new app version hourly (default is 0 = never); see deviations.md (N-3).
				version: { pollInterval: 3_600_000 }
			}),
			svelteTesting()
		],
		test: {
			environment: 'jsdom',
			include: ['test/**/*.test.ts'],
			setupFiles: ['./test/setup.ts']
		}
	};
});
