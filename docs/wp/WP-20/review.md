# Review WP-20, ronde 2
Oordeel: APPROVED

Beoordeeld: `docs/wp/WP-20/blueprint.md`, revisie 2, en de verwerking van review ronde 1. Naast WP-20 gelegd: `.claude/worktrees/WP-21/docs/wp/WP-21/blueprint.md` (revisie 2, alleen gelezen).

## Status van ronde 1
- **B-1 (bestandsnamen): opgelost.** WP-20 houdt `#lib/session-page-data.ts`, `test/session-page-data.test.ts` en `test/fixtures/session-data.ts`. WP-21 revisie 2 heeft deze bestanden echt hernoemd naar `public-session-data.ts`, `public-session-data.test.ts` en `fixtures/public-session.ts` (WP-21 A2, Bestanden, stappenplan r. 1114). Daar staat ook een expliciet verbod op de drie WP-20-namen. Beide blueprints zijn het eens over de volgorde: WP-20 merget eerst, WP-21 rebaset. R1 klopt nu. De overlap is echt beperkt tot `user-tables.test.ts` (andere test in hetzelfde bestand) en `RUNBOOK.md` (andere secties). `app.css` raakt alleen WP-21. De eindcontrole in stap 13 (`grep -E "routes/s/|rsvp|public-session|session-view"`) bewaakt dit.
- **N-1 t/m N-10: verwerkt.** Gecontroleerd:
  - `GO_RUN_MIN_HOURS = 1`, met het beslispunt voor Lars;
  - AC-6 stap 7 is uitvoerbaar;
  - de wissel naar zomertijd op 28-03-2027 klopt: de laatste zondag van maart 2027, met 02:30 → `[]` en 03:00 → 01:00Z;
  - `goHref` is gekoppeld aan `GO_URL_DST_*`;
  - A16 staat achter `{#if $session && runs.length}`;
  - `PGRST301`/`PGRST303` gaan naar `signedOut`; dat is nagekeken in de PostgREST-bron;
  - `handledFor` is gekoppeld aan `returnPath`;
  - N-7 heeft een expliciete override (`EVAL_DARK` bestaat in `spot-data.ts`);
  - de datumgrens `dateRange` werkt. `2026-07-15 + 365 = 2027-07-15` en `addDaysToKey`/`localDateKey` bestaan in `time.ts`;
  - `new-session-page.test.ts` zet de klok vast.

## Gecontroleerd en in orde
- **Terugkeer via `/go`:** blijft veilig.
  - `isAllowedReturnPath` eist het prefix `/go?` (dat sluit `//evil…` en absolute URL's uit), plus `parseGoParams` en dezelfde origin.
  - `takeReturnTo` verwijdert de sleutel altijd en gooit nooit. De TTL is 0..60 min.
  - `goto` navigeert alleen intern.
  - De loginpagina navigeert zelf niet weg (`login/+page.svelte` heeft geen `goto`), dus er is geen race met het layout-`$effect`.
  - Dat `/go` uitgelogd blijft werken, past bij A16.
- **Tikkie-regel (A18):** veilig.
  - Door het vaste prefix `https://tikkie.me/` volgt na de host direct `/`. Gebruikersnaam, poort, subdomein en lijkende domeinen zijn dus uitgesloten, en `\S+` sluit tab en regeleinde uit.
  - De controle van `new URL(...)` op hostname, gebruikersnaam en poort is redundant maar onschuldig.
  - De lengtegrenzen in E26 kloppen: 22 + 178 = 200 tekens.
  - Wat het WP-20-formulier doorlaat, is een deelverzameling van wat WP-21 `tikkieLink` toont: prefix, minstens één teken, URL parseert, hostname `tikkie.me`. Een sessie die via de app is gemaakt, toont zijn Tikkie dus altijd op `/s/{slug}`.
  - Het formulier blijft strenger dan de CHECK `^https://[^[:space:]]+$`, `char_length <= 200`.
- **R9/E50 (een bestaande niet-Tikkie-link blokkeert opslaan):** acceptabel.
  - Zo'n link kan alleen via SQL ontstaan (alleen Lars).
  - De melding zegt precies wat er moet gebeuren, en annuleren werkt los daarvan.
  - WP-21 toont zo'n link toch al niet (WP-21 A14).
  - Stil wissen of stil doorlaten zou slechter zijn.
- **Contract `/s/{slug}`:** gelijk in beide blueprints (regex `{10,64}`, geen query of fragment, `sessionPath`).
- **Importgraaf zonder cyclus:**
  - `local-prefs` importeert `session-form`, die `session-model` en `time` importeert;
  - `browser-storage` heeft geen imports;
  - `session-tables.test.ts` bewaakt dat deze modules puur blijven.

## Blokkerend
Geen.

## Niet-blokkerend
N-1: **De gedeelde helpers (A17) komen niet overeen met WP-21 revisie 2. Actie voor de orchestrator vóórdat WP-21 wordt goedgekeurd.** Waar: WP-20 A17 en "Gevolgen" (WP-21), tegenover WP-21 A20, "Consistentie" (r. 887) en stap 9 (r. 1152–1154).

Beide blueprints zijn tegelijk herzien, en elk nam de namen over die de ander in revisie 1 had. Daardoor kruisen ze nu.

| Helper | WP-20 rev 2 levert | WP-21 rev 2, stap 9, verwacht |
|---|---|---|
| slugregex | `SESSION_SLUG_RE`, `isValidSessionSlug` in `session-model.ts` | `SESSION_SLUG_PATTERN`, `isSessionSlug` in `session-model.ts` |
| code points | `countCodePoints` | `codePointLength` |
| opslag | `StorageLike`, `browserStorage(): StorageLike \| undefined` in `browser-storage.ts` | `KeyValueStorage`, `browserStorage(): … \| null` in `local-prefs.ts` |
| Tikkie | `safeTikkieLink(): { href, host } \| null` ("zelfde vorm als WP-21 `safeHttpsLink`") | `tikkieLink(): string \| null`; `safeHttpsLink` bestaat niet meer |

Waarom dit niet blokkeert voor WP-20:
- WP-20 is op zichzelf consistent en uitvoerbaar, en merget eerst.
- Stap 9 van WP-21 loopt op compileerfouten vast. Volgens WP-21 draait de builder dan per vervanging terug, en blijven de helpers dubbel (zoals bij N-8 van ronde 1). Er ontstaat geen fout in de werking.

Toch klopt de bewering van WP-20 niet: "zelfde naam en signature als WP-21". En de beweerde vermindering van dubbele code gebeurt zo niet.

Voorstel: pas WP-21 (revisie 3) aan, niet WP-20. Na de merge is de WP-20-code de bron. Stap 9 wordt dan:
- `session-view.ts` herexporteert `SESSION_SLUG_RE`, `isValidSessionSlug` en `countCodePoints` uit `#lib/session-model.js`;
- `rsvp-storage.ts` importeert `StorageLike` en `browserStorage` uit `#lib/browser-storage.js`. De parameters worden `StorageLike | undefined` (of `browserStorage() ?? null` op de aanroepplek);
- de "Consistentie"-alinea van WP-21 noemt de WP-20-namen van revisie 2.

Pas daarna ook de tekst van WP-20 A17 en "Gevolgen" aan: `null` → `undefined`, en de verwijzing naar `safeHttpsLink`. Dat raakt de WP-20-build niet.

N-2: `safeTikkieLink` heeft in WP-20 geen gebruiker, en WP-21 gebruikt zijn eigen `tikkieLink`, met een andere returnvorm. Eenvoudiger:
- laat `safeTikkieLink` in WP-20 weg (YAGNI) en houd alleen `isTikkieUrl`;
- of laat WP-21 `tikkieLink` bouwen als `isTikkieUrl(url) ? new URL(url).href : null`.

Dan bestaat de Tikkie-regel op één plek. Kies één van de twee bij de afstemming van N-1. De tests voor `safeTikkieLink` in `session-model.test.ts` vallen dan weg of verhuizen mee.

N-3: In `isValidOrganizerName` staan U+2028 en U+2029 als **letterlijke** tekens in de regex (r. 377, `…\u009f  ]`). Ze zien eruit als spaties. Plakt een builder die regel, dan is dat een syntaxfout, want een regexliteral mag geen regeleinde bevatten. Of hij typt twee spaties, en dan wordt "Jan Willem" geweigerd. Schrijf ze als `  `, en voeg een test toe dat `'Jan Willem'` geldig is.

N-4: Is er een verouderde `shakka:return_to` (R4) en opent de gebruiker ingelogd een andere `/go`-URL vanuit een melding? Dan kunnen het layout-`$effect` en het `/go`-`$effect` in dezelfde tick allebei `goto` aanroepen. In de praktijk is dat zeldzaam: de sleutel bestaat hoogstens één uur en wordt bij de eerste sessie al opgenomen. Beide doelen zijn bovendien een geldig `/sessie/nieuw`. Laat het zo, of laat de layout `takeReturnTo` overslaan als de pagina zelf `/go` is.

N-5: Een sessie die via SQL over middernacht loopt (RUNBOOK §16.9) kan in het bewerkformulier niet ongewijzigd worden opgeslagen. Dat komt door `sessionToForm` met één datum (A7) en `endBeforeStart`/`dateRange`. Het is vergelijkbaar met E50, en annuleren werkt wel. Eventueel kan het als extra regel bij E50/R9 worden genoemd.

## Gecontroleerde bronnen
- https://raw.githubusercontent.com/PostgREST/postgrest/main/docs/references/errors.rst
  - `PGRST301` en `PGRST303`: 401, JWT ongeldig of claims;
  - `PGRST302`: 401, anonieme rol uitgeschakeld;
  - `RAISE sqlstate 'PT400'`: HTTP 400, met code `PT400` en de eigen message.
- Uit ronde 1 en niet opnieuw nodig: https://svelte.dev/docs/kit/$app-navigation, https://developer.mozilla.org/en-US/docs/Web/API/Navigator/share, https://developer.mozilla.org/en-US/docs/Web/API/Clipboard/writeText, https://supabase.com/docs/reference/javascript/insert
- Lokaal:
  - `.claude/worktrees/WP-21/docs/wp/WP-21/blueprint.md` (revisie 2: A2, A14, A20, A21, `session-view.ts`, `rsvp-storage.ts`, Consistentie, stap 8–9, Verwerking review);
  - in de worktree van WP-20: `web/src/lib/time.ts` (`parseKey`, `addDaysToKey`, `localDateKey`, `localParts`, `parseGoParams`), `web/src/routes/login/+page.svelte`, `web/test/fixtures/spot-data.ts` (`EVAL_*`, `pageData`, `GO_URL_*`), `web/scripts/verify-build.mjs` (trackermarkers), `supabase/migrations/20261015200000_sessions.sql` (CHECKs voor `organizer_name`, `tikkie_url` en de slug).
