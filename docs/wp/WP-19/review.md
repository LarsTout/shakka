# Review WP-19, ronde 1
Oordeel: APPROVED

Ik heb de blueprint naast deze documenten gelegd: de WP-sectie in `WORK_PACKAGES.md`, de bestaande migraties (`m1_schema`, `m1_security`, `push_subscriptions`, `marine_hours`), de pgTAP-bestanden `01`–`05`, `ingest/src/shakka/pipeline.py`, `db.py`, `tests/fakes.py`, `test_pipeline.py`, `test_cli_pipeline.py`, `test_migrations.py`, RUNBOOK §8 en §13, en de "Gevolgen" van WP-11.

Wat ik heb gecontroleerd:
- **Rechten.** `anon` heeft geen tabelrechten. Op `rsvps` heeft geen enkele API-rol rechten. `service_role` mag alleen de purge-RPC uitvoeren, en geen enkele job in `ingest/src` leest `sessions` of `rsvps`. `authenticated` heeft kolomprivileges zonder `slug`, `id`, `created_at` of `recent_rsvp_creates`. Elke functie krijgt eerst `revoke all` en daarna een gerichte grant. Alle `security definer`-functies hebben `set search_path = ''`, en alle namen zijn volledig gekwalificeerd of komen uit `pg_catalog`.
- **Tokens.** Een token is 32 bytes uit `gen_random_bytes`, base64url van 43 tekens (44 tekens base64 zonder regeleinde, min de `=`-padding). Opgeslagen wordt alleen de sha256-hash, met een unique index. De vergelijking gaat via een hash-lookup.
- **Rate limits.**
  - Het RSVP-limiet via `recent_rsvp_creates` is niet te omzeilen. Alleen de RPC schrijft de kolom (test 85 toont dat de organisator hem niet kan wijzigen), en afmelden telt mee.
  - Het sessielimiet is ook niet te omzeilen. `created_at` is niet schrijfbaar en verwijderen kan niet. Bij een insert van meerdere rijen werkt de telling dankzij een `VOLATILE` row-level `BEFORE`-trigger. De advisory lock serialiseert de inserts, en in READ COMMITTED krijgt elk statement een nieuwe snapshot, dus de telling klopt ook bij gelijktijdige inserts.
  - Via de RLS-telling in de invoker-trigger lekt niets over het aantal sessies van een andere organisator.
- **Concurrency.** Elke schrijvende RPC zet eerst `for update` op de sessierij. Daardoor zijn er geen deadlock-volgordes en kloppen de tellingen exact.
- **`get_public_session`.** Geeft geen `organizer_id`, `user_id`, e-mail, hashes, `cancelled_at` of `recent_rsvp_creates` terug.
- **Foutcontract.** `PT400` geeft HTTP 400 met `code: "PT400"`; geverifieerd tegen de PostgREST v14-docs (lokaal draait v14.18).
- **Postgres 17.** `ON DELETE SET NULL (rides_with)` bestaat (remote draait 17.11). `WITH CHECK` wordt na de `BEFORE`-triggers afgedwongen.
- **Asserts.** De nummering van de pgTAP-asserts telt op tot `plan(107)` en `plan(62)`. De fixtures en de volgorde van de asserts in `08` leveren de verwachte uitkomsten op.
- **Gewijzigde tests.** Het verwijderen van `test_no_later_milestone_tables` en het vervangen van `[-1]` door opzoeken op naam zijn terecht.

Ik vond geen blokkerende punten. Wel zijn er een paar dingen die de builder of de planner beter meteen meeneemt.

## Blokkerend
Geen.

## Niet-blokkerend
**N-1: Eén bestaande test breekt en staat niet in het plan.**
- Waar: Bestanden/Testplan, `test_pipeline.py`.
- Probleem: `test_spots_sync_failure_continues` (regel 519) controleert `[s.status for s in report.steps[1:]] == ["ok"] * 5`. Met `sessions_cleanup` erbij zijn dat 6 stappen, dus de test wordt rood.
- Voorstel: zet de wijziging in het testplan, als `* 6` of liever als `all(s.status == "ok" for s in report.steps[1:])`. Dan hoeft de builder niets zelf te bedenken.

**N-2: RUNBOOK §8.2 spreekt het ontwerp tegen.**
- Waar: RUNBOOK-wijzigingen.
- Probleem: §8.2 zegt dat elke nieuwe tabel grants krijgt, "ook aan `service_role`, anders kan de ingest er niet bij". Dit ontwerp geeft `service_role` bewust geen rechten op `sessions` en `rsvps` (A5). Alleen §16.6 zegt dat.
- Voorstel: vul §8.2 aan met de uitzondering: geen grants aan `service_role` als de ingest de tabel niet nodig heeft, met `sessions` en `rsvps` als voorbeeld en een verwijzing naar §16.

**N-3: pgcrypto in een ander schema geeft pas een fout bij gebruik.**
- Waar: migratie, R3.
- Probleem: `create extension if not exists pgcrypto with schema extensions` doet niets als pgcrypto remote al in een ander schema staat. Omdat plpgsql function bodies pas bij het uitvoeren controleert, faalt `rsvp_create` dan pas bij de eerste RSVP.
- Voorstel: zet direct na de `create extension` een guard, bijvoorbeeld een `do $$ … $$`-blok dat `raise exception` geeft als `pg_extension.extnamespace` voor pgcrypto niet `extensions` is. Dan faalt `db push` zichtbaar, en de handmatige check in RUNBOOK §16.2 wordt een vangnet in plaats van de enige bescherming.

**N-4: Een sessie ver in de toekomst omzeilt de bewaartermijn.**
- Waar: CHECKs op `sessions`, A1.
- Probleem: er is geen bovengrens voor `starts_at`. Een organisator kan een sessie in 2099 aanmaken, of `starts_at`/`ends_at` later zo bijwerken. De RSVP's blijven dan in de praktijk onbeperkt bewaard. Dat schuurt met de privacybelofte "7 dagen na het einde" (WP-23).
- Voorstel: overweeg een CHECK zoals `starts_at < created_at + interval '30 days'`; die geldt ook bij updates. Of leg het expliciet vast als risico en verwijs naar WP-20/WP-23.

**N-5: Een paar edge cases hebben geen test.** Allemaal klein; het kost een paar asserts:
- E28 en E30 zijn alleen getest met een geannuleerde sessie, niet met een afgelopen sessie (`rsvp_update` op `R_ENDED_DRIVER` → `session_closed`; `rsvp_delete` met `repeat('E',43)` → `true`).
- E14: `null`, een te korte en een te lange slug.
- E18: `p_seats_offered = -1`.
- E5: een insert met `id` en met `created_at` als `authenticated`. Dat laatste is de belangrijkste route om het sessielimiet te omzeilen; die is nu alleen indirect gedekt via `column_privs_are`.
- Een insert van twee rijen als `authenticated` die over de grens van 10 gaat.
- Een purge of sessiedelete van een sessie met een meerijder en een aanbieder: de cascade plus de self-FK met `set null`.

**N-6: De statische test `test_no_grants_on_rsvps` is zwak.**
- Waar: Testplan, `test_migrations.py`.
- Probleem: in `GRANT … ON` is `TABLE` optioneel. De regex mist daardoor `grant select on public.rsvps to anon` en `grant … on all tables in schema public`.
- Voorstel: gebruik iets als `grant\s[^;]*\bon\s+(?:table\s+)?[^;]*\bpublic\.rsvps\b` en een aparte check op `on\s+all\s+tables`. pgTAP dekt het al echt af, dus dit is een extra vangnet.

**N-7: Een linkhouder kan legitieme deelnemers buitensluiten (R1).**
- Probleem:
  - Wie de link heeft, kan een sessie in ongeveer 30 minuten vol zetten. Daarna geeft `rsvp_create` voor iedereen `session_full`. De organisator kan in deze WP niets verwijderen.
  - Ook legitieme drukte (meer dan 10 aanmeldingen binnen 10 minuten) geeft `rate_limited`.
- Dat volgt uit de WP-specificatie en staat bij de risico's, dus het blokkeert niet.
- Voorstel:
  - Leg in "Gevolgen voor WP-21" vast dat de melding bij `rate_limited` "probeer het over een paar minuten opnieuw" zegt.
  - Leg bij WP-22 de moderatie-RPC vast als concrete taak.
  - Noteer ook dat `[[:cntrl:]]` geen Unicode-opmaaktekens weert (zoals U+202E, rechts-naar-links). WP-21 kan namen met `dir="auto"` of `unicode-bidi: isolate` renderen.

**N-8: Tokens alleen in POST-bodies.**
- Waar: Gevolgen voor WP-21, A14.
- Probleem: de blueprint legt niet expliciet vast dat de token nooit in een URL mag staan.
  - PostgREST voert GET-verzoeken read-only uit. `rsvp_delete` via GET zou dus falen, maar de token staat dan al in de querystring en daarmee in de gateway-logs.
  - In de request-body is hij veilig. Postgres logt standaard geen bind-parameters (`log_parameter_max_length_on_error = 0`), en PostgREST geeft de body als parameter mee.
- Voorstel: zet bij WP-21 "RPC's met een token altijd via POST (de standaard van supabase-js); de token nooit in een URL of link". Neem de redenering op in A14.

**N-9: De timing van de fouten in E41/R8 klopt niet precies.** RUNBOOK §13.1 zegt dat de schedule de code van `main` draait. De stap `sessions_cleanup` gaat dus pas falen na promotie naar `main` zonder `db push`, niet direct na de merge naar `develop`. Formuleer RUNBOOK §16.2 als: "`supabase db push` vóór de promotie naar `main`".

**N-10: Een defensieve rem op `p_now` (optioneel).** Met `ends_at < least(p_now, now()) - interval '7 days'` kan een `p_now` in de toekomst (een bug of klokfout) nooit lopende sessies verwijderen. Het contract blijft gelijk; R7 vervalt dan grotendeels. Als je dit doet, pas dan de statische test `test_session_retention_matches_migration` en de fake mee aan.

**N-11: Een expliciete `not found`-controle in `rsvp_update`.** Na `select * into s … for update` volgt geen controle op `not found`. Het gedrag klopt wel: door de cascade bestaat de RSVP dan niet meer, en de update geeft `invalid_token`. Een expliciete `if not found then raise … 'invalid_token'` maakt dat leesbaarder en onafhankelijk van de volgorde.

**N-12: Een verouderde beschrijving in `01_schema`.** De FK-`set_eq` heet "foreign keys cascade on delete", maar bevat nu ook `r` (restrict) en `n` (set null). Pas de beschrijving aan, bijvoorbeeld naar "foreign keys and delete actions".

## Gecontroleerde bronnen
- https://docs.postgrest.org/en/v14/references/errors.html: `PTxyz` geeft HTTP-status xyz, met body `{code: "PT402", message, details, hint}`; `P0001` geeft 400; `42501` geeft 403 (geauthenticeerd) of 401.
- https://supabase.com/docs/guides/database/functions: `security definer` met een vaste `search_path`, volledig gekwalificeerde namen, en `revoke execute` van `public` en `anon` met daarna een gerichte grant.
- https://github.com/supabase/supabase/issues/43884: de standaardprivileges van Supabase geven nieuwe functies in `public` `EXECUTE` voor `anon` en `authenticated`.
- https://github.com/bradytrock/truss/pull/69 (via zoeken): pgcrypto staat op hosted Supabase in het schema `extensions`, en `gen_random_bytes` moet gekwalificeerd worden aangeroepen.
- https://www.postgresql.org/docs/17/sql-createpolicy.html: `WITH CHECK` wordt na de `BEFORE`-triggers en vóór de andere constraints afgedwongen; RETURNING vereist de SELECT-policy.
- https://www.postgresql.org/docs/17/trigger-datachanges.html: een row-level `BEFORE`-trigger (`VOLATILE`) ziet de rijen die eerder in hetzelfde statement zijn verwerkt.
- https://www.postgresql.org/docs/17/sql-createtable.html: `ON DELETE SET NULL (column_list)` (alleen bij ON DELETE).
- Lokaal: `supabase/.temp/rest-version` (v14.18), `supabase/.temp/postgres-version` (17.11), `config.toml` (`major_version = 17`).
