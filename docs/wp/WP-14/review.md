# Review WP-14, ronde 1
Oordeel: APPROVED

## Blokkerend
Geen.

## Niet-blokkerend
N-1: **Afgeleide waarden op de spotpagina zijn niet versmald.** Waar: "`/spot/[id]`", regel "Afgeleid: … `groups = groupByLocalDay(data.evaluations)`, … `station = data.spot.rws_station?.trim()`". Waarom: `data` is een unie (`ok | not_found | error`). Door de `OptionalUnion` van SvelteKit is `data.evaluations` hier `Evaluation[] | undefined`. Letterlijk overgenomen faalt `svelte-check` (AC-1). Leest de template de waarde buiten de `ok`-tak, dan crasht de pagina bovendien in de fouttoestand. Voorstel: schrijf het voor, bijvoorbeeld `groups = data.kind === 'ok' ? groupByLocalDay(data.evaluations) : []`, en hetzelfde voor `latest` en `station`. Of laat de `ok`-weergave over aan een kindcomponent met props `{ spot, evaluations, tides, now }`.

N-2: **Paginatests laden de echte Supabase-client.** Waar: Testplan (spot-page, spot-list) en de pagina's. Waarom: beide `+page.svelte`'s importeren `shouldRefreshOnResume` uit `#lib/page-data.js`. Die module importeert `#lib/data.js` en daarmee `#lib/supabase.js`, en zo wordt in jsdom een echte client aangemaakt (`autoRefreshToken`, `detectSessionInUrl`). Dat werkt waarschijnlijk, maar het is onnodig en kan timers of waarschuwingen achterlaten. Voorstel: zet `RESUME_REFRESH_MS` en `shouldRefreshOnResume` in `view.ts` (puur), of mock `#lib/supabase.js` ook in de paginatests.

N-3: **Import met `.ts`-extensie in `go.test.ts`.** Waar: Testplan, `go.test.ts` (`import { load } from '../src/routes/go/+page.ts'`). Waarom: de bestaande tests importeren met `.js` (bijv. `../src/lib/env-schema.js`). Een `.ts`-extensie vraagt `allowImportingTsExtensions`, en `npm run check` (dat `test/` meeneemt) kan dan TS5097 geven. Voorstel: `'../src/routes/go/+page.js'`.

N-4: **`/go` en de terugknop.** Waar: R2, stap 9. Waarom: een `redirect()` in een universele load bij de eerste client-side navigatie kan de doelpagina als nieuwe history-entry toevoegen. "Terug" komt dan weer op `/go` uit en wordt opnieuw doorgestuurd (een terugknop-val). De docs zeggen hier niets over. Voorstel: laat de builder in stap 9 ook de terugknop testen. Is er een lus, gebruik dan de fallback uit R2. `goto(…, { replace: true })` bestaat in kit 3 (gecontroleerd; `replaceState` is daar deprecated).

N-5: **A8 klopt niet helemaal.** Waar: A8, "waar Python al een label heeft (`TIDE_PREFERENCE_LABEL_NL`, `TIDE_KIND_LABEL_NL`) is de tekst gelijk, met een hoofdletter". Waarom: `TIDE_KIND_LABEL_NL` in `messages.py` is `hoog`/`laag`, terwijl de blueprint `Hoogwater`/`Laagwater` gebruikt. Alleen de getijvoorkeur is gelijk. Er is geen test die erop leunt. Voorstel: pas de zin aan, of noem `Hoogwater`/`Laagwater` als bewuste afwijking.

N-6: **Schemadrift na latere migraties (R7) is goedkoop af te vangen.** Waar: `schema-columns.test.ts`. Waarom: de test leest alleen de M1-migratie. Een `alter table public.evaluations add column …` in een latere migratie blijft dan onopgemerkt. Voorstel: laat dezelfde test alle bestanden in `supabase/migrations/` scannen en falen op `alter table (only )?public\.(spots|evaluations|tide_extremes)` met `add|drop|rename column`, met de melding "update types.ts and this test". De parser zelf is robuust genoeg: inspringing van precies twee spaties, `constraint`/`primary` uitgesloten en `);` als einde. Ik heb dat nagelopen op de huidige migratie.

N-7: **Grens van `fetchAllPages` is dubbelzinnig.** Waar: A9 en de docstring ("more than maxPages full pages"). Waarom: het is niet duidelijk of er na `maxPages` volle pagina's nog een request gaat (en pas een volle pagina `maxPages + 1` de fout geeft), of dat er meteen een fout volgt. Voorstel: leg één regel vast, bijvoorbeeld "na `maxPages` volle pagina's volgt `DataError(…, 'too_many_rows')` zonder verder request", en laat de test het aantal aanroepen controleren (3 bij `maxPages = 3`).

N-8: **Dubbele tekst in de lijst.** Waar: `/`, `daySummaryText` met alleen `no_go`. Waarom: dat geeft "Morgen: [Niet gaan] niet gaan". Voorstel: laat bij een badge de herhaling weg (bijv. "geen go- of twijfeluren"), of houd het zo als Lars dat goed vindt. Verder suggereert "2 uur go vanaf 14:00" aaneengesloten uren, terwijl de go-uren verspreid kunnen liggen. Dat is acceptabel, maar overweeg "2 uur go, eerste om 14:00".

N-9: **Tekstmatching in `spot-list.test.ts`.** Waar: Testplan. Waarom: `getByText('niet gaan')` of `getByText('2 uur go vanaf 14:00, 1 uur twijfel')` matcht exact op de eigen tekstnodes van de `<p>`. Daar staat ook "Morgen:" of "Vandaag:" in, dus de exacte match faalt. Voorstel: zoek de `<p class="day-summary">` binnen het item en gebruik `toHaveTextContent(/…/)`.

N-10: **Cloudflare build watch paths (A7).** Waar: RUNBOOK §11.3. Waarom: met de repo-root als root directory start elke push een Pages-build, ook een push die alleen `ingest/` raakt (gratis tier: 500 builds per maand). Voorstel: noem in §11.3 de optionele build watch paths `web/*` en `data/contracts/*`. A7 zelf vind ik de beste oplossing. Communitymeldingen bevestigen dat bestanden buiten de root directory niet beschikbaar zijn ("Could not resolve '../../shared/…'"), en de aanbevolen workaround is precies deze: root leeg en `cd <map> && …`. Een kopieerstap naar `web/` zou een tweede bron en een extra sync voor `dev`, `check` en `test` vragen. RUNBOOK §11.3 en de WP-13-regel in WORK_PACKAGES (regel 930, "root `web`") worden consistent zodra de orchestrator die regel bijwerkt, zoals de blueprint zegt. `docs/wp/WP-13/verification.md` noemt ook root `web`; dat is historisch en hoeft niet aangepast te worden.

N-11: **Lengtegrens van de slug.** Waar: A10 en `parseGoParams`. Waarom: `/go` weigert een `spot` langer dan 100 tekens, maar ingest (`SPOT_ID_PATTERN`) en `getSpot` hebben geen lengtegrens. In theorie stuurt een geldige alert-link dan naar `/`. Dat is in de praktijk irrelevant. Voorstel: laat het zo, of noem het in A10 als bewuste grens.

N-12: **Voorstellen voor Lars (A2, A3).** De labels "Go/Twijfel/Niet gaan" en de standaard verborgen donkere uren zijn verdedigbaar en strijdig met niets. Zie de orchestrator.

Gecontroleerd en in orde:
- **Harde regels.** `data.ts` leest alleen `spots`, `evaluations` en `tide_extremes`. Er wordt niets client-side bij Open-Meteo opgehaald, de guard blijft draaien, en de volledige `Attribution` staat op de spotpagina (vermeldt ook de bewerking, WP-13 N-10). Er is geen tracking, en `console.warn` bevat geen fouttekst. De richtingsklasse komt altijd uit `dir_class`, nooit uit `dir_deg` (E12, E13). Offshore wordt alleen getoond, niet herberekend.
- **RLS.** `20261015090100_m1_security.sql` geeft `grant select` aan `anon, authenticated` op `spots`, `tide_extremes` en `evaluations`, met policies `using (true)`.
- **Contracten.** `SPOT_COLUMNS` en `EVALUATION_COLUMNS` zijn gelijk aan de migratie, in dezelfde volgorde. `season`-sleutels komen overeen met `SpotProfile.to_row()`. `COMPASS_POINTS_NL` en de formule zijn gelijk aan `direction.py` (ook bij negatieve graden). `URL_SUMMER` en `URL_WINTER` zijn gelijk aan `message_fixtures.py`. De vorm van de contract-JSON (`_generated`, `items`, `effect`, `ridable`) klopt. De signatures van `data.ts`, `contracts.ts`, `time.ts` en `HourVerdict` volgen WORK_PACKAGES.
- **Tijd.** `startOfLocalDay` heb ik nagerekend voor 15-07, 29-03, 30-03, 25-10 en 26-10 (allemaal correct). De dag van 25 uur en de dubbele 02:00 (E5, E6) gaan goed, en er staan nergens lokale getters.
- **Pijl.** `rotate((deg + 180) % 360)` wijst correct de stroomrichting aan (250° → 70°).
- **Kleurcontrast.** Wit op `#1b7f3b` is ≈ 5,1:1, op `#8a5a00` ≈ 5,9:1 en op `#a4161a` ≈ 7,8:1.
- **Daglicht.** WP-05 voegt `dark` altijd toe bij nachturen (`evaluation.py`), dus "daglichturen = zonder `dark`" klopt.
- **Paginering.** Elke gepagineerde query heeft een unieke sortering (PK-volgorde), dus `.range()` is stabiel.

## Gecontroleerde bronnen
- https://svelte.dev/docs/kit/$app-navigation (`refreshAll(): Promise<void>`; `invalidateAll` deprecated; `GotoOptions.replace` bestaat, `replaceState` deprecated)
- https://svelte.dev/docs/kit/@sveltejs-kit (`redirect(status, location, options?)`, 307 toegestaan, `isRedirect`, `Redirect.status`/`.location`)
- https://svelte.dev/docs/kit/load (`PageProps` uit `./$types` met `let { data }: PageProps = $props()`; niets expliciet over `redirect` in de browser, dus R2 terecht)
- https://svelte.dev/docs/kit/$app-tsconfig (alleen `paths`, `types`, `isolatedModules` en `verbatimModuleSyntax` niet overschrijven)
- https://vite.dev/config/server-options (`server.fs.allow`: relatief tot de projectroot; automatische workspace-root vervalt; `searchForWorkspaceRoot`)
- https://supabase.com/docs/reference/javascript/not (operator en waarde as-is in PostgREST-syntax)
- https://supabase.com/docs/reference/javascript/range (0-gebaseerd, inclusief, volgt `order`)
- https://developers.cloudflare.com/pages/configuration/build-configuration/
- https://developers.cloudflare.com/pages/configuration/monorepos/
- https://community.cloudflare.com/t/cloudflare-pages-root-directory/329038 en https://community.cloudflare.com/t/issue-with-cloudflare-pages-deployment-for-monorepo-projects/801926 (bestanden buiten de root directory niet beschikbaar; workaround root leeg met `cd`)
- Lokaal: `supabase/migrations/20261015090000_m1_schema.sql`, `supabase/migrations/20261015090100_m1_security.sql`, `supabase/config.toml` (`max_rows = 1000`), `data/contracts/*.json`, `ingest/src/shakka/domain/direction.py`, `ingest/src/shakka/domain/evaluation.py`, `ingest/src/shakka/domain/spot.py`, `ingest/src/shakka/domain/messages.py`, `ingest/tests/message_fixtures.py`, `web/` (vite.config.ts, tsconfig.json, package.json, supabase.ts, layout, Attribution, sw/shell.ts, bestaande tests), `.github/workflows/ci.yml`, `docs/RUNBOOK.md` §11 en §13
