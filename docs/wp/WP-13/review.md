# Review WP-13, ronde 1
Oordeel: APPROVED

## Toetsing SvelteKit 3 (specifieke opdracht)
De keuze voor kit 3 is goed onderbouwd. Elke aanname over kit 3 heb ik nagelopen in de actuele documentatie en op npm (14-10-2026):

| Aanname in de blueprint | Bevinding |
|---|---|
| Config in `vite.config.ts` via `sveltekit({...})`, geen `svelte.config.js` | Bevestigd (migratiegids en configuratiepagina: "Prior to SvelteKit 3, config lived in a `svelte.config.js` file, which is no longer supported"). |
| `#lib` via `imports` in `package.json` (`"#lib": "./src/lib/index.js"`, `"#lib/*": "./src/lib/*"`), imports met extensie `#lib/foo.js` | Bevestigd, letterlijk zo in de migratiegids en het sv-template. |
| `src/env.ts` met `defineEnvVars` uit `@sveltejs/kit/env`, `public`, `static`, `schema`, `description`, import uit `$app/env/public` | Bevestigd. Het schema mag een functie `(value: string \| undefined) => T` zijn die gooit. `static: true` wordt bij de build ingevuld. |
| **Onzekerheid 1: hoe het env-systeem laadt en valideert** | Grotendeels bevestigd. De docs zeggen dat `.env`/`.env.local` bij dev en build "will be added to the environment", dus de procesomgeving (de CI-variabelen op jobniveau, de Cloudflare-variabelen) is de basis. Validatie gebeurt "at startup and build time"; een schema dat gooit, laat start of build falen. Niet gedocumenteerd: of `src/env.ts` relatief mag importeren, en of validatie ook onder vitest draait. Voor allebei heeft de blueprint een concrete terugvaloptie (functies inline in `src/env.ts`; placeholders in testmodus in `vite.config.ts`). Een builder hoeft hier dus geen ontwerpkeuze te maken. |
| **Onzekerheid 2: naam van het service-worker-bestand na de build** | Bevestigd. De standaardregistratie van kit 3 in de docs gebruikt `const script_url = './service-worker.js'` met `{ type: 'module' }`. `build/service-worker.js` en registratie als module kloppen. |
| `src/service-worker/index.ts`, `$app/service-worker` (`self`), `$app/env` (`version`), `$app/manifest` (`immutable`, `assets`), `$app/paths` (`resolve`), aparte `tsconfig.json` met `extends: "$app/tsconfig/service-worker"` | Bevestigd. De code van de blueprint volgt het voorbeeld uit de docs. |
| `serviceWorker: { register: false }` | Bevestigd (`@sveltejs/kit/vite`: `register`, standaard `true`). |
| `$app/tsconfig`; `paths`, `types`, `isolatedModules`, `verbatimModuleSyntax` niet overschrijven | Bevestigd. `$app/tsconfig` wordt door `svelte-kit sync` in `node_modules/$app` geschreven. `prepare` en `check` draaien `sync` eerst, dus dat werkt. |
| Versies: kit 3.0.1 (Node ≥ 22.17, peer TS ^6, vite ^8.0.12, svelte ^5.57.1, vite-plugin-svelte ^7), adapter-static 4.0.0 (peer kit ^3), vite-plugin-svelte 7.3.1, svelte-check 4.7.6 (TS ^5 \|\| ^6), vitest 5.0.4, jsdom 30.1.2, jest-dom 7.0.1 (met `./vitest`), @testing-library/svelte 5.4.2 (met `./vite`), supabase-js 2.117.3, typescript 6.0.3 | Alle versies bestaan en de peer-ranges passen bij elkaar. TS 6 (niet 7) is terecht. |

Conclusie: kit 3 leunt niet op onbevestigde aannames waar een builder op vastloopt. De afwijkingen van de contracten in WORK_PACKAGES zijn daarom een **beslispunt voor Lars** (N-1) en geen blokkade. De blueprint somt ze expliciet op: A1, "Buiten scope" en "Gevolgen voor latere WP's".

## Blokkerend
Geen.

## Niet-blokkerend
N-1: **Beslispunt voor Lars: SvelteKit 3 in plaats van 2.** Waar: A1. Gevolg: drie contractregels in WORK_PACKAGES kloppen niet meer letterlijk: regel 891 (`src/service-worker.ts`), regel 899 (`$env/static/public`) en regel 1101 (WP-18 "In `service-worker.ts`"). Voorstel: kit 3 aanhouden. Werk na de goedkeuring die drie regels in WORK_PACKAGES bij (orchestrator of Lars), zodat de planners van WP-14, WP-15 en WP-18 niet op de oude contracten bouwen.

N-2: **Het pad van de service worker is in kit 3 een keuze, geen verplichting.** Waar: A1, vierde bullet ("niet `src/service-worker.ts`"). De docs zeggen: "`src/service-worker.ts` or `.js` is also valid, but see the section on type safety". De keuze voor de directory is terecht, want die maakt de aparte tsconfig mogelijk. Formuleer het wel als keuze. Hetzelfde geldt voor `$env/static/public`: dat is in kit 3 deprecated maar werkt nog, dus het contract had letterlijk gehaald kunnen worden. Kiezen voor de nieuwe API is redelijk.

N-3: **R7 bevat een feitelijke onjuistheid.** "De versiecontrole van SvelteKit (elk uur `/_app/version.json`)" klopt niet: `version.pollInterval` staat standaard op 0. SvelteKit controleert de versie alleen als een navigatie of chunk faalt. Voorstel: de tekst corrigeren, of `version: { pollInterval: 3_600_000 }` expliciet in `sveltekit({...})` zetten als die mitigatie gewenst is.

N-4: **`NODE_VERSION=24.22.0` is vandaag (14-10-2026) uitgebracht.** Bevestigd in nodejs.org/dist/index.json. Het risico dat het Cloudflare-buildimage die versie nog niet kan installeren is klein, maar bestaat. Overweeg in de RUNBOOK een terugvaloptie: een eerdere 24.x-versie (≥ 24.15) als 24.22.0 niet installeert. Volgens de docs van Cloudflare werkt `.nvmrc` ook "in the root directory of your project". Met root `web` kan `web/.nvmrc` dus al volstaan.

N-5: **jsdom-engines verkeerd geciteerd.** A2 en de tabel noemen "^24.15.0". De werkelijke range is `^22.22.2 || ^24.15.0 || >=26.0.0`. Dit heeft geen gevolg voor de keuze van Node 24.

N-6: **Node-types in `svelte-check`.** `$app/tsconfig` legt `types` vast, en TS 6 laadt `@types/*` niet meer vanzelf. Dat `node:fs`, `process` en `Buffer` in `test/` en `vite.config.ts` toch typechecken, komt waarschijnlijk alleen doordat de types van vite/vitest `/// <reference types="node" />` meenemen. Faalt dat toch, dan mag de builder `/// <reference types="node" />` bovenaan de betreffende testbestanden zetten. Benoem dat als toegestane oplossing, zodat de builder `types` niet gaat aanpassen.

N-7: **`FakeCache` en typecheck.** `ShellDeps.caches` is `Pick<CacheStorage, 'open' | ...>`, en `open` geeft `Promise<Cache>`. `svelte-check` controleert ook `test/`, dus `FakeCache` moet dan de volledige `Cache`-interface implementeren of gecast worden (`as unknown as Cache`). Noem de cast expliciet als toegestaan.

N-8: **Een GET buiten een navigatie naar `/` wordt cache-first bediend** (regel 4 van `classifyRequest`, want `/` staat in de precache-set). Dat is onschuldig zolang niets `/` via `fetch` ophaalt. Het alternatief is `/` alleen als navigatie-fallback te gebruiken en uit de `precached`-set van `classifyRequest` te laten.

N-9: **Open aanmelden (A5).** Iemand die niet in het team zit, kan via `signInWithOtp` mogelijk een rij in `auth.users` (en via de trigger van WP-01 in `profiles`) laten aanmaken, ook als de mail wordt geweigerd. Dat zijn persoonsgegevens van onbekenden. Overweeg tot WP-22 `shouldCreateUser: false`, waarbij Lars zichzelf eenmalig via het dashboard aanmaakt. Een alternatief is een expliciete notitie dat WP-22 deze rijen opruimt.

N-10: **CC BY "indicate if changes were made".** De compacte attributie in de footer vermeldt de bewerking niet; alleen `/over` doet dat. Via de footerlink naar `/over` is dat "any reasonable manner", dus acceptabel. Overweeg voor WP-14 en WP-21 (pagina's met data) toch het woord "bewerkt" in de compacte stand.

N-11: **Typegeneratie.** De blueprint van WP-01 (regel 1059) noemt de typegeneratie voor de PWA "WP-13 en WP-14". Deze blueprint schuift die expliciet door naar WP-14. Dat is in orde, want WORK_PACKAGES vraagt er in WP-13 niet om. Ter info voor de planner van WP-14.

## Gecontroleerde bronnen
- https://svelte.dev/docs/kit/migrating-to-sveltekit-3
- https://svelte.dev/blog/sveltekit-3-is-here
- https://svelte.dev/docs/kit/environment-variables
- https://svelte.dev/docs/kit/@sveltejs-kit-env
- https://svelte.dev/docs/kit/service-workers
- https://raw.githubusercontent.com/sveltejs/kit/main/documentation/docs/30-advanced/40-service-workers.md
- https://svelte.dev/docs/kit/@sveltejs-kit-vite
- https://svelte.dev/docs/kit/configuration
- https://svelte.dev/docs/kit/$app-tsconfig
- https://svelte.dev/docs/kit/$app-tsconfig-service-worker
- https://svelte.dev/docs/kit/adapter-static
- https://svelte.dev/docs/kit/single-page-apps
- https://github.com/sveltejs/kit/issues/17350
- https://raw.githubusercontent.com/sveltejs/cli/main/packages/sv/src/create/templates/minimal/package.template.json
- https://dev.to/jamilxt/sveltekit-3-just-shipped-here-is-your-migration-checklist-1ag
- https://registry.npmjs.org/@sveltejs/kit/latest
- https://registry.npmjs.org/@sveltejs/adapter-static/latest
- https://registry.npmjs.org/@sveltejs/vite-plugin-svelte/latest
- https://registry.npmjs.org/svelte-check/latest
- https://registry.npmjs.org/vitest/latest
- https://registry.npmjs.org/jsdom/latest
- https://registry.npmjs.org/@testing-library/svelte/latest
- https://registry.npmjs.org/@testing-library/jest-dom/7.0.1
- https://registry.npmjs.org/@supabase/supabase-js/latest
- https://registry.npmjs.org/typescript/6.0.3
- https://nodejs.org/dist/index.json
- https://developers.cloudflare.com/pages/configuration/build-image/
- https://github.com/actions/setup-node
- https://supabase.com/docs/reference/javascript/auth-signinwithotp
- https://supabase.com/docs/guides/auth/debugging/error-codes
- https://raw.githubusercontent.com/supabase/supabase-js/master/packages/core/auth-js/src/GoTrueClient.ts
- https://supabase.com/changelog/46599-changes-to-email-template-customisation-on-free-tier
- https://open-meteo.com/en/licence
