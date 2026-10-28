# Blueprint WP-25: Moderatie voor organisatoren
Status: DRAFT
Revisie: 1

## Doel
Een organisator beheert de aanmeldingen op zijn eigen sessie zonder Lars en zonder SQL-editor:
1. een aanmelding van iemand anders verwijderen (spam, dubbel, verloren token) via de nieuwe RPC `organizer_delete_rsvp`;
2. het aanmelden sluiten en weer openen (`sessions.rsvps_closed_at`), zonder de sessie te annuleren.

Deelnemers met een token kunnen bij gesloten aanmelden nog wijzigen en afmelden. Scope en contracten: `docs/WORK_PACKAGES_V2.md` § WP-25.

## Aannames
- **A1. "Sessie sluiten" = aanmelden stoppen zonder annuleren.** Dit is de lezing uit de WP-sectie. **Lars bevestigt dit** (WORK_PACKAGES_V2, "Wat Lars moet aanleveren", punt 4). Tot die bevestiging bouwt de builder volgens deze lezing.
- **A2. Verwijderen mag altijd**, ook bij een geannuleerde of afgelopen sessie (binnen de 7 dagen bewaartermijn). Een naam weghalen gaat voor, net als bij `rsvp_delete` (WP-19 A10).
- **A3. Sluiten raakt alleen `rsvp_create`.** `rsvp_update` en `rsvp_delete` blijven ongewijzigd, ook bij gesloten aanmelden. Een deelnemer kan dus nog zijn vervoer wijzigen. Dat is bewust: wijzigen voegt geen nieuwe naam toe.
- **A4. De beheerpagina leest de aanmeldingen via `get_public_session`** (WP-sectie). De organisator ziet dus precies wat iedereen met de link ziet: geen tokens, geen extra velden. Er komt geen lees-RPC voor organisatoren.
- **A5. `SESSION_COLUMNS` krijgt `rsvps_closed_at` bewust niet.** De beheerpagina haalt de status uit `get_public_session` (`rsvps_closed`). Twee redenen:
  - er is één bron voor de status;
  - in de periode tussen de deploy en `supabase db push` zou een select op een kolom die nog niet bestaat, alle sessiepagina's van de organisator breken (PostgREST 42703).
- **A6. `parsePublicSession` accepteert een ontbrekende `rsvps_closed` als `false`.** Om dezelfde reden als A5: een oude database geeft de sleutel niet. Is de sleutel er, maar is het geen boolean, dan volgt `RsvpError('unknown')`.
- **A7. Geen melding aan de verwijderde deelnemer** (Buiten scope in de WP). Opent die de pagina weer, dan wist de bestaande stale-key-regel (WP-21 A7) zijn opgeslagen token. Hij ziet dan het formulier, of de melding "gesloten".
- **A8. De schakelaar staat alleen bij een sessie die niet geannuleerd en niet afgelopen is.** Verwijderen kan altijd (A2). Sluiten en openen vraagt geen bevestiging, want het is omkeerbaar. Verwijderen vraagt wel om bevestiging.
- **A9. "Aanmeldingen beheren" staat in `/mijn-sessies` bij elke getoonde sessie**, ook bij een geannuleerde. Die lijst bevat al alleen komende sessies (`ends_at > now`).
- **A10. Migratietijdstempel `20261028090000`.** Dit is de eerstvolgende vrije tijdstempel (de laatste is `20261016090000`). Merget een andere v2-WP eerder een migratie met een latere tijdstempel, dan verandert er niets. Andersom geldt afspraak 5 (`--include-all`).
- **A11. Docker** zoals WP-19 A13. Zonder Docker komt het pgTAP-bewijs uit de CI-job `db`.

## Ontwerp
**Database.** Er komt één migratie, `20261028090000_organizer_moderation.sql`, met:
- de kolom `rsvps_closed_at` en een kolomgrant voor `authenticated`. De bestaande policy `sessions_update_own` beperkt het bijwerken al tot de eigen sessies, en de tabelbrede `grant select` maakt de kolom leesbaar;
- `create or replace` van `get_public_session` en `rsvp_create`. Postgres behoudt dan eigenaar en rechten ([bron](https://www.postgresql.org/docs/17/sql-createfunction.html)). Toch herhaalt de migratie expliciet de `revoke` en `grant`, zodat de rechten in het bestand zelf leesbaar zijn (afspraak 2);
- de nieuwe RPC `organizer_delete_rsvp`, `security definer`. Hij controleert zelf `sessions.organizer_id = auth.uid()`, want als eigenaar valt hij niet onder RLS. Net als `rsvp_delete` zet hij eerst `for update` op de sessierij (WP-19 A12), zodat alle schrijfacties per sessie na elkaar lopen. Hij geeft `false` bij elke weigering: onbekend id, niet van jou, niet ingelogd of `null`. Zo verraadt hij niets over het bestaan van een id.

**Contractbewaking.** De drift-check (0) in `rsvp-contract.test.ts` verbiedt nu dat een latere migratie de sessie-RPC's noemt. Hij wordt omgebouwd naar een lijst `CONTRACT_FILES`:
- `fnBlock` leest steeds de laatste definitie;
- alleen het WP-25-bestand mag `get_public_session` en `rsvp_create` noemen;
- elke andere latere migratie blijft verboden terrein.

`session-schema.test.ts` krijgt een alter-guard voor `public.sessions`. De guard in `schema-columns.test.ts` dekt `sessions` niet (zijn regex noemt alleen de app-tabellen van `types.ts`) en blijft ongewijzigd.

**Web.**
- Een nieuwe module `lib/moderation.ts` (in `RPC_FILES`) doet de RPC-aanroep op dezelfde manier als `account.ts`: timeout, nooit throwen, geen details loggen. Sluiten en openen loopt via de bestaande `updateOwnSession`, zodat `.from(` en het aantal `.update(` in `user-data.ts` gelijk blijven (`user-tables.test.ts`).
- De nieuwe route `/sessie/[slug]/beheer` volgt het patroon van `/sessie/[slug]/delen`: auth-store, laadtoken en `LoginPrompt`.
- Op `/s/[slug]` krijgt `RsvpPanel` een optionele prop `rsvpsClosed`. Die verbergt alleen het aanmeldformulier; wijzigen en afmelden blijven gekoppeld aan `closed` (geannuleerd of afgelopen).

## Bestanden
| Pad | Actie | Inhoud |
|---|---|---|
| `supabase/migrations/20261028090000_organizer_moderation.sql` | aanmaken | Zie Interfaces. |
| `supabase/tests/11_organizer_moderation.test.sql` | aanmaken | 32 asserts (Testplan AC-1/AC-2). |
| `supabase/tests/07_sessions.test.sql` | wijzigen | `columns_are` + `rsvps_closed_at`; nieuwe `column_privs_are` (SELECT, UPDATE); functielijsten `authenticated` en `prosecdef` + `organizer_delete_rsvp`; `plan(113)`. |
| `supabase/tests/08_session_rpcs.test.sql` | wijzigen | Regel 36: `('rsvps_closed')` toevoegen aan de sessiesleutels. Het plan blijft 71. |
| `supabase/tests/01_schema.test.sql` | wijzigen | Kolom-`set_eq` + `('sessions', 'rsvps_closed_at', 'timestamp with time zone', true)`. Het plan blijft 70. |
| `web/src/lib/moderation.ts` | aanmaken | `MODERATION_MESSAGES`, `deleteRsvpAsOrganizer`, `setRsvpsClosed`. |
| `web/src/lib/session-model.ts` | wijzigen | `SessionUpdate` + `rsvps_closed_at?: string \| null`. |
| `web/src/lib/rsvp-types.ts` | wijzigen | `PUBLIC_SESSION_KEYS` + `'rsvps_closed'` (laatste), `PublicSessionInfo.rsvps_closed: boolean`, commentaar bovenaan noemt beide migraties. |
| `web/src/lib/session-view.ts` | wijzigen | Parser (A6), `RSVPS_CLOSED_MESSAGE`, nieuwe tekst `RSVP_MESSAGES.session_closed`. |
| `web/src/lib/session-page-data.ts` | wijzigen | `ManagePageData` en `loadManagePage`. |
| `web/src/lib/components/RsvpPanel.svelte` | wijzigen | Prop `rsvpsClosed = false`; die verbergt alleen het aanmeldformulier. |
| `web/src/routes/s/[slug]/+page.svelte` | wijzigen | Banner bij `rsvps_closed`; `rsvpsClosed` doorgeven aan `RsvpPanel`. |
| `web/src/routes/sessie/[slug]/beheer/+page.ts` | aanmaken | `load = ({ params }) => ({ slug: params.slug })`. |
| `web/src/routes/sessie/[slug]/beheer/+page.svelte` | aanmaken | Beheerpagina (zie Interfaces). |
| `web/src/routes/mijn-sessies/+page.svelte` | wijzigen | De link "Aanmeldingen beheren" bij elke sessie (A9). |
| `web/src/routes/privacy/+page.svelte` | wijzigen | Eén bijzin bij "Als je je aanmeldt voor een sessie" (zie Interfaces). |
| `web/test/rsvp-contract.test.ts` | wijzigen | `CONTRACT_FILES`, de drift-check (0) herzien, test (9) (zie Interfaces). |
| `web/test/session-schema.test.ts` | wijzigen | De alter-guard voor `sessions` (zie Interfaces). |
| `web/test/user-tables.test.ts` | wijzigen | `RPC_FILES` + `'lib/moderation.ts'`. |
| `web/test/moderation.test.ts` | aanmaken | Unit- en contracttests van `moderation.ts`. |
| `web/test/manage-page.test.ts` | aanmaken | Componenttests van `/sessie/[slug]/beheer` (AC-4). |
| `web/test/session-page-data.test.ts` | wijzigen | Tests van `loadManagePage`. |
| `web/test/public-session-page.test.ts` | wijzigen | AC-5. |
| `web/test/session-view.test.ts` | wijzigen | De parser met `rsvps_closed`. |
| `web/test/my-sessions-page.test.ts` | wijzigen | De link naar de beheerpagina. |
| `web/test/a11y-session-pages.test.ts` | wijzigen | Een geval voor `/sessie/[slug]/beheer`. |
| `web/test/fixtures/public-session.ts` | wijzigen | `SESSION_INFO.rsvps_closed: false`. Ook elke andere getypte `PublicSessionInfo` in de tests krijgt het veld. |
| `docs/RUNBOOK.md` | wijzigen | §16.5 en §16.8 (derde bullet) herschrijven, plus de nieuwe §16.10 (zie Interfaces). |
| `docs/PRIVACY.md` | wijzigen | Rij "Georganiseerde sessies": + `rsvps_closed_at`. Rij "Aanmeldingen": bewaard "Tot afmelden of verwijdering door de organisator; …", verwijderd door "`rsvp_delete`, `organizer_delete_rsvp`; cascade via `sessions`". |

Ongewijzigd blijven `ingest/` (`TABLE_KEYS` en `db_usage` blijven gelijk, afspraak 1), `web/test/schema-columns.test.ts` en `_headers`. `docs/STATUS.md` werkt de orchestrator bij.

## Interfaces en contracten

### Migratie `20261028090000_organizer_moderation.sql`
Volgorde en inhoud liggen vast. Het commentaar en de code van dit bestand noemen **nooit** `rsvp_update`, `rsvp_delete` of `purge_expired_sessions`, en bevatten nergens `public.rsvps` tussen een `grant` en de volgende `;` (`test_no_grants_on_rsvps`).
```sql
-- WP-25: organizer moderation. An organizer closes and reopens sign-ups on an own session
-- (rsvps_closed_at) and removes any RSVP on an own session (organizer_delete_rsvp).
-- Closing only blocks new RSVPs; edits and sign-offs with a valid token keep working.

alter table public.sessions add column rsvps_closed_at timestamptz null;
grant update (rsvps_closed_at) on table public.sessions to authenticated;
```
Daarna volgt `create or replace function public.get_public_session(p_slug text)`. De body is letterlijk die uit `20261015200000_sessions.sql` (r. 131–181), met precies één wijziging: na `'cancelled', s.cancelled_at is not null` komt
```sql
      'cancelled', s.cancelled_at is not null,
      'rsvps_closed', s.rsvps_closed_at is not null
```
Daarna volgt `create or replace function public.rsvp_create(p_slug text, p_first_name text, p_ride text, p_seats_offered integer)`. Ook die body is letterlijk die uit r. 184–234, met precies één wijziging in stap 3:
```sql
  if not found or s.cancelled_at is not null or s.rsvps_closed_at is not null
     or s.ends_at <= now() then
    raise sqlstate 'PT400' using message = 'session_closed';
  end if;
```
Daarna volgt de nieuwe RPC:
```sql
-- Remove one RSVP on a session of the caller. false for unknown, foreign, null or signed out,
-- so the result never reveals whether an id exists. rides_with of riders is cleared by the FK.
create function public.organizer_delete_rsvp(p_rsvp_id uuid)
returns boolean
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_uid uuid := auth.uid();
  v_session uuid;
begin
  if v_uid is null or p_rsvp_id is null then
    return false;
  end if;
  select r.session_id into v_session
    from public.rsvps r
    join public.sessions s on s.id = r.session_id
   where r.id = p_rsvp_id and s.organizer_id = v_uid;
  if not found then
    return false;
  end if;
  perform 1 from public.sessions s where s.id = v_session for update;
  delete from public.rsvps r where r.id = p_rsvp_id and r.session_id = v_session;
  return found;
end;
$$;

revoke all on function public.get_public_session(text)
  from public, anon, authenticated, service_role;
revoke all on function public.rsvp_create(text, text, text, integer)
  from public, anon, authenticated, service_role;
revoke all on function public.organizer_delete_rsvp(uuid)
  from public, anon, authenticated, service_role;
grant execute on function
  public.get_public_session(text),
  public.rsvp_create(text, text, text, integer)
to anon, authenticated;
grant execute on function public.organizer_delete_rsvp(uuid) to authenticated;
```

### Rechten na WP-25 (wat pgTAP vastlegt)
| Object | `anon` | `authenticated` | `service_role` |
|---|---|---|---|
| `sessions.rsvps_closed_at` | – | SELECT, UPDATE (RLS: eigen rijen) | – |
| `organizer_delete_rsvp(uuid)` | – | EXECUTE | – |

Functielijsten in `07_sessions.test.sql`:
- `authenticated`: `get_public_session`, `rsvp_create`, `rsvp_update`, `rsvp_delete`, `delete_my_account` en `organizer_delete_rsvp`;
- `prosecdef`: de huidige acht plus `organizer_delete_rsvp`;
- de lijsten voor `anon` en `service_role` blijven ongewijzigd.

### RPC-contract (aanvulling op WP-19)
| RPC | Rollen | Body | Resultaat |
|---|---|---|---|
| `organizer_delete_rsvp` | authenticated | `{"p_rsvp_id": uuid}` | `true` (verwijderd) of `false` |

`get_public_session`: het object `session` heeft 12 sleutels, de 11 van WP-19 plus `"rsvps_closed": boolean`. `rsvp_create`: dezelfde signatuur en foutcodes; `session_closed` ook als `rsvps_closed_at is not null`.

### `web/src/lib/moderation.ts`
```ts
export const MODERATION_RPC_TIMEOUT_MS = 15_000;
export const MODERATION_MESSAGES = {
	deleted: 'Aanmelding verwijderd.',
	alreadyGone: 'Deze aanmelding bestond al niet meer.',
	failed: 'Verwijderen is niet gelukt. Probeer het later opnieuw.',
	network: 'Verwijderen is niet gelukt: geen verbinding met de server. Probeer het opnieuw.',
	open: 'Aanmelden is open.',
	closed: 'Aanmelden is gesloten. Nieuwe mensen kunnen zich niet aanmelden; wie al aangemeld is, kan zich nog afmelden.',
	closeButton: 'Aanmelden sluiten',
	openButton: 'Aanmelden weer openen'
} as const;

/** Never throws. UUID_RE fails -> { ok: false, error: failed } without a request.
 *  supabase.rpc('organizer_delete_rsvp', { p_rsvp_id }) with abortSignal(AbortSignal.timeout(...)) like account.ts.
 *  data === true -> { ok: true }; data === false -> { ok: false, error: alreadyGone };
 *  thrown or status 0 -> network; any other error or non-boolean data -> failed.
 *  On every failure exactly one console.warn('organizer delete failed') without details. */
export async function deleteRsvpAsOrganizer(rsvpId: string): Promise<{ ok: boolean; error?: string }>;

/** updateOwnSession(sessionId, { rsvps_closed_at: closed ? now.toISOString() : null }). Throws DataError like updateOwnSession. */
export function setRsvpsClosed(sessionId: string, closed: boolean, now: Date = new Date()): Promise<void>;
```
Imports: `supabase` uit `#lib/supabase.js`, `UUID_RE` uit `./session-view.js` en `updateOwnSession` uit `./user-data.js`. Geen `.from(`; `supabase.rpc(` staat er precies één keer in.

### `web/src/lib/session-model.ts`
`export type SessionUpdate = Partial<NewSession> & { cancelled_at?: string; rsvps_closed_at?: string | null };`. `SESSION_COLUMNS` en `SESSION_EDITABLE_COLUMNS` blijven ongewijzigd (A5).

### `web/src/lib/session-view.ts`
- `parsePublicSession`: `const rc = s.rsvps_closed;`. Is `rc` `undefined`, dan geldt `false`. Is het geen boolean, dan volgt `RsvpError('unknown', op)`. `session.rsvps_closed` komt als laatste veld.
- `export const RSVPS_CLOSED_MESSAGE = 'De organisator heeft het aanmelden gesloten.';`
- `RSVP_MESSAGES.session_closed = 'Dit kan niet meer: de sessie is geannuleerd of voorbij, of het aanmelden is gesloten.'`

### `web/src/lib/session-page-data.ts`
```ts
export type ManagePageData =
	| { kind: 'ok'; session: SessionRow; spotName: string; rsvps: PublicRsvp[]; rsvpsClosed: boolean }
	| { kind: 'not_found' }
	| { kind: 'error' };
/** getMySession(slug); null -> not_found (no RPC). Then getPublicSession(slug); null -> not_found.
 *  spotName = public spot_name ?? session.spot_id. Throw -> console.warn('manage page load failed'), error. */
export async function loadManagePage(slug: string): Promise<ManagePageData>;
```

### `RsvpPanel.svelte`
Er komt een prop bij: `rsvpsClosed?: boolean` (standaard `false`). Er wijzigen twee voorwaarden, verder niets:
- de buitenste `#if` wordt `stored || (!isClosed && !rsvpsClosed) || notice || error`. `aria-labelledby` volgt dezelfde voorwaarde;
- de tak met het aanmeldformulier wordt `{:else if !isClosed && !rsvpsClosed}`.

"Wijzigen" en "Afmelden" blijven alleen van `isClosed` afhangen.

### `/s/[slug]/+page.svelte`
- In de bannerketen komt na `{:else if ended}` de tak `{:else if session.rsvps_closed}<div class="banner" role="note"><p>{RSVPS_CLOSED_MESSAGE}</p></div>`.
- De pagina geeft `rsvpsClosed={session.rsvps_closed}` door aan `RsvpPanel`.

### `/sessie/[slug]/beheer/+page.svelte`
- `<title>Aanmeldingen beheren · Shakka</title>`, `<h1>Aanmeldingen beheren</h1>`.
- De toestanden en het laadtoken zijn een kopie van `delen`:
  - `$session === undefined` of laden: "Laden…";
  - `null`: `<LoginPrompt reason="aanmeldingen te beheren" />`, zonder queries;
  - `error`: een banner met "Opnieuw proberen";
  - `not_found`: `<p><strong>Sessie niet gevonden.</strong> Deze sessie bestaat niet (meer), of je bent niet de organisator.</p>` met de link "Naar mijn sessies".
- `ok`:
  1. `<p class="session-summary"><strong>{spotName}</strong> · {formatWindowLocal(...)}</p>`. Bij `cancelled_at` volgt de banner "Deze sessie is geannuleerd." (`role="note"`).
  2. Alleen als de sessie niet geannuleerd is en `Date.parse(ends_at) > Date.now()` (A8): de sectie "Aanmelden", met de tekst `MODERATION_MESSAGES.open` of `MODERATION_MESSAGES.closed` en één knop (`closeButton` of `openButton`). Tijdens het opslaan is de knop `disabled`.
     - Klik: `setRsvpsClosed(session.id, !rsvpsClosed)`.
     - Gelukt: `rsvpsClosed` omdraaien.
     - Fout: `sessionErrorMessage(err)` in `role="status"`, en de status blijft ongewijzigd.
  3. De sectie "Aanmeldingen ({n})". Is de lijst leeg, dan staat er "Nog niemand heeft zich aangemeld."
     - Anders een `<ul>` met per RSVP `<bdi id="rsvp-name-{id}">{first_name}</bdi>`, het label van `rideLabel(r, byId)` en de knop "Verwijderen" met `aria-describedby="rsvp-name-{id}"`.
     - Na een klik vraagt die rij om bevestiging: "Aanmelding van `<bdi>`naam`</bdi>` verwijderen? Diegene krijgt hier geen bericht van.", met de knoppen "Ja, verwijderen" en "Nee". Er staat hoogstens één bevestiging tegelijk open.
     - "Ja, verwijderen" roept `deleteRsvpAsOrganizer(id)` aan; tijdens de aanroep zijn de knoppen `disabled`.
     - `ok`: de rij verdwijnt uit de lokale lijst en `MODERATION_MESSAGES.deleted` verschijnt.
     - `!ok` en `error === alreadyGone`: de rij verdwijnt ook, met die melding.
     - Een andere fout: de rij blijft staan en de foutmelding verschijnt.
     - In alle gevallen sluit de bevestiging. Meldingen staan in één `<p role="status">`.
  4. Links: "Sessiepagina" (`sessionPath(slug)`) · "Mijn sessies".

### `/mijn-sessies`
Elke sessie krijgt, buiten de `cancelled_at`-tak, `<a href="/sessie/{slug}/beheer">Aanmeldingen beheren</a>`.

### `/privacy`
De zin wordt: "Het verdwijnt als je je afmeldt of als de organisator je aanmelding verwijdert, en anders {SESSION_RETENTION_DAYS} dagen na het einde van de sessie."

### `web/test/rsvp-contract.test.ts`
- `const CONTRACT_FILES = ['20261015200000_sessions.sql', '20261028090000_organizer_moderation.sql'] as const;`
- `sql` is de samenvoeging van beide bestanden (gebruikt in (7) en (8)).
- `fnBlock(name)` zoekt de laatste definitie: het loopt `CONTRACT_FILES` van achter naar voren af met `/create (?:or replace )?function public\.<name>\(/`. `params` accepteert ook `or replace`.
- (0a): elke migratie na het WP-19-bestand die niet in `CONTRACT_FILES` staat, noemt geen van de vijf namen en heeft geen `alter table public.rsvps`. De regexen zijn die van nu.
- (0b): in het WP-25-bestand is de verzameling genoemde namen uit die vijf exact `{get_public_session, rsvp_create}`. Ook daar staat geen `alter table public.rsvps`.
- (9): `fnBlock('get_public_session')` bevat `'rsvps_closed', s.rsvps_closed_at is not null`, en `fnBlock('rsvp_create')` bevat `s.rsvps_closed_at is not null`.

### `web/test/session-schema.test.ts` (nieuwe test)
"later migrations change public.sessions only by adding rsvps_closed_at". De test verzamelt in elke migratie na het WP-19-bestand alle treffers van `/alter\s+table\s+(?:if\s+exists\s+)?(?:only\s+)?public\.sessions\b[^;]*?\b(add|drop|rename)\s+column\s+(?:if\s+(?:not\s+)?exists\s+)?(\w+)/gi` als `${file}:${op}:${col}`.
- De verwachte lijst is exact `['20261028090000_organizer_moderation.sql:add:rsvps_closed_at']`.
- Het WP-25-bestand bevat `grant update (rsvps_closed_at) on table public.sessions to authenticated`.
- `SESSION_COLUMNS` bevat `rsvps_closed_at` niet (A5).

### `docs/RUNBOOK.md`
- **§16.5:** "Een aanmelding verwijderen doet de organisator zelf op `/sessie/<slug>/beheer` (vanaf WP-25). Terugvaloptie, of bij misbruik over meerdere sessies: de SQL-editor, met `delete from public.sessions where slug = '<slug>';` (de RSVP's gaan mee) of `delete from public.rsvps where id = '<id>';`."
- **§16.8, derde bullet:** "Een RSVP voor iemand verwijderen: de organisator via 'Mijn sessies' → 'Aanmeldingen beheren'. Anders §16.5."
- **§16.10 "Moderatie (vanaf WP-25)":**
  - wat de organisator kan: verwijderen, sluiten en openen. Sluiten blokkeert alleen nieuwe aanmeldingen;
  - na de merge `supabase db push` voor `20261028090000_organizer_moderation.sql`, vóór de promotie naar `main`. Tot die tijd geeft "Verwijderen" een foutmelding en lukt sluiten niet; `/s/<slug>` blijft werken (A6);
  - bij `PGRST202`: §16.3;
  - de controle van AC-7.

## Edge cases
- E1. `organizer_delete_rsvp(null)`, of geen `sub` in de JWT → `false`; er wordt niets verwijderd.
- E2. B roept het aan op een RSVP in de sessie van A → `false`, en de rij blijft staan (geen verschil met "bestaat niet").
- E3. Een lift-aanbieder wordt verwijderd → de FK zet `rides_with` van zijn meerijders op `null`. Lokaal toont `rideLabel` die meerijders als "Zoekt een lift", want de bestuurder ontbreekt in `byId`.
- E4. Verwijderen bij een geannuleerde of afgelopen sessie → toegestaan (A2). De schakelaar is daar verborgen (A8).
- E5. `rsvp_create` op een gesloten sessie met een ongeldige naam → `invalid_input`, want de invoer wordt eerst gecontroleerd (vaste volgorde, WP-19).
- E6. Gesloten én geannuleerd → `/s/` toont alleen de annuleringsbanner (die gaat voor in de bannerketen).
- E7. Een deelnemer met een token bij gesloten aanmelden → hij ziet "Wijzigen" en "Afmelden", en beide werken.
- E8. De organisator verwijdert een RSVP die de deelnemer net zelf heeft afgemeld → `false` → `alreadyGone`, en de rij verdwijnt lokaal.
- E9. Een misvormde slug op `/beheer` → `not_found`, zonder query en zonder RPC.
- E10. De sessie loopt af terwijl de beheerpagina open is → de schakelaar blijft zichtbaar tot een herlaadactie. Een update is onschadelijk.
- E11. Een netwerk- of serverfout bij verwijderen → een melding, de rij blijft staan en de bevestiging sluit.
- E12. Een oude database zonder `rsvps_closed` → `rsvps_closed: false` (A6). Een niet-boolean → `RsvpError('unknown')`.
- E13. Snel dubbelklikken op de schakelaar of op "Ja, verwijderen" → de knoppen zijn `disabled` zolang een aanroep loopt, dus er volgt maar één aanroep.
- E14. Uitloggen terwijl de pagina laadt → de `LoginPrompt` verschijnt, en het laadtoken negeert het late resultaat (patroon van `delen`).
- E15. Openen na sluiten → `rsvps_closed_at = null`. `recent_rsvp_creates` blijft ongemoeid, dus de rate limit telt gewoon door.
- E16. `updateOwnSession` raakt 0 rijen (de sessie is net verlopen of verwijderd) → `DataError('not_found')` → `SESSION_ERROR_MESSAGES.notFound`.

## Testplan
**AC-1 en AC-2: `supabase/tests/11_organizer_moderation.test.sql`, `plan(32)`.**
- Fixture (postgres):
  - gebruikers A `aaaaaaaa-…-0a` en B `bbbbbbbb-…-0b`, en de spot `pgtap-mod-spot`;
  - sessie SA `pgtap-mod-sa-01` (van A, start over 1 dag, 4 uur) en SO `pgtap-mod-so-01` (van B, open);
  - RSVP's op SA: R1 "Eva" `offers_ride`, R2 "Bram" `needs_ride` met `rides_with` = R1, en R3 "Cas" `own` met token `repeat('K',43)`.
- De rolwissels gaan zoals in `09`.
- Vorm (1–7): `has_function`, `function_returns` boolean, `is_definer`, `search_path` vastgezet, en `function_privs_are` voor anon `{}`, authenticated `EXECUTE` en service_role `{}`.
- Verwijderen (8–17):
  - anon `throws_ok` 42501;
  - authenticated zonder `sub` → `false`;
  - B op R3 → `false`, en R3 bestaat nog;
  - A met een onbekende uuid → `false`;
  - A met `null` → `false`;
  - A op R1 → `true`, en R1 is weg;
  - R2 bestaat nog, met `rides_with is null`;
  - A nogmaals op R1 → `false`.
- Sluiten (18–22):
  - A insert met `rsvps_closed_at` → 42501;
  - een update van B op SA lukt (`lives_ok`), maar `rsvps_closed_at` blijft `null`;
  - een update van A lukt, en daarna is de kolom gezet.
- Publiek bij gesloten aanmelden, als anon (23–30):
  - SA `rsvps_closed` = `'true'`, SO = `'false'`;
  - `set_eq` van de 12 sessiesleutels;
  - de JSON-tekst matcht niet `(organizer_id|edit_token|email|user_id|recent_rsvp_creates|rsvps_closed_at)`;
  - `rsvp_create` op SA → `PT400`/`session_closed`;
  - `rsvp_create` op SA met een lege naam → `invalid_input`;
  - `rsvp_update` met token K geeft `first_name` "Cas2";
  - `rsvp_delete` met token K → `true`.
- Heropenen (31–32): A zet de kolom op `null`, waarna `rsvp_create` op SA een token van 43 tekens geeft.

**AC-2 en AC-3: bestaande pgTAP-bestanden.**
- `07_sessions.test.sql`: `sessions columns` met de nieuwe kolom, `authenticated column privileges on sessions.rsvps_closed_at`, de twee aangepaste functielijsten.
- `08_session_rpcs.test.sql`: `session keys` met `rsvps_closed`.
- `01_schema.test.sql`: de kolom-`set_eq`.
- `supabase test db` is volledig groen.

**Ingest.** `uv run pytest` blijft groen zonder wijzigingen: `test_no_grants_on_rsvps` en `test_security_definer_functions_pin_search_path` lezen de nieuwe migratie mee.

**AC-4: `web/test/manage-page.test.ts`.** De mock combineert `createFakeSupabase().client.from` met `createFakeRpc().rpc` in één `supabase`-object, zoals in `public-session-page-integration`. De auth-store komt uit `helpers/fake-session.js`.
- `(a) signed out: login prompt, no queries`: "Log in om aanmeldingen te beheren." verschijnt, en `calls` en `rpc.calls` zijn leeg.
- `(b) not my session: not found, no RPC`: de `sessions`-select geeft `null`, er staat "Sessie niet gevonden", en er volgt geen enkele RPC-aanroep (dus ook geen `organizer_delete_rsvp`).
- `(c) delete asks for confirmation, then exactly one call`:
  - na "Verwijderen" is er nog geen RPC-aanroep;
  - na "Ja, verwijderen" volgt precies één `organizer_delete_rsvp` met `{ p_rsvp_id: EVA_ID }`;
  - de rij "Eva" is weg en "Aanmelding verwijderd." staat er.
- `(d) "Nee" cancels without a call`.
- `(e) failure keeps the row`: een PT-fout geeft `failed`, en Eva blijft staan.
- `(f) false removes the row with alreadyGone`.
- `(g) toggle updates only rsvps_closed_at`:
  - zet de `sessions`-respons van de update in de wachtrij als `{ data: [{ id }], error: null }`, anders geeft `updateOwnSession` `not_found`;
  - `writeCalls` geeft precies één call, met de ops exact `[['update', { rsvps_closed_at: <ISO van de vaste tijd> }], ['eq', 'id', SESSION_ROW.id], ['select', 'id']]`;
  - daarna staat de tekst `closed` er, met de knop `openButton`.
- `(h) reopen sends null`.
- `(i) cancelled session: no toggle, delete still there`.
- Fixtures: `SESSION_ROW` en `SESSION_CANCELLED` (`fixtures/session-data.ts`), en `SESSION_JSON` (`fixtures/public-session.ts`) als `get_public_session`-antwoord.

**AC-4 (ondersteunend).**
- `session-page-data.test.ts`, `loadManagePage`:
  - `ok` met `spotName` uit `spot_name`;
  - `not_found` als de select niets geeft (en dan geen RPC);
  - `not_found` als `get_public_session` `null` geeft;
  - `error` plus een `warn` bij een DataError.
- `my-sessions-page.test.ts`, `(h) manage link`: de link "Aanmeldingen beheren" heeft `href` `/sessie/${SLUG}/beheer`, ook bij een geannuleerde sessie.
- `a11y-session-pages.test.ts`, `'/sessie/[slug]/beheer'`: geen axe-violations in de `ok`-toestand.

**AC-5: `public-session-page.test.ts`.**
- `(rsvps closed) notice and no form`: met `session: { ...SESSION_INFO, rsvps_closed: true }` staat `RSVPS_CLOSED_MESSAGE` op de pagina en is er geen knop "Ik ook".
- `(rsvps closed) stored token keeps Afmelden and Wijzigen`: met een opgeslagen RSVP voor `EVA_ID` zijn beide knoppen er.
- `(rsvps closed) cancelled wins`: met beide vlaggen is alleen de annuleringsbanner zichtbaar.
- `session-view.test.ts`:
  - `parsePublicSession reads rsvps_closed`: `true` blijft `true`, een ontbrekende sleutel wordt `false`, en `"yes"` geeft `RsvpError('unknown')`.

**AC-6.**
- `user-tables.test.ts`: `.rpc( occurs only in the allowed modules` met `lib/moderation.ts`.
- `rsvp-contract.test.ts`: (0a), (0b), (2) met `rsvps_closed` en (9) zijn groen.
- `session-schema.test.ts`: de nieuwe guard is groen.
- `moderation.test.ts` (`#lib/supabase.js` gemockt met `createFakeRpc` plus een `from` van `createFakeSupabase`):
  - `sends exactly the migration parameters`: de sleutels zijn gelijk aan de parameters van `organizer_delete_rsvp`, uit de migratie gelezen;
  - `true -> ok`, `false -> alreadyGone`, `PT error -> failed`, `status 0 -> network`, `thrown -> network`, `non-boolean -> failed`;
  - `invalid uuid: no request`;
  - `sets an abort signal`;
  - `warns once without details`;
  - `setRsvpsClosed(true|false)` geeft de exacte update-payload; 0 rijen geeft `DataError('updateOwnSession','not_found')`.

**AC-7.** Valt onder `NEEDS_LARS`: de stappen staan in RUNBOOK §16.10.

## Externe afhankelijkheden
- Geen nieuwe packages.
- Postgres `CREATE OR REPLACE FUNCTION` behoudt eigenaar en rechten, en staat geen andere returntypes of parameternamen toe: https://www.postgresql.org/docs/17/sql-createfunction.html (**zelf gecontroleerd** op 28 oktober 2026). Beide vervangen functies houden hun signatuur, returntype en parameternamen.
- PostgREST `POST /rest/v1/rpc/<naam>`, `PT400` → HTTP 400, en `PGRST202` na een schemawijziging: overgenomen uit WP-19 (https://docs.postgrest.org/en/v14/references/errors.html).
- Supabase: nieuwe functies in `public` krijgen standaard `EXECUTE`, dus eerst een expliciete `revoke`. Overgenomen uit WP-19 (https://supabase.com/docs/guides/database/functions).

## Risico's
- R1. **Deployvenster.** Web staat live vóór `db push`. Dan faalt verwijderen of sluiten met een nette foutmelding, en `/s/` blijft werken dankzij A5 en A6. RUNBOOK §16.10 legt de volgorde vast.
- R2. **Tekstguards op migraties.** Wie in het commentaar van de migratie `rsvp_update` noemt, of `grant … public.rsvps` schrijft, maakt (0b) of `test_no_grants_on_rsvps` rood. Dat staat expliciet bij de migratie.
- R3. **Iemand meldt zich na verwijdering opnieuw aan.** Mitigatie: aanmelden sluiten. De bestaande limieten (30 per sessie, 10 per 10 minuten) blijven gelden.
- R4. **Verouderde lijst.** De beheerpagina ververst niet vanzelf. Een nieuwe aanmelding verschijnt pas na opnieuw openen. Voor de verwachte aantallen (hoogstens 30) is dat acceptabel.
- R5. **Kopiëren van de bodies.** Een overschrijffout in de kopie van `get_public_session` of `rsvp_create` kan het WP-19-gedrag stil veranderen. Mitigatie: de bestaande `08_session_rpcs` draait volledig mee tegen de nieuwe definities, en de contracttests lezen de laatste definitie.

## Buiten scope
- Sessies verwijderen, meldingen aan deelnemers, CAPTCHA en IP-limieten, moderatie door Lars over alle sessies heen, een capaciteitscontrole (WP-sectie).
- Een link naar het beheer op `/s/[slug]` of `/sessie/[slug]/delen`. Die pagina's zijn anoniem of hebben een ander doel.
- Automatisch verversen van de beheerlijst.
- `SESSION_COLUMNS` uitbreiden (A5).

## Gevolgen voor latere WP's
- **WP-31.** Die WP voegt een functie toe aan dezelfde lijsten in `07_sessions.test.sql`. Raakt hij een sessie-RPC, dan:
  - voegt hij zijn migratie toe aan `CONTRACT_FILES` en breidt hij (0b) uit voor zijn eigen bestand;
  - verandert hij `public.sessions`, dan breidt hij de verwachte lijst in de alter-guard van `session-schema.test.ts` uit.
- `get_public_session` heeft nu 12 sessiesleutels. Het actuele contract staat in de laatste definitie (`fnBlock`), niet meer alleen in het WP-19-bestand.
- `RPC_FILES` is `['lib/rsvp.ts', 'lib/account.ts', 'lib/moderation.ts']`.
- `SessionUpdate` kent `rsvps_closed_at`. Wil een latere WP de kolom selecteren, dan wijzigt hij `SESSION_COLUMNS` en de assert "bevat niet" in `session-schema.test.ts`.

## Stappenplan voor de builder
1. **Migratie en contracttests.** Maak de migratie. Werk `01`, `07` en `08` bij en maak `11`. Daarna in web, in dezelfde stap: `rsvp-types.ts` (sleutel en veld), de parser in `session-view.ts` (A6), `fixtures/public-session.ts` en de andere getypte `PublicSessionInfo`'s, `rsvp-contract.test.ts` en de guard in `session-schema.test.ts`. Controle: `supabase test db`, `uv run pytest` en `cd web && npm run check && npm test`.
2. **Publieke pagina.** `RSVPS_CLOSED_MESSAGE`, de nieuwe tekst voor `session_closed`, de prop in `RsvpPanel` en de banner op `/s/[slug]`. Daarbij de tests voor AC-5 en de parser. Controle: `npm run check && npm test`.
3. **`moderation.ts`.** Verder `SessionUpdate`, `RPC_FILES` en `moderation.test.ts`. Controle: `npm test`.
4. **Beheerpagina.** `loadManagePage` met zijn tests, de route `beheer` (`+page.ts` en `+page.svelte`), `manage-page.test.ts` en het a11y-geval. Controle: `npm run check && npm test`.
5. **`/mijn-sessies`.** De link en de test. Controle: `npm test`.
6. **Documentatie.** `/privacy`, `docs/PRIVACY.md` en RUNBOOK §16.5, §16.8 en §16.10.
7. **Eindcontrole.** `supabase test db`, `cd ingest && uv run pytest && uv run ruff check . && uv run ruff format --check .`, `cd web && npm run check && npm test && npm run build`. Noteer onder "Nodig van Lars": de bevestiging van A1, `supabase db push` na de merge, en AC-7.
