# Review WP-21, ronde 1
Oordeel: CHANGES_REQUIRED

## Blokkerend
B-1: Drie bestanden van deze blueprint bestaan ook in WP-20, met een andere inhoud. Het gaat om `web/src/lib/session-page-data.ts`, `web/test/session-page-data.test.ts` en `web/test/fixtures/session-data.ts`. Waar: tabel "Bestanden", "Interfaces" (`session-page-data.ts`), Testplan (Fixtures), R3 en "Consistentie met afhankelijke WP's" (WP-20). Waarom: WP-20 wordt parallel gebouwd. Zijn blueprint (`.claude/worktrees/WP-20/docs/wp/WP-20/blueprint.md`, tabel "Bestanden" r. 89 en 105, Testplan r. 696–713 en 736, stap 5) maakt dezelfde drie bestanden aan:
- `session-page-data.ts` met `loadNewSessionPage`, `loadSharePage` en `loadMySessionsPage`;
- een eigen `session-page-data.test.ts`;
- fixtures met `SLUG`, `SESSION_ROW`, `NOW_SESSIONS` en `GO_URL_*`.

Wie als tweede merget, krijgt add/add-conflicten in drie bestanden met totaal verschillende inhoud. Dat is geen mechanisch samenvoegen. `fixtures/session-data.ts` exporteert in beide WP's bijvoorbeeld `SLUG`, en de tests importeren elk hun eigen set. Daarmee kloppen de claims "minder mergeconflicten met WP-20" (Bestanden), "Er is geen afhankelijkheid van WP-20-code" en R3 ("alleen `user-tables.test.ts` en `app.css`") niet. Ook de eindcontrole van de builder (`git diff --stat develop` raakt alleen bestanden uit de tabel) beschermt hier niet tegen. Voorstel: geef de WP-21-bestanden eenduidige namen, bijvoorbeeld `#lib/public-session-data.ts` (`PublicSessionPageData`, `loadPublicSessionPage`), `test/public-session-data.test.ts` en `test/fixtures/public-session.ts`. Pas alle verwijzingen aan: de lagenschets, `+page.ts`, de imports in de tests, `session-no-auth.test.ts` en "Gevolgen voor latere WP's" (WP-23-axe). Werk R3 bij met de echte overlap met WP-20, dus `user-tables.test.ts` (andere tests in hetzelfde bestand) en `app.css`.

## Niet-blokkerend
N-1: "Gesloten" volgt na een `session_closed` van de server niet altijd. `closed` gebruikt `data.now` van de load. Blijft de pagina open tot na `ends_at`, dan staat het formulier er nog. De server geeft dan `session_closed`, maar de verversing (`refresh()`) verandert alleen `session` en niet `now`. Bij een sessie die alleen in de tijd voorbij is, blijft het formulier dus staan en kan de bezoeker steeds opnieuw dezelfde melding krijgen. E15 ("dan volgen de melding en een verversing") wekt de indruk dat dit vanzelf goed komt. Voorstel: een lokale vlag `serverClosed` in `RsvpPanel` (of een `closedOverride` op de pagina), die bij `session_closed` het formulier en Wijzigen verbergt. Of geef `isSessionClosed` na een verversing `new Date()` mee.

N-2: R8 zegt dat de pagina "Sessie niet gevonden" `SESSION_RETENTION_DAYS` volgt, maar de markup bevat de vaste tekst "Sessies verdwijnen 7 dagen na afloop." Gebruik daar `{SESSION_RETENTION_DAYS}`, zodat de drifttest ook deze tekst dekt.

N-3: `RSVP_MESSAGES.session_full` zegt "er kunnen hoogstens 30 mensen mee". De pagina telt de organisator mee (A12), dus bij een volle sessie staat er "Deelnemers (31)". Voorstel: "Deze sessie zit vol: er kunnen hoogstens 30 mensen zich aanmelden."

N-4: Robuustheid van de contracttest. `rsvp-contract.test.ts` leest alleen `20261015200000_sessions.sql` en zoekt naar `create function public.<name>(`. Vervangt een latere migratie (bijv. WP-22 of een nieuwe bewaartermijn, WP-19 A1) een functie met `create or replace function`, dan blijft de test groen op de oude tekst. Voorstel: lees alle migraties in sorteervolgorde en neem per functie de laatste definitie (`create (or replace )?function public.<name>\(`). Of laat de test falen zodra een latere migratie een van de vijf functienamen noemt, met de melding "update rsvp-types.ts and this test", zoals `session-schema.test.ts` in WP-20 doet. Maak in test (2) ook expliciet dat het stuk na `'rsvps'` begint, dus dat de sleutel `'rsvps',` zelf niet meetelt.

N-5: Specificeer in `rsvp-flow.test.ts` een standaardantwoord voor `getPublicSession`, bijvoorbeeld `mockResolvedValue({ session: SESSION_INFO, rsvps: [...4] })` in `beforeEach`. Zonder dat geeft de `vi.fn` `undefined`. `applyRefresh(undefined)` zet dan `gone = true`, waardoor stap (3) tot en met (8) "Sessie niet gevonden" tonen in plaats van het verwachte formulier of de melding.

N-6: Tikkie-link. De blueprint accepteert elke `https:`-host en toont die host. Dat is consistent met WP-19 R5 en de WP-20-validatie (alleen `https://`). Wil Lars alleen `https://tikkie.me/...` toestaan, dan moet dat ook in WP-20 (en eventueel in de DB-CHECK). Anders accepteert WP-20 links die WP-21 stil verbergt. Dit is een beslissing voor Lars, geen fout in deze blueprint.

N-7: Een `<option>` kan geen `<bdi>` bevatten. In de keuzelijst "Rijd mee met" kan een naam met U+202E dus de optietekst omdraaien. Dit is cosmetisch. Voorstel: zet de optietekst tussen U+2068 en U+2069 (FSI/PDI), of accepteer het en noteer het.

N-8: Een RPC heeft geen timeout. Op een slechte mobiele verbinding kan "Bezig…" eindeloos blijven staan. Optioneel: `.abortSignal(AbortSignal.timeout(15_000))` op de builder van `supabase.rpc(...)`. Dat blijft een POST, en een afgebroken fetch geeft `status: 0`, dus `network`. Pas dan `fake-rpc` en de `argCount`-check aan.

N-9: Er komt dubbele logica naast WP-20:
- `sessionWindowText` hier en `formatWindowLocal` in WP-20 `time.ts`, met verschillende formaten ("zaterdag 18 juli, 14:00–18:00" tegenover "za 18 jul 14:00–18:00");
- `SESSION_SLUG_RE` tegenover `SESSION_SLUG_PATTERN`;
- `countCodePoints` tegenover `codePointLength`.

Dat is acceptabel voor parallelle bouw. Noteer het wel als opruimpunt na de merge van beide WP's (bij voorkeur één slugregex en één windowformatter).

N-10: Twee kleine opslagranden:
- A7 kan in een ander tabblad nog net een verse sleutel wissen. Laadt tabblad B terwijl tabblad A zich aanmeldt, dan komt het antwoord van B zonder de nieuwe RSVP, en de eerste controle van B wist de sleutel die A net schreef. Het venster is klein; documenteer het bij A7/A15 of accepteer het.
- Bij E26 (geen opslag) zet een `refreshAll()` bij hervatten `stored` via de `$effect` terug op `null`. Wijzigen en afmelden werken dus niet "zolang de pagina open is", maar tot de eerste hervatverversing. Pas de tekst aan, of laat de `$effect` een `stored` in het geheugen staan als de opslag niet beschikbaar is.

N-11: AC-2 ("geen auth-sessie opgevraagd"): de pagina en de modules raken `auth` niet aan, en de tests bewijzen dat. supabase-js zelf roept intern wel `auth.getSession()` aan om de bearer-header te bepalen, en de layout start `initAuth()`. Dat is bestaand gedrag en geen probleem. Noteer het in de verificatie, zodat niemand de trap-test als bewijs voor de echte client leest.

N-12: Bij `!stored && closed`, met alleen een notice of fout, wijst `aria-labelledby="rsvp-heading"` naar een kop die niet bestaat. Laat het attribuut in dat geval weg of geef een kop.

## Gecontroleerde bronnen
- https://raw.githubusercontent.com/supabase/supabase-js/master/packages/core/postgrest-js/src/PostgrestClient.ts: `rpc(fn, args = {}, { head = false, get = false, count } = {})`. Zonder opties gaan de argumenten met POST in de body (`body = args`). Alleen met `get`/`head` komen ze in `url.searchParams`. De claim in A6 klopt.
- https://raw.githubusercontent.com/supabase/supabase-js/master/packages/core/postgrest-js/src/PostgrestBuilder.ts: een niet-ok antwoord geeft `error = JSON.parse(body)` (anders `{ message: body }`) met `status = res.status`. Als de fetch faalt, resolvet de builder met `status: 0`, `data: null` en een `error` (`code` uit `fetchError.cause.code` of `''`). `shouldThrowOnError` staat standaard op `false`. De claim "status 0 bij een netwerkfout, geen reject" klopt.
- https://raw.githubusercontent.com/supabase/supabase-js/master/packages/core/postgrest-js/src/fetchWithRetry.ts: automatische retries gelden alleen voor GET, HEAD en OPTIONS (bij een netwerkfout of 503/520). POST-RPC's (`rsvp_create`) worden dus niet automatisch herhaald: geen extra dubbele RSVP door de client.
- https://svelte.dev/docs/svelte/$derived: een derived overschrijven kan sinds 5.25 en wordt bij een wijziging van de bron opnieuw berekend (A8).
- https://docs.postgrest.org/en/stable/references/errors.html: niet op te halen (HTTP 429). Voor `PT400` steun ik op WP-19 (A2, geverifieerd met PostgREST v14.18) en op de migratie.
- Lokaal gecontroleerd: `supabase/migrations/20261015200000_sessions.sql`, met parameternamen, antwoordsleutels, `PT400`-codes, regexen, `between 0 and 8`, `between 1 and 30`, `>= 30`, `interval '7 days'` en de carpoolregels A6. De contracttestregexen (1) tot en met (8) leveren op de huidige migratie de verwachte waarden. Verder gelezen: `web/src/lib/{supabase,data,time,view,page-data}.ts`, `Freshness.svelte`, `HourVerdict.svelte`, `Attribution.svelte`, `routes/spot/[id]/+page.svelte`, `routes/+layout.{ts,svelte}`, `app.html`, `vite.config.ts`, `package.json`, `test/{user-tables,no-local-date-getters,no-third-party}.test.ts`, `test/helpers/fake-supabase.ts`, `docs/RUNBOOK.md` §16, `docs/wp/WP-19/blueprint.md` (A1–A14) en `.claude/worktrees/WP-20/docs/wp/WP-20/blueprint.md` (bestanden, fixtures, tests).
