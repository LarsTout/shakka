# Afwijkingen WP-21

## N-1 ronde 3: tabelrij N-9 (ronde 1) is achterhaald
De rij N-9 in "Verwerking review, Ronde 1" van de blueprint zegt dat `browserStorage` `null` geeft zoals in WP-20 en dat stap 9 `browserStorage` vervangt. Dat is achterhaald (zie A20): WP-20 geeft `undefined`, WP-21 `null`. Gebouwd volgens A20: `browserStorage` blijft de eigen versie in `rsvp-storage.ts` (geeft `null`); alleen het type `StorageLike` komt uit `#lib/browser-storage.ts`. Impact: geen. Opruimpunt blijft staan voor een latere WP (uiterlijk WP-23).

## Stap 9 (hergebruik WP-20-helpers): direct uitgevoerd
De branch is gerebased op `develop` mét WP-20, dus de helpers bestonden al bij het begin van de bouw. In plaats van eerst eigen kopieën te maken en ze later te vervangen, is meteen de eindvorm van stap 9 gebouwd (één commit-reeks, geen aparte stap 9-commit):
- (9a) `session-view.ts` herexporteert `SESSION_SLUG_RE`, `isValidSessionSlug` en `countCodePoints` uit `#lib/session-model.ts`; er zijn geen eigen definities.
- (9b) `sessionWindowText` roept `formatWindowLocal(new Date(startsAt), new Date(endsAt))` aan uit `#lib/time.ts`. De test in `session-view.test.ts` met de vensternotatie (A21) is groen, ook voor de wintertijd-gevallen.
- (9c) `tikkieLink` gebruikt `isTikkieUrl(url) ? new URL(url).href : null` (`safeTikkieLink` bestaat niet in de gemergde WP-20). Daarvoor blijft een snelle prefixcontrole (`TIKKIE_PREFIX`, minstens één teken erna) staan. Alle Tikkie-testgevallen uit het Testplan (E38) zijn groen.
- (9d) `rsvp-storage.ts` heeft `import type { StorageLike }` en `export type { StorageLike }` uit `./browser-storage.js`.
- `browserStorage` blijft dubbel (zie hierboven).
- `user-tables.test.ts`: geen conflict; alleen de test `no file uses .rpc(` is vervangen door de allowlist-test met `RPC_FILES = ['lib/rsvp.ts']`.
Geen WP-20-bestand is gewijzigd (alleen `user-tables.test.ts` en `docs/RUNBOOK.md` §16).

## Kleine afwijkingen
- `RsvpForm.svelte`: `prefix` is `untrack(() => ...)`, zodat svelte-check geen waarschuwing geeft over het lezen van `mode` buiten een closure. Zelfde gedrag.
- Spaties in `SessionParticipants.svelte` en `RsvpPanel.svelte` staan als `{' '}` voor `<bdi>`, omdat Svelte de spatie aan het begin van een `{#if}`-blok weghaalt (anders zou de tekst "Rijdt mee metEva" worden). Zichtbaar gedrag is wat de blueprint beschrijft.
- `rsvp-contract.test.ts` heeft de controle van de verzonden sleutels (1b) in hetzelfde bestand, met een eigen `vi.mock` van `#lib/supabase.js`.
- Test (j) in `public-session-page.test.ts` controleert na `unmount()` dat `vi.getTimerCount()` terug is op de beginstand van een verse fake-timerklok (in plaats van de telling van vóór de eerste render).
- Klok in de drie pagina-/flowtests: `vi.useFakeTimers({ toFake: ['Date'] })` plus `vi.setSystemTime(new Date(NOW))` in `beforeEach` (B-1 ronde 2). `applyRefresh` en de klok-`$effect` zijn ongewijzigd (N-1 niet teruggedraaid).

## Niet uitgevoerd
- Stap 7 (handmatige rooktest tegen de lokale stack): Docker is in deze omgeving niet bereikbaar. AC-7 blijft `NEEDS_LARS` (RUNBOOK §16.9).
- R4 (`<svelte:head>` in jsdom): de `meta`-tag is in `document.head` te vinden; er is geen terugvaloptie nodig.
- Browsercontrole van `noindex` in de gebouwde app (`npm run preview`): niet gedaan, hoort bij de rooktest.
