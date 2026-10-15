# Verificatie WP-21, ronde 1
Resultaat: NEEDS_LARS

Alle criteria behalve AC-7 zijn aantoonbaar gehaald. AC-7 (rooktest op een telefoon, `noindex` via de preview) is NEEDS_LARS by design.

| Criterium | Resultaat | Bewijs |
|---|---|---|
| AC-1 | PASS | In `web`: `npm ci`, `npm run check` (0 errors, 0 warnings, 653 files), `npm test` (75 files, 903 tests groen), `npm run build` en `npm run verify:build` (ok) slagen. CI-run 38786281620 op `wp/WP-21` is `success`. |
| AC-2 | PASS | `public-session-page.test.ts` (a) en `public-session-page-integration.test.ts` renderen deelnemers, carpool en uren van het window met gemockte RPC's. `session-no-auth.test.ts` en `authSpy` bewijzen dat auth niet wordt aangeraakt. `grep` op `#lib/auth`, `.auth` en `getSession` in de nieuwe bestanden levert niets. |
| AC-3 | PASS | `rsvp-flow.test.ts` (1) toetst de getrimde naam `Sanne` in `createRsvp` en de opslag onder `shakka:rsvp:{slug}` met exact `{rsvp_id, edit_token}`. (2) toetst "Jij gaat" met Wijzigen en Afmelden na het opnieuw renderen. (3) toetst dat `deleteRsvp(TOKEN)` wordt aangeroepen en de sleutel weg is. De token komt niet in de DOM of URL. |
| AC-4 | PASS | (7) toetst vier eigen NL-teksten voor `rate_limited`, `session_full`, `session_closed` en `invalid_input` (4 unieke teksten, geen codenaam op het scherm). (8) toetst dat een onbekende fout alleen de generieke tekst toont. Mijn eigen controle: `rsvpErrorKind` geeft `unknown` bij `PT400` met een vreemde of gevaarlijke tekst (`DROP TABLE <b>x`, `__proto__`, `toString`) en bij een andere SQLSTATE met een bekende tekst. |
| AC-5 | PASS | `<meta name="robots" content="noindex" />` staat in `<svelte:head>` van `+page.svelte`. Er zijn tests voor `ok` en `not_found` (`public-session-page.test.ts` (b), `session-no-auth.test.ts`). De banner voor een geannuleerde of afgelopen sessie bestaat, en `RsvpPanel` toont geen formulier bij `closed` (tests (b), (15), (18), (j)). |
| AC-6 | PASS | `<Attribution />` staat op de sessiepagina (test (c)) en `<Attribution compact />` in `+layout.svelte`. |
| AC-7 | NEEDS_LARS | Handmatige rooktest op een telefoon tegen een echte of lokale stack. Docker is niet beschikbaar. Procedure staat in RUNBOOK §16.9. `noindex` in de gebouwde preview moet Lars controleren. |

## Harde regels
- Persoonsgegevens: PASS. Het formulier heeft alleen voornaam en vervoer. Er zijn geen e-mail, IP of tracking. De privacytekst is zichtbaar. De RPC-keys komen overeen met de migratie.
- Geen tracking of CDN: PASS. In de nieuwe `src`-bestanden staat geen externe URL behalve `TIKKIE_PREFIX`.
- Open-Meteo: PASS. `bash scripts/check-no-client-openmeteo.sh` geeft ok.
- Geen secrets in de diff: PASS (grep op sleutelpatronen levert niets). Geen scraping. Geen nieuwe dienst of package (`package.json` ongewijzigd).
- Offshore blijft `no_go`: PASS. De pagina hergebruikt `HourVerdict` ongewijzigd, en (a) toont "Niet gaan / Aflandige wind: niet kiten".
- Bronvermelding: PASS (zie AC-6).

## Extra beveiligingscontroles
1. `.rpc(` komt voor in precies één bestand, `src/lib/rsvp.ts` (één `supabase.rpc(`-aanroep). `user-tables.test.ts` bewaakt dit met allowlist `RPC_FILES = ['lib/rsvp.ts']`. Er is geen `get`/`head`-optie, dus POST met de token in de body. `.from(` en auth komen er niet voor (`session-no-auth.test.ts`).
2. De token staat alleen in `localStorage` via `rsvp-storage.ts`, per slug. Andere `localStorage`-treffers zijn alleen commentaar en `browser-storage.ts` (WP-20). Er is geen `goto`, `history` of `location` in de nieuwe bestanden. De `console.`-treffers zijn drie vaste `console.warn`-teksten zonder variabelen (`public-session-data.ts` twee keer, `RsvpPanel.svelte` één keer). De test blokkeert `console.log/info/debug`. `RsvpError.message` bevat alleen `operation` en `kind`.
3. De ruwe servertekst wordt nooit getoond: `.message` en `error.details` worden in UI-code nergens gelezen. Elke code gaat via `RSVP_MESSAGES`, met `unknown` als generieke terugval.
4. XSS: er is geen `{@html}` in `src` (grep). Alle namen en vrije teksten staan in `<bdi>`. Namen in `<option>` krijgen FSI/PDI via `isolateText`. Tikkie staat alleen als `https://tikkie.me/…` met `target="_blank" rel="noopener noreferrer"`. Eigen scratchtest (daarna verwijderd, werkboom schoon) met `<script>alert(1)</script>`, `<img onerror>` en U+202E als organisator, notitie, vertrekpunt en voornaam: er ontstaat geen `<script>` of `<img>` in de DOM, de tekst staat geëscapet en elke U+202E staat binnen een `<bdi>`. Zeven hostile Tikkie-URL's (`javascript:`, `http:`, `tikkie.me.evil.com`, `tikkie.me@evil.com`, andere poort, spatie, hoofdletters) en meer worden geweigerd.
5. `noindex` is aanwezig in `<svelte:head>`. De route heeft `ssr = false`, dus controle in `build/` is niet mogelijk. Zie AC-7 voor de preview.
6. De contracttest `rsvp-contract.test.ts` is groen tegen `supabase/migrations/20261015200000_sessions.sql`: parameternamen, verzonden sleutels (1b), JSON-keys, foutcodes `PT400`, regexen, retentie van 7 dagen en limieten (30 tekens, 8 plekken, 30 RSVP's). Er is ook een driftcontrole voor latere migraties.
7. De drie pagina- en flowtests gebruiken een vaste klok (`useFakeTimers({ toFake: ['Date'] })` plus `setSystemTime`). `applyRefresh` zet `now = new Date()`. De `ends_at`-timer bestaat (`$effect` met `setTimeout`) en test (j) toetst dat het formulier na `ends_at` sluit en dat de timer bij `unmount` wordt opgeruimd.
8. Hergebruik van WP-20: `session-view.ts` herexporteert `SESSION_SLUG_RE`, `isValidSessionSlug` en `countCodePoints` uit `session-model.ts` en gebruikt `isTikkieUrl` en `formatWindowLocal`. Er zijn geen eigen definities (grep). Alleen `browserStorage` is dubbel, gedocumenteerd in `deviations.md` en `StorageLike` komt uit WP-20.
9. Scope: gewijzigd zijn alleen nieuwe WP-21-bestanden, `app.css` (WP-21-sectie), `user-tables.test.ts` (allowlist), RUNBOOK §16 (punten 8 en 9), `STATUS.md` en `docs/wp/WP-21/*`. Er is geen WP-20-bronbestand gewijzigd.
10. De ingest-suite is groen: 1569 passed, 24 skipped (lokale Supabase), ruff check en format zijn ok.

## Problemen
Geen. Open voor Lars: AC-7 (rooktest op een telefoon zonder account: aanmelden, wijzigen, afmelden, plus `noindex` in de Cloudflare-preview, RUNBOOK §16.9).
