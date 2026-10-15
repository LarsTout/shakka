# Verificatie WP-20, ronde 1
Resultaat: NEEDS_LARS

Alle automatisch toetsbare criteria zijn PASS. Alleen AC-6 (telefoon, echte push en WhatsApp) en de Mailpit-browserstap blijven voor Lars.

| Criterium | Resultaat | Bewijs |
|---|---|---|
| AC-1 | PASS | `cd web && npm ci && npm run check` 0 errors, 0 warnings (630 files). `npm test`: 66 files, 810 tests groen. `npm run build` ok, `npm run verify:build` "ok". `bash scripts/check-no-client-openmeteo.sh` "ok". Ingest: `uv run pytest` 1569 passed, 24 skipped (lokale Supabase-stack); `ruff check` en `ruff format --check` groen. CI `ci` op `wp/WP-20` (commit "docs(WP-20): verifying"): completed, success. |
| AC-2 | PASS | `go.test.ts`, `go-page.test.ts` (b: uitgelogd slaat exacte URL op en gaat één keer naar `/login`; c: ingelogd naar het `/sessie/nieuw`-doel zonder opslag), `layout.test.ts` (terugkeer, 60 min, sleutel verwijderd), `session-form.test.ts` E12/E13 en `new-session-page.test.ts` (c) rond 2026-10-25: allemaal groen. Zelf nagerekend met een tijdelijke test (daarna verwijderd): `localWallTimeToUtc('2026-10-25','02:30')` geeft de eerste 02:30 (`00:30Z`, kandidaten `00:30Z` en `01:30Z`), `'14:00'` geeft `13:00Z`; `2027-03-28` `02:30` geeft `null` (gat), `03:00` geeft `01:00Z`. |
| AC-3 | PASS | `session-model.test.ts` en `share-page.test.ts` groen. `whatsappUrl` is `https://wa.me/?text=${encodeURIComponent(text)}`. `shareText` heeft spotnaam, lokaal tijdvenster via `formatWindowLocal` en de URL. |
| AC-4 | PASS | `session-form-component.test.ts` (a t/m e: `ends == starts`, `ends < starts`, seats 9, Tikkie http en vreemde host, naam van 31 tekens), `new-session-page.test.ts` (f: geen write bij weigering), `session-schema.test.ts` (drift met de migratie) groen. |
| AC-5 | PASS | `sessions.test.ts` ("sets cancelled_at only") en `my-sessions-page.test.ts` (b: alleen `organizer_id = USER_ID`, `ends_at > now`; d: annuleren in twee stappen) groen. `user-data.test.ts` toetst de `.eq('organizer_id', ...)`. |
| AC-6 | NEEDS_LARS | Telefoon: echte pushmelding, aanmaken, delen naar WhatsApp en de link openen. Nodig: WP-19-migratie in productie, `APP_BASE_URL` gezet, deze WP op de productie-URL, push aan op de telefoon. Procedure in blueprint Testplan stap 1 t/m 8. Ook niet gedaan: browserstap `npm run preview` met Mailpit (geen lokale Supabase-stack). |

## Harde regels
- Geen secrets: `git grep -E "sb_(secret|publishable)_..|eyJhbGciOi" -- . ':!docs'` leeg; geen `sb_secret_`/`service_role` in de diff; `web/.env` is gitignored en niet getrackt.
- Geen client-side Open-Meteo: `check-no-client-openmeteo.sh` ok; geen `open-meteo` in de nieuwe routes of libs.
- Privacy en tracking: `wa.me` komt in `web/src` alleen voor in `session-model.ts` (regel 122: `https://wa.me/?text=` plus `encodeURIComponent`, geen andere parameters). Web Share gebruikt alleen `{ text }`. Geen analytics, `fetch(` of `@html` in de nieuwe bestanden. Lokaal bewaard: `shakka:organizer_name` en `shakka:return_to` (hoogstens 60 min), beide in `local-prefs.ts`.
- Geen scraping, geen nieuwe betaalde dienst, geen nieuwe dependency. Bronvermelding (`Attribution`) ongewijzigd. Offshore-logica niet geraakt; `goRuns` neemt alleen `verdict === 'go'`.
- `/go`-terugkeer (zelf geprobeerd via `isAllowedReturnPath` en `takeReturnTo`, met een tijdelijke test die daarna is verwijderd): geweigerd zijn `https://evil`, `//evil`, `/profiel`, `/go`, `/go?`, `/go?spot=a`, `//evil/go?...`, `https://evil/go?...`, `/go?/../x`, `/\evil` en `javascript:alert(1)`. In `takeReturnTo` geven een geïnjecteerd `//evil`, `https://evil`, `/profiel`, onleesbare JSON, een waarde ouder dan 61 min en een `saved_at` in de toekomst allemaal `null`, en de sleutel is steeds verwijderd. Precies 60 min is geldig, 60 min + 1 ms niet; de sleutel is dan ook verwijderd. Het `goto`-doel komt uit `newSessionHref(parseGoParams(url))`, dus uit geparste waarden.
- Sessies: `insertSession` stuurt exact de acht kolommen en laat `organizer_id` en `slug` weg; de test geeft bewust extra `organizer_id`, `slug` en `cancelled_at` mee en toetst dat de payload `NEW` blijft. `createSession` herhaalt alleen op `23505`, één keer (test "gives up after a second collision"). `updateSession` stuurt alleen `SESSION_EDITABLE_COLUMNS`; annuleren zet alleen `cancelled_at`. Schrijven (`.insert`/`.update`/`.upsert`/`.delete`) staat alleen in `user-data.ts`; `data.ts` heeft alleen bestaande leesqueries; `session-tables.test.ts` bewaakt de purity.
- Tikkie: `isTikkieUrl` geeft `false` voor `https://tikkie.me.evil.com/x`, `https://user@tikkie.me/x`, `https://tikkie.me@evil.com/x`, `https://tikkie.me/`, `https://tikkie.me`, `http://tikkie.me/x`, `https://TIKKIE.me/x`, `https://tikkie.me:444/x`, `https://tikkie.me/x y` en `HTTPS://tikkie.me/x`; `true` voor `https://tikkie.me/pay/abc`.
- "Ik ga": alleen zichtbaar met `$session` (`spot-page.test.ts` "Ik ga links (WP-20, A16)"). `GO_RUN_MIN_HOURS = 1` in `go.ts`.
- Gedeelde helpers voor WP-21 bestaan met exact deze namen: `SESSION_SLUG_RE`, `isValidSessionSlug`, `countCodePoints`, `isTikkieUrl` in `session-model.ts`; `StorageLike`, `browserStorage` in `browser-storage.ts`. Er zijn geen bestanden met `public-session-*` in de naam.
- Scope: gewijzigd zijn alleen `web/`, `docs/RUNBOOK.md`, `docs/STATUS.md` en `docs/wp/WP-20/`. Geen wijzigingen in `ingest`, `supabase`, `data` of `scripts`. De diff komt overeen met de blueprint; de afwijkingen (N-2 t/m N-5, commit-indeling, extra tests) staan in `deviations.md` en raken geen acceptatiecriterium.

## Problemen
Geen fails.

N-1 (geen fail, informatief): AC-6 en de Mailpit-stap vragen Lars. Vooraf nodig: WP-19-migratie in productie, `APP_BASE_URL` gezet, WP-20 op de productie-URL, push aan op de telefoon; daarna blueprint Testplan stap 1 t/m 8, met de uitkomst per stap hier genoteerd.
