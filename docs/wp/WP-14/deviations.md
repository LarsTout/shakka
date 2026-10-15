# Afwijkingen WP-14

Alle afwijkingen zijn klein (geen contract, schema, externe API, dependency of acceptatiecriterium geraakt).

- **N-1 (review).** De spotpagina versmalt afgeleide waarden op `data.kind === 'ok'` (`groups`, `latest`, `station`); de `ok`-tak gebruikt `{@const spot = data.spot}`. De drie `<svelte:head>`-varianten zijn één `<svelte:head>` met een afgeleide `title`, omdat Svelte `<svelte:head>` in een `{#if}`-blok niet toestaat. Impact: geen.
- **N-2 (review).** `RESUME_REFRESH_MS` en `shouldRefreshOnResume` staan in `view.ts` (puur) en worden door `page-data.ts` her-geexporteerd. De pagina's importeren uit `#lib/view.js`. De paginatests mocken `#lib/supabase.js` zo dat een import een fout geeft; zo ziet een test direct als een pagina toch de client laadt.
- **N-3 (review).** `go.test.ts` importeert `../src/routes/go/+page.js` (niet `.ts`).
- **N-6 (review).** `schema-columns.test.ts` scant alle migraties en faalt op `alter table public.(spots|evaluations|tide_extremes) ... add|drop|rename column` met de melding "update types.ts and this test".
- **N-9 (review, dubbele tekst; in de review genummerd N-8).** `daySummaryText` geeft voor een dag met alleen no_go `geen go- of twijfeluren` in plaats van `niet gaan` (anders: "[Niet gaan] niet gaan"). De spot-list-test controleert dit. De tekstmatching in `spot-list.test.ts` gaat via `p.day-summary` en `toHaveTextContent(/.../)` (review N-9).
- **N-11 (review).** De slug-lengte van 100 in `/go` is een bewuste grens (`MAX_SLUG_LENGTH` in `time.ts`); `getSpot` heeft geen lengtegrens.
- **N-4 (review), handmatige rooktest voor Lars.** De redirect zelf blijft `redirect(307, ...)` in `+page.ts` (zoals de blueprint). Een `redirect()` in een load kan geen `replace` meegeven; daarom doet `go/+page.svelte` als vangnet `goto(goTarget(page.url), { replace: true })`. Rooktest voor Lars op de gedeployde site: open vanuit de app (client-side navigatie) een `/go?...`-link, druk op Terug en controleer dat je niet in een lus op `/go` blijft hangen. De directe paginalading (link uit WhatsApp) is lokaal met headless Chrome op `npm run preview` gecontroleerd: een geldige `/go` komt op `/spot/test-strand`, `/go?x=1` op `/`.
- **N-5/N-10 (review).** RUNBOOK §11.3 noemt de build watch paths `web/*` en `data/contracts/*` (N-10). `Hoogwater`/`Laagwater` in `labels.ts` wijken bewust af van `hoog`/`laag` in `messages.py` (N-5); alleen de getijvoorkeur is gelijk.
- **RUNBOOK.** De nieuwe sectie staat als punt 7 van §11 (niet als apart `§11.7`-kopje, want §11 is een genummerde lijst).
- **Tests.** `contracts.test.ts` draait in de node-omgeving (de `import.meta.url`-bestandsleesactie werkt niet in jsdom). Bij een directe controle van een lokaal draaiende `npm run dev` geeft `data/contracts` geen 403.
- **Fixtures.** Pariteits- en bronnentests zijn naast de rode-eerst-volgorde in een keer geschreven met de module; de tests zijn wel eerst geschreven, maar de rode run is niet apart gecommit.
- **AC-7 / Lars.** Open: Pages inrichten (§11.3), `APP_BASE_URL` zetten (§13.2), reactie op A2 en A7, en de N-4-rooktest hierboven.
