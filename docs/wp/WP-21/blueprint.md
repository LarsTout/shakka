# Blueprint WP-21: Publieke sessiepagina en RSVP zonder account
Status: DRAFT
Revisie: 3

## Doel
Iedereen met een link `/s/{slug}` (meestal gedeeld in WhatsApp) ziet zonder account:
- de sessie: spotnaam met link naar de spotpagina, datum en tijdvenster in lokale tijd, organisator, notitie, Tikkie-link (alleen `https://tikkie.me/...`);
- de deelnemerslijst en de carpoolsituatie (vrije plekken en vertrekpunt van de organisator, wie een lift aanbiedt, wie meerijdt, wie een lift zoekt);
- per uur van het window het oordeel (`HourVerdict` uit WP-14) met de versheid van de data, en `Attribution`;
- een banner als de sessie geannuleerd of voorbij is.

De bezoeker tikt "Ik ook" met alleen een voornaam en een vervoerskeuze. Na `rsvp_create` bewaart de browser de edit-token in `localStorage` onder `shakka:rsvp:{slug}`. Daarna toont de pagina "Jij gaat", met wijzigen en afmelden. Elke RPC-fout krijgt een vaste Nederlandse melding; de servertekst komt nooit op het scherm.

Alles gebeurt in `/web`. Er zijn geen migraties, geen wijzigingen in `ingest/` en geen nieuwe packages. Het databasecontract komt uit WP-19.

## Aannames
Voorstellen waar Lars op kan reageren staan als **Voorstel**.

- **A1. Eén module voor anonieme RPC's: `#lib/rsvp.ts`.** `user-data.ts` blijft de enige module die tabellen van ingelogde gebruikers schrijft (WP-16). De vier sessie-RPC's zijn geen tabeltoegang en horen niet bij een gebruiker, dus ze staan niet in `user-data.ts`. `rsvp.ts` is de enige module in `web/src` die `.rpc(` aanroept. Dat bewaakt de aangepaste test in `user-tables.test.ts` (allowlist `RPC_FILES = ['lib/rsvp.ts']`). `rsvp.ts` gebruikt geen `.from(` en raakt `supabase.auth` niet aan.
- **A2. De pure logica staat los van de I/O.** De bestanden:
  - `#lib/rsvp-types.ts`: types en constanten;
  - `#lib/session-view.ts`: parsers, foutcodes, `RsvpError`, meldingen, formuliervalidatie, carpool en tijdvenster. Puur, zonder I/O;
  - `#lib/rsvp-storage.ts`: `localStorage`, met een injecteerbare `Storage` en een geheugenfallback (E26);
  - `#lib/rsvp.ts`: de RPC-aanroepen;
  - `#lib/public-session-data.ts`: de load.

  Alle nieuwe bestandsnamen botsen niet met WP-20 (B-1 van review ronde 1): WP-20 maakt `session-page-data.ts`, `session-model.ts`, `session-form.ts`, `sessions.ts`, `browser-storage.ts`, `local-prefs.ts` en `test/fixtures/session-data.ts`; WP-21 maakt geen van die bestanden.

  Paginatests mocken alleen `#lib/rsvp.js` en gebruiken de echte opslag en de echte pure logica (zelfde patroon als WP-14 A6).
- **A3. Laden via een universele `+page.ts`, met een gediscrimineerde unie** (`ok`, `not_found`, `error`), zoals WP-14. De load roept `get_public_session` aan en daarna `getEvaluations` (WP-14) voor het window. Faalt alleen het laden van de evaluaties, dan blijft de pagina bruikbaar met `evaluations: null` en de melding "Het oordeel kon niet worden geladen." Het oordeel is aanvullende informatie; aanmelden moet blijven werken.
- **A4. De uren van het window.** De uren `[floorHour(starts_at), ends_at)` worden getoond, allemaal, ook donkere uren (de gebruiker koos dit venster zelf; er is geen knop). Een uur `[T, T+1h)` overlapt het window precies als `floorHour(starts_at) <= T < ends_at`. Dat klopt ook voor een begin- of eindtijd die niet op het hele uur valt. Het window is hoogstens 16 uur (WP-19), dus hoogstens 17 rijen. Valt het window over middernacht, dan krijgt elke dag een kop (`formatDateKey(key, 'day')`); bij één dag is er geen dagkop.
- **A5. "Gesloten" in de browser** is `cancelled || ends_at <= now`. `now` begint als `data.now` uit de load en wordt bijgewerkt naar `new Date()`:
  - na elke verversing door het paneel (`applyRefresh`);
  - door een timer die 1 seconde na `ends_at` afgaat, zolang de pagina open staat.

  De server beslist (`session_closed`). Antwoordt de server `session_closed` terwijl de browser de sessie nog open vindt (klok van het apparaat loopt achter), dan zet het paneel een eigen vlag `serverClosed` en verbergt het formulier en Wijzigen. Bij een gesloten sessie:
  - is er geen formulier om je aan te melden en geen "Wijzigen";
  - blijft "Afmelden" wel staan voor wie een token heeft (WP-19 A10);
  - is de versheidsmelding verborgen.
- **A6. De token staat alleen in `localStorage`**, als JSON `{"rsvp_id": "<uuid>", "edit_token": "<43 tekens>"}` onder `shakka:rsvp:{slug}`. Niet in een cookie, URL, link, de DOM of een log. RPC's gaan via `supabase.rpc(naam, args)` zonder derde argument. supabase-js doet dan een POST met de argumenten in de body (`get`/`head` staan standaard op `false`), dus de token komt niet in de querystring (WP-19 review N-8, RUNBOOK §16.7). Elke RPC krijgt een timeout van 15 seconden via `.abortSignal(AbortSignal.timeout(15_000))` op de builder; dat blijft een POST. Een afgebroken fetch wordt door postgrest-js opgevangen als fetchfout en resolvet met `status: 0`, dus `network`. Kent de browser `AbortSignal.timeout` niet, dan gaat de RPC zonder timeout.
- **A7. Wanneer de sleutel verdwijnt:**
  - na een geslaagde of al eerder uitgevoerde afmelding (`rsvp_delete` geeft `true` of `false`);
  - bij `invalid_token` van `rsvp_update`;
  - als de sessie niet (meer) bestaat (`not_found`, of een verversing geeft `null`);
  - bij de eerste load van een slug op deze pagina-instantie, als de opgeslagen `rsvp_id` niet in de deelnemerslijst staat. De RSVP bestaat dan niet meer; WP-19 heeft geen andere route waarlangs een RSVP verdwijnt dan de bewaartermijn of handmatig ingrijpen van Lars;
  - als de waarde misvormd is.

  Daarna kun je je opnieuw aanmelden. De controle bij de eerste load gebeurt maar één keer per slug. Zo wist een verversing (`refreshAll` bij terugkeer) die toevallig gelijktijdig met een aanmelding loopt, de net opgeslagen sleutel niet.

  **Geaccepteerde rand (review N-10).** Twee tabbladen: laadt tabblad B terwijl tabblad A zich net aanmeldt, dan kan het antwoord van B de nieuwe RSVP nog missen. De eerste controle van B wist dan de sleutel die A net schreef. Het venster is een fractie van een seconde. Gevolg: in A staat "Jij gaat" (in het geheugen van A), in B het formulier; bij een volgende load in A verschijnt het formulier weer en kan de bezoeker zich niet meer afmelden (R1-route via Lars). Dit wordt niet opgelost in deze WP.
- **A8. Na elke mutatie ververst het paneel alleen de sessie**, via `getPublicSession(slug)`, en niet via `refreshAll()`. Dat is één RPC, en de evaluaties en de rest van de pagina blijven staan. De pagina zet de nieuwe `session` en `rsvps` via overschrijfbare `$derived`-waarden (Svelte ≥ 5.25). Een nieuwe load (`data`) zet ze weer terug naar de loadwaarde.
- **A9. Meerijden (`rides_with`) kies je pas bij "Wijzigen".** `rsvp_create` heeft geen parameter `p_rides_with` (WP-19). Wie zich aanmeldt met "Ik zoek een lift" staat bij "Zoekt een lift". Via Wijzigen kies je daarna een aanbieder uit de lijst ("Rijd mee met"). Bij een aanmelding met `needs_ride` zegt een korte hint dat dit kan.
- **A10. Plekken bij een liftaanbod: "Weet ik nog niet" (`null`) of 0 t/m 8**, gelijk aan de DB-CHECK. 0 heet "Geen (auto zit vol)". Er is geen controle op capaciteit (WP-19 Buiten scope).
- **A11. Namen in `<bdi>`.** Elke vrije tekst van gebruikers (voornaam, organisatornaam, vertrekpunt, notitie) wordt gerenderd in een `<bdi>`-element. Zo kan een naam met een rechts-naar-links-teken (U+202E) de tekst eromheen niet omdraaien (WP-19 review N-7). Een `<option>` kan geen elementen bevatten; daar staat de naam tussen U+2068 (FSI) en U+2069 (PDI) via `isolateText` (review N-7). Svelte escapet alle tekst; nergens `{@html}`.
- **A12. De organisator telt mee in "Deelnemers"** (`rsvps.length + 1`) en staat bovenaan met "organisator". Hij is geen RSVP; zijn vrije plekken staan bij Carpool.
- **A13. Voorstel: een privacyregel bij het formulier**: "Alleen je voornaam en je vervoerskeuze worden opgeslagen, tot 7 dagen na de sessie. Iedereen met deze link kan ze zien. Wijzigen of afmelden kan later alleen in deze browser op dit apparaat." De 7 dagen komen uit `SESSION_RETENTION_DAYS`. Een drifttest vergelijkt die met de migratie (WP-19 A1; Lars moet de termijn nog bevestigen).
- **A14. De Tikkie-link** wordt alleen getoond als hij begint met `https://tikkie.me/`, er na die prefix nog minstens één teken volgt, `new URL(tikkie_url)` slaagt en `hostname === 'tikkie.me'` (beslissing orchestrator bij review N-6: alleen `https://tikkie.me/...`; dezelfde regel komt via de orchestrator in de validatie van WP-20). Een echte Tikkie heeft de vorm `https://tikkie.me/pay/<code>`. De prefix sluit een poort, gebruikersnaam, andere host en subdomein uit. Linktekst "Open betaalverzoek", met `target="_blank" rel="noopener noreferrer"`. Daarnaast staat "(link naar tikkie.me)", zodat je ziet waar je heen gaat (WP-19 R5). Een andere `https:`-link (bijvoorbeeld van een sessie die vóór de WP-20-regel is aangemaakt) wordt stil niet getoond.
- **A15. Een tweede tabblad maakt geen dubbele RSVP.** Vlak voor `createRsvp` leest het paneel de opslag opnieuw. Staat daar al een sleutel (aangemaakt in een ander tabblad), dan maakt het geen nieuwe RSVP. Het toont dan "Jij gaat" en ververst. De omgekeerde rand (B wist de verse sleutel van A) staat bij A7.
- **A16. Afmelden vraagt een bevestiging in de pagina** ("Weet je zeker dat je je wilt afmelden?" met "Ja, afmelden" en "Nee"), geen `window.confirm`. Dat is beter te testen en werkt ook in in-app-browsers.
- **A17. De voornaam wordt niet onthouden tussen sessies**, en `shakka:organizer_name` (WP-20) wordt niet gelezen. Minimale persoonsgegevens; elke RSVP is los.
- **A18. Geen dynamische OG-preview, geen `X-Robots-Tag`-header.** `noindex` staat als `<meta>` in de pagina (via `<svelte:head>`, door JavaScript toegevoegd; Google ondersteunt dat). Crawlers zonder JavaScript krijgen de lege app-shell zonder sessiedata. Een `X-Robots-Tag` voor `/s/*` in `web/static/_headers` is een voorstel voor WP-23, dat dit bestand maakt.
- **A19. Docker en de lokale stack zijn niet nodig voor de tests.** Alle tests draaien met vitest en mocks. De handmatige rooktest (stap 7) gebruikt de lokale stack als die er is.
- **A20. Volgorde ten opzichte van WP-20: WP-20 merget eerst.** WP-21 wordt parallel gebouwd met eigen kleine helpers. Na de merge van WP-20 rebaset WP-21 op `develop` (stap 9) en vervangt het de helpers die WP-20 identiek levert (namen gecontroleerd in de WP-20-blueprint revisie 2, r. 100, 104, 191–208 en 296–309):
  - `SESSION_SLUG_RE`, `isValidSessionSlug` en `countCodePoints`: WP-20 levert ze met precies deze namen in `#lib/session-model.ts`. `session-view.ts` herexporteert ze daarvandaan en verwijdert de eigen definities;
  - de body van `sessionWindowText` door `formatWindowLocal(start: Date, end: Date)` uit `#lib/time.ts`;
  - optioneel de body van `tikkieLink` door `safeTikkieLink(url)?.href ?? null` uit `#lib/session-model.ts` (zelfde zichtbare gedrag, zie stap 9);
  - het type `StorageLike` in `rsvp-storage.ts` door `StorageLike` uit `#lib/browser-storage.ts` (identiek: `Pick<Storage, 'getItem' | 'setItem' | 'removeItem'>`).

  **`browserStorage` blijft de eigen versie in `rsvp-storage.ts`.** WP-20 `browserStorage()` (in `#lib/browser-storage.ts`) geeft `StorageLike | undefined`; de WP-21-versie geeft `StorageLike | null`, en `rsvp-storage.test.ts` eist `null`. Die test mag in stap 9 niet veranderen (R10-criterium), dus de functie blijft dubbel. Dat staat als opruimpunt in "Gevolgen voor latere WP's". De WP-21-PR merget pas na stap 9.
- **A21. De vensternotatie is die van WP-20 en WP-08** (`za 18 jul 14:00–18:00`; over middernacht `za 18 jul 22:00 – zo 19 jul 04:00`). Dezelfde notatie als in de WhatsApp-deeltekst waar de bezoeker vandaan komt, en als in de alerts. De volledige dag- en maandnamen van revisie 1 vervallen (review N-9).

## Ontwerp

**Lagen.**
```
routes/s/[slug]/+page.ts  ──> #lib/public-session-data.ts ──> #lib/rsvp.ts ──> #lib/supabase.js
                                                         └──> #lib/data.ts (getEvaluations, bestaand)
routes/s/[slug]/+page.svelte ──> components/SessionParticipants.svelte (deelnemers + carpool, puur)
                             ──> components/RsvpPanel.svelte ──> #lib/rsvp.ts, #lib/rsvp-storage.ts
                                   └──> components/RsvpForm.svelte (validatie via session-view)
                             ──> HourVerdict, Freshness, Attribution (bestaand)
puur, zonder I/O: #lib/rsvp-types.ts, #lib/session-view.ts (+ bestaande time, view, labels, contracts)
```
- De load (`loadPublicSessionPage`) controleert eerst de vorm van de slug (geen RPC bij een ongeldige slug). Daarna `getPublicSession` en, als die een sessie geeft, `getEvaluations(spot_id, floorHour(starts_at), ends_at)`.
- De pagina is presentatie plus de opslagstatus en de klok (`now`, A5). Bij elke nieuwe `data` leest een `$effect` de opgeslagen RSVP. Bij de eerste data van een slug ruimt hij een verouderde sleutel op (A7).
- `RsvpPanel` is de toestandsmachine. Er zijn drie toestanden:
  - geen token en open sessie: het aanmeldformulier;
  - wel een token: "Jij gaat", met Wijzigen (alleen bij een open sessie en als de eigen RSVP in de lijst staat) en Afmelden;
  - geen token en gesloten sessie: niets.

  Daarbinnen zijn er de modi `view`, `edit` en `confirm_delete`, plus één `busy`-vlag tegen dubbele verzending en de vlag `serverClosed` (A5). "Gesloten" in het paneel is `closed || serverClosed`. `stored` is een `$bindable` prop, zodat de pagina "(jij)" in de lijst kan tonen. De pagina zet het paneel in `{#key data.slug}`, zodat modus, meldingen en `serverClosed` niet meegaan naar een andere sessie.
- **Foutafhandeling.** `rsvp.ts` zet elke fout om in `RsvpError` met een `kind`:
  - de vijf contractcodes (alleen bij `code === 'PT400'` en een bekende `message`);
  - `network` (HTTP-status 0, ook na de timeout, of een gegooide fout);
  - `unknown` (al het andere, ook een misvormd antwoord).

  De UI kent alleen `kind` en toont `RSVP_MESSAGES[kind]`. De servertekst gaat nergens heen: niet in `Error.message`, niet in de DOM en niet in de console.

**Waarom zo.** De anonieme route is de meest blootgestelde plek van de app. Daarom:
- is er één module die de RPC's doet, met een broncodetest;
- zijn de parsers strikt en geven ze nooit onbekende velden door;
- is er een contracttest die parameternamen, sleutels, foutcodes, regexen en de bewaartermijn rechtstreeks uit de WP-19-migratie leest;
- staat de token alleen in een POST-body en in `localStorage`, met tests die controleren dat hij niet in de DOM, de URL of de console komt.

De pure modules maken alle beslissingen (gesloten, carpool, labels, validatie, foutmelding) toetsbaar zonder netwerk.

## Bestanden

| Pad | Actie | Inhoud |
|---|---|---|
| `web/src/lib/rsvp-types.ts` | aanmaken | Types en constanten (exact, zie Interfaces). |
| `web/src/lib/session-view.ts` | aanmaken | Pure logica: regexen, `rsvpStorageKey`, `RsvpError`, `rsvpErrorKind`, meldingen, parsers, `isSessionClosed`, `sessionWindowText`, `seatsText`, `rideLabel`, `carpoolView`, `tikkieLink`, `isolateText`, formulierlogica. |
| `web/src/lib/rsvp-storage.ts` | aanmaken | `browserStorage`, `readStoredRsvp`, `writeStoredRsvp`, `clearStoredRsvp`, `resetRsvpMemory`. |
| `web/src/lib/rsvp.ts` | aanmaken | `RPC_TIMEOUT_MS`, `getPublicSession`, `createRsvp`, `updateRsvp`, `deleteRsvp` (exact, zie Interfaces). |
| `web/src/lib/public-session-data.ts` | aanmaken | `PublicSessionPageData`, `loadPublicSessionPage`. |
| `web/src/lib/components/SessionParticipants.svelte` | aanmaken | Deelnemerslijst en carpool. |
| `web/src/lib/components/RsvpForm.svelte` | aanmaken | Formulier "Ik ook" en "Wijzigen". |
| `web/src/lib/components/RsvpPanel.svelte` | aanmaken | Toestand "aanmelden / Jij gaat / wijzigen / afmelden". |
| `web/src/routes/s/[slug]/+page.ts` | aanmaken | Eén regel: `loadPublicSessionPage(params.slug, new Date())`. |
| `web/src/routes/s/[slug]/+page.svelte` | aanmaken | De publieke sessiepagina. |
| `web/src/app.css` | wijzigen | Een blok `/* WP-21: public session page */` aan het eind (zie Stijl). Bestaande regels blijven. |
| `web/test/helpers/fake-rpc.ts` | aanmaken | Nep-`rpc` (thenable builder met `abortSignal`) met vastgelegde aanroepen, plus een client met een `auth`-teller. |
| `web/test/fixtures/public-session.ts` | aanmaken | Fixtures (zie Testplan). |
| `web/test/session-view.test.ts` | aanmaken | Zie Testplan. |
| `web/test/rsvp-storage.test.ts` | aanmaken | Zie Testplan. |
| `web/test/rsvp.test.ts` | aanmaken | Zie Testplan. |
| `web/test/rsvp-contract.test.ts` | aanmaken | Zie Testplan. |
| `web/test/public-session-data.test.ts` | aanmaken | Zie Testplan. |
| `web/test/public-session-page.test.ts` | aanmaken | Zie Testplan. |
| `web/test/public-session-page-integration.test.ts` | aanmaken | Zie Testplan. |
| `web/test/rsvp-flow.test.ts` | aanmaken | Zie Testplan. |
| `web/test/session-no-auth.test.ts` | aanmaken | Zie Testplan. |
| `web/test/user-tables.test.ts` | wijzigen | Alleen de test `'no file uses .rpc('` wordt vervangen door de allowlist-test (zie Interfaces). De rest blijft. |
| `docs/RUNBOOK.md` | wijzigen | §16, nieuwe punten 8 en 9 (zie Interfaces). |

Stap 9 (na de merge van WP-20, A20) wijzigt daarnaast alleen `session-view.ts` en `rsvp-storage.ts` uit deze tabel; geen WP-20-bestanden.

Geen wijzigingen in `ingest/`, `supabase/`, `data/`, `.github/`, de service worker, de layout, `time.ts`, `types.ts`, `data.ts`, `user-data.ts`, `test/helpers/fake-supabase.ts` of `package.json`.

**Overlap met WP-20 (gecontroleerd tegen `.claude/worktrees/WP-20/docs/wp/WP-20/blueprint.md`, tabel "Bestanden" en Testplan).** Geen enkel bestand dat WP-21 aanmaakt, wordt ook door WP-20 aangemaakt: de load heet `public-session-data.ts` (WP-20: `session-page-data.ts`), de fixtures `fixtures/public-session.ts` (WP-20: `fixtures/session-data.ts`), en de paginatests `public-session-*.test.ts` (WP-20: `session-page-data.test.ts`, `session-model.test.ts`, `session-form*.test.ts`, `session-schema.test.ts`, `session-tables.test.ts`). WP-21 raakt `time.ts` en `fake-supabase.ts` niet aan (WP-20 wel). Gewijzigd door beide: alleen `web/test/user-tables.test.ts` (andere tests in hetzelfde bestand) en `docs/RUNBOOK.md` (WP-20 §11, WP-21 §16). `app.css` wijzigt alleen WP-21; WP-20 gebruikt `<style>`-blokken (WP-20, alinea onder "Bestanden"). Zie R3. `docs/STATUS.md` en `WORK_PACKAGES.md` werkt de orchestrator bij.

## Interfaces en contracten
Imports gaan via `#lib/<bestand>.js` (WP-13). Alle teksten voor de gebruiker zijn Nederlands. Code, identifiers en `Error`-meldingen zijn Engels. In `web/src` mogen de woorden `plausible` en `cdn.` nergens voorkomen, ook niet in commentaar (de trackerscan uit WP-13). Tijden worden alleen opgemaakt met `formatLocal` en `formatDateKey` uit `time.ts` (`no-local-date-getters`).

### `web/src/lib/rsvp-types.ts` (exact)
```ts
// Shapes of the public session RPCs (WP-19 migration 20261015200000_sessions.sql).
// rsvp-contract.test.ts reads that migration and checks these keys, limits and the retention.

export const RIDES = ['own', 'needs_ride', 'offers_ride'] as const;
export type Ride = (typeof RIDES)[number];

export const MAX_FIRST_NAME = 30; // code points, like char_length in Postgres
export const MAX_SEATS = 8;
export const MAX_RSVPS = 30;
export const SESSION_RETENTION_DAYS = 7; // mirrors interval '7 days' in purge_expired_sessions

export const PUBLIC_SESSION_KEYS = [
	'slug', 'spot_id', 'spot_name', 'organizer_name', 'starts_at', 'ends_at', 'note',
	'seats_free', 'departure_point', 'tikkie_url', 'cancelled'
] as const;
export const PUBLIC_RSVP_KEYS = ['id', 'first_name', 'ride', 'seats_offered', 'rides_with', 'created_at'] as const;

export interface PublicSessionInfo {
	slug: string;
	spot_id: string;
	spot_name: string | null;
	organizer_name: string;
	starts_at: string; // ISO 8601 with offset; parse, never compare as string
	ends_at: string;
	note: string | null;
	seats_free: number | null;
	departure_point: string | null;
	tikkie_url: string | null;
	cancelled: boolean;
}

export interface PublicRsvp {
	id: string;
	first_name: string;
	ride: Ride;
	seats_offered: number | null;
	rides_with: string | null;
	created_at: string;
}

export interface PublicSession {
	session: PublicSessionInfo;
	rsvps: PublicRsvp[];
}

export interface RsvpInput {
	first_name: string;
	ride: Ride;
	seats_offered: number | null;
}
export interface RsvpUpdateInput extends RsvpInput {
	rides_with: string | null;
}

/** Value under shakka:rsvp:{slug} in localStorage. */
export interface StoredRsvp {
	rsvp_id: string;
	edit_token: string;
}
```

### `web/src/lib/session-view.ts`
```ts
import type { PublicRsvp, PublicSession, PublicSessionInfo, Ride, RsvpUpdateInput, StoredRsvp } from './rsvp-types.js';
import { formatLocal, localDateKey } from './time.js';

// Until WP-20 is merged: own copies of SESSION_SLUG_RE/isValidSessionSlug/countCodePoints (WP-20 session-model.ts,
// same names) and formatWindowLocal (time.ts), with identical behaviour. Step 9 replaces them (blueprint A20).
export const SESSION_SLUG_RE = /^[A-Za-z0-9_-]{10,64}$/;   // same as the migration and WP-20 SESSION_SLUG_RE
export const EDIT_TOKEN_RE = /^[A-Za-z0-9_-]{43}$/;        // same as the migration
export const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
export const RSVP_STORAGE_PREFIX = 'shakka:rsvp:';

export function isValidSessionSlug(slug: string): boolean;          // SESSION_SLUG_RE.test(slug)
export function rsvpStorageKey(slug: string): string;              // RSVP_STORAGE_PREFIX + slug

export const RPC_ERROR_CODES = ['rate_limited', 'session_closed', 'session_full', 'invalid_input', 'invalid_token'] as const;
export type RpcErrorCode = (typeof RPC_ERROR_CODES)[number];
export type RsvpErrorKind = RpcErrorCode | 'network' | 'unknown';

/** The only error the RSVP code throws. message: `${operation} failed: ${kind}`; never server text. */
export class RsvpError extends Error {
	readonly kind: RsvpErrorKind;
	readonly operation: string;
	constructor(kind: RsvpErrorKind, operation: string);
}

/** status === 0 -> 'network'; error.code === 'PT400' and error.message in RPC_ERROR_CODES -> that code;
 *  everything else (incl. null, non-objects, other codes) -> 'unknown'. Reads code/message defensively. */
export function rsvpErrorKind(error: unknown, status?: number): RsvpErrorKind;

export const RSVP_MESSAGES: Record<RsvpErrorKind, string>;   // exact texts below
export const RSVP_NOTICES: {
	created: string; storageFailed: string; updated: string; deleted: string; alreadyDeleted: string;
};
export const RSVP_FORM_MESSAGES: {
	nameRequired: string; nameTooLong: string; nameInvalid: string; rideRequired: string;
	seatsInvalid: string; ridesWithInvalid: string;
};
export const RIDE_OPTION_LABEL_NL: Record<Ride, string>;

/** Strict parsers: unknown keys are dropped, wrong types throw RsvpError('unknown', operation). */
export function parsePublicSession(json: unknown): PublicSession;           // operation 'getPublicSession'
export function parsePublicRsvp(json: unknown, operation: string): PublicRsvp;
export function parseCreateResult(json: unknown): StoredRsvp;               // operation 'createRsvp'
/** Value from localStorage (already JSON.parsed); null when the shape is wrong. Never throws. */
export function parseStoredRsvp(json: unknown): StoredRsvp | null;

/** cancelled || Date.parse(ends_at) <= now.getTime() */
export function isSessionClosed(s: Pick<PublicSessionInfo, 'cancelled' | 'ends_at'>, now: Date): boolean;
/** Same notation as WP-20 formatWindowLocal and WP-08 format_window_local (A21). start = new Date(startsAt),
 *  end = new Date(endsAt); RangeError('invalid window') when end <= start.
 *  localDateKey(start) === localDateKey(new Date(end.getTime() - 1)):
 *    `${formatLocal(start, 'day')} ${formatLocal(start, 'time')}–${formatLocal(end, 'time')}`  -> 'za 18 jul 14:00–18:00'
 *  otherwise:
 *    `${formatLocal(start, 'dateTime')} – ${formatLocal(end, 'dateTime')}`                       -> 'za 18 jul 22:00 – zo 19 jul 04:00'
 *  En dash U+2013 (with spaces only in the two-day form). Europe/Amsterdam via time.ts. */
export function sessionWindowText(startsAt: string, endsAt: string): string;
/** null -> 'aantal plekken onbekend'; 0 -> 'geen plek meer'; 1 -> '1 plek'; n -> `${n} plekken`. */
export function seatsText(n: number | null): string;
/** own -> {'Rijdt zelf', null}; offers_ride -> {'Biedt een lift aan' (+ ` (${seatsText})` when seats !== null), null};
 *  needs_ride with rides_with pointing to an offers_ride RSVP in byId -> {'Rijdt mee met', driver.first_name};
 *  needs_ride otherwise -> {'Zoekt een lift', null}. */
export function rideLabel(r: PublicRsvp, byId: ReadonlyMap<string, PublicRsvp>): { label: string; name: string | null };

export interface CarpoolDriver { rsvp: PublicRsvp; riders: PublicRsvp[] }
export interface CarpoolView {
	organizerSeats: number | null;
	departurePoint: string | null;   // null when null, empty or only whitespace
	drivers: CarpoolDriver[];        // offers_ride in list order; riders = needs_ride with rides_with === driver id, in list order
	seekers: PublicRsvp[];           // needs_ride whose rides_with is null or not a driver in the list
	isEmpty: boolean;                // no organizerSeats, no departurePoint, no drivers, no seekers
}
export function carpoolView(session: Pick<PublicSessionInfo, 'seats_free' | 'departure_point'>, rsvps: readonly PublicRsvp[]): CarpoolView;

export const TIKKIE_PREFIX = 'https://tikkie.me/';
/** A14: url.startsWith(TIKKIE_PREFIX) && url.length > TIKKIE_PREFIX.length && new URL(url) succeeds
 *  && parsed.hostname === 'tikkie.me' -> parsed.href; otherwise null. Never throws. */
export function tikkieLink(url: string | null): string | null;
/** null, '' or whitespace -> null; otherwise the text unchanged. */
export function optionalText(s: string | null): string | null;
/** '⁨' + s + '⁩' (FSI ... PDI): bidi isolation where <bdi> is impossible, e.g. <option> text (A11). */
export function isolateText(s: string): string;

export type RsvpFormMode = 'create' | 'edit';
export interface RsvpFormValues { first_name: string; ride: Ride | ''; seats: string; rides_with: string }
export type RsvpFormField = 'first_name' | 'ride' | 'seats' | 'rides_with';
export type RsvpFormResult =
	| { ok: true; value: RsvpUpdateInput }
	| { ok: false; errors: Partial<Record<RsvpFormField, string>> };

export function countCodePoints(s: string): number;                 // [...s].length; step 9: re-exported from WP-20 session-model.ts
export function emptyRsvpForm(): RsvpFormValues;                    // { first_name: '', ride: 'own', seats: '', rides_with: '' }
/** seats: '' for null, otherwise String(n); rides_with: '' for null. */
export function rsvpFormFromRsvp(r: PublicRsvp): RsvpFormValues;
export function parseRsvpForm(values: RsvpFormValues, mode: RsvpFormMode, driverIds: ReadonlySet<string>): RsvpFormResult;
```

**Exacte teksten.**

| Sleutel | Tekst |
|---|---|
| `RSVP_MESSAGES.rate_limited` | `Er melden zich nu veel mensen tegelijk aan. Probeer het over een paar minuten opnieuw.` |
| `RSVP_MESSAGES.session_full` | `Deze sessie zit vol: naast de organisator kunnen hoogstens 30 mensen zich aanmelden.` |
| `RSVP_MESSAGES.session_closed` | `Dit kan niet meer: de sessie is geannuleerd of al voorbij.` |
| `RSVP_MESSAGES.invalid_input` | `Dat ging niet goed. Controleer je voornaam (1 tot 30 tekens) en je vervoerskeuze, en probeer het opnieuw.` |
| `RSVP_MESSAGES.invalid_token` | `Je aanmelding is niet meer gevonden. Meld je opnieuw aan als je nog mee wilt.` |
| `RSVP_MESSAGES.network` | `Geen verbinding met de server. Controleer je internet en probeer het opnieuw.` |
| `RSVP_MESSAGES.unknown` | `Er ging iets mis. Probeer het later opnieuw.` |
| `RSVP_NOTICES.created` | `Je staat op de lijst.` |
| `RSVP_NOTICES.storageFailed` | `Je staat op de lijst, maar deze browser kon je aanmelding niet onthouden. Wijzigen of afmelden lukt daardoor alleen zolang deze pagina open is.` |
| `RSVP_NOTICES.updated` | `Je wijziging is opgeslagen.` |
| `RSVP_NOTICES.deleted` | `Je bent afgemeld.` |
| `RSVP_NOTICES.alreadyDeleted` | `Je aanmelding bestond al niet meer.` |
| `RSVP_FORM_MESSAGES.nameRequired` | `Vul je voornaam in.` |
| `RSVP_FORM_MESSAGES.nameTooLong` | `Je voornaam mag hoogstens 30 tekens hebben.` |
| `RSVP_FORM_MESSAGES.nameInvalid` | `Je voornaam mag geen regeleinden of andere stuurtekens bevatten.` |
| `RSVP_FORM_MESSAGES.rideRequired` | `Kies hoe je naar de spot gaat.` |
| `RSVP_FORM_MESSAGES.seatsInvalid` | `Kies een aantal plekken van 0 tot 8, of "Weet ik nog niet".` |
| `RSVP_FORM_MESSAGES.ridesWithInvalid` | `Kies iemand die een lift aanbiedt, of "Nog niemand".` |
| `RIDE_OPTION_LABEL_NL` | `own` → `Ik rijd zelf`, `needs_ride` → `Ik zoek een lift`, `offers_ride` → `Ik kan mensen meenemen` |

**Regels voor de parsers** (`isObj(x)`: een object, niet `null`, geen array):
- `parsePublicSession(json)`:
  - `json` is een object met `session` (een object) en `rsvps` (een array), anders volgt een fout;
  - `session`: `slug`, `spot_id`, `organizer_name`, `starts_at` en `ends_at` zijn strings, `Date.parse` van `starts_at` en `ends_at` is niet `NaN`, en `Date.parse(ends_at) > Date.parse(starts_at)` (de DB eist dat ook; zo kan `sessionWindowText` op de pagina niet gooien);
  - `spot_name`, `note`, `departure_point` en `tikkie_url` zijn een string of `null`;
  - `seats_free` is `null` of een geheel getal (`Number.isInteger`);
  - `cancelled` is een boolean;
  - elke RSVP gaat via `parsePublicRsvp(item, 'getPublicSession')`;
  - het resultaat is een nieuw object met alleen de sleutels uit `PUBLIC_SESSION_KEYS` en `PUBLIC_RSVP_KEYS`.
- `parsePublicRsvp`: `id`, `first_name` en `created_at` zijn strings; `ride ∈ RIDES`; `seats_offered` is `null` of een geheel getal; `rides_with` is `null` of een string.
- `parseCreateResult`: `rsvp_id` matcht `UUID_RE` en `edit_token` matcht `EDIT_TOKEN_RE`. Het resultaat is `{ rsvp_id, edit_token }`.
- `parseStoredRsvp`: dezelfde regels als `parseCreateResult`, maar bij een fout volgt `null` in plaats van een exception.

**Regels voor `parseRsvpForm(values, mode, driverIds)`** (alle fouten tegelijk verzamelen):
1. `name = values.first_name.trim()`:
   - leeg → `first_name: nameRequired`;
   - anders `countCodePoints(name) > MAX_FIRST_NAME` → `nameTooLong`;
   - anders `/\p{Cc}/u.test(name)` → `nameInvalid`.
2. `values.ride` niet in `RIDES` → `ride: rideRequired`.
3. Alleen als `ride === 'offers_ride'`: `seats === ''` → `null`; anders moet `seats` matchen op `^[0-8]$`, anders `seats: seatsInvalid`. Bij een andere `ride` wordt `seats` genegeerd en is het resultaat `null`.
4. Alleen als `mode === 'edit'` en `ride === 'needs_ride'`: `rides_with === ''` → `null`; anders moet het in `driverIds` staan, anders `rides_with: ridesWithInvalid`. In alle andere gevallen is `rides_with` `null`.
5. Zonder fouten: `{ ok: true, value: { first_name: name, ride, seats_offered, rides_with } }`.

### `web/src/lib/rsvp-storage.ts` (exact)
```ts
import { parseStoredRsvp, rsvpStorageKey, isValidSessionSlug } from './session-view.js';
import type { StoredRsvp } from './rsvp-types.js';

// StorageLike: same type as WP-20 browser-storage.ts; step 9 re-exports that one.
// browserStorage stays here: it returns null, WP-20's returns undefined (blueprint A20).
export type StorageLike = Pick<Storage, 'getItem' | 'setItem' | 'removeItem'>;

/** globalThis.localStorage, or null when absent or when accessing it throws (SecurityError). */
export function browserStorage(): StorageLike | null {
	try {
		return globalThis.localStorage ?? null;
	} catch {
		return null;
	}
}

// Fallback for the lifetime of this page when localStorage is unavailable or full (E26).
// Lost on reload; never written anywhere else.
const memory = new Map<string, StoredRsvp>();

/** Tests only: forget the in-memory fallback. */
export function resetRsvpMemory(): void {
	memory.clear();
}

/** The stored RSVP for this slug, else the in-memory fallback, else null. A malformed value is removed. Never throws. */
export function readStoredRsvp(storage: StorageLike | null, slug: string): StoredRsvp | null {
	if (!isValidSessionSlug(slug)) return null;
	const fallback = memory.get(slug) ?? null;
	if (!storage) return fallback;
	let raw: string | null;
	try {
		raw = storage.getItem(rsvpStorageKey(slug));
	} catch {
		return fallback;
	}
	if (raw === null) return fallback;
	let parsed: StoredRsvp | null = null;
	try {
		parsed = parseStoredRsvp(JSON.parse(raw));
	} catch {
		parsed = null;
	}
	if (parsed === null) clearStoredRsvp(storage, slug);
	return parsed;
}

/** Stores exactly {rsvp_id, edit_token}. true when persisted; false when storage is unavailable or full,
 *  in which case the value is kept in memory for this page lifetime. Never throws. */
export function writeStoredRsvp(storage: StorageLike | null, slug: string, value: StoredRsvp): boolean {
	if (!isValidSessionSlug(slug)) return false;
	const clean: StoredRsvp = { rsvp_id: value.rsvp_id, edit_token: value.edit_token };
	if (!storage) {
		memory.set(slug, clean);
		return false;
	}
	try {
		storage.setItem(rsvpStorageKey(slug), JSON.stringify(clean));
		memory.delete(slug);
		return true;
	} catch {
		memory.set(slug, clean);
		return false;
	}
}

/** Removes the key and the in-memory fallback. Never throws. */
export function clearStoredRsvp(storage: StorageLike | null, slug: string): void {
	if (!isValidSessionSlug(slug)) return;
	memory.delete(slug);
	if (!storage) return;
	try {
		storage.removeItem(rsvpStorageKey(slug));
	} catch {
		// nothing to do: the key stays until the next successful removal
	}
}
```

### `web/src/lib/rsvp.ts` (exact)
```ts
import { supabase } from '#lib/supabase.js';
import type { PublicRsvp, PublicSession, RsvpInput, RsvpUpdateInput, StoredRsvp } from './rsvp-types.js';
import {
	EDIT_TOKEN_RE,
	RsvpError,
	isValidSessionSlug,
	parseCreateResult,
	parsePublicRsvp,
	parsePublicSession,
	rsvpErrorKind
} from './session-view.js';

// The only module that calls RPCs (WP-21). Anonymous and signed-in visitors use the same calls;
// nothing here reads or requires an auth session. RPCs go as POST with the arguments in the body
// (supabase-js default): an edit token never ends up in a URL (RUNBOOK §16.7). Never log tokens.

export const RPC_TIMEOUT_MS = 15_000;

interface RpcResult {
	data: unknown;
	error: unknown;
	status: number;
}

async function call(operation: string, fn: string, args: Record<string, unknown>): Promise<unknown> {
	let res: RpcResult;
	try {
		const builder = supabase.rpc(fn, args);
		// postgrest-js catches the rejected fetch (TimeoutError) and resolves with status 0 -> 'network'.
		const timed =
			typeof AbortSignal !== 'undefined' && typeof AbortSignal.timeout === 'function'
				? builder.abortSignal(AbortSignal.timeout(RPC_TIMEOUT_MS))
				: builder;
		res = (await timed) as unknown as RpcResult;
	} catch {
		throw new RsvpError('network', operation);
	}
	if (res.error) throw new RsvpError(rsvpErrorKind(res.error, res.status), operation);
	return res.data;
}

/** null for a malformed slug (no request) or an unknown session. */
export async function getPublicSession(slug: string): Promise<PublicSession | null> {
	if (!isValidSessionSlug(slug)) return null;
	const data = await call('getPublicSession', 'get_public_session', { p_slug: slug });
	return data === null ? null : parsePublicSession(data);
}

export async function createRsvp(slug: string, input: RsvpInput): Promise<StoredRsvp> {
	if (!isValidSessionSlug(slug)) throw new RsvpError('session_closed', 'createRsvp');
	const data = await call('createRsvp', 'rsvp_create', {
		p_slug: slug,
		p_first_name: input.first_name.trim(),
		p_ride: input.ride,
		p_seats_offered: input.seats_offered ?? null
	});
	return parseCreateResult(data);
}

/** Replaces all editable fields; send current values for fields that stay the same. */
export async function updateRsvp(token: string, input: RsvpUpdateInput): Promise<PublicRsvp> {
	if (!EDIT_TOKEN_RE.test(token)) throw new RsvpError('invalid_token', 'updateRsvp');
	const data = await call('updateRsvp', 'rsvp_update', {
		p_edit_token: token,
		p_first_name: input.first_name.trim(),
		p_ride: input.ride,
		p_seats_offered: input.seats_offered ?? null,
		p_rides_with: input.rides_with ?? null
	});
	return parsePublicRsvp(data, 'updateRsvp');
}

/** true: removed; false: unknown or malformed token (already removed). */
export async function deleteRsvp(token: string): Promise<boolean> {
	if (!EDIT_TOKEN_RE.test(token)) return false;
	const data = await call('deleteRsvp', 'rsvp_delete', { p_edit_token: token });
	if (typeof data !== 'boolean') throw new RsvpError('unknown', 'deleteRsvp');
	return data;
}
```
Alle vier de parameters (resp. vijf) gaan altijd mee, ook als ze `null` zijn. `JSON.stringify` laat een sleutel met `undefined` weg, en dan vindt PostgREST de functie niet (`PGRST202`). Vandaar `?? null`.

Lukt de cast naar `RpcResult` niet zonder `as unknown as` door de generics van supabase-js, dan blijft die dubbele cast staan; dat is geen ontwerpwijziging.

De timeout geldt per RPC. Een `rsvp_create` die na 15 seconden wordt afgebroken, kan op de server toch zijn gelukt; dat is hetzelfde geval als E25 (R5).

### `web/src/lib/public-session-data.ts`
```ts
import { getEvaluations } from '#lib/data.js';
import { getPublicSession } from '#lib/rsvp.js';
import { isValidSessionSlug } from './session-view.js';
import { floorHour } from './time.js';
import type { Evaluation } from './types.js';
import type { PublicRsvp, PublicSessionInfo } from './rsvp-types.js';

export type PublicSessionPageData =
	| {
			kind: 'ok';
			now: string;              // now.toISOString()
			slug: string;
			session: PublicSessionInfo;
			rsvps: PublicRsvp[];
			evaluations: Evaluation[] | null; // null: the verdict could not be loaded (A3)
	  }
	| { kind: 'not_found'; now: string; slug: string }
	| { kind: 'error'; now: string; slug: string };

export async function loadPublicSessionPage(slug: string, now: Date): Promise<PublicSessionPageData>;
```
Gedrag:
1. `!isValidSessionSlug(slug)` → `{ kind: 'not_found' }`, zonder aanroep.
2. `ps = await getPublicSession(slug)`. Gooit die (wat dan ook), dan `console.warn('session page load failed')` (zonder argumenten) en `{ kind: 'error' }`. Bij `null` volgt `{ kind: 'not_found' }`.
3. `from = floorHour(new Date(ps.session.starts_at))` en `to = new Date(ps.session.ends_at)`. Dan `evaluations = await getEvaluations(ps.session.spot_id, from, to)` in een eigen `try`. Gooit die, dan `console.warn('session verdict load failed')` (zonder argumenten) en `evaluations = null`.
4. `{ kind: 'ok', now: now.toISOString(), slug, session: ps.session, rsvps: ps.rsvps, evaluations }`.

### `web/src/routes/s/[slug]/+page.ts` (exact)
```ts
import { loadPublicSessionPage } from '#lib/public-session-data.js';
import type { PageLoad } from './$types';

export const load: PageLoad = ({ params }) => loadPublicSessionPage(params.slug, new Date());
```

### `web/src/routes/s/[slug]/+page.svelte`
Script:
- imports: `refreshAll` uit `$app/navigation`; `Attribution`, `Freshness`, `HourVerdict`, `SessionParticipants` en `RsvpPanel`; `browserStorage`, `readStoredRsvp` en `clearStoredRsvp` uit `#lib/rsvp-storage.js`; `isSessionClosed`, `optionalText`, `tikkieLink` en `sessionWindowText` uit `#lib/session-view.js`; `SESSION_RETENTION_DAYS` uit `#lib/rsvp-types.js`; `formatDateKey` uit `#lib/time.js`; `groupByLocalDay`, `latestEvaluatedAt` en `shouldRefreshOnResume` uit `#lib/view.js`; de types `PublicSession` en `StoredRsvp`. **Niet** `#lib/auth.js`, `#lib/supabase.js` of `#lib/rsvp.js` (die laatste gebruikt alleen `RsvpPanel`).
- `let { data }: PageProps = $props();`
- Overschrijfbare deriveds (A8):
  - `let session = $derived(data.kind === 'ok' ? data.session : null);`
  - `let rsvps = $derived(data.kind === 'ok' ? data.rsvps : []);`
  - `let gone = $derived(data.kind !== 'ok');` (wordt `true` als een verversing `null` geeft).
- `let stored = $state<StoredRsvp | null>(null)`, `let storageReady = $state(false)`, en een gewone (niet-reactieve) `let checkedSlug: string | null = null`.
- `let now = $derived(new Date(data.now));` (overschrijfbaar, A5; een nieuwe load zet hem terug op `data.now`)
- `const closed = $derived(session !== null && isSessionClosed(session, now));`
- `const ended = $derived(session !== null && !session.cancelled && closed);`
- `const groups = $derived(data.kind === 'ok' && data.evaluations ? groupByLocalDay(data.evaluations) : []);`
- `const latest = $derived(data.kind === 'ok' && data.evaluations ? latestEvaluatedAt(data.evaluations) : null);`
- `const spotName = $derived(session?.spot_name ?? 'Onbekende spot');`
- `const tikkie = $derived(tikkieLink(session?.tikkie_url ?? null));` (een `href` of `null`)
- `const note = $derived(optionalText(session?.note ?? null));`
- `$effect` (opslag, A7):
  ```ts
  $effect(() => {
  	const d = data;
  	const storage = browserStorage();
  	if (d.kind === 'ok') {
  		let s = readStoredRsvp(storage, d.slug);
  		if (checkedSlug !== d.slug) {
  			checkedSlug = d.slug;
  			if (s !== null && !d.rsvps.some((r) => r.id === s!.rsvp_id)) {
  				clearStoredRsvp(storage, d.slug);
  				s = null;
  			}
  		}
  		stored = s;
  	} else {
  		if (d.kind === 'not_found') clearStoredRsvp(storage, d.slug);
  		stored = null;
  	}
  	storageReady = true;
  });
  ```
- `function applyRefresh(fresh: PublicSession | null) { now = new Date(); if (fresh) { session = fresh.session; rsvps = fresh.rsvps; } else { gone = true; } }`
- `$effect` (klok, A5): sluit het formulier vanzelf na `ends_at`.
  ```ts
  $effect(() => {
  	if (!session || closed) return;
  	const ms = Date.parse(session.ends_at) - Date.now();
  	if (ms > 2_147_483_647) return; // beyond the setTimeout range; a later load or resume handles it
  	const id = setTimeout(() => {
  		now = new Date();
  	}, Math.max(0, ms) + 1_000);
  	return () => clearTimeout(id);
  });
  ```
  De marge van 1 seconde voorkomt dat een timer die een fractie te vroeg afgaat, `now` net vóór `ends_at` zet; `closed` blijft dan `false` en de effect zou niet opnieuw lopen.
- `onMount`: een `visibilitychange`-listener zoals op de spotpagina: `void refreshAll()` als `document.visibilityState === 'visible' && shouldRefreshOnResume(data.now, Date.now())`. De cleanup verwijdert de listener.

Markup (in deze volgorde):
```svelte
<svelte:head>
	<meta name="robots" content="noindex" />
	<title>{data.kind === 'ok' ? `Kitesessie ${spotName}` : data.kind === 'not_found' ? 'Sessie niet gevonden' : 'Sessie'} · Shakka</title>
</svelte:head>

{#if data.kind === 'not_found' || (gone && data.kind === 'ok')}
	<h1>Sessie niet gevonden</h1>
	<p>Deze sessie bestaat niet (meer). Sessies verdwijnen {SESSION_RETENTION_DAYS} dagen na afloop.</p>
	<p><a href="/">Naar alle spots</a></p>
{:else if data.kind === 'error'}
	<h1>Sessie</h1>
	<div class="banner" role="alert">
		<p>De sessie kon niet worden geladen. Controleer je verbinding.</p>
		<button type="button" onclick={() => refreshAll()}>Opnieuw proberen</button>
	</div>
{:else if session}
	<h1>Kitesessie: {spotName}</h1>
	<p class="session-when">{sessionWindowText(session.starts_at, session.ends_at)}</p>
	<p class="session-organizer">Georganiseerd door <bdi>{session.organizer_name}</bdi></p>
	{#if session.cancelled}
		<div class="banner warning" role="alert">
			<p><strong>Deze sessie is geannuleerd.</strong> Aanmelden kan niet meer. Afmelden kan nog wel.</p>
		</div>
	{:else if ended}
		<div class="banner" role="note"><p>Deze sessie is voorbij. Aanmelden kan niet meer.</p></div>
	{/if}
	<p><a href="/spot/{encodeURIComponent(session.spot_id)}">Naar de spotpagina van {spotName}</a></p>
	{#if note}
		<section class="session-note"><h2>Notitie</h2><p class="prewrap"><bdi>{note}</bdi></p></section>
	{/if}
	{#if tikkie}
		<p class="session-tikkie">
			Kosten delen: <a href={tikkie} target="_blank" rel="noopener noreferrer">Open betaalverzoek</a>
			<span class="muted">(link naar tikkie.me)</span>
		</p>
	{/if}

	{#if storageReady}
		{#key data.slug}
			<RsvpPanel slug={data.slug} {rsvps} {closed} bind:stored onrefresh={applyRefresh} />
		{/key}
	{/if}

	<SessionParticipants {session} {rsvps} myRsvpId={stored?.rsvp_id ?? null} />

	<section class="session-hours" aria-labelledby="oordeel">
		<h2 id="oordeel">Oordeel per uur</h2>
		<p class="muted">Met de standaardgrenzen van de spot, niet met persoonlijke instellingen.</p>
		{#if !closed}<Freshness {latest} {now} showUpdated />{/if}
		{#if data.evaluations === null}
			<p class="no-data">Het oordeel kon niet worden geladen.</p>
		{:else if groups.length === 0}
			<p class="no-data">Er is nog geen oordeel voor dit tijdvenster.</p>
		{:else}
			{#each groups as g (g.dateKey)}
				{#if groups.length > 1}<h3>{formatDateKey(g.dateKey, 'day')}</h3>{/if}
				<ol class="hours">
					{#each g.hours as e (e.valid_at)}<li><HourVerdict evaluation={e} /></li>{/each}
				</ol>
			{/each}
		{/if}
	</section>

	<section class="sources"><h2>Bronnen</h2><Attribution /></section>
{/if}
```
De `meta` staat buiten elke tak, dus ook bij `not_found` en `error` geldt `noindex`.

### `web/src/lib/components/SessionParticipants.svelte`
Props: `{ session: PublicSessionInfo; rsvps: PublicRsvp[]; myRsvpId: string | null }`. Afgeleid: `byId = new Map(rsvps.map((r) => [r.id, r]))` en `carpool = carpoolView(session, rsvps)`.
```svelte
<section class="participants" aria-labelledby="deelnemers">
	<h2 id="deelnemers">Deelnemers ({rsvps.length + 1})</h2>
	<ul class="participant-list">
		<li class="organizer"><bdi>{session.organizer_name}</bdi> <span class="muted">organisator</span></li>
		{#each rsvps as r (r.id)}
			{@const ride = rideLabel(r, byId)}
			<li data-rsvp={r.id}>
				<bdi>{r.first_name}</bdi>{#if r.id === myRsvpId} <span class="muted">(jij)</span>{/if}
				<span class="ride"> · {ride.label}{#if ride.name} <bdi>{ride.name}</bdi>{/if}</span>
			</li>
		{/each}
	</ul>
</section>
<section class="carpool" aria-labelledby="carpool">
	<h2 id="carpool">Carpool</h2>
	{#if carpool.organizerSeats !== null}
		<p>Vrije plekken bij <bdi>{session.organizer_name}</bdi>: {carpool.organizerSeats}</p>
	{/if}
	{#if carpool.departurePoint}<p>Vertrekpunt: <bdi>{carpool.departurePoint}</bdi></p>{/if}
	{#if carpool.drivers.length}
		<h3>Biedt een lift aan</h3>
		<ul class="carpool-drivers">
			{#each carpool.drivers as d (d.rsvp.id)}
				<li data-driver={d.rsvp.id}>
					<bdi>{d.rsvp.first_name}</bdi> · {seatsText(d.rsvp.seats_offered)}{#if d.riders.length} · meerijders: {#each d.riders as m, i (m.id)}{#if i > 0}, {/if}<bdi>{m.first_name}</bdi>{/each}{/if}
				</li>
			{/each}
		</ul>
	{/if}
	{#if carpool.seekers.length}
		<h3>Zoekt een lift</h3>
		<ul class="carpool-seekers">
			{#each carpool.seekers as s (s.id)}<li data-seeker={s.id}><bdi>{s.first_name}</bdi></li>{/each}
		</ul>
	{/if}
	{#if carpool.isEmpty}<p class="muted">Nog niemand heeft iets over vervoer doorgegeven.</p>{/if}
</section>
```

### `web/src/lib/components/RsvpForm.svelte`
Props: `{ mode: RsvpFormMode; initial: RsvpFormValues; drivers: PublicRsvp[]; busy: boolean; onsubmit: (value: RsvpUpdateInput) => void; oncancel?: () => void }`.

Toestand:
- `let values = $state<RsvpFormValues>(untrack(() => ({ ...initial })))`, met hetzelfde `untrack`-patroon als `AlertRuleForm`;
- `let errors = $state<Partial<Record<RsvpFormField, string>>>({})`;
- `const prefix = mode === 'create' ? 'rsvp' : 'rsvp-edit'`, voor unieke id's.

`submit(e)`:
1. `e.preventDefault()`. Is `busy` waar, doe dan niets.
2. `const r = parseRsvpForm(values, mode, new Set(drivers.map((d) => d.id)))`.
3. Bij `!r.ok`: zet `errors = r.errors` en stop. Er volgt geen `onsubmit`.
4. Anders: `errors = {}` en `onsubmit(r.value)`.

Markup: `<form novalidate onsubmit={submit} class="rsvp-form">` met:
- `.form-field`:
  - `<label for="{prefix}-name">Voornaam</label>`;
  - `<input id="{prefix}-name" name="first_name" type="text" autocomplete="given-name" bind:value={values.first_name} aria-invalid={errors.first_name ? 'true' : undefined} aria-describedby={errors.first_name ? `${prefix}-name-error` : undefined} />`;
  - bij een fout: `<p id="{prefix}-name-error" class="error">{errors.first_name}</p>`.
- `<fieldset><legend>Vervoer</legend>`: per `ride` in `RIDES` een `<input type="radio" id="{prefix}-ride-{ride}" name="{prefix}-ride" value={ride} bind:group={values.ride} />` met `<label for=…>{RIDE_OPTION_LABEL_NL[ride]}</label>`, en de fout `ride` als `<p class="error">`.
- Als `values.ride === 'offers_ride'`: `<label for="{prefix}-seats">Plekken over in je auto</label>` en een `<select id="{prefix}-seats" bind:value={values.seats}>` met de opties:
  - `''` → `Weet ik nog niet`;
  - `'0'` → `Geen (auto zit vol)`;
  - `'1'` → `1 plek`;
  - `'2'` t/m `'8'` → `n plekken`.

  Plus de fout `seats`.
- Als `mode === 'edit' && values.ride === 'needs_ride'`: `<label for="{prefix}-rides-with">Rijd mee met</label>` en een `<select id="{prefix}-rides-with" bind:value={values.rides_with}>` met `''` → `Nog niemand: ik zoek een lift`, plus per driver `<option value={d.id}>{isolateText(d.first_name)}</option>` (A11, review N-7). Plus de fout `rides_with`.
- Als `mode === 'create' && values.ride === 'needs_ride'`: `<p class="hint">Rijdt iemand al met een lege plek? Na het aanmelden kun je via Wijzigen kiezen met wie je meerijdt.</p>`
- Knoppen:
  - `create`: `<button type="submit" disabled={busy}>{busy ? 'Bezig…' : 'Ik ook'}</button>`;
  - `edit`: `<button type="submit" disabled={busy}>{busy ? 'Bezig…' : 'Opslaan'}</button>` en `<button type="button" disabled={busy} onclick={() => oncancel?.()}>Annuleren</button>`.

### `web/src/lib/components/RsvpPanel.svelte`
Props: `{ slug: string; rsvps: PublicRsvp[]; closed: boolean; stored: StoredRsvp | null (= $bindable()); onrefresh: (fresh: PublicSession | null) => void }`.

Toestand:
- `mode = $state<'view' | 'edit' | 'confirm_delete'>('view')`;
- `busy = $state(false)`;
- `error = $state<string | null>(null)`;
- `notice = $state<string | null>(null)`;
- `serverClosed = $state(false)` (A5; wordt nooit terug op `false` gezet; een andere slug geeft een nieuw paneel via `{#key}`).

Afgeleid:
- `isClosed = $derived(closed || serverClosed)`;
- `me = $derived(stored ? rsvps.find((r) => r.id === stored!.rsvp_id) ?? null : null)`;
- `byId = $derived(new Map(rsvps.map((r) => [r.id, r])))`;
- `drivers = $derived(rsvps.filter((r) => r.ride === 'offers_ride' && r.id !== stored?.rsvp_id))`.

Functies (allemaal met `busy = true` in een `try` en `busy = false` in `finally`; aan het begin `error = null; notice = null`; geen enkele `console`-regel bevat een token, naam of fouttekst):
- `kindOf(e: unknown): RsvpErrorKind`: `e instanceof RsvpError ? e.kind : 'unknown'`.
- `refresh()`: `try { const fresh = await getPublicSession(slug); if (fresh === null) { clearStoredRsvp(browserStorage(), slug); stored = null; } onrefresh(fresh); } catch { console.warn('session refresh failed'); }`.
- `create(value)`:
  1. `const existing = readStoredRsvp(browserStorage(), slug)`. Is er al een sleutel, dan `stored = existing`, `await refresh()` en stoppen (A15).
  2. `const res = await createRsvp(slug, { first_name: value.first_name, ride: value.ride, seats_offered: value.seats_offered })`.
  3. `const ok = writeStoredRsvp(browserStorage(), slug, res); stored = res; notice = ok ? RSVP_NOTICES.created : RSVP_NOTICES.storageFailed; await refresh();`.
  4. `catch (e)`: `const k = kindOf(e); error = RSVP_MESSAGES[k];`. Bij `k === 'session_closed'` ook `serverClosed = true`. Daarna `await refresh()` als `k` `session_closed` of `session_full` is.
- `save(value)` (modus `edit`, vereist `stored`):
  1. `await updateRsvp(stored.edit_token, value); mode = 'view'; notice = RSVP_NOTICES.updated; await refresh();`.
  2. `catch (e)`: `k = kindOf(e)`.
     - Bij `invalid_token`: `clearStoredRsvp(...)`, `stored = null`, `mode = 'view'`, `error = RSVP_MESSAGES.invalid_token`, `await refresh()`.
     - Bij `session_closed`: `serverClosed = true`, `mode = 'view'`, `error = RSVP_MESSAGES.session_closed`, `await refresh()`.
     - Anders: `error = RSVP_MESSAGES[k]` (de modus blijft `edit`).
- `remove()` (vereist `stored`):
  1. `const removed = await deleteRsvp(stored.edit_token); clearStoredRsvp(browserStorage(), slug); stored = null; mode = 'view'; notice = removed ? RSVP_NOTICES.deleted : RSVP_NOTICES.alreadyDeleted; await refresh();`.
  2. `catch (e)`: `error = RSVP_MESSAGES[kindOf(e)]; mode = 'view';`. De sleutel blijft staan.

Markup:
```svelte
{#if stored || !isClosed || notice || error}
<section class="rsvp-panel" aria-labelledby={stored || !isClosed ? 'rsvp-heading' : undefined}>
	{#if stored}
		<h2 id="rsvp-heading">Jij gaat</h2>
		{#if me}
			{@const ride = rideLabel(me, byId)}
			<p>Aangemeld als <bdi>{me.first_name}</bdi> · {ride.label}{#if ride.name} <bdi>{ride.name}</bdi>{/if}</p>
		{/if}
		<p class="muted">Wijzigen of afmelden kan alleen in deze browser op dit apparaat.</p>
		{#if mode === 'edit' && me && !isClosed}
			<RsvpForm mode="edit" initial={rsvpFormFromRsvp(me)} {drivers} {busy} onsubmit={save} oncancel={() => (mode = 'view')} />
		{:else if mode === 'confirm_delete'}
			<p>Weet je zeker dat je je wilt afmelden?</p>
			<button type="button" disabled={busy} onclick={remove}>Ja, afmelden</button>
			<button type="button" disabled={busy} onclick={() => (mode = 'view')}>Nee</button>
		{:else}
			{#if me && !isClosed}<button type="button" disabled={busy} onclick={() => (mode = 'edit')}>Wijzigen</button>{/if}
			<button type="button" disabled={busy} onclick={() => (mode = 'confirm_delete')}>Afmelden</button>
		{/if}
	{:else if !isClosed}
		<h2 id="rsvp-heading">Ga je mee?</h2>
		<p>Tik "Ik ook" met alleen je voornaam. Je hebt geen account nodig.</p>
		<RsvpForm mode="create" initial={emptyRsvpForm()} drivers={[]} {busy} onsubmit={create} />
		<p class="hint" id="rsvp-privacy">Alleen je voornaam en je vervoerskeuze worden opgeslagen, tot {SESSION_RETENTION_DAYS} dagen na de sessie. Iedereen met deze link kan ze zien. Wijzigen of afmelden kan later alleen in deze browser op dit apparaat.</p>
	{/if}
	{#if notice}<p class="notice-ok" role="status">{notice}</p>{/if}
	{#if error}<p class="error" role="alert">{error}</p>{/if}
</section>
{/if}
```
Bij `!stored && isClosed` rendert de sectie alleen een eventuele `notice` of `error`, bijvoorbeeld "Je bent afgemeld." na het afmelden op een gesloten sessie, of de melding `session_closed`. Er is dan geen kop, dus ook geen `aria-labelledby` (review N-12). Zijn beide leeg, dan rendert de `<section>` niet.

### Stijl (`web/src/app.css`, toevoegen aan het eind)
```css
/* WP-21: public session page */
.session-when { font-weight: 600; margin: 0.25rem 0; }
.participant-list, .carpool-drivers, .carpool-seekers { padding-left: 1.25rem; }
.participant-list li, .carpool-drivers li, .carpool-seekers li { overflow-wrap: anywhere; margin: 0.125rem 0; }
.rsvp-panel { margin: 1rem 0; padding: 0.75rem; border: 1px solid #ddd; border-radius: 0.25rem; }
.rsvp-panel h2 { font-size: 1.1rem; margin: 0 0 0.25rem; }
.rsvp-panel button + button { margin-left: 0.5rem; }
.notice-ok { color: #1b7f3b; }
.session-hours h3 { font-size: 1rem; margin: 1rem 0 0.25rem; }
```

### `web/test/user-tables.test.ts` (alleen deze test vervangen)
```ts
// Anonymous session RPCs live only in lib/rsvp.ts (WP-21). A later module that needs an RPC is added here.
const RPC_FILES = ['lib/rsvp.ts'];
it('.rpc( occurs only in the allowed modules', () => {
	const hits = [...text].filter(([, t]) => /\.rpc\(/.test(t)).map(([f]) => f).sort();
	expect(hits).toEqual([...RPC_FILES].sort());
});
```
Ze vervangt `it('no file uses .rpc(', …)`. De constante staat boven de `describe`.

### `docs/RUNBOOK.md`, §16 (toevoegen)
8. **Publieke sessiepagina (vanaf WP-21).**
   - `/s/<slug>` werkt zonder account. Je ziet de sessie, de deelnemers, de carpool en het oordeel per uur, en je meldt je aan met alleen een voornaam.
   - De edit-token staat alleen in de browser van de bezoeker (`localStorage`, sleutel `shakka:rsvp:<slug>`). Wie een andere browser of de in-app-browser van WhatsApp gebruikt, of de websitedata wist, kan zich daar niet meer afmelden.
   - Een RSVP verwijderen voor iemand gaat via de SQL-editor (punt 5): zoek eerst de id met `select r.id, r.first_name from public.rsvps r join public.sessions s on s.id = r.session_id where s.slug = '<slug>';`.
   - De pagina heeft `noindex`. Zoekmachines nemen hem niet op, maar iedereen met de link kan de voornamen zien.
9. **Controle (WP-21 AC-7).**
   - Zonder WP-20 maak je een testsessie in de SQL-editor:
     ```sql
     insert into public.sessions (slug, spot_id, organizer_id, organizer_name, starts_at, ends_at, seats_free, departure_point)
     values ('<eigen slug, 10-64 tekens A-Z a-z 0-9 _ ->', '<spot-id>', '<jouw user-id>', 'Lars',
             date_trunc('hour', now()) + interval '1 day', date_trunc('hour', now()) + interval '1 day 4 hours', 3, 'Utrecht CS');
     ```
   - Open `https://<project>.pages.dev/s/<slug>` op een telefoon zonder in te loggen, bijvoorbeeld via een link in WhatsApp. Meld je aan, wijzig je aanmelding (bijvoorbeeld naar "Ik kan mensen meenemen") en meld je af.
   - Controleer in de SQL-editor dat de RSVP weg is.
   - Ruim de testsessie op met `delete from public.sessions where slug = '<slug>';`.

### Consistentie met afhankelijke WP's
- **WP-19.**
  - De RPC-namen, parameternamen en antwoordvormen zijn exact die uit de migratie; de contracttest leest ze daaruit.
  - Fouten: `code === 'PT400'` met `message` als code (A2 van WP-19). Een onbekende slug geeft bij `rsvp_create` `session_closed` (WP-19 A3). Bij `rsvp_delete` geeft een onbekende token `false` (A10).
  - Afmelden blijft mogelijk op een gesloten sessie (A10). Een gesloten sessie betekent `cancelled` of `ends_at <= now` (A11).
  - De carpoolbetekenis volgt A6: "zoekt een lift" is `needs_ride` zonder geldige `rides_with`.
  - De Tikkie-host wordt getoond (R5); strenger dan de DB-CHECK (alleen `https://tikkie.me/...`, A14).
  - Bij `rate_limited` zegt de melding "over een paar minuten" (review N-7). Namen staan in `<bdi>` (N-7).
  - De token gaat alleen via POST (N-8).
- **WP-14.** Hergebruikt worden `HourVerdict` (props `{ evaluation }`, ongewijzigd), `Freshness`, `getEvaluations`, `groupByLocalDay`, `latestEvaluatedAt`, `shouldRefreshOnResume`, `formatDateKey`, `formatLocal` en `Attribution`. Verder:
  - het patroon met een universele load en een gediscrimineerde unie;
  - Nederlandse foutteksten;
  - geen `{@html}`;
  - de `$app/navigation`-mock in de tests.
- **WP-13.**
  - Cloudflare levert deep links als `/s/<slug>` uit via de SPA-fallback (er is geen `404.html`).
  - De service worker laat POST-verzoeken en Supabase ongemoeid. Offline valt de pagina terug op de shell, de load faalt en de pagina toont de foutmelding met "Opnieuw proberen".
  - `Attribution` staat in de footer van de layout en ook volledig op de pagina.
- **WP-16.** `user-data.ts` blijft ongewijzigd en de enige schrijfmodule voor gebruikerstabellen. Anonieme RPC's staan in `rsvp.ts` (A1), en `user-tables.test.ts` legt dat vast.
- **WP-20 (parallel, merget eerst, A20).**
  - Stap 1 tot en met 8 hebben geen WP-20-code nodig. Het URL-contract `/s/{slug}` en de slugvorm zijn gelijk (WP-20 `SESSION_SLUG_RE` heeft dezelfde naam en dezelfde `source` als die van WP-21).
  - Gecontroleerd in de WP-20-blueprint revisie 2 (`.claude/worktrees/WP-20/docs/wp/WP-20/blueprint.md`, r. 100, 104, 191–208, 265 en 296–309):
    - `#lib/session-model.ts`: `SESSION_SLUG_RE = /^[A-Za-z0-9_-]{10,64}$/`, `isValidSessionSlug(slug)` (`SESSION_SLUG_RE.test(slug)`) en `countCodePoints(s)` (`[...s].length`), met precies dezelfde namen als in WP-21. Daarnaast `TIKKIE_URL_RE = /^https:\/\/tikkie\.me\/\S+$/`, `isTikkieUrl(s)` en `safeTikkieLink(url): { href: string; host: string } | null`;
    - `#lib/time.ts`: `formatWindowLocal(start: Date, end: Date)` met `za 18 jul 14:00–18:00` / `za 18 jul 22:00 – zo 19 jul 02:00` en `RangeError` bij `start >= end`;
    - `#lib/browser-storage.ts` (eigen module, niet `local-prefs.ts`): `StorageLike = Pick<Storage, 'getItem' | 'setItem' | 'removeItem'>` en `browserStorage(): StorageLike | undefined`. Die geeft `undefined`, de WP-21-versie `null`; daarom blijft de WP-21-`browserStorage` staan (A20).

    WP-21 bouwt de eigen varianten met hetzelfde gedrag, zodat stap 9 ze kan vervangen (behalve `browserStorage`).
  - WP-20 laat de test "no file uses .rpc(" in `user-tables.test.ts` staan voor WP-21 (WP-20 "Gevolgen", WP-21). WP-21 vervangt alleen die test.
  - WP-20 vraagt `/mijn-sessies` geen RSVP-gegevens op (WP-20 A13) en linkt naar `/s/{slug}`.
  - Tikkie: WP-21 toont alleen `https://tikkie.me/...` (A14). De orchestrator brengt dezelfde regel in de validatie van WP-20.

### Gevolgen voor latere WP's
- **WP-20:**
  - gebruikt WP-20 later toch een RPC (bijv. het aantal deelnemers op `/mijn-sessies`), dan importeert het `getPublicSession` uit `#lib/rsvp.js`, of komt zijn module in `RPC_FILES` in `user-tables.test.ts`;
  - de Tikkie-validatie van het sessieformulier wordt `https://tikkie.me/...` (orchestrator, review N-6).
- **WP-22:** de moderatie-RPC voor de organisator (WP-19 R1) zou in `rsvp.ts` komen of in een eigen module in `RPC_FILES`. De UI-melding bij `rate_limited` blijft gelijk.
- **WP-23:**
  - `docs/PRIVACY.md` en `/privacy` noemen de `localStorage`-sleutel `shakka:rsvp:{slug}` (`rsvp_id` plus edit-token). Die verdwijnt bij afmelden, en als de sessie bij een volgend bezoek niet meer bestaat; anders blijft hij in de browser staan. Voorstel voor WP-23: een opruimronde over alle `shakka:rsvp:*`-sleutels bij het starten van de app;
  - in `web/static/_headers` komt `X-Robots-Tag: noindex` voor `/s/*` (A18);
  - de CSP blijft gelijk: deze WP voegt geen origin toe;
  - axe op `/s/[slug]` kan `publicSessionPageData()` uit `test/fixtures/public-session.ts` gebruiken.
- **Opruimpunt na de merge van WP-20 en WP-21:**
  - `browserStorage` staat zeker dubbel: WP-20 `#lib/browser-storage.ts` geeft `undefined`, WP-21 `rsvp-storage.ts` geeft `null` (A20). Samenvoegen betekent `rsvp-storage.ts` laten werken met `StorageLike | undefined` en de bijbehorende tests in `rsvp-storage.test.ts` aanpassen. Dat doet een volgende WP of de orchestrator, uiterlijk WP-23;
  - blijft er na stap 9 nog een helper dubbel (omdat het gedrag van WP-20 toch afweek en de builder dat in `deviations.md` noteerde), dan voegt dezelfde opruimronde ze samen: één slugregex, één vensterformatter, één Tikkie-regel.

## Edge cases

| # | Geval | Gedrag |
|---|---|---|
| E1 | `/s/kort` of `/s/bad%20slug!` (de slug past niet op `SESSION_SLUG_RE`) | `not_found` zonder RPC. Een eventuele sleutel voor die slug wordt niet aangeraakt (ongeldige slug). |
| E2 | Onbekende slug (`get_public_session` geeft `null`) | "Sessie niet gevonden". `shakka:rsvp:{slug}` wordt verwijderd. |
| E3 | Netwerkfout bij het laden | `error`: banner met "Opnieuw proberen" (`refreshAll`). Eén `console.warn` zonder details. |
| E4 | `get_public_session` geeft een misvormd antwoord (verkeerde types, onbekende `ride`) | `parsePublicSession` gooit `RsvpError('unknown')`, met als gevolg `error`. |
| E5 | Het antwoord bevat extra sleutels (bijv. `edit_token_hash` door een serverfout) | De parser neemt alleen de bekende sleutels over; niets ervan komt in de UI. |
| E6 | Evaluaties laden faalt | De pagina werkt verder, met "Het oordeel kon niet worden geladen." en één `console.warn` zonder details. |
| E7 | Window buiten de horizon van de forecast, of in het verleden zonder rijen | "Er is nog geen oordeel voor dit tijdvenster." |
| E8 | `starts_at` 12:30Z, `ends_at` 15:30Z | Uren 12:00Z, 13:00Z, 14:00Z en 15:00Z (`gte 12:00Z`, `lt 15:30Z`). |
| E9 | Window over middernacht (22:00–04:00 lokaal) | `za 18 jul 22:00 – zo 19 jul 04:00`. Uren gegroepeerd met een dagkop. |
| E10 | Window eindigt precies om lokale middernacht | Vorm voor één dag: `za 18 jul 22:00–00:00`. |
| E11 | Wintertijdnacht 25-10-2026, `00:00Z`–`03:00Z` | `zo 25 okt 02:00–04:00`. Twee uren tonen `02:00` (het uur komt twee keer voor); geen fout. |
| E12 | Geannuleerde sessie | Banner "Deze sessie is geannuleerd." (`role="alert"`). Geen formulier, geen Wijzigen, geen versheid. Afmelden met een token blijft mogelijk. |
| E13 | Afgelopen sessie (`ends_at <= now`) | Banner "Deze sessie is voorbij." (`role="note"`). Verder als E12. |
| E14 | Sessie begonnen maar niet voorbij | Open; aanmelden mogelijk (WP-19 A11). |
| E15 | Klok van het apparaat loopt voor of achter | Hooguit een verborgen of zichtbaar formulier op het randje. Antwoordt de server `session_closed`, dan: de melding, `serverClosed = true` (formulier en Wijzigen weg, Afmelden blijft), een verversing en `now = new Date()`. Een tweede poging is niet meer mogelijk. De banner "voorbij" volgt alleen als de klok van het apparaat dat ook vindt. |
| E16 | Voornaam `"  Sanne  "` | `rsvp_create` met `p_first_name: 'Sanne'`. |
| E17 | Lege voornaam, 31 tekens, of een regeleinde | Veldfout, 0 RPC's. 30 emoji (60 UTF-16-eenheden) is geldig (code points). |
| E18 | Voornaam met U+202E | Toegestaan (geen `Cc`). Gerenderd in `<bdi>`, dus de tekst eromheen draait niet om. |
| E19 | Naam met `<script>` | Svelte escapet; nergens `{@html}`. |
| E20 | Dubbelklik op "Ik ook" | Knop `disabled` tijdens `busy`; precies één `createRsvp`. |
| E21 | Tweede tabblad heeft zich intussen aangemeld | Opslag opnieuw lezen vóór de create, geen tweede RSVP (A15). |
| E22 | `rate_limited`, `session_full`, `session_closed`, `invalid_input` | De eigen melding (exacte tekst); bij `session_full` en `session_closed` ook een verversing. Er komt nooit een code of servertekst in beeld. |
| E23 | Onbekende fout (`PGRST202` na een niet-gepushte migratie, 401 door een verlopen JWT van een ingelogde bezoeker, 500) | `RSVP_MESSAGES.unknown`. |
| E24 | Netwerkfout bij een mutatie (status 0, of `rpc` gooit) | `RSVP_MESSAGES.network`; de sleutel en de toestand blijven ongewijzigd. |
| E25 | Create geslaagd, maar het antwoord ging verloren (netwerk) | Melding `network`. De RSVP bestaat zonder token op dit apparaat; een nieuwe poging geeft een tweede RSVP. Dit is geaccepteerd (R5). |
| E26 | `localStorage` niet beschikbaar of vol (privémodus, cookies geblokkeerd) | Aanmelden lukt. `notice = storageFailed`. De sleutel staat in de geheugenfallback van `rsvp-storage.ts`, dus wijzigen en afmelden werken zolang de pagina niet herladen wordt, ook na een `refreshAll()` bij hervatten of een navigatie binnen de app. |
| E27 | Misvormde JSON of een verkeerde vorm onder `shakka:rsvp:{slug}` | Behandeld als geen sleutel; de sleutel wordt verwijderd. |
| E28 | Opgeslagen `rsvp_id` staat niet in de lijst bij de eerste load | De sleutel wordt verwijderd en het formulier verschijnt (A7). |
| E29 | Opgeslagen sleutel plus een gesloten sessie | "Jij gaat" met alleen Afmelden. |
| E30 | Create gelukt, verversing faalt | "Jij gaat" zonder naamregel (`me` is `null`), alleen Afmelden. Eén `console.warn('session refresh failed')`. |
| E31 | `rsvp_update` geeft `invalid_token` | De sleutel wordt verwijderd, met de melding `invalid_token`. Het formulier verschijnt weer (bij een open sessie). |
| E32 | `rsvp_delete` geeft `false` | De sleutel wordt verwijderd, met de notice `alreadyDeleted`. |
| E33 | Meerijden met jezelf of met iemand die geen lift aanbiedt | Niet in de keuzelijst. Een gemanipuleerde waarde geeft `ridesWithInvalid` (client) of `invalid_input` (server). |
| E34 | Een aanbieder stopt met aanbieden of meldt zich af | Na de verversing staan zijn meerijders bij "Zoekt een lift" (server zet `rides_with` op `null`, WP-19 E26/E27). |
| E35 | `rides_with` wijst naar een id die niet in de lijst staat | Telt als "Zoekt een lift" (`rideLabel` en `carpoolView`). |
| E36 | `seats_free = 0` bij de organisator | "Vrije plekken bij Lars: 0". |
| E37 | `departure_point` of `note` is `''` of alleen witruimte | Niet getoond (`optionalText`). |
| E38 | `tikkie_url` met `http://`, `javascript:`, iets wat geen URL is, een andere `https:`-host (`https://evil.example/pay/x`, `https://tikkie.me.evil.example/x`, `https://www.tikkie.me/pay/x`), een poort (`https://tikkie.me:8443/x`), een gebruikersnaam (`https://u@tikkie.me/x`), `HTTPS://TIKKIE.ME/x` of alleen `https://tikkie.me/` | Geen link (`tikkieLink` geeft `null`). |
| E39 | `spot_name` is `null` (kan niet volgens WP-19) | "Onbekende spot". |
| E40 | De verversing na een mutatie geeft `null` (sessie net verwijderd) | De sleutel wordt verwijderd en de pagina toont "Sessie niet gevonden". |
| E41 | PWA of tabblad uren later hervat | `refreshAll()` bij een zichtbaar document en data ouder dan 10 minuten (WP-14 A11). |
| E42 | Ingelogde bezoeker | Dezelfde pagina en dezelfde RPC's (`authenticated` mag ze ook uitvoeren). De pagina leest `$session` niet. |
| E43 | Offline | Shell uit de SW-cache, de load faalt, dan E3. |
| E44 | 30 deelnemers | De lijst toont ze allemaal. Een nieuwe aanmelding geeft `session_full`. |
| E45 | De token in de DOM, de URL of de console | Nooit: de tests controleren `document.body.innerHTML`, `window.location.href` en de console-spies. |
| E46 | Pagina blijft open tot na `ends_at` | 1 seconde na `ends_at` zet de klok-`$effect` `now`; het formulier en Wijzigen verdwijnen, de banner "voorbij" verschijnt, de versheidsmelding verdwijnt. |
| E47 | Een RPC hangt (slechte mobiele verbinding) | Na 15 seconden wordt de fetch afgebroken: `status: 0`, melding `network`, `busy` weer `false`. |
| E48 | Browser zonder `AbortSignal.timeout` (oudere browsers; de methode is "Baseline 2024") | De RPC gaat zonder timeout; verder gelijk. |
| E49 | Naam met U+202E in de keuzelijst "Rijd mee met" | Optietekst tussen FSI en PDI (`isolateText`), dus de rest van de optie draait niet om. |

## Testplan
Alle tests staan in `web/test/` en draaien met `npm test`. Pure logica komt eerst: eerst de test (rood), dan de implementatie, voor `session-view`, `rsvp-storage`, `rsvp`, het contract en `public-session-data`. Elk bestand met mocks heeft `beforeEach(() => vi.clearAllMocks())`. Tests die `localStorage` gebruiken doen in `beforeEach` `localStorage.clear()` en `resetRsvpMemory()` (echte module), en in `afterEach` `vi.restoreAllMocks()` en `vi.useRealTimers()`.

**Vaste klok in de pagina- en flowtests (review ronde 2, B-1).** De fixtures liggen op 18-07-2026; de echte datum ligt later. Zonder vaste klok zet `applyRefresh` (`now = new Date()`) de sessie na de eerste verversing op gesloten, en gaat de klok-timer (`Date.parse(ends_at) - Date.now()`, dus negatief, plus 1 s) binnen elke test af. Daarom zetten `rsvp-flow.test.ts`, `public-session-page.test.ts` en `public-session-page-integration.test.ts` in `beforeEach`, na de bestaande regels:
```ts
vi.useFakeTimers({ toFake: ['Date'] });
vi.setSystemTime(new Date(NOW));
```
Alleen `Date` is nep; `setTimeout`, `clearTimeout` en de rest blijven echt, dus `userEvent`, `findBy*` en `waitFor` werken ongewijzigd. Met `Date.now()` op `NOW` (09:00Z) ligt `ends_at` (16:00Z) 7 uur verder: de klok-timer gaat binnen een test niet af, en `applyRefresh` houdt de sessie open. `afterEach` heeft al `vi.useRealTimers()`. Uitzondering: test (j) in `public-session-page.test.ts` zet zijn eigen klok (zie daar). De builder lost dit niet op door `now = new Date()` uit `applyRefresh` of de klok-`$effect` te halen: die blijven zoals in A5 (N-1 uit ronde 1).

Mocks volgen het WP-13/WP-14-patroon (`vi.hoisted` plus `vi.mock('#lib/…js', …)`; lost `#lib` in `vi.mock` niet op, gebruik dan het relatieve pad).

### Fixtures (`web/test/fixtures/public-session.ts`)
Alleen testdata. Een eigen bestand, los van `fixtures/session-data.ts` van WP-20 (B-1). `SLUG` heeft dezelfde waarde als in WP-20; geen test importeert beide fixturebestanden.
- `SLUG = 'Q2x0aHJ1c3RtZTEyMzQ1Ng'` (22 tekens).
- `NOW = '2026-07-18T09:00:00.000Z'` (lokaal za 18 jul 11:00), `NOW_STALE = '2026-07-18T11:06:00.000Z'`, `NOW_ENDED = '2026-07-18T16:00:00.000Z'` (gelijk aan `ends_at`).
- `TOKEN = 'T'.repeat(43)`, `TOKEN_NEW = 'U'.repeat(43)`.
- Id's:
  - `EVA_ID = 'e0000000-0000-4000-8000-000000000001'`;
  - `SANNE_ID = '…02'`, `NOOR_ID = '…03'`, `TOM_ID = '…04'`, `NEW_ID = '…05'` (zelfde prefix).
- `SESSION_INFO: PublicSessionInfo`:
  - `slug SLUG`, `spot_id 'test-strand'`, `spot_name 'Teststrand'`, `organizer_name 'Lars'`;
  - `starts_at '2026-07-18T12:00:00+00:00'`, `ends_at '2026-07-18T16:00:00+00:00'`;
  - `note 'Parkeren bij de strandopgang'`, `seats_free 3`, `departure_point 'Utrecht CS'`;
  - `tikkie_url 'https://tikkie.me/pay/test'`, `cancelled false`.
- RSVP's (alle met `created_at '2026-07-17T18:0n:00+00:00'`, oplopend):
  - `RSVP_EVA`: `offers_ride`, 2, `rides_with null`;
  - `RSVP_SANNE`: `needs_ride`, `null`, `rides_with EVA_ID`;
  - `RSVP_NOOR`: `needs_ride`, `null`, `null`;
  - `RSVP_TOM`: `own`, `null`, `null`;
  - `RSVP_NEW`: `id NEW_ID`, `first_name 'Ilse'`, `own`, `null`, `null`.
- `SESSION_JSON = { session: SESSION_INFO, rsvps: [RSVP_EVA, RSVP_SANNE, RSVP_NOOR, RSVP_TOM] }`. Dat is de vorm uit de RPC, met `+00:00`-tijden.
- `SESSION_EVALS: Evaluation[]` (`spot_id 'test-strand'`, `tide_level_cm null`, `evaluated_at '2026-07-18T08:05:00+00:00'`):
  - 12:00Z `go`, `[]`, 18.4/23.6, 250, `onshore`, `high`;
  - 13:00Z `go`, `[]`, 19.0/24.0, 255, `onshore`, `high`;
  - 14:00Z `marginal`, `['low_confidence']`, 14.0/`null`, 300, `side_onshore`, `low`;
  - 15:00Z `no_go`, `['offshore']`, 15.2/19.8, 90, `offshore`, `medium`.
- `publicSessionPageData(overrides = {})` → `{ kind: 'ok', now: NOW, slug: SLUG, session: SESSION_INFO, rsvps: [RSVP_EVA, RSVP_SANNE, RSVP_NOOR, RSVP_TOM], evaluations: SESSION_EVALS, ...overrides }`.

### `web/test/helpers/fake-rpc.ts`
```ts
export interface RpcResponse { data: unknown; error: { code?: string; message?: string; details?: unknown; hint?: unknown } | null; status: number }
export interface FakeRpcCall {
	fn: string;
	args: Record<string, unknown> | undefined;
	options: unknown;
	argCount: number;
	signal: AbortSignal | null;   // set by .abortSignal(); null when never called
}
/** What rpc() returns: thenable like the postgrest builder, plus abortSignal() that records the signal. */
export interface FakeRpcBuilder extends PromiseLike<RpcResponse> {
	abortSignal(signal: AbortSignal): FakeRpcBuilder;
}
export function createFakeRpc(): {
	rpc: (fn: string, args?: Record<string, unknown>, options?: unknown) => FakeRpcBuilder;
	calls: FakeRpcCall[];
	/** Queue responses per function; an empty queue answers { data: null, error: null, status: 200 }. */
	respond(fn: string, ...responses: RpcResponse[]): void;
	/** The next call of fn rejects with err when awaited (simulates a thrown client). */
	throwNext(fn: string, err: unknown): void;
	reset(): void;
};
/** Client for vi.mock('#lib/supabase.js'): { rpc, from } plus an `auth` getter that only counts accesses. */
export function clientWithAuthTrap(parts: { rpc: unknown; from?: unknown }): { client: object; authAccesses: () => number };
```
`argCount` is `arguments.length` van `rpc(...)`, zodat een test kan eisen dat er geen derde argument is (POST, A6); `abortSignal` telt daar niet mee. `rpc` legt de call vast en bepaalt het antwoord bij de aanroep; `then` delegeert naar die promise. De `auth`-getter geeft `undefined` terug en verhoogt een teller.

### Tests per bestand

| Bestand | Tests |
|---|---|
| `session-view.test.ts` | **Slug en sleutel:** `isValidSessionSlug`: `SLUG`, 10 tekens en 64 tekens geven `true`; `'short'`, 65 tekens, `'bad slug!'`, `'a/b…'` en `''` geven `false`. `rsvpStorageKey(SLUG) === 'shakka:rsvp:' + SLUG`. **Foutsoort:** `rsvpErrorKind` geeft voor `{ code: 'PT400', message: k }` precies `k`, voor elk van de vijf codes; `{ code: 'PT400', message: 'boom' }` geeft `unknown`; `{ code: '42501', message: 'x' }` geeft `unknown`; `(anything, 0)` geeft `network`; `null`, `'x'` en `undefined` geven `unknown`. `new RsvpError('session_full', 'createRsvp').message === 'createRsvp failed: session_full'`. **(AC-4)** De teksten van `RSVP_MESSAGES` zijn allemaal verschillend, niet leeg, bevatten geen `_`, en zijn gelijk aan de tabel. `RSVP_MESSAGES.session_full` bevat `String(MAX_RSVPS)` en `organisator`. **Parsers:** `parsePublicSession(SESSION_JSON)` is diep gelijk aan `SESSION_JSON`. Met een extra sleutel `edit_token_hash` in de sessie en `email` in een RSVP: de uitvoer heeft die sleutels niet. Een fout volgt bij: `session` ontbreekt, `rsvps` is geen array, `ride: 'walk'`, `seats_free: 1.5`, `cancelled: 'false'`, `starts_at: 'gisteren'`, en `ends_at` gelijk aan `starts_at` (elke fout is `RsvpError` met `kind 'unknown'`). `parseCreateResult({ rsvp_id: NEW_ID, edit_token: TOKEN })` geeft hetzelfde object; met een token van 42 tekens, met `+` erin, of met `rsvp_id: 'x'` volgt een fout. `parseStoredRsvp`: geldig geeft het object; `null`, `[]`, `{}` en een verkeerde token geven `null`. **Gesloten:** `isSessionClosed`: `cancelled` geeft `true`; `now = ends_at` geeft `true`; `now = ends_at - 1 ms` geeft `false`; `now` tussen begin en eind geeft `false`. **Tijdvenster (A21; dezelfde verwachtingen als `formatWindowLocal` in WP-20 `time.test.ts`):** `sessionWindowText(SESSION_INFO.starts_at, SESSION_INFO.ends_at) === 'za 18 jul 14:00–18:00'`; `('2026-07-18T20:00:00Z', '2026-07-19T00:00:00Z') === 'za 18 jul 22:00 – zo 19 jul 02:00'`; `('2026-07-18T20:00:00Z', '2026-07-19T02:00:00Z') === 'za 18 jul 22:00 – zo 19 jul 04:00'`; `('2026-07-18T20:00:00Z', '2026-07-18T22:00:00Z') === 'za 18 jul 22:00–00:00'`; `('2026-10-25T00:00:00Z', '2026-10-25T02:00:00Z') === 'zo 25 okt 02:00–03:00'`; `('2026-10-25T00:00:00Z', '2026-10-25T03:00:00Z') === 'zo 25 okt 02:00–04:00'`; begin gelijk aan eind gooit `RangeError`. Deze test blijft in stap 9 ongewijzigd. **Labels:** `seatsText` geeft voor `null`, 0, 1 en 3 de vier teksten. `rideLabel` met `byId` van de fixtures: Eva → `{ 'Biedt een lift aan (2 plekken)', null }`; Sanne → `{ 'Rijdt mee met', 'Eva' }`; Noor → `{ 'Zoekt een lift', null }`; Tom → `{ 'Rijdt zelf', null }`; Sanne met `rides_with: TOM_ID` → `Zoekt een lift`; Eva met `seats_offered: null` → `'Biedt een lift aan'`. **Carpool:** `carpoolView(SESSION_INFO, fixtures)` geeft `organizerSeats 3`, `departurePoint 'Utrecht CS'`, `drivers` gelijk aan `[{ rsvp: Eva, riders: [Sanne] }]`, `seekers [Noor]` en `isEmpty false`. Met `{ seats_free: null, departure_point: '  ' }` en alleen Tom: `departurePoint null` en `isEmpty true`. Een meerijder met een `rides_with` die nergens naar wijst, staat bij `seekers`. **Links (A14):** `tikkieLink('https://tikkie.me/pay/x')` geeft `'https://tikkie.me/pay/x'`; `null`, `''`, `'http://tikkie.me/pay/x'`, `'javascript:alert(1)'`, `'geen url'`, `'https://evil.example/pay/x'`, `'https://tikkie.me.evil.example/x'`, `'https://www.tikkie.me/pay/x'`, `'https://tikkie.me:8443/x'`, `'https://u@tikkie.me/x'`, `'HTTPS://TIKKIE.ME/x'` en `'https://tikkie.me/'` geven `null`. `optionalText`: `null`, `''` en `'  '` geven `null`; `'x'` geeft `'x'`. `isolateText('Eva') === '⁨Eva⁩'`. **Formulier:** `parseRsvpForm`:
  - `{ first_name: '  Sanne ', ride: 'own', seats: '3', rides_with: EVA_ID }` in `create` geeft `{ first_name: 'Sanne', ride: 'own', seats_offered: null, rides_with: null }`;
  - `''` en `'   '` geven `nameRequired`;
  - 31× `'x'` geeft `nameTooLong`; 30× `'😀'` is ok;
  - `'Sa\nnne'` en `'Sa\u0007'` geven `nameInvalid`;
  - `ride: ''` geeft `rideRequired`;
  - `offers_ride` met `seats` `''` geeft `null`, `'0'` geeft 0, `'8'` geeft 8; `'9'`, `'-1'` en `'2.5'` geven `seatsInvalid`;
  - `edit` plus `needs_ride` met `rides_with EVA_ID` en `driverIds {EVA_ID}` geeft `EVA_ID`; met `TOM_ID` geeft het `ridesWithInvalid`; `''` geeft `null`;
  - `create` plus `needs_ride` met `rides_with EVA_ID` geeft `null`;
  - een lege naam plus `ride: ''` geeft twee fouten tegelijk.

  `rsvpFormFromRsvp(RSVP_EVA)` geeft `{ 'Eva', 'offers_ride', '2', '' }`. |
| `rsvp-storage.test.ts` | Met een `Map`-gebaseerde `StorageLike` en met de echte jsdom-`localStorage`. **(AC-3)** `writeStoredRsvp(localStorage, SLUG, { rsvp_id: NEW_ID, edit_token: TOKEN })` geeft `true`, en `localStorage.getItem('shakka:rsvp:' + SLUG) === JSON.stringify({ rsvp_id: NEW_ID, edit_token: TOKEN })`. Bij een extra eigenschap op het argument staat die niet in de waarde. `readStoredRsvp` geeft het object terug. `clearStoredRsvp` verwijdert de sleutel. Afwezig geeft `null`. `'{kapot'` en `'{"rsvp_id":"x"}'` geven `null`, en de sleutel is daarna weg. `storage` `null`: `readStoredRsvp` geeft `null` en gooit niet. Bij een `getItem` die gooit volgt `null`; bij een `removeItem` die gooit volgt geen fout. Bij een ongeldige slug volgt geen toegang tot de storage (spies 0 keer aangeroepen). `browserStorage()` geeft in jsdom `localStorage`; met een getter die gooit geeft hij `null` (`const d = Object.getOwnPropertyDescriptor(globalThis, 'localStorage')`, dan `Object.defineProperty(globalThis, 'localStorage', { configurable: true, get: () => { throw new Error('SecurityError'); } })`, en in `finally` `Object.defineProperty(globalThis, 'localStorage', d!)`; is de eigenschap niet configureerbaar, dan vervalt alleen deze deeltest en noteert de builder dat in `deviations.md`). **Geheugenfallback (E26):** (a) `writeStoredRsvp(null, SLUG, v)` geeft `false`, daarna geeft `readStoredRsvp(null, SLUG)` `v` en ook `readStoredRsvp(localStorage, SLUG)` `v` (lege opslag); `clearStoredRsvp(null, SLUG)` maakt beide `null`. (b) Een `setItem` die gooit: `false`, `localStorage` heeft de sleutel niet, en `readStoredRsvp(localStorage, SLUG)` geeft `v`. (c) Een geslaagde `writeStoredRsvp` na (b) wist de geheugenwaarde (na `localStorage.removeItem(key)` geeft `read` `null`). (d) `resetRsvpMemory()` wist de geheugenwaarde. (e) De geheugenwaarde is per slug: een andere geldige slug geeft `null`. |
| `rsvp.test.ts` | `fake = createFakeRpc()`, `trap = clientWithAuthTrap({ rpc: fake.rpc })`, en `vi.mock('#lib/supabase.js', () => ({ supabase: trap.client, initialUrlHash: '' }))` (hoisted). Daarnaast spies op `console.warn`, `console.error` en `console.log`. **(AC-3)** `createRsvp(SLUG, { first_name: '  Sanne  ', ride: 'needs_ride', seats_offered: null })`: `fake.calls[0]` is `{ fn: 'rsvp_create', args: { p_slug: SLUG, p_first_name: 'Sanne', p_ride: 'needs_ride', p_seats_offered: null }, argCount: 2 }`, en het resultaat is de geparste `{ rsvp_id, edit_token }`. `getPublicSession('kort')` geeft `null` met 0 calls. `getPublicSession(SLUG)`: `('get_public_session', { p_slug: SLUG })` met `argCount` 2; `data SESSION_JSON` geeft het geparste object; `data null` geeft `null`. `updateRsvp(TOKEN, { first_name: ' Eva ', ride: 'needs_ride', seats_offered: null, rides_with: null })`: `args` heeft precies de vijf sleutels `p_edit_token`, `p_first_name` (`'Eva'`), `p_ride`, `p_seats_offered` en `p_rides_with`; `'p_rides_with' in args` en de waarde is `null`; het resultaat is een `PublicRsvp`. `updateRsvp('abc', …)` gooit `RsvpError` `invalid_token` met 0 calls. `deleteRsvp(TOKEN)`: `('rsvp_delete', { p_edit_token: TOKEN })`; `true` en `false` komen door; `data: 'yes'` geeft `RsvpError` `unknown`. `deleteRsvp('abc')` geeft `false` met 0 calls. **(AC-4)** Voor elk van de vijf codes geeft een antwoord `{ data: null, error: { code: 'PT400', message: <code>, details: null, hint: null }, status: 400 }` bij `createRsvp` een `RsvpError` met die `kind`. Een antwoord met `message: 'secret detail'` en `code: 'XX000'` geeft `kind 'unknown'`, en `String(err)` en `err.message` bevatten geen `'secret detail'`. `status: 0` geeft `network`. `fake.throwNext('rsvp_create', new Error('secret detail'))` geeft `network`. **Timeout (A6, review N-8):** elke call heeft een `signal` met `typeof signal.aborted === 'boolean'`; met `vi.spyOn(AbortSignal, 'timeout')` is die aangeroepen met `RPC_TIMEOUT_MS` (15 000). Met `AbortSignal.timeout` tijdelijk op `undefined` (via `Object.defineProperty(AbortSignal, 'timeout', { configurable: true, value: undefined })`, origineel terug in `finally`) slaagt `getPublicSession(SLUG)` en is `signal` `null`. **Altijd:** elke call heeft `argCount === 2` (geen `{ get: true }`); `trap.authAccesses() === 0`; geen console-spy is aangeroepen met een argument dat `TOKEN` bevat. |
| `rsvp-contract.test.ts` (node) | Leest `../../supabase/migrations/20261015200000_sessions.sql` (via `new URL(…, import.meta.url)`). **(0) Drift door latere migraties (review N-4):** lees alle `*.sql` in `../../supabase/migrations/` (`readdirSync`, gesorteerd); voor elk bestand met een naam die na `20261015200000_sessions.sql` sorteert, matcht de tekst niet `/\b(get_public_session\|rsvp_create\|rsvp_update\|rsvp_delete\|purge_expired_sessions)\b/` en niet `/alter\s+table\s+(if\s+exists\s+)?(only\s+)?public\.rsvps\b/i`. Faalt dat, dan is de melding `` `${file} changes the session RPCs or rsvps: update rsvp-types.ts, session-view.ts and rsvp-contract.test.ts` ``. Zo blijft de test niet groen op een verouderde definitie (`create or replace function` in een latere migratie). `fnBlock(name)` is de tekst van `create function public.<name>(` tot de eerste `$$;` daarna. `params(name)`: de groep uit `/create function public\.\w+\(([\s\S]*?)\)\s*returns/`, gesplitst op `,`, per deel het eerste woord. De tests: (1) `params('get_public_session')` is `['p_slug']`; `params('rsvp_create')` is `['p_slug', 'p_first_name', 'p_ride', 'p_seats_offered']`; `params('rsvp_update')` is `['p_edit_token', 'p_first_name', 'p_ride', 'p_seats_offered', 'p_rides_with']`; `params('rsvp_delete')` is `['p_edit_token']`. Plus: de sleutels die `rsvp.ts` werkelijk stuurt (via `createFakeRpc` en de vier functies) zijn per functie exact gelijk aan `params(...)`. (2) In `fnBlock('get_public_session')`: de namen uit `/'([a-z_]+)',/g` in het stuk tussen `'session', jsonb_build_object(` en `'rsvps',` (exclusief) zijn exact `PUBLIC_SESSION_KEYS`; in het stuk dat direct ná de letterlijke tekst `'rsvps',` begint (dus zonder de sleutel `rsvps` zelf) en loopt tot `order by r.created_at` zijn ze exact `PUBLIC_RSVP_KEYS`. (3) De `return jsonb_build_object(` in `fnBlock('rsvp_update')` heeft precies `PUBLIC_RSVP_KEYS`. (4) `fnBlock('rsvp_create')` bevat `'rsvp_id'` en `'edit_token'`. (5) De set `using message = '([a-z_]+)'` over `fnBlock('rsvp_create') + fnBlock('rsvp_update') + fnBlock('rsvp_delete')` is gelijk aan `RPC_ERROR_CODES`. (6) `fnBlock('rsvp_update')` bevat `` `'${EDIT_TOKEN_RE.source}'` `` en `fnBlock('get_public_session')` bevat `` `'${SESSION_SLUG_RE.source}'` ``. (7) `/ends_at < p_now - interval '(\d+) days'/` geeft `SESSION_RETENTION_DAYS`. (8) De CHECK `between 0 and 8` voor `seats_offered` en `between 1 and 30` voor `first_name` staan in het bestand (`MAX_SEATS`, `MAX_FIRST_NAME`), en `>= 30` (het maximum aantal RSVP's) staat in `fnBlock('rsvp_create')` (`MAX_RSVPS`). |
| `public-session-data.test.ts` | Mockt `#lib/rsvp.js` (`getPublicSession`) en `#lib/data.js` (`getEvaluations`). `loadPublicSessionPage('kort', new Date(NOW))` geeft `not_found` met 0 calls. Bij `null` volgt `not_found` en wordt `getEvaluations` niet aangeroepen. Bij een geldige sessie: `getEvaluations` met `('test-strand', 2026-07-18T12:00:00.000Z, 2026-07-18T16:00:00.000Z)` (vergelijk `toISOString()`), en het resultaat is gelijk aan `publicSessionPageData()` (met `now === NOW`). Met `starts_at '2026-07-18T12:30:00+00:00'` is `from` 12:00Z. Als `getEvaluations` rejectet met `new Error('secret detail')`: `ok` met `evaluations: null`, en `console.warn` precies één keer met exact `('session verdict load failed')`. Als `getPublicSession` rejectet: `error`, met `console.warn('session page load failed')` en geen argument met `secret detail`. |
| `public-session-page.test.ts` | `beforeEach`: `Date` vast op `NOW` (zie "Vaste klok"; (j) wijkt af). Mockt `$app/navigation` (`refreshAll`) en `#lib/rsvp.js` (`getPublicSession`, `createRsvp`, `updateRsvp` en `deleteRsvp` als `vi.fn`). `#lib/supabase.js` wordt gemockt als een factory die gooit (zoals `spot-page.test.ts`). `#lib/auth.js` wordt gemockt met `session: { subscribe: authSpy }`. Renders met `render(Page, { data } as never)`. **(AC-2)** (a) Met `publicSessionPageData()`: h1 `Kitesessie: Teststrand`; `.session-when` heeft tekst `za 18 jul 14:00–18:00`; `.session-organizer` heeft tekst `Georganiseerd door Lars`; de link `Naar de spotpagina van Teststrand` heeft `href '/spot/test-strand'`; de notitie; de link `Open betaalverzoek` heeft `href 'https://tikkie.me/pay/test'`, `target '_blank'` en `rel 'noopener noreferrer'`, en de tekst `(link naar tikkie.me)` staat er. Deelnemers: kop `Deelnemers (5)`; `li.organizer` met `Lars` en `organisator`; `[data-rsvp=EVA_ID]` bevat `Biedt een lift aan (2 plekken)`, `SANNE_ID` bevat `Rijdt mee met Eva`, `NOOR_ID` bevat `Zoekt een lift` en `TOM_ID` bevat `Rijdt zelf`. Carpool: `Vrije plekken bij Lars: 3` en `Vertrekpunt: Utrecht CS`; `[data-driver=EVA_ID]` bevat `2 plekken` en `meerijders: Sanne`; `[data-seeker=NOOR_ID]`. Uren: `time`-elementen `14:00`, `15:00`, `16:00` en `17:00`; binnen `.hour` van `17:00` staan `Niet gaan` en `Aflandige wind: niet kiten`. Daarnaast `Bijgewerkt: za 18 jul 10:05`. `authSpy` is niet aangeroepen. Elke voornaam staat in een `bdi` (`container.querySelectorAll('bdi')` bevat de tekst `Eva`). (b) **(AC-5)** `document.head.querySelector('meta[name="robots"]')` heeft `content === 'noindex'`, ook bij `{ kind: 'not_found', … }`. Met `session: { …SESSION_INFO, cancelled: true }`: `getByRole('alert')` bevat `Deze sessie is geannuleerd`; er is geen `Voornaam`-veld (`queryByLabelText('Voornaam')` is `null`) en geen knop `Ik ook`; `ouder dan 3 uur` staat er niet. Met `now: NOW_ENDED`: de tekst `Deze sessie is voorbij`, geen formulier. (c) **(AC-6)** Een link met `href === 'https://open-meteo.com/'` en de tekst `Rijkswaterstaat`. (d) `not_found` geeft h1 `Sessie niet gevonden` en de tekst `` `Sessies verdwijnen ${SESSION_RETENTION_DAYS} dagen na afloop.` `` (review N-2). `error` geeft een alert met de tekst; een klik op `Opnieuw proberen` roept `refreshAll` één keer aan. (e) `now: NOW_STALE` geeft een alert met `ouder dan 3 uur`. (f) `evaluations: null` geeft `Het oordeel kon niet worden geladen.`; `[]` geeft `Er is nog geen oordeel voor dit tijdvenster.` (g) Een window over middernacht (`starts_at '2026-07-18T20:00:00+00:00'`, `ends_at '2026-07-19T02:00:00+00:00'`, evaluaties om 21:00Z en 23:00Z) geeft de koppen (`getByRole('heading', { level: 3, name })`) `za 18 jul` en `zo 19 jul`, en `.session-when` `za 18 jul 22:00 – zo 19 jul 04:00`. (h) Met `tikkie_url 'http://tikkie.me/x'` en met `'https://evil.example/pay/x'` is er geen link `Open betaalverzoek` en geen tekst `link naar`. Met `note: '   '` is er geen kop `Notitie`. (i) Hervatten: met `now` 20 minuten vóór `Date.now()`, `visibilityState` `'visible'` en een event volgt `refreshAll`, zoals in `spot-page.test.ts`. (j) **Klok (A5, E46, review N-1):** eerst `vi.useRealTimers()` (heft de `Date`-klok uit `beforeEach` op), dan `vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout', 'Date'] })` en `vi.setSystemTime(new Date('2026-07-18T15:59:00.000Z'))`, render met `now: '2026-07-18T15:59:00.000Z'`: het veld `Voornaam` en de knop `Ik ook` staan er (`getByLabelText`, na `await tick()` voor de opslag-`$effect`). `vi.advanceTimersByTime(61_000)` en `await tick()`: geen `Voornaam`-veld, de tekst `Deze sessie is voorbij` staat er. Bij een unmount vóór het afgaan is de timer opgeruimd: `vi.getTimerCount()` na `unmount()` is gelijk aan de telling vóór `render`. |
| `public-session-page-integration.test.ts` | `beforeEach`: `Date` vast op `NOW` (zie "Vaste klok"). **(AC-2, letterlijk: gemockte RPC)** `fake = createFakeRpc()` en `db = createFakeSupabase()` (bestaande helper), plus `trap = clientWithAuthTrap({ rpc: fake.rpc, from: db.client.from })`. `vi.mock('#lib/supabase.js', () => ({ supabase: trap.client, initialUrlHash: '' }))`, en `$app/navigation` gemockt. `fake.respond('get_public_session', { data: SESSION_JSON, error: null, status: 200 })` en `db.respond('evaluations', { data: SESSION_EVALS, error: null })`. Daarna `data = await loadPublicSessionPage(SLUG, new Date(NOW))` (echte modules) en `render(Page, { data } as never)`. Dan staan de deelnemers (`Eva`, `Sanne`, `Noor` en `Tom` in de deelnemerslijst), de carpool (`Vrije plekken bij Lars: 3`, `meerijders: Sanne`, `Zoekt een lift` bij Noor) en de vier uren in beeld. `fake.calls` is precies één `get_public_session` met `argCount 2`. `db.calls` is precies één `evaluations`-call met `gte('valid_at', '2026-07-18T12:00:00.000Z')` en `lt('valid_at', '2026-07-18T16:00:00.000Z')`. `trap.authAccesses() === 0`. |
| `rsvp-flow.test.ts` | `beforeEach`: `Date` vast op `NOW` (zie "Vaste klok"; nodig voor (1), (3), (5), (6) en (13), die na een verversing een open sessie verwachten). Mockt `#lib/rsvp.js` (vier `vi.fn`), `$app/navigation`, en `#lib/supabase.js` (gooiende factory). De opslag (`rsvp-storage`) en `session-view` zijn echt. `user = userEvent.setup()`. Helper `key = 'shakka:rsvp:' + SLUG`. **Standaardantwoord (review N-5):** in `beforeEach` krijgt `getPublicSession` `mockResolvedValue({ session: SESSION_INFO, rsvps: [RSVP_EVA, RSVP_SANNE, RSVP_NOOR, RSVP_TOM] })`; tests die iets anders nodig hebben, overschrijven dat met `mockResolvedValueOnce`. Zonder standaard geeft de `vi.fn` `undefined` en zet `applyRefresh` `gone = true`. **(AC-3)** (1) Render `publicSessionPageData()`. Typ `'  Sanne  '` in `Voornaam` (`findByLabelText`, want de opslag-`$effect` loopt eerst) en klik `Ik ook`. `createRsvp` is één keer aangeroepen met `(SLUG, { first_name: 'Sanne', ride: 'own', seats_offered: null })`. Met `createRsvp` → `{ rsvp_id: NEW_ID, edit_token: TOKEN_NEW }` en `getPublicSession` → `{ session: SESSION_INFO, rsvps: [...4, RSVP_NEW] }`: daarna is `localStorage.getItem(key) === JSON.stringify({ rsvp_id: NEW_ID, edit_token: TOKEN_NEW })`; `findByRole('heading', { name: 'Jij gaat' })`; de knoppen `Wijzigen` en `Afmelden`; `role="status"` met `Je staat op de lijst.`; `[data-rsvp=NEW_ID]` bevat `(jij)`. (2) Opnieuw renderen: `unmount()`, met `localStorage.setItem(key, JSON.stringify({ rsvp_id: TOM_ID, edit_token: TOKEN }))` en `render` met `publicSessionPageData()`. Dan staan `Jij gaat`, `Wijzigen` en `Afmelden` er, `Aangemeld als Tom · Rijdt zelf`, en geen `Voornaam`-veld. (3) Afmelden: vanuit (2) klik je `Afmelden` en dan `Ja, afmelden`. `deleteRsvp` is aangeroepen met `(TOKEN)` → `true`; `localStorage.getItem(key)` is `null`; `role="status"` bevat `Je bent afgemeld.`; het veld `Voornaam` is er weer. (4) Met `deleteRsvp` → `false`: de sleutel is weg en de tekst `Je aanmelding bestond al niet meer.` staat er. (5) Wijzigen: vanuit (2) klik je `Wijzigen`, kies je `Ik zoek een lift`, kies je in `Rijd mee met` de optie van Eva op waarde (`user.selectOptions(getByLabelText('Rijd mee met'), EVA_ID)`; de optietekst is `'⁨Eva⁩'`, A11) en klik je `Opslaan`. `updateRsvp` krijgt `(TOKEN, { first_name: 'Tom', ride: 'needs_ride', seats_offered: null, rides_with: EVA_ID })`, daarna `Je wijziging is opgeslagen.` en `getPublicSession` één keer. (6) `updateRsvp` rejectet met `new RsvpError('invalid_token', 'updateRsvp')` (echte klasse uit `session-view`): de sleutel is weg, de melding is `RSVP_MESSAGES.invalid_token`, en het formulier `Voornaam` is er weer. **(AC-4)** (7) Geparametriseerd over `rate_limited`, `session_full`, `session_closed` en `invalid_input`: `createRsvp` rejectet met `new RsvpError(kind, 'createRsvp')`; dan heeft `findByRole('alert')` exact `RSVP_MESSAGES[kind]`. `queryByText(/rate_limited\|session_full\|session_closed\|invalid_input/)` is `null`; de sleutel bestaat niet. Daarna: de vier verzamelde teksten zijn paarsgewijs verschillend. Bij `session_full` en `session_closed` is `getPublicSession` aangeroepen. (8) `createRsvp` rejectet met `new Error('secret detail')`: `RSVP_MESSAGES.unknown`, en `secret detail` staat niet in `document.body.textContent`. **Overig:** (9) een lege naam plus `Ik ook` geeft `Vul je voornaam in.`, `aria-invalid="true"` op het veld, en `createRsvp` 0 keer. (10) Dubbelklik: `createRsvp` geeft een promise die nog niet is opgelost. Twee klikken op `Ik ook` geven één aanroep, en de knop `Bezig…` is `disabled`. (11) Een verouderde sleutel (`{ rsvp_id: NEW_ID, edit_token: TOKEN }`, terwijl `NEW_ID` niet in de lijst staat) is na de render verwijderd, en het formulier staat er. (12) Een kapotte sleutel (`'{kapot'`) wordt verwijderd, en het formulier staat er. (13) `vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => { throw new Error('quota'); })`. Na een geslaagde create staat `RSVP_NOTICES.storageFailed` er. Daarna een nieuwe load zoals bij hervatten: `rerender({ data: publicSessionPageData({ rsvps: [...4, RSVP_NEW] }) })` (nieuw object). `Jij gaat` blijft staan (geheugenfallback, review N-10), en `Afmelden` werkt (`deleteRsvp` met `TOKEN_NEW`). De `rerender` zet `now` terug op `data.now` (`NOW`); met de vaste klok blijft de sessie open (review ronde 2, N-3: geen apart probleem). (14) Tweede tabblad: vóór de klik zet de test `localStorage.setItem(key, JSON.stringify({ rsvp_id: TOM_ID, edit_token: TOKEN }))` (na de render). De klik op `Ik ook` geeft 0 keer `createRsvp`, `getPublicSession` één keer, en `Jij gaat`. (15) Gesloten plus sleutel (`cancelled: true`, sleutel Tom): `Afmelden` staat er, `Wijzigen` niet; de sectie `.rsvp-panel` heeft `aria-labelledby="rsvp-heading"`. Na `Afmelden` en `Ja, afmelden`: de sectie toont `Je bent afgemeld.` en heeft geen attribuut `aria-labelledby` (review N-12). (16) Een verversing die `null` geeft na een create: `Sessie niet gevonden`, en de sleutel is weg. (17) Na alle stappen in (1)–(5): `document.body.innerHTML` en `window.location.href` bevatten `TOKEN` en `TOKEN_NEW` niet. (18) **Server sluit (A5, review N-1):** een open sessie volgens de browser (`publicSessionPageData()`), `createRsvp` rejectet met `new RsvpError('session_closed', 'createRsvp')`: de melding `RSVP_MESSAGES.session_closed` staat er, het veld `Voornaam` en de knop `Ik ook` zijn weg, `getPublicSession` is één keer aangeroepen, en `createRsvp` is één keer aangeroepen. (19) Met sleutel Tom: `Wijzigen`, `Opslaan` met `updateRsvp` dat rejectet met `session_closed`: `Wijzigen` is weg, `Afmelden` staat er nog. |
| `session-no-auth.test.ts` (node) | **(AC-2, A1)** Leest de bestanden `src/routes/s/[slug]/+page.svelte`, `src/routes/s/[slug]/+page.ts`, `src/lib/rsvp.ts`, `src/lib/rsvp-storage.ts`, `src/lib/session-view.ts`, `src/lib/rsvp-types.ts`, `src/lib/public-session-data.ts`, en `RsvpPanel.svelte`, `RsvpForm.svelte` en `SessionParticipants.svelte` uit `src/lib/components/`. Geen van die bestanden matcht `/#lib\/auth\.js\|\.\/auth\.js\|\.auth\b\|getSession\|getUser\|\$session/`. `rsvp.ts` matcht niet `/get:\s*true\|head:\s*true/` en niet `/\.from\(/`, en bevat precies één keer `supabase.rpc(` (in `call`). Geen van de bestanden matcht `/\{@html/` of `/console\.(log\|info\|debug)\(/`. `+page.svelte` bevat `<meta name="robots" content="noindex" />` binnen `<svelte:head>`. |
| `user-tables.test.ts` (gewijzigd) | `.rpc(` komt alleen voor in `lib/rsvp.ts` (zie Interfaces). De bestaande tests blijven ongewijzigd groen. |

### Per acceptatiecriterium
- **AC-1:** `cd web && npm run check && npm test && npm run build`, plus `npm run verify:build` en vanuit de root `bash scripts/check-no-client-openmeteo.sh`. In CI loopt dit via de bestaande job `web`.
- **AC-2:** `public-session-page-integration.test.ts` (gemockte RPC: deelnemers, carpool en uren, `authAccesses() === 0`), `public-session-page.test.ts` (a) (`authSpy` niet aangeroepen) en `session-no-auth.test.ts`.
  - **Reikwijdte van dit bewijs (review N-11).** De tests tonen aan dat de pagina en de WP-21-modules `auth`/`$session` niet aanraken en geen auth-sessie vereisen. Ze tonen niet aan dat de echte client geen auth-aanroep doet: supabase-js roept intern `auth.getSession()` aan om de bearer-header te bepalen (anoniem: de anon key), en de layout start `initAuth()`. Dat is bestaand gedrag en geen probleem: zonder sessie gaat de RPC als `anon`. De verifier noteert dit in de verificatie, zodat niemand de trap-test leest als bewijs voor de echte client.
- **AC-3:**
  - `rsvp.test.ts`: `rsvp_create` met de getrimde voornaam;
  - `rsvp-flow.test.ts` (1): versturen met de getrimde naam en de sleutel `shakka:rsvp:{slug}` met `{rsvp_id, edit_token}`;
  - `rsvp-flow.test.ts` (2): opnieuw renderen toont Wijzigen en Afmelden;
  - `rsvp-flow.test.ts` (3): afmelden roept `rsvp_delete` aan en verwijdert de sleutel;
  - `rsvp-storage.test.ts`.
- **AC-4:** `rsvp-flow.test.ts` (7) en (8), `rsvp.test.ts` (PT400-mapping) en `session-view.test.ts` (teksten verschillend en gelijk aan de tabel).
- **AC-5:** `public-session-page.test.ts` (b) en (j): `noindex` in `document.head`, de banner bij annuleren, en geen formulier bij een geannuleerde of afgelopen sessie (ook als de sessie afloopt terwijl de pagina open staat). Daarnaast `session-no-auth.test.ts` (meta in de bron) en `rsvp-flow.test.ts` (18) (server sluit).
- **AC-6:** `public-session-page.test.ts` (c). De footer-`Attribution` van de layout blijft gedekt door `layout.test.ts`.
- **AC-7:** `NEEDS_LARS`, volgens RUNBOOK §16.9.

Daarnaast blijven alle bestaande webtests groen (`no-local-date-getters`, `no-third-party`, `no-telegram`, `data-tables` en de rest van `user-tables`), en `cd ingest && uv run pytest` ook (deze WP raakt `ingest/` niet).

## Externe afhankelijkheden
Gecontroleerd op 15 oktober 2026. **Geen nieuwe packages.** Gebruikt worden de versies uit WP-13 en WP-15 (`@supabase/supabase-js` ^2.117.3, `svelte` ^5.57.2, `@sveltejs/kit` ^3.0.1, `vitest` ^5.0.4, `jsdom` ^30.1.2, `@testing-library/*`).

| Onderwerp | Bevinding die het ontwerp raakt | Bron |
|---|---|---|
| supabase-js `rpc(fn, args = {}, { head = false, get = false, count } = {})` | Standaard POST met de argumenten als JSON-body. `get: true` of `head: true` zet de argumenten in de querystring; dat gebruiken we nooit (A6). | https://raw.githubusercontent.com/supabase/supabase-js/master/packages/core/postgrest-js/src/PostgrestClient.ts, https://supabase.com/docs/reference/javascript/rpc |
| postgrest-js foutvorm | Een HTTP-fout geeft `error = JSON.parse(body)` met `code`, `message`, `details` en `hint`. Een netwerkfout resolvet (rejectet niet) met `status: 0` en een lege `code`. Daarom `rsvpErrorKind(error, status)`. | https://raw.githubusercontent.com/supabase/supabase-js/master/packages/core/postgrest-js/src/PostgrestBuilder.ts |
| postgrest-js `abortSignal(signal: AbortSignal): this` | Zet `this.signal`, dat aan `fetch` wordt meegegeven. Bij `shouldThrowOnError === false` (standaard) vangt de builder elke fetchfout op en resolvet met `status: 0`, `data: null` en een `error` met lege `code`; voor een `AbortError` zet hij alleen een andere hint. Door `AbortSignal.timeout` rejectet `fetch` met de reden van het signaal (een `TimeoutError`); ook dat is een fetchfout, dus `status: 0` en `network` (A6, E47). | https://raw.githubusercontent.com/supabase/supabase-js/master/packages/core/postgrest-js/src/PostgrestTransformBuilder.ts, https://raw.githubusercontent.com/supabase/supabase-js/master/packages/core/postgrest-js/src/PostgrestBuilder.ts (gecontroleerd 15-10-2026) |
| `AbortSignal.timeout(ms)` | Statische methode, abort met een `TimeoutError` als reden; "Baseline 2024" (breed beschikbaar sinds april 2024), dus oudere browsers missen hem: daarom de `typeof`-controle (E48) | https://developer.mozilla.org/en-US/docs/Web/API/AbortSignal/timeout_static |
| Tikkie-linkvorm | Een echt betaalverzoek heeft de vorm `https://tikkie.me/pay/<code>`; het enige echte domein is `tikkie.me` (A14) | https://tikkie.me/vraag-en-antwoord/nl, https://www.seniorweb.nl/artikel/hoe-zie-je-of-een-tikkie-betaalverzoek-veilig-is |
| Unicode FSI/PDI (U+2068/U+2069) | Bidi-isolatie in platte tekst, voor `<option>` (A11) | https://www.w3.org/International/questions/qa-bidi-unicode-controls |
| PostgREST `PTxyz` | `code: "PT400"`, HTTP 400, `message` = de code uit WP-19 | https://docs.postgrest.org/en/v14/references/errors.html (via WP-19) |
| `JSON.stringify` laat `undefined` weg | Daarom `?? null` voor elke parameter. Zonder de sleutel vindt PostgREST de functie niet (`PGRST202`). | https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/JSON/stringify |
| Svelte 5.25+: een `let … = $derived(…)` mag je tijdelijk overschrijven | A8 (`session`, `rsvps`, `gone`) | https://svelte.dev/docs/svelte/$derived ("Overriding derived values"; "Prior to Svelte 5.25, deriveds were read-only") |
| Svelte `$bindable`, `untrack` | `stored` in `RsvpPanel`, en de beginwaarden van het formulier (zelfde patroon als `AlertRuleForm`) | https://svelte.dev/docs/svelte/$bindable, https://svelte.dev/docs/svelte/svelte#untrack |
| HTML `<bdi>` | Bidi-isolatie van vrije tekst (A11) | https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Elements/bdi |
| Robots-meta via JavaScript | Google: "You can use JavaScript to add a robots meta tag to a page or change its content." (A18) | https://developers.google.com/search/docs/crawling-indexing/javascript/javascript-seo-basics, https://developers.google.com/search/docs/crawling-indexing/robots-meta-tag |
| `rel="noopener noreferrer"` | Geen `window.opener` en geen Referer (de slug) naar de Tikkie-host | https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Attributes/rel/noreferrer |
| Unicode property escape `\p{Cc}` met de vlag `u` | Stuurtekens in de voornaam weigeren (zoals `[[:cntrl:]]` in de migratie) | https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Regular_expressions/Unicode_character_class_escape |
| Database-contract | RPC's, vormen, foutcodes, limieten en de bewaartermijn | `docs/wp/WP-19/blueprint.md`, `supabase/migrations/20261015200000_sessions.sql` |

Geen Open-Meteo, geen nieuwe origin, geen CDN, geen analytics, geen nieuwe dienst.

## Risico's
- **R1. De token gaat verloren.** In-app-browsers (WhatsApp, Instagram), privémodus of het wissen van websitedata maken een andere of lege `localStorage`. Wie dan terugkomt, kan zich niet meer afmelden of wijzigen. Mitigatie:
  - de UI zegt het ("alleen in deze browser op dit apparaat");
  - het formulier verschijnt weer, dus de bezoeker kan zich opnieuw aanmelden (dan staat hij er twee keer in);
  - Lars kan een RSVP verwijderen via RUNBOOK §16.5 en §16.8;
  - een moderatie-RPC voor de organisator hoort bij WP-22.
- **R2. De token in `localStorage` is leesbaar voor elk script op de origin (XSS).** De gevolgen zijn beperkt tot het wijzigen of afmelden van die ene RSVP. Mitigatie: nergens `{@html}` (test), geen scripts van derden (bestaande trackerscan), en een CSP met `script-src 'self'` in WP-23.
- **R3. Overlap met WP-20 (bijgewerkt na review B-1).** Na de hernoemingen maakt WP-21 geen bestand aan dat WP-20 ook aanmaakt, dus geen add/add-conflicten. De echte overlap:
  - `web/test/user-tables.test.ts`: WP-20 wijzigt de tests voor tabellen en schrijfacties (`sessions` erbij); WP-21 vervangt alleen de test `no file uses .rpc(` door de allowlist-test. Een tekstueel conflict is mogelijk als de hunks aangrenzen. Oplossing in stap 9: de WP-20-versie van het bestand nemen en daarin alleen `it('no file uses .rpc(', …)` vervangen door de WP-21-test plus de constante `RPC_FILES`;
  - `docs/RUNBOOK.md`: WP-20 wijzigt §11 (punt 7 en nieuw punt 10), WP-21 voegt §16 punt 8 en 9 toe. Andere secties; een conflict is onwaarschijnlijk, en anders beide behouden;
  - `app.css` wijzigt alleen WP-21 (WP-20 gebruikt `<style>`-blokken); `time.ts` en `fake-supabase.ts` wijzigt alleen WP-20.

  De volgorde ligt vast: WP-20 merget eerst, WP-21 rebaset daarna (stap 9). Faalt een test van WP-20 na de rebase door WP-21-code, dan past de builder alleen WP-21-bestanden aan; WP-20-bestanden blijven ongemoeid (behalve de genoemde conflictoplossing in `user-tables.test.ts`).
- **R10. Een WP-20-helper wijkt toch af van de blueprint.** Stap 9 vervangt een eigen helper alleen als het WP-20-gedrag gelijk is (de bestaande WP-21-tests blijven ongewijzigd groen). Anders blijft de eigen helper staan, noteert de builder het in `deviations.md`, en geldt het opruimpunt uit "Gevolgen voor latere WP's".
- **R4. `<svelte:head>` in jsdom.** Verwacht wordt dat Svelte 5 de `meta` in `document.head` zet. Lukt dat in vitest niet, dan blijft het bewijs voor AC-5 de bronregel in `session-no-auth.test.ts`. De builder noteert dat in `deviations.md`, en de verifier controleert de `meta` in de gebouwde app met `npm run preview` en de devtools.
- **R5. Een dubbele RSVP na een verloren antwoord** (E25, en na de timeout van 15 seconden, E47). Dit komt zelden voor. Zonder een idempotentiesleutel in de RPC (een wijziging in WP-19) is het niet op te lossen. Het geeft hooguit één extra naam in de lijst.
- **R6. Spam en vol zetten** (WP-19 R1, review N-7). De UI geeft duidelijke meldingen (`rate_limited` met "over een paar minuten", `session_full`). Echte moderatie hoort bij WP-22.
- **R7. `noindex` alleen via JavaScript** (A18). Crawlers zonder JavaScript zien de lege shell zonder sessiedata. Er lekt dus niets, maar de URL kan wel in een index komen als iemand hem publiek deelt. `X-Robots-Tag` volgt in WP-23.
- **R8. De bewaartermijn van 7 dagen is nog niet bevestigd door Lars** (WP-19 A1). De tekst in de UI en de pagina "Sessie niet gevonden" volgen `SESSION_RETENTION_DAYS`. Verandert de migratie, dan faalt `rsvp-contract.test.ts` en moet de constante mee.
- **R9. Egress.** Per bezoek één RPC (hoogstens 30 RSVP's, < 5 kB), één query van ≤ 17 evaluaties, en per mutatie twee RPC's. Dat is verwaarloosbaar.

## Buiten scope
- Dynamische OG-previews per sessie; pushmeldingen naar deelnemers.
- Sessies aanmaken, delen, bewerken of annuleren (WP-20); een moderatie-RPC voor de organisator (WP-22).
- Een capaciteitscontrole voor meerijders en de koppeling van `seats_free` aan RSVP's (WP-19 Buiten scope).
- `X-Robots-Tag` in `web/static/_headers`, de CSP, de privacypagina en een opruimronde over oude `shakka:rsvp:*`-sleutels (WP-23).
- De voornaam onthouden tussen sessies (A17); een kaart of golven op de sessiepagina.
- Wijzigingen in `ingest/`, `supabase/`, `data/`, `.github/`, de service worker, de layout, `data.ts`, `user-data.ts` en `types.ts`.

## Stappenplan voor de builder
Werk in de worktree `/Users/larst/Dev/Shakka/.claude/worktrees/WP-21` op branch `wp/WP-21`, met Node 24. Lees of print `.env` en `web/.env` nooit. Na elke stap draai je vanuit `web/` `npm run check && npm test`, plus de extra's die bij de stap staan. Eén commit per stap, in het Engels (bijv. `WP-21: add session view logic`).

Maak geen bestand aan met de naam `web/src/lib/session-page-data.ts`, `web/test/session-page-data.test.ts` of `web/test/fixtures/session-data.ts`: die zijn van WP-20 (B-1).

1. **Types en pure logica (tests eerst).**
   - Schrijf `test/fixtures/public-session.ts`, `test/session-view.test.ts` en `test/rsvp-contract.test.ts` (inclusief driftcheck (0)), zonder het deel van contracttest (1) dat `rsvp.ts` nodig heeft (de verzonden sleutels). Dat deel komt in stap 3. Rood.
   - Maak `src/lib/rsvp-types.ts` en `src/lib/session-view.ts`. Groen.
2. **Opslag (tests eerst).** Schrijf `test/rsvp-storage.test.ts`. Rood. Maak `src/lib/rsvp-storage.ts`. Groen.
3. **RPC-module (tests eerst).**
   - Schrijf `test/helpers/fake-rpc.ts` en `test/rsvp.test.ts`, en vul `rsvp-contract.test.ts` aan met de check van de verzonden sleutels. Pas `test/user-tables.test.ts` aan (de allowlist). Rood.
   - Maak `src/lib/rsvp.ts`. Groen.
   - Controleer met `grep -rn "\.rpc(" web/src` dat alleen `lib/rsvp.ts` voorkomt.
4. **Paginadata en route (tests eerst).** Schrijf `test/public-session-data.test.ts`. Rood. Maak `src/lib/public-session-data.ts` en `src/routes/s/[slug]/+page.ts`. Groen.
5. **Componenten en pagina.**
   - Maak `SessionParticipants.svelte`, `RsvpForm.svelte`, `RsvpPanel.svelte` en `src/routes/s/[slug]/+page.svelte`, en voeg het CSS-blok toe aan `app.css`.
   - Schrijf `test/public-session-page.test.ts`, `test/public-session-page-integration.test.ts`, `test/rsvp-flow.test.ts` en `test/session-no-auth.test.ts`.
   - Groen, plus `npm run build` en `npm run verify:build`.
   - Lukt de `noindex`-check in `document.head` niet: R4.
6. **Documentatie.** Werk RUNBOOK §16 bij (punt 8 en 9).
7. **Handmatige rooktest** (als de lokale stack met Docker beschikbaar is; anders noteer je dat in `deviations.md` en sla je deze stap over):
   - `supabase start` en `web/.env` op de lokale stack;
   - een gebruiker via Studio en een spot via `cd ingest && uv run shakka spots sync`;
   - een sessie met de SQL uit RUNBOOK §16.9 in Studio (rol `postgres`);
   - `npm run build && npm run preview` en open `/s/<slug>`;
   - meld je aan als `  Test  `, wijzig naar "Ik kan mensen meenemen" met 2 plekken, en meld je af;
   - controleer in de devtools (Network) dat elke `rpc/…`-call een POST is en de token alleen in de request-body staat, nooit in de URL;
   - controleer in Application → Local Storage de sleutel `shakka:rsvp:<slug>` (weg na afmelden), en controleer de `<meta name="robots" content="noindex">` in Elements;
   - controleer `/s/bestaat-niet-123` ("Sessie niet gevonden") en `/s/kort`.
8. **Eindcontrole.**
   - `cd web && npm ci && npm run check && npm test && npm run build && npm run verify:build`;
   - vanuit de root `bash scripts/check-no-client-openmeteo.sh` (exit 0);
   - `grep -rEn "googletagmanager|google-analytics|plausible|fonts.googleapis|cdn\." web/src web/static` geeft niets;
   - `grep -rn "\.rpc(" web/src` geeft alleen `web/src/lib/rsvp.ts`;
   - `grep -rn "{@html" web/src` geeft niets;
   - `cd ingest && uv run pytest`;
   - `git status`: geen `web/.env`, `web/build` of `node_modules` gestaged; `git diff --stat $(git merge-base origin/develop HEAD)` raakt alleen bestanden uit de tabel "Bestanden", en geen van de drie WP-20-namen hierboven.
9. **Integratie met WP-20 (A20; pas na de merge van WP-20 in `develop`).**
   - Controleer met `git fetch origin && git ls-tree origin/develop web/src/lib/session-model.ts web/src/lib/browser-storage.ts` dat WP-20 gemerged is (beide paden moeten in de uitvoer staan). Zo niet: noteer in `deviations.md` "stap 9 open: wacht op merge WP-20" en stop hier; de orchestrator laat deze stap uitvoeren zodra WP-20 gemerged is. De WP-21-PR merget niet vóór stap 9.
   - `git rebase origin/develop`. Bij een conflict in `web/test/user-tables.test.ts`: neem de WP-20-versie en vervang daarin alleen `it('no file uses .rpc(', …)` door de allowlist-test met `RPC_FILES` (R3). Bij een conflict in `docs/RUNBOOK.md`: behoud beide toevoegingen. Wijzig geen andere WP-20-bestanden.
   - Draai `npm run check && npm test` vóór de vervangingen hieronder: alles groen (ook de WP-20-tests).
   - Lees in de gemergde code `session-model.ts`, `time.ts` (`formatWindowLocal`) en `browser-storage.ts`, en vervang alleen waar het gedrag gelijk is aan wat "Consistentie met afhankelijke WP's", WP-20, beschrijft. Elke vervanging hieronder is los terug te draaien:
     - **(9a) `session-view.ts`, slug en code points.** Verwijder de eigen `SESSION_SLUG_RE`, `isValidSessionSlug` en `countCodePoints`. Voeg toe:
       ```ts
       export { SESSION_SLUG_RE, isValidSessionSlug, countCodePoints } from './session-model.js';
       import { countCodePoints } from './session-model.js'; // used by parseRsvpForm
       ```
       Gebruikt `session-view.ts` zelf ook `SESSION_SLUG_RE` of `isValidSessionSlug`, neem die dan ook in de lokale `import` op. De namen blijven gelijk, dus `rsvp.ts`, `rsvp-storage.ts`, `public-session-data.ts`, `rsvp-contract.test.ts` en `session-view.test.ts` importeren ongewijzigd uit `session-view.js`.
     - **(9b) `session-view.ts`, venster.** Voeg `import { formatWindowLocal } from './time.js';` toe. De body van `sessionWindowText` wordt `return formatWindowLocal(new Date(startsAt), new Date(endsAt));`. Imports die daarna ongebruikt zijn (`formatLocal`, `localDateKey`) gaan weg.
     - **(9c, optioneel) `session-view.ts`, Tikkie.** Voeg `safeTikkieLink` toe aan de lokale import uit `./session-model.js`. De body van `tikkieLink` wordt `return safeTikkieLink(url)?.href ?? null;`. `TIKKIE_PREFIX` blijft staan als export. Verschil met de eigen regel: WP-20 eist ook geen witruimte (`\S+`) en hoogstens 200 tekens. De DB-CHECK verbiedt beide al, dus het zichtbare gedrag is gelijk (review ronde 2, N-2).
     - **(9d) `rsvp-storage.ts`, type.** Verwijder de eigen `export type StorageLike = …`. Voeg toe `import type { StorageLike } from './browser-storage.js';` en `export type { StorageLike } from './browser-storage.js';`.
     - **`browserStorage` blijft staan** in `rsvp-storage.ts` (geeft `null`; WP-20 geeft `undefined`, A20). Niet vervangen; het is een opruimpunt ("Gevolgen voor latere WP's").
   - Criterium voor "gelijk": de bestaande tests in `session-view.test.ts`, `rsvp-storage.test.ts`, `rsvp-contract.test.ts`, `rsvp-flow.test.ts` en `public-session-page.test.ts` blijven **zonder wijziging** groen, en `npm run check` slaagt. Faalt er een door een vervanging, draai die ene vervanging terug, laat de eigen helper staan en noteer het in `deviations.md` (R10, opruimpunt).
   - Controleer dat er geen importcyclus is (`npm run check`; `session-model.ts` importeert alleen `time.ts`), en na (9a) dat `grep -n "function countCodePoints\|function isValidSessionSlug\|SESSION_SLUG_RE = " web/src/lib/session-view.ts` niets geeft.
   - Eindcontrole uit stap 8 opnieuw. Commit: `WP-21: reuse WP-20 session helpers after rebase`.

**Nodig van Lars (AC-7):**
- `supabase db push` van WP-19 is gedaan (RUNBOOK §16.2), en Cloudflare Pages draait (WP-13/WP-14);
- een testsessie volgens RUNBOOK §16.9 (of via WP-20 als dat al gemerged is). Open de link in WhatsApp op een telefoon zonder in te loggen, en meld je aan, wijzig en meld je af;
- een reactie op de voorstellen A13 (privacyregel met 7 dagen) en A10 (0 t/m 8 plekken, met "Geen (auto zit vol)").

## Verwerking review
### Ronde 2 (revisie 3)
Review ronde 2 (`docs/wp/WP-21/review.md`, CHANGES_REQUIRED), met de beslissingen van de orchestrator. Een gerichte revisie; de rest van de blueprint is ongewijzigd.

| Punt | Verwerking |
|---|---|
| **B-1** (blokkerend): flow- en paginatests met de echte klok, fixtures in het verleden | Overgenomen zoals voorgesteld. Nieuwe alinea "Vaste klok in de pagina- en flowtests" in het Testplan: `vi.useFakeTimers({ toFake: ['Date'] })` en `vi.setSystemTime(new Date(NOW))` in `beforeEach` van `rsvp-flow.test.ts`, `public-session-page.test.ts` en `public-session-page-integration.test.ts`; de drie tabelcellen verwijzen ernaar. Test (j) doet eerst `vi.useRealTimers()` en zet daarna zijn eigen klok en timers. `afterEach` had `vi.useRealTimers()` al. N-1 uit ronde 1 blijft: `applyRefresh` zet `now = new Date()` en de klok-`$effect` gaat 1 s na `ends_at` af; de alinea verbiedt de builder expliciet om dat weg te halen als oplossing. |
| N-1: WP-20-helpernamen kloppen niet | Overgenomen. Nagelopen in de WP-20-blueprint revisie 2 (r. 100, 104, 191–208, 265, 296–309). A20, de commentaarregels in `session-view.ts` en `rsvp-storage.ts`, "Consistentie" (WP-20) en stap 9 gebruiken nu de echte namen: `SESSION_SLUG_RE`, `isValidSessionSlug` en `countCodePoints` uit `#lib/session-model.ts` (herexport in `session-view.ts`, stap 9a), en `StorageLike` uit `#lib/browser-storage.ts` (stap 9d). `browserStorage` blijft de eigen versie (`null`; WP-20 geeft `undefined`), zoals de reviewer voorstelt, omdat `rsvp-storage.test.ts` niet mag veranderen; dat staat als opruimpunt in "Gevolgen voor latere WP's". De `git ls-tree`-controle noemt nu `web/src/lib/browser-storage.ts` in plaats van `local-prefs.ts`. De onjuiste bewering in A20 ("geeft `null` en niet `undefined`", als WP-20-gedrag) is weg. Optioneel hergebruik van `safeTikkieLink` is stap 9c. |
| N-2: WP-20-blueprint beschrijft WP-21 nog als revisie 1 | Alleen genoteerd: de orchestrator werkt de tekst in WP-20 bij (`safeHttpsLink` en de volle `sessionWindowText`-notatie bestaan in WP-21 niet meer). Het optionele voorstel uit dit punt is verwerkt als stap 9c (`tikkieLink` → `safeTikkieLink(url)?.href ?? null`). |
| N-3: `rerender` in (13) hangt af van de klok | Opgelost door B-1. Een korte zin bij `rsvp-flow.test.ts` (13) zegt dat de `rerender` `now` terugzet op `NOW` en de sessie open blijft. |

### Ronde 1 (revisie 2)
Review ronde 1 (CHANGES_REQUIRED), met de beslissingen van de orchestrator. Let op: wat de tabel hieronder over de WP-20-namen en `browserStorage` zegt (N-9), is in ronde 2 gecorrigeerd (zie hierboven en A20).

| Punt | Verwerking |
|---|---|
| **B-1** (blokkerend): drie bestanden botsen met WP-20 | Overgenomen. Hernoemd: `web/src/lib/session-page-data.ts` → `web/src/lib/public-session-data.ts` (`SessionPageData` → `PublicSessionPageData`, `loadSessionPage` → `loadPublicSessionPage`), `web/test/session-page-data.test.ts` → `web/test/public-session-data.test.ts`, `web/test/fixtures/session-data.ts` → `web/test/fixtures/public-session.ts` (`sessionPageData()` → `publicSessionPageData()`). Voor de duidelijkheid ook `session-page.test.ts` → `public-session-page.test.ts` en `session-page-integration.test.ts` → `public-session-page-integration.test.ts` (botsten niet, maar stonden naast WP-20's `session-page-data.test.ts`). Alle verwijzingen aangepast: lagenschets, `+page.ts`, tabel "Bestanden", Testplan, `session-no-auth.test.ts`, "Gevolgen" (WP-23-axe) en het stappenplan. De WP-20-blueprint is nagelopen op `session-*`-namen, `time.ts`-helpers en `fake-supabase.ts`: WP-21 maakt geen WP-20-bestand aan en wijzigt `time.ts` en `fake-supabase.ts` niet. De alinea onder "Bestanden" en "Consistentie" (WP-20) beschrijven de echte overlap; R3 is herschreven (`user-tables.test.ts` en `RUNBOOK.md`; `app.css` raakt alleen WP-21, want WP-20 gebruikt `<style>`-blokken). Volgorde: WP-20 merget eerst, WP-21 rebaset en hergebruikt identieke helpers (A20, stap 9, R10). De builder-instructie verbiedt de drie WP-20-namen expliciet, en de eindcontrole controleert dat. |
| N-1: "gesloten" volgt `session_closed` en `ends_at` niet | Overgenomen. `now` is een overschrijfbare `$derived`; `applyRefresh` zet `now = new Date()`, en een klok-`$effect` zet `now` 1 seconde na `ends_at` (A5, E46). `RsvpPanel` heeft `serverClosed`, gezet bij `session_closed` van `rsvp_create` en `rsvp_update`; `isClosed = closed \|\| serverClosed` verbergt formulier en Wijzigen (E15). Tests: `public-session-page.test.ts` (j), `rsvp-flow.test.ts` (18) en (19). |
| N-2: vaste "7 dagen" op "Sessie niet gevonden" | Overgenomen: `{SESSION_RETENTION_DAYS}` in de markup, getest in `public-session-page.test.ts` (d). |
| N-3: tekst `session_full` klopt niet met de telling | Overgenomen: "Deze sessie zit vol: naast de organisator kunnen hoogstens 30 mensen zich aanmelden." Test: de tekst bevat `String(MAX_RSVPS)` en `organisator`. |
| N-4: contracttest leest alleen één migratie | Overgenomen (variant 2 uit de review, zoals `session-schema.test.ts` van WP-20): driftcheck (0) faalt zodra een latere migratie een van de vijf functienamen noemt of `public.rsvps` wijzigt, met de melding om `rsvp-types.ts` en de test bij te werken. (2) begint het RSVP-stuk expliciet ná de letterlijke `'rsvps',`. (5) kijkt nu alleen naar de blokken van `rsvp_create`, `rsvp_update` en `rsvp_delete`. |
| N-5: geen standaardantwoord voor `getPublicSession` in `rsvp-flow.test.ts` | Overgenomen: `mockResolvedValue({ session: SESSION_INFO, rsvps: [4 fixtures] })` in `beforeEach`, overschrijven met `mockResolvedValueOnce`. |
| N-6: Tikkie-host | Beslissing orchestrator: alleen `https://tikkie.me/...`. `safeHttpsLink` is vervangen door `tikkieLink` (prefix `https://tikkie.me/`, minstens één teken erna, `hostname === 'tikkie.me'`), A14, E38, tests in `session-view.test.ts` en `public-session-page.test.ts` (h). De tekst "(link naar tikkie.me)" blijft. Dezelfde regel komt via de orchestrator in WP-20 (genoteerd bij "Consistentie" en "Gevolgen"). |
| N-7: `<option>` kan geen `<bdi>` bevatten | Overgenomen: optietekst via `isolateText` (FSI/PDI, A11, E49). De flowtest kiest de optie op waarde. |
| N-8: RPC zonder timeout | Overgenomen: `.abortSignal(AbortSignal.timeout(RPC_TIMEOUT_MS))` met `RPC_TIMEOUT_MS = 15_000`, alleen als `AbortSignal.timeout` bestaat (A6, E47, E48). Geverifieerd in postgrest-js: `abortSignal` zet het signaal op de fetch, en een rejectende fetch resolvet met `status: 0`. `fake-rpc.ts` geeft nu een thenable builder met `abortSignal` die het signaal vastlegt; `argCount` blijft 2. R5 noemt de timeout als extra bron van een dubbele RSVP. |
| N-9: dubbele logica naast WP-20 | Overgenomen via A20, A21 en stap 9. De vensternotatie van WP-21 is nu exact die van `formatWindowLocal` (WP-20/WP-08), zodat de helper na de rebase vervangen kan worden. Ook `browserStorage` geeft nu `null` zoals in WP-20. Stap 9 vervangt slugregex, `countCodePoints`, `sessionWindowText`-body en `browserStorage` door de WP-20-helpers als het gedrag gelijk is; anders volgt het opruimpunt in "Gevolgen" (R10). |
| N-10: opslagranden | (a) Geaccepteerd en gedocumenteerd bij A7 (en verwezen vanuit A15). (b) Overgenomen: `rsvp-storage.ts` heeft een geheugenfallback per slug, gevuld als schrijven mislukt. Daardoor overleeft `stored` een `refreshAll()` bij hervatten en blijft de tekst "zolang deze pagina open is" kloppen (E26). Tests in `rsvp-storage.test.ts` en `rsvp-flow.test.ts` (13). |
| N-11: AC-2 en de interne `auth.getSession()` van supabase-js | Overgenomen als notitie bij AC-2 in "Per acceptatiecriterium", voor de verifier. |
| N-12: `aria-labelledby` naar een kop die er niet is | Overgenomen: `aria-labelledby` alleen als er een kop is (`stored \|\| !isClosed`). Test: `rsvp-flow.test.ts` (15). |
