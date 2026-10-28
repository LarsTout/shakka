# Review WP-25, ronde 1
Oordeel: APPROVED

## Blokkerend
Geen.

## Niet-blokkerend
N-1: `SESSION_ROW` eindigt op 2026-07-18; zonder vaste klok (`vi.setSystemTime(NOW_SESSIONS)`) verbergt A8 de schakelaar in `manage-page` (g), (h) en het a11y-geval. Noem de vaste tijd expliciet in het testplan.
N-2: De JSDoc van `deleteRsvpAsOrganizer` bevat letterlijk `supabase.rpc(`; wie die kopieert, botst met "`supabase.rpc(` staat er precies één keer in". Formuleer het commentaar zonder `.rpc(`.
N-3: De alter-guard in `session-schema.test.ts` mist `add <kolom>` zonder het woord `column` (geldige Postgres) en een tweede clausule in één `alter table`; maak `column` optioneel en match per clausule, want WP-31 erft deze guard.
N-4: `RsvpPanel.serverClosed` wordt nooit gereset: na een geweigerde aanmelding bij gesloten aanmelden blijft het formulier weg na heropenen tot een herlaadactie. Neem dit op als edge case (gedrag is acceptabel).

## Zelf gecontroleerd
- `07_sessions.test.sql`: `plan(112)` + één `column_privs_are` = 113; `prosecdef`-lijst nu 8 functies (`handle_new_user`, vier sessie-RPC's, `purge_expired_sessions`, `delete_my_account`, `db_usage`) + `organizer_delete_rsvp`; lijsten voor `anon` en `service_role` blijven kloppen door de `revoke … from public, anon, authenticated, service_role`.
- `11_organizer_moderation.test.sql`: 7 + 10 + 5 + 8 + 2 = 32 asserts, gelijk aan `plan(32)`.
- `test_no_grants_on_rsvps` (`grant\s[^;]*\bon\s+(?:table\s+)?[^;]*\bpublic\.rsvps\b`): geen treffer op de nieuwe `grant`-regels (`rsvps_closed_at` en `public.rsvp_create` matchen `public\.rsvps\b` niet). `test_security_definer_functions_pin_search_path` splitst ook op `create or replace function`; alle drie de headers bevatten `set search_path = ''`.
- Drift-check (0b): `\brsvp_delete\b` matcht niet binnen `organizer_delete_rsvp`; de voorgeschreven migratietekst noemt alleen `get_public_session` en `rsvp_create`.
- Test (2): `keysIn` pakt `'rsvps_closed',` als twaalfde sessiesleutel; `indexOf("'rsvps',")` matcht `'rsvps_closed'` niet, dus de slice blijft correct.
- `updateOwnSession` geeft exact de ops `update`, `eq('id')`, `select('id')`, zoals AC-4 (g) verwacht; de nep-client antwoordt standaard `{ data: [] }`, dus de wachtrij in (g) is nodig zoals de blueprint zegt.
- `organizer_delete_rsvp`: `auth.uid()` is schema-gekwalificeerd, alle tabellen `public.`-gekwalificeerd, `false` bij null, geen `sub`, vreemd en onbekend id; lockvolgorde (sessie vóór delete) gelijk aan `rsvp_delete` en `rsvp_update`.
- `rsvp_update` en `rsvp_delete` blijven ongewijzigd; in `RsvpPanel` hangen "Wijzigen" en "Afmelden" alleen aan `isClosed`, dus afmelden en wijzigen met token blijven werken bij gesloten aanmelden.
