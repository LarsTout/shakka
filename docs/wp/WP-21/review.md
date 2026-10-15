# Review WP-21, ronde 3
Oordeel: APPROVED

Beoordeeld: blueprint revisie 3. Dit is een gerichte review op de punten uit ronde 2 en op wat er in revisie 3 nieuw is.

**(a) B-1 uit ronde 2 is opgelost.**
- In het Testplan staat een nieuwe alinea "Vaste klok in de pagina- en flowtests". Die zet `vi.useFakeTimers({ toFake: ['Date'] })` en `vi.setSystemTime(new Date(NOW))` in `beforeEach` van alle drie de bestanden: `rsvp-flow.test.ts`, `public-session-page.test.ts` en `public-session-page-integration.test.ts`. Elke tabelcel verwijst naar die alinea.
- Alleen `Date` wordt nep gemaakt. `setTimeout` en de microtaken blijven echt, dus `userEvent`, `findBy*` en `waitFor` werken ongewijzigd. Testing Library herkent hier geen Jest-fake-timers en gebruikt dus de echte timers.
- Met `Date.now()` op `NOW` (09:00Z) ligt `ends_at` 7 uur later. De klok-timer gaat dus niet af binnen een test, en `applyRefresh` houdt de sessie open. Dat dekt (1), (3), (5), (6) en (13).
- (b) `NOW_ENDED`, (e) `NOW_STALE` en (i) rekenen met `data.now` of relatief aan `Date.now()`, en blijven dus kloppen.
- `afterEach` doet al `vi.useRealTimers()`.

**N-1 uit ronde 1 is niet teruggedraaid.** A5 is ongewijzigd: `applyRefresh` zet `now = new Date()`, en de klok-`$effect` gaat 1 s na `ends_at` af. De nieuwe alinea verbiedt de builder ook uitdrukkelijk om dit weg te halen als oplossing.

**Test (j) blijft correct.** De test doet eerst `vi.useRealTimers()` en zet daarna eigen fake timers voor `setTimeout`, `clearTimeout` en `Date`, plus een eigen systeemtijd van 15:59Z. Daarna volgen `advanceTimersByTime(61_000)` en de check met `getTimerCount` na `unmount`. `await tick()` van Svelte gebruikt microtaken, en die zijn niet nep, dus dat werkt.

**(b) N-1 uit ronde 2 is opgelost.** Ik heb dit vergeleken met WP-20 revisie 2. Alle namen en vormen kloppen:
- `session-model.ts`: `SESSION_SLUG_RE` (r. 191), `isValidSessionSlug` (r. 193) en `countCodePoints` (r. 199);
- `safeTikkieLink(url): { href; host } | null` (r. 208);
- `formatWindowLocal(start: Date, end: Date)` in `time.ts` (r. 265);
- `browser-storage.ts` met `StorageLike = Pick<Storage, 'getItem' | 'setItem' | 'removeItem'>` en `browserStorage(): StorageLike | undefined` (r. 296–309).

Wat stap 9 nu doet:
- **9a** gebruikt `export { … } from './session-model.js'` met daarnaast een lokale `import { countCodePoints }`. Dat is geldige TS, en de importeurs van `session-view.js` hoeven niet te veranderen.
- **9d** gebruikt `import type` plus `export type { StorageLike } from './browser-storage.js'`. Ook dat is geldig.
- `browserStorage` blijft de eigen versie (`null`), en het opruimpunt staat bij "Gevolgen".
- `git ls-tree` controleert `web/src/lib/session-model.ts` en `web/src/lib/browser-storage.ts`.
- A20 beschrijft het WP-20-gedrag nu correct (`undefined`).

**9c (optioneel)** levert dezelfde uitkomst voor alle Tikkie-testgevallen van WP-21. De regex van WP-20 is hoofdlettergevoelig en eist minstens één teken na `tikkie.me/` (`\S+`). Daarnaast sluit `isTikkieUrl` een gebruikersnaam, een wachtwoord en een poort uit.

**(c) Revisie 3 introduceert niets dat blokkeert.**

## Blokkerend
Geen.

## Niet-blokkerend
N-1: De tabel "Ronde 1 (revisie 2)", rij N-9, zegt nog dat `browserStorage` "nu `null` geeft zoals in WP-20" en dat stap 9 `browserStorage` vervangt. Dat is historisch en staat al gemarkeerd met de "Let op"-zin boven die tabel. Toch kan een builder die alleen die rij leest, op het verkeerde been gezet worden. Overweeg om er "(achterhaald, zie A20)" achter te zetten.

N-2: Bij 9a staat de tekst "Gebruikt `session-view.ts` zelf ook `SESSION_SLUG_RE` of `isValidSessionSlug`, neem die dan ook in de lokale `import` op". Dat is correct, maar `npm run check` vangt dit toch al af. Geen actie nodig.

## Gecontroleerde bronnen
- https://vitest.dev/api/vi.html: de opties `vi.useFakeTimers` en `toFake`, en `vi.setSystemTime`. De docs zeggen: "If fake timers are not enabled, this method will only mock `Date.*`". Het patroon `toFake: ['Date']` is hetzelfde als in WP-20 (Testplan, r. 753).
- Lokaal gecontroleerd:
  - `.claude/worktrees/WP-20/docs/wp/WP-20/blueprint.md` (revisie 2, APPROVED): r. 50–55, 100, 104, 185–208, 255–265, 296–313 en 753;
  - `.claude/worktrees/WP-21/docs/wp/WP-21/blueprint.md` (revisie 3): A5, A20, Interfaces (`session-view.ts`, `rsvp-storage.ts`), "Consistentie" (WP-20), "Gevolgen", de Testplan-alinea "Vaste klok", de testcellen (j), (i), (13), stap 9 en "Verwerking review" ronde 2.
