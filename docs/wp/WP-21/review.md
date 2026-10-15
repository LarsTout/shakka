# Review WP-21, ronde 2
Oordeel: CHANGES_REQUIRED

Beoordeeld: blueprint revisie 2. Eerst de punten uit ronde 1:
- **B-1 (ronde 1) is opgelost.** WP-21 maakt geen enkel bestand aan dat ook in de tabel "Bestanden" van WP-20 (revisie 2) staat. Het gaat om `session-page-data.ts`, `session-model.ts`, `session-form.ts`, `sessions.ts`, `browser-storage.ts`, `local-prefs.ts`, `fixtures/session-data.ts`, `SessionForm.svelte` en de routes `sessie/…`, `go/…` en `mijn-sessies`. WP-20 belooft van zijn kant niets onder `routes/s/` aan te maken, en geen bestand met `rsvp`, `public-session` of `session-view` in de naam. De echte overlap staat goed in R3 en stap 9: `user-tables.test.ts` en `RUNBOOK.md`. Stap 8 controleert de drie verboden namen.
- **N-1 is correct opgelost.** `now` is een overschrijfbare `$derived`. De klok-`$effect` hangt af van `session` en `closed`, gaat 1 s na `ends_at` af, en draait daarna niet opnieuw zodra `closed` waar is. `serverClosed` reageert op `session_closed` van zowel `rsvp_create` als `rsvp_update`. De tests zijn (j), (18) en (19).
- **N-6 is correct opgelost.** De prefix `https://tikkie.me/` sluit al uit: hoofdletters, een poort, een gebruikersnaam, een subdomein, `www.` en `tikkie.me.evil…`. Daarna volgen nog de controles `new URL` en `hostname`. E38 en de tests dekken alle varianten.
- **N-8 klopt met de bron.** `abortSignal(signal): this` zet `this.signal`, en dat gaat mee naar `fetch`. `AbortSignal.timeout` breekt af met een `TimeoutError`. Een fetch die daardoor faalt, wordt bij `shouldThrowOnError === false` opgevangen en resolvet met `status: 0`, `data: null` en een `error`. Dat wordt dus `network`. De `typeof`-terugval en de aanpassing van `fake-rpc` zijn in orde.
- **N-2 t/m N-5, N-7 en N-9 t/m N-12** zijn verwerkt zoals beschreven.

## Blokkerend
B-1: De flow- en paginatests draaien met de echte klok, maar de fixtures liggen in het verleden. Daardoor falen de AC-3-tests zoals ze nu beschreven staan. Waar: Testplan, `rsvp-flow.test.ts` (1), (3), (5) en (6), plus `public-session-page.test.ts` en `public-session-page-integration.test.ts`. Waarom: dit probleem ontstaat door de revisie voor N-1.
- `applyRefresh` zet `now = new Date()`.
- De klok-`$effect` rekent met `Date.parse(ends_at) - Date.now()`.
- Alleen test (j) zet de klok vast. In `rsvp-flow.test.ts` loopt de echte datum (vanaf 15-10-2026), terwijl de fixturesessie op 18-07-2026 eindigt.

De gevolgen:
- Na de eerste verversing is `closed` waar. In (1) staat er na de create dan geen `Wijzigen`. In (3), na het afmelden, en in (6), na `invalid_token`, komt het veld `Voornaam` niet terug, terwijl de test dat verwacht. Die tests falen dus altijd.
- Daarnaast gaat de klok-timer bij elke render met een fixturesessie na 1 seconde echte tijd af (`Math.max(0, negatief) + 1000`). Daarna verdwijnen het formulier en `Wijzigen` midden in een test. Dat maakt vooral (2) en (5) (userEvent-reeksen) en de paginatests (a)–(h) wisselvallig.
- Een builder moet dan zelf kiezen hoe hij dit oplost. De verleidelijkste verkeerde keuze is `now = new Date()` uit `applyRefresh` halen, en dan valt N-1 terug.

Voorstel: zet in `beforeEach` van `rsvp-flow.test.ts`, `public-session-page.test.ts` en `public-session-page-integration.test.ts` deze twee regels:
- `vi.useFakeTimers({ toFake: ['Date'] })`;
- `vi.setSystemTime(new Date(NOW))`.

Dit is hetzelfde patroon als WP-20. `afterEach` heeft `vi.useRealTimers()` al. Test (j) zet zijn eigen tijd en timers (eerst `vi.useRealTimers()`, of direct opnieuw `useFakeTimers` met zijn eigen `toFake`). Test (i) rekent al relatief aan `Date.now()`, dus die blijft werken. Met `Date` op NOW (09:00Z) ligt `ends_at` 7 uur verder. De timer gaat dan niet af binnen een test, en `applyRefresh` houdt de sessie open. Omdat `setTimeout` echt blijft, werken `userEvent` en `findBy*` ongewijzigd.

## Niet-blokkerend
N-1: De WP-20-namen in A20, "Consistentie" (WP-20) en stap 9 kloppen niet met de WP-20-blueprint revisie 2. De bewering "Gecontroleerd in de WP-20-blueprint" is daarom onjuist. Wat WP-20 echt levert:
- `SESSION_SLUG_RE`, `isValidSessionSlug(slug)` en `countCodePoints(s)` in `#lib/session-model.ts`, met precies dezelfde namen als in WP-21 (WP-20 r. 100, 191–199, A17);
- `StorageLike` en `browserStorage(): StorageLike | undefined` in een eigen module `#lib/browser-storage.ts` (WP-20 r. 296–309). Dus niet `KeyValueStorage`, niet in `local-prefs.ts`, en de functie geeft `undefined` en niet `null`.

`formatWindowLocal(start: Date, end: Date)` in `time.ts` klopt wel. Stap 9 zoals het er nu staat:
- importeert `SESSION_SLUG_PATTERN`, `isSessionSlug`, `codePointLength` en `KeyValueStorage`, en die bestaan niet. `npm run check` faalt dan. Volgens het R10-criterium draait de builder dat terug, en de dubbele helpers blijven staan. Dat is veilig, dus niet blokkerend, maar het mist het doel.
- Correcter is in `session-view.ts`: `export { SESSION_SLUG_RE, isValidSessionSlug, countCodePoints } from './session-model.js';` en de eigen definities verwijderen.
- Laat `browserStorage` in `rsvp-storage.ts` staan. WP-20 geeft `undefined`, en de bestaande WP-21-test eist `null`. Die test mag volgens het criterium niet veranderen. Noteer het als opruimpunt.
- Laat de `git ls-tree`-controle `web/src/lib/browser-storage.ts` noemen in plaats van `local-prefs.ts`. Werk ook A20 bij: "`browserStorage()` geeft `null` en niet `undefined`" is het omgekeerde van WP-20.

N-2: De WP-20-blueprint (Consistentie r. 674 en 678) beschrijft WP-21 nog als revisie 1: `safeHttpsLink`, en `sessionWindowText` voluit ("zaterdag 18 juli, 14:00–18:00"). Dat moet de orchestrator in WP-20 bijwerken; het is geen fout in WP-21. Optioneel voor stap 9: `tikkieLink` vervangen door `safeTikkieLink(url)?.href ?? null` uit `session-model.ts`. De regels verschillen alleen in `\S+` en de grens van 200 tekens. De DB-CHECK verbiedt witruimte en lengte boven 200 al, dus het zichtbare gedrag is gelijk.

N-3: In `rsvp-flow.test.ts` (13) slaagt `rerender` met een nieuwe `data` alleen als de klok niet verder loopt (zie B-1). Met de klok op NOW is dat in orde. Ik noem het alleen zodat de builder (13) na de fix van B-1 niet als apart probleem ziet.

## Gecontroleerde bronnen
- https://raw.githubusercontent.com/supabase/supabase-js/master/packages/core/postgrest-js/src/PostgrestTransformBuilder.ts: `abortSignal(signal: AbortSignal): this { this.signal = signal; return this }`. De docs noemen expliciet "You can use this to set a timeout for the request."
- https://raw.githubusercontent.com/supabase/supabase-js/master/packages/core/postgrest-js/src/PostgrestBuilder.ts: bij `!this.shouldThrowOnError` doet `res.catch(fetchError => …)` de afhandeling, met `status: 0`, `data: null` en een `error` met `code` en `hint`. Een `AbortError` krijgt alleen een andere hint. `signal: this.signal` gaat mee naar `fetch`. De builder is thenable.
- https://developer.mozilla.org/en-US/docs/Web/API/AbortSignal/timeout_static: "Baseline 2024" (newly available sinds april 2024). Het signaal breekt af met een `TimeoutError`-`DOMException`. E48 en de `typeof`-controle kloppen.
- Lokaal gecontroleerd:
  - `.claude/worktrees/WP-20/docs/wp/WP-20/blueprint.md` (revisie 2): tabel "Bestanden", `session-model.ts`, `browser-storage.ts`, `time.ts` (`formatWindowLocal`), Testplan (`session-tables`, `user-tables`, `browser-storage`, `time.test`) en R1;
  - `supabase/migrations/20261015200000_sessions.sql`: regexen, `using message`-codes per functie, `>= 30`, `between 0 and 8`, `between 1 and 30` en `interval '7 days'`. Er zijn geen latere migraties, dus driftcheck (0) is nu groen;
  - `web/src/lib/time.ts`: `formatLocal` `day`/`dateTime` geven `za 18 jul` en `za 18 jul 22:00`. De verwachtingen voor DST en middernacht in de `sessionWindowText`-tests kloppen. 18-07-2026 is een zaterdag en 25-10-2026 een zondag;
  - `web/src/routes/+layout.ts` (`ssr = false`, `prerender = false`), `web/vite.config.ts` (fallback `index.html`) en `web/test/user-tables.test.ts`.
