# Verificatie WP-23, ronde 1
Resultaat: NEEDS_LARS

Alle automatische criteria slagen. Open blijven AC-6 (Lighthouse, installeerbaarheid en een testaccount verwijderen op de preview) en het akkoord van Lars op de privacytekst. Beide zijn NEEDS_LARS by design.

| Criterium | Resultaat | Bewijs |
|---|---|---|
| AC-1 `delete_my_account()` | PASS | CI-run 38810174216 (HEAD `f80cf73`), job `db` success: `09_delete_my_account.test.sql ... ok` en `07_sessions.test.sql ... ok`, `Files=9, Tests=448, Result: PASS`. Lokaal niet te draaien (geen Docker). De test controleert: functie bestaat, `void`, `is_definer`, `search_path=""`, `anon` en `service_role` hebben geen EXECUTE, `authenticated` wel, anon wordt geweigerd (42501), een token zonder `sub` geeft `PT401`. Daarna verwijdert A zijn account en zijn rijen in `auth.users`, `profiles`, `favorites`, `alert_rules`, `alert_state`, `push_subscriptions`, `sessions` en de `rsvps` daarop. De rijen van B (inclusief de anonieme RSVP van A op de sessie van B) blijven staan. Een tweede aanroep is een no-op. `plan(23)` klopt met 23 assertions. |
| AC-2 axe-core | PASS | 9 `web/test/a11y-*.test.ts` plus `a11y-compiler.test.ts`. Gedekt zijn `/`, `/spot/[id]`, `/s/[slug]`, `/profiel`, `/alerts`, `/login` en de statische pagina's. De helper filtert op `serious` en `critical`. Alleen `color-contrast` staat uit, omdat jsdom geen layout heeft; `contrast.test.ts` dekt de kleuren apart. `npm test`: 93 bestanden, 1092 tests groen. |
| AC-3 bundelbudget | PASS | `node scripts/check-bundle-size.mjs` geeft exit 0: initiële JS 102,4 kB (17 bestanden, budget 150 kB), precache 595,1 kB (60 bestanden, budget 900 kB), MapLibre-chunk 279,5 kB. `bundle-size.test.ts` heeft een CLI-test die exit 1 geeft boven het budget en een test die checkt dat CI het script na de build draait. `.github/workflows/ci.yml` bevat de stap `node scripts/check-bundle-size.mjs`. |
| AC-4 `_headers` / CSP | PASS | `headers.test.ts` en `verify-build` slagen. De CSP in `build/_headers` heeft `connect-src 'self' https://<supabase-project>.supabase.co https://api.maptiler.com`. Er is geen `open-meteo`, geen `*` en geen analytics-domein. `script-src` is `'self'` plus een sha256 van het inline script. `checkHeaders` wijst al die gevallen af. |
| AC-5 `/privacy` | PASS | `privacy-page.test.ts` en `retention-consistency.test.ts` zijn groen. De footer in `+layout.svelte` linkt naar `/privacy`. De pagina noemt e-mail, voornaam, profiel en push-abonnementen, en niet Telegram (er is een test voor). Bewaartermijnen: forecast, getij en evaluaties 48 uur, `alert_state` 48 uur, sessies 7 dagen. De retentietest leest de Python-constanten in `ingest/src/shakka/jobs/*.py` en `interval '7 days'` in de sessiesmigratie, en vergelijkt die met `privacy.ts`. |
| AC-6 Lighthouse, installeerbaarheid, testaccount verwijderen | NEEDS_LARS | Een preview-deploy is nodig. Zie RUNBOOK §17 stap 5. Lars moet Lighthouse mobiel draaien (toegankelijkheid minstens 90, performance minstens 80), de installeerbaarheid controleren, en een testaccount verwijderen. |
| Akkoord privacytekst | NEEDS_LARS | Lars moet `/privacy` en `docs/PRIVACY.md` goedkeuren. `PRIVACY_CONTACT_EMAIL` is bewust `null`. |

## Uitgevoerde commando's
- `cd web && npm ci && npm run check && npm test && npm run build && npm run verify:build && node scripts/check-bundle-size.mjs`: alles groen. `svelte-check` geeft 0 errors en 0 warnings, `write-headers: ok (1 inline script hash(es))`, `verify-build: ok`.
- `bash scripts/check-no-client-openmeteo.sh`: ok.
- Ingest: `uv run pytest` geeft 1569 passed en 24 skipped (skips komen door een ontbrekende lokale Supabase-env, bestaand gedrag). `ruff check` en `ruff format --check` zijn schoon.
- CI-run 38810174216 op `wp/WP-23`: jobs `web`, `db` en `ingest` zijn alle success.

## Harde regels
- Geen secrets in de diff. De Supabase-URL komt alleen bij de build uit de env en staat niet in `static/_headers`.
- Geen tracking. `grep` op trackers en CDN's in `src`, `static` en `build` geeft niets. `verify-build` heeft `TRACKER_MARKERS`, `no-third-party.test.ts` bestaat en gebruikt zonder aanpassing. De externe hosts in `build` zijn alleen bronlinks, MapTiler en Supabase.
- Open-Meteo wordt niet client-side aangeroepen: guard-script ok, en de CSP laat Open-Meteo niet toe. De enige vermelding is de bronlink in de attributie.
- Bronvermelding intact en uitgebreid. `Attribution.svelte` noemt nu ook de golfmodellen van DWD en ECMWF, en `attribution.test.ts` is bijgewerkt.
- Offshore blijft `no_go`: niets in de diff raakt de evaluatie.
- Geen nieuwe betaalde dienst. De enige nieuwe dependency is `axe-core` (devDependency, gratis).
- Geen scraping.

## Extra controles
1. **Privacytekst tegen de code.** De `localStorage`-sleutels in `web/src` zijn `shakka:organizer_name`, `shakka:return_to`, `shakka:rsvp:{slug}` en de supabase-js-sessie. Dat zijn precies de sleutels in de tekst en in PRIVACY.md. `sessionStorage` en de Cache API worden onderbouwd (SW-cache `shakka-shell-<versie>`).
   - `takeReturnTo` en `pruneReturnTo` worden aangeroepen in `+layout.svelte`.
   - `clearStoredRsvp` wordt aangeroepen bij afmelden en bij `not_found`.
   - `signOut` roept `releasePushForSignOut` aan.
   - `shakka:rsvp:*` blijft na het verwijderen van het account staan, zoals PRIVACY.md zegt.
   - Er is geen `geolocation`-gebruik, dus "vraagt nooit om je locatie" klopt.
   - De logbewaartermijnen van Supabase (1 dag en 1 uur) en de Cloudflare-instellingen zijn externe feiten. Ze staan in het RUNBOOK en vallen onder de goedkeuring door Lars.
2. **`delete_my_account()`.** `security definer`, `set search_path = ''`, `revoke all` van `public`, `anon`, `authenticated` en `service_role`, daarna `grant execute` aan `authenticated`. Hij verwijdert alleen `auth.uid()` en geeft `PT401` bij `null`. Alle FK's naar `auth.users` zijn `on delete cascade`: `profiles`, `push_subscriptions` en `sessions` direct, `favorites` via `user_id`, `alert_rules` via `favorites`, `alert_state` via `user_id`. `rsvps` gaan mee via `sessions`.
3. **`_headers`.** Het sjabloon staat in `static/_headers` en wordt bij de build omgezet naar `build/_headers` (`write-headers.mjs`) met Supabase-origin en CSP-hash. `Referrer-Policy: strict-origin-when-cross-origin` en `X-Robots-Tag: noindex` op `/s/*` staan erin. `PRECACHE_EXCLUDED_PATHS` houdt `/_headers` uit de precache; de test controleert dat de lijst gelijk is aan `PRECACHE_EXCLUDED` in `check-bundle-size.mjs`.
4. **A11y.** De skiplink `Naar de inhoud` staat in `+layout.svelte` en verwijst naar `<main id="main" tabindex="-1">`. `a11y-compiler.test.ts` compileert alle `.svelte`-bestanden en eist 0 `a11y_`-waarschuwingen.
5. **Afwijking `dynamicImports` (deviations.md punt 4).** Beoordeeld als geen verzwakking.
   - `index.html` preloadt een kit-chunk die `entry/start` dynamisch importeert.
   - `dynamicImports` wordt alleen gebruikt om die preload te verklaren in de kruiscontrole.
   - `initial.files` is nog steeds de statische afsluiting plus de preloadbestanden, dus de chunk telt mee in de meting.
   - Budgetten zijn niet verhoogd: 150 en 900 kB.
   - De test voor een preload van `route.js` buiten de afsluiting blijft falen zoals bedoeld.
6. **Scope.** De gewijzigde bestanden vallen binnen de WP: web, migratie, pgTAP, docs en CI-stap. De wijziging in `07_sessions.test.sql` (r. 67 en 69) voegt alleen `delete_my_account` toe aan de verwachte lijsten. De `rsvp-storage`-refactor naar `browser-storage.ts` staat in de blueprint. Alle afwijkingen staan in `deviations.md`.
7. **WP-22 (parallel).** `07_sessions.test.sql` (r. 67 en 69) en `docs/RUNBOOK.md` (nieuw §17 aan het einde) worden mogelijk ook door WP-22 gewijzigd. Alleen noteren; mergeconflicten zijn bij de merge op te lossen.

## Problemen
Geen blokkerende problemen.

N-1 (informatief): `deviations.md` punt 5 en RUNBOOK §17 noemen precache 595,2 kB. De lokale meting geeft 595,1 kB. Dat is een afrondingsverschil binnen 0,1 kB en past ruim binnen het budget.

N-2 (informatief): `deviations.md` punt 8. `supabase db reset` en `supabase test db` zijn niet lokaal gedraaid. De CI-job `db` heeft ze wel gedraaid en was groen.
