# Blueprint WP-13: PWA-basis
Status: DRAFT
Revisie: 1

## Doel
Een installeerbare SvelteKit-PWA in `/web` die als statische SPA op Cloudflare Pages draait, met:
- magic-link-login via Supabase Auth (alleen de publishable key);
- een layout met header (loginstatus) en een footer met `Attribution` op elke pagina;
- de routes `/`, `/login` en `/over`;
- een manifest en een service worker die alleen de app-shell precachet en nooit Supabase-responses cachet;
- een CI-job `web` met `check`, `test`, `build`, een buildcontrole en de guard `scripts/check-no-client-openmeteo.sh`.

Na deze WP kunnen WP-14 (spotlijst), WP-16 en WP-18 op deze basis bouwen.

## Aannames
Voorstellen waar Lars op kan reageren staan als **Voorstel**.

- A1. **Voorstel: SvelteKit 3, niet 2.** SvelteKit 3.0 is uitgebracht op 1 oktober 2026; `latest` op npm is 3.0.1. Dit is een nieuw project en alle latere web-WP's (WP-14 t/m WP-23) bouwen erop voort. Met kit 2 zou er later een migratie-WP nodig zijn. Gevolgen, allemaal uit de officiële migratiegids:
  - de configuratie staat in `vite.config.ts` (`sveltekit({...})`), er is geen `svelte.config.js` meer;
  - `$lib` heet `#lib` (subpath imports in `package.json`), en imports krijgen een extensie: `#lib/auth.js`;
  - `$env/static/public` is deprecated. Publieke variabelen worden gedeclareerd in `src/env.ts` met `defineEnvVars` en geïmporteerd uit `$app/env/public`. Met `public: true, static: true` worden ze tijdens de build ingevuld, net als `$env/static/public`. **Dit wijkt af van de letterlijke contractregel in WORK_PACKAGES** ("via `$env/static/public`"). De bedoeling blijft gelijk: alleen publieke waarden, vastgelegd tijdens de build.
  - de service worker staat in `src/service-worker/index.ts` (niet `src/service-worker.ts`). Hij gebruikt `$app/service-worker`, `$app/env`, `$app/manifest` en `$app/paths`, en wordt als module geregistreerd.

  Kiest Lars toch voor kit 2, dan moet deze blueprint opnieuw door de planner.
- A2. **Voorstel: Node 24 LTS ("Krypton", nu 24.22.0).** `web/.nvmrc` bevat `24`. Kit 3 vereist Node ≥ 22.17, jsdom 30 vereist ^24.15.0. Het standaard-buildimage v3 van Cloudflare Pages draait Node 22.16.0; dat is te oud. Lars moet daarom in Pages `NODE_VERSION=24.22.0` zetten (volledige versie, zoals in het voorbeeld in de Cloudflare-docs).
- A3. **Voorstel: placeholder-icoon.** Een script (`web/scripts/make-placeholder-icons.mjs`, alleen Node-stdlib) maakt PNG's: een blauw vlak (`#0b5e8a`) met een witte vlieger-ruit. Lars kan de PNG's later vervangen door een eigen ontwerp met dezelfde bestandsnamen en afmetingen; er hoeft dan niets anders te veranderen.
- A4. **Implicit flow (de standaard van supabase-js) in plaats van PKCE.** Bij PKCE moet de link geopend worden in dezelfde browser waarin hij is aangevraagd. Bij een mailapp met een eigen in-app-browser gaat dat mis. Bij de implicit flow staan de tokens in het URL-fragment, en dat gaat nooit naar een server. `flowType: 'implicit'` wordt expliciet gezet, zodat een latere wijziging van de standaard niets verandert.
- A5. **Aanmelden blijft open** (`shouldCreateUser` wordt niet meegegeven, de standaard is `true`). In M2 mailt de standaard-SMTP alleen naar teamleden van het Supabase-project (max. 2 per uur). Iemand anders krijgt de Nederlandse melding bij `email_address_not_authorized`. Aanmelden beperken en eigen SMTP horen bij WP-22.
- A6. **Voorstel: nu geen inlogcode (OTP) naast de link.** Een code in de mail vereist een aangepast e-mailtemplate. Nieuwe free-tier-projecten (aangemaakt na 3 juni 2026, zoals dat van Lars op 14 oktober) kunnen templates niet meer aanpassen zolang ze de standaard-SMTP gebruiken. Voorstel: inloggen met een code toevoegen zodra er eigen SMTP is (WP-22), of eerder als WP-18 dat voor iOS nodig heeft (zie R3).
- A7. **Service worker zonder runtime-caching.** Hij precachet alleen de app-shell (Vite-output, `static/` en `/`). Navigatie gaat eerst naar het netwerk en valt offline terug op de gecachete shell. Requests naar een andere origin (Supabase, later MapTiler) en alle niet-GET-requests worden niet onderschept. Er is geen `skipWaiting`: een nieuwe versie wordt actief als alle vensters van de app dicht zijn. Zo passen oude shell en oude chunks altijd bij elkaar.
- A8. **Registratie in eigen code** (`serviceWorker: { register: false }` en `registerServiceWorker()` in de root-layout). Daardoor is de registratie te testen (AC-2) en is uit te sluiten dat de SW tijdens `vite dev` cachet: in dev wordt niet geregistreerd.
- A9. **Lokale Auth-URL's.** In `supabase/config.toml` worden `site_url` en `additional_redirect_urls` op de Vite-devserver (`http://localhost:5173`) gezet, zodat magic links lokaal via Mailpit werken. Dat raakt alleen de lokale stack.
- A10. **Cloudflare-projectnaam.** De RUNBOOK gebruikt `<project>` als placeholder (voorstel: `shakka`, dus `https://shakka.pages.dev`). Is die naam bezet, dan kiest Lars een andere; de code hangt er niet van af.
- A11. **`@supabase/supabase-js` staat in `dependencies`**, de rest in `devDependencies`. Zo controleert `npm audit --omit=dev` (WP-22, AC-5) precies de code die naar de browser gaat.
- A12. **De header toont het eigen e-mailadres** als je ingelogd bent. Het staat alleen op je eigen apparaat en er gaat niets naar derden.
- A13. **Geen ESLint en Prettier** in deze WP. De WP vraagt om `check`, `test` en `build`. `check` doet `svelte-check` plus een typecheck van de service worker.

## Ontwerp

**Statische SPA.** `@sveltejs/adapter-static` 4 met `fallback: 'index.html'`. In `src/routes/+layout.ts` staan `ssr = false` en `prerender = false`; er wordt geen enkele pagina geprerenderd. Daardoor is `build/index.html` de app-shell voor elke route (AC-2), en is er geen conflict tussen prerender en fallback (de SvelteKit-docs waarschuwen voor `index.html` als fallback samen met prerenderen). Cloudflare Pages gedraagt zich als SPA zolang er geen top-level `404.html` is: onbekende paden krijgen `/`. `verify-build` controleert daarom dat `build/404.html` ontbreekt.

**Omgevingsvariabelen.** `src/env.ts` declareert `PUBLIC_SUPABASE_URL` en `PUBLIC_SUPABASE_PUBLISHABLE_KEY` met `public: true, static: true` en een eigen schemafunctie uit `src/lib/env-schema.ts`. Die functies:
- weigeren lege waarden;
- weigeren een URL met pad of een niet-https-URL (behalve localhost en 127.0.0.1);
- weigeren elke sleutel die niet met `sb_publishable_` begint, en geven een expliciete fout bij `sb_secret_`.

Een ontbrekende of foute waarde laat de build dus falen met een duidelijke melding. De waarde zelf staat nooit in de melding. Zo kan de secret key niet per ongeluk in de browserbundel komen. CI zet onschuldige placeholders (`http://127.0.0.1:54321` en `sb_publishable_ci`). Onder vitest (`mode === 'test'`) zet `vite.config.ts` dezelfde placeholders als ze ontbreken, zodat tests geen `web/.env` nodig hebben.

**Auth.** `src/lib/supabase.ts` maakt één client met de publishable key (`flowType: 'implicit'`, `persistSession`, `autoRefreshToken`, `detectSessionInUrl`). Vóór `createClient` legt het `initialUrlHash` vast. supabase-js verwerkt het fragment asynchroon na het laden van de module, dus zo is een foutfragment van een verlopen link (`#error=…&error_code=otp_expired`) nog betrouwbaar te lezen. `src/lib/auth.ts` heeft:
- een store `session` met drie toestanden: `undefined` (nog onbekend), `null` (uitgelogd) en `Session`;
- `initAuth()`, dat zich abonneert op `onAuthStateChange` (dat ook `INITIAL_SESSION` levert);
- `signInWithMagicLink()`, dat het adres trimt, valideert, `signInWithOtp` aanroept met `emailRedirectTo = window.location.origin` en elke fout omzet in een vaste Nederlandse melding;
- `signOut()` met `scope: 'local'`, zodat je alleen op dit apparaat uitlogt.

De root-layout roept `initAuth()` aan in `onMount`.

**Layout en pagina's.** De header heeft de merknaam (link naar `/`), "Over" en de loginstatus: niets zolang de toestand onbekend is (geen flikkering), "Inloggen" als je uitgelogd bent, of je e-mailadres met "Uitloggen". De footer bevat `<Attribution compact />` en een link naar `/over`. `Attribution` toont in beide standen dezelfde links:
- Open-Meteo met de tekst "Weather data by Open-Meteo.com", zoals de licentiepagina voorschrijft;
- CC BY 4.0;
- KNMI, DWD, ECMWF en NOAA;
- Rijkswaterstaat (CC0).

De volledige stand vermeldt ook dat Shakka de data bewerkt. CC BY vraagt om "indicate if changes were made".

**Service worker.** De logica staat in `src/lib/sw/shell.ts`, met structurele types (`WaitUntilEvent`, `FetchLikeEvent`) en geïnjecteerde `caches` en `fetch`. Daardoor typecheckt het bestand zowel onder de DOM-config als onder de service-worker-config, en is het in vitest (Node-omgeving) te testen met een nep-CacheStorage. `src/service-worker/index.ts` is alleen bedrading. De cache heet `shakka-shell-${version}`. Bij `activate` worden alleen oude caches met het prefix `shakka-shell-` verwijderd. WP-18 voegt in hetzelfde `index.ts` de `push`- en `notificationclick`-handlers toe.

**Guards.**
- `scripts/check-no-client-openmeteo.sh` (repo-root, bash, grep) scant standaard `web/src`, `web/static` en (als die bestaat) `web/build`. Met argumenten scant het precies die paden; dat maakt de fixturetest van AC-3 mogelijk.
- `web/scripts/verify-build.mjs` controleert na de build `index.html`, het ontbreken van `404.html`, het manifest, de iconen, `service-worker.js`, externe scripts in `index.html` en trackerpatronen in `src` en `static` (AC-2 en AC-6).
- De vitest-test `no-third-party` doet dezelfde trackerscan al tijdens `npm test`.

**Waarom zo.** Elke regel die een randvoorwaarde bewaakt (geen Open-Meteo in de client, bronvermelding, geen trackers of CDN's, alleen de publishable key) is een geautomatiseerde test of een CI-stap. Geen van die regels hangt alleen af van discipline.

## Bestanden

| Pad | Actie | Inhoud |
|---|---|---|
| `web/package.json` | aanmaken | Zie Interfaces (exact). |
| `web/package-lock.json` | aanmaken | Door `npm install` (lockfile v3). Wordt gecommit. |
| `web/.npmrc` | aanmaken | `engine-strict=true` |
| `web/.nvmrc` | aanmaken | `24` |
| `web/.env.example` | aanmaken | Zie Interfaces (exact). |
| `web/vite.config.ts` | aanmaken | Zie Interfaces (exact). |
| `web/tsconfig.json` | aanmaken | Zie Interfaces (exact). |
| `web/src/app.html` | aanmaken | Zie Interfaces (exact). |
| `web/src/app.d.ts` | aanmaken | Kopie van het sv-template (lege `App`-namespace, `export {}`). |
| `web/src/app.css` | aanmaken | Minimale stijl, zie "Stijl". Geen webfonts. |
| `web/src/env.ts` | aanmaken | `defineEnvVars` met de twee variabelen. |
| `web/src/lib/index.ts` | aanmaken | `// Shared code is imported via #lib/<file>.js` plus `export {};` (doel van de `#lib`-entry). |
| `web/src/lib/env-schema.ts` | aanmaken | `parseSupabaseUrl`, `parsePublishableKey`. |
| `web/src/lib/supabase.ts` | aanmaken | `initialUrlHash` en `supabase`. |
| `web/src/lib/auth.ts` | aanmaken | `AUTH_MESSAGES`, `session`, `initAuth`, `signInWithMagicLink`, `signOut`, `authErrorMessage`, `parseAuthRedirectError`, `initialAuthRedirectError`. |
| `web/src/lib/sw-register.ts` | aanmaken | `SERVICE_WORKER_URL`, `registerServiceWorker`. |
| `web/src/lib/sw/shell.ts` | aanmaken | Strategie en handlers van de service worker. |
| `web/src/lib/components/Attribution.svelte` | aanmaken | Prop `compact?: boolean`. |
| `web/src/routes/+layout.ts` | aanmaken | `export const ssr = false; export const prerender = false;` |
| `web/src/routes/+layout.svelte` | aanmaken | Header, foutbanner bij de magic link, `main`, footer, `onMount`. |
| `web/src/routes/+page.svelte` | aanmaken | Placeholder (WP-14 vervangt deze). |
| `web/src/routes/login/+page.svelte` | aanmaken | Loginformulier. |
| `web/src/routes/over/+page.svelte` | aanmaken | Uitleg en volledige `Attribution`. |
| `web/src/service-worker/index.ts` | aanmaken | Bedrading van `shell.ts`. |
| `web/src/service-worker/tsconfig.json` | aanmaken | `{ "extends": "$app/tsconfig/service-worker" }` |
| `web/static/manifest.webmanifest` | aanmaken | Zie Interfaces (exact). |
| `web/static/favicon.svg` | aanmaken | Zie Interfaces (exact). |
| `web/static/icons/icon-192.png`, `icon-512.png`, `icon-maskable-192.png`, `icon-maskable-512.png`, `apple-touch-icon.png` | aanmaken | Gegenereerd door `npm run icons` en gecommit. |
| `web/scripts/make-placeholder-icons.mjs` | aanmaken | PNG-generator (alleen `node:zlib`, `node:fs`, `node:path`, `node:url`). |
| `web/scripts/verify-build.mjs` | aanmaken | Buildcontrole, exporteert pure functies. |
| `web/test/setup.ts` | aanmaken | `import '@testing-library/jest-dom/vitest';` |
| `web/test/helpers/fake-cache.ts` | aanmaken | `FakeCacheStorage`, `FakeCache` voor de SW-tests. |
| `web/test/*.test.ts` | aanmaken | Zie Testplan (11 bestanden). |
| `scripts/check-no-client-openmeteo.sh` | aanmaken | Guard (exact, zie Interfaces). Git-modus 100755. |
| `.github/workflows/ci.yml` | wijzigen | Job `web` toevoegen. `ingest` en `db` blijven ongewijzigd. |
| `ingest/tests/test_repo_hygiene.py` | wijzigen | `test_ci_workflow_contract` uitbreiden met de regels van job `web`. |
| `supabase/config.toml` | wijzigen | Alleen in `[auth]`: `site_url` en `additional_redirect_urls` (zie Interfaces). |
| `docs/RUNBOOK.md` | wijzigen | Secties 1, 4 en 7 aanvullen, nieuwe sectie 9 "Web-app (PWA)" (zie Interfaces). |

Geen andere bestanden. `.gitignore` hoeft niet te veranderen: `.env` en `.env.*` (behalve `.env.example`), `node_modules/`, `web/.svelte-kit/` en `web/build/` staan er al in. `docs/STATUS.md` werkt de orchestrator bij.

## Interfaces en contracten

### `web/package.json` (exact, behalve dat `npm install` versies binnen de ranges vastlegt in de lockfile)
```json
{
	"name": "shakka-web",
	"private": true,
	"version": "0.0.1",
	"type": "module",
	"engines": {
		"node": "^24.15.0 || >=26.0.0"
	},
	"scripts": {
		"dev": "vite dev",
		"build": "vite build",
		"preview": "vite preview",
		"prepare": "svelte-kit sync || echo ''",
		"check": "svelte-kit sync && svelte-check --tsconfig ./tsconfig.json && tsc -p src/service-worker/tsconfig.json --noEmit",
		"test": "vitest run",
		"verify:build": "node scripts/verify-build.mjs",
		"icons": "node scripts/make-placeholder-icons.mjs"
	},
	"dependencies": {
		"@supabase/supabase-js": "^2.117.3"
	},
	"devDependencies": {
		"@sveltejs/adapter-static": "^4.0.0",
		"@sveltejs/kit": "^3.0.1",
		"@sveltejs/vite-plugin-svelte": "^7.3.1",
		"@testing-library/dom": "^10.4.2",
		"@testing-library/jest-dom": "^7.0.1",
		"@testing-library/svelte": "^5.4.2",
		"@testing-library/user-event": "^14.6.8",
		"@types/node": "^24.0.0",
		"jsdom": "^30.1.2",
		"svelte": "^5.57.2",
		"svelte-check": "^4.7.6",
		"typescript": "^6.0.3",
		"vite": "^8.3.4",
		"vitest": "^5.0.4"
	},
	"imports": {
		"#lib": "./src/lib/index.js",
		"#lib/*": "./src/lib/*"
	}
}
```
TypeScript blijft bewust op 6.x: kit 3 heeft peer `typescript ^6.0.0` en svelte-check `^5 || ^6`. `latest` op npm is 7.0.2, en die past daar niet bij.

### `web/.env.example` (exact)
```
# Copy to web/.env and fill in. web/.env is gitignored. See docs/RUNBOOK.md section 9.
# Supabase project URL without path, e.g. https://<project-ref>.supabase.co (local stack: http://127.0.0.1:54321)
PUBLIC_SUPABASE_URL=
# Publishable key (starts with sb_publishable_). Never the secret key.
PUBLIC_SUPABASE_PUBLISHABLE_KEY=
```

### `web/vite.config.ts` (exact)
```ts
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
				serviceWorker: { register: false }
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
```

### `web/tsconfig.json` (exact)
```json
{
	"extends": "$app/tsconfig",
	"compilerOptions": {
		"strict": true,
		"allowJs": true,
		"checkJs": true
	},
	"include": ["src", "test", "vite.config.ts"],
	"exclude": ["src/service-worker"]
}
```
`paths`, `types`, `isolatedModules` en `verbatimModuleSyntax` worden niet overschreven; dat verbiedt `$app/tsconfig`. `allowJs` en `checkJs` zijn nodig omdat `test/verify-build.test.ts` `scripts/verify-build.mjs` importeert (JSDoc-types).

### `web/src/app.html` (exact)
```html
<!doctype html>
<html lang="nl">
	<head>
		<meta charset="utf-8" />
		<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover" />
		<meta name="text-scale" content="scale" />
		<meta name="description" content="Shakka: per kitespot zien of je kunt kiten." />
		<meta name="theme-color" content="#0b5e8a" />
		<meta name="apple-mobile-web-app-title" content="Shakka" />
		<link rel="manifest" href="/manifest.webmanifest" />
		<link rel="icon" href="/favicon.svg" type="image/svg+xml" />
		<link rel="apple-touch-icon" href="/icons/apple-touch-icon.png" />
		%sveltekit.head%
	</head>
	<body data-sveltekit-preload-data="hover">
		<div style="display: contents">%sveltekit.body%</div>
	</body>
</html>
```
Paden zijn absoluut (`/…`), want `paths.base` is leeg en de fallbackpagina gebruikt altijd absolute paden. Titels komen per pagina uit `<svelte:head>`.

### `web/src/env.ts`
```ts
import { defineEnvVars } from '@sveltejs/kit/env';
import { parsePublishableKey, parseSupabaseUrl } from './lib/env-schema.js';

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
	}
});
```
Kan SvelteKit `src/env.ts` niet laden met een relatieve import, dan zet de builder beide functies letterlijk in `src/env.ts` en laat `src/lib/env-schema.ts` ze daar re-exporteren (`export { parseSupabaseUrl, parsePublishableKey } from '../env.js'`). Dat noteert hij in `deviations.md`; aan het ontwerp verandert niets.

### `web/src/lib/env-schema.ts`
```ts
/** Validates PUBLIC_SUPABASE_URL. Returns the normalised origin (no trailing slash). Never echoes the value. */
export function parseSupabaseUrl(value: string | undefined): string;
/** Validates PUBLIC_SUPABASE_PUBLISHABLE_KEY. Returns the trimmed key. Never echoes the value. */
export function parsePublishableKey(value: string | undefined): string;
```
Regels voor `parseSupabaseUrl` (bij een fout volgt `throw new Error(<melding>)`):

| Invoer | Uitkomst |
|---|---|
| `undefined`, `''` of alleen witruimte | `PUBLIC_SUPABASE_URL is missing: copy web/.env.example to web/.env (see docs/RUNBOOK.md)` |
| `new URL()` faalt | `PUBLIC_SUPABASE_URL is not a valid URL` |
| protocol niet `https:` en niet (`http:` met hostname `localhost` of `127.0.0.1`) | `PUBLIC_SUPABASE_URL must use https (http only for localhost)` |
| `pathname !== '/'`, of `search`/`hash` niet leeg, of `username`/`password` gezet | `PUBLIC_SUPABASE_URL must be the project URL without path` |
| anders | `url.origin`, bijv. `https://abc.supabase.co` |

Regels voor `parsePublishableKey`:

| Invoer | Uitkomst |
|---|---|
| leeg of witruimte | `PUBLIC_SUPABASE_PUBLISHABLE_KEY is missing: copy web/.env.example to web/.env (see docs/RUNBOOK.md)` |
| begint (na trim) met `sb_secret_` | `PUBLIC_SUPABASE_PUBLISHABLE_KEY must be the publishable key, never the secret key` |
| begint niet met `sb_publishable_`, of bevat witruimte na trim | `PUBLIC_SUPABASE_PUBLISHABLE_KEY must start with sb_publishable_` |
| anders | de getrimde sleutel |

### `web/src/lib/supabase.ts`
```ts
import { createClient, type SupabaseClient } from '@supabase/supabase-js';
import { PUBLIC_SUPABASE_PUBLISHABLE_KEY, PUBLIC_SUPABASE_URL } from '$app/env/public';

/** URL fragment at load time, captured before supabase-js consumes it (used for magic-link error messages). */
export const initialUrlHash: string = typeof window === 'undefined' ? '' : window.location.hash;

/** The only Supabase client in the app. Publishable key only; RLS protects the data. */
export const supabase: SupabaseClient = createClient(PUBLIC_SUPABASE_URL, PUBLIC_SUPABASE_PUBLISHABLE_KEY, {
	auth: {
		flowType: 'implicit',
		persistSession: true,
		autoRefreshToken: true,
		detectSessionInUrl: true
	}
});
```
De volgorde ligt vast: `initialUrlHash` staat vóór `createClient`. Database-typegeneratie hoort bij WP-14.

### `web/src/lib/auth.ts`
```ts
import type { Session } from '@supabase/supabase-js';
import type { Readable } from 'svelte/store';

export const AUTH_MESSAGES = {
	invalidEmail: 'Vul een geldig e-mailadres in.',
	rateLimited: 'Te veel inlogpogingen. Wacht een paar minuten en probeer het opnieuw.',
	notAuthorized: 'Met dit e-mailadres kun je nog niet inloggen. Shakka is nog in de testfase.',
	network: 'Geen verbinding met de server. Controleer je internet en probeer het opnieuw.',
	generic: 'Het versturen van de inloglink is niet gelukt. Probeer het later opnieuw.',
	linkExpired: 'Deze inloglink is verlopen of al gebruikt. Vraag een nieuwe aan.',
	linkFailed: 'Inloggen via de link is niet gelukt. Vraag een nieuwe inloglink aan.'
} as const;

/** undefined = not known yet (auth initialising), null = signed out. */
export const session: Readable<Session | null | undefined>;

/** Subscribes the session store to supabase.auth.onAuthStateChange (idempotent).
 *  Returns a teardown that unsubscribes and resets the store to undefined. */
export function initAuth(): () => void;

/** Sends a magic link. emailRedirectTo is window.location.origin. Never throws.
 *  Returns {} on success or { error } with one of AUTH_MESSAGES. */
export function signInWithMagicLink(email: string): Promise<{ error?: string }>;

/** Signs out on this device only (scope 'local'). Never throws; logs a warning on error. */
export function signOut(): Promise<void>;

/** Maps a supabase-js auth error (or anything thrown) to a Dutch message. */
export function authErrorMessage(error: unknown): string;

/** Parses a magic-link redirect fragment such as '#error=access_denied&error_code=otp_expired&...'.
 *  Returns a Dutch message, or null when the fragment carries no error. */
export function parseAuthRedirectError(hash: string): string | null;

/** parseAuthRedirectError(initialUrlHash) */
export function initialAuthRedirectError(): string | null;
```
Gedrag:
- `session` is intern een `writable(undefined)`. Naar buiten gaat alleen `{ subscribe }`.
- `initAuth()` roept `supabase.auth.onAuthStateChange((_event, s) => store.set(s))` aan. Het callback is synchroon en roept geen andere Supabase-functies aan. Een tweede aanroep zolang de eerste actief is, abonneert niet opnieuw. De teardown roept `data.subscription.unsubscribe()` aan en zet de store op `undefined`.
- `signInWithMagicLink(email)`:
  1. `const address = email.trim()`;
  2. matcht `address` niet op `/^[^\s@]+@[^\s@]+\.[^\s@]+$/`, dan volgt `{ error: AUTH_MESSAGES.invalidEmail }` zonder aanroep;
  3. anders `await supabase.auth.signInWithOtp({ email: address, options: { emailRedirectTo: window.location.origin } })`. Precies dit object, zonder extra opties;
  4. is `error` gezet, dan volgt `{ error: authErrorMessage(error) }`, anders `{}`;
  5. gooit de aanroep, dan volgt `{ error: AUTH_MESSAGES.network }`.
- `authErrorMessage(error)` (lees `name`, `status` en `code` defensief; geen object geeft `generic`):
  - `name === 'AuthRetryableFetchError'` of `status === 0` geeft `network`;
  - `status === 429`, `code === 'over_email_send_rate_limit'` of `code === 'over_request_rate_limit'` geeft `rateLimited`;
  - `code === 'email_address_not_authorized'` geeft `notAuthorized`;
  - `code === 'email_address_invalid'` of `code === 'validation_failed'` geeft `invalidEmail`;
  - anders `generic`.
- `parseAuthRedirectError(hash)`:
  - haal een leidende `#` weg en parse met `URLSearchParams`;
  - geen `error` en geen `error_code` geeft `null`;
  - `error_code === 'otp_expired'` geeft `linkExpired`;
  - anders `linkFailed`.

  `error_description` wordt nooit getoond (Engels, en vrije tekst van buiten).
- `signOut()`: `const { error } = await supabase.auth.signOut({ scope: 'local' })`. Bij een fout volgt `console.warn('signOut failed')` zonder details. De store volgt via het `SIGNED_OUT`-event.

### `web/src/lib/sw-register.ts`
```ts
export const SERVICE_WORKER_URL = '/service-worker.js';

export interface ServiceWorkerHost {
	serviceWorker?: Pick<ServiceWorkerContainer, 'register'>;
}

/** Registers the SvelteKit service worker as a module. No-op (null) when disabled
 *  (dev/test), when nav is undefined, or when service workers are unsupported.
 *  Registration errors are caught (console.warn) and give null; never throws. */
export async function registerServiceWorker(
	nav: ServiceWorkerHost | undefined,
	enabled: boolean
): Promise<ServiceWorkerRegistration | null>;
```
Bij `enabled && nav?.serviceWorker`: `nav.serviceWorker.register(SERVICE_WORKER_URL, { type: 'module', scope: '/' })`. Het type `module` volgt uit kit 3 ("SvelteKit will bundle and register your service worker as a module"). De layout roept `registerServiceWorker(navigator, import.meta.env.PROD)` aan.

### `web/src/lib/sw/shell.ts`
```ts
export const CACHE_PREFIX = 'shakka-shell-';
export const SHELL_PATH = '/';

export interface WaitUntilEvent { waitUntil(promise: Promise<unknown>): void }
export interface FetchLikeEvent { readonly request: Request; respondWith(response: Promise<Response>): void }
export type RequestKind = 'navigate' | 'precached' | 'passthrough';

/** Unique list of absolute paths to precache, always including shellPath. Order: input order, shell last if new. */
export function precacheList(paths: readonly string[], shellPath: string): string[];

/** Decides how the service worker treats a request. Order of rules:
 *  1. method !== 'GET'                      -> 'passthrough'
 *  2. new URL(url).origin !== origin        -> 'passthrough' (Supabase, MapTiler, ...: never cached)
 *  3. mode === 'navigate'                   -> 'navigate'
 *  4. precached.has(new URL(url).pathname)  -> 'precached'
 *  5. otherwise                             -> 'passthrough' */
export function classifyRequest(
	request: Pick<Request, 'url' | 'method' | 'mode'>,
	origin: string,
	precached: ReadonlySet<string>
): RequestKind;

export interface ShellDeps {
	cacheName: string;            // `${CACHE_PREFIX}${version}`
	precache: readonly string[];  // result of precacheList
	shellPath: string;            // SHELL_PATH
	origin: string;               // self.location.origin
	caches: Pick<CacheStorage, 'open' | 'keys' | 'delete'>;
	fetch: (request: Request) => Promise<Response>;
}

export function createShellHandlers(deps: ShellDeps): {
	onInstall(event: WaitUntilEvent): void;   // waitUntil(open(cacheName).addAll(precache))
	onActivate(event: WaitUntilEvent): void;  // waitUntil(delete every key that starts with CACHE_PREFIX and !== cacheName)
	onFetch(event: FetchLikeEvent): void;     // see below
};
```
`onFetch`:
- `passthrough`: geen `respondWith`, de browser handelt het zelf af;
- `precached`: `respondWith` met (cache `match(pathname)` ?? `deps.fetch(request)`);
- `navigate`: `respondWith` met `deps.fetch(request)`. Faalt die (reject), dan cache `match(shellPath)`; zonder shell in de cache wordt de oorspronkelijke fout opnieuw gegooid. Een HTTP-foutrespons (bijv. 500) komt ongewijzigd terug.

Er is nergens een `cache.put`. Er is geen `skipWaiting` en geen `clients.claim`.

### `web/src/service-worker/index.ts`
```ts
import { self } from '$app/service-worker';
import { version } from '$app/env';
import { immutable, assets } from '$app/manifest';
import { resolve } from '$app/paths';
import { CACHE_PREFIX, SHELL_PATH, createShellHandlers, precacheList } from '#lib/sw/shell.js';

const precache = precacheList(
	[...immutable.map((asset) => resolve(asset.path)), ...assets.map((asset) => resolve(asset.path))],
	SHELL_PATH
);

const handlers = createShellHandlers({
	cacheName: `${CACHE_PREFIX}${version}`,
	precache,
	shellPath: SHELL_PATH,
	origin: self.location.origin,
	caches: self.caches,
	fetch: (request) => self.fetch(request)
});

self.addEventListener('install', handlers.onInstall);
self.addEventListener('activate', handlers.onActivate);
self.addEventListener('fetch', handlers.onFetch);
// WP-18 adds the 'push' and 'notificationclick' handlers here.
```
`resolve(asset.path)` volgt het voorbeeld uit de SvelteKit-docs. De builder controleert na `npm run build` dat het bestand `build/service-worker.js` heet. Heet het anders, dan past hij `SERVICE_WORKER_URL` en `verify-build` aan en noteert dat in `deviations.md`.

### `web/src/lib/components/Attribution.svelte`
Props: `let { compact = false }: { compact?: boolean } = $props();`

Elke link krijgt `target="_blank" rel="noopener noreferrer"`. De links en teksten, in beide standen:

| Link-tekst | href |
|---|---|
| `Weather data by Open-Meteo.com` | `https://open-meteo.com/` |
| `CC BY 4.0` | `https://creativecommons.org/licenses/by/4.0/` |
| `KNMI` | `https://www.knmi.nl/` |
| `DWD` | `https://www.dwd.de/` |
| `ECMWF` | `https://www.ecmwf.int/` |
| `NOAA` | `https://www.noaa.gov/` |
| `Rijkswaterstaat` | `https://rijkswaterstaatdata.nl/waterdata/` |

Omhulsel: `<section class="attribution" aria-label="Bronvermelding">`.

Volledige stand (`compact=false`), drie `<p>`'s:
1. `[Weather data by Open-Meteo.com], gelicenseerd onder [CC BY 4.0]. Shakka rekent de data om naar knopen en beoordeelt ze per spot.`
2. `Weermodellen van [KNMI], [DWD], [ECMWF] en [NOAA], via Open-Meteo.`
3. `Getijdata: [Rijkswaterstaat] (CC0).`

Compacte stand (`compact=true`), één `<p class="compact">`:
`[Weather data by Open-Meteo.com] ([CC BY 4.0]) · Modellen: [KNMI], [DWD], [ECMWF], [NOAA] · Getij: [Rijkswaterstaat]`

### Routes
- `+layout.svelte`:
  - script: `import '../app.css'`, `Attribution`, `{ session, initAuth, signOut, initialAuthRedirectError } from '#lib/auth.js'`, `{ registerServiceWorker } from '#lib/sw-register.js'`; `let { children }: { children: Snippet } = $props()`; `let redirectError = $state<string | null>(null)`;
  - `onMount`: `redirectError = initialAuthRedirectError(); const stop = initAuth(); void registerServiceWorker(navigator, import.meta.env.PROD); return stop;`.

  Markup:
  ```svelte
  <header class="site-header">
  	<a class="brand" href="/">Shakka</a>
  	<nav aria-label="Hoofdmenu">
  		<a href="/over">Over</a>
  		{#if $session}
  			<span class="who">{$session.user.email}</span>
  			<button type="button" onclick={() => signOut()}>Uitloggen</button>
  		{:else if $session === null}
  			<a href="/login">Inloggen</a>
  		{/if}
  	</nav>
  </header>
  {#if redirectError}
  	<div class="banner" role="alert">
  		<p>{redirectError}</p>
  		<a href="/login">Nieuwe inloglink</a>
  		<button type="button" onclick={() => (redirectError = null)}>Sluiten</button>
  	</div>
  {/if}
  <main>{@render children()}</main>
  <footer class="site-footer">
  	<Attribution compact />
  	<p><a href="/over">Over Shakka en bronnen</a></p>
  </footer>
  ```
- `+page.svelte` (`/`): `<svelte:head><title>Shakka</title></svelte:head>`, `<h1>Shakka</h1>`, `<p>Hier komt straks het overzicht van alle spots.</p>`.
- `login/+page.svelte`: `<svelte:head><title>Inloggen · Shakka</title></svelte:head>`. Toestand: `email = $state('')`, `status = $state<'idle' | 'sending' | 'sent'>('idle')`, `error = $state<string | null>(null)`, `sentTo = $state('')`.
  - Als `$session` gezet is: `<h1>Inloggen</h1><p>Je bent ingelogd als {$session.user.email}.</p><p><a href="/">Naar de start</a></p>`.
  - Anders, als `status === 'sent'`: `<h1>Check je mail</h1><p>We hebben een inloglink gestuurd naar {sentTo}. Open de link op dit apparaat om in te loggen.</p>` en een knop `Ander e-mailadres` die `status = 'idle'` zet.
  - Anders: `<h1>Inloggen</h1>`, `<p>Je krijgt een link per mail. Een wachtwoord is niet nodig.</p>` en het formulier `<form novalidate onsubmit={submit}>` met:
    - `<label for="email">E-mailadres</label>`;
    - `<input id="email" name="email" type="email" autocomplete="email" inputmode="email" required bind:value={email} />`;
    - `<button type="submit" disabled={status === 'sending'}>`, met de tekst `Stuur inloglink`, of `Bezig met versturen…` tijdens het versturen;
    - als er een fout is: `<p role="alert" class="error">{error}</p>`.
  - `submit(e)`: `e.preventDefault()`. Doe niets als de status `sending` is. Anders `error = null; status = 'sending'; const result = await signInWithMagicLink(email)`:
    - bij `result.error`: `error = result.error; status = 'idle'`;
    - anders: `sentTo = email.trim(); status = 'sent'`.
- `over/+page.svelte`: `<svelte:head><title>Over · Shakka</title></svelte:head>`.
  - `<h1>Over Shakka</h1>`
  - `<p>Shakka is een gratis app voor kiters in Nederland. Per spot zie je of je kunt kiten, je krijgt een melding als het gaat waaien, en je deelt met één link dat je gaat.</p>`
  - `<h2>Hoe werkt het oordeel?</h2><p>Shakka combineert de windverwachting van meerdere weermodellen met het profiel van de spot: de windrichting ten opzichte van de kust, het getij, seizoensregels en daglicht. Bij aflandige of schuin aflandige wind is het oordeel altijd: niet gaan.</p>`
  - `<h2>Spotgegevens</h2><p>De spotprofielen zijn met de hand samengesteld. Een spot die nog niet is gecontroleerd, staat gemarkeerd als niet geverifieerd. Check ter plekke altijd de lokale regels.</p>`
  - `<h2>Geen advertenties, geen tracking</h2><p>Shakka heeft geen advertenties en gebruikt geen analytics of trackers van derden.</p>`
  - `<h2>Bronnen</h2><Attribution />`

### Stijl (`web/src/app.css`)
- Lettertype `system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif`. Geen `@import` en geen `url(http…)`.
- Variabelen: `--color-brand: #0b5e8a`, `--color-text: #1a1a1a`, `--color-muted: #555`, `--color-bg: #fff`, `--color-error: #a4161a`.
- `main` en de footer: `max-width: 40rem; margin: 0 auto; padding: 1rem`.
- `.site-header`: flex, `justify-content: space-between`, achtergrond `--color-brand`, witte tekst en links.
- `.site-footer` en `.compact`: `font-size: 0.875rem; color: var(--color-muted)`.
- Links onderstreept. `:focus-visible` krijgt een outline van 2px in `--color-brand` (in de header wit).
- `.banner`: lichte achtergrond `#fff4e5` met een rand. `.error`: kleur `--color-error`.

### `web/static/manifest.webmanifest` (exact)
```json
{
	"id": "/",
	"name": "Shakka",
	"short_name": "Shakka",
	"description": "Per kitespot zien of je kunt kiten.",
	"lang": "nl",
	"dir": "ltr",
	"start_url": "/",
	"scope": "/",
	"display": "standalone",
	"background_color": "#ffffff",
	"theme_color": "#0b5e8a",
	"icons": [
		{ "src": "/icons/icon-192.png", "sizes": "192x192", "type": "image/png", "purpose": "any" },
		{ "src": "/icons/icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any" },
		{ "src": "/icons/icon-maskable-192.png", "sizes": "192x192", "type": "image/png", "purpose": "maskable" },
		{ "src": "/icons/icon-maskable-512.png", "sizes": "512x512", "type": "image/png", "purpose": "maskable" }
	]
}
```

### `web/static/favicon.svg` (exact)
```svg
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><rect width="64" height="64" rx="12" fill="#0b5e8a"/><path d="M32 11.5 L46 32 L32 52.5 L18 32 Z" fill="#fff"/></svg>
```

### `web/scripts/make-placeholder-icons.mjs`
- Alleen `node:zlib` (`deflateSync` en `crc32`, beschikbaar sinds Node 22.2), `node:fs`, `node:path` en `node:url`. Schrijft naar `web/static/icons/` (pad relatief aan het script).
- PNG: signatuur `89 50 4E 47 0D 0A 1A 0A`, `IHDR` (breedte, hoogte, bitdiepte 8, kleurtype 2 (RGB), compressie 0, filter 0, interlace 0), `IDAT` (`deflateSync` van rijen met filterbyte 0 plus RGB), `IEND`. Elke chunk bestaat uit lengte (UInt32BE), type, data en `crc32(type+data)` (UInt32BE).
- Pixel `(x, y)` met middelpunt `c = (size-1)/2`: wit (`255,255,255`) als `|x-c|/hw + |y-c|/hh <= 1`, anders `#0b5e8a` (`11,94,138`).
  - `any`: `hw = 0.22*size`, `hh = 0.32*size`;
  - `maskable` en apple-touch: `hw = 0.16*size`, `hh = 0.24*size` (binnen de veilige zone met straal 0,4).
- Uitvoer: `icon-192.png` (any, 192), `icon-512.png` (any, 512), `icon-maskable-192.png`, `icon-maskable-512.png` en `apple-touch-icon.png` (maskable-verhouding, 180).

### `web/scripts/verify-build.mjs`
Met JSDoc-types (wordt gecontroleerd via `checkJs`). Exporteert pure functies en draait `main()` alleen als het bestand direct gestart wordt (`import.meta.url === pathToFileURL(process.argv[1]).href`).
```js
/** @param {unknown} manifest @returns {string[]} problems (empty = ok) */
export function checkManifest(manifest);
// name === 'Shakka'; display === 'standalone'; start_url === '/';
// icons contains sizes '192x192' and '512x512' with purpose 'any' (or no purpose),
// and '192x192' and '512x512' with purpose 'maskable'; every icon has type 'image/png'.

/** @param {string} html @returns {string[]} offending <script> tags */
export function findExternalScripts(html);
// matches /<script\b[^>]*\bsrc\s*=\s*["']?(?:https?:)?\/\//gi

/** @param {string} text @returns {string[]} matched tracker/CDN markers */
export function findTrackerRefs(text);
// markers: 'googletagmanager', 'google-analytics', 'plausible', 'fonts.googleapis', 'cdn.'
// (case-sensitive, same as the AC-6 grep)

/** @param {Uint8Array} buffer PNG file contents @returns {{ width: number, height: number }} read from IHDR
 *  (bytes 16-19 width, 20-23 height, big-endian); throws on a missing PNG signature. */
export function pngSize(buffer);
```
`main()` controleert, relatief aan `web/`:
1. `build/index.html` bestaat;
2. `build/404.html` bestaat **niet**;
3. `checkManifest(JSON.parse(build/manifest.webmanifest))` is leeg;
4. elk icoon uit het manifest bestaat onder `build/` en `pngSize` klopt met `sizes`;
5. `build/service-worker.js` bestaat;
6. `findExternalScripts(build/index.html)` is leeg;
7. `findTrackerRefs` is leeg voor elk tekstbestand onder `src/` en `static/` (extensies `.ts .js .svelte .html .css .json .webmanifest .svg .txt`).

Bij een fout volgt per probleem één regel op stderr en exitcode 1. Anders `verify-build: ok` en exitcode 0.

### `scripts/check-no-client-openmeteo.sh` (exact)
```bash
#!/usr/bin/env bash
# Fails when web code references Open-Meteo API hosts. Open-Meteo is called server-side only (ingest).
# Usage: check-no-client-openmeteo.sh [path ...]
#   no args: scans web/src, web/static and (if present) web/build of this repo.
# Exit: 0 clean, 1 forbidden reference found, 2 usage or grep error.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PATTERN='api\.open-meteo\.com|marine-api\.open-meteo\.com|open-meteo\.com/v1'

if [ "$#" -gt 0 ]; then
  targets=("$@")
  for t in "${targets[@]}"; do
    if [ ! -e "$t" ]; then
      echo "check-no-client-openmeteo: path not found: $t" >&2
      exit 2
    fi
  done
else
  targets=("$ROOT/web/src" "$ROOT/web/static")
  for t in "${targets[@]}"; do
    if [ ! -d "$t" ]; then
      echo "check-no-client-openmeteo: missing directory: $t" >&2
      exit 2
    fi
  done
  if [ -d "$ROOT/web/build" ]; then
    targets+=("$ROOT/web/build")
  else
    echo "check-no-client-openmeteo: web/build not found, skipped (run npm run build first)"
  fi
fi

set +e
matches="$(grep -rIniE --exclude-dir=node_modules "$PATTERN" "${targets[@]}")"
status=$?
set -e

if [ "$status" -eq 0 ]; then
  echo "$matches"
  echo "check-no-client-openmeteo: FAIL, Open-Meteo must only be called from /ingest" >&2
  exit 1
fi
if [ "$status" -eq 1 ]; then
  echo "check-no-client-openmeteo: ok"
  exit 0
fi
echo "check-no-client-openmeteo: grep failed" >&2
exit 2
```
`https://open-meteo.com/` (de attributielink) matcht bewust niet.

### `.github/workflows/ci.yml`: job `web` (toevoegen na `db`)
```yaml
  web:
    runs-on: ubuntu-latest
    timeout-minutes: 10
    defaults:
      run:
        working-directory: web
    env:
      # Non-secret placeholders: the build inlines public env vars; CI never talks to Supabase.
      PUBLIC_SUPABASE_URL: http://127.0.0.1:54321
      PUBLIC_SUPABASE_PUBLISHABLE_KEY: sb_publishable_ci
    steps:
      - uses: actions/checkout@v7
      - uses: actions/setup-node@v7
        with:
          node-version-file: web/.nvmrc
          cache: npm
          cache-dependency-path: web/package-lock.json
      - run: npm ci
      - run: npm run check
      - run: npm test
      - run: npm run build
      - run: npm run verify:build
      - run: bash ../scripts/check-no-client-openmeteo.sh
```
`sb_publishable_ci` heeft maar 2 tekens na het prefix en matcht dus niet op het secret-scanpatroon (`{20,}`) uit `test_no_keys_in_repo`.

### `ingest/tests/test_repo_hygiene.py`
In `test_ci_workflow_contract` komen de volgende regels bij de verwachte regels (na `"- run: supabase test db",`):
```python
        "web:",
        "working-directory: web",
        "- run: npm ci",
        "- run: npm run check",
        "- run: npm test",
        "- run: npm run build",
        "- run: npm run verify:build",
        "- run: bash ../scripts/check-no-client-openmeteo.sh",
```

### `supabase/config.toml` (alleen deze twee regels in `[auth]`)
```toml
site_url = "http://localhost:5173"
additional_redirect_urls = ["http://localhost:5173", "http://127.0.0.1:5173"]
```

### `docs/RUNBOOK.md`
- Sectie 1 "Vereisten": `- Node 24 LTS (bijv. via nvm: \`nvm install 24\`); \`web/.nvmrc\` bevat de versie. Vanaf WP-13.`
- Sectie 4: twee rijen toevoegen:
  - `PUBLIC_SUPABASE_URL`, `PUBLIC_SUPABASE_PUBLISHABLE_KEY` | `web/.env`, Cloudflare Pages | web | WP-13;
  - `NODE_VERSION` | Cloudflare Pages | build | WP-13.

  De zin "De `PUBLIC_*`-variabelen voor de web-app komen in `web/.env.example` (WP-13)." wordt: "De `PUBLIC_*`-variabelen voor de web-app staan in `web/.env.example`. Gebruik daar nooit de secret key; de build weigert een sleutel die met `sb_secret_` begint."
- Sectie 7: job `web` beschrijven: `npm ci`, `check`, `test`, `build`, `verify:build` en de Open-Meteo-guard. Placeholders voor de publieke variabelen, geen secrets.
- Nieuwe sectie 9 "Web-app (PWA)":
  1. **Lokaal.** `cd web && cp .env.example .env` en vul je waarden in: remote (Dashboard, Project Settings, API) of de lokale stack (`http://127.0.0.1:54321` en de publishable key uit `supabase status`). Daarna `npm ci`, `npm run dev` (http://localhost:5173), `npm run check`, `npm test`, `npm run build`, `npm run verify:build` en vanuit de repo-root `bash scripts/check-no-client-openmeteo.sh`.
  2. **Lokaal inloggen.** Met de lokale stack komt de magic link in Mailpit (`http://127.0.0.1:54324`). `config.toml` staat `http://localhost:5173` als redirect toe.
  3. **Cloudflare Pages (eenmalig, Lars).**
     - Workers & Pages, Create, Pages, Connect to Git, repo `LarsTout/shakka`;
     - production branch `main`;
     - framework preset "None", build command `npm run build`, build output directory `build`, root directory `web`;
     - Preview branches: alle niet-productiebranches (dus `develop` en `wp/*`);
     - environment variables voor **Production en Preview**: `PUBLIC_SUPABASE_URL`, `PUBLIC_SUPABASE_PUBLISHABLE_KEY` en `NODE_VERSION=24.22.0` (het standaardimage heeft Node 22.16, en dat is te oud voor SvelteKit 3).
  4. **Supabase Auth (Lars).** Authentication, URL Configuration:
     - Site URL: `https://<project>.pages.dev`;
     - Redirect URLs: `https://<project>.pages.dev`, `https://<project>.pages.dev/**`, `https://*.<project>.pages.dev`, `https://*.<project>.pages.dev/**`, `http://localhost:5173` en `http://localhost:5173/**`.
  5. **Beperkingen.** De standaard-SMTP mailt alleen naar teamleden van het project, max. 2 per uur. Een inloglink is één keer bruikbaar en verloopt na 1 uur. Op iOS heeft een app op het beginscherm eigen opslag, los van Safari. Een magic link uit de mail logt je in Safari in, niet in de geïnstalleerde app (zie WP-18).
  6. **App-icoon vervangen.** Vervang de PNG's in `web/static/icons/` door bestanden met dezelfde naam en afmeting. `npm run icons` maakt de placeholders opnieuw.

### Gevolgen voor latere WP's
- Imports van gedeelde code gaan via `#lib/<bestand>.js` (`$lib` bestaat niet in kit 3). Publieke variabelen komen erbij in `src/env.ts` (WP-15: `PUBLIC_MAPTILER_KEY`, WP-18: `PUBLIC_VAPID_PUBLIC_KEY`), met `public: true, static: true`.
- WP-18 breidt `src/service-worker/index.ts` uit (niet `src/service-worker.ts`) en haalt de registratie op via `navigator.serviceWorker.ready`. Handlerlogica komt in `src/lib/sw/` met structurele types, net als `shell.ts`, zodat die in vitest te testen is.
- Component- en routetests mocken `#lib/supabase.js` met het `vi.hoisted`-patroon uit `test/login.test.ts`.
- `session` kent drie toestanden. "Uitgelogd" is `$session === null`; `undefined` betekent "nog onbekend" (WP-16 AC-6: dan nog niet queryen).
- WP-20: `emailRedirectTo` is de origin. Terugkeren naar een `/go`-URL na het inloggen vraagt een eigen mechanisme (bijv. `sessionStorage`).
- WP-23: de SPA-fallbackpagina bevat een inline bootstrapscript van SvelteKit. Een CSP met `script-src 'self'` heeft dus de `csp`-optie van SvelteKit of een hash nodig.

## Edge cases
- **Ontbrekende of foute env-variabelen.** De build faalt met een Engelse melding zonder de waarde. De secret key in `PUBLIC_SUPABASE_PUBLISHABLE_KEY` laat de build falen. Een URL met `/rest/v1` laat de build falen.
- **E-mailinvoer:**
  - witruimte eromheen wordt weggetrimd;
  - leeg of ongeldig geeft een melding zonder aanroep;
  - dubbel klikken wordt voorkomen: de knop staat uit tijdens het versturen en `submit` negeert `sending`.
- **Fouten bij het versturen:** 429 of een rate-limitcode, een niet-geautoriseerd adres (standaard-SMTP), een ongeldig adres, een netwerkfout (geretourneerde `AuthRetryableFetchError` of een gegooide fout) en elke andere fout krijgen elk een vaste Nederlandse melding.
- **Een verlopen of al gebruikte link** (`#error=…&error_code=otp_expired`) geeft een banner met "Nieuwe inloglink". Bij andere fouten in het fragment volgt de algemene bannertekst. De Engelse `error_description` wordt nooit getoond.
- **Auth nog niet geïnitialiseerd** (`undefined`): de header toont geen login- of uitlogknop, dus er is geen flikkering.
- **Uitloggen zonder netwerk:** `signOut` gooit niet. De sessie blijft dan staan (gedrag van supabase-js) en er volgt een waarschuwing in de console zonder details.
- **Browser zonder service worker of geen secure context:** er wordt niet geregistreerd en de app werkt gewoon. Faalt de registratie, dan volgt een waarschuwing en `null`.
- **SW-install faalt** (een asset geeft 404): er komt geen nieuwe SW en de app werkt via het netwerk.
- **Navigatie offline:** de gecachete `/` (shell) wordt geserveerd. Offline zonder cache gaat de netwerkfout door. Een navigatie met HTTP 500 komt ongewijzigd terug.
- **Requests die de SW niet raakt:** POST, Supabase en andere origins, en same-origin-bestanden die niet geprecachet zijn (bijv. `/_app/version.json`). Er is nergens runtime-caching.
- **Deep link op Cloudflare** (`/over`, `/login`): de SPA-fallback werkt omdat er geen `404.html` is. `verify-build` bewaakt dat.
- **Guard:** de attributielink `https://open-meteo.com/` mag. Binaire bestanden (PNG) worden overgeslagen (`-I`). Zonder `web/build` slaat de standaardmodus de build over met een melding. Een niet-bestaand pad als argument geeft exitcode 2.
- **Secret-scan van WP-00.** Fixtures bevatten nooit `eyJhbGciOi` of `sb_publishable_`/`sb_secret_` met 20 of meer tekens erachter. Gebruik `access_token: 'test-access-token'` en `sb_publishable_test`.
- **AC-6-grep.** In `web/src` en `web/static` staan de woorden `plausible` en `cdn.`, of de andere markers, nergens, ook niet in commentaar. Tests in `web/test/` bouwen zulke strings op met `join` of concatenatie.

## Testplan
Alle tests staan in `web/test/` en draaien met `npm test` (vitest, jsdom, tenzij `// @vitest-environment node` bovenaan staat). Tests voor pure logica schrijf je vóór de implementatie: `env-schema`, `auth` (mapping en fragmentparser), `sw/shell` en `verify-build`. Voeg in elke test met mocks `beforeEach(() => vi.clearAllMocks())` toe, en zet returnwaarden per test.

Mockpatroon voor supabase (in `login.test.ts` en `auth.test.ts`):
```ts
const auth = vi.hoisted(() => ({
	signInWithOtp: vi.fn(),
	signOut: vi.fn(),
	onAuthStateChange: vi.fn()
}));
vi.mock('#lib/supabase.js', () => ({ supabase: { auth }, initialUrlHash: '' }));
```
Lost vitest `#lib/…` niet op in `vi.mock`, gebruik dan het relatieve pad `../src/lib/supabase.js`. Dat is geen ontwerpwijziging.

| Bestand | Tests |
|---|---|
| `env-schema.test.ts` (node) | `https://abc.supabase.co` en `https://abc.supabase.co/` geven `https://abc.supabase.co`. `http://127.0.0.1:54321` en `http://localhost:54321` zijn ok. Fouten volgen bij `undefined`, `''`, `'  '`, `http://abc.supabase.co`, `https://abc.supabase.co/rest/v1`, `https://abc.supabase.co/?x=1` en `not a url`. Sleutels: `sb_publishable_test` is ok (getrimd). Er volgt een fout bij leeg, `sb_secret_xyz` (melding bevat "never the secret key"), `abc` en `sb_publishable_a b`. In geen enkele foutmelding staat de ingevoerde waarde. |
| `auth.test.ts` | `signInWithMagicLink(' lars@example.com ')` roept `signInWithOtp` precies aan met `{ email: 'lars@example.com', options: { emailRedirectTo: window.location.origin } }` en geeft `{}`. Ongeldig (`''`, `'lars'`, `'lars@x'`) geeft `invalidEmail` en 0 aanroepen. Een geretourneerde fout met status 500 geeft `generic`. Een fout met code `over_email_send_rate_limit` of status 429 geeft `rateLimited`. `email_address_not_authorized` geeft `notAuthorized`. `{ name: 'AuthRetryableFetchError', status: 0 }` geeft `network`. Een rejected promise geeft `network`. `authErrorMessage(null)` en `authErrorMessage('x')` geven `generic`. `parseAuthRedirectError`: `''` en `'#access_token=a'` geven `null`; `'#error=access_denied&error_code=otp_expired&error_description=x'` geeft `linkExpired`; `'#error=server_error'` geeft `linkFailed`. `initAuth`: het callback van `onAuthStateChange` met `('INITIAL_SESSION', null)` zet de store op `null`, en met `('SIGNED_IN', fakeSession)` op `fakeSession`. Een tweede `initAuth()` abonneert niet opnieuw. De teardown roept `unsubscribe` aan en zet de store op `undefined`. `signOut()` roept `signOut({ scope: 'local' })` aan en gooit niet als er `{ error }` terugkomt. |
| `attribution.test.ts` | Geparametriseerd over `compact` `false` en `true`. Een link met `href === 'https://open-meteo.com/'` heeft een tekst met "Open-Meteo". Een link heeft `href === 'https://creativecommons.org/licenses/by/4.0/'`. `textContent` bevat KNMI, DWD, ECMWF, NOAA en Rijkswaterstaat. Alle links hebben `rel` met `noopener`. **(AC-4)** |
| `layout.test.ts` | Rendert `src/routes/+layout.svelte` met `children: createRawSnippet(() => ({ render: () => '<p>Kind</p>' }))`. `#lib/auth.js` wordt gemockt met `session: writable(null)`, `initAuth: vi.fn(() => () => {})`, `signOut: vi.fn()` en `initialAuthRedirectError: vi.fn(() => null)`. `#lib/sw-register.js` wordt gemockt met `registerServiceWorker: vi.fn()`. De tests: (a) `getByRole('contentinfo')` bevat een link naar `https://open-meteo.com/` en de tekst Rijkswaterstaat **(AC-4)**; (b) "Kind" wordt gerenderd; (c) `registerServiceWorker` is één keer aangeroepen met `(navigator, false)` **(AC-2)**; (d) bij `session = null` staat er een link "Inloggen" naar `/login`; (e) met een sessie `{ user: { email: 'lars@example.com' } }` staan het e-mailadres en "Uitloggen" er, en een klik roept `signOut` aan; (f) bij `undefined` staan "Inloggen" en "Uitloggen" er geen van beide; (g) als `initialAuthRedirectError` `AUTH_MESSAGES.linkExpired` geeft, staat er een `alert` met die tekst, en "Sluiten" haalt die weg. |
| `login.test.ts` | Rendert `src/routes/login/+page.svelte` met het supabase-mockpatroon; de echte `auth.ts`. (a) Typt `lars@example.com`, klikt "Stuur inloglink": `signInWithOtp` is aangeroepen met `{ email: 'lars@example.com', options: { emailRedirectTo: window.location.origin } }`, en daarna staan de tekst "Check je mail" en het adres er **(AC-5)**; (b) `signInWithOtp` geeft `{ data: { user: null, session: null }, error: { name: 'AuthApiError', status: 500, code: 'unexpected_failure', message: 'x' } }`: `findByRole('alert')` heeft de tekst `AUTH_MESSAGES.generic`, en "x" staat niet op de pagina **(AC-5)**; (c) bij een rate-limitfout staat `AUTH_MESSAGES.rateLimited` er; (d) een leeg veld plus klik geeft `invalidEmail` en 0 aanroepen; (e) tijdens een pending promise staat de knop uit. |
| `over.test.ts` | `/over` rendert de h1 "Over Shakka" en de volledige `Attribution` (link `https://open-meteo.com/`). |
| `sw-shell.test.ts` (node) | Met `test/helpers/fake-cache.ts`. Een `FakeCache` slaat responses op per absoluut pad (string); `addAll(paths)` vult elk pad met `new Response('cached:' + path)`; `match`, `put` (telt aanroepen) en `keys`. `FakeCacheStorage` heeft `open`, `keys`, `delete` en `has`. Origin `https://app.test`, precache `['/_app/immutable/entry/start.js', '/manifest.webmanifest', '/']`. Tests: `precacheList(['/a','/a','/b'], '/')` geeft `['/a','/b','/']`, en met `/` er al in komt er geen dubbele. `classifyRequest`: POST geeft passthrough; `https://abc.supabase.co/rest/v1/spots` (GET) geeft passthrough; navigate `/login` geeft navigate; navigate `/` geeft navigate; GET `/_app/immutable/entry/start.js` geeft precached; GET `/_app/version.json` geeft passthrough. Handlers: install vult alle precache-paden in `shakka-shell-v2`; activate verwijdert `shakka-shell-v1`, houdt `shakka-shell-v2` en houdt `other-cache`; fetch POST en fetch Supabase roepen `respondWith` niet aan **(Supabase wordt niet gecachet)**; fetch op een precached pad geeft de cache-respons zonder `deps.fetch`; navigate online geeft de netwerkrespons; navigate met fetch-reject geeft de shell (`cached:/`); navigate met fetch-reject zonder shell rejectet; na alle scenario's is `put` 0 keer aangeroepen. **(AC-2)** |
| `sw-register.test.ts` | `enabled=false` geeft `null` en 0 aanroepen; `nav=undefined` geeft `null`; `{}` (geen `serviceWorker`) geeft `null`; `enabled=true` roept `register('/service-worker.js', { type: 'module', scope: '/' })` aan en geeft de registratie terug; een rejectende `register` geeft `null` zonder throw. **(AC-2)** |
| `manifest.test.ts` (node) | Parset `static/manifest.webmanifest`. `checkManifest(...)` uit `scripts/verify-build.mjs` is `[]`. Elk icoonbestand bestaat in `static/` en `pngSize` klopt met `sizes`. `static/icons/apple-touch-icon.png` is 180×180. `src/app.html` linkt naar `/manifest.webmanifest` en `/icons/apple-touch-icon.png`. **(AC-2)** |
| `verify-build.test.ts` (node) | `checkManifest`: het geldige manifest geeft `[]`; zonder het 512-icoon, met `display: 'browser'` en zonder `name` volgt telkens een probleem. `findExternalScripts`: `<script type="module" src="/_app/x.js">` geeft `[]`; `<script src="https://x.test/a.js">` en `<script src="//x.test/a.js">` geven elk één treffer. `findTrackerRefs`: tekst met de marker die je opbouwt als `['google', 'tagmanager'].join('')` geeft een treffer; `https://open-meteo.com/` geeft `[]`. `pngSize` op een gegenereerd icoon geeft de juiste afmeting. **(AC-2, AC-6)** |
| `guard.test.ts` (node) | `spawnSync('bash', [<repo>/scripts/check-no-client-openmeteo.sh, tmpDir])`. Een tijdelijke dir (`fs.mkdtempSync(os.tmpdir())`) met `fixture.ts` met `'https://' + 'api.open-meteo.com/v1/forecast'` geeft status 1, en stdout noemt `fixture.ts`. Dezelfde dir met alleen `https://open-meteo.com/` geeft 0. `marine-api.open-meteo.com` geeft 1. Een niet-bestaand pad geeft 2. Zonder argumenten (de repo zelf) geeft 0. **(AC-3)** |
| `no-third-party.test.ts` (node) | Loopt recursief door `src/` en `static/` (tekstextensies zoals in `verify-build`) en verwacht dat `findTrackerRefs` voor elk bestand `[]` geeft. **(AC-6)** |
| `env-example.test.ts` (node) | `web/.env.example` heeft, buiten commentaar, precies de sleutels `PUBLIC_SUPABASE_URL` en `PUBLIC_SUPABASE_PUBLISHABLE_KEY` (in die volgorde), allebei met een lege waarde. |

Per acceptatiecriterium:
- **AC-1:** `cd web && npm ci && npm run check && npm test && npm run build` lokaal en in CI-job `web`.
- **AC-2:**
  - `npm run verify:build`: `build/index.html`, geen `404.html`, manifest met `name`, iconen van 192 en 512 (any en maskable), `display: standalone`, `build/service-worker.js`;
  - de registratie in de code: `sw-register.test.ts` en `layout.test.ts` (c);
  - de cachestrategie: `sw-shell.test.ts`;
  - de statische bestanden: `manifest.test.ts`.
- **AC-3:** `guard.test.ts`. De CI-stap staat in `ci.yml` en `test_repo_hygiene.py::test_ci_workflow_contract` bewaakt die (`cd ingest && uv run pytest`).
- **AC-4:** `attribution.test.ts`, en `layout.test.ts` (a) voor de footer.
- **AC-5:** `login.test.ts` (a) en (b), plus `auth.test.ts`.
- **AC-6:**
  - de verifier draait letterlijk `grep -rEn "googletagmanager|google-analytics|plausible|fonts.googleapis|cdn\." web/src web/static`; dat geeft niets;
  - `grep -c '<script src="http' web/build/index.html` geeft 0;
  - automatisch: `no-third-party.test.ts` en `npm run verify:build`.
- **AC-7:** `NEEDS_LARS`: de Pages-URL laadt, de app is te installeren (Chrome "App installeren" of Safari "Zet op beginscherm"), en een magic link naar Lars' adres logt in. De header toont het adres.

Daarnaast blijft `cd ingest && uv run pytest && uv run ruff check . && uv run ruff format --check .` groen.

## Externe afhankelijkheden
Gecontroleerd op 14 oktober 2026.

| Package | Versie (range) | Reden | Bron |
|---|---|---|---|
| `@sveltejs/kit` | ^3.0.1 | Framework. Peers: vite ^8.0.12, svelte ^5.57.1, typescript ^6, vite-plugin-svelte ^7. Node ≥ 22.17. | https://registry.npmjs.org/@sveltejs/kit/latest, https://svelte.dev/blog/sveltekit-3-is-here, https://svelte.dev/docs/kit/migrating-to-sveltekit-3 |
| `@sveltejs/adapter-static` | ^4.0.0 | Statische output plus SPA-fallback (peer kit ^3) | https://registry.npmjs.org/@sveltejs/adapter-static/latest, https://svelte.dev/docs/kit/adapter-static, https://svelte.dev/docs/kit/single-page-apps |
| `@sveltejs/vite-plugin-svelte` | ^7.3.1 | Peer van kit 3 | https://registry.npmjs.org/@sveltejs/vite-plugin-svelte/latest |
| `svelte` | ^5.57.2 | UI. `createRawSnippet` voor de layouttest | https://registry.npmjs.org/svelte/latest, https://svelte.dev/docs/svelte/svelte#createRawSnippet |
| `vite` | ^8.3.4 | Bundler (peer kit) | https://registry.npmjs.org/vite/latest |
| `typescript` | ^6.0.3 | Strikte types. Bewust niet 7.x (kit-peer ^6, svelte-check ^5 of ^6) | https://registry.npmjs.org/typescript/6.0.3, https://registry.npmjs.org/svelte-check/latest |
| `svelte-check` | ^4.7.6 | `npm run check` | idem |
| `vitest` | ^5.0.4 | Tests. Peer vite ^6.4, ^7 of ^8. Node ^22.12, ^24 of ≥ 26 | https://registry.npmjs.org/vitest/latest |
| `jsdom` | ^30.1.2 | DOM-omgeving. Node ^24.15.0 | https://registry.npmjs.org/jsdom/latest |
| `@testing-library/svelte` | ^5.4.2 | Componenttests. `svelteTesting` uit `@testing-library/svelte/vite` | https://registry.npmjs.org/@testing-library/svelte/latest, https://testing-library.com/docs/svelte-testing-library/setup |
| `@testing-library/jest-dom` | ^7.0.1 | Matchers via `@testing-library/jest-dom/vitest` (export bestaat in 7.0.1) | https://registry.npmjs.org/@testing-library/jest-dom/7.0.1 |
| `@testing-library/user-event` | ^14.6.8 | Typen en klikken | https://registry.npmjs.org/@testing-library/user-event/latest |
| `@testing-library/dom` | ^10.4.2 | Peer van user-event en jest-dom (>=10 <11) | https://registry.npmjs.org/@testing-library/dom/latest |
| `@types/node` | ^24.0.0 | Types voor `node:fs` en `node:child_process` in tests en scripts, gelijk aan de runtime Node 24 | – |
| `@supabase/supabase-js` | ^2.117.3 | Auth-client (Node ≥ 22 voor tests en build) | https://registry.npmjs.org/@supabase/supabase-js/latest |

| Externe API of dienst | Gebruik | Bron |
|---|---|---|
| Supabase Auth `signInWithOtp({ email, options: { emailRedirectTo } })` | Magic link versturen | https://supabase.com/docs/reference/javascript/auth-signinwithotp |
| `createClient(url, key, { auth: { flowType, persistSession, autoRefreshToken, detectSessionInUrl } })`; standaard `flowType: 'implicit'` | Client | https://supabase.com/docs/reference/javascript/initializing, `DEFAULT_OPTIONS` in https://raw.githubusercontent.com/supabase/supabase-js/master/packages/core/auth-js/src/GoTrueClient.ts, https://supabase.com/docs/guides/auth/sessions/pkce-flow |
| `onAuthStateChange` (events inclusief `INITIAL_SESSION`; `data.subscription.unsubscribe()`) | Sessiestore | https://supabase.com/docs/reference/javascript/auth-onauthstatechange |
| `signOut({ scope: 'local' })` | Alleen dit apparaat uitloggen | https://supabase.com/docs/reference/javascript/auth-signout |
| Auth-foutcodes `over_email_send_rate_limit`, `over_request_rate_limit`, `email_address_not_authorized`, `email_address_invalid`, `validation_failed`, `otp_expired` | Nederlandse meldingen | https://supabase.com/docs/guides/auth/debugging/error-codes |
| Redirect-URL-allowlist met globs (`*`, `**`) | RUNBOOK | https://supabase.com/docs/guides/auth/redirect-urls |
| Magic link en OTP: 1 aanvraag per 60 s, 1 uur geldig | Edge cases, RUNBOOK | https://supabase.com/docs/guides/auth/auth-email-passwordless |
| Templates niet aanpasbaar op nieuwe free-tier-projecten zonder eigen SMTP (sinds 3 juni 2026) | A6 | https://supabase.com/changelog/46599-changes-to-email-template-customisation-on-free-tier |
| SvelteKit-service-worker (`src/service-worker/index.ts`, `$app/service-worker`, `$app/env` `version`, `$app/manifest` `immutable`/`assets`, `$app/paths` `resolve`, aparte tsconfig) | Service worker | https://raw.githubusercontent.com/sveltejs/kit/main/documentation/docs/30-advanced/40-service-workers.md, https://svelte.dev/docs/kit/$app-manifest, https://svelte.dev/docs/kit/$app-service-worker |
| Config `serviceWorker.register` (standaard `true`) | Handmatige registratie | https://svelte.dev/docs/kit/configuration |
| Env (`src/env.ts`, `defineEnvVars` uit `@sveltejs/kit/env`, `public`, `static`, `schema`, import uit `$app/env/public`) | Publieke variabelen | https://svelte.dev/docs/kit/environment-variables, https://svelte.dev/docs/kit/@sveltejs-kit-env, https://svelte.dev/tutorial/kit/env-public |
| `$app/tsconfig` en `$app/tsconfig/service-worker` | tsconfig | https://svelte.dev/docs/kit/$app-tsconfig, https://svelte.dev/docs/kit/$app-tsconfig-service-worker |
| sv-template (scripts, `imports`, runes-config, `app.html`, `.npmrc`) | Scaffolding | https://raw.githubusercontent.com/sveltejs/cli/main/packages/sv/src/create/templates/minimal/package.template.json, …/shared/vite.config.ts, …/shared/+typescript/package.json, …/shared/+typescript/tsconfig.json, …/templates/minimal/src/app.html |
| Cloudflare Pages build image v3 (standaard Node 22.16.0; `NODE_VERSION`, `.nvmrc`) | RUNBOOK, A2 | https://developers.cloudflare.com/pages/configuration/build-image/ |
| Cloudflare Pages SPA-gedrag zonder `404.html` | Fallback | https://developers.cloudflare.com/pages/configuration/serving-pages/ (via WORK_PACKAGES) |
| Installeerbaarheid in Chrome (name/short_name, 192 en 512, start_url, display, prefer_related_applications) | Manifest | https://developer.chrome.com/docs/lighthouse/pwa/installable-manifest |
| Open-Meteo-attributie ("Weather data by Open-Meteo.com", link naar de licentie, vermelden of de data is bewerkt) | `Attribution` | https://open-meteo.com/en/licence |
| `actions/setup-node@v7` (`node-version-file`, `cache: npm`, `cache-dependency-path`) | CI | https://github.com/actions/setup-node |
| Node-releases (24.22.0 LTS "Krypton" op 14-10-2026) | A2 | https://nodejs.org/dist/index.json |
| iOS: een app op het beginscherm deelt geen opslag met Safari | R3 (bron is van derden, geen Apple-documentatie) | https://www.netguru.com/blog/how-to-share-session-cookie-or-state-between-pwa-in-standalone-mode-and-safari-on-ios |

Geen betaalde dienst, geen CDN, geen webfonts, geen analytics.

## Risico's
- **R1. SvelteKit 3 is twee weken oud.** Er kunnen bugs in zitten (adapter-static 4, het nieuwe env-systeem), en de builder kent kit 2 beter. Mitigatie: alle configuratiebestanden staan exact in deze blueprint, de versies zijn vastgelegd en de stappen zijn klein. Werkt iets niet zoals de docs zeggen en raakt dat het ontwerp, dan schrijft de builder `deviations.md` en stopt; Lars kiest dan tussen kit 2 en een workaround.
- **R2. Details van het env-systeem van kit 3** (relatieve import in `src/env.ts`, validatie onder vitest of `svelte-kit sync`). Mitigatie: de placeholders in de testmodus van `vite.config.ts`, de CI-variabelen op jobniveau en de terugvaloptie bij `src/env.ts`.
- **R3. iOS en geïnstalleerde PWA's.** Op iOS heeft een app op het beginscherm eigen opslag. Een magic link uit de mail opent Safari, dus de sessie komt in Safari en niet in de geïnstalleerde app. AC-7 (installeren én inloggen) haal je zo nog wel, maar WP-18 (push op iOS vraagt de geïnstalleerde app plús een sessie) loopt hier tegenaan. Mitigatie: inloggen met een code (A6), zodra er eigen SMTP is.
- **R4. Linkscanners** (bijv. Outlook) kunnen de eenmalige link al openen. De gebruiker ziet dan "verlopen of al gebruikt". Dezelfde mitigatie als R3.
- **R5. Standaard-SMTP:** max. 2 mails per uur en alleen naar teamleden. Lars testen gaat goed; de crew pas na WP-22.
- **R6. Node-versie op Cloudflare.** Zonder `NODE_VERSION` faalt de build: `engine-strict` geeft dan een heldere fout. Dat staat in de RUNBOOK en bij "Nodig van Lars".
- **R7. Verouderde shell.** Zonder `skipWaiting` draait een gebruiker de oude versie tot alle vensters dicht zijn. De versiecontrole van SvelteKit (elk uur `/_app/version.json`) en het herstel bij een ontbrekend chunk vangen het meeste op.
- **R8. Cloudflare-builds (500 per maand).** Elke push naar elke branch bouwt een preview. Bij het huidige tempo is dat ruim genoeg. Wordt het krap, dan beperkt Lars de previews tot `develop`.
- **R9. Bundelgrootte van supabase-js.** WP-23 legt een budget vast. Hier wordt niets extra geladen (geen realtime-subscriptions).

## Buiten scope
- Spotdata tonen (WP-14), kaart (WP-15), profiel, favorieten en alerts (WP-16), push abonneren en de push-handlers (WP-18), sessies (WP-20, WP-21), privacypagina, CSP (`_headers`), axe en het bundelbudget (WP-23).
- Database-typegeneratie (WP-14). Inloggen met een code, eigen SMTP en het beperken van aanmeldingen (WP-22, zie A5 en A6).
- ESLint en Prettier, runtime-caching en offline data, `skipWaiting` en een "nieuwe versie"-melding.
- Aanpassingen aan `WORK_PACKAGES.md`. De contractregels die in kit 3 anders heten (`$env/static/public`, `src/service-worker.ts`) staan in A1 en onder "Gevolgen voor latere WP's". De orchestrator of Lars werkt die bij als dat gewenst is.

## Stappenplan voor de builder
Na elke stap: de genoemde commando's zijn groen, en er volgt een commit (Engels, bijv. `WP-13: scaffold web app`).

1. **Scaffold.**
   - Maak `web/` aan met `package.json`, `.npmrc`, `.nvmrc`, `.env.example`, `vite.config.ts`, `tsconfig.json`, `src/app.html`, `src/app.d.ts`, `src/app.css`, `src/lib/index.ts`, `src/routes/+layout.ts` en `src/routes/+page.svelte`. Maak voorlopig een `+layout.svelte` met alleen `{@render children()}`.
   - Maak `test/setup.ts`.
   - Gebruik Node 24 (`nvm use`). Draai `npm install`; dat maakt de lockfile.
   - Maak een lokale `web/.env` met `PUBLIC_SUPABASE_URL=http://127.0.0.1:54321` en `PUBLIC_SUPABASE_PUBLISHABLE_KEY=sb_publishable_local`. Die wordt niet gecommit; controleer dat met `git status`.
   - Maak nog geen `src/env.ts`. Groen: `npm run build`.
2. **Env (tests eerst).**
   - Schrijf `test/env-schema.test.ts` en `test/env-example.test.ts`, en daarna `src/lib/env-schema.ts` en `src/env.ts`.
   - Controleer dat `npm run build` faalt met de juiste melding bij een lege `PUBLIC_SUPABASE_URL` en bij `PUBLIC_SUPABASE_PUBLISHABLE_KEY=sb_secret_x`. Zet daarna de waarden terug.
   - Groen: `npm run check`, `npm test` en `npm run build`.
3. **Auth (tests eerst).** Schrijf `test/auth.test.ts`, en daarna `src/lib/supabase.ts` en `src/lib/auth.ts`. Groen: `npm run check` en `npm test`.
4. **UI.**
   - Maak `Attribution.svelte`, de definitieve `+layout.svelte`, `+page.svelte`, `login/+page.svelte` en `over/+page.svelte`.
   - Maak voor de layout eerst een `src/lib/sw-register.ts` met de echte signature en implementatie, en schrijf `test/sw-register.test.ts`.
   - Schrijf `test/attribution.test.ts`, `test/layout.test.ts`, `test/login.test.ts` en `test/over.test.ts`.
   - Groen: `npm run check`, `npm test` en `npm run build`.
5. **Service worker (tests eerst).**
   - Schrijf `test/helpers/fake-cache.ts` en `test/sw-shell.test.ts`, en daarna `src/lib/sw/shell.ts`, `src/service-worker/index.ts` en `src/service-worker/tsconfig.json`.
   - Groen: `npm run check` (inclusief `tsc -p src/service-worker/tsconfig.json`), `npm test` en `npm run build`. Controleer dat `build/service-worker.js` bestaat.
6. **PWA-assets.**
   - Schrijf `scripts/make-placeholder-icons.mjs` en draai `npm run icons`.
   - Maak `static/manifest.webmanifest` en `static/favicon.svg`.
   - Schrijf eerst `test/verify-build.test.ts` en `test/manifest.test.ts`, en daarna `scripts/verify-build.mjs`.
   - Groen: `npm test`, `npm run build` en `npm run verify:build`.
7. **Guards.**
   - Maak `scripts/check-no-client-openmeteo.sh` en zet de modus: `chmod +x` en `git update-index --chmod=+x`.
   - Schrijf `test/guard.test.ts` en `test/no-third-party.test.ts`.
   - Groen: `npm test`, en vanuit de root `bash scripts/check-no-client-openmeteo.sh` (exit 0).
   - Draai ook de AC-6-grep letterlijk (die geeft niets) en `grep -c '<script src="http' web/build/index.html` (0).
8. **CI.**
   - Voeg job `web` toe aan `.github/workflows/ci.yml` en breid `test_ci_workflow_contract` uit.
   - Groen: `cd ingest && uv run pytest && uv run ruff check . && uv run ruff format --check .`.
   - Draai de hele webketen in een schone shell, zonder `web/.env`, met de CI-variabelen: `PUBLIC_SUPABASE_URL=http://127.0.0.1:54321 PUBLIC_SUPABASE_PUBLISHABLE_KEY=sb_publishable_ci npm ci && npm run check && npm test && npm run build && npm run verify:build`.
9. **Supabase en documentatie.**
   - Pas de twee `[auth]`-regels in `supabase/config.toml` aan. De ingest-tests blijven groen, inclusief `test_supabase_config_disables_auto_expose`.
   - Werk `docs/RUNBOOK.md` bij (secties 1, 4, 7 en 9).
10. **Eindcontrole.**
    - `cd web && npm ci && npm run check && npm test && npm run build && npm run verify:build`, en `bash scripts/check-no-client-openmeteo.sh` vanuit de root.
    - `cd ingest && uv run pytest`.
    - `git status`: geen `web/.env`, geen `web/build` en geen `node_modules` gestaged.

**Nodig van Lars (voor AC-7):**
- een Cloudflare-account en een Pages-project zoals in RUNBOOK sectie 9.3, inclusief `NODE_VERSION=24.22.0`;
- de Supabase-URL-configuratie zoals in sectie 9.4;
- Node 24 lokaal;
- akkoord op het placeholder-icoon (A3) of een eigen icoon;
- een reactie op de voorstellen A1, A2, A3 en A6.
