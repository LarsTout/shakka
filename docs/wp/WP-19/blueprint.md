# Blueprint WP-19: Sessies: datamodel, RLS en RPC's
Status: APPROVED
Revisie: 1

## Doel
Een veilig datamodel voor sessies ("ik ga") en RSVP's zonder account, als één migratie met pgTAP-tests, plus een opruimstap in de uurlijkse pipeline:
1. Tabel `sessions`. Een ingelogde organisator maakt, leest en wijzigt alleen zijn eigen sessies. Dat regelen RLS en kolomprivileges. De slug wordt server-side gegenereerd, en er geldt een limiet van 10 sessies per organisator per 24 uur.
2. Tabel `rsvps`. Geen enkele API-rol heeft er rechten op. Anonieme bezoekers lezen en schrijven alleen via vier `security definer`-RPC's met `set search_path = ''`. Wijzigen of afmelden kan alleen met een geheime edit-token (32 willekeurige bytes in base64url). Opgeslagen wordt alleen de sha256-hash.
3. Rate limits zonder IP-adressen, met vaste foutcodes.
4. Een bewaartermijn: `purge_expired_sessions(p_now)` (alleen voor `service_role`) en de pipelinestap `sessions_cleanup` aan het eind van `STEPS`.

Na deze WP kunnen WP-20 (aanmaken en delen) en WP-21 (publieke pagina en RSVP) parallel bouwen tegen een vaststaand database-contract.

## Aannames
- **A1. Bewaartermijn 7 dagen na `ends_at`.** Dit is het voorstel uit "Beslissingen voor Lars". Lars heeft nog niet beslist; de builder neemt het over. Een sessie (en via de cascade ook haar RSVP's) wordt verwijderd zodra `ends_at < p_now - interval '7 days'` (strikt). Precies 7 dagen blijft dus nog staan. Geannuleerde sessies volgen dezelfde regel, ook gerekend vanaf `ends_at`. Kiest Lars een andere termijn, dan komt er een nieuwe migratie die de functie vervangt, en verandert `SESSION_RETENTION` in Python mee. `test_session_retention_matches_migration` bewaakt dat die twee gelijk blijven.
- **A2. Foutcontract.** Elke fout uit de RPC's en uit de insert-trigger van `sessions` heeft SQLSTATE **`PT400`**. De `message` is exact één van `rate_limited`, `session_closed`, `session_full`, `invalid_input` of `invalid_token`. Er komen geen `detail` of `hint` bij.
  - PostgREST zet `PTxyz` om naar HTTP-status `xyz` en geeft `code: "PT400"` terug ([bron](https://docs.postgrest.org/en/v14/references/errors.html); lokaal draait PostgREST v14.18). Eén vaste code maakt het eenvoudig voor WP-20 en WP-21: `error.code === 'PT400'`, en dan `error.message` mappen.
  - CHECK-schendingen bij directe inserts en updates door de organisator (WP-20) blijven `23514`, en ontbrekende rechten blijven `42501`.
- **A3. Een onbekende slug bij `rsvp_create` geeft `session_closed`.** De contractcodes kennen geen `not_found`. Een sessie verdwijnt pas 7 dagen na afloop, dus "afgelopen of geannuleerd" is voor de bezoeker de juiste melding. `get_public_session` geeft bij een onbekende of ongeldig gevormde slug `null`.
- **A4. Het RSVP-ratelimit telt aanroepen, niet bestaande rijen.** "Max. 10 keer `rsvp_create` per sessie per 10 minuten" wordt exact gehandhaafd met een interne kolom `sessions.recent_rsvp_creates timestamptz[]`. Bij elke geslaagde `rsvp_create` worden tijdstippen ouder dan 10 minuten verwijderd en het nieuwe tijdstip toegevoegd (hoogstens 10). Telde de limiet bestaande rijen, dan kon iemand hem omzeilen door aan te maken en meteen weer af te melden.
  - Bijwerking: `sessions.updated_at` verandert ook bij een nieuwe RSVP, door de bestaande `set_updated_at`-trigger.
  - De kolom is leesbaar voor de organisator. Hij bevat alleen tijdstippen en geen persoonsgegevens, en is niet schrijfbaar.
- **A5. `service_role` heeft geen tabelrechten op `sessions` en `rsvps`.** Het enige wat de ingest kan, is `purge_expired_sessions` uitvoeren (`security definer`). Het contract zegt "op `rsvps` heeft niemand directe rechten"; dit ontwerp past minste rechten ook toe op `sessions`, want de ingest leest geen sessies. Lars kijkt in de data via het dashboard (rol `postgres`).
- **A6. Carpool-semantiek** (het contract legt die niet vast; dit ontwerp kiest de eenvoudigste consistente regels):
  - `seats_offered` mag alleen gezet zijn als `ride = 'offers_ride'` (CHECK). Bij `offers_ride` mag het ook `null` zijn (aantal onbekend).
  - `rides_with` mag alleen gezet zijn als `ride = 'needs_ride'` (CHECK), nooit naar zichzelf wijzen (CHECK) en alleen naar een RSVP in dezelfde sessie (samengestelde FK).
  - De RPC eist daarnaast dat het doel `ride = 'offers_ride'` heeft.
  - Betekenis voor WP-21: `needs_ride` zonder `rides_with` betekent "zoekt een lift"; `needs_ride` met `rides_with = X` betekent "rijdt mee met X".
  - Stopt X met `offers_ride` (via `rsvp_update`), dan wordt `rides_with` van zijn meerijders `null`. Meldt X zich af, dan doet de FK (`on delete set null`) hetzelfde.
  - Er is geen controle op capaciteit (meerijders ≤ `seats_offered`); zie Buiten scope.
- **A7. `sessions.spot_id` heeft `on delete restrict`.** `shakka spots sync` verwijdert nooit spots (WP-02). Een handmatige delete van een spot met lopende sessies faalt dus bewust; sessies verdwijnen vanzelf na de bewaartermijn.
- **A8. Namen.** `first_name` en `organizer_name` zijn getrimd (de spaties aan begin en eind, `btrim`), tellen 1–30 code points (`char_length`) en bevatten geen controletekens (`[[:cntrl:]]`, dus ook geen regeleinden).
  - De RPC's trimmen zelf.
  - Voor `organizer_name` is het een CHECK, dus WP-20 trimt vóór de insert.
  - JavaScript telt UTF-16-eenheden (`'😀'.length === 2`). WP-20 en WP-21 tellen daarom met `[...s].length`.
- **A9. Slug en token.**
  - **Slug.** Een `BEFORE INSERT`-trigger vult de slug als die `null` is. `authenticated` heeft geen INSERT-recht op de kolom `slug`, dus via de API is de slug altijd server-side gegenereerd. Hij bestaat uit 22 tekens base64url uit `gen_random_uuid()` (ingebouwd in Postgres 13+, CSPRNG, 122 willekeurige bits). Alleen `postgres` (migraties en pgTAP) kan een slug meegeven, en de CHECK `^[A-Za-z0-9_-]{10,64}$` geldt dan ook. Zo kunnen de tests vaste slugs gebruiken.
  - **Token.** `extensions.gen_random_bytes(32)` uit pgcrypto, in base64url zonder padding (43 tekens). De hash is `encode(sha256(convert_to(token, 'UTF8')), 'hex')`, met de ingebouwde `sha256(bytea)`. Een salt of pepper is niet nodig: de token heeft 256 bits entropie, dus brute force op de hash is zinloos.
- **A10. Afmelden mag altijd, wijzigen niet.** `rsvp_delete` werkt ook bij een geannuleerde of afgelopen sessie: je eigen naam weghalen gaat voor (privacy). `rsvp_update` op een geannuleerde of afgelopen sessie geeft `session_closed`.
  - Een verkeerde of misvormde token geeft bij `rsvp_delete` `false`, ook bij een tweede aanroep (idempotent).
  - Bij `rsvp_update` geeft een verkeerde of misvormde token `invalid_token`.
- **A11. "Afgelopen" betekent `ends_at <= now()`** (de databaseklok, UTC). Een sessie die al begonnen maar nog niet afgelopen is, accepteert nog RSVP's.
- **A12. Concurrency.**
  - Elke RSVP-RPC die schrijft, zet eerst `select … for update` op de sessierij. Alle schrijfacties per sessie lopen dus na elkaar, en de tellingen (30 RSVP's, 10 per 10 minuten) kloppen exact.
  - De sessielimiet per organisator gebruikt `pg_advisory_xact_lock` op een hash van de `organizer_id`.
- **A13. Docker bij de builder**, zoals WP-01 A1. Zonder Docker schrijft de builder de SQL en pgTAP toch, en komt het bewijs uit de CI-job `db`.
- **A14. IP-adressen.** De database slaat geen IP op. De API-gateway van Supabase logt verzoeken op platformniveau; dat valt buiten deze WP en komt in de privacytekst (WP-23).

## Ontwerp

### Eén migratie
`supabase/migrations/20261015200000_sessions.sql` bevat in deze volgorde:
1. `pgcrypto` (als die er nog niet is, in schema `extensions`);
2. de twee tabellen, constraints en indexen;
3. de triggers;
4. de vijf RPC's;
5. RLS, revokes, grants en policies.

WP-12 en WP-17 hadden ook één migratie per WP. De beveiliging staat hier toch in dezelfde file als het schema: de RPC's en de rechten horen bij elkaar en worden samen gereviewd. Het patroon is dat van WP-01 en WP-17: `enable row level security`, `revoke all … from public, anon, authenticated, service_role`, daarna precies de bedoelde grants. Voor functies gebeurt hetzelfde. Supabase geeft nieuwe functies in `public` standaard `EXECUTE` aan `anon` en `authenticated`, en Postgres geeft ze aan `PUBLIC` ([bron](https://supabase.com/docs/guides/database/functions), [bron](https://github.com/supabase/supabase/issues/43884)). Daarom krijgt elke functie in deze migratie eerst `revoke all … from public, anon, authenticated, service_role`.

### Rechtenmatrix

| Object | `anon` | `authenticated` | `service_role` |
|---|---|---|---|
| tabel `sessions` | – | SELECT; INSERT op 9 kolommen; UPDATE op 9 kolommen (zie Interfaces) | – |
| tabel `rsvps` | – | – | – |
| `get_public_session`, `rsvp_create`, `rsvp_update`, `rsvp_delete` | EXECUTE | EXECUTE | – |
| `purge_expired_sessions` | – | – | EXECUTE |
| `sessions_prepare_insert` (trigger) | – | – | – |

Policies op `sessions`: `select`, `insert` en `update` op `organizer_id = (select auth.uid())`. Er is geen delete: annuleren gaat via `cancelled_at`. Op `rsvps` zijn er geen policies. pgTAP legt de verzameling uitvoerbare functies in `public` per rol vast. Elke nieuwe functie die later per ongeluk uitvoerbaar is, laat die test falen.

### Waarom de trigger `security invoker` is
`sessions_prepare_insert` telt de recente sessies van `new.organizer_id`. Als `security invoker` onder RLS telt hij voor `authenticated` alleen eigen rijen. Probeert A te inserten met de `organizer_id` van B, dan telt de trigger 0. Daarna faalt de `WITH CHECK`, die volgens de Postgres-docs na `BEFORE`-triggers wordt afgedwongen ([bron](https://www.postgresql.org/docs/17/sql-createpolicy.html)). Zo lekt er niets over het aantal sessies van B. De slug komt uit `gen_random_uuid()` (`pg_catalog`), dus de trigger heeft geen rechten op `extensions` nodig. De trigger heeft ook geen `EXECUTE` nodig; dat is aangetoond in WP-01 A7.

Rijen die eerder in hetzelfde statement zijn ingevoegd, zijn zichtbaar voor een `VOLATILE` row-level `BEFORE`-trigger ([bron](https://www.postgresql.org/docs/17/trigger-datachanges.html)). De limiet klopt dus ook bij een insert van meerdere rijen.

### Waarom de RPC's `security definer` zijn
`anon` heeft geen enkel tabelrecht. De RPC's draaien als eigenaar van de tabellen (`postgres`), en eigenaars vallen niet onder RLS. Daarom hebben ze `set search_path = ''`, gebruiken ze overal volledig gekwalificeerde namen (`public.…`, `extensions.gen_random_bytes`) en valideren ze elke parameter vóór gebruik ([bron](https://supabase.com/docs/guides/database/functions)). Ze geven nooit `organizer_id`, `edit_token_hash`, `recent_rsvp_creates` of e-mailadressen terug.

### Volgorde van controles (vast, zodat de foutcodes deterministisch zijn)
- `rsvp_create`:
  1. invoer → `invalid_input`;
  2. slugvorm → `session_closed`;
  3. sessie opzoeken met `for update` → `session_closed` als die niet bestaat, geannuleerd is of afgelopen is;
  4. aantal RSVP's ≥ 30 → `session_full`;
  5. recente aanroepen ≥ 10 → `rate_limited`;
  6. insert en bijwerken van `recent_rsvp_creates`.
- `rsvp_update`:
  1. tokenvorm → `invalid_token`;
  2. invoer → `invalid_input`;
  3. RSVP opzoeken via de hash → `invalid_token`;
  4. sessie `for update`, geannuleerd of afgelopen → `session_closed`;
  5. `rides_with` (doel bestaat, zit in dezelfde sessie, is niet zichzelf en biedt een lift aan) → `invalid_input`;
  6. update, en daarna zo nodig `rides_with` van de meerijders wissen.
- `rsvp_delete`:
  1. tokenvorm → `false`;
  2. RSVP opzoeken → `false`;
  3. sessie `for update`;
  4. delete → `true`.
- Insert in `sessions` (trigger): advisory lock, telling ≥ 10 → `rate_limited`, slug vullen. Daarna `WITH CHECK` (42501), dan NOT NULL en CHECK (23502, 23514), dan FK (23503).

### Pipeline
Een nieuwe module `shakka.jobs.sessions` roept de RPC aan. De nieuwe stapfunctie `step_sessions_cleanup` komt als laatste in `STEPS` (WP-11 "Gevolgen"). Faalt de stap, dan wordt die `failed` via de bestaande `run_step`. De run wordt dan `partial` (de alertsstap is `ok`), met exitcode 0 en een `::error::`-annotatie. De andere stappen zijn dan al gedraaid en blijven ongemoeid. De logregel en `counts` bevatten alleen `deleted` (een aantal).

`FakeSupabase` krijgt `purge_expired_sessions` als ingebouwde RPC (dezelfde regel als in SQL, met cascade naar `rsvps`), zodat de bestaande pipelinetests zonder registratie groen blijven. Een met `register_rpc` geregistreerde handler gaat voor.

## Bestanden

| Pad | Actie | Inhoud |
|---|---|---|
| `supabase/migrations/20261015200000_sessions.sql` | aanmaken | Exact zoals onder Interfaces. |
| `supabase/tests/01_schema.test.sql` | wijzigen | `tables_are` plus `sessions` en `rsvps`; de kolom-`set_eq` plus 24 rijen; de FK-`set_eq` plus 4 rijen. `plan(71)` blijft gelijk (er komen geen nieuwe asserts bij). |
| `supabase/tests/07_sessions.test.sql` | aanmaken | Vorm, rechten, functies, constraints, RLS en cascades: 107 asserts (zie Testplan). |
| `supabase/tests/08_session_rpcs.test.sql` | aanmaken | RPC-gedrag, rate limits en opruimen: 62 asserts (zie Testplan). |
| `ingest/src/shakka/db.py` | wijzigen | `TABLE_KEYS` plus `"sessions": ("id",)` en `"rsvps": ("id",)`, direct na `"push_subscriptions"`. Verder niets. |
| `ingest/src/shakka/jobs/sessions.py` | aanmaken | `PURGE_RPC`, `SESSION_RETENTION` en `purge_expired_sessions` (zie Interfaces). |
| `ingest/src/shakka/pipeline.py` | wijzigen | Import `purge_expired_sessions`, `step_sessions_cleanup`, `STEP_NAMES` en `STEPS` met `sessions_cleanup` aan het eind, en de module-docstring (stappenlijst) bijwerken. |
| `ingest/tests/fakes.py` | wijzigen | Een cascade `sessions` → `rsvps` in `delete`, de ingebouwde RPC `purge_expired_sessions`, en de opzoekvolgorde in `rpc` (zie Interfaces). |
| `ingest/tests/test_jobs_sessions.py` | aanmaken | Tests van `shakka.jobs.sessions` (zie Testplan). |
| `ingest/tests/test_fakes.py` | wijzigen | Vier tests erbij (zie Testplan). |
| `ingest/tests/test_pipeline.py` | wijzigen | De stappenvolgorde, de alertsstap zoeken op naam, en drie nieuwe tests (AC-7). |
| `ingest/tests/test_cli_pipeline.py` | wijzigen | Regel 124: de alertsstap op naam zoeken in plaats van `[-1]`. |
| `ingest/tests/test_migrations.py` | wijzigen | `test_no_later_milestone_tables` vervalt (WP-01 AC-6 is historisch: de tabellen bestaan nu), en er komen drie statische tests bij (zie Testplan). |
| `docs/RUNBOOK.md` | wijzigen | §8: punt 6 over functies. §13 punt 1: de stappenlijst plus `sessions_cleanup`. Een nieuwe §16 "Sessies en RSVP (vanaf WP-19)" (zie Interfaces). |

Geen wijzigingen in `web/`, `shakka.domain`, `pyproject.toml`, `uv.lock` of `ci.yml`. Er komen geen nieuwe dependencies bij. `docs/STATUS.md` werkt de orchestrator bij.

## Interfaces en contracten

### Migratie `supabase/migrations/20261015200000_sessions.sql` (exact)
```sql
-- Sessions and RSVPs (WP-19).
-- Organizers (authenticated) manage their own sessions through RLS and column privileges.
-- RSVPs are only reachable through the security-definer RPCs in this file: no API role has any
-- privilege on public.rsvps. Retention: a session and, by cascade, its RSVPs are removed
-- 7 days after ends_at by purge_expired_sessions (pipeline step sessions_cleanup).
-- Errors raised here: SQLSTATE PT400 (PostgREST: HTTP 400) with message exactly one of
-- rate_limited, session_closed, session_full, invalid_input, invalid_token.

create extension if not exists pgcrypto with schema extensions;

-- Tables --------------------------------------------------------------------------------------

create table public.sessions (
  id uuid primary key default gen_random_uuid(),
  slug text not null
    constraint sessions_slug_key unique
    constraint sessions_slug_format check (slug ~ '^[A-Za-z0-9_-]{10,64}$'),
  spot_id text not null references public.spots (id) on delete restrict,
  organizer_id uuid not null default auth.uid() references auth.users (id) on delete cascade,
  organizer_name text not null constraint sessions_organizer_name_valid check (
    organizer_name = btrim(organizer_name)
    and char_length(organizer_name) between 1 and 30
    and organizer_name !~ '[[:cntrl:]]'
  ),
  starts_at timestamptz not null,
  ends_at timestamptz not null,
  note text null constraint sessions_note_length check (char_length(note) <= 280),
  seats_free smallint null constraint sessions_seats_free_range check (seats_free between 0 and 8),
  departure_point text null
    constraint sessions_departure_point_length check (char_length(departure_point) <= 80),
  tikkie_url text null constraint sessions_tikkie_url_https
    check (tikkie_url ~ '^https://[^[:space:]]+$' and char_length(tikkie_url) <= 200),
  cancelled_at timestamptz null,
  -- Internal: times of recent successful rsvp_create calls (rate limit, at most 10 kept).
  recent_rsvp_creates timestamptz[] not null default '{}'
    constraint sessions_recent_rsvp_creates_size check (cardinality(recent_rsvp_creates) <= 10),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint sessions_window_order check (ends_at > starts_at),
  constraint sessions_window_max_16h check (ends_at <= starts_at + interval '16 hours')
);
create index sessions_organizer_created_idx on public.sessions (organizer_id, created_at);
create index sessions_ends_at_idx on public.sessions (ends_at);
create index sessions_spot_id_idx on public.sessions (spot_id);

create table public.rsvps (
  id uuid primary key default gen_random_uuid(),
  session_id uuid not null references public.sessions (id) on delete cascade,
  first_name text not null constraint rsvps_first_name_valid check (
    first_name = btrim(first_name)
    and char_length(first_name) between 1 and 30
    and first_name !~ '[[:cntrl:]]'
  ),
  ride text not null default 'own'
    constraint rsvps_ride_enum check (ride in ('own', 'needs_ride', 'offers_ride')),
  seats_offered smallint null
    constraint rsvps_seats_offered_range check (seats_offered between 0 and 8),
  rides_with uuid null,
  edit_token_hash text not null
    constraint rsvps_edit_token_hash_key unique
    constraint rsvps_edit_token_hash_format check (edit_token_hash ~ '^[0-9a-f]{64}$'),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint rsvps_session_id_id_key unique (session_id, id),
  constraint rsvps_seats_only_when_offering check (seats_offered is null or ride = 'offers_ride'),
  constraint rsvps_rides_with_needs_ride check (rides_with is null or ride = 'needs_ride'),
  constraint rsvps_rides_with_not_self check (rides_with is null or rides_with <> id)
);
-- rides_with points to an RSVP of the same session; deleting that RSVP clears only rides_with.
alter table public.rsvps
  add constraint rsvps_rides_with_fkey foreign key (session_id, rides_with)
  references public.rsvps (session_id, id) on delete set null (rides_with);
create index rsvps_rides_with_idx on public.rsvps (session_id, rides_with);

create trigger sessions_set_updated_at before update on public.sessions
  for each row execute function public.set_updated_at();
create trigger rsvps_set_updated_at before update on public.rsvps
  for each row execute function public.set_updated_at();

-- Insert trigger: per-organizer rate limit and server-side slug. Security invoker on purpose:
-- under RLS an authenticated caller only counts own rows, so nothing leaks about other users.
create function public.sessions_prepare_insert()
returns trigger
language plpgsql
set search_path = ''
as $$
declare
  v_recent integer;
begin
  -- Serialize inserts per organizer so the limit holds under concurrency.
  perform pg_catalog.pg_advisory_xact_lock(
    pg_catalog.hashtextextended('shakka.sessions:' || new.organizer_id::text, 0)
  );
  select count(*) into v_recent
    from public.sessions s
   where s.organizer_id = new.organizer_id
     and s.created_at > now() - interval '24 hours';
  if v_recent >= 10 then
    raise sqlstate 'PT400' using message = 'rate_limited';
  end if;
  if new.slug is null then
    new.slug := rtrim(translate(encode(uuid_send(gen_random_uuid()), 'base64'), '+/', '-_'), '=');
  end if;
  return new;
end;
$$;

create trigger sessions_prepare_insert before insert on public.sessions
  for each row execute function public.sessions_prepare_insert();

-- RPCs ----------------------------------------------------------------------------------------

-- Public view of one session by slug. Never organizer_id, tokens, hashes or e-mail addresses.
create function public.get_public_session(p_slug text)
returns jsonb
language plpgsql
stable
security definer
set search_path = ''
as $$
declare
  s public.sessions;
  v_spot_name text;
begin
  if p_slug is null or p_slug !~ '^[A-Za-z0-9_-]{10,64}$' then
    return null;
  end if;
  select * into s from public.sessions where slug = p_slug;
  if not found then
    return null;
  end if;
  select sp.name into v_spot_name from public.spots sp where sp.id = s.spot_id;
  return jsonb_build_object(
    'session', jsonb_build_object(
      'slug', s.slug,
      'spot_id', s.spot_id,
      'spot_name', v_spot_name,
      'organizer_name', s.organizer_name,
      'starts_at', s.starts_at,
      'ends_at', s.ends_at,
      'note', s.note,
      'seats_free', s.seats_free,
      'departure_point', s.departure_point,
      'tikkie_url', s.tikkie_url,
      'cancelled', s.cancelled_at is not null
    ),
    'rsvps', coalesce((
      select jsonb_agg(
               jsonb_build_object(
                 'id', r.id,
                 'first_name', r.first_name,
                 'ride', r.ride,
                 'seats_offered', r.seats_offered,
                 'rides_with', r.rides_with,
                 'created_at', r.created_at
               )
               order by r.created_at, r.id
             )
        from public.rsvps r
       where r.session_id = s.id
    ), '[]'::jsonb)
  );
end;
$$;

-- RSVP without an account. Returns {rsvp_id, edit_token}; only the sha256 of the token is stored.
create function public.rsvp_create(
  p_slug text, p_first_name text, p_ride text, p_seats_offered integer
)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_name text := btrim(p_first_name);
  s public.sessions;
  v_recent timestamptz[];
  v_token text;
  v_id uuid;
begin
  if v_name is null
     or char_length(v_name) not between 1 and 30
     or v_name ~ '[[:cntrl:]]'
     or p_ride is null
     or p_ride not in ('own', 'needs_ride', 'offers_ride')
     or (p_seats_offered is not null
         and (p_seats_offered not between 0 and 8 or p_ride <> 'offers_ride')) then
    raise sqlstate 'PT400' using message = 'invalid_input';
  end if;
  if p_slug is null or p_slug !~ '^[A-Za-z0-9_-]{10,64}$' then
    raise sqlstate 'PT400' using message = 'session_closed';
  end if;
  select * into s from public.sessions where slug = p_slug for update;
  if not found or s.cancelled_at is not null or s.ends_at <= now() then
    raise sqlstate 'PT400' using message = 'session_closed';
  end if;
  if (select count(*) from public.rsvps r where r.session_id = s.id) >= 30 then
    raise sqlstate 'PT400' using message = 'session_full';
  end if;
  v_recent := array(
    select t from unnest(s.recent_rsvp_creates) as u(t)
     where t > now() - interval '10 minutes'
     order by t
  );
  if cardinality(v_recent) >= 10 then
    raise sqlstate 'PT400' using message = 'rate_limited';
  end if;
  v_token := rtrim(translate(encode(extensions.gen_random_bytes(32), 'base64'), '+/', '-_'), '=');
  insert into public.rsvps (session_id, first_name, ride, seats_offered, edit_token_hash)
  values (s.id, v_name, p_ride, p_seats_offered,
          encode(sha256(convert_to(v_token, 'UTF8')), 'hex'))
  returning id into v_id;
  update public.sessions set recent_rsvp_creates = v_recent || now() where id = s.id;
  return jsonb_build_object('rsvp_id', v_id, 'edit_token', v_token);
end;
$$;

-- Replace the editable fields of one RSVP. Returns the public shape of the RSVP.
create function public.rsvp_update(
  p_edit_token text, p_first_name text, p_ride text, p_seats_offered integer, p_rides_with uuid
)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_name text := btrim(p_first_name);
  v_rsvp public.rsvps;
  s public.sessions;
begin
  if p_edit_token is null or p_edit_token !~ '^[A-Za-z0-9_-]{43}$' then
    raise sqlstate 'PT400' using message = 'invalid_token';
  end if;
  if v_name is null
     or char_length(v_name) not between 1 and 30
     or v_name ~ '[[:cntrl:]]'
     or p_ride is null
     or p_ride not in ('own', 'needs_ride', 'offers_ride')
     or (p_seats_offered is not null
         and (p_seats_offered not between 0 and 8 or p_ride <> 'offers_ride'))
     or (p_rides_with is not null and p_ride <> 'needs_ride') then
    raise sqlstate 'PT400' using message = 'invalid_input';
  end if;
  select * into v_rsvp from public.rsvps r
   where r.edit_token_hash = encode(sha256(convert_to(p_edit_token, 'UTF8')), 'hex');
  if not found then
    raise sqlstate 'PT400' using message = 'invalid_token';
  end if;
  select * into s from public.sessions where id = v_rsvp.session_id for update;
  if s.cancelled_at is not null or s.ends_at <= now() then
    raise sqlstate 'PT400' using message = 'session_closed';
  end if;
  if p_rides_with is not null and (
       p_rides_with = v_rsvp.id
       or not exists (
         select 1 from public.rsvps t
          where t.id = p_rides_with and t.session_id = s.id and t.ride = 'offers_ride'
       )
     ) then
    raise sqlstate 'PT400' using message = 'invalid_input';
  end if;
  update public.rsvps
     set first_name = v_name, ride = p_ride, seats_offered = p_seats_offered,
         rides_with = p_rides_with
   where id = v_rsvp.id
  returning * into v_rsvp;
  if not found then
    raise sqlstate 'PT400' using message = 'invalid_token';
  end if;
  if p_ride <> 'offers_ride' then
    -- No longer offering a ride: riders who rode along are looking again.
    update public.rsvps set rides_with = null
     where session_id = s.id and rides_with = v_rsvp.id;
  end if;
  return jsonb_build_object(
    'id', v_rsvp.id,
    'first_name', v_rsvp.first_name,
    'ride', v_rsvp.ride,
    'seats_offered', v_rsvp.seats_offered,
    'rides_with', v_rsvp.rides_with,
    'created_at', v_rsvp.created_at
  );
end;
$$;

-- Remove one RSVP. Allowed for closed sessions too. Unknown or malformed token: false.
create function public.rsvp_delete(p_edit_token text)
returns boolean
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_hash text;
  v_session uuid;
begin
  if p_edit_token is null or p_edit_token !~ '^[A-Za-z0-9_-]{43}$' then
    return false;
  end if;
  v_hash := encode(sha256(convert_to(p_edit_token, 'UTF8')), 'hex');
  select r.session_id into v_session from public.rsvps r where r.edit_token_hash = v_hash;
  if not found then
    return false;
  end if;
  perform 1 from public.sessions s where s.id = v_session for update;
  delete from public.rsvps r where r.edit_token_hash = v_hash;
  return found;
end;
$$;

-- Retention (service role only): sessions that ended more than 7 days before p_now, with their
-- RSVPs (cascade). Returns the number of sessions removed.
create function public.purge_expired_sessions(p_now timestamptz)
returns integer
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_count integer;
begin
  if p_now is null then
    raise sqlstate 'PT400' using message = 'invalid_input';
  end if;
  delete from public.sessions where ends_at < p_now - interval '7 days';
  get diagnostics v_count = row_count;
  return v_count;
end;
$$;

-- Security ------------------------------------------------------------------------------------

alter table public.sessions enable row level security;
alter table public.rsvps enable row level security;

revoke all on table public.sessions, public.rsvps from public, anon, authenticated, service_role;

-- Organizer: read own sessions; insert and update only the user-editable columns.
-- slug, id, recent_rsvp_creates and the timestamps are never writable through the API.
grant select on table public.sessions to authenticated;
grant insert (spot_id, organizer_id, organizer_name, starts_at, ends_at, note, seats_free,
              departure_point, tikkie_url)
  on table public.sessions to authenticated;
grant update (spot_id, organizer_name, starts_at, ends_at, note, seats_free, departure_point,
              tikkie_url, cancelled_at)
  on table public.sessions to authenticated;

-- rsvps: no table privileges for any API role (RPCs only).

create policy sessions_select_own on public.sessions for select to authenticated
  using (organizer_id = (select auth.uid()));
create policy sessions_insert_own on public.sessions for insert to authenticated
  with check (organizer_id = (select auth.uid()));
create policy sessions_update_own on public.sessions for update to authenticated
  using (organizer_id = (select auth.uid())) with check (organizer_id = (select auth.uid()));

revoke all on function public.sessions_prepare_insert()
  from public, anon, authenticated, service_role;
revoke all on function public.get_public_session(text)
  from public, anon, authenticated, service_role;
revoke all on function public.rsvp_create(text, text, text, integer)
  from public, anon, authenticated, service_role;
revoke all on function public.rsvp_update(text, text, text, integer, uuid)
  from public, anon, authenticated, service_role;
revoke all on function public.rsvp_delete(text)
  from public, anon, authenticated, service_role;
revoke all on function public.purge_expired_sessions(timestamptz)
  from public, anon, authenticated, service_role;

grant execute on function
  public.get_public_session(text),
  public.rsvp_create(text, text, text, integer),
  public.rsvp_update(text, text, text, integer, uuid),
  public.rsvp_delete(text)
to anon, authenticated;

grant execute on function public.purge_expired_sessions(timestamptz) to service_role;
```
De builder mag regels anders afbreken of inspringen en commentaar toevoegen. Namen, types, constraints, defaults, controles, de volgorde van controles en de foutteksten liggen vast.

### Kolomprivileges van `authenticated` op `sessions` (wat pgTAP vastlegt)

| Kolom | Privileges |
|---|---|
| `id`, `slug`, `recent_rsvp_creates`, `created_at`, `updated_at` | SELECT |
| `organizer_id` | INSERT, SELECT |
| `spot_id`, `organizer_name`, `starts_at`, `ends_at`, `note`, `seats_free`, `departure_point`, `tikkie_url` | INSERT, SELECT, UPDATE |
| `cancelled_at` | SELECT, UPDATE |

### RPC-contract (PostgREST `POST /rest/v1/rpc/<naam>`, body met de parameternamen)

| RPC | Rollen | Body | Resultaat |
|---|---|---|---|
| `get_public_session` | anon, authenticated | `{"p_slug": str}` | `null` of `{"session": {...}, "rsvps": [...]}` (zie hieronder) |
| `rsvp_create` | anon, authenticated | `{"p_slug", "p_first_name", "p_ride", "p_seats_offered": int\|null}` | `{"rsvp_id": uuid, "edit_token": str(43)}` |
| `rsvp_update` | anon, authenticated | `{"p_edit_token", "p_first_name", "p_ride", "p_seats_offered": int\|null, "p_rides_with": uuid\|null}` | `{"id", "first_name", "ride", "seats_offered", "rides_with", "created_at"}` |
| `rsvp_delete` | anon, authenticated | `{"p_edit_token": str}` | `true` of `false` |
| `purge_expired_sessions` | service_role | `{"p_now": timestamptz}` | integer (aantal verwijderde sessies) |

Alle parameters zijn verplicht (geen defaults). `null` is wel toegestaan waar de tabel dat zegt. `rsvp_update` vervangt alle bewerkbare velden; de client stuurt de huidige waarden mee voor velden die gelijk blijven.

Vorm van `get_public_session`:
```json
{
  "session": {
    "slug": "Q2x0aHJ1c3RtZTEyMzQ1Ng",
    "spot_id": "brouwersdam",
    "spot_name": "Brouwersdam",
    "organizer_name": "Lars",
    "starts_at": "2026-10-17T12:00:00+00:00",
    "ends_at": "2026-10-17T16:00:00+00:00",
    "note": null,
    "seats_free": 3,
    "departure_point": "Utrecht CS",
    "tikkie_url": null,
    "cancelled": false
  },
  "rsvps": [
    {"id": "…uuid…", "first_name": "Eva", "ride": "offers_ride", "seats_offered": 2,
     "rides_with": null, "created_at": "2026-10-15T18:03:11.123456+00:00"}
  ]
}
```
- De `rsvps` zijn gesorteerd op `created_at` en daarna `id`, en het zijn er hoogstens 30.
- Tijden zijn ISO 8601 met offset, zoals Postgres `timestamptz` naar JSON schrijft (de sessietijdzone is UTC). Parse ze altijd; vergelijk ze nooit als string.
- `spot_name` is `null` als de spot geen naam heeft. Dat kan niet, want `spots.name` is `not null`.

Fouten (`rsvp_create`, `rsvp_update`, `purge_expired_sessions`, en een directe insert in `sessions`): HTTP 400, body `{"code": "PT400", "message": "<code>", "details": null, "hint": null}`.

| `message` | Wanneer |
|---|---|
| `invalid_input` | Een naam die na trimmen leeg is, meer dan 30 tekens heeft of een controleteken bevat. `p_ride` leeg of onbekend. `p_seats_offered` buiten 0–8 of gezet zonder `offers_ride`. `p_rides_with` gezet zonder `needs_ride`, naar zichzelf, naar een andere sessie of naar iemand die geen lift aanbiedt. `p_now` leeg. |
| `session_closed` | Een slug die onbekend of ongeldig is, een geannuleerde sessie, of een afgelopen sessie (`ends_at <= now()`). Ook bij `rsvp_update` op zo'n sessie. |
| `session_full` | De sessie heeft al 30 RSVP's. |
| `rate_limited` | Al 10 geslaagde `rsvp_create` op deze sessie in de laatste 10 minuten, of al 10 sessies van deze organisator in de laatste 24 uur (insert in `sessions`). |
| `invalid_token` | `rsvp_update` met een token die niet uit 43 base64url-tekens bestaat of die bij geen RSVP hoort. |

### `ingest/src/shakka/jobs/sessions.py` (exact)
```python
"""Session retention (WP-19): sessions, and by cascade their RSVPs, are removed 7 days after
ends_at through the service-only RPC purge_expired_sessions. Never reads sessions or RSVPs."""

import logging
from datetime import datetime, timedelta
from typing import Final

from shakka.db import SupabaseRest
from shakka.jobs.inputs import require_aware

PURGE_RPC: Final = "purge_expired_sessions"
SESSION_RETENTION: Final = timedelta(days=7)  # mirrors interval '7 days' in the migration

logger = logging.getLogger("shakka.jobs.sessions")


def purge_expired_sessions(db: SupabaseRest, *, now: datetime) -> int:
    """Call the RPC with p_now = now; returns the number of sessions removed.

    ValueError for a naive `now` (before any request) or a response that is not an int >= 0.
    DatabaseError from the client propagates.
    """
    require_aware(now)
    result = db.rpc(PURGE_RPC, {"p_now": now})
    if isinstance(result, bool) or not isinstance(result, int) or result < 0:
        raise ValueError("purge_expired_sessions: unexpected response")
    logger.info("sessions: purged=%d", result)
    return result
```
`to_json` codeert `now` als `…Z` (WP-01), en PostgREST cast dat naar `timestamptz`.

### `shakka.pipeline` (wijzigingen)
```python
from shakka.jobs.sessions import purge_expired_sessions

STEP_NAMES: Final = (
    "spots_sync", "forecast", "marine", "tides", "evaluate", "alerts", "sessions_cleanup",
)

def step_sessions_cleanup(ctx: PipelineContext) -> StepOutcome:
    deleted = purge_expired_sessions(ctx.db, now=ctx.now)
    return StepOutcome("ok", {"deleted": deleted})

STEPS: Final[tuple[Step, ...]] = (
    ("spots_sync", step_spots_sync),
    ("forecast", step_forecast),
    ("marine", step_marine),
    ("tides", step_tides),
    ("evaluate", step_evaluate),
    ("alerts", step_alerts),
    ("sessions_cleanup", step_sessions_cleanup),
)
```
`run_step`, `run_status`, `exit_code_for`, `error_summary` en `build_annotations` blijven ongewijzigd.

### `ingest/tests/fakes.py` (wijzigingen)
- Import: `from shakka.jobs.sessions import PURGE_RPC, SESSION_RETENTION`.
- `delete`: na de bestaande cascades komt er een tak bij. Bij `table == "sessions"` worden de rijen in `rsvps` met `session_id` in de verwijderde `id`'s ook verwijderd (niet als aparte entry in `writes`).
- `rpc(function, args)`:
  - de handler is `self._rpcs.get(function)`, en anders `self._builtin_rpcs().get(function)`;
  - zijn beide `None`, dan volgt `DatabaseError(..., status=404, code="PGRST202")`, zoals nu;
  - `rpc_calls` wordt altijd bijgewerkt, zoals nu;
  - `_builtin_rpcs()` geeft `{PURGE_RPC: self._purge_expired_sessions}`.
- `_purge_expired_sessions(args)`:
  - `p_now` ontbreekt of is `None` → `DatabaseError("invalid_input", status=400, code="PT400")`;
  - anders `cutoff = datetime.fromisoformat(p_now) - SESSION_RETENTION` (naïef telt als UTC);
  - verwijder de sessies met `datetime.fromisoformat(ends_at) < cutoff` (naïef telt als UTC), en hun RSVP's (cascade);
  - geef het aantal verwijderde sessies terug;
  - geen entry in `writes`.
- Geen kolomdefaults voor `sessions` en `rsvps`: tests seeden `id` en de benodigde velden expliciet. Daarmee wordt ook de FK `rides_with` en de `restrict` vanaf `spots` níet nagebootst; dat past bij WP-01 ("FK-constraints niet").

### `docs/RUNBOOK.md`
- **§8, nieuw punt 6:** "Elke nieuwe functie in `public` krijgt `revoke all on function … from public, anon, authenticated, service_role` en daarna een expliciete `grant execute` aan precies de rollen die hem nodig hebben. `security definer` alleen met `set search_path = ''` en volledig gekwalificeerde namen. `supabase/tests/07_sessions.test.sql` legt per rol vast welke functies uitvoerbaar zijn; pas die test aan bij een nieuwe RPC."
- **§13, punt 1:** de stappenlijst wordt `spots_sync`, `forecast`, `marine`, `tides`, `evaluate`, `alerts`, `sessions_cleanup`.
- **Nieuw §16 "Sessies en RSVP (vanaf WP-19)":**
  1. De bewaartermijn is 7 dagen na het einde van een sessie (`ends_at`). De uurlijkse stap `sessions_cleanup` verwijdert oudere sessies met hun RSVP's. In `ingest_runs.steps` staat `counts.deleted`.
  2. Na de merge: `supabase db push` (§8.3). Controleer eerst in de SQL-editor dat pgcrypto in het schema `extensions` staat: `select extnamespace::regnamespace from pg_extension where extname = 'pgcrypto';` moet `extensions` geven. Staat pgcrypto ergens anders, push dan niet en meld het; `rsvp_create` gebruikt `extensions.gen_random_bytes`.
  3. Geeft een RPC direct na de push `PGRST202` (functie niet gevonden), voer dan in de SQL-editor `notify pgrst, 'reload schema';` uit.
  4. Limieten: hoogstens 30 RSVP's per sessie, hoogstens 10 nieuwe RSVP's per sessie per 10 minuten, hoogstens 10 nieuwe sessies per organisator per 24 uur. Er wordt geen IP-adres opgeslagen.
  5. Een sessie handmatig verwijderen (bijv. bij misbruik): in de SQL-editor `delete from public.sessions where slug = '<slug>';`. De RSVP's gaan mee. Eén RSVP verwijderen: `delete from public.rsvps where id = '<id>';`.
  6. Geen enkele API-rol mag `rsvps` direct lezen, ook de ingest niet. Kijken kan alleen via de SQL-editor (rol `postgres`).

### Consistentie met afhankelijke WP's
- **WP-01:** dezelfde patronen (revoke en expliciete grants, `(select auth.uid())`, `set_updated_at`, triggerfuncties zonder `EXECUTE`). `TABLE_KEYS` en `test_table_keys_match_migrations`. De regex-test `test_no_later_milestone_tables` (WP-01 AC-6) is historisch en vervalt.
- **WP-17:** `organizer_id uuid not null default auth.uid()` zoals `push_subscriptions.user_id`, en kolomgranted inserts.
- **WP-08 en WP-14:** de `/go`-URL levert hele uren in UTC (`start` < `end`). Elk window van de alert-engine past in `sessions_window_order`. Langer dan 16 uur kan in Nederland niet bij daglicht; als het toch voorkomt, kapt WP-20 af (zie Gevolgen).
- **WP-11:** de stap komt aan het eind van `STEPS`, met dezelfde foutisolatie en alleen tellingen in `counts`.

### Gevolgen voor latere WP's
- **WP-20:**
  - **Insert.** Alleen `spot_id`, `organizer_name`, `starts_at`, `ends_at`, `note`, `seats_free`, `departure_point` en `tikkie_url` (eventueel `organizer_id`, maar dat volgt al uit `auth.uid()`). Andere kolommen geven `42501`. `createSession` doet `.insert({...}).select('slug').single()`.
  - **Slugbotsing.** Heel onwaarschijnlijk, maar een `23505` op `sessions_slug_key` mag één keer opnieuw geprobeerd worden.
  - **Validatie gelijk aan de CHECKs:**
    - `organizer_name` getrimd, 1–30 code points (`[...s].length`), zonder regeleinden;
    - `ends_at > starts_at` en hoogstens 16 uur;
    - `seats_free` 0–8;
    - `note` hoogstens 280 en `departure_point` hoogstens 80 code points;
    - `tikkie_url` begint met `https://`, zonder witruimte, hoogstens 200 tekens.

    Lege optionele velden worden `null`. Bij een `/go`-window langer dan 16 uur kapt het formulier `end` af op `start + 16 h`.
  - **Rate limit.** De elfde sessie binnen 24 uur geeft `code PT400`, `message rate_limited`. Toon daarvoor een eigen melding.
  - **Update.** Alleen de 8 bewerkbare velden plus `cancelled_at`. `cancelSession` zet `cancelled_at = new Date().toISOString()`. Verwijderen kan niet (geen delete-recht).
  - **`listMySessions`.** RLS beperkt de resultaten tot de eigen sessies. Gebruik een expliciete kolomlijst; `recent_rsvp_creates` hoeft niet in het `Session`-type. Het aantal RSVP's per sessie haal je via `get_public_session(slug)`.
  - **Tijden.** `updated_at` verandert ook bij nieuwe RSVP's (A4); gebruik die kolom dus niet als "laatst bewerkt".
- **WP-21:**
  - **Foutmeldingen.** Map de RPC-fouten op `error.code === 'PT400'` en `error.message`. Een andere fout krijgt een algemene melding.
  - **Onbekende sessie.** `get_public_session` geeft `null` → "Sessie niet gevonden".
  - **Formulier.** Na een geslaagde `rsvp_create` sla je `{rsvp_id, edit_token}` op onder `shakka:rsvp:{slug}`. Een sessie is gesloten als `cancelled` waar is of `ends_at <= now`. Toon dan geen formulier, maar wel "Afmelden" voor wie al een token heeft (`rsvp_delete` blijft werken).
  - **Wijzigen.** `rsvp_update` stuurt alle vijf parameters mee. Geeft hij `invalid_token`, dan bestaat de RSVP niet meer (de organisator of de opruimstap heeft hem verwijderd); wis de `localStorage`-sleutel.
  - **Afmelden.** Geeft `rsvp_delete` `false`, wis de sleutel dan ook.
  - **Carpool** (A6):
    - "zoekt een lift" = `needs_ride` en `rides_with` is `null`;
    - "rijdt mee met X" = `needs_ride` en `rides_with = X.id`;
    - meerijden kan alleen bij iemand met `offers_ride`.
  - **Tikkie-link.** Toon de host van `tikkie_url` naast de link: de organisator kan elke `https`-URL invullen.
- **WP-22:**
  - `db_usage()` moet `security definer` zijn om rijen in `sessions` en `rsvps` te kunnen tellen (`service_role` heeft daar geen rechten, A5).
  - IP-limieten blijven buiten scope. Als misbruik toch voorkomt: Supabase heeft geen per-IP-limiet voor PostgREST in de gratis tier; dan is een moderatie-RPC voor de organisator de eerste stap (zie Risico's R1).
- **WP-23:**
  - `delete_my_account()` verwijdert via `auth.users` → `sessions` (cascade) → `rsvps` (cascade) ook de sessies van de gebruiker. RSVP's die de gebruiker zonder account bij anderen heeft geplaatst, zijn niet aan zijn account gekoppeld; die verwijdert hij met zijn token of ze verdwijnen na de bewaartermijn.
  - Privacytekst:
    - voornaam bij een RSVP, en optioneel lift-informatie;
    - de bewaartermijn van 7 dagen na het einde van de sessie;
    - in de database geen IP-adres; de API-gateway van Supabase logt verzoeken (A14);
    - de `localStorage`-sleutels `shakka:rsvp:{slug}` en `shakka:organizer_name`.
  - `axe` op `/s/[slug]` met fixturedata in de vorm van het contract hierboven.

## Edge cases

| # | Geval | Gedrag |
|---|---|---|
| E1 | `anon` doet `select`, `insert`, `update` of `delete` op `sessions` of `rsvps` | 42501 (geen privilege). Via REST: 401. |
| E2 | `authenticated` leest of schrijft `rsvps` direct | 42501. |
| E3 | `service_role` leest `sessions` of `rsvps` direct | 42501. Alleen `purge_expired_sessions` is uitvoerbaar. |
| E4 | A insert met `organizer_id` van B | De trigger telt 0 (RLS, invoker), daarna `WITH CHECK` → 42501. |
| E5 | A insert met eigen `slug`, `id`, `cancelled_at`, `recent_rsvp_creates` of `created_at` | 42501 (kolomprivilege). |
| E6 | A wijzigt of leest een sessie van B | Lezen: 0 rijen. Update: 0 rijen, geen fout, data van B ongewijzigd. |
| E7 | A wijzigt `organizer_id`, `slug` of `recent_rsvp_creates` | 42501. |
| E8 | A verwijdert een eigen sessie | 42501. Annuleren kan via `cancelled_at`. |
| E9 | 11e sessie van A binnen 24 uur (ook als eerdere geannuleerd zijn) | `PT400` `rate_limited`. Een sessie van 25 uur geleden telt niet mee. |
| E10 | Twee gelijktijdige inserts bij de 10e sessie | Advisory lock per organisator: de tweede wacht en krijgt `rate_limited`. |
| E11 | `ends_at = starts_at`, `ends_at < starts_at` of meer dan 16 uur | 23514. Precies 16 uur is toegestaan. |
| E12 | `tikkie_url` met `http://`, witruimte of meer dan 200 tekens | 23514. |
| E13 | `organizer_name` met spatie eromheen, leeg, 31 tekens of een regeleinde | 23514. |
| E14 | `get_public_session` met een onbekende slug, `null`, minder dan 10 tekens, meer dan 64 tekens of ongeldige tekens | `null`. Zonder fout en zonder query bij een ongeldige vorm. |
| E15 | `get_public_session` voor een geannuleerde sessie | `cancelled: true` plus de RSVP's. |
| E16 | `get_public_session` voor een afgelopen sessie (binnen de bewaartermijn) | Normaal resultaat; WP-21 beslist op basis van `ends_at`. |
| E17 | `rsvp_create` met een naam van spaties of 31 tekens, of een naam met een regeleinde | `invalid_input`. Een naam als `"  Sanne  "` wordt opgeslagen als `"Sanne"`. |
| E18 | `rsvp_create` met `p_ride` `null` of `'walk'`, `p_seats_offered` 9 of -1, of stoelen bij `own` of `needs_ride` | `invalid_input`. |
| E19 | `rsvp_create` op een onbekende, geannuleerde of afgelopen sessie | `session_closed`. |
| E20 | 31e RSVP | `session_full`, vóór de controle op `rate_limited`. |
| E21 | 11e `rsvp_create` binnen 10 minuten, ook als eerdere RSVP's al zijn afgemeld | `rate_limited`. Na 10 minuten kan het weer; de array wordt opgeschoond. |
| E22 | Gelijktijdige `rsvp_create` bij de 30e RSVP | `for update` op de sessie zet ze achter elkaar; de tweede krijgt `session_full`. |
| E23 | `rsvp_update` met een token van 42 of 44 tekens, `+` of `/`, of `null` | `invalid_token`. |
| E24 | `rsvp_update` met een goedgevormde maar onbekende token | `invalid_token`. |
| E25 | `rsvp_update` met `rides_with` naar zichzelf, naar een andere sessie, naar iemand die geen lift aanbiedt, of met eigen `ride` ongelijk aan `needs_ride` | `invalid_input`. |
| E26 | Een aanbieder wordt `own` of `needs_ride` | `rides_with` van zijn meerijders wordt `null`. |
| E27 | Een aanbieder meldt zich af | De FK `on delete set null (rides_with)` zet `rides_with` van de meerijders op `null`. |
| E28 | `rsvp_update` op een geannuleerde of afgelopen sessie | `session_closed`. |
| E29 | `rsvp_delete` met een verkeerde, misvormde of al gebruikte token | `false`. |
| E30 | `rsvp_delete` op een geannuleerde of afgelopen sessie | `true` (A10). |
| E31 | De RSVP verdwijnt tussen het opzoeken en de update (`rsvp_update`) | De update raakt 0 rijen → `invalid_token`. |
| E32 | `purge_expired_sessions` als `anon` of `authenticated` | 42501. Via REST: 401 of 403. |
| E33 | `purge_expired_sessions(null)` | `invalid_input`. |
| E34 | Een sessie met `ends_at` precies `p_now - 7 dagen` | Blijft staan (strikte `<`). |
| E35 | Een organisator verwijdert zijn account (`auth.users`) | Zijn sessies en hun RSVP's gaan mee (cascade). |
| E36 | Een spot met sessies verwijderen | 23503 (`restrict`, A7). |
| E37 | Een RSVP-rij met `rides_with` naar een RSVP van een andere sessie (direct, als `postgres`) | 23503 (samengestelde FK). |
| E38 | Pipeline: de RPC geeft `DatabaseError` | Stap `failed` met `error_type` `DatabaseError (…)`. Run `partial`, exitcode 0, `::error::step sessions_cleanup failed (…)`. De andere stappen zijn al gedraaid. |
| E39 | Pipeline: de RPC geeft `null`, een string, `True` of een negatief getal | `ValueError` → stap `failed` met `error_type` `ValueError`. |
| E40 | Pipeline: `now` is naïef | `ValueError` vóór de request (`run_hourly` controleert dit al eerder). |
| E41 | De RPC ontbreekt in het remote project (migratie nog niet gepusht) | `PGRST202` → stap `failed`, run `partial`. Elk uur een `::error::`-annotatie, maar geen mail (exit 0), tot Lars pusht (RUNBOOK §16). |

## Testplan
Tests eerst. De pgTAP-bestanden schrijft de builder vóór de migratie (rood), de Python-tests vóór `jobs/sessions.py` en de wijzigingen aan de fake en de pipeline.

**Conventies voor pgTAP** (gelijk aan WP-01 en WP-17):
- Elk bestand: `begin;`, `create extension if not exists pgtap with schema extensions;`, `select plan(N);`, de asserts, `select * from finish();` en `rollback;`.
- Rollen wisselen met `set local role …`. Voor `authenticated` komt daarbij `set_config('request.jwt.claims', '{"sub":"<uuid>","role":"authenticated"}', true)`. Terug met `reset role`.
- Altijd de getypeerde varianten met schema en beschrijving (`::name`, `::name[]`).
- Fouten toetsen met `throws_ok(sql, '<sqlstate>', <message of null>, '<beschrijving>')`. Voor RPC-fouten altijd `'PT400'` met de exacte message, bijvoorbeeld `throws_ok($$select public.rsvp_create(…)$$, 'PT400', 'session_full', '…')`.

**Vaste waarden:**
- Gebruikers: A = `11111111-1111-1111-1111-111111111111`, B = `22222222-2222-2222-2222-222222222222`.
- Spot: `('pgtap-spot', 'Pgtap Spot')`.
- `HASH(x)` staat voor `encode(sha256(convert_to(x, 'UTF8')), 'hex')`.

### `01_schema.test.sql` (bestaande asserts aanvullen, `plan(71)` blijft gelijk)
- `tables_are`: de lijst plus `'sessions'` en `'rsvps'`.
- Kolom-`set_eq`, 24 rijen erbij:
  - `sessions`:
    - `id uuid f`, `slug text f`, `spot_id text f`, `organizer_id uuid f`, `organizer_name text f`;
    - `starts_at` en `ends_at`: `timestamp with time zone f`;
    - `note text t`, `seats_free smallint t`, `departure_point text t`, `tikkie_url text t`;
    - `cancelled_at timestamp with time zone t`;
    - `recent_rsvp_creates timestamp with time zone[] f`;
    - `created_at` en `updated_at`: `timestamp with time zone f`.
  - `rsvps`:
    - `id uuid f`, `session_id uuid f`, `first_name text f`, `ride text f`;
    - `seats_offered smallint t`, `rides_with uuid t`, `edit_token_hash text f`;
    - `created_at` en `updated_at`: `timestamp with time zone f`.
- FK-`set_eq`, erbij: `('sessions', 'spots', 'r')`, `('sessions', 'auth.users', 'c')`, `('rsvps', 'sessions', 'c')` en `('rsvps', 'rsvps', 'n')`.

### `07_sessions.test.sql`: `plan(107)`
**Fixture** (als `postgres`, in deze volgorde):
```sql
insert into auth.users (id, email) values (A, 'a@example.test'), (B, 'b@example.test');
insert into public.spots (id, name) values ('pgtap-spot', 'Pgtap Spot');
insert into public.sessions (id, slug, spot_id, organizer_id, organizer_name, starts_at, ends_at) values
  ('b0000000-0000-4000-8000-000000000001', 'pgtap-b-session-01', 'pgtap-spot', B, 'Bob',
   now() + interval '1 day', now() + interval '1 day 3 hours');
insert into public.sessions (id, slug, spot_id, organizer_id, organizer_name, starts_at, ends_at, created_at) values
  ('a0000000-0000-4000-8000-000000000001', 'pgtap-a-old-00001', 'pgtap-spot', A, 'Anna',
   now() - interval '26 hours', now() - interval '25 hours', now() - interval '25 hours');
insert into public.rsvps (id, session_id, first_name, ride, seats_offered, edit_token_hash) values
  ('c0000000-0000-4000-8000-000000000001', 'b0000000-0000-4000-8000-000000000001', 'Eva',
   'offers_ride', 2, HASH(repeat('D', 43)));
```
Namen in de lijst hieronder: SB = `b0000000-…-000000000001`, RB1 = `c0000000-…-000000000001`. Een "geldige sessie-insert als postgres" is `(slug, spot_id, organizer_id, organizer_name, starts_at, ends_at)` met `('pgtap-check-0001', 'pgtap-spot', B, 'Bob', now() + interval '1 day', now() + interval '1 day 3 hours')`, waarin precies het genoemde veld afwijkt of erbij komt.

**Vorm (1–11).**
1. `columns_are` `sessions`: de 15 kolommen.
2. `columns_are` `rsvps`: de 9 kolommen.
3. `col_is_pk` `sessions` (`id`).
4. `col_is_pk` `rsvps` (`id`).
5. `has_index` `sessions_organizer_created_idx`.
6. `has_index` `sessions_ends_at_idx`.
7. `has_index` `sessions_spot_id_idx`.
8. `has_index` `rsvps_rides_with_idx`.
9. `has_trigger` `sessions_prepare_insert`.
10. `has_trigger` `sessions_set_updated_at`.
11. `has_trigger` `rsvps_set_updated_at`.

**Rechten (12–34).**
- 12–14. `table_privs_are` `sessions`: `anon` `'{}'`, `authenticated` `['SELECT']`, `service_role` `'{}'`.
- 15–17. `table_privs_are` `rsvps`: `anon`, `authenticated` en `service_role`, alle drie `'{}'`.
- 18–32. `column_privs_are` `sessions` × `authenticated` voor elk van de 15 kolommen, volgens de tabel "Kolomprivileges" (alfabetisch gesorteerde arrays, bijvoorbeeld `array['INSERT','SELECT','UPDATE']::name[]`).
- 33. `policies_are` `sessions`: `sessions_select_own`, `sessions_insert_own` en `sessions_update_own`.
- 34. `policies_are` `rsvps`: `'{}'`.

**Functies (35–44).**
- 35–39. `has_function`:
  - `get_public_session` met `['text']`;
  - `rsvp_create` met `['text','text','text','integer']`;
  - `rsvp_update` met `['text','text','text','integer','uuid']`;
  - `rsvp_delete` met `['text']`;
  - `purge_expired_sessions` met `['timestamp with time zone']`.
- 40. `set_eq($$select p.proname::text from pg_proc p where p.pronamespace = 'public'::regnamespace and has_function_privilege('anon', p.oid, 'EXECUTE')$$, $$values ('get_public_session'), ('rsvp_create'), ('rsvp_update'), ('rsvp_delete')$$, …)`.
- 41. Idem voor `authenticated`, met dezelfde vier.
- 42. Idem voor `service_role`: alleen `('purge_expired_sessions')`.
- 43. `set_eq` op de namen van functies in `public` met `prosecdef`: `handle_new_user`, `get_public_session`, `rsvp_create`, `rsvp_update`, `rsvp_delete` en `purge_expired_sessions`.
- 44. `is_empty($$select p.proname from pg_proc p where p.pronamespace = 'public'::regnamespace and p.prosecdef and not coalesce(p.proconfig @> array['search_path=""'], false)$$, …)`.

**Constraints op `sessions` (45–61)**, als `postgres`, telkens een "geldige sessie-insert" met één afwijking:
- 45–48. `organizer_name` is `''`, `repeat('x', 31)`, `' Lars'` of `E'La\nrs'` → `23514`.
- 49. `ends_at = starts_at` → `23514`.
- 50. `ends_at = starts_at + interval '17 hours'` → `23514`.
- 51. `lives_ok`: id `b0000000-0000-4000-8000-000000000016`, slug `'pgtap-16h-000001'`, `ends_at = starts_at + interval '16 hours'`. Deze sessie heet S16.
- 52. `note = repeat('x', 281)` → `23514`.
- 53–54. `seats_free` is 9 of -1 → `23514`.
- 55. `departure_point = repeat('x', 81)` → `23514`.
- 56. `tikkie_url = 'http://tikkie.me/pay/x'` → `23514` (AC-5).
- 57. `tikkie_url = 'https://tikkie.me/pay/a b'` → `23514`.
- 58. `tikkie_url = 'https://' || repeat('a', 193)` (201 tekens) → `23514`.
- 59. `slug = 'short'` → `23514`.
- 60. `spot_id = 'pgtap-unknown'` → `23503`.
- 61. `lives_ok`: id `b0000000-0000-4000-8000-000000000017`, slug `'pgtap-tikkie-0001'`, `tikkie_url = 'https://tikkie.me/pay/abc'`.

**Constraints op `rsvps` (62–71)**, als `postgres`, in SB tenzij anders vermeld, met `edit_token_hash = HASH('t<n>')` per assert (uniek):
- 62–63. `first_name` is `''` of `repeat('x', 31)` → `23514`.
- 64. `ride = 'walk'` → `23514`.
- 65. `ride = 'own'` met `seats_offered = 2` → `23514`.
- 66. `ride = 'offers_ride'` met `seats_offered = 9` → `23514`.
- 67. `edit_token_hash = 'abc'` → `23514`.
- 68. Expliciete id `c0000000-…-000000000068` met `rides_with` gelijk aan die id, `ride = 'needs_ride'` → `23514`.
- 69. `ride = 'own'`, `rides_with = RB1` → `23514`.
- 70. In S16: `ride = 'needs_ride'`, `rides_with = RB1` → `23503`.
- 71. `edit_token_hash = HASH(repeat('D', 43))` (gelijk aan RB1) → `23505`.

**Slug-generatie (72–73)**, als `postgres`:
- 72. `lives_ok`: een insert zonder `slug`, id `b0000000-0000-4000-8000-000000000018` (SGEN), organisator B.
- 73. `ok((select slug ~ '^[A-Za-z0-9_-]{22}$' from public.sessions where id = SGEN), …)`.

**Als A, `authenticated` (74–92):**
- 74. `lives_ok`: `insert into public.sessions (spot_id, organizer_name, starts_at, ends_at, note) values ('pgtap-spot', 'Anna', now() + interval '1 day', now() + interval '1 day 2 hours', 'pgtap-a-1')`.
- 75. `is_empty($$select 1 from public.sessions where organizer_id = B$$)`.
- 76. `ok((select slug ~ '^[A-Za-z0-9_-]{10,}$' from public.sessions where note = 'pgtap-a-1'), …)` (AC-2).
- 77. Een insert met `organizer_id = B` → `42501` (AC-2).
- 78. Een insert met `slug` → `42501`.
- 79. Een insert met `cancelled_at` → `42501`.
- 80. Een insert met `recent_rsvp_creates` → `42501`.
- 81. `lives_ok`: `update public.sessions set organizer_name = 'Hacked' where id = SB` (0 rijen).
- 82. `lives_ok`: `update public.sessions set cancelled_at = now() where note = 'pgtap-a-1'`.
- 83–85. `update … set` `organizer_id = B`, `slug = 'pgtap-new-slug-01'` of `recent_rsvp_creates = '{}'` op de eigen sessie → telkens `42501`.
- 86. `delete from public.sessions where note = 'pgtap-a-1'` → `42501`.
- 87–90. `select 1 from public.rsvps`, een insert in `rsvps`, `update public.rsvps set first_name = 'x'` en `delete from public.rsvps` → telkens `42501` (AC-1).
- 91. `lives_ok`: `insert into public.sessions (spot_id, organizer_name, starts_at, ends_at) select 'pgtap-spot', 'Anna', now() + interval '2 days', now() + interval '2 days 2 hours' from generate_series(1, 9)`. A heeft nu 10 sessies in 24 uur; de fixture van 25 uur geleden telt niet mee.
- 92. Nog één insert → `throws_ok(…, 'PT400', 'rate_limited', …)` (AC-5).

**Als `postgres` (93–94):**
- 93. `is((select organizer_name from public.sessions where id = SB), 'Bob', …)`.
- 94. `ok((select cancelled_at is not null from public.sessions where note = 'pgtap-a-1'), …)`.

**Als `anon` (95–102), alles `42501` (AC-1):** op `sessions` en daarna op `rsvps` telkens `select 1 from …`, een insert, `update … set` (één kolom) en `delete from …`.

**Als `service_role` (103–104):** `select 1 from public.sessions` en `select 1 from public.rsvps` → `42501`.

**Cascades (105–107)**, als `postgres`:
- 105. `delete from public.sessions where id = SB`, daarna `is_empty($$select 1 from public.rsvps where session_id = SB$$)`.
- 106. `delete from auth.users where id = A`, daarna `is_empty($$select 1 from public.sessions where organizer_id = A$$)`.
- 107. `delete from public.spots where id = 'pgtap-spot'` → `23503` (S16, de tikkie-sessie en SGEN van B bestaan nog).

Asserts 105 en 106 zijn elk één pgTAP-assert. De delete-statements ervoor zijn gewone statements.

### `08_session_rpcs.test.sql`: `plan(62)`
**Fixture** (als `postgres`). Organisator A, spot `pgtap-spot`. Sessies (alle met organisator A, `organizer_name 'Lars'`, en expliciete `id`, `slug`, `starts_at` en `ends_at`):

| Naam | id | slug | starts_at | ends_at | Extra |
|---|---|---|---|---|---|
| S_OPEN | `50000000-0000-4000-8000-000000000001` | `pgtap-open-0001` | now()+1 day | now()+1 day 4 h | `note 'Parkeren bij de strandopgang'`, `seats_free 3`, `departure_point 'Utrecht CS'`, `tikkie_url 'https://tikkie.me/pay/pgtap'` |
| S_CANCEL | `…02` | `pgtap-cancel-01` | now()+1 day | now()+1 day 2 h | `cancelled_at now()` |
| S_ENDED | `…03` | `pgtap-ended-001` | now()−5 h | now()−1 h | |
| S_FULL | `…04` | `pgtap-full-0001` | now()+1 day | now()+1 day 2 h | |
| S_RATE | `…05` | `pgtap-rate-0001` | now()+1 day | now()+1 day 2 h | |
| S_OLD | `…06` | `pgtap-old-00001` | now()−8 days 3 h | now()−8 days | |
| S_EDGE | `…07` | `pgtap-edge-0001` | now()−7 days 2 h | now()−7 days | |
| S_RECENT | `…08` | `pgtap-recent-01` | now()−6 days 2 h | now()−6 days | |

RSVP's (`postgres`):

| Naam | id | sessie | first_name | ride | seats | token | created_at |
|---|---|---|---|---|---|---|---|
| R_DRIVER | `60000000-0000-4000-8000-000000000001` | S_OPEN | Eva | offers_ride | 2 | `repeat('D',43)` | now()−2 h |
| R_CANCEL | `…02` | S_CANCEL | Tom | own | null | `repeat('C',43)` | default |
| R_ENDED_DRIVER | `…03` | S_ENDED | Piet | offers_ride | 1 | `repeat('E',43)` | default |
| R_OLD1, R_OLD2 | `…04`, `…05` | S_OLD | Ida, Jan | own | null | `repeat('O',43)`, `repeat('P',43)` | default |

Plus 30 RSVP's in S_FULL: `insert … select gen_random_uuid(), S_FULL, 'Gast ' || i, 'own', null, HASH('full-' || i), now() - interval '1 hour' from generate_series(1, 30) i`.

Opgeslagen resultaten van `rsvp_create` gaan via `set_config('pgtap.<naam>', <jsonb>::text, true)` en worden later gelezen met `current_setting('pgtap.<naam>')::jsonb`. Daarin staan `T(c1)` (`->>'edit_token'`) en `ID(c1)` (`->>'rsvp_id'`)`::uuid`.

**`get_public_session` als `anon` (1–9, AC-3):**
1. `is(public.get_public_session('pgtap-unknown-01'), null::jsonb, …)`.
2. `is(public.get_public_session('bad slug!'), null::jsonb, …)`.
3. `set_eq` op `jsonb_object_keys(get_public_session('pgtap-open-0001'))` = `session`, `rsvps`.
4. `set_eq` op de sleutels van `->'session'` = de 11 contractsleutels.
5. `set_eq` op de sleutels van `->'rsvps'->0` = `id`, `first_name`, `ride`, `seats_offered`, `rides_with` en `created_at`.
6. `ok(public.get_public_session('pgtap-open-0001')::text !~ '(organizer_id|edit_token|email|user_id|recent_rsvp_creates)', …)`.
7. `is(…->'session'->>'spot_name', 'Pgtap Spot', …)`.
8. `is(…('pgtap-open-0001')->'session'->>'cancelled', 'false', …)`.
9. `is(…('pgtap-cancel-01')->'session'->>'cancelled', 'true', …)`.

**`rsvp_create` en `rsvp_update` als `anon` (10–20, AC-4):**
10. `ok((select set_config('pgtap.c1', public.rsvp_create('pgtap-open-0001', '  Sanne  ', 'needs_ride', null)::text, true))::jsonb->>'edit_token' ~ '^[A-Za-z0-9_-]{43}$', …)`.
11. `set_eq` op de sleutels van `current_setting('pgtap.c1')::jsonb` = `rsvp_id`, `edit_token`.
12. `results_eq($$select e->>'first_name' from jsonb_array_elements(public.get_public_session('pgtap-open-0001')->'rsvps') with ordinality as t(e, n) order by n$$, $$values ('Eva'), ('Sanne')$$, …)`.
13. `is(public.rsvp_update(T(c1), 'Sanne', 'needs_ride', null, R_DRIVER)->>'rides_with', R_DRIVER::text, …)`.
14. `rsvp_update(repeat('Z',43), 'X', 'own', null, null)` → `PT400 invalid_token`.
15. `rsvp_update('abc', 'X', 'own', null, null)` → `PT400 invalid_token`.
16. `rsvp_update(T(c1), 'Sanne', 'needs_ride', null, ID(c1))` → `PT400 invalid_input` (naar zichzelf).
17. `rsvp_update(T(c1), 'Sanne', 'needs_ride', null, R_ENDED_DRIVER)` → `PT400 invalid_input` (andere sessie).
18. `rsvp_update(T(c1), 'Sanne', 'own', null, R_DRIVER)` → `PT400 invalid_input`.
19. `rsvp_update(repeat('D',43), 'Eva', 'needs_ride', null, ID(c1))` → `PT400 invalid_input` (c1 biedt geen lift aan).
20. `rsvp_update(repeat('C',43), 'Tom', 'own', null, null)` → `PT400 session_closed`.

**Validatie van `rsvp_create` op S_OPEN als `anon` (21–30, AC-5):** alles `PT400 invalid_input`, behalve 30.
- 21–25. Een naam `''`, `'   '`, `repeat('x', 31)`, `null` of `E'Sa\nnne'` (met `'own'` en `null`).
- 26–27. `p_ride` is `'walk'` of `null`.
- 28. `offers_ride` met 9 stoelen.
- 29. `own` met 2 stoelen.
- 30. `lives_ok`: `rsvp_create('pgtap-open-0001', repeat('x', 30), 'offers_ride', 0)`.

**Gesloten, vol en rate limit als `anon` (31–39, AC-5):**
- 31. `rsvp_create('pgtap-cancel-01', 'Ann', 'own', null)` → `PT400 session_closed`.
- 32. Idem met `'pgtap-ended-001'` → `session_closed`.
- 33. Idem met `'pgtap-unknown-01'` → `session_closed`.
- 34. Idem met `'pgtap-full-0001'` → `session_full`.
- 35. `lives_ok($$select public.rsvp_create('pgtap-rate-0001', 'Gast', 'own', null) from generate_series(1, 10)$$, …)`.
- 36. Nog één `rsvp_create` op `pgtap-rate-0001` → `PT400 rate_limited`.
- Dan `reset role; delete from public.rsvps where session_id = S_RATE; set local role anon;`.
- 37. Weer een `rsvp_create` → `rate_limited` (afgemelde RSVP's tellen mee, A4).
- Dan `reset role; update public.sessions set recent_rsvp_creates = array_fill(now() - interval '11 minutes', array[10]) where id = S_RATE; set local role anon;`.
- 38. `lives_ok`: een `rsvp_create` op `pgtap-rate-0001`.
- Dan `reset role;`.
- 39. `is((select cardinality(recent_rsvp_creates) from public.sessions where id = S_RATE), 1, …)`.

**Carpool als `anon` (40–44):**
- 40. `lives_ok`: `rsvp_update(repeat('D',43), 'Eva', 'own', null, null)`.
- Dan `reset role;`.
- 41. `is((select rides_with from public.rsvps where id = ID(c1)), null::uuid, …)` (E26).
- Dan `set local role anon;`.
- 42. `ok((select set_config('pgtap.c2', public.rsvp_create('pgtap-open-0001', '  Noor ', 'needs_ride', null)::text, true)) is not null, …)`.
- 43. `lives_ok`: `rsvp_update(repeat('D',43), 'Eva', 'offers_ride', 3, null)`.
- 44. `lives_ok`: `rsvp_update(T(c2), 'Noor', 'needs_ride', null, R_DRIVER)`.

**`rsvp_delete` als `anon` (45–53, AC-4):**
- 45. `is(public.rsvp_delete(repeat('Z',43)), false, …)`.
- 46. `is(public.rsvp_delete('abc'), false, …)`.
- 47. `is(public.rsvp_delete(T(c1)), true, …)`.
- 48. `is(public.rsvp_delete(T(c1)), false, …)`.
- 49. `is(public.rsvp_delete(repeat('C',43)), true, …)` (geannuleerde sessie, A10).
- 50. `is(public.rsvp_delete(repeat('D',43)), true, …)`.
- Dan `reset role;`.
- 51. `is((select rides_with from public.rsvps where id = ID(c2)), null::uuid, …)` (E27).
- 52. `is((select first_name from public.rsvps where id = ID(c2)), 'Noor', …)`.
- 53. `ok((select edit_token_hash = HASH(T(c2)) and edit_token_hash <> T(c2) from public.rsvps where id = ID(c2)), …)` (AC-4).

**`authenticated` (A) en de opruimfunctie (54–62, AC-6):**
- 54. Als A: `ok(public.get_public_session('pgtap-open-0001') is not null, …)`.
- 55. Als A: `lives_ok`: `rsvp_create('pgtap-open-0001', 'Lars', 'offers_ride', 2)`.
- 56. Als A: `purge_expired_sessions(now())` → `42501`.
- 57. Als `anon`: `purge_expired_sessions(now())` → `42501`.
- 58. Als `service_role`: `purge_expired_sessions(null)` → `PT400 invalid_input`.
- 59. Als `service_role`: `is(public.purge_expired_sessions(now()), 1, …)`.
- Dan `reset role;`.
- 60. `is_empty`: S_OLD bestaat niet meer.
- 61. `is_empty($$select 1 from public.rsvps where session_id = S_OLD$$)` (cascade).
- 62. `results_eq($$select count(*)::int from public.sessions where id in (S_EDGE, S_RECENT, S_ENDED)$$, array[3], …)`. S_EDGE (precies 7 dagen) blijft staan.

### Python
**`ingest/tests/test_jobs_sessions.py`** (nieuw; met `NOW` uit `job_fixtures`):
- `test_purge_calls_rpc_with_iso_now`: de geregistreerde handler geeft `3` terug, het resultaat is `3`, en `db.rpc_calls == [("purge_expired_sessions", {"p_now": iso_utc(NOW)})]`.
- `test_purge_naive_now_raises`: `ValueError`, en `rpc_calls` blijft leeg.
- `test_purge_rejects_unexpected_response` (geparametriseerd over `None`, `"3"`, `True`, `-1`, `1.5`): `ValueError`.
- `test_purge_database_error_propagates`: een handler die `DatabaseError(status=503)` gooit → `DatabaseError`.
- `test_purge_with_builtin_fake`:
  - seed `sessions`:
    - id `s-old`, `ends_at = NOW - 8 d`;
    - id `s-edge`, `ends_at = NOW - 7 d`;
    - id `s-new`, `ends_at = NOW - 6 d`;
  - seed `rsvps`: `r1` en `r2` met `session_id = s-old`, en `r3` met `s-new`;
  - na `purge_expired_sessions(db, now=NOW)` is het resultaat `1`;
  - de sessie-id's zijn `{s-edge, s-new}` en de RSVP-id's `{r3}`.
- `test_retention_constant`: `SESSION_RETENTION == timedelta(days=7)`.

**`ingest/tests/test_fakes.py`** (erbij):
- `test_delete_session_cascades_rsvps`: na `delete("sessions", filters={"id": "eq.s1"})` zijn de RSVP's van `s1` weg en die van `s2` niet. `writes` krijgt één entry `("delete", "sessions")`.
- `test_builtin_purge_boundary`: hetzelfde als de purge-test hierboven, maar direct met `fake.rpc("purge_expired_sessions", {"p_now": …})`.
- `test_registered_rpc_overrides_builtin`: na `register_rpc("purge_expired_sessions", lambda a: 42)` geeft de aanroep `42` en blijven de rijen staan.
- `test_builtin_purge_requires_p_now`: `rpc("purge_expired_sessions", {})` → `DatabaseError` met `code == "PT400"`.

**`ingest/tests/test_pipeline.py`** (AC-7):
- `test_steps_contract_order`: de lijst eindigt op `"alerts", "sessions_cleanup"`, en is gelijk aan `STEP_NAMES`.
- `test_all_steps_ok_records_run`:
  - `alerts = next(s for s in row["steps"] if s["name"] == "alerts")` in plaats van `row["steps"][-1]`;
  - erbij: `row["steps"][-1]["name"] == "sessions_cleanup"`, `row["steps"][-1]["status"] == "ok"` en `row["steps"][-1]["counts"] == {"deleted": 0}`.
- Nieuw `test_sessions_cleanup_deletes_expired`:
  - seed een sessie met `ends_at = NOW - 8 d` en één RSVP;
  - `run_real` → stap `sessions_cleanup` is `ok` met `counts == {"deleted": 1}`;
  - de tabellen `sessions` en `rsvps` zijn leeg;
  - `("purge_expired_sessions", {"p_now": iso_utc(NOW)})` staat in `db.rpc_calls`.
- Nieuw `test_sessions_cleanup_failure_is_partial`:
  - `db.register_rpc("purge_expired_sessions", <gooit DatabaseError("boom", status=503)>)`, plus `seed_user(db)`, net als in de ok-test;
  - stap `sessions_cleanup` is `failed` en `error_type.startswith("DatabaseError")`;
  - alle andere stappen hebben dezelfde status als in `test_all_steps_ok_records_run` (allemaal `ok`);
  - `report.status == "partial"` en `report.exit_code == 0`;
  - de rij in `ingest_runs` heeft `status == "partial"`;
  - een annotatie begint met `"::error::step sessions_cleanup failed (DatabaseError"`.
- Nieuw `test_sessions_cleanup_value_error_is_failed`: de handler geeft `None` → de stap is `failed` met `error_type == "ValueError"`, en de run is `partial`.

**`ingest/tests/test_cli_pipeline.py`**: in `test_no_user_ids_or_message_texts_in_output` wordt `alerts = next(s for s in db.rows("ingest_runs")[0]["steps"] if s["name"] == "alerts")`.

**`ingest/tests/test_migrations.py`**:
- `test_no_later_milestone_tables` verwijderen.
- `test_session_retention_matches_migration`: in de migratie die `create function public.purge_expired_sessions` bevat, staat `ends_at < p_now - interval '7 days'`, en `SESSION_RETENTION == timedelta(days=7)`.
- `test_no_grants_on_rsvps`: `re.search(r"grant\s[^;]*\bon\s+table\s[^;]*\bpublic\.rsvps\b", _sql(), re.I)` is `None`.
- `test_security_definer_functions_pin_search_path`:
  - splits `_sql()` op `re.split(r"create (?:or replace )?function", sql, flags=re.I)`;
  - voor elk deel dat vóór de eerste `$$` `security definer` bevat, staat daar ook `set search_path = ''`.

### Koppeling acceptatiecriteria → bewijs

| AC | Bewijs |
|---|---|
| AC-1 | `supabase test db` groen (alle 8 bestanden). `07`: 12–17, 87–90 (`authenticated` op `rsvps`), 95–102 (`anon` op beide tabellen, alle vier de operaties), 103–104. |
| AC-2 | `07`: 74 en 76 (eigen sessie, slug-regex), 77 (`organizer_id` van een ander → 42501), 81 en 93 (updaten van een sessie van een ander raakt niets). |
| AC-3 | `08`: 1–9 (exacte sleutels, geen verboden sleutels, onbekende slug → `null`). |
| AC-4 | `08`: 10–15 (token, update, `invalid_token`), 45–50 (`false` en `true`), 53 (hash ≠ token). |
| AC-5 | `08`: 34 (`session_full`), 35–37 (`rate_limited` bij de 11e), 31–33 (`session_closed`), 21 en 23 (lege naam, naam van 31 tekens). `07`: 56 (`http://`), 91–92 (11e sessie). |
| AC-6 | `08`: 59–62 (alleen `ends_at < p_now - 7 d`, met cascade), 56–57 (`authenticated` en `anon` → 42501). `07`: 40–42. |
| AC-7 | `cd ingest && uv run pytest tests/test_pipeline.py`: `test_steps_contract_order`, `test_sessions_cleanup_failure_is_partial`, `test_sessions_cleanup_deletes_expired`. Daarnaast de volledige suite plus ruff. |

## Externe afhankelijkheden
Er komen geen nieuwe packages bij (Python en npm). Gebruikte onderdelen, gecontroleerd tegen de documentatie:
- **PostgREST v14** (lokaal v14.18): SQLSTATE `PTxyz` geeft HTTP-status `xyz`, en `code` in de body is de SQLSTATE; `P0001` en onbekende codes geven 400; `42501` geeft 401 of 403. [docs.postgrest.org/en/v14/references/errors.html](https://docs.postgrest.org/en/v14/references/errors.html)
- **Supabase database functions**: `security definer` alleen met een vaste `search_path` en volledig gekwalificeerde namen; `EXECUTE` intrekken van `public` en van de rol zelf, en daarna gericht granten. [supabase.com/docs/guides/database/functions](https://supabase.com/docs/guides/database/functions)
- **Standaard functieprivileges in Supabase** (`anon`/`authenticated` krijgen `EXECUTE` op nieuwe functies): [github.com/supabase/supabase/issues/43884](https://github.com/supabase/supabase/issues/43884), [discussie #45329](https://github.com/orgs/supabase/discussions/45329).
- **Supabase-extensies** staan in het schema `extensions` (`create extension … with schema extensions`). [supabase.com/docs/guides/database/extensions](https://supabase.com/docs/guides/database/extensions). Dat pgcrypto daar staat (en dus `extensions.gen_random_bytes`), bevestigen meerdere projectfixes, bijvoorbeeld [deze](https://github.com/bradytrock/truss/pull/69); de migratie doet daarom `create extension if not exists pgcrypto with schema extensions`, en RUNBOOK §16.2 controleert het remote project.
- **Postgres 17** (`major_version = 17` in `config.toml`):
  - `ON DELETE SET NULL (column_list)` (sinds 15) [CREATE TABLE](https://www.postgresql.org/docs/17/sql-createtable.html);
  - `WITH CHECK` na `BEFORE`-triggers, vóór andere constraints [CREATE POLICY](https://www.postgresql.org/docs/17/sql-createpolicy.html);
  - zichtbaarheid van eerder verwerkte rijen in row-level `BEFORE`-triggers (`VOLATILE`) [Visibility of Data Changes](https://www.postgresql.org/docs/17/trigger-datachanges.html);
  - `gen_random_uuid()`, `sha256(bytea)`, `uuid_send`, `pg_advisory_xact_lock` en `hashtextextended` zijn ingebouwd (`pg_catalog`).
- **pgTAP** (al in gebruik): `has_function`, `column_privs_are`, `table_privs_are`, `policies_are`, `set_eq`, `results_eq`, `throws_ok` met een eigen SQLSTATE.

## Risico's
- **R1. Spam met een gelekte link.** Wie de link heeft, kan per 10 minuten 10 nep-RSVP's plaatsen, tot 30 in totaal. De organisator heeft in deze WP geen RPC om andermans RSVP te verwijderen. Mitigatie nu: annuleren en een nieuwe sessie (nieuwe slug) delen, of Lars verwijdert rijen in de SQL-editor (RUNBOOK §16.5). Een moderatie-RPC voor de organisator is een kandidaat voor WP-22 en valt buiten deze scope.
- **R2. IP-adressen in platformlogs** (A14). Daar is niets aan te doen; het komt in de privacytekst (WP-23).
- **R3. pgcrypto staat op het remote project niet in `extensions`.** Dan faalt `rsvp_create` pas bij gebruik. Mitigatie: de controle in RUNBOOK §16.2 vóór `db push`. Lokaal en in CI toont `08` het aan.
- **R4. Toekomstige functies standaard uitvoerbaar.** Een latere WP die een functie toevoegt zonder revoke, laat asserts 40–42 van `07` falen. Dat is bewust een vangnet; RUNBOOK §8.6 beschrijft het patroon.
- **R5. Phishing via `tikkie_url`.** Elke `https`-URL is toegestaan. Organisatoren zijn ingelogde gebruikers (in M3 alleen Lars, `shouldCreateUser: false`). WP-21 toont de host en gebruikt `rel="noopener noreferrer"`.
- **R6. `updated_at` beweegt mee met RSVP's** (A4). Dat is gedocumenteerd voor WP-20.
- **R7. De databaseklok tegenover `p_now`.** `rsvp_create` en `rsvp_update` gebruiken `now()` van de database, de opruimfunctie gebruikt `p_now` van de runner. Een klokverschil van seconden is zonder gevolg. Een `p_now` ver in de toekomst (bug) zou te veel verwijderen; `p_now` komt altijd uit `runtime.utcnow()` en is één keer per run gemeten (WP-11).
- **R8. Remote nog niet gepusht na de merge.** Elk uur faalt de stap `sessions_cleanup` (`PGRST202`) met een annotatie, maar zonder mail (exit 0). RUNBOOK §16.2–16.3 en "Nodig van Lars" in WORK_PACKAGES.
- **R9. Supabase-linter.** Het Security Advisor-overzicht kan waarschuwen voor `security definer`-functies die via de API bereikbaar zijn. Dat is hier bewust zo; er is geen actie nodig.

## Buiten scope
- UI (WP-20, WP-21) en elke wijziging in `web/`.
- Rate limiting op IP-adres; IP-opslag.
- Een capaciteitscontrole voor meerijders (aantal meerijders ≤ `seats_offered`), en `seats_free` van de organisator koppelen aan RSVP's.
- Een moderatie-RPC voor de organisator (andermans RSVP verwijderen), en meldingen aan deelnemers.
- Een CLI-commando om handmatig op te ruimen. Dat kan via de uurlijkse stap of de SQL-editor.
- `docs/PRIVACY.md` en `/privacy` (WP-23); `db_usage` (WP-22).
- Aanpassingen aan `docs/WORK_PACKAGES.md` of `docs/STATUS.md` (orchestrator).

## Stappenplan voor de builder
1. **pgTAP en migratie.**
   - Schrijf `supabase/tests/07_sessions.test.sql` en `08_session_rpcs.test.sql` zoals beschreven, en pas `01_schema.test.sql` aan. `supabase db reset && supabase test db` faalt (rood).
   - Maak `supabase/migrations/20261015200000_sessions.sql` exact zoals onder Interfaces.
   - `supabase db reset` foutloos en `supabase test db` groen (alle bestanden, ook `01`–`06`). Klopt een `plan(N)` niet, tel dan opnieuw tegen de genummerde lijst; de nummering in de blueprint is bindend.
   - Commit: `feat(db): sessions and rsvps with RLS, RPCs and pgTAP (WP-19)`.
2. **`TABLE_KEYS` en de statische migratietests.**
   - Voeg `sessions` en `rsvps` toe aan `TABLE_KEYS`.
   - Pas `test_migrations.py` aan: verwijder `test_no_later_milestone_tables` en voeg de drie nieuwe tests toe.
   - `test_session_retention_matches_migration` importeert `SESSION_RETENTION`. Maak daarom in deze stap ook `shakka/jobs/sessions.py` met alleen `PURGE_RPC` en `SESSION_RETENTION`.
   - `uv run pytest` groen, ruff schoon. Commit.
3. **De opruimjob en de fake.**
   - Schrijf `test_jobs_sessions.py` en de vier nieuwe tests in `test_fakes.py` (rood).
   - Maak `purge_expired_sessions` af in `shakka/jobs/sessions.py`, en voeg aan `fakes.py` de cascade `sessions` → `rsvps`, `_builtin_rpcs` en `_purge_expired_sessions` toe.
   - `uv run pytest` groen. Commit.
4. **Pipelinestap.**
   - Pas de tests in `test_pipeline.py` en `test_cli_pipeline.py` aan en voeg de nieuwe tests toe (rood).
   - Voeg `step_sessions_cleanup`, `STEP_NAMES`, `STEPS` en de docstring toe in `pipeline.py`.
   - `uv run pytest tests/test_pipeline.py` (AC-7) en de volledige suite groen; `uv run ruff check . && uv run ruff format --check .` schoon. Commit.
5. **RUNBOOK.** §8.6, §13.1 en §16, zoals onder Interfaces. Commit `docs(WP-19): runbook for sessions`.
6. **Eindcontrole.**
   - `supabase db reset && supabase test db` groen.
   - `cd ingest && uv run pytest` groen, ruff schoon.
   - `grep -rn "rsvps" supabase/migrations | grep -i grant` toont alleen commentaar.
   - `git diff --stat` raakt geen bestanden buiten de tabel "Bestanden".
