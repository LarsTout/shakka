-- WP-25: organizer moderation. An organizer closes and reopens sign-ups on an own session
-- (rsvps_closed_at) and removes any RSVP on an own session (organizer_delete_rsvp).
-- Closing only blocks new RSVPs; edits and sign-offs with a valid token keep working.

alter table public.sessions add column rsvps_closed_at timestamptz null;
grant update (rsvps_closed_at) on table public.sessions to authenticated;

-- Public view of one session by slug. Never organizer_id, tokens, hashes or e-mail addresses.
create or replace function public.get_public_session(p_slug text)
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
      'cancelled', s.cancelled_at is not null,
      'rsvps_closed', s.rsvps_closed_at is not null
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
create or replace function public.rsvp_create(
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
  if not found or s.cancelled_at is not null or s.rsvps_closed_at is not null
     or s.ends_at <= now() then
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
