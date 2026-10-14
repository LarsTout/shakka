# Verificatie WP-13, ronde 1
Resultaat: NEEDS_LARS

Alles wat zonder Lars te toetsen is, is PASS. AC-7 (Cloudflare Pages, Supabase URL-config, handmatige test) is NEEDS_LARS. Er zijn geen fails.

## Suites (Node 24.22.0, branch `wp/WP-13`)
- `cd web && npm ci && npm run check && npm test && npm run build && npm run verify:build` met placeholder-env: exit 0. `svelte-check` 0 errors/0 warnings, `tsc` voor de service worker schoon, vitest 13 bestanden / 87 tests groen, `verify-build: ok`.
- `bash scripts/check-no-client-openmeteo.sh`: `ok`, exit 0.
- `cd ingest && uv run pytest`: 202 passed, 23 skipped (de skips zijn de pariteitstests die een lokale Supabase vereisen, bestaand gedrag). `ruff check` en `ruff format --check` schoon.
- CI-run 38634393409 op `wp/WP-13` (commit `0f1c485`): jobs `web`, `ingest` en `db` alle drie groen.

| Criterium | Resultaat | Bewijs |
|---|---|---|
| AC-1 | PASS | `npm ci && npm run check && npm test && npm run build` exit 0 (zie boven). CI-job `web` groen. |
| AC-2 | PASS | `web/build` bevat `index.html`, `manifest.webmanifest`, `service-worker.js` en alle vier de iconen plus apple-touch-icon. Manifest: `name` Shakka, `display: standalone`, `start_url /`, iconen 192 en 512 (`any` en `maskable`). `index.html` linkt het manifest. `src/routes/+layout.svelte` roept `registerServiceWorker(navigator, import.meta.env.PROD)` aan; `test/layout.test.ts`, `test/sw-register.test.ts`, `test/manifest.test.ts` en `test/verify-build.test.ts` groen; `npm run verify:build` ok. |
| AC-3 | PASS | Zelf getest: tijdelijk bestand `web/src/tmpfix/x.ts` met `fetch("https://api.open-meteo.com/v1/forecast")` geeft exit 1 en `FAIL`; na verwijderen exit 0. `test/guard.test.ts` dekt hetzelfde. CI-job `web` bevat `bash ../scripts/check-no-client-openmeteo.sh` en `test_repo_hygiene.py::test_ci_workflow_contract` bewaakt die regel. |
| AC-4 | PASS | `test/attribution.test.ts` (compact true en false): link `https://open-meteo.com/` met tekst "Weather data by Open-Meteo.com", link `https://creativecommons.org/licenses/by/4.0/`, tekst bevat KNMI, DWD, ECMWF, NOAA, Rijkswaterstaat. `test/layout.test.ts` toetst dat de `contentinfo`-footer de Open-Meteo-link en Rijkswaterstaat bevat. `Attribution.svelte` heeft `compact?: boolean`. |
| AC-5 | PASS | `test/login.test.ts`: `signInWithOtp` aangeroepen met het ingevoerde adres en `emailRedirectTo: window.location.origin` (plus `shouldCreateUser: false`, gedocumenteerde N-9); fout geeft vaste Nederlandse melding in `role="alert"`, nooit de ruwe servertekst; rate-limit, leeg veld, disabled knop getest. `test/auth.test.ts` dekt de foutmapping. |
| AC-6 | PASS | `grep -rEn "googletagmanager\|google-analytics\|plausible\|fonts.googleapis\|cdn\." web/src web/static` geeft niets (exit 1). `web/build/index.html` bevat 0 keer `<script src="http`; het enige `<script>` is inline. `test/no-third-party.test.ts` groen. |
| AC-7 | NEEDS_LARS | Zie onder. |

## Harde regels
- Geen Open-Meteo-API in `web/`: PASS. Alleen de bronvermelding-links `https://open-meteo.com/` in `Attribution.svelte` (en de gebouwde chunk daarvan); geen `api.open-meteo.com`, `marine-api.` of `/v1` in `web/src`, `web/static` of `web/build`. Guard slaagt.
- Bronvermelding zichtbaar: PASS. Compact in de footer van elke pagina (layout) en volledig op `/over`; getest.
- Geen tracking of third-party analytics, geen CDN's of externe fonts: PASS (AC-6, `no-third-party.test.ts`; de build bevat geen externe URL's behalve de lokale placeholder-Supabase-URL).
- Geen `sb_secret_` of andere secrets: PASS. De string `sb_secret_` komt voor in `web/src/lib/env-schema.ts` (de weigering) en `web/test/env-schema.test.ts`, en als literal in de supabase-js-library-chunk in de build; geen sleutelwaarde. Geen `service_role` of JWT in `web/`. De build weigert een `sb_secret_`-sleutel (test + build-validatie).
- `web/.env` niet in de diff: PASS. Het bestand bestaat lokaal (uit `git check-ignore`: genegeerd) en is niet gecommit. `git ls-files web` bevat geen `build`, `.svelte-kit` of `node_modules`.
- Geen nieuwe betaalde dienst: PASS. Cloudflare Pages en Supabase zijn gratis tiers; geen andere dienst toegevoegd.
- Offshore/side-offshore altijd `no_go`: niet geraakt (geen wijziging in evaluatiecode).
- SW cachet nooit Supabase: PASS. `classifyRequest` geeft `passthrough` voor een andere origin of niet-GET; getest in `test/sw-shell.test.ts`.

## Diff versus blueprint
De diff bevat alle bestanden uit de tabel "Bestanden"; `docs/STATUS.md` is de orchestrator (zoals de blueprint zegt). Geen bestanden buiten scope. `vite.config.ts` is gelijk aan de blueprint plus `version.pollInterval` (N-3); `supabase/config.toml` precies de twee regels; CI-job en hygiene-test volgens blueprint. Afwijkingen staan in `deviations.md` (Node-versie lokaal, N-3, N-9 `shouldCreateUser: false` met `otp_disabled`-mapping, `resolve()` vervangen door `new URL(path, self.registration.scope).pathname`, kleine extra's) en zijn geen fail. SvelteKit 3 in plaats van 2 is door de reviewer als beslispunt voor Lars aangemerkt (N-1) en is geen fail.

## NEEDS_LARS (AC-7)
Stappen uit `docs/RUNBOOK.md` sectie 9:
1. 9.3: Cloudflare Pages-project koppelen aan `LarsTout/shakka` (production branch `main`, preset None, build `npm run build`, output `build`, root `web`, previews voor alle andere branches). Environment variables voor Production en Preview: `PUBLIC_SUPABASE_URL`, `PUBLIC_SUPABASE_PUBLISHABLE_KEY` (publishable key, nooit de secret key) en `NODE_VERSION=24.22.0`.
2. 9.4: in Supabase Auth, URL Configuration: Site URL en Redirect URLs (Pages-URL, `*.pages.dev`-previews en `http://localhost:5173`, met en zonder `/**`).
3. 9.2: jezelf eenmalig aanmaken via Dashboard, Authentication, Users, Add user (nodig door `shouldCreateUser: false`).
4. Handmatig: Pages-URL laadt; de app is te installeren (Chrome of Safari "Zet op beginscherm"); magic-link-login met Lars' e-mailadres werkt end-to-end.
5. Beslispunten: akkoord op SvelteKit 3 (A1/N-1), placeholder-icoon (A3), en de drie contractregels in `docs/WORK_PACKAGES.md` bijwerken (`src/service-worker.ts`, `$env/static/public`, WP-18-verwijzing).

## Problemen
Geen.
