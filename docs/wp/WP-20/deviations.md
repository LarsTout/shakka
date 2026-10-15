# Afwijkingen WP-20

Geen afwijking raakt een contract, schema, externe API, dependency of acceptatiecriterium.

## Klein (genoteerd, doorgegaan)

- **N-2 (review ronde 2): `safeTikkieLink` weggelaten.** Wat: `session-model.ts` exporteert `TIKKIE_URL_RE` en `isTikkieUrl`, maar geen `safeTikkieLink`. Waarom: geen gebruiker in WP-20 (YAGNI), WP-21 bouwt zijn eigen `tikkieLink`. Impact: de Tikkie-regel staat op een plek; WP-21 kan `isTikkieUrl(url) ? new URL(url).href : null` gebruiken. De blueprint-tests voor `safeTikkieLink` zijn dus niet geschreven. De orchestrator past A17 en "Gevolgen" aan.
- **N-3 (review ronde 2): U+2028/U+2029 als escapes.** Wat: `NAME_FORBIDDEN` in `session-form.ts` is `/[\u0000-\u001f\u007f-\u009f  ]/` (alleen escapes, geen letterlijke tekens). Test `isValidOrganizerName('Jan Willem')` is geldig, plus aparte tests dat ` `, ` `, `\u0085` en tab geweigerd worden. Impact: geen.
- **N-4 (alleen genoteerd):** het layout-`$effect` en het `/go`-`$effect` kunnen bij een verouderde `shakka:return_to` in dezelfde tick allebei `goto` aanroepen. Zeldzaam (sleutel hoogstens een uur, wordt bij de eerste sessie al opgenomen) en beide doelen zijn een geldig `/sessie/nieuw`. Niet aangepast.
- **N-5 (alleen genoteerd):** een via SQL over middernacht lopende sessie kan in het bewerkformulier niet ongewijzigd worden opgeslagen (`sessionToForm` met een datum, A7). Vergelijkbaar met E50/R9; annuleren werkt wel.
- **Commit-indeling:** `go.ts`, `go/+page.ts` en de nieuwe `go.test.ts` zijn in de commit "session form parsing and prefill" terechtgekomen (stap 3) in plaats van stap 4, omdat `session-form.ts` het type `NewSessionParams` uit `go.ts` importeert. Impact: alleen de commit-indeling; de tijdelijke `onMount`-versie van `go/+page.svelte` (stap 4) is niet apart gecommit, de definitieve versie volgt in stap 7.
- **Extra tests:** `session-tables.test.ts` controleert imports met een regex op import/export-regels in plaats van `/supabase/i` op de hele tekst (commentaren noemen "Supabase"). Extra tests voor `SessionForm` (edit-modus) en `sessionErrorMessage` zoals in het testplan.
- **`browser-storage.test.ts` (c):** jsdom liet de getter die gooit toe; alle drie de gevallen uit het testplan zijn getest.
- **`web/.env`** (gitignored) is lokaal aangemaakt voor de build, met de publishable key en `PUBLIC_VAPID_PUBLIC_KEY`; nooit de secret key.

## AC-6 (telefoon): NEEDS_LARS
Procedure staat in het Testplan van de blueprint (stap 1 t/m 8); uitkomst per stap in `docs/wp/WP-20/verification.md`. Vooraf: migratie WP-19 in productie, `APP_BASE_URL` gezet, deze WP op de productie-URL, push aan op de telefoon. Niet in de browserstap `npm run preview` met Mailpit uitgevoerd (geen lokale Supabase-stack in deze sessie).
