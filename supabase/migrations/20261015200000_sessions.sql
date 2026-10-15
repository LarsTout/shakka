-- Sessions and RSVPs (WP-19).
-- Organizers (authenticated) manage their own sessions through RLS and column privileges.
-- RSVPs are only reachable through the security-definer RPCs in this file: no API role has any
-- privilege on public.rsvps. Retention: a session and, by cascade, its RSVPs are removed
-- 7 days after ends_at by purge_expired_sessions (pipeline step sessions_cleanup).
-- Errors raised here: SQLSTATE PT400 (PostgREST: HTTP 400) with message exactly one of
-- rate_limited, session_closed, session_full, invalid_input, invalid_token.

create extension if not exists pgcrypto with schema extensions;

-- rsvp_create calls extensions.gen_random_bytes. If pgcrypto already lives in another schema,
-- "if not exists" does nothing and the function would only fail at the first RSVP: fail here.
do $guard$
begin
  if not exists (
    select 1
      from pg_catalog.pg_extension e
      join pg_catalog.pg_namespace n on n.oid = e.extnamespace
     where e.extname = 'pgcrypto' and n.nspname = 'extensions'
  ) then
    raise exception 'pgcrypto must be installed in schema extensions';
  end if;
end;
$guard$;

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
  if not found then
    raise sqlstate 'PT400' using message = 'invalid_token';
  end if;
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
