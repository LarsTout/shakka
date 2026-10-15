# Review WP-20, ronde 1
Oordeel: CHANGES_REQUIRED

## Blokkerend
B-1: WP-20 en WP-21 maken allebei dezelfde drie bestanden aan, met verschillende inhoud. Waar: Bestanden (`web/src/lib/session-page-data.ts`, `web/test/fixtures/session-data.ts`, `web/test/session-page-data.test.ts` in het Testplan), Risico's R1 en "Gevolgen voor latere WP's". De WP-21-blueprint (`.claude/worktrees/WP-21/docs/wp/WP-21/blueprint.md`, Bestanden r. 99, 107 en 112) maakt dezelfde paden aan:
- `session-page-data.ts` met `SessionPageData`/`loadSessionPage`, gebouwd op `rsvp.ts`;
- een eigen `fixtures/session-data.ts` (ook met een export `SLUG`, plus `NOW`, `SESSION_INFO` enz.);
- een eigen `session-page-data.test.ts` met RPC-mocks in plaats van `createFakeSupabase`.

Waarom: wie als tweede merget, krijgt add/add-conflicten op een `src/lib`-module en op een fixturebestand. Die oplossen vraagt ontwerpkeuzes: twee laadlagen samenvoegen (de ene leest tabellen via `user-data`, de andere RPC's via `rsvp`), twee mockstrategieën in één testbestand, en botsende fixturenamen. R1 zegt "inhoudelijk botst er niets" en noemt deze bestanden niet. Dat klopt dus niet, terwijl de parallelle bouw juist op die bewering leunt.

Voorstel: geef de WP-20-bestanden een naam die niet botst, bijvoorbeeld:
- `#lib/organizer-page-data.ts`;
- `test/fixtures/organizer-data.ts`;
- `test/organizer-page-data.test.ts`.

Werk de lagenschets, de tabel Bestanden, het Testplan, het Stappenplan (stap 2 en 5) en "Gevolgen" bij (WP-23 axe-fixtures). Pas R1 aan met de echte gedeelde bestanden: `user-tables.test.ts`, `RUNBOOK.md` en `app.css` (alleen WP-21).

## Niet-blokkerend
N-1: A10. De orchestrator noemt "minimaal 2 go-uren", maar de blueprint legt `GO_RUN_MIN_HOURS = 1` vast en vraagt Lars om een keuze. Ik adviseer 1. Dan heeft elk Go-blok op de spotpagina een knop, en is er geen Go-blok zonder knop (dat zou verwarrend zijn). De alertdefault `min_go_hours` is een persoonlijke drempel voor meldingen, geen drempel voor wat je zelf mag plannen. Kiest Lars 2, dan moet ook de spotpaginatest mee: die gebruikt nu één los `EVAL_GO`-uur ("Ik ga 14:00–15:00").

N-2: AC-6, procedure stap 6 ("Herhaal stap 2 uitgelogd") kan zo niet worden uitgevoerd. Uitloggen verwijdert het push-abonnement van dit apparaat (WP-18, RUNBOOK §14.14), dus er komt geen nieuwe melding om op te tikken. Beter:
- uitgelogd op "Ik ga" tikken op de spotpagina, of de `go_url` met de hand openen;
- na het inloggen meldingen opnieuw aanzetten (RUNBOOK §14.12).

N-3: Tijdtests.
- Voeg naast de gat-test van 29-03-2026 (al verleden) de eerstvolgende echte wissel toe: `localWallTimeCandidates('2027-03-28','02:30')` → `[]` en `('2027-03-28','03:00')` → `[01:00Z]`.
- `GO_URL_DST_*` komen niet uit `build_go_url` (`message_fixtures.py` heeft ze niet). Leg het formaat vast met een test als `goHref('test-strand', 2026-10-25T10Z, 14Z)` = `pathname + search` van `GO_URL_DST_DAY` (en idem voor `_NIGHT`). Dan is het formaat via de bewaakte `GO_URL_SUMMER` gekoppeld aan WP-08.

N-4: In M3 hebben crewleden geen account. "Ik ga" is voor uitgelogde gebruikers zichtbaar en eindigt dan bij een inlogmuur die voor hen niet werkt (A1, R7). Overweeg om de knop alleen te tonen als `$session` waar is: één `{#if $session}`, want `FavoriteStar` leest de sessie al. Een andere optie is een korte hint. Dit is een keuze voor Lars, geen fout.

N-5: `sessionErrorMessage`. Overweeg ook de JWT-fouten van PostgREST (`PGRST301`, `PGRST303`) op `signedOut` te mappen in plaats van `generic`. Een `42501` kan ook een kolomprivilege-bug zijn; dan klopt "Je bent niet meer ingelogd" niet, maar dat is acceptabel.

N-6: `go/+page.svelte`: `done` wordt niet teruggezet als SvelteKit de component hergebruikt voor een andere `/go`-URL. In de praktijk gebeurt dat niet (`WindowClient.navigate` laadt de pagina volledig). Wie het robuust wil: koppel `done` aan `data.returnPath`.

N-7: Spotpaginatest "een dag zonder go-uren heeft geen Ik ga-link". De bestaande `pageData()` heeft op beide dagen een go-uur (`EVAL_GO` en `EVAL_TOMORROW`). Geef de override expliciet op (bijv. `evaluations: [EVAL_GO, EVAL_OFFSHORE, EVAL_LOWCONF]` voor "morgen zonder link"), zodat de builder niet zelf hoeft te kiezen.

N-8: Na de merge van WP-20 en WP-21 bestaan sommige helpers dubbel:
- `browserStorage` (in `local-prefs.ts` en in `rsvp-storage.ts`);
- `SESSION_SLUG_PATTERN`/`isSessionSlug` en `SESSION_SLUG_RE`/`isValidSessionSlug`;
- `formatWindowLocal` en `sessionWindowText`.

Neem in "Gevolgen" op wie dit samenvoegt en wanneer (orchestrator na de merge, of WP-23).

N-9: De contractafwijkingen in A3 zijn acceptabel:
- `SessionRow` voorkomt een naamsbotsing met de supabase-js-`Session` in `auth.ts`;
- `listMySessions(userId, now)` maakt AC-5 te toetsen en voegt naast RLS een expliciet `organizer_id`-filter toe;
- `cancelSession(id, now?)` breekt geen aanroepen;
- `getMySession` is een aanvulling.

De orchestrator werkt `WORK_PACKAGES.md` bij.

N-10: Het datumveld heeft geen grenzen. Bij een datum ver in het verleden (vóór 1977 is Amsterdam niet UTC+1/+2) geeft `localWallTimeCandidates` `[]`, en dan verschijnt de misleidende melding `timeNonexistent`. Dat is onschuldig. Optioneel: `min`/`max` op de input, of een datumcontrole van bijvoorbeeld vandaag −1 tot +365 dagen.

Gecontroleerd en in orde (ter informatie):
- de `/go`-terugkeer is veilig tegen open redirects (`/go?`-prefix, `parseGoParams`, zelfde origin, `goto` alleen intern), en de sleutel wordt altijd verwijderd;
- de terugkeer werkt via een nieuw tabblad (gedeelde `localStorage`) en via een geplakte link in de iOS-beginschermapp (zelfde opslag als de `/go` uit de pushmelding);
- `wa.me/?text=` zonder andere parameters, `rel="noopener noreferrer"`, Web Share alleen met `text`;
- de insert zonder `organizer_id`, slug en `id` past bij de kolomgrants van de migratie;
- het slugformaat van de trigger (22 tekens base64url uit 16 bytes, zonder `=`) matcht `^[A-Za-z0-9_-]{10,64}$`;
- de drifttest-parser van `schema-columns.test.ts` geeft op de sessions-tabel precies `SESSION_COLUMNS` (plus `organizer_id` en `recent_rsvp_creates`);
- de DST-voorbeelden (E12, E13, de kandidaten op 25-10) en de weekdagen (za 18 jul, zo 25 okt, za 7 nov) kloppen;
- `user-data.ts` blijft de enige schrijfmodule;
- er wordt nergens een `sb_secret_` gebruikt.

## Gecontroleerde bronnen
- https://svelte.dev/docs/kit/$app-navigation (`goto(url, { replace })`; `replaceState` deprecated; `goto` weigert externe URL's)
- https://developer.mozilla.org/en-US/docs/Web/API/Navigator/share (alleen `text` is toegestaan; transient activation; `AbortError` en andere rejects)
- https://developer.mozilla.org/en-US/docs/Web/API/Clipboard/writeText (secure context, `NotAllowedError`)
- https://quadlayers.com/how-to-create-a-whatsapp-link-wa-me-with-a-pre-filled-message/ en de zoekresultaten over `https://wa.me/?text=urlencodedtext` (een vooraf ingevuld bericht zonder nummer opent de contactkeuze); faq.whatsapp.com laadde niet volledig
- https://supabase.com/docs/reference/javascript/insert (`.insert(...).select()`)
- docs.postgrest.org errors (v14): niet te laden (HTTP 429); de PT400-mapping is overgenomen uit de goedgekeurde WP-19-blueprint en de migratie
- Lokaal: `supabase/migrations/20261015200000_sessions.sql`, `docs/wp/WP-19/blueprint.md`, `docs/wp/WP-21/blueprint.md` (worktree WP-21), `web/src/lib/{time,go,data,user-data,auth,forms}.ts`, `web/src/routes/{+layout.svelte,go/*,login/+page.svelte,spot/[id]/+page.svelte}`, `web/test/{user-tables,schema-columns,go,go-url-fixture,layout}.test.ts`, `web/test/helpers/{fake-supabase,fake-session}.ts`, `web/test/fixtures/spot-data.ts`, `ingest/src/shakka/domain/messages.py`
