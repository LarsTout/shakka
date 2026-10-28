# Review WP-30, ronde 1
Oordeel: APPROVED

## Blokkerend
Geen.

## Niet-blokkerend
N-1: `test_cancel_and_return_in_quiet_gives_nothing` slaagt ook zonder poort (dan zou T1b de staat al herstellen en geeft T2 ook 0 events). Voeg op T1 en T1b de asserts toe: 0 messages en `alert_rows(db)` gelijk aan de stand na T0.
N-2: `quietHourOptions(current)` moet `''` niet toevoegen ("current if non-empty and absent"). Anders staat er naast `<option value="">–</option>` nog een tweede lege optie.
N-3: Leg in de jobtests `seed_favorite(db, USER_X, min_kn=12)` vast, zoals in `test_job_alerts_push.py`. "2× new" met `SPLIT_WINDS` en de overgang naar `improved` zijn alleen met die regel aangetoond (`test_write_order_merge`).
N-4: A1 en A7 staan nog op "Lars bevestigen", terwijl stap 7 het akkoord in `PROJECT_PLAN.md` vastlegt. De orchestrator moet die bevestiging hebben vóór de build.
N-5: De alter-guard in `schema-columns.test.ts` slaat de migraties in `PROFILE_ADD_MIGRATIONS` helemaal over. Beter: in die bestanden alleen `add column` op `profiles` toestaan en de andere tabellen gewoon blijven controleren (WP-24 gebruikt dezelfde lijst).

## Zelf gecontroleerd
- Grants en RLS: `20261015090100_m1_security.sql` geeft `authenticated` op tabelniveau alleen SELECT op `profiles`, plus kolom-UPDATE op vijf kolommen en `profiles_update_own` (using en with check op eigen `user_id`). De nieuwe kolomgrant voegt alleen UPDATE op de twee kolommen toe. Er komt geen INSERT bij, `anon` krijgt niets, en de rijbeperking blijft via de bestaande policy. `table_privs_are` in `02_privileges.test.sql` (authenticated = SELECT) blijft groen, omdat kolomgrants daar niet in meetellen. De nieuwe kolommen vallen onder de tabelbrede SELECT, dus `.select(PROFILE_COLUMNS)` na de update werkt.
- Poort in `run_alerts` (`ingest/src/shakka/jobs/alerts.py`, regels 474–513): de poort komt na `assert plan.diff is not None` en vóór `dry_run`, `assign_new_ids`, `deliver_plan` en `store_plan`. Een stille favoriet krijgt dus geen ids, geen aflevering, geen opslag en geen `messages`. De volgende run berekent de diff tegen de opgeslagen (laatst gemelde) `alert_state`. Bij geboren-en-verdwenen, geannuleerd-en-terug en verbeterd geeft dat 0, 0 en 1 event: geen dubbele en geen verouderde melding. `delete_old_alert_state` (48 uur) raakt een nacht niet. `dry_run` volgt dezelfde regel.
- `FakeSupabase.select` projecteert met `row.get(column)`. Profielrijen zonder de nieuwe sleutels geven dus `None`/`None`, en daaruit volgt "niet stil". Bestaande tests breken niet.
- DST, nagerekend:
  - 28→29-03-2026: 22:00 CET is 21:00 UTC en 07:00 CEST is 05:00 UTC. Dat is 8 uur, 32 kwartieren.
  - 24→25-10-2026: 22:00 CEST is 20:00 UTC en 07:00 CET is 06:00 UTC. Dat is 10 uur, 40 kwartieren.
  - 02:00–03:00: op 29-03 bestaat dat tijdstip niet (0 kwartieren). Op 25-10 valt het tussen 00:00 en 02:00 UTC (8 kwartieren).
  - Run-tijden: T0 = 21:17, T1 = 23:17, T1b = 00:17 en T2 = 07:17 CEST. Dat klopt.
- Privacy: `docs/PRIVACY.md` rij "Profiel" heeft al als bewaartermijn "tot het account wordt verwijderd" via cascade. De nieuwe kolommen vallen daaronder. Logs en de foutregel bevatten geen user-id; `quiet` is alleen een telling.
