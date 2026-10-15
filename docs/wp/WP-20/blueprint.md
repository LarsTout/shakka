# Blueprint WP-20: Sessie aanmaken en delen
Status: APPROVED
Revisie: 2

## Doel
De organisator (in M3 alleen Lars) maakt met een paar tikken een sessie aan en deelt die als link in WhatsApp:
1. `/go?spot&start&end` (de "ik ga"-link uit een pushmelding, WP-08/WP-17) gaat ingelogd door naar `/sessie/nieuw`, vooraf ingevuld in lokale tijd. Uitgelogd gaat hij eerst naar `/login`, en na het inloggen terug naar exact dezelfde `/go`-URL.
2. `/sessie/nieuw`: formulier met spot, datum, begin- en eindtijd (lokaal), voornaam (alleen lokaal onthouden), notitie, vrije plekken, vertrekpunt en optionele Tikkie-link (alleen `https://tikkie.me/…`, A18). De validatie is gelijk aan of strenger dan de CHECK-constraints van WP-19. Een weigering leidt niet tot een insert.
3. `/sessie/[slug]/delen`: de link `{origin}/s/{slug}`, een WhatsApp-knop (`https://wa.me/?text=…`, zonder trackingparameters), Web Share als de browser die heeft, en een kopieerknop.
4. Een knop "Ik ga" op de spotpagina bij elke reeks go-uren, die naar `/go` linkt. Alleen zichtbaar voor ingelogde gebruikers (A16).
5. `/mijn-sessies`: eigen komende sessies, met delen, bewerken en annuleren (`cancelled_at`).

Er verandert niets aan de backend: tabel, RLS, trigger en slug komen uit WP-19, de `go_url` uit WP-08. De publieke pagina `/s/{slug}` en RSVP bouwt WP-21; deze blueprint legt alleen het URL-contract vast.

## Aannames
Voorstellen waar Lars op kan reageren staan als **Voorstel**.

- **A1. In M3 organiseert alleen Lars** (bevestigde beslissing). Er komt geen code die dat afdwingt. Inloggen kan alleen met een bestaand account (`shouldCreateUser: false`, WP-13), en alleen Lars heeft er een. Elke ingelogde gebruiker mag een sessie maken; de database beperkt dat tot 10 per 24 uur (WP-19). Een crewlid zonder account ziet geen "Ik ga" (A16) en krijgt geen pushmeldingen, dus ook geen `go_url`. Opent iemand toch met de hand een `/go`-link, dan komt hij op `/login` en krijgt hij daar de bestaande melding "Met dit e-mailadres kun je nog niet inloggen…". Open aanmelden komt met eigen SMTP (WP-22).
- **A2. Terugkeren na inloggen via `localStorage`, niet via `redirect_to`.** `emailRedirectTo` blijft de origin (WP-13, getest in `auth.test.ts`). Een magic link opent vaak in een nieuw tabblad, en `sessionStorage` geldt maar per tabblad. In de beginschermapp op iOS logt Lars in met een geplakte link, die nooit op een `redirect_to`-pagina landt (WP-18, "Gevolgen"). Daarom slaat `/go` (uitgelogd) het pad op onder `shakka:return_to`, als `{"path": "/go?…", "saved_at": <ms>}`. Zodra de layout een sessie ziet, neemt hij die sleutel (lezen en altijd verwijderen) en navigeert hij met `replace` naar het pad, mits:
  - het hoogstens 60 minuten oud is (een inloglink verloopt na 1 uur, RUNBOOK §11.5);
  - het pad begint met `/go?` en `parseGoParams` het accepteert (geen open redirect).

  Dit werkt voor beide inlogroutes. De opgeslagen waarde bevat geen persoonsgegevens, alleen spot en tijden.
- **A3. Typenamen en signatures wijken iets af van het contract.** Het blijven aanvullingen; bestaande aanroepen breken niet:
  - Het rijtype heet `SessionRow`, niet `Session`. `Session` is al het sessietype van supabase-js (`#lib/auth.js`); twee betekenissen voor dezelfde naam in één codebase leidt tot fouten.
  - `listMySessions(userId: string, now: Date)` in plaats van `listMySessions()`. RLS beperkt al tot de eigen rijen, maar met een expliciete `.eq('organizer_id', userId)` is AC-5 ("vraagt alleen sessies op van de ingelogde gebruiker") te toetsen tegen de nep-client. Met `now` filtert hij op "komend" (`ends_at > now`) zonder klok in de module.
  - `cancelSession(id: string, now: Date = new Date())`: de extra parameter met default maakt de test deterministisch.
  - `shareText(session, spotName, url)` krijgt `session: Pick<NewSession, 'organizer_name' | 'starts_at' | 'ends_at'>`.

  De reviewer vond deze afwijkingen acceptabel (review N-9). De orchestrator werkt het contract in `WORK_PACKAGES.md` bij.
- **A4. Eén schrijfmodule blijft de regel (WP-16).** De Supabase-aanroepen op `sessions` staan in `#lib/user-data.ts` (`insertSession`, `listOwnSessions`, `getOwnSession`, `updateOwnSession`). `#lib/sessions.ts` is de contractmodule: daar staat de logica (één retry bij een slugbotsing, alleen bewerkbare velden, annuleren) en die roept `user-data.ts` aan. `user-tables.test.ts` blijft eisen dat `.from('` alleen in `data.ts` en `user-data.ts` staat.
- **A5. Sessietypes in een eigen module.** `SessionRow`, `NewSession`, de kolomlijsten en de limieten staan in `#lib/session-model.ts`, niet in `types.ts`. WP-21 wordt parallel gebouwd en voegt waarschijnlijk zijn eigen typen toe aan `types.ts`. Zo raken de twee WP's elkaar daar niet.
- **A6. Datum- en tijdvelden zijn native `type="date"` en `type="time"`.** Op telefoons geven die de beste kiezer. De waarden zijn altijd `YYYY-MM-DD` en `HH:MM`; de parser accepteert alleen die vormen. Het formulier heeft `novalidate`; alle validatie zit in de pure module `#lib/session-form.ts`, net als bij WP-16.
- **A7. Eén datum per sessie.** Begin en eind liggen op dezelfde lokale datum: dat is het formulier (datum, van, tot). Nachtelijke sessies over middernacht bestaan in de praktijk niet (donkere uren zijn altijd `no_go`). Een `/go`-window dat toch over lokale middernacht loopt, vult alleen datum en begintijd in en vraagt om een eindtijd (E14).
- **A8. Tijden rond de wisseling van zomer- naar wintertijd.**
  - Een wandkloktijd die niet bestaat (29-03, 02:00–02:59) wordt geweigerd.
  - Een tijd die twee keer bestaat (25-10, 02:00–02:59) wordt het eerste moment (zomertijd), behalve als het vooraf ingevulde moment uit `/go` een van de twee is: dan blijft dat moment staan.

  Zo levert een ongewijzigd vooraf ingevuld formulier exact het window uit de alert op.
- **A9. Een `/go`-window langer dan 16 uur wordt bij het invullen afgekapt** op `start + 16 h`, met een melding (WP-19, "Gevolgen"). Een sessie waarvan het eind al voorbij is (`ends_at <= now`), weigert het formulier. Een begintijd in het verleden mag wel ("ik sta al op het water"). De datum moet liggen tussen vandaag en vandaag + 365 dagen (lokale datum, `SESSION_MAX_DAYS_AHEAD = 365`). Zo krijgt een datum ver in het verleden (vóór 1977 kent Amsterdam geen UTC+1/+2) niet de misleidende melding `timeNonexistent` (review N-10). Een datum vóór vandaag kan nooit een geldige sessie opleveren (A7: begin en eind op één dag), dus deze grens weigert niets wat anders wel geldig was. De database controleert dit niet.
- **A10. "Ik ga" bij elke reeks van minstens 1 aaneengesloten go-uur** (`GO_RUN_MIN_HOURS = 1`), per lokale dag op de spotpagina. Zo heeft elk Go-blok een knop, en is er geen Go-blok zonder knop. De alertdefault `min_go_hours` is een persoonlijke drempel voor meldingen, geen drempel voor wat je zelf mag plannen. De reviewer adviseert 1 (review N-1), en de orchestrator houdt die waarde aan.
  **Beslispunt voor Lars:** liever alleen reeksen van minstens 2 uur, zoals de alertdefault? Dan wordt het `GO_RUN_MIN_HOURS = 2`, en moeten `go.test.ts` en de spotpaginatest mee: die gebruiken nu één los go-uur (`EVAL_GO`, "Ik ga 14:00–15:00") en hebben dan een fixture met twee aaneengesloten go-uren nodig.
- **A11. Delen deelt alleen tekst, met de URL erin.** `navigator.share({ text })`, met dezelfde tekst als de WhatsApp-knop. Doelapps gaan verschillend om met `text` plus `url` (de URL soms dubbel, soms weggelaten). Met alleen `text` komt de link er altijd precies één keer in. De kopieerknop kopieert alleen de URL.
- **A12. De voornaam wordt pas onthouden na een geslaagde sessie** (`shakka:organizer_name`, getrimd). Bij een volgende sessie staat hij vooraf ingevuld. Een ongeldige opgeslagen waarde wordt genegeerd.
- **A13. Geen RSVP-gegevens in deze WP.** `/mijn-sessies` toont geen aantal deelnemers: dat vraagt `get_public_session` (een `.rpc(`, terrein van WP-21). Elke sessie linkt naar zijn publieke pagina `/s/{slug}`, en daar staan de deelnemers.
- **A14. Bewerken en annuleren** kan alleen bij komende sessies (`ends_at > now`) die niet geannuleerd zijn. Een annulering terugdraaien zit niet in de scope; de kolomrechten zouden het toestaan. Deelnemers krijgen geen bericht bij een wijziging; het formulier zegt dat.
- **A15. Geen nieuwe npm-packages, geen migratie, geen wijziging aan `ingest/` of `supabase/`.**
- **A16. "Ik ga" alleen voor ingelogde gebruikers (beslissing orchestrator, review N-4).** In M3 hebben crewleden geen account. Een knop die uitgelogd eindigt bij een inlogmuur die voor hen niet werkt, helpt niemand. De spotpagina toont de "Ik ga"-links daarom alleen als `$session` een sessie is; bij `null` en `undefined` staat er niets (geen knop, geen hint). `/go` zelf blijft uitgelogd werken (A2): de link uit een pushmelding of een met de hand geopende `go_url`. WP-22/WP-24 heroverweegt dit bij open aanmelden.
- **A17. Gedeelde helpers krijgen de namen van WP-21 (beslissing orchestrator, review B-1 en N-8).** WP-20 merget eerst; WP-21 rebaset daarna en kan deze helpers dan importeren in plaats van eigen kopieën:
  - `SESSION_SLUG_RE` en `isValidSessionSlug(slug)` in `#lib/session-model.ts` (zelfde naam en regex als WP-21 `session-view.ts`);
  - `countCodePoints(s)` in `#lib/session-model.ts` (zelfde naam en gedrag als WP-21);
  - `StorageLike` en `browserStorage(): StorageLike | undefined` in een eigen module `#lib/browser-storage.ts` (zelfde signature als WP-21 `rsvp-storage.ts`);
  - `isTikkieUrl` en `safeTikkieLink` in `#lib/session-model.ts` (A18), met dezelfde returnvorm als WP-21 `safeHttpsLink` (`{ href, host } | null`).

  Functies in `local-prefs.ts` krijgen de opslag als eerste, verplichte parameter (`storage: StorageLike | undefined`), net als `readStoredRsvp(storage, slug)` in WP-21. Aanroepers geven `browserStorage()` mee.
- **A18. Tikkie-link: alleen `https://tikkie.me/…` (beslissing orchestrator, zelfde regel als WP-21).** Het formulier accepteert alleen een waarde die `^https://tikkie\.me/\S+$` matcht en waarvan `new URL(v)` precies host `tikkie.me` heeft (geen gebruikersnaam, wachtwoord of poort). Een echt Tikkie-betaalverzoek begint met `https://tikkie.me/pay/`. De CHECK in de database blijft ruimer (elke `https://`); het formulier is dus strenger, en wat het doorlaat accepteert de database altijd. WP-20 toont de Tikkie-link nergens als klikbare link (alleen als waarde in het bewerkformulier). Elke plek die hem wel als link toont (WP-21), gebruikt `safeTikkieLink` en `target="_blank" rel="noopener noreferrer"`.

## Ontwerp

**Lagen** (patroon van WP-14 en WP-16):
```
routes/go, routes/sessie/nieuw, routes/sessie/[slug]/delen, routes/mijn-sessies
   ──> #lib/session-page-data.ts ──> #lib/sessions.ts ──> #lib/user-data.ts ──> #lib/supabase.js
                                 ──> #lib/data.ts (listSpots, getSpot; bestaand)
components/SessionForm.svelte ──> #lib/session-form.ts
puur, zonder I/O: #lib/session-model.ts, #lib/session-form.ts, #lib/go.ts, #lib/time.ts
browseropslag (geïnjecteerd, te testen): #lib/local-prefs.ts ──> #lib/browser-storage.ts
```

**Bestandsnamen naast WP-21 (review B-1).** WP-20 merget als eerste en houdt de namen `#lib/session-page-data.ts`, `test/session-page-data.test.ts` en `test/fixtures/session-data.ts`. WP-21 hernoemt zijn eigen laadlaag, test en fixtures naar `public-session-data.ts`, `public-session-data.test.ts` en `fixtures/public-session.ts`, en rebaset na de merge van WP-20. WP-20 maakt niets aan onder `routes/s/` en geen bestanden met `rsvp` of `public-session` in de naam, en ook geen `session-view.ts`.

**`/go`.** De universele load valideert met de bestaande `parseGoParams` (WP-14). Ongeldig: `redirect(307, '/')`, zoals nu. Geldig: de load geeft twee paden terug, `returnPath` (`url.pathname + url.search`, dus byte voor byte de ontvangen URL) en `target` (`/sessie/nieuw?spot=…&start=…&end=…`, met dezelfde codering als `build_go_url`). De pagina wacht op `$session`:
- `undefined` → "Doorsturen…";
- `null` → `saveReturnTo(browserStorage(), returnPath, Date.now())` en `goto('/login', { replace: true })`;
- een sessie → `goto(target, { replace: true })`.

Met `replace` blijft `/go` niet in de geschiedenis staan, zodat Terug geen lus geeft (WP-14 N-4). De pagina onthoudt voor welke `returnPath` ze al heeft doorgestuurd. Een nieuwe sessiewaarde voor dezelfde URL doet dus niets, maar hergebruikt SvelteKit de component voor een andere `/go`-URL, dan stuurt ze opnieuw door (review N-6).

**Terugkeren.** `+layout.svelte` krijgt één `$effect`: zodra `$session` een sessie is, roept het `takeReturnTo(browserStorage(), Date.now())` aan, en bij een pad volgt `goto(pad, { replace: true })`. Een token-refresh (nieuw sessie-object) vindt geen sleutel meer en doet niets.

**Formulier.** `SessionForm.svelte` werkt voor aanmaken en bewerken. Het houdt alleen strings vast (`SessionFormValues`). Bij Opslaan zet `parseSessionForm` ze om naar een `NewSession` met UTC-tijden, of geeft het Nederlandse fouten per veld. Pas bij een geldige waarde roept het formulier `onsave(value)` aan. Die prop geeft `null` (gelukt) of een Nederlandse foutmelding terug. De pagina beslist wat er daarna gebeurt: na aanmaken naar `/sessie/{slug}/delen`, na bewerken blijft het formulier staan. Lokale tijd ↔ UTC gaat via `localWallTimeToUtc` in `time.ts`: die zoekt de UTC-momenten waarvan de klok in Amsterdam die datum en tijd aanwijst (0, 1 of 2 kandidaten, A8).

**Delen.** De share-pagina leest de eigen sessie via RLS (`getOwnSession(slug)`) en de spotnaam via `getSpot`. Ze bouwt:
- `url = sessionUrl(origin, slug)`, met `origin` uit de load (`url.origin`);
- `text = shareText(session, spotName, url)`;
- `whatsappUrl(text)`.

De WhatsApp-knop is een gewone link (`target="_blank"`, `rel="noopener noreferrer"`), dus er is geen script of SDK van derden. Web Share alleen als `navigator.share` een functie is. Kopiëren via `navigator.clipboard.writeText`.

**Mijn sessies.** `Promise.all([listMySessions(userId, now), listSpots()])`, en per sessie een kaart met de spotnaam, `formatWindowLocal`, "Geannuleerd" of de acties Delen, Bewerken (`<details>` met `SessionForm`) en Annuleren (in twee stappen, met bevestiging).

**Spotpagina.** Per daggroep berekent `goRuns(g.hours)` de aaneengesloten go-uren. Is `$session` een sessie (A16), dan komt er per reeks een link "Ik ga 14:00–18:00" naar `goHref(spot.id, start, end)`. De spotpagina leest `session` uit `#lib/auth.js`; dat module laadt de layout al, dus er komt geen extra client bij.

**Waarom zo.** Alle beslissende logica (tijdzones, validatie, URL's, deeltekst, terugkeren) zit in pure modules met tests vooraf. De pagina's zijn dunne lagen die reageren op `$session` (WP-16 A1: `undefined` = nog niet queryen). Schrijven blijft in één module, met een broncodetest. De drifttests houden de formuliergrenzen gelijk aan de migratie van WP-19.

## Bestanden

| Pad | Actie | Inhoud |
|---|---|---|
| `web/src/lib/session-model.ts` | aanmaken | Kolomlijsten, `NewSession`, `SessionRow`, `SessionUpdate`, limieten, `SESSION_SLUG_RE`, `isValidSessionSlug`, `sessionPath`, `sessionUrl`, `shareText`, `whatsappUrl`, `countCodePoints`, `TIKKIE_URL_RE`, `isTikkieUrl`, `safeTikkieLink`. Puur: importeert alleen `time.ts`. |
| `web/src/lib/session-form.ts` | aanmaken | `SessionFormValues`, `SESSION_FORM_MESSAGES`, `SESSION_MAX_DAYS_AHEAD`, `emptySessionForm`, `prefillSessionForm`, `withKnownSpot`, `sessionToForm`, `isValidOrganizerName`, `sessionDateBounds`, `parseSessionForm`. Puur. |
| `web/src/lib/sessions.ts` | aanmaken | Contract: `createSession`, `listMySessions`, `getMySession`, `cancelSession`, `updateSession`, `SESSION_ERROR_MESSAGES` en `sessionErrorMessage`; herexport van `shareText`, `whatsappUrl` en `sessionUrl`. |
| `web/src/lib/session-page-data.ts` | aanmaken | `loadNewSessionPage`, `loadSharePage`, `loadMySessionsPage` en de paginatypes. Naam blijft (afspraak B-1: WP-21 gebruikt `public-session-data.ts`). |
| `web/src/lib/browser-storage.ts` | aanmaken | `StorageLike` en `browserStorage()` (A17). |
| `web/src/lib/local-prefs.ts` | aanmaken | `ORGANIZER_NAME_KEY`, `RETURN_TO_KEY`, `RETURN_TO_TTL_MS`, `readOrganizerName`, `writeOrganizerName`, `isAllowedReturnPath`, `saveReturnTo`, `takeReturnTo`. |
| `web/src/lib/go.ts` | vervangen | `goTarget` vervalt (WP-14 "Gevolgen"). Nieuw: `GO_RUN_MIN_HOURS`, `GoRun`, `goRuns`, `isoHour`, `goHref`, `newSessionHref`, `NewSessionParams`, `parseNewSessionParams`. |
| `web/src/lib/time.ts` | wijzigen | Aan het eind: `isSpotSlug`, `localWallTimeCandidates`, `localWallTimeToUtc`, `formatWindowLocal`. Bestaande exports ongewijzigd. |
| `web/src/lib/user-data.ts` | wijzigen | `insertSession`, `listOwnSessions`, `getOwnSession`, `updateOwnSession`; de kopregel noemt `sessions`. |
| `web/src/lib/components/SessionForm.svelte` | aanmaken | Formulier voor aanmaken en bewerken. |
| `web/src/routes/go/+page.ts` | vervangen | Validatie, met `returnPath` en `target`. |
| `web/src/routes/go/+page.svelte` | vervangen | Wacht op `$session` en stuurt door. |
| `web/src/routes/sessie/nieuw/+page.ts` | aanmaken | `{ params: parseNewSessionParams(url) }`. |
| `web/src/routes/sessie/nieuw/+page.svelte` | aanmaken | Pagina "Sessie aanmaken". |
| `web/src/routes/sessie/[slug]/delen/+page.ts` | aanmaken | `{ slug: params.slug, origin: url.origin }`. |
| `web/src/routes/sessie/[slug]/delen/+page.svelte` | aanmaken | Pagina "Sessie delen". |
| `web/src/routes/mijn-sessies/+page.svelte` | aanmaken | Pagina "Mijn sessies" (geen `+page.ts`). |
| `web/src/routes/+layout.svelte` | wijzigen | Navigatielink "Mijn sessies" en het `$effect` voor terugkeren. |
| `web/src/routes/spot/[id]/+page.svelte` | wijzigen | "Ik ga"-links per reeks go-uren, alleen ingelogd (A16). |
| `web/test/helpers/fake-supabase.ts` | wijzigen | `'gt'` in de lijst met methodes (na `'gte'`). Verder niets. |
| `web/test/fixtures/session-data.ts` | aanmaken | Sessiefixtures en `/go`-fixtures voor de wisseling naar wintertijd (zie Testplan). Naam blijft (afspraak B-1: WP-21 gebruikt `fixtures/public-session.ts`). |
| `web/test/go.test.ts` | vervangen | Zie Testplan. |
| `web/test/*.test.ts` | aanmaken/wijzigen | Zie Testplan. |
| `docs/RUNBOOK.md` | wijzigen | §11 punt 7 (`/go`) en een nieuw punt 10 (zie Interfaces). |

Er komt niets onder `web/src/routes/s/` (WP-21), en geen bestand met `rsvp`, `public-session` of `session-view` in de naam. Ook geen wijzigingen in `types.ts`, `app.css`, `data.ts`, `auth.ts`, `supabase/`, `ingest/`, `package.json`, de service worker of `.github/`. Stijlen staan in `<style>`-blokken van de nieuwe componenten en pagina's, en die gebruiken de bestaande klassen (`.form-field`, `.hint`, `.error`, `.banner`, `.notice`, `.muted`, `.prewrap`). `docs/STATUS.md` en `WORK_PACKAGES.md` werkt de orchestrator bij.

## Interfaces en contracten

Imports gaan via `#lib/<bestand>.js`. Teksten voor de gebruiker zijn Nederlands; code, identifiers en `Error`-meldingen Engels. Nergens `{@html}`. Nergens lokale `Date`-getters (`getHours`, `toLocaleString`, …; `no-local-date-getters.test.ts`). Nergens de strings `cdn.` of trackernamen (`no-third-party.test.ts`).

### URL-contract `/s/{slug}` (gedeeld met WP-21)
- **Pad:** `/s/` + slug. De slug matcht `^[A-Za-z0-9_-]{10,64}$` (de CHECK `sessions_slug_format`); in de praktijk zijn het 22 tekens base64url, server-side gemaakt door de trigger van WP-19.
- **Absolute vorm:** `{origin}/s/{slug}`. `origin` is `url.origin` van de app die de link maakt (productie `https://<project>.pages.dev`), zonder slash aan het eind.
- **Verder niets:**
  - geen query, geen fragment, geen slash aan het eind en geen trackingparameters;
  - de slug wordt niet gecodeerd (alle tekens zijn al URL-veilig);
  - de edit-token van een RSVP komt nooit in deze URL (RUNBOOK §16.7).
- **Wie bouwt wat.** WP-21 bouwt de route `web/src/routes/s/[slug]/`. WP-20 maakt de link (`sessionPath`, `sessionUrl`) en linkt ernaartoe vanaf de deelpagina en `/mijn-sessies`. Tot WP-21 gemerged is, geeft `/s/…` de standaardfoutpagina van de SPA; dat is geaccepteerd.
- **Relatieve vorm:** `sessionPath(slug)` = `'/s/' + slug`.

### `/go`-contract (ongewijzigd formaat, nieuw gedrag)
- Invoer: `build_go_url` van WP-08, bijvoorbeeld `/go?spot=test-strand&start=2026-07-18T12%3A00%3A00Z&end=2026-07-18T16%3A00%3A00Z`. Gevalideerd met `parseGoParams` (WP-14 A10).
- Ongeldig → `redirect(307, '/')`.
- Geldig, ingelogd → `/sessie/nieuw?spot=<spot>&start=<iso>&end=<iso>` (`replace`), in hetzelfde formaat (dezelfde codering: `:` → `%3A`).
- Geldig, uitgelogd → `shakka:return_to` = `{"path": url.pathname + url.search, "saved_at": Date.now()}`, dan `/login` (`replace`). Na het inloggen stuurt de layout terug naar `path`.

### `web/src/lib/session-model.ts`
```ts
// Pure: imports only ./time.js (no data.js, no supabase), so session-form.ts and local-prefs.ts stay pure too.
import { formatWindowLocal } from './time.js';

/** Columns of public.sessions that the app selects: all except organizer_id and recent_rsvp_creates. */
export const SESSION_COLUMNS = [
	'id', 'slug', 'spot_id', 'organizer_name', 'starts_at', 'ends_at', 'note', 'seats_free',
	'departure_point', 'tikkie_url', 'cancelled_at', 'created_at', 'updated_at'
] as const;
/** Columns the organizer sets on insert and may update (column grants, WP-19; without organizer_id and cancelled_at). */
export const SESSION_EDITABLE_COLUMNS = [
	'spot_id', 'organizer_name', 'starts_at', 'ends_at', 'note', 'seats_free', 'departure_point', 'tikkie_url'
] as const;
export type SessionEditableColumn = (typeof SESSION_EDITABLE_COLUMNS)[number];

export interface NewSession {
	spot_id: string;
	organizer_name: string;   // trimmed, 1–30 code points, no control characters
	starts_at: string;        // ISO 8601 UTC (Date.toISOString())
	ends_at: string;
	note: string | null;
	seats_free: number | null;
	departure_point: string | null;
	tikkie_url: string | null;
}
export interface SessionRow extends NewSession {
	id: string;
	slug: string;
	cancelled_at: string | null;
	created_at: string;
	updated_at: string;       // also changes on a new RSVP (WP-19 A4): never "last edited"
}
/** Payload of updateOwnSession: editable columns plus cancelled_at. */
export type SessionUpdate = Partial<NewSession> & { cancelled_at?: string };

export const ORGANIZER_NAME_MAX = 30;      // sessions_organizer_name_valid
export const NOTE_MAX = 280;               // sessions_note_length
export const DEPARTURE_POINT_MAX = 80;     // sessions_departure_point_length
export const TIKKIE_URL_MAX = 200;         // sessions_tikkie_url_https
export const SEATS_FREE_RANGE = [0, 8] as const; // sessions_seats_free_range
export const SESSION_MAX_HOURS = 16;       // sessions_window_max_16h

/** Same name and regex as WP-21 session-view.ts (A17); equals CHECK sessions_slug_format. */
export const SESSION_SLUG_RE = /^[A-Za-z0-9_-]{10,64}$/;
/** SESSION_SLUG_RE.test(slug). */
export function isValidSessionSlug(slug: string): boolean;
/** '/s/' + slug. RangeError('invalid session slug') when !isValidSessionSlug(slug). */
export function sessionPath(slug: string): string;
/** origin with trailing '/' removed + sessionPath(slug). */
export function sessionUrl(origin: string, slug: string): string;
/** [...s].length: code points, as Postgres char_length counts them (WP-19 A8). Same name as WP-21 (A17). */
export function countCodePoints(s: string): number;

/** A18: only Tikkie payment links. Case-sensitive, like the https:// CHECK. */
export const TIKKIE_URL_RE = /^https:\/\/tikkie\.me\/\S+$/;
/** TIKKIE_URL_RE.test(s) && countCodePoints(s) <= TIKKIE_URL_MAX && new URL(s) succeeds with
 *  protocol 'https:', hostname 'tikkie.me', username '', password '' and port ''. Never throws. */
export function isTikkieUrl(s: string): boolean;
/** isTikkieUrl(url) -> { href: new URL(url).href, host: 'tikkie.me' }; null, '' or anything else -> null.
 *  Same return shape as WP-21 safeHttpsLink. Render as <a target="_blank" rel="noopener noreferrer">. */
export function safeTikkieLink(url: string | null): { href: string; host: string } | null;

/** Exactly four lines joined with '\n':
 *  `${organizer_name} gaat kiten bij ${spotName}.`
 *  formatWindowLocal(new Date(starts_at), new Date(ends_at))
 *  'Ga je mee? Meld je aan via de link, een account is niet nodig:'
 *  url */
export function shareText(
	session: Pick<NewSession, 'organizer_name' | 'starts_at' | 'ends_at'>,
	spotName: string,
	url: string
): string;
/** 'https://wa.me/?text=' + encodeURIComponent(text). No other parameters. */
export function whatsappUrl(text: string): string;
```
Voorbeeld (AC-3, golden): `shareText({ organizer_name: 'Lars', starts_at: '2026-07-18T12:00:00.000Z', ends_at: '2026-07-18T16:00:00.000Z' }, 'Teststrand', 'https://example.org/s/Q2x0aHJ1c3RtZTEyMzQ1Ng')` geeft:
```
Lars gaat kiten bij Teststrand.
za 18 jul 14:00–18:00
Ga je mee? Meld je aan via de link, een account is niet nodig:
https://example.org/s/Q2x0aHJ1c3RtZTEyMzQ1Ng
```
(`–` is U+2013, zoals `format_window_local` in WP-08.)

### Foutmeldingen (in `web/src/lib/sessions.ts`, omdat ze `DataError` uit `data.ts` nodig hebben)
```ts
export const SESSION_ERROR_MESSAGES = {
	rateLimited: 'Je hebt in de afgelopen 24 uur al 10 sessies aangemaakt. Probeer het later opnieuw.',
	spotGone: 'Deze spot bestaat niet meer. Kies een andere spot.',
	invalid: 'De sessie kon niet worden opgeslagen: een van de velden is ongeldig.',
	signedOut: 'Je bent niet meer ingelogd. Log opnieuw in en probeer het nog eens.',
	notFound: 'Deze sessie bestaat niet meer.',
	generic: 'Opslaan is niet gelukt. Controleer je verbinding en probeer het opnieuw.',
	cancelFailed: 'Annuleren is niet gelukt. Probeer het opnieuw.'
} as const;
/** DataError code -> message: 'rate_limited' -> rateLimited; '23503' -> spotGone;
 *  '23514' | '23502' | '22001' -> invalid; '42501' | 'PGRST301' | 'PGRST303' -> signedOut;
 *  'not_found' -> notFound; anything else (other codes, null, non-DataError) -> generic.
 *  Never the Supabase message. */
export function sessionErrorMessage(e: unknown): string;
```
`PGRST301` ("Provided JWT couldn't be decoded or it is invalid") en `PGRST303` ("JWT claims validation or parsing failed") zijn de JWT-fouten van PostgREST, met HTTP 401 (review N-5). Een `42501` kan in theorie ook een bug in de kolomrechten zijn; dan klopt "niet meer ingelogd" niet, maar dat is geaccepteerd.

### `web/src/lib/time.ts` (toevoegingen aan het eind)
```ts
/** SLUG.test(s) && s.length <= MAX_SLUG_LENGTH (the spot-id rule parseGoParams uses). */
export function isSpotSlug(s: string): boolean;
/** UTC instants whose Europe/Amsterdam wall clock reads `dateKey` + `time` ('HH:MM', 00:00–23:59).
 *  Ascending; [] in the spring-forward gap, 2 items in the autumn overlap.
 *  RangeError on a malformed key or time. */
export function localWallTimeCandidates(dateKey: string, time: string): Date[];
/** preferred (same getTime()) if it is a candidate; else the earliest candidate; else null.
 *  RangeError like localWallTimeCandidates. */
export function localWallTimeToUtc(dateKey: string, time: string, preferred?: Date | null): Date | null;
/** Mirror of WP-08 format_window_local: same local date of (end - 1 ms) as start ->
 *  'za 18 jul 14:00–18:00'; otherwise 'za 18 jul 22:00 – zo 19 jul 02:00'.
 *  RangeError when start >= end. */
export function formatWindowLocal(start: Date, end: Date): string;
```
Implementatie van `localWallTimeCandidates`:
- datum via de bestaande `parseKey`;
- tijd via `/^([01]\d|2[0-3]):([0-5]\d)$/`, anders `RangeError('malformed time')`;
- `naive = Date.UTC(y, m - 1, d, hh, mm)`, dan voor `off` in `[2, 1]` (uren; Amsterdam is altijd UTC+1 of UTC+2): `t = naive - off * 3_600_000`. `t` is een kandidaat als `localParts(new Date(t))` precies `y, m, d, hh, mm` geeft.

### `web/src/lib/go.ts` (vervangt het bestand)
```ts
import type { Evaluation } from './types.js';
import { isSpotSlug, parseGoParams, type GoParams } from './time.js';

export const GO_RUN_MIN_HOURS = 1;   // A10
export interface GoRun { start: Date; end: Date }   // [start, end), end = last go hour + 1 h
/** Sorted by valid_at; consecutive 'go' hours exactly 3_600_000 ms apart form one run.
 *  Runs shorter than GO_RUN_MIN_HOURS are dropped. Non-go hours (also 'dark') break a run. */
export function goRuns(hours: readonly Evaluation[]): GoRun[];
/** 'YYYY-MM-DDTHH:MM:SSZ' (toISOString without milliseconds), as WP-08 iso(). */
export function isoHour(d: Date): string;
/** `/go?spot=${enc(spot)}&start=${enc(isoHour(start))}&end=${enc(isoHour(end))}`, enc = encodeURIComponent
 *  (':' -> '%3A', equal to WP-08 build_go_url without the base). */
export function goHref(spotId: string, start: Date, end: Date): string;
/** Same query on /sessie/nieuw. */
export function newSessionHref(p: GoParams): string;

export interface NewSessionParams { spot: string | null; start: string | null; end: string | null } // ISO strings
/** parseGoParams(url) ok -> { spot, start: start.toISOString(), end: end.toISOString() };
 *  else a valid spot param (isSpotSlug) -> { spot, start: null, end: null }; else all null. */
export function parseNewSessionParams(url: URL): NewSessionParams;
```

### `web/src/lib/browser-storage.ts` (exact)
```ts
// Shared with WP-21 (A17): same names and signature as its rsvp-storage.ts, so it can import these after rebasing.
export type StorageLike = Pick<Storage, 'getItem' | 'setItem' | 'removeItem'>;

/** globalThis.localStorage, or undefined when unavailable (access can throw a SecurityError). */
export function browserStorage(): StorageLike | undefined {
	try {
		return globalThis.localStorage ?? undefined;
	} catch {
		return undefined;
	}
}
```

### `web/src/lib/local-prefs.ts`
```ts
import type { StorageLike } from './browser-storage.js';
import { parseGoParams } from './time.js';
import { isValidOrganizerName } from './session-form.js';

export const ORGANIZER_NAME_KEY = 'shakka:organizer_name';
export const RETURN_TO_KEY = 'shakka:return_to';
export const RETURN_TO_TTL_MS = 60 * 60 * 1000;

/** Stored name if isValidOrganizerName(name), else ''. '' when storage is undefined. Never throws. */
export function readOrganizerName(storage: StorageLike | undefined): string;
/** Stores name.trim() when valid; ignores invalid names, undefined storage and storage errors. */
export function writeOrganizerName(storage: StorageLike | undefined, name: string): void;

/** path starts with '/go?' and parseGoParams(new URL(path, 'https://shakka.invalid')) !== null
 *  and new URL(path, base).origin === base origin. */
export function isAllowedReturnPath(path: string): boolean;
/** Writes JSON {"path", "saved_at": nowMs} when isAllowedReturnPath(path).
 *  false on refusal, undefined storage or storage error. */
export function saveReturnTo(storage: StorageLike | undefined, path: string, nowMs: number): boolean;
/** Reads and ALWAYS removes the key. Returns path when the JSON is {path: string, saved_at: number},
 *  0 <= nowMs - saved_at <= RETURN_TO_TTL_MS and isAllowedReturnPath(path); else null.
 *  null when storage is undefined. Never throws. */
export function takeReturnTo(storage: StorageLike | undefined, nowMs: number): string | null;
```
De opslag is de eerste, verplichte parameter (A17); aanroepers geven `browserStorage()` mee. Alle toegang staat in `try/catch`: bij Safari met geblokkeerde opslag gaat het dan zonder terugkeer of zonder onthouden naam verder.

### `web/src/lib/session-form.ts`
```ts
import type { FieldErrors, FormResult } from './forms.js';
import type { NewSession, SessionRow } from './session-model.js';
import type { Spot } from './types.js';
import type { NewSessionParams } from './go.js';

export interface SessionFormValues {
	spot_id: string; date: string; start_time: string; end_time: string; organizer_name: string;
	note: string; seats_free: string; departure_point: string; tikkie_url: string;
}
export type SessionFormField = keyof SessionFormValues;
export interface PreferredWindow { start: Date; end: Date }
export interface SessionFormContext { now: Date; spotIds: ReadonlySet<string>; preferred: PreferredWindow | null }

export const SESSION_FORM_MESSAGES = {
	spot: 'Kies een spot uit de lijst.',
	date: 'Kies een geldige datum.',
	dateRange: 'Kies een datum van vandaag tot hoogstens een jaar vooruit.',
	time: 'Kies een tijd.',
	timeNonexistent: 'Deze tijd bestaat niet op deze dag (de klok gaat een uur vooruit). Kies een andere tijd.',
	endBeforeStart: 'De eindtijd moet na de begintijd liggen.',
	tooLong: `Een sessie duurt hoogstens ${SESSION_MAX_HOURS} uur.`,
	inPast: 'Deze sessie is dan al voorbij. Kies een latere eindtijd.',
	organizerName: `Vul je voornaam in: 1 tot ${ORGANIZER_NAME_MAX} tekens, zonder regeleinden.`,
	note: `De notitie is te lang (hoogstens ${NOTE_MAX} tekens).`,
	seatsFree: `Vul een heel getal van ${SEATS_FREE_RANGE[0]} tot ${SEATS_FREE_RANGE[1]} in, of laat het veld leeg.`,
	departurePoint: `Het vertrekpunt is te lang (hoogstens ${DEPARTURE_POINT_MAX} tekens).`,
	tikkieUrl: `Plak een Tikkie-link: die begint met https://tikkie.me/, bevat geen spaties en is hoogstens ${TIKKIE_URL_MAX} tekens.`,
	summary: 'Niet opgeslagen: controleer de gemarkeerde velden.'
} as const;
export const PREFILL_NOTICES = {
	truncated: `De eindtijd is ingekort: een sessie duurt hoogstens ${SESSION_MAX_HOURS} uur.`,
	otherDay: 'Het tijdvenster loopt door na middernacht. Kies een eindtijd op dezelfde dag.',
	past: 'Dit tijdvenster is al voorbij. Kies een nieuwe tijd.',
	spotUnknown: 'De spot uit de link bestaat niet (meer). Kies een spot.'
} as const;

/** trimmed; 1..ORGANIZER_NAME_MAX code points; no /[\u0000-\u001f\u007f-\u009f  ]/. */
export function isValidOrganizerName(name: string): boolean;
/** A9: last allowed date = local today + this many days. */
export const SESSION_MAX_DAYS_AHEAD = 365;
/** { min: localDateKey(now), max: addDaysToKey(localDateKey(now), SESSION_MAX_DAYS_AHEAD) }. */
export function sessionDateBounds(now: Date): { min: string; max: string };
/** All fields '' except organizer_name; date = localDateKey(now). */
export function emptySessionForm(organizerName: string, now: Date): SessionFormValues;
export interface Prefill { form: SessionFormValues; preferred: PreferredWindow | null; notices: string[] }
export function prefillSessionForm(params: NewSessionParams, organizerName: string, now: Date): Prefill;
/** Clears form.spot_id (and adds PREFILL_NOTICES.spotUnknown) when it is non-empty and not in spots. */
export function withKnownSpot(p: Prefill, spots: readonly Pick<Spot, 'id'>[]): Prefill;
/** Edit mode: date/start/end in local time, numbers as String(n), null -> ''. preferred = the stored instants. */
export function sessionToForm(s: SessionRow): Prefill;
export function parseSessionForm(f: SessionFormValues, ctx: SessionFormContext): FormResult<NewSession, SessionFormField>;
```
De constanten (`SESSION_MAX_HOURS` enz.), `countCodePoints` en `isTikkieUrl` komen uit `session-model.ts` (waarde-import); `localDateKey`, `addDaysToKey`, `formatLocal` en `localWallTimeToUtc` uit `time.ts`.

**`prefillSessionForm(params, name, now)`:**
1. `form = emptySessionForm(name, now)`, `notices = []`, `preferred = null`.
2. Als `params.spot !== null`, dan `form.spot_id = params.spot`.
3. Zijn `start` en `end` niet `null`:
   - `s = new Date(start)` en `e = new Date(end)`;
   - is `e - s > 16 h`, dan `e = s + 16 h` en `notices.push(truncated)`;
   - `form.date = localDateKey(s)` en `form.start_time = formatLocal(s, 'time')`;
   - is `localDateKey(e) === form.date`, dan `form.end_time = formatLocal(e, 'time')`; anders blijft `end_time` `''` en `notices.push(otherDay)` (ook bij een eind precies om middernacht);
   - `preferred = { start: s, end: e }`;
   - is `e <= now`, dan `notices.push(past)`.

**`parseSessionForm(f, ctx)`.** Alle velden worden gecontroleerd (alle fouten tegelijk). Waarden worden pas gebruikt nadat ze geldig zijn:
1. `spot_id`: niet leeg en in `ctx.spotIds`, anders `spot`.
2. `date`: `addDaysToKey(f.date, 0)` gooit niet (vorm en bestaande datum), anders `date`. Daarna moet `min <= f.date <= max` gelden (stringvergelijking van `YYYY-MM-DD`, met `sessionDateBounds(ctx.now)`), anders `dateRange`. Alleen bij geen van beide fouten is de datum geldig.
3. `start_time` en `end_time`: moeten elk `/^([01]\d|2[0-3]):[0-5]\d$/` matchen, anders `time`. Bij een geldige datum: `localWallTimeToUtc(f.date, t, ctx.preferred?.start resp. .end ?? null)`; geeft die `null`, dan `timeNonexistent` op dat veld.
4. Zijn beide momenten `s` en `e` bekend, dan alleen de eerste die geldt, op `end_time`: `e <= s` → `endBeforeStart`; `e - s > 16 h` → `tooLong`; `e <= ctx.now` → `inPast`.
5. `organizer_name`: `isValidOrganizerName(f.organizer_name)`, anders `organizerName`. De waarde is `trim()`.
6. `note`: `trim()`; leeg wordt `null`; meer dan `NOTE_MAX` code points → `note`.
7. `seats_free`: `trim()`; leeg wordt `null`; moet `/^\d{1,2}$/` matchen en binnen 0–8 liggen, anders `seatsFree`.
8. `departure_point`: `trim()`; leeg wordt `null`; meer dan `DEPARTURE_POINT_MAX` code points → `departurePoint`.
9. `tikkie_url`: `trim()`; leeg wordt `null`. Een gevulde waarde moet `isTikkieUrl(v)` zijn (A18), anders `tikkieUrl`. Dat omvat alle eisen van de CHECK (`^https://`, geen witruimte, hoogstens 200 tekens) plus host `tikkie.me`. Opgeslagen wordt de getrimde invoer zelf, niet `new URL(v).href`.
10. Geen fouten → `{ ok: true, value }`, met `starts_at = s.toISOString()` en `ends_at = e.toISOString()`. `value` heeft precies de 8 sleutels van `NewSession`.

De controles zijn gelijk aan of strenger dan de CHECKs (bijv. `\s` in JS ⊇ `[[:space:]]`, extra controletekens). Wat het formulier doorlaat, accepteert de database dus altijd.

### `web/src/lib/user-data.ts` (toevoegingen)
```ts
import { SESSION_COLUMNS, type NewSession, type SessionRow, type SessionUpdate } from './session-model.js';

/** Inserts exactly the eight organizer columns. organizer_id comes from the column default auth.uid(),
 *  slug from the trigger (WP-19). PT400 'rate_limited' -> DataError('insertSession', 'rate_limited'). */
export async function insertSession(values: NewSession): Promise<{ slug: string }>;
/** Own sessions with ends_at > now, by starts_at then id (RLS limits to the organizer as well). */
export function listOwnSessions(userId: string, now: Date): Promise<SessionRow[]>;
/** Own session by slug (RLS), or null. */
export async function getOwnSession(slug: string): Promise<SessionRow | null>;
/** Updates exactly the given keys; 0 rows -> DataError('updateOwnSession', 'not_found'). */
export async function updateOwnSession(id: string, payload: SessionUpdate): Promise<void>;
```

| Functie | Query | Fout |
|---|---|---|
| `insertSession` | `payload` = een letterlijk uitgeschreven object met precies `spot_id`, `organizer_name`, `starts_at`, `ends_at`, `note`, `seats_free`, `departure_point` en `tikkie_url` uit `values`; `supabase.from('sessions').insert(payload).select('slug').single()` | `error.code === 'PT400' && error.message === 'rate_limited'` → `DataError('insertSession', 'rate_limited')`; anders `DataError('insertSession', error.code ?? null)`. `data.slug` geen string → `DataError('insertSession', 'no_slug')`. |
| `listOwnSessions` | `fetchAllPages('listOwnSessions', () => supabase.from('sessions').select(SESSION_COLUMNS.join(',')).eq('organizer_id', userId).gt('ends_at', now.toISOString()).order('starts_at', { ascending: true }).order('id', { ascending: true }))` | via `fetchAllPages` |
| `getOwnSession` | `supabase.from('sessions').select(SESSION_COLUMNS.join(',')).eq('slug', slug).maybeSingle()` → `data ?? null` | `DataError('getOwnSession', code)` |
| `updateOwnSession` | `supabase.from('sessions').update(payload).eq('id', id).select('id')` | `error` → `DataError('updateOwnSession', code)`; `(data ?? []).length === 0` → `DataError('updateOwnSession', 'not_found')` |

Nooit `organizer_id`, `slug`, `id`, `recent_rsvp_creates`, `created_at` of `updated_at` in een payload. De kopregel wordt `// The only module that reads or writes profiles, favorites, alert_rules, push_subscriptions and sessions.`

### `web/src/lib/sessions.ts` (contractmodule)
```ts
export { shareText, whatsappUrl, sessionUrl } from './session-model.js';

/** insertSession; on DataError code '23505' (slug collision, WP-19) exactly one retry with the same input. */
export async function createSession(input: NewSession): Promise<{ slug: string }>;
/** listOwnSessions(userId, now). */
export function listMySessions(userId: string, now: Date): Promise<SessionRow[]>;
/** null without a query when !isValidSessionSlug(slug); else getOwnSession(slug). */
export function getMySession(slug: string): Promise<SessionRow | null>;
/** updateOwnSession(id, { cancelled_at: now.toISOString() }). */
export function cancelSession(id: string, now?: Date): Promise<void>;
/** Payload = the keys of SESSION_EDITABLE_COLUMNS whose value in patch is not undefined (in that order);
 *  an empty payload makes no call. Never cancelled_at or any other key. */
export function updateSession(id: string, patch: Partial<NewSession>): Promise<void>;
```
`sessions.ts` importeert `#lib/supabase.js` niet direct; dat bewaakt `session-tables.test.ts`.

### `web/src/lib/session-page-data.ts`
```ts
export type NewSessionPageData = { kind: 'ok'; spots: Spot[] } | { kind: 'error' };
/** listSpots(); throw -> console.warn('new session load failed') and error. */
export function loadNewSessionPage(): Promise<NewSessionPageData>;

export type SharePageData =
	| { kind: 'ok'; session: SessionRow; spotName: string }
	| { kind: 'not_found' }
	| { kind: 'error' };
/** getMySession(slug); null -> not_found; then getSpot(session.spot_id): spotName = spot?.name ?? session.spot_id.
 *  throw -> console.warn('share page load failed') and error. */
export function loadSharePage(slug: string): Promise<SharePageData>;

export interface MySessionEntry { session: SessionRow; spotName: string }
export type MySessionsPageData = { kind: 'ok'; entries: MySessionEntry[]; spots: Spot[] } | { kind: 'error' };
/** Promise.all([listMySessions(userId, now), listSpots()]); spotName from the list, else spot_id.
 *  throw -> console.warn('my sessions load failed') and error. */
export function loadMySessionsPage(userId: string, now: Date): Promise<MySessionsPageData>;
```
De `console.warn`-regels bevatten nooit een foutmelding, user-id, slug of spot-id.

### `web/src/lib/components/SessionForm.svelte`
Props:
```ts
{
	mode: 'create' | 'edit';
	idPrefix: string;                        // 'new' or the session id: unique ids per form
	spots: Spot[];
	initial: SessionFormValues;
	preferred: PreferredWindow | null;
	onsave: (value: NewSession) => Promise<string | null>;  // null = saved, else a Dutch message
}
```
- **State:**
  - `let form = $state<SessionFormValues>(untrack(() => ({ ...initial })))`, met het commentaar `// initial value only`;
  - `errors = $state<FieldErrors<SessionFormField>>({})`;
  - `status = $state<'idle' | 'saving' | 'saved' | 'failed'>('idle')`;
  - `failMessage = $state('')`.
- **Id's:** `` `${idPrefix}-${field}` ``.
- **Markup** in `<form novalidate onsubmit={submit} class="session-form">`, in deze volgorde. Elk veld staat in een `.form-field` met `<label for>`, de input, een optionele `<p class="hint" id="{id}-hint">` en bij een fout `<p class="error" id="{id}-error">`. `aria-invalid={!!errors.x || undefined}`; `aria-describedby` krijgt de hint- en fout-id's die er zijn.
  1. `Spot`: `<select>` met `<option value="">Kies een spot</option>` en per spot `<option value={s.id}>{s.name}{s.verified ? '' : ' (niet geverifieerd)'}</option>`.
  2. `Datum`: `<input type="date" min={bounds.min} max={bounds.max}>`, met `const bounds = sessionDateBounds(new Date())` eenmalig bij het aanmaken van de component. Door `novalidate` begrenzen `min` en `max` alleen de datumkiezer; de echte controle zit in `parseSessionForm` (`dateRange`).
  3. `Van`: `<input type="time">`.
  4. `Tot`: `<input type="time">`, met de hint `Tijden in Nederlandse tijd.`
  5. `Je voornaam`: `type="text"`, `autocomplete="given-name"`, hint `Alleen je voornaam. Shakka onthoudt hem op dit apparaat.`
  6. `Notitie (optioneel)`: `<textarea rows="3">`, hint `Hoogstens 280 tekens.`
  7. `Vrije plekken in je auto (optioneel)`: `type="text"`, `inputmode="numeric"`, hint `0 tot 8. Leeg als je niet rijdt.`
  8. `Vertrekpunt (optioneel)`: `type="text"`, hint `Bijvoorbeeld Utrecht CS.`
  9. `Tikkie-link (optioneel)`: `type="url"`, `inputmode="url"`, `autocomplete="off"`, hint `Een link uit de Tikkie-app (https://tikkie.me/…). Deelnemers zien deze link.`
  10. Alleen bij `mode === 'edit'`: `<p class="hint">Deelnemers krijgen geen bericht van een wijziging. Laat het ze zelf weten.</p>`.
  11. `<button type="submit" disabled={status === 'saving'}>`, met de tekst `Sessie aanmaken` (create) of `Wijzigingen opslaan` (edit).
  12. Meldingen:
      - zijn er fouten: `<p role="alert" class="error">{SESSION_FORM_MESSAGES.summary}</p>`;
      - `saved` en `edit`: `<p role="status">Opgeslagen.</p>`;
      - `failed`: `<p role="alert" class="error">{failMessage}</p>`.
- **`submit(e)`:**
  1. `e.preventDefault()`; doe niets als `status === 'saving'`.
  2. `r = parseSessionForm(form, { now: new Date(), spotIds: new Set(spots.map((s) => s.id)), preferred })`.
  3. Fout: `errors = r.errors`, `status = 'idle'`, return (geen `onsave`).
  4. Anders: `errors = {}`, `status = 'saving'`, `msg = await onsave(r.value)`.
  5. `msg === null` → `status = 'saved'`; anders `status = 'failed'` en `failMessage = msg`.

### Routes
- **`go/+page.ts`:**
  ```ts
  export const load: PageLoad = ({ url }) => {
  	const p = parseGoParams(url);
  	if (!p) redirect(307, '/');
  	return { returnPath: url.pathname + url.search, target: newSessionHref(p) };
  };
  ```
- **`go/+page.svelte`:** `let { data }: PageProps = $props();` en `let handledFor: string | null = null; // plain variable, not $state: the returnPath already redirected for`. Het `$effect` (review N-6: gekoppeld aan `data.returnPath`):
  ```ts
  $effect(() => {
  	const s = $session;
  	const returnPath = data.returnPath;
  	if (s === undefined || handledFor === returnPath) return;
  	handledFor = returnPath;
  	if (s === null) {
  		saveReturnTo(browserStorage(), returnPath, Date.now());
  		void goto('/login', { replace: true });
  	} else {
  		void goto(data.target, { replace: true });
  	}
  });
  ```
  Imports: `goto` uit `$app/navigation`, `session` uit `#lib/auth.js`, `browserStorage` uit `#lib/browser-storage.js`, `saveReturnTo` uit `#lib/local-prefs.js`.
  Markup: `<svelte:head><title>Doorsturen · Shakka</title></svelte:head><p>Doorsturen…</p>`.
- **`+layout.svelte`:**
  - `import { goto } from '$app/navigation'`, `import { browserStorage } from '#lib/browser-storage.js'` en `import { takeReturnTo } from '#lib/local-prefs.js'`;
  - `$effect(() => { if (!$session) return; const path = takeReturnTo(browserStorage(), Date.now()); if (path !== null) void goto(path, { replace: true }); });`;
  - in `<nav>`, na `Profiel`: `<a href="/mijn-sessies">Mijn sessies</a>`.
- **`sessie/nieuw/+page.ts`:** `export const load: PageLoad = ({ url }) => ({ params: parseNewSessionParams(url) });`
- **`sessie/nieuw/+page.svelte`:**
  - Gebruikt hetzelfde laadpatroon als `/profiel` (WP-16), met `userId`, `page`, `token`, `load` en `retry`; `load` roept `loadNewSessionPage()` aan.
  - `const prefill = untrack(() => prefillSessionForm(data.params, readOrganizerName(browserStorage()), new Date()));`
  - `<svelte:head><title>Sessie aanmaken · Shakka</title></svelte:head>`, `<h1>Sessie aanmaken</h1>`.
  - Weergave:
    - `$session === undefined` → `<p class="muted">Laden…</p>`;
    - `null` → `<LoginPrompt reason="een sessie aan te maken" />`;
    - `loading` → "Laden…";
    - `error` → `<div class="banner" role="alert"><p>De spots konden niet worden geladen. Controleer je verbinding.</p><button type="button" onclick={retry}>Opnieuw proberen</button></div>`;
    - `ok`:
      - eerst `{@const p = withKnownSpot(prefill, page.spots)}`;
      - dan `<p class="muted">Iedereen met de link ziet je voornaam, het tijdvenster, de notitie, het vertrekpunt en de Tikkie-link.</p>`;
      - dan per notice `<p class="notice" role="status">…</p>`;
      - dan `<SessionForm mode="create" idPrefix="new" spots={page.spots} initial={p.form} preferred={p.preferred} {onsave} />`.
  - `onsave`:
    ```ts
    async (v) => {
    	try {
    		const { slug } = await createSession(v);
    		writeOrganizerName(browserStorage(), v.organizer_name);
    		await goto(`/sessie/${slug}/delen`, { replace: true });
    		return null;
    	} catch (e) {
    		return sessionErrorMessage(e);
    	}
    }
    ```
- **`sessie/[slug]/delen/+page.ts`:** `export const load: PageLoad = ({ params, url }) => ({ slug: params.slug, origin: url.origin });`
- **`sessie/[slug]/delen/+page.svelte`:**
  - Hetzelfde laadpatroon, met `loadSharePage(data.slug)`. Titel `Sessie delen · Shakka`, `<h1>Sessie delen</h1>`.
  - `undefined` → "Laden…"; `null` → `<LoginPrompt reason="deze sessie te delen" />`; `error` → banner `De sessie kon niet worden geladen. Controleer je verbinding.` met de knop "Opnieuw proberen".
  - `not_found` → `<p>Deze sessie bestaat niet, of je bent niet de organisator.</p><p><a href="/mijn-sessies">Naar mijn sessies</a></p>`.
  - `ok`, met `url = sessionUrl(data.origin, s.slug)` en `text = shareText(s, spotName, url)`:
    1. `<p class="session-summary"><strong>{spotName}</strong> · {formatWindowLocal(new Date(s.starts_at), new Date(s.ends_at))}</p>`.
    2. Bij `s.cancelled_at !== null`: `<div class="banner warning" role="note"><p>Deze sessie is geannuleerd.</p></div>`. Daarna alleen nog punt 6.
    3. `<label for="share-url">Link naar de sessie</label> <input id="share-url" type="text" readonly value={url} />`.
    4. Knoppen:
       - `<a class="share-button" href={whatsappUrl(text)} target="_blank" rel="noopener noreferrer">Deel via WhatsApp</a>`;
       - `{#if canShare}<button type="button" onclick={share}>Delen…</button>{/if}`;
       - `<button type="button" onclick={copy}>Kopieer link</button>`;
       - `{#if shareStatus}<p role="status">{shareStatus}</p>{/if}`.
    5. `<details><summary>Voorbeeld van het bericht</summary><p class="prewrap share-preview">{text}</p></details>`.
    6. `<p><a href={sessionPath(s.slug)}>Bekijk de sessiepagina</a> · <a href="/mijn-sessies">Mijn sessies</a></p>`.
  - `canShare` wordt gezet in `onMount`: `typeof navigator.share === 'function'`.
  - `share`: `try { await navigator.share({ text }); shareStatus = ''; } catch (e) { shareStatus = (e as { name?: string })?.name === 'AbortError' ? '' : 'Delen is niet gelukt. Gebruik de WhatsApp-knop of kopieer de link.'; }`.
  - `copy`: `try { await navigator.clipboard.writeText(url); shareStatus = 'Link gekopieerd.'; } catch { shareStatus = 'Kopiëren is niet gelukt. Houd de link hierboven ingedrukt om hem te kopiëren.'; }`. Ontbreekt `navigator.clipboard`, dan gaat het ook naar de `catch`.
- **`mijn-sessies/+page.svelte`** (geen `+page.ts`):
  - Hetzelfde laadpatroon, met `loadMySessionsPage(id, new Date())`. Titel `Mijn sessies · Shakka`, `<h1>Mijn sessies</h1>`.
  - `undefined` → "Laden…"; `null` → `<LoginPrompt reason="je sessies te zien" />`; `error` → banner `Je sessies konden niet worden geladen. Controleer je verbinding.` met "Opnieuw proberen".
  - `ok`:
    1. `<p><a class="share-button" href="/sessie/nieuw">Nieuwe sessie</a></p>`.
    2. Geen entries → `<p>Je hebt geen komende sessies. Tik bij een spot op "Ik ga" of maak hier een nieuwe sessie.</p>`.
    3. Per entry (`{#each page.entries as e (e.session.id)}`):
       ```svelte
       <section class="my-session" data-slug={e.session.slug} aria-labelledby="sessie-{e.session.id}">
         <h2 id="sessie-{e.session.id}">{e.spotName}</h2>
         <p>{formatWindowLocal(new Date(e.session.starts_at), new Date(e.session.ends_at))}</p>
         {#if e.session.cancelled_at}
           <p class="banner warning" role="note">Geannuleerd</p>
         {:else}
           <p><a href="/sessie/{e.session.slug}/delen">Delen</a> · <a href={sessionPath(e.session.slug)}>Sessiepagina</a></p>
           <details><summary>Bewerken</summary>
             <SessionForm mode="edit" idPrefix={e.session.id} spots={page.spots} initial={sessionToForm(e.session).form}
               preferred={sessionToForm(e.session).preferred} onsave={(v) => saveEdit(e, v)} />
           </details>
           {#if confirmId === e.session.id}
             <p>Weet je het zeker? Wie de link heeft, ziet dat de sessie is geannuleerd.</p>
             <button type="button" disabled={busyId === e.session.id} onclick={() => cancel(e)}>Ja, annuleer de sessie</button>
             <button type="button" onclick={() => (confirmId = null)}>Nee</button>
           {:else}
             <button type="button" onclick={() => (confirmId = e.session.id)}>Sessie annuleren</button>
           {/if}
         {/if}
         {#if messages[e.session.id]}<p role="status">{messages[e.session.id]}</p>{/if}
       </section>
       ```
  - State: `confirmId = $state<string | null>(null)`, `busyId = $state<string | null>(null)` en `messages = $state<Record<string, string>>({})`.
  - `saveEdit(e, v)`: `try { await updateSession(e.session.id, v); e.session = { ...e.session, ...v }; return null; } catch (err) { return sessionErrorMessage(err); }`.
  - `cancel(e)`: `busyId = id`. Daarna `try { const now = new Date(); await cancelSession(id, now); e.session = { ...e.session, cancelled_at: now.toISOString() }; messages[id] = 'Sessie geannuleerd.'; } catch (err) { messages[id] = sessionErrorMessage(err) === SESSION_ERROR_MESSAGES.notFound ? SESSION_ERROR_MESSAGES.notFound : SESSION_ERROR_MESSAGES.cancelFailed; } finally { busyId = null; confirmId = null; }`.
  - De `ok`-tak staat binnen `{#if page.kind === 'ok'}`. `e.session = …` werkt op de `$state`-proxy van `page`, zoals bij `/alerts` (WP-16).
- **`spot/[id]/+page.svelte`:** `import { session } from '#lib/auth.js'`, `import { goHref, goRuns } from '#lib/go.js'` en `formatLocal` toevoegen aan de bestaande import uit `#lib/time.js`. In elke daggroep, direct na de getijregel en vóór `{#if hours.length}` (A16: alleen bij een sessie; bij `null` en `undefined` niets):
  ```svelte
  {@const runs = goRuns(g.hours)}
  {#if $session && runs.length}
  	<ul class="go-runs">
  		{#each runs as r (r.start.getTime())}
  			<li><a class="go-run" href={goHref(spot.id, r.start, r.end)}>Ik ga {formatLocal(r.start, 'time')}–{formatLocal(r.end, 'time')}</a></li>
  		{/each}
  	</ul>
  {/if}
  ```
  `{@const}` moet direct onder een blok staan; zet `runs` daarom naast de bestaande `{@const}`'s aan het begin van `{#each groups as g}`.

Stijl in `<style>`-blokken. In de spotpagina:
- `.go-runs { list-style: none; padding: 0; margin: 0.25rem 0; display: flex; flex-wrap: wrap; gap: 0.5rem; }`;
- `.go-run { display: inline-block; padding: 0.4rem 0.75rem; border-radius: 0.25rem; background: #1b7f3b; color: #fff; font-weight: 600; text-decoration: none; }`.

`.share-button` in de deelpagina en `/mijn-sessies` gebruikt dezelfde stijl met `background: #0b5e8a`. Tik-doelen zijn minstens 2.75rem hoog: `min-height: 2.75rem` op deze links en op de knoppen.

### `docs/RUNBOOK.md`
- **§11 punt 7**, de zin over `/go` wordt: `` `/go?spot=...&start=...&end=...` (de "ik ga"-link in een melding) opent vanaf WP-20 "Sessie aanmaken", vooraf ingevuld. Uitgelogd vraagt de app eerst om in te loggen, en binnen een uur na het inloggen gaat hij terug naar dezelfde link. Ongeldige parameters gaan naar `/`. ``
- **Nieuw §11 punt 10, "Sessies aanmaken en delen (vanaf WP-20)":**
  - Organiseren kan alleen met een account; in M3 is dat alleen Lars (§11.2). De crew meldt zich aan via de link, zonder account (WP-21).
  - Aanmaken kan via een melding ("ik ga"-link), via "Ik ga" op de spotpagina (alleen zichtbaar als je bent ingelogd), of via Mijn sessies, Nieuwe sessie. Daarna deel je de link `https://<project>.pages.dev/s/<code>` via WhatsApp, het deelmenu of kopiëren.
  - Hoogstens 10 nieuwe sessies per 24 uur (§16.4). Een sessie duurt hoogstens 16 uur, op één dag, van vandaag tot hoogstens een jaar vooruit.
  - De Tikkie-link moet beginnen met `https://tikkie.me/` (de app weigert andere links).
  - Bewerken en annuleren doe je in Mijn sessies. Deelnemers krijgen daar geen bericht van. Verwijderen kan niet; een sessie verdwijnt 7 dagen na het einde (§16.1).
  - Op dit apparaat bewaart de app de voornaam (`shakka:organizer_name`) en, bij inloggen vanuit een link, hoogstens een uur lang die link (`shakka:return_to`).
  - Controle (WP-20 AC-6): zie de procedure in `docs/wp/WP-20/blueprint.md`, Testplan.

### Gevolgen voor latere WP's
- **WP-21:**
  - **Afspraak (orchestrator, review B-1):** WP-20 merget als eerste en houdt zijn bestandsnamen. WP-21 hernoemt naar `#lib/public-session-data.ts`, `test/public-session-data.test.ts` en `test/fixtures/public-session.ts`, en rebaset na de merge van WP-20.
  - De route is `web/src/routes/s/[slug]/`. Het URL-contract staat hierboven.
  - **Helpers die WP-21 bij zijn rebase kan hergebruiken (A17, review N-8):**
    - `SESSION_SLUG_RE` en `isValidSessionSlug` uit `#lib/session-model.js`: zelfde naam en regex als in WP-21 `session-view.ts`. WP-21 kan ze daar herexporteren in plaats van zelf definiëren.
    - `countCodePoints` uit `#lib/session-model.js`: zelfde naam en gedrag.
    - `StorageLike` en `browserStorage` uit `#lib/browser-storage.js`: zelfde signature als in WP-21 `rsvp-storage.ts`.
    - `isTikkieUrl` en `safeTikkieLink` uit `#lib/session-model.js`: de Tikkie-regel van A18, met dezelfde returnvorm als `safeHttpsLink`. WP-21 toont de link met `safeTikkieLink` (dus alleen `https://tikkie.me/…`) en `target="_blank" rel="noopener noreferrer"`.
    - `sessionPath(slug)` voor links naar `/s/{slug}`.

    Doet WP-21 dit niet bij de rebase, dan voegt de orchestrator de dubbele helpers na de merge van beide WP's samen, uiterlijk in WP-23. Dat is mechanisch: dezelfde namen, regex en signatures.
  - **Bewust dubbel:** `formatWindowLocal` (WP-20, `time.ts`, compact: `za 18 jul 14:00–18:00`, gelijk aan de alerts en de deeltekst) en `sessionWindowText` (WP-21, voluit: `zaterdag 18 juli, 14:00–18:00`, voor de paginakop). Twee formaten voor twee doelen; samenvoegen is een keuze voor WP-23, niet nodig voor de werking.
  - `user-tables.test.ts`: WP-20 wijzigt de tests voor tabellen en schrijfacties (er komt `sessions` bij). De test "no file uses .rpc(" laat WP-20 staan; WP-21 vervangt die bij zijn rebase door de allowlist.
  - `fake-supabase.ts` krijgt van WP-20 alleen `'gt'` erbij; WP-21 raakt dat bestand niet.
- **WP-22/WP-24:** met eigen SMTP en open aanmelden kan iedereen met een account organiseren; de UI is daar al klaar voor. Heroverweeg dan A16 ("Ik ga" alleen ingelogd; uitgelogd misschien een knop met inlog- of aanmeldhint). Overweeg ook een eigen melding bij `rate_limited`, of de limiet zichtbaar maken.
- **WP-23:**
  - Privacy-inventaris:
    - `sessions.organizer_name`, `note`, `departure_point` en `tikkie_url` zijn zichtbaar voor iedereen met de link en worden 7 dagen na het einde verwijderd;
    - `localStorage`: `shakka:organizer_name` (voornaam, op het apparaat) en `shakka:return_to` (spot en tijden, hoogstens 1 uur).
  - axe-tests op `/sessie/nieuw`, `/sessie/[slug]/delen` en `/mijn-sessies` met de fixtures uit `test/fixtures/session-data.ts` (WP-20). Voor `/s/[slug]` staan de fixtures van WP-21 in `test/fixtures/public-session.ts`.
  - Opruimen van de helpers die na de merge van WP-20 en WP-21 nog dubbel zijn (zie WP-21 hierboven).
  - CSP: de WhatsApp-knop is een navigatie (geen `connect-src`), en Web Share en het klembord hebben geen origin nodig. `connect-src` blijft ongewijzigd.
- **WORK_PACKAGES:** het contract van WP-20 bijwerken naar A3 (`SessionRow`, `listMySessions(userId, now)`, `cancelSession(id, now?)`), en §11 punt 7 van de RUNBOOK vervangt de M2-zin over `/go`.

## Edge cases

| # | Geval | Gedrag |
|---|---|---|
| E1 | `/go` zonder of met ongeldige parameters (zie WP-14 E25) | `redirect(307, '/')`, zoals nu. |
| E2 | `/go` geldig, `$session` nog `undefined` | "Doorsturen…", geen navigatie, geen opslag. |
| E3 | `/go` geldig, uitgelogd | `shakka:return_to` = exact `pathname + search`, dan `goto('/login', { replace: true })`. |
| E4 | `/go` geldig, ingelogd | `goto('/sessie/nieuw?…', { replace: true })`, geen opslag. |
| E5 | De sessiestore wijzigt opnieuw op `/go` (token-refresh) | `handledFor === returnPath` voorkomt een tweede `goto`. |
| E5b | SvelteKit hergebruikt de `/go`-component voor een andere `/go`-URL (in de praktijk niet: `WindowClient.navigate` laadt volledig) | Andere `returnPath`, dus opnieuw één keer doorsturen (review N-6). |
| E6 | Inloggen via een magic link in een nieuw tabblad of via een geplakte link | De layout ziet de sessie, `takeReturnTo` geeft het pad, en `goto(pad, { replace: true })` → `/go` → `/sessie/nieuw`. |
| E7 | De terugkeersleutel is ouder dan 60 minuten, de JSON is kapot, het pad is `/login`, `https://evil.example/go?…`, `//evil.example/go?…` of `/go?spot=Bad` | `null`, de sleutel wordt verwijderd, geen navigatie. |
| E8 | `saved_at` ligt in de toekomst (klok teruggezet) | `nowMs - saved_at < 0` → `null`. |
| E9 | `localStorage` gooit (Safari met geblokkeerde opslag) | `saveReturnTo` geeft `false` en `/go` gaat toch naar `/login` (zonder terugkeer); `readOrganizerName` geeft `''`; geen crash. |
| E10 | iOS: `/go` in de beginschermapp, de magic link opent in Safari | Safari heeft geen sleutel en logt alleen Safari in. De app blijft uitgelogd: bekende WP-18-beperking; gebruik "Inloglink plakken" in de app. |
| E11 | Prefill 2026-07-18 12:00Z–16:00Z | Datum `2026-07-18`, van `14:00`, tot `18:00`. |
| E12 | Prefill 2026-10-25 10:00Z–14:00Z (eerste wintertijddag) en 2026-10-24 10:00Z–14:00Z | `11:00`–`15:00`, en `12:00`–`16:00`. |
| E13 | Prefill 2026-10-25 00:00Z–02:00Z (over de wisseling heen) | Datum `2026-10-25`, `02:00`–`03:00`. Ongewijzigd opslaan geeft precies 00:00Z–02:00Z (A8). |
| E14 | Prefill over lokale middernacht (of eind precies om 00:00) | `end_time` blijft `''`, met de melding `otherDay`. |
| E15 | Prefill langer dan 16 uur | Het eind wordt `start + 16 h`, met de melding `truncated`. |
| E16 | Prefill met een window dat al voorbij is (oude melding) | Ingevuld, met de melding `past`. Opslaan geeft `dateRange` (datum vóór vandaag) of `inPast` (vandaag, eind voorbij) tot datum of tijd is aangepast. |
| E17 | `/go` of `/sessie/nieuw?spot=onbekend` (geldige slug, maar de spot bestaat niet) | `withKnownSpot` maakt de spot leeg, met de melding `spotUnknown`. |
| E18 | `/sessie/nieuw` zonder parameters | Datum vandaag (lokaal), de rest leeg behalve de onthouden voornaam. |
| E19 | Van 02:30 op 28-03-2027 (eerstvolgende wissel naar zomertijd; 29-03-2026 is al voorbij en valt nu onder `dateRange`) | `timeNonexistent`, 0 writes. |
| E20 | Van 02:30 op 25-10-2026, handmatig ingevuld | Het eerste moment (00:30Z, zomertijd). |
| E21 | Tot = Van, of Tot vóór Van | `endBeforeStart` op `end_time`, 0 writes (AC-4). |
| E22 | Van 06:00, Tot 23:00 (17 uur) | `tooLong`. Precies 16 uur is toegestaan. |
| E23 | Een eind dat al voorbij is | `inPast`. Een begin in het verleden met een eind in de toekomst mag. |
| E24 | Voornaam: `'  Lars  '` | Opgeslagen als `Lars`. Leeg, 31 tekens of een regeleinde → `organizerName`. 30 emoji's (60 UTF-16-eenheden) zijn geldig (30 code points). |
| E25 | Vrije plekken `9`, `-1`, `2,5`, `abc` | `seatsFree`. `0` en `8` zijn geldig; leeg wordt `null`. |
| E26 | Tikkie `http://tikkie.me/pay/x`, `HTTPS://tikkie.me/pay/x`, `https://tikkie.me/pay/a b`, `https://tikkie.me/`, `https://example.org/pay/x`, `https://tikkie.me.evil.example/pay/x`, `https://tikkie.me@evil.example/x`, `https://www.tikkie.me/pay/x`, `https://tikkie.me:8443/pay/x`, en `https://tikkie.me/pay/` (22 tekens) + 179 × `a` (201 tekens) | `tikkieUrl`, 0 writes (A18). `https://tikkie.me/pay/abc`, `https://tikkie.me/pay/Tikkie/qzdnzr8hnVWTgXXcFRLUMc` en `https://tikkie.me/pay/` + 178 × `a` (precies 200 tekens) zijn geldig. |
| E27 | Notitie van 281 code points, of een vertrekpunt van 81 | Fout bij dat veld. Meerdere regels in de notitie mogen. |
| E28 | Dubbel klikken op "Sessie aanmaken" | De knop staat uit tijdens het opslaan, en `submit` negeert `saving`: één insert. |
| E29 | De insert geeft `23505` (slugbotsing) | Eén retry. Faalt die ook, dan de algemene melding. |
| E30 | De elfde sessie binnen 24 uur (`PT400`, `rate_limited`) | Melding `rateLimited`; de voornaam wordt niet opgeslagen. |
| E31 | De spot is net verwijderd (`23503`) | Melding `spotGone`. |
| E32 | Sessie verlopen (`42501`, of een JWT-fout `PGRST301`/`PGRST303` met 401) | Melding `signedOut`. |
| E33 | Netwerkfout | Melding `generic`. De Supabase-melding komt nooit op de pagina of in de console. |
| E34 | `/sessie/abc/delen` (geen geldige slug) of een sessie van iemand anders | `not_found`, zonder query bij een ongeldige vorm. RLS geeft voor een andere organisator `null`. |
| E35 | Deelpagina van een geannuleerde sessie | Banner "Deze sessie is geannuleerd.", geen deelknoppen. |
| E36 | Browser zonder `navigator.share` (desktop Firefox) | Geen knop "Delen…"; WhatsApp en kopiëren blijven. |
| E37 | Delen geannuleerd door de gebruiker (`AbortError`) | Geen melding. Een andere fout → "Delen is niet gelukt…". |
| E38 | Klembord niet beschikbaar of geweigerd | "Kopiëren is niet gelukt…"; de link staat zichtbaar in het veld. |
| E39 | Een spotnaam of notitie met `&`, `#`, `?`, emoji of `<script>` | `encodeURIComponent` in `whatsappUrl`; Svelte escapet alle tekst. |
| E40 | `/mijn-sessies` met een geannuleerde komende sessie | Getoond met "Geannuleerd", zonder acties. |
| E41 | Annuleren terwijl de sessie al verdwenen is (`not_found`) | Melding `notFound`. Andere fouten → `cancelFailed`. |
| E42 | Bewerken: de eindtijd in het verleden zetten | `inPast`, 0 writes. |
| E43 | Een sessie in een ander tabblad bewerkt | De laatste schrijfactie wint (geen versiecontrole); geaccepteerd voor één organisator. |
| E44 | Spotpagina: go-uren 12:00Z, 13:00Z, daarna `no_go`, dan weer go om 15:00Z | Twee reeksen: [12:00Z, 14:00Z) en [15:00Z, 16:00Z). |
| E45 | Spotpagina: gat in de data (12:00Z go, 14:00Z go, 13:00Z ontbreekt) | Twee reeksen (niet aaneengesloten). |
| E46 | Uitgelogd (of sessie nog `undefined`) op de spotpagina | Geen "Ik ga"-links (A16). De rest van de pagina is ongewijzigd. |
| E47 | Crewlid zonder account opent met de hand een `/go`-link | `/login`, en bij het versturen de bestaande melding `notAuthorized` (A1). Via de spotpagina kan dit niet meer (A16). |
| E48 | `/s/{slug}` openen vóór de merge van WP-21 | Standaard-SPA-fallback (geen pagina); buiten scope. |
| E49 | Datum gisteren, of meer dan 365 dagen vooruit, of een datum als `1970-06-01` | `dateRange` op de datum; geen tijdconversie, dus geen `timeNonexistent` (review N-10). Vandaag en vandaag + 365 dagen zijn geldig. |
| E50 | Bewerken van een sessie met een niet-Tikkie-`https`-link (bijv. met SQL aangemaakt, RUNBOOK §16.9) | Het formulier toont de waarde; opslaan geeft `tikkieUrl` tot het veld leeg is of een Tikkie-link bevat. Annuleren blijft werken (raakt `tikkie_url` niet). |

## Testplan
Alle tests staan in `web/test/` en draaien met `npm test`. Tests voor pure logica komen vóór de implementatie: `time` (toevoegingen), `go`, `browser-storage`, `local-prefs`, `session-model`, `session-form`, de drift- en schematests, en `user-data`/`sessions` met de nep-client. Mocks volgen het patroon van WP-13, WP-14 en WP-16:
- `#lib/supabase.js` via `createFakeSupabase` (`vi.hoisted`);
- `#lib/auth.js` via `test/helpers/fake-session.js` (`authModule`, `sessionStore`, `SESSION`, `USER_ID`);
- `$app/navigation` als `vi.mock('$app/navigation', () => ({ goto: nav.goto, refreshAll: nav.refreshAll }))`, met `nav = vi.hoisted(() => ({ goto: vi.fn(async () => {}), refreshAll: vi.fn() }))`.

Elk bestand met mocks heeft `beforeEach(() => { vi.clearAllMocks(); localStorage.clear(); })` (en `fake.current.reset()`). Datum- en tijdvelden vullen tests met `fireEvent.input(el, { target: { value: '14:00' } })`, niet met `userEvent.type`; houdt jsdom de waarde dan niet vast, gebruik `fireEvent.change`. De klok zet je met `vi.useFakeTimers({ toFake: ['Date'] })` plus `vi.setSystemTime(...)`, en terug met `vi.useRealTimers()` in `afterEach`.

### Fixtures (`web/test/fixtures/session-data.ts`)
```ts
export const SLUG = 'Q2x0aHJ1c3RtZTEyMzQ1Ng';            // 22 chars base64url (test data)
export const SESSION_ID = '00000000-0000-4000-8000-0000000000a1';
export const NOW_SESSIONS = '2026-07-15T12:30:00.000Z';
export const SESSION_ROW: SessionRow = {
	id: SESSION_ID, slug: SLUG, spot_id: 'test-strand', organizer_name: 'Lars',
	starts_at: '2026-07-18T12:00:00+00:00', ends_at: '2026-07-18T16:00:00+00:00',
	note: 'Neem een wetsuit mee', seats_free: 3, departure_point: 'Utrecht CS', tikkie_url: null,
	cancelled_at: null, created_at: '2026-07-15T12:00:00+00:00', updated_at: '2026-07-15T12:00:00+00:00'
};
export const SESSION_CANCELLED: SessionRow = { ...SESSION_ROW, id: '…a2', slug: 'Q2FuY2VsbGVkU2Vzc2lvbg', cancelled_at: '2026-07-15T13:00:00+00:00' };
/** /go fixtures in the WP-08 format around the switch to winter time (25-10-2026). */
export const GO_URL_DST_DAY = 'https://example.org/go?spot=test-strand&start=2026-10-25T10%3A00%3A00Z&end=2026-10-25T14%3A00%3A00Z';
export const GO_URL_DST_BEFORE = 'https://example.org/go?spot=test-strand&start=2026-10-24T10%3A00%3A00Z&end=2026-10-24T14%3A00%3A00Z';
export const GO_URL_DST_NIGHT = 'https://example.org/go?spot=test-strand&start=2026-10-25T00%3A00%3A00Z&end=2026-10-25T02%3A00%3A00Z';
export const TIKKIE_URL = 'https://tikkie.me/pay/test';   // test data, A18 format
export function validForm(over: Partial<SessionFormValues> = {}): SessionFormValues; // test-strand, 2026-07-18, 14:00, 18:00, 'Lars', rest ''
```
`GO_URL_SUMMER` en `GO_URL_WINTER` komen uit `fixtures/spot-data.ts`; `go-url-fixture.test.ts` bewaakt al dat ze gelijk zijn aan `ingest/tests/message_fixtures.py` (de uitvoer van `build_go_url`). De `GO_URL_DST_*`-fixtures staan niet in `message_fixtures.py`; hun formaat is via `goHref` gekoppeld aan `GO_URL_SUMMER` (zie `go.test.ts`, review N-3). Spots: `SPOT_UNVERIFIED` (`test-strand`) en `SPOT_VERIFIED` (`test-meer`).

### Per testbestand

| Bestand | Tests |
|---|---|
| `time.test.ts` (toevoegen) | `localWallTimeCandidates('2026-07-18','14:00')` → `[12:00Z]`; `('2026-10-25','02:30')` → `[00:30Z, 01:30Z]`; `('2026-03-29','02:30')` → `[]`; `('2026-03-29','03:00')` → `[01:00Z]`; de eerstvolgende wissel naar zomertijd (review N-3): `('2027-03-28','02:30')` → `[]` en `('2027-03-28','03:00')` → `[2027-03-28T01:00Z]`; `('2026-02-30','12:00')` en `('2026-07-18','24:00')` gooien `RangeError`. `localWallTimeToUtc('2026-10-25','02:00', 01:00Z)` → 01:00Z; zonder preferred → 00:00Z; met een preferred die geen kandidaat is → 00:00Z. `formatWindowLocal(2026-07-18T12Z, 16Z)` = `za 18 jul 14:00–18:00`; `(2026-10-25T00Z, 02Z)` = `zo 25 okt 02:00–03:00`; `(2026-07-18T20Z, 2026-07-19T00Z)` = `za 18 jul 22:00 – zo 19 jul 02:00` (`end - 1 ms` valt lokaal op 19-07); `(2026-07-18T20Z, 22Z)` = `za 18 jul 22:00–00:00` (eind om middernacht, zoals WP-08); `start >= end` gooit. `isSpotSlug('test-strand')` is `true`; `'Test'` en `'a'.repeat(101)` zijn `false`. |
| `go.test.ts` (vervangen) | **`load`:** voor `GO_URL_SUMMER` geeft het `{ returnPath: '/go?spot=test-strand&start=2026-07-18T12%3A00%3A00Z&end=2026-07-18T16%3A00%3A00Z', target: '/sessie/nieuw?spot=test-strand&start=2026-07-18T12%3A00%3A00Z&end=2026-07-18T16%3A00%3A00Z' }`. De ongeldige gevallen van WP-14 (zonder parameters, `spot=../x`, `spot=Test`, `start` met minuten, `start > end`, alleen `spot`) geven `isRedirect`, status 307 en location `/`. **`goHref`:** `goHref('test-strand', 2026-07-18T12:00Z, 16:00Z)` is gelijk aan `pathname + search` van `GO_URL_SUMMER`, en `parseGoParams(new URL(goHref(…), 'https://x'))` geeft dezelfde spot en tijden. Idem (review N-3): `goHref('test-strand', 2026-10-25T10:00Z, 14:00Z)` = `pathname + search` van `GO_URL_DST_DAY`, en `goHref('test-strand', 2026-10-25T00:00Z, 02:00Z)` = die van `GO_URL_DST_NIGHT`. Zo liggen de DST-fixtures via de bewaakte `GO_URL_SUMMER` vast aan het WP-08-formaat. **`goRuns`:** [go 12, go 13, no_go 14, go 15] → twee reeksen (E44); een gat → twee reeksen (E45); onsorteerde invoer wordt gesorteerd; alleen `no_go`/`marginal` → `[]`; `dark` breekt een reeks. **`parseNewSessionParams`:** voor `GO_URL_SUMMER` de ISO-strings, alleen `?spot=test-meer` → spot zonder tijden, `?spot=Bad` → alles `null`. **(AC-2)** |
| `go-page.test.ts` | Rendert `go/+page.svelte` met `data` uit `load(GO_URL_SUMMER)`; mocks voor auth en navigatie. (a) Bij `undefined` staat "Doorsturen…" er, is `goto` niet aangeroepen en is `localStorage` leeg. (b) Bij `null` volgt precies één `goto('/login', { replace: true })`, en `JSON.parse(localStorage.getItem('shakka:return_to')).path` is exact `returnPath`, dus gelijk aan `new URL(GO_URL_SUMMER).pathname + new URL(GO_URL_SUMMER).search`. (c) Met `SESSION` volgt precies één `goto(target, { replace: true })` en is er geen sleutel. (d) Eerst `undefined`, dan `SESSION`, dan een nieuw sessie-object: nog steeds één `goto`. (e) Review N-6: met `SESSION` gerenderd, daarna `rerender({ data: await load(GO_URL_WINTER) })`: precies twee `goto`-aanroepen, de tweede met de `target` van `GO_URL_WINTER`. **(AC-2)** |
| `layout.test.ts` (toevoegen) | Mock `$app/navigation` (`goto`). (a) Een verse sleutel (`saved_at = Date.now()`, pad uit `GO_URL_SUMMER`) plus `SESSION` geeft `goto(pad, { replace: true })`, en de sleutel is weg. (b) Een sleutel van 61 minuten oud geeft geen `goto`, en de sleutel is weg. (c) Bij `null` geen `goto`, en de sleutel blijft staan. (d) Ingelogd staat er een link "Mijn sessies" naar `/mijn-sessies`; bij `null` en `undefined` niet. De bestaande tests blijven groen. **(AC-2)** |
| `browser-storage.test.ts` | (a) In jsdom geeft `browserStorage()` hetzelfde object als `globalThis.localStorage`. (b) Met `vi.stubGlobal('localStorage', undefined)` geeft het `undefined` (`vi.unstubAllGlobals()` in `afterEach`). (c) Met een getter die gooit (`Object.defineProperty(globalThis, 'localStorage', { configurable: true, get() { throw new DOMException('denied', 'SecurityError'); } })`, en de oorspronkelijke descriptor terugzetten in `afterEach`) geeft het `undefined`. Laat jsdom (c) niet toe, dan schrijft de builder dat in `deviations.md` en blijft het bij (a) en (b). |
| `local-prefs.test.ts` | Met een in-memory storage, een storage die bij elke aanroep gooit, en `undefined`. **`saveReturnTo(storage, path, nowMs)`/`takeReturnTo(storage, nowMs)`:** de roundtrip werkt; precies 60 minuten oud geeft het pad, 60 minuten plus 1 ms geeft `null`; `saved_at` in de toekomst geeft `null`; kapotte JSON, `saved_at` als string of een ontbrekend `path` geven `null`; na elke `take` is de sleutel weg. `saveReturnTo(storage, '/login', …)` geeft `false` en schrijft niets. **`isAllowedReturnPath`:** de gevallen uit E7 geven `false`; het `GO_URL_SUMMER`-pad geeft `true`. Een storage die gooit, en `undefined`: `save` geeft `false`, `take` geeft `null`, `readOrganizerName` geeft `''`, `writeOrganizerName` gooit niet. **Voornaam:** `writeOrganizerName(storage, '  Lars ')` slaat `Lars` op; een ongeldige naam schrijft niets; een opgeslagen naam van 31 tekens leest als `''`. De sleutels zijn exact `shakka:organizer_name` en `shakka:return_to`. |
| `session-model.test.ts` (node) | Geen mocks: de module is puur. **Golden:** `shareText` geeft exact de vier regels uit Interfaces. **AC-3:** `u = whatsappUrl(shareText(...))` begint met `https://wa.me/?text=`; `new URL(u).searchParams` heeft alleen de sleutel `text`; `decodeURIComponent(u.slice(20))` bevat `Teststrand`, `za 18 jul`, `14:00–18:00` en `https://example.org/s/Q2x0aHJ1c3RtZTEyMzQ1Ng`. Een tekst met `&`, `#`, `?`, `+`, een spatie en een emoji komt exact terug na het decoderen (E39). **URL's:** `sessionUrl('https://example.org/', SLUG)` = `https://example.org/s/Q2x0aHJ1c3RtZTEyMzQ1Ng`; `sessionPath('abc')` en `sessionPath('a/b…')` gooien. `isValidSessionSlug(SLUG)` is `true`, `'abc'` en `'a'.repeat(65)` zijn `false`. `countCodePoints('😀')` = 1. **Tikkie (A18):** `isTikkieUrl` is `true` voor de geldige waarden uit E26 en `false` voor alle ongeldige; `isTikkieUrl('')` is `false` en gooit niet. `safeTikkieLink(TIKKIE_URL)` = `{ href: 'https://tikkie.me/pay/test', host: 'tikkie.me' }`; `safeTikkieLink(null)`, `('')`, `('https://example.org/x')` en `('javascript:alert(1)')` geven `null`. **(AC-3)** |
| `session-form.test.ts` | Met `NOW = 2026-07-15T12:30Z` en `spotIds = {test-strand, test-meer}`. **Prefill:** E11 (`GO_URL_SUMMER`), `GO_URL_WINTER` (`2026-11-07`, `12:00`, `15:00`), E12 (`GO_URL_DST_DAY` en `GO_URL_DST_BEFORE`) en E13 (`GO_URL_DST_NIGHT`: `02:00`–`03:00`, en `parseSessionForm(prefill.form, {…, preferred: prefill.preferred})` geeft precies `2026-10-25T00:00:00.000Z` en `…T02:00:00.000Z`). Ook E14, E15, E16, E17 (`withKnownSpot`) en E18. Bij E11, E12 en E16 zet de test `now` vóór het window, behalve bij E16 zelf. **Parse:** een geldig formulier geeft exact `{spot_id: 'test-strand', organizer_name: 'Lars', starts_at: '2026-07-18T12:00:00.000Z', ends_at: '2026-07-18T16:00:00.000Z', note: null, seats_free: null, departure_point: null, tikkie_url: null}`; E19–E27, elk met de exacte melding uit `SESSION_FORM_MESSAGES` (E19 met datum `2027-03-28`, Van `02:30`, Tot `05:00` → `timeNonexistent` op `start_time`; E20 met `2026-10-25`); E49: `2026-07-14` (gisteren) en `2027-07-16` (366 dagen) → `dateRange` en geen `timeNonexistent`/`inPast`, `2026-07-15` en `2027-07-15` → geen datumfout, `1970-06-01` met Van `02:30` → alleen `dateRange`; `sessionDateBounds(NOW)` = `{ min: '2026-07-15', max: '2027-07-15' }`; `tikkie_url` = `TIKKIE_URL` komt ongewijzigd in `value`; meerdere fouten tegelijk; `sessionToForm(SESSION_ROW)` roundtript naar dezelfde waarden; E50: `sessionToForm({ ...SESSION_ROW, tikkie_url: 'https://example.org/pay' })` toont de waarde, en parse geeft `tikkieUrl`. **(AC-2, AC-4)** |
| `session-schema.test.ts` (node) | Leest `supabase/migrations/20261015200000_sessions.sql`. `columns('sessions')` (zelfde parser als `schema-columns.test.ts`) zonder `organizer_id` en `recent_rsvp_creates` is gelijk aan `[...SESSION_COLUMNS]`. De `grant insert (…) on table public.sessions to authenticated` zonder `organizer_id`, en de `grant update (…)` zonder `cancelled_at`, zijn als verzameling gelijk aan `SESSION_EDITABLE_COLUMNS`. Grenzen uit de constraints (fragment van 300 tekens na de naam): `sessions_organizer_name_valid` `between 1 and 30` → `ORGANIZER_NAME_MAX`; `sessions_note_length` `<= 280`; `sessions_seats_free_range` `between 0 and 8`; `sessions_departure_point_length` `<= 80`; `sessions_tikkie_url_https` bevat `'^https://` en `<= 200`; `sessions_window_max_16h` `interval '16 hours'`; `sessions_slug_format` bevat `{10,64}` (en `SESSION_SLUG_RE.source` bevat ook `{10,64}`). Een latere migratie met `alter table public.sessions … add/drop/rename column` laat de test falen ("update session-model.ts and this test"). **(AC-4)** |
| `user-data.test.ts` (toevoegen) | **`insertSession`:** de ops zijn `[['insert', {8 sleutels}], ['select', 'slug'], ['single']]`; de payload-sleutels zijn precies `SESSION_EDITABLE_COLUMNS` (dus geen `organizer_id`, `slug` of `cancelled_at`). `{ code: 'PT400', message: 'rate_limited' }` → `DataError` met `code` `rate_limited`, en de `message` van de error bevat geen Supabase-tekst. `{ code: '23503' }` → code `23503`. **`listOwnSessions`:** de ops bevatten `['eq', 'organizer_id', USER_ID]`, `['gt', 'ends_at', NOW_SESSIONS]`, `['order', 'starts_at', asc]`, `['order', 'id', asc]` en `range`. **`getOwnSession`:** `eq('slug', SLUG)` en `maybeSingle`. **`updateOwnSession`:** `[['update', payload], ['eq', 'id', SESSION_ID], ['select', 'id']]`; `data: []` → `not_found`. |
| `sessions.test.ts` | Fake-supabase. **`createSession`:** bij `23505` en daarna succes volgen twee inserts met dezelfde payload, en het resultaat is `{slug}`; bij twee keer `23505` gooit hij `DataError` met code `23505`; bij `rate_limited` volgt geen retry. **`cancelSession(SESSION_ID, new Date(NOW_SESSIONS))`:** precies één call op `sessions`, met de ops `[['update', { cancelled_at: '2026-07-15T12:30:00.000Z' }], ['eq', 'id', SESSION_ID], ['select', 'id']]` (respons `[{ id }]`). **`updateSession`:** `{ note: 'x', starts_at: … }` geeft een payload met precies die twee sleutels; `{}` geeft 0 calls; een object met een extra sleutel `cancelled_at` of `organizer_id` (via cast) komt niet in de payload. **`getMySession('abc')`:** `null` en 0 calls. **`listMySessions(USER_ID, now)`:** dezelfde ops als `listOwnSessions`. **Fouten:** `sessionErrorMessage` per code (`new DataError('x', 'rate_limited')`, `'23503'`, `'23514'`, `'42501'`, `'PGRST301'`, `'PGRST303'`, `'PGRST302'` (→ `generic`), `'not_found'`, `null`, en `new Error('geheim')`), en de uitvoer bevat nooit `geheim`. **(AC-5)** |
| `session-tables.test.ts` (node) | `sessions.ts`, `session-model.ts`, `session-form.ts`, `go.ts`, `local-prefs.ts` en `browser-storage.ts` bevatten geen `.from(`, geen `.rpc(` en geen import van `supabase`. `session-model.ts`, `session-form.ts`, `go.ts`, `local-prefs.ts` en `browser-storage.ts` importeren geen `./data.js`, `./user-data.js` of `./sessions.js` (ze blijven puur). `session-model.ts`, `session-form.ts` en `go.ts` bevatten geen `localStorage`. In heel `web/src` komt `wa.me` alleen voor in `session-model.ts`. |
| `user-tables.test.ts` (wijzigen) | De lijst met toegestane tabellen in `user-data.ts` krijgt `'sessions'` erbij (naam en test: vijf tabellen). `.update(` komt precies 2 keer voor, telkens direct na `.from('profiles')` of `.from('sessions')`. `.insert(` mag na `favorites`, `push_subscriptions` of `sessions`. De test "no file uses .rpc(" blijft ongewijzigd. |
| `session-form-component.test.ts` | Rendert `SessionForm` (create) met `spots = [SPOT_UNVERIFIED, SPOT_VERIFIED]`, `initial = validForm()`, `preferred = null` en `onsave = vi.fn(async () => null)`, met de klok op `NOW_SESSIONS`. AC-4, elk met de veldmelding, de samenvatting met `role="alert"` en `onsave` niet aangeroepen: (a) `Tot` `14:00` (gelijk aan Van); (b) `Tot` `13:00`; (c) vrije plekken `9`; (d) Tikkie `http://tikkie.me/x`, en apart Tikkie `https://example.org/pay/x` (A18); (e) een voornaam van 31 tekens. (f) Het geldige formulier roept `onsave` één keer aan met de `NewSession` uit `session-form.test.ts`. (g) Een `onsave` die `'X'` teruggeeft toont `X` in een `role="alert"`. (h) Het veld met de fout heeft `aria-invalid="true"` en `aria-describedby` met de fout-id. (i) Edit-modus toont "Wijzigingen opslaan" en de hint over deelnemers. (j) Het datumveld heeft `min="2026-07-15"` en `max="2027-07-15"`; Datum `2026-07-14` geeft de melding `dateRange` en geen `onsave`. **(AC-4)** |
| `new-session-page.test.ts` | Fake-supabase, fake-session, navigatiemock. De klok staat op `NOW_SESSIONS` (`vi.useFakeTimers({ toFake: ['Date'] })`), anders vallen de fixturevensters buiten `dateRange`/`inPast` zodra de echte datum verder is. (a) Bij `null`: de loginprompt "Log in om een sessie aan te maken." en 0 calls. (b) Bij `SESSION`, `data = await load({ url: new URL('https://example.org' + target) })` voor `GO_URL_SUMMER` en `spots` → `[SPOT_UNVERIFIED, SPOT_VERIFIED]`: Spot is `test-strand`, Datum `2026-07-18`, Van `14:00` en Tot `18:00`. (c) Idem voor `GO_URL_DST_DAY` (`11:00`/`15:00`) en `GO_URL_DST_NIGHT` (`2026-10-25`, `02:00`/`03:00`). (d) Met `shakka:organizer_name` = `Lars` staat de voornaam vooraf ingevuld. (e) Opslaan met `sessions` → `{ data: { slug: SLUG } }`: precies één insert (`writeCalls` = 1) met de payload van E13 bij (c), daarna `goto('/sessie/Q2x0aHJ1c3RtZTEyMzQ1Ng/delen', { replace: true })`, en `localStorage` heeft `Lars`. (f) Met Tot = Van: 0 writes (AC-4). (g) Bij `rate_limited` staat de melding `rateLimited` er, is er geen `goto` en is de naam niet opgeslagen. (h) Bij een spotfout de banner en "Opnieuw proberen". **(AC-2, AC-4)** |
| `share-page.test.ts` | `data = { slug: SLUG, origin: 'https://example.org' }`; `sessions` → `SESSION_ROW`, `spots` (getSpot) → `SPOT_UNVERIFIED`. (a) De link "Deel via WhatsApp" heeft een `href` die begint met `https://wa.me/?text=`; de gedecodeerde tekst is gelijk aan `shareText(SESSION_ROW, 'Teststrand', 'https://example.org/s/' + SLUG)`; `target="_blank"` en `rel` bevat `noopener` en `noreferrer`. (b) Het veld "Link naar de sessie" heeft precies de URL. (c) Met `navigator.clipboard = { writeText: vi.fn(async () => {}) }` roept "Kopieer link" `writeText(url)` aan en volgt "Link gekopieerd.". Een rejectende `writeText` geeft de foutmelding. (d) Zonder `navigator.share` is er geen knop "Delen…"; met `navigator.share = vi.fn(async () => {})` roept de knop `share({ text })` aan; een reject met `{ name: 'AbortError' }` geeft geen melding. (e) Bij `SESSION_CANCELLED` de banner en geen WhatsApp-link. (f) `data.slug = 'abc'`: "Deze sessie bestaat niet…" en 0 calls. (g) Bij `null` de loginprompt. Ruim `navigator.share` en `navigator.clipboard` op in `afterEach`. **(AC-3)** |
| `my-sessions-page.test.ts` | (a) Bij `null` de loginprompt en 0 calls. (b) Bij `SESSION` (`USER_ID`) en de klok op `NOW_SESSIONS`: de call op `sessions` bevat `['eq', 'organizer_id', USER_ID]` en `['gt', 'ends_at', '2026-07-15T12:30:00.000Z']`; er is geen enkele call met een andere `organizer_id`. **(AC-5)** (c) Twee entries: `SESSION_ROW` met de titel `Teststrand`, `za 18 jul 14:00–18:00` en de links `Delen` (`/sessie/…/delen`) en `Sessiepagina` (`/s/…`); `SESSION_CANCELLED` met "Geannuleerd" en zonder de knop "Sessie annuleren". (d) "Sessie annuleren" → "Ja, annuleer de sessie": een update op `sessions` met `cancelled_at` = `NOW_SESSIONS` en `eq('id', SESSION_ID)`; daarna "Geannuleerd" en "Sessie geannuleerd.". **(AC-5)** (e) "Nee" annuleert de bevestiging zonder write. (f) Bewerken: Vertrekpunt `Amersfoort` en "Wijzigingen opslaan" → een update met precies de 8 bewerkbare sleutels (`departure_point: 'Amersfoort'`) en "Opgeslagen.". (g) Een lege lijst toont de uitleg en de link "Nieuwe sessie". |
| `session-page-data.test.ts` | `loadSharePage('abc')` → `not_found` met 0 calls; `getOwnSession` `null` → `not_found`; een onbekende spot → `spotName` = `spot_id`; een fout → `error`, met `console.warn` precies `'share page load failed'`. `loadMySessionsPage` koppelt de spotnamen. `loadNewSessionPage` geeft bij een fout `error`. |
| `spot-page.test.ts` (toevoegen) | Extra mock: `vi.mock('#lib/auth.js', async () => (await import('./helpers/fake-session.js')).authModule)`, met `sessionStore` en `SESSION` uit `./helpers/fake-session.js`; in de bestaande `beforeEach` komt `sessionStore.set(null)`. De supabase-mock die bij import gooit, blijft staan: met `auth.js` gemockt laadt de spotpagina de client niet. (a) Met `sessionStore.set(SESSION)` en `pageData()`: precies twee links met een naam die begint met `Ik ga`: "Ik ga 14:00–15:00" met `href` `/go?spot=test-strand&start=2026-07-15T12%3A00%3A00Z&end=2026-07-15T13%3A00%3A00Z`, en "Ik ga 10:00–11:00" (morgen, `EVAL_TOMORROW`) met `href` `/go?spot=test-strand&start=2026-07-16T08%3A00%3A00Z&end=2026-07-16T09%3A00%3A00Z`. (b) Review N-7, een dag zonder go-uren: met `SESSION` en `pageData({ evaluations: [EVAL_OFFSHORE, EVAL_LOWCONF, EVAL_DARK, EVAL_TOMORROW] })` is er precies één `Ik ga`-link, "Ik ga 10:00–11:00"; vandaag (`no_go`, `marginal`, `dark`) heeft er geen. (c) A16: met `pageData()` en `sessionStore.set(null)`, en apart met `sessionStore.set(undefined)`, is er geen enkele link met een naam die begint met `Ik ga`; de uren staan er wel. |

`go-url-fixture.test.ts`, `no-local-date-getters.test.ts`, `no-third-party.test.ts`, `no-telegram.test.ts` en `guard.test.ts` blijven ongewijzigd groen.

### Koppeling acceptatiecriteria → bewijs
- **AC-1:** `cd web && npm run check && npm test && npm run build && npm run verify:build`, plus vanuit de root `bash scripts/check-no-client-openmeteo.sh`.
- **AC-2:** `go.test.ts` (load en fixture), `go-page.test.ts` (ingelogd → `/sessie/nieuw`; uitgelogd → `/login` met exact dezelfde URL opgeslagen), `layout.test.ts` (terugkeer na inloggen), `session-form.test.ts` en `new-session-page.test.ts` (lokale tijden, ook rond 25-10-2026).
- **AC-3:** `session-model.test.ts` (golden, prefix, decodering) en `share-page.test.ts`.
- **AC-4:** `session-form-component.test.ts`, `new-session-page.test.ts` (0 writes), `session-form.test.ts` en `session-schema.test.ts` (drift).
- **AC-5:** `sessions.test.ts` (`cancelSession` zet `cancelled_at`, gemockt) en `my-sessions-page.test.ts` (alleen `organizer_id = USER_ID`).
- **AC-6 (`NEEDS_LARS`):**
  - **Vooraf:**
    - de migratie van WP-19 staat in productie (`supabase db push`, RUNBOOK §16.2);
    - `APP_BASE_URL` is gezet (RUNBOOK §13.2);
    - deze WP staat op de productie-URL;
    - push staat aan op de telefoon (WP-18), en de telefoon is ingelogd in de app op het beginscherm.
  - **Procedure:**
    1. Laat een echte alert binnenkomen, of forceer er een (RUNBOOK §14.9 en `uv run shakka alerts run`).
    2. Tik op de melding. "Sessie aanmaken" opent, met de spot en het window in lokale tijd.
    3. Vul de voornaam in en tik "Sessie aanmaken". De deelpagina toont `https://<project>.pages.dev/s/<22 tekens>`.
    4. Tik "Deel via WhatsApp" (en probeer ook "Delen…" en "Kopieer link"), en stuur het bericht naar jezelf of een testgroep. Controleer dat de tekst de spot, de datum, het tijdvenster en de link bevat, zonder extra parameters.
    5. Open de link vanuit WhatsApp. Met WP-21 erbij opent de sessiepagina; zonder WP-21 controleer je alleen de URL.
    6. Ingelogd: open een spot met Go-uren en tik op "Ik ga". "Sessie aanmaken" opent, vooraf ingevuld met die reeks. Sla niet op.
    7. Terugkeer na inloggen (review N-2). Uitloggen in de beginschermapp verwijdert het push-abonnement van dat apparaat (WP-18, RUNBOOK §14.14), dus er komt dan geen nieuwe melding om op te tikken. Doe deze stap daarom bij voorkeur in een browser (laptop, of Safari op de telefoon, niet de beginschermapp):
       1. Log daar uit. Controleer dat de spotpagina geen "Ik ga" toont (A16).
       2. Open met de hand een `go_url`: `https://<project>.pages.dev/go?spot=<spot-id>&start=<YYYY-MM-DD>T12%3A00%3A00Z&end=<YYYY-MM-DD>T14%3A00%3A00Z`, met een datum in de komende dagen. De app gaat naar `/login`.
       3. Vraag een inloglink aan en open die in dezelfde browser (of plak hem met "Inloglink plakken"). Binnen een uur na stap 2 kom je terug op "Sessie aanmaken", met 14:00–16:00 (zomertijd) of 13:00–15:00 (wintertijd).
       4. Heb je deze stap toch in de beginschermapp gedaan: log daar weer in en zet meldingen opnieuw aan (RUNBOOK §14.12).
    8. Annuleer de testsessie in Mijn sessies.

    Noteer de uitkomst per stap in `docs/wp/WP-20/verification.md`.

## Externe afhankelijkheden
Geen nieuwe packages. Gecontroleerd op 15 oktober 2026:
- **WhatsApp click-to-chat:** `https://wa.me/?text=urlencodedtext` opent WhatsApp met de tekst vooraf ingevuld en een keuzelijst van contacten. Er is geen telefoonnummer en er zijn geen andere parameters. Bron: https://faq.whatsapp.com/452366545421244 (officieel; de pagina laadde niet volledig) en https://help.businesschat.io/en/articles/6517838-how-to-build-a-whatsapp-click-to-chat-url-wa-me ("You can also create a link with just a pre-filled message, use `https://wa.me/?text=urlencodedtext`").
- **Web Share API:** `navigator.share({ text })`. Vereist een secure context en een gebruikersactie (transient activation). Mogelijke rejects: `AbortError` (geannuleerd of geen doel), `NotAllowedError`, `TypeError`, `DataError` en `InvalidStateError`. De API is niet in elke browser beschikbaar, dus de app controleert `typeof navigator.share === 'function'`. Bron: https://developer.mozilla.org/en-US/docs/Web/API/Navigator/share
- **Clipboard API:** `navigator.clipboard.writeText(text): Promise<void>`. Alleen in een secure context; een weigering geeft `NotAllowedError`. Bron: https://developer.mozilla.org/en-US/docs/Web/API/Clipboard/writeText
- **SvelteKit 3 `goto`:** `goto(url, { replace: true })`. `replaceState` is deprecated ("Use `replace` instead"). Bron: https://svelte.dev/docs/kit/$app-navigation
- **supabase-js insert met returning:** `.insert(...).select()`. Bron: https://supabase.com/docs/reference/javascript/insert. `.select('slug').single()` en `.update(...).eq(...).select('id')` gebruiken dezelfde builder als de bestaande `upsert(...).select(...).single()` en `update(...).select(...).single()` in `user-data.ts`.
- **PostgREST-fouten:** `{code: 'PT400', message: 'rate_limited'}` bij de elfde sessie (WP-19 A2; `RAISE sqlstate 'PTxyz'` geeft HTTP-status `xyz`). CHECK-schendingen geven `23514` en ontbrekende rechten `42501`. JWT-fouten (review N-5): `PGRST301` (401, "Provided JWT couldn't be decoded or it is invalid") en `PGRST303` (401, "JWT claims validation or parsing failed"); `PGRST302` (anonieme rol uitgeschakeld) komt in dit project niet voor en valt onder `generic`. Bron: https://docs.postgrest.org/en/v14/references/errors.html (gaf HTTP 429), daarom gecontroleerd in de bron van die pagina: https://raw.githubusercontent.com/PostgREST/postgrest/main/docs/references/errors.rst (15 oktober 2026).
- **Tikkie-links (A18):** een echt Tikkie-betaalverzoek begint met `https://tikkie.me/pay/`, bijvoorbeeld `https://tikkie.me/pay/Tikkie/qzdnzr8hnVWTgXXcFRLUMc`. Bronnen: https://www.fixjeprivacy.nl/tip/controleer-of-een-tikkie-betaalverzoek-veilig-is/ (een echte link begint met `https://tikkie.me/pay/`; nepsites gebruiken lijkende domeinen) en https://github.com/KentaaNL/tikkie-api/blob/master/README.md (voorbeeld-URL). De app eist `https://tikkie.me/` plus minstens één teken, zoals de orchestrator besliste; `/pay/` is niet verplicht gemaakt.
- **`rel="noopener noreferrer"`** op externe links (WhatsApp hier, Tikkie in WP-21): geen `window.opener` en geen Referer. Bron: https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Attributes/rel/noreferrer
- **Supabase Auth-redirect:** `emailRedirectTo` blijft de origin (WP-13); er is geen nieuwe Redirect URL nodig.

## Risico's
- **R1. Parallelle bouw met WP-21 (herzien na review B-1).** In revisie 1 maakten WP-20 en WP-21 allebei `#lib/session-page-data.ts`, `test/session-page-data.test.ts` en `test/fixtures/session-data.ts` aan, met verschillende inhoud. **Afspraak (orchestrator):** WP-20 merget als eerste en houdt die namen; WP-21 hernoemt naar `public-session-data.ts`, `public-session-data.test.ts` en `fixtures/public-session.ts`, en rebaset na de merge van WP-20. Daarna overlappen alleen nog:
  - `web/test/user-tables.test.ts`: WP-20 wijzigt de tests voor tabellen en schrijfacties, WP-21 vervangt alleen de test "no file uses .rpc(" door een allowlist. Andere tests in hetzelfde bestand; een eventueel tekstconflict lost WP-21 bij zijn rebase mechanisch op.
  - `docs/RUNBOOK.md`: WP-20 wijzigt §11 (punt 7, nieuw punt 10), WP-21 §16 (punten 8 en 9). Andere secties.

  `app.css` wijzigt alleen WP-21; `fake-supabase.ts`, `time.ts`, `+layout.svelte` en de spotpagina alleen WP-20. De helpers met dezelfde rol hebben dezelfde naam en signature als in WP-21 (A17), zodat WP-21 ze na de rebase kan importeren. De eindcontrole (stap 13) controleert dat WP-20 geen bestand aanmaakt dat bij WP-21 hoort.
- **R2. Web Share verschilt per platform.** Alleen `text` delen (A11) voorkomt dubbele of ontbrekende links. Valt het toch tegen op Lars' telefoon (AC-6), dan blijft de WhatsApp-knop de hoofdroute.
- **R3. Terugkeer na inloggen op iOS.** Safari en de app op het beginscherm delen geen opslag (E10). Dat is de bekende beperking van WP-13 en WP-18. De route via "Inloglink plakken" werkt wel.
- **R4. Een oude terugkeersleutel.** Wie het inloggen afbreekt en binnen een uur via een andere weg inlogt, komt op "Sessie aanmaken" terecht. Dat gebeurt hoogstens één keer (de sleutel wordt altijd verwijderd) en is onschuldig.
- **R5. jsdom en `type="date"`/`type="time"`.** jsdom saneert waarden van deze inputs. De tests gebruiken geldige waarden via `fireEvent.input`, met `fireEvent.change` als terugvaloptie. Lukt het geen van beide, dan schrijft de builder dat in `deviations.md` en test hij die velden alleen via `session-form.test.ts`.
- **R6. Een verkeerde klok op het apparaat.** De controle "al voorbij" gebruikt de apparaatklok; de database controleert dat niet. Bij een sterk afwijkende klok kan een sessie onterecht geweigerd of geaccepteerd worden. Dat is geaccepteerd.
- **R7. Crew zonder account** ziet geen "Ik ga" (A16) en kan dus niet zelf organiseren; alleen wie met de hand een `/go`-link opent, komt bij een loginmuur (A1). Dat verandert pas met eigen SMTP en open aanmelden (WP-22/WP-24).
- **R9. Tikkie-regel strenger dan de database (A18).** Een sessie die buiten de app om met een andere `https`-link is gemaakt (SQL, RUNBOOK §16.9), kan in het bewerkformulier pas worden opgeslagen als de link leeg is of een Tikkie-link is (E50). Annuleren werkt wel. Geaccepteerd: alleen Lars maakt zulke sessies.
- **R8. `redirect()` in een universele load** werkt bij de eerste paginalading van de statische SPA. WP-14 heeft dat met `npm run preview` gecontroleerd; deze WP houdt hetzelfde patroon aan.

## Buiten scope
- De publieke pagina `/s/[slug]`, RSVP, `get_public_session` en `#lib/rsvp.ts` (WP-21).
- Backendwijzigingen, migraties en nieuwe RPC's.
- Het aantal deelnemers op `/mijn-sessies` (A13).
- Een annulering terugdraaien, een sessie verwijderen, en meldingen aan deelnemers bij een wijziging of annulering.
- Dynamische OG-previews per sessie (statische site).
- Organiseren door crewleden, eigen SMTP en open aanmelden (WP-22).
- Privacypagina, CSP en axe-tests (WP-23).
- Sessies over middernacht (A7).

## Stappenplan voor de builder
Werk op branch `wp/WP-20` in `/Users/larst/Dev/Shakka/.claude/worktrees/WP-20`. Lees of print `.env` en `web/.env` nooit. Draai na elke stap vanuit `web/`: `npm run check && npm test`. Maak één commit per stap, met een Engels commitbericht.

0. **Basis controleren.** `git merge-base --is-ancestor origin/develop HEAD` slaagt, `supabase/migrations/20261015200000_sessions.sql` bestaat en `docs/RUNBOOK.md` heeft `## 16.`. Zo niet: stop en meld het aan de orchestrator. Geen commit.
1. **Tijd.** Tests in `time.test.ts` (rood), dan `isSpotSlug`, `localWallTimeCandidates`, `localWallTimeToUtc` en `formatWindowLocal` aan het eind van `time.ts`. Commit: `feat(WP-20): local wall time to UTC and window formatting`.
2. **Sessiemodel en drift.** `test/fixtures/session-data.ts` (deze naam; niet `public-session.ts`, dat is van WP-21), `session-model.test.ts` en `session-schema.test.ts` (rood), dan `session-model.ts`, inclusief `SESSION_SLUG_RE`, `isValidSessionSlug`, `countCodePoints`, `isTikkieUrl` en `safeTikkieLink` (A17, A18). Commit: `feat(WP-20): session model, share text and WhatsApp URL`.
3. **Formulierlogica.** `session-form.test.ts` (rood), dan `session-form.ts`, met `dateRange` en de Tikkie-regel. Commit: `feat(WP-20): session form parsing and prefill`.
4. **Go en lokale opslag.** `go.test.ts` (vervangen, alleen de pure delen: `goRuns`, `goHref` inclusief de DST-fixtures, `newSessionHref`, `parseNewSessionParams`), `browser-storage.test.ts` en `local-prefs.test.ts` (rood), dan `go.ts` (zonder `goTarget`), `browser-storage.ts` (exact zoals in Interfaces) en `local-prefs.ts`. Zet `go/+page.ts` meteen om naar de nieuwe load. Maak `go/+page.svelte` tijdelijk een `onMount` die `goto(data.target, { replace: true })` doet, zodat de build blijft werken. Commit: `feat(WP-20): go runs, go hrefs and return-to storage`.
5. **Data.** Voeg `'gt'` toe aan `fake-supabase.ts`. Tests in `user-data.test.ts`, `sessions.test.ts`, `session-tables.test.ts` en de wijziging in `user-tables.test.ts` (rood). Dan de vier functies in `user-data.ts` (met de nieuwe kopregel), `sessions.ts` en `session-page-data.ts`, met `session-page-data.test.ts`. Commit: `feat(WP-20): session queries and contract module`.
6. **Formuliercomponent.** `session-form-component.test.ts` (rood), dan `SessionForm.svelte`. Commit: `feat(WP-20): SessionForm component`.
7. **`/go` en terugkeren.** `go-page.test.ts` en de nieuwe tests in `layout.test.ts`, met de `$app/navigation`-mock (rood). Dan `go/+page.svelte` volgens Interfaces, en het `$effect` plus de navigatielink in `+layout.svelte`. Commit: `feat(WP-20): /go continues to the session form or to login and back`.
8. **`/sessie/nieuw`.** `new-session-page.test.ts` (rood), dan de route (`+page.ts`, `+page.svelte`). Commit: `feat(WP-20): create session page`.
9. **Delen.** `share-page.test.ts` (rood), dan `sessie/[slug]/delen/`. Commit: `feat(WP-20): share page with WhatsApp, Web Share and copy`.
10. **Mijn sessies.** `my-sessions-page.test.ts` (rood), dan `mijn-sessies/+page.svelte`. Commit: `feat(WP-20): my sessions with edit and cancel`.
11. **Spotpagina.** De `#lib/auth.js`-mock en de nieuwe tests in `spot-page.test.ts` (rood), dan de "Ik ga"-links achter `{#if $session && runs.length}` (A16). Commit: `feat(WP-20): Ik ga links for go runs on the spot page`.
12. **RUNBOOK.** §11 punt 7 en het nieuwe punt 10, zoals in Interfaces. Commit: `docs(WP-20): runbook for creating and sharing sessions`.
13. **Eindcontrole.**
    - Vanuit `web/`: `npm ci && npm run check && npm test && npm run build && npm run verify:build`.
    - Vanuit de root: `bash scripts/check-no-client-openmeteo.sh`.
    - `cd ingest && uv run pytest` (moet ongewijzigd groen zijn).
    - `git grep -nE "sb_(secret|publishable)_[A-Za-z0-9_-]{20,}|eyJhbGciOi" -- . ':!docs'` geeft niets.
    - `grep -rn "wa.me" web/src` toont alleen `session-model.ts`.
    - Geen bestanden van WP-21 (afspraak B-1): `git diff --name-only --diff-filter=A origin/develop...HEAD | grep -E "routes/s/|rsvp|public-session|session-view"` geeft niets.
    - Met `npm run preview` handmatig: `/go?…` uitgelogd → `/login`; na inloggen (lokale stack, Mailpit) terug via `/go` naar het vooraf ingevulde formulier; aanmaken → deelpagina; Terug geeft geen lus op `/go`.

    Schrijf afwijkingen in `docs/wp/WP-20/deviations.md` en zet AC-6 op `NEEDS_LARS` (procedure in het Testplan).

## Verwerking review
Review ronde 1 (`docs/wp/WP-20/review.md`, CHANGES_REQUIRED), met de beslissingen van de orchestrator.

| Punt | Verwerking |
|---|---|
| **B-1** (blokkerend): dezelfde drie bestanden in WP-20 en WP-21 | Opgelost volgens de afspraak van de orchestrator: WP-20 merget eerst en **houdt** `#lib/session-page-data.ts`, `test/session-page-data.test.ts` en `test/fixtures/session-data.ts`; WP-21 hernoemt naar `public-session-data.ts`, `public-session-data.test.ts` en `fixtures/public-session.ts` en rebaset na de merge. Aangepast: Ontwerp (alinea "Bestandsnamen naast WP-21"), Bestanden (opmerking bij beide bestanden, plus de lijst met namen die WP-20 niet gebruikt), R1 (herschreven, met de echte overlap: `user-tables.test.ts` en `RUNBOOK.md`; `app.css` alleen WP-21), "Gevolgen" (WP-21-afspraak, WP-23-fixtures per WP), Stappenplan stap 2 en een extra controle in stap 13. Voor gedeelde helpers koos ik de namen en signatures van WP-21 (A17): `SESSION_SLUG_RE`, `isValidSessionSlug`, `countCodePoints`, en `StorageLike`/`browserStorage()` in de nieuwe module `#lib/browser-storage.ts`. `local-prefs.ts` krijgt de opslag daarom als eerste parameter. `fake-supabase.ts` (alleen `'gt'`) en `time.ts` raakt WP-21 niet. |
| N-1: A10, minimaal 1 of 2 go-uren | `GO_RUN_MIN_HOURS = 1` blijft, volgens het advies van de reviewer en de beslissing van de orchestrator. A10 is herschreven met de onderbouwing, en met een expliciet **beslispunt voor Lars** inclusief wat er bij 2 moet veranderen (constante, `go.test.ts`, spotpaginatest met twee aaneengesloten go-uren). |
| N-2: AC-6 stap 6 niet uitvoerbaar | Herschreven als stap 7, met vier deelstappen: uitloggen in een browser (niet de beginschermapp), controleren dat er geen "Ik ga" staat (A16), de `go_url` met de hand openen (met sjabloon), inloggen en terugkomen op "Sessie aanmaken", en zo nodig meldingen weer aanzetten (RUNBOOK §14.12). "Ik ga" op de spotpagina is uitgelogd niet meer zichtbaar (N-4), dus die route test nu de nieuwe stap 6, ingelogd. |
| N-3: tijdtests | `time.test.ts`: `('2027-03-28','02:30')` → `[]` en `('2027-03-28','03:00')` → `[01:00Z]`. `go.test.ts`: `goHref` voor `GO_URL_DST_DAY` en `GO_URL_DST_NIGHT` gelijk aan `pathname + search`, zodat de DST-fixtures via `GO_URL_SUMMER` aan WP-08 vastliggen. De formuliertest voor E19 gebruikt nu 28-03-2027, omdat 29-03-2026 onder de nieuwe datumgrens (N-10) valt. |
| N-4: "Ik ga" voor uitgelogde crew | Beslissing orchestrator vastgelegd als A16: "Ik ga" alleen bij een sessie (`{#if $session && runs.length}`), uitgelogd geen knop en geen hint. Aangepast: Doel, A1, Ontwerp, spotpagina-interface (import van `session` uit `#lib/auth.js`), E46/E47, R7, RUNBOOK punt 10, spotpaginatests (met `#lib/auth.js`-mock) en "Gevolgen" (WP-22/WP-24 heroverweegt). |
| N-5: JWT-fouten | `PGRST301` en `PGRST303` gaan naar `signedOut`; `PGRST302` blijft `generic`. Codes en betekenis gecontroleerd in de bron van de PostgREST-documentatie (Externe afhankelijkheden). De opmerking over `42501` staat bij de foutmeldingen. Tests in `sessions.test.ts`. |
| N-6: `done` bij hergebruik van de component | Overgenomen: `handledFor` onthoudt de `returnPath` waarvoor al is doorgestuurd. Nieuwe E5b en `go-page.test.ts` (e) met `rerender`. |
| N-7: spotpaginatest zonder go-uren | Overgenomen, met een expliciete override: `pageData({ evaluations: [EVAL_OFFSHORE, EVAL_LOWCONF, EVAL_DARK, EVAL_TOMORROW] })`, waarna er precies één link is ("Ik ga 10:00–11:00", morgen) en vandaag geen. Niet de voorgestelde `[EVAL_GO, EVAL_OFFSHORE, EVAL_LOWCONF]`: daarin staat geen morgen, dus dan wordt er geen dag zónder link getoond. |
| N-8: dubbele helpers na de merge | Grotendeels voorkomen met A17 (dezelfde namen en signatures als WP-21, zodat WP-21 bij zijn rebase kan importeren). In "Gevolgen" staat wie wat samenvoegt: WP-21 bij de rebase, anders de orchestrator na de merge, uiterlijk WP-23. `formatWindowLocal` en `sessionWindowText` blijven bewust twee formaten (compact en voluit). |
| N-9: contractafwijkingen A3 | Geen wijziging nodig; in A3 genoteerd dat de reviewer ze accepteert en dat de orchestrator `WORK_PACKAGES.md` bijwerkt. |
| N-10: datumveld zonder grenzen | Overgenomen: `dateRange` met vandaag tot vandaag + 365 dagen (`SESSION_MAX_DAYS_AHEAD`, `sessionDateBounds`), plus `min`/`max` op de datuminput. Een datum vóór vandaag kon nooit geldig zijn (A7), dus dit weigert niets extra's. Aangepast: A9, interfaces, E16, E19, nieuwe E49, tests in `session-form.test.ts`, `session-form-component.test.ts` (j) en RUNBOOK punt 10. `new-session-page.test.ts` zet nu ook de klok op `NOW_SESSIONS`; zonder dat zou de test na juli 2026 al op `inPast` falen (ook in revisie 1). |
| Tikkie-link (orchestrator, uit de WP-21-review N-6) | A18: alleen `https://tikkie.me/…` (`TIKKIE_URL_RE`, `isTikkieUrl`, host precies `tikkie.me`), met de nieuwe melding en hint. `safeTikkieLink` geeft WP-21 dezelfde regel, met de returnvorm van `safeHttpsLink`; een Tikkie-link als `<a>` krijgt altijd `target="_blank" rel="noopener noreferrer"`. WP-20 toont de link zelf nergens als `<a>`. Nieuwe E50 en R9 voor bestaande niet-Tikkie-links; E26 en de tests zijn uitgebreid. |
